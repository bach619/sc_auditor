"""SourceDetector — orchestrates multiple providers to fetch and cache contract source code.

Manages providers in priority order, caches results on disk under
``/data/source/contracts/{chain}/{address}/``, and provides a unified
interface for the REST endpoints.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from src.models import SourceResult
from src.providers import SourceProvider
from src.providers.blockscout import BlockscoutProvider
from src.providers.etherscan import EtherscanProvider
from src.providers.fork_aware import ForkAwareGitHubProvider
from src.providers.github import GitHubProvider
from src.providers.sourcify import SourcifyProvider

log = structlog.get_logger()

# ── Constants ──────────────────────────────────────────────

DATA_DIR = Path(os.getenv("DATA_DIR", "/data/source"))
CONTRACTS_DIR = DATA_DIR / "contracts"

# Default provider priority order (fork_aware first!)
DEFAULT_PROVIDERS: list[str] = [
    "fork_aware_github",  # Cek fork dulu sebelum search global
    "etherscan",
    "sourcify",
    "blockscout",
    "github",             # Fallback GitHub search biasa
]

# Provider instances indexed by name
_PROVIDER_REGISTRY: dict[str, SourceProvider] = {
    "fork_aware_github": ForkAwareGitHubProvider(),
    "etherscan": EtherscanProvider(),
    "sourcify": SourcifyProvider(),
    "blockscout": BlockscoutProvider(),
    "github": GitHubProvider(),
}


# ── JSON helpers (atomic write) ───────────────────────────


def _write_json(path: Path, data: Any) -> bool:
    """Write JSON atomically: write .tmp then rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, default=str)
        tmp.replace(path)
        return True
    except OSError as exc:
        log.error("detector.write_failed", path=str(path), error=str(exc))
        if tmp.exists():
            tmp.unlink()
        return False


def _read_json(path: Path) -> Any:
    """Read JSON file, return None if missing or invalid."""
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("detector.read_failed", path=str(path), error=str(exc))
        return None


# ── SourceDetector ─────────────────────────────────────────


class SourceDetector:
    """Orchestrates source fetching across multiple providers with disk caching.

    Cached structure on disk::

        /data/source/contracts/{chain}/{address}/
            metadata.json    # {chain, address, provider, fetched_at, compiler_version, ...}
            sources/
                Contract.sol
                ...

    Usage::

        detector = SourceDetector()
        result = await detector.fetch("ethereum", "0x...")
    """

    def __init__(self) -> None:
        """Initialize the detector and ensure data directories exist."""
        CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)
        log.info("detector.initialized", data_dir=str(DATA_DIR))

    # ── Public API ──────────────────────────────────────────

    async def fetch(
        self,
        chain: str,
        address: str,
        providers: list[str] | None = None,
    ) -> SourceResult | None:
        """Try providers in order until one succeeds.

        Args:
            chain: Blockchain name.
            address: Contract address.
            providers: Ordered list of provider names to try.
                       Defaults to ``DEFAULT_PROVIDERS``.

        Returns:
            The first successful ``SourceResult``, or ``None`` if all fail.
        """
        provider_names = providers or DEFAULT_PROVIDERS
        addr_key = address.lower()

        for name in provider_names:
            provider = _PROVIDER_REGISTRY.get(name)
            if not provider:
                log.warning("detector.unknown_provider", provider=name)
                continue

            log.info("detector.trying_provider", provider=name, chain=chain, address=addr_key)
            try:
                result = await provider.fetch(chain, addr_key)
            except Exception as exc:
                log.error("detector.provider_error", provider=name, chain=chain, address=addr_key, error=str(exc))
                continue

            if result is not None:
                log.info("detector.provider_success", provider=name, chain=chain, address=addr_key)
                # Cache the result
                self.cache_source(chain, addr_key, result)
                return result

        log.info("detector.all_providers_failed", chain=chain, address=addr_key)
        return None

    def get_cached(self, chain: str, address: str) -> SourceResult | None:
        """Return cached source for a contract, or None if not cached.

        Args:
            chain: Blockchain name.
            address: Contract address.

        Returns:
            ``SourceResult`` from cache, or ``None`` if not found.
        """
        contract_dir = CONTRACTS_DIR / chain.lower() / address.lower()
        if not contract_dir.is_dir():
            return None

        metadata = _read_json(contract_dir / "metadata.json")
        if not metadata:
            return None

        sources_dir = contract_dir / "sources"
        if not sources_dir.is_dir():
            return None

        sources: dict[str, str] = {}
        for sol_file in sorted(sources_dir.iterdir()):
            if sol_file.suffix == ".sol" and sol_file.is_file():
                try:
                    sources[sol_file.name] = sol_file.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    log.warning("detector.cache_read_error", path=str(sol_file), error=str(exc))

        if not sources:
            return None

        return SourceResult(
            sources=sources,
            compiler_version=metadata.get("compiler_version", ""),
            license=metadata.get("license"),
            provider=metadata.get("provider", "unknown"),
            constructor_args=metadata.get("constructor_args"),
        )

    def cache_source(self, chain: str, address: str, source: SourceResult) -> None:
        """Persist a ``SourceResult`` to disk under ``CONTRACTS_DIR``.

        Structure::

            {chain}/{address}/
                metadata.json
                sources/{filename}
        """
        base = CONTRACTS_DIR / chain.lower() / address.lower()
        sources_dir = base / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)

        # Write individual source files
        for filename, content in source.sources.items():
            # Sanitise filename — avoid path traversal
            safe_name = filename.replace("/", "_").replace("\\", "_")
            file_path = sources_dir / safe_name
            try:
                file_path.write_text(content, encoding="utf-8")
            except OSError as exc:
                log.error("detector.cache_write_error", path=str(file_path), error=str(exc))

        # Write metadata
        metadata = {
            "chain": chain.lower(),
            "address": address.lower(),
            "provider": source.provider,
            "compiler_version": source.compiler_version,
            "license": source.license,
            "constructor_args": source.constructor_args,
            "file_count": len(source.sources),
            "files": list(source.sources.keys()),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_json(base / "metadata.json", metadata)

        log.info(
            "detector.cached",
            chain=chain,
            address=address,
            provider=source.provider,
            files=len(source.sources),
        )

    def clear_cache(self, chain: str, address: str) -> bool:
        """Remove cached source for a contract.

        Args:
            chain: Blockchain name.
            address: Contract address.

        Returns:
            True if cache existed and was removed, False otherwise.
        """
        contract_dir = CONTRACTS_DIR / chain.lower() / address.lower()
        if not contract_dir.is_dir():
            return False

        shutil.rmtree(contract_dir)
        log.info("detector.cache_cleared", chain=chain, address=address)
        return True

    def list_providers(self) -> list[dict[str, Any]]:
        """Return metadata about all registered providers.

        Each entry contains: ``name``, ``available``, ``priority``.

        ``available`` is always ``True`` for now — we could ping each
        provider in the future for a live health check.
        """
        results: list[dict[str, Any]] = []
        for idx, (name, provider) in enumerate(_PROVIDER_REGISTRY.items()):
            results.append({
                "name": provider.name,
                "available": True,
                "priority": idx,
            })
        return results

    def count_cached(self) -> int:
        """Count the number of cached contracts on disk."""
        if not CONTRACTS_DIR.is_dir():
            return 0
        count = 0
        for chain_dir in CONTRACTS_DIR.iterdir():
            if chain_dir.is_dir():
                for addr_dir in chain_dir.iterdir():
                    if addr_dir.is_dir() and (addr_dir / "metadata.json").exists():
                        count += 1
        return count
