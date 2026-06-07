"""EnhancedJSONStorage — Source code cache dengan indexing, history, dan atomic operations.

Menggantikan cache flat file sebelumnya dengan struktur multi-file + index.
Semua data tetap 100% JSON file-based (VYPER.md philosophy).

Struktur direktori::

    /data/source/
    ├── contracts/{chain}/{address}/
    │       metadata.json          # Metadata kontrak
    │       sources/*.sol          # Source files
    │       abi.json               # Extracted ABI (Level 2)
    ├── indexes/
    │       by_chain.json          # chain → [{address, name, compiler}, ...]
    │       by_provider.json       # provider → [address_key, ...]
    │       by_compiler.json       # version → [address_key, ...]
    │       by_bytecode_hash.json  # hash → [address_key, ...]
    ├── history/
    │       {chain}_{address}.jsonl # Append-only log perubahan (JSON Lines)
    └── _meta.json                 # Schema version, stats
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from src.models import ContractMetadata, SourceResult

log = structlog.get_logger()

SCHEMA_VERSION = "2.0"


# ── JSON Helpers ────────────────────────────────────────────


def _write_json(path: Path, data: Any) -> bool:
    """Write JSON atomically: write .tmp then rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        tmp.replace(path)
        return True
    except OSError as exc:
        log.error("storage.write_failed", path=str(path), error=str(exc))
        if tmp.exists():
            tmp.unlink()
        return False


def _read_json(path: Path) -> Any:
    """Read JSON file, return None if missing or invalid."""
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("storage.read_failed", path=str(path), error=str(exc))
        return None


def _content_hash(content: str) -> str:
    """SHA-256 hash of source content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ── EnhancedJSONStorage ─────────────────────────────────────


class EnhancedJSONStorage:
    """JSON storage with indexing, history, and atomic operations.

    Usage::

        storage = EnhancedJSONStorage()
        storage.save_source("ethereum", "0x...", result)
        cached = storage.get_source("ethereum", "0x...")
        stats = storage.get_cache_stats()
    """

    def __init__(self, data_dir: str | Path | None = None) -> None:
        """Initialize storage with an optional data directory.

        Args:
            data_dir: Root directory for storage.
                      Defaults to ``DATA_DIR`` env var, or ``/tmp/sc_auditor_data``.
        """
        if data_dir is None:
            data_dir = os.getenv("DATA_DIR", "/tmp/sc_auditor_data")
        base = Path(data_dir) / "source"
        self.contracts_dir = base / "contracts"
        self.indexes_dir = base / "indexes"
        self.history_dir = base / "history"
        self.meta_path = base / "_meta.json"

        for d in [self.contracts_dir, self.indexes_dir, self.history_dir]:
            d.mkdir(parents=True, exist_ok=True)
        self._init_meta()

    # ── Metadata ────────────────────────────────────────────

    def _init_meta(self) -> None:
        """Initialize metadata file if it doesn't exist."""
        if not self.meta_path.exists():
            self._write_meta(
                schema_version=SCHEMA_VERSION,
                created_at=datetime.now(UTC).isoformat(),
                last_updated=datetime.now(UTC).isoformat(),
                total_contracts=0,
            )

    def _read_meta(self) -> dict[str, Any]:
        """Read metadata file."""
        meta = _read_json(self.meta_path)
        if not meta:
            return {"schema_version": SCHEMA_VERSION}
        return meta

    def _write_meta(self, **kwargs: Any) -> None:
        """Update metadata file."""
        meta = self._read_meta()
        meta.update(kwargs)
        meta["last_updated"] = datetime.now(UTC).isoformat()
        _write_json(self.meta_path, meta)

    # ── Contract Path Helpers ───────────────────────────────

    def _contract_dir(self, chain: str, address: str) -> Path:
        return self.contracts_dir / chain.lower() / address.lower()

    def _sources_dir(self, chain: str, address: str) -> Path:
        return self._contract_dir(chain, address) / "sources"

    def _metadata_path(self, chain: str, address: str) -> Path:
        return self._contract_dir(chain, address) / "metadata.json"

    def _abi_path(self, chain: str, address: str) -> Path:
        return self._contract_dir(chain, address) / "abi.json"

    def _history_path(self, chain: str, address: str) -> Path:
        return self.history_dir / f"{chain.lower()}_{address.lower()}.jsonl"

    def _address_key(self, chain: str, address: str) -> str:
        return f"{chain.lower()}:{address.lower()}"

    # ── Save Source ─────────────────────────────────────────

    def save_source(self, chain: str, address: str, source: SourceResult) -> bool:
        """Save source result to disk with metadata.

        Returns True if saved successfully.
        """
        chain_l = chain.lower()
        addr_l = address.lower()
        self._contract_dir(chain_l, addr_l)
        sources_dir = self._sources_dir(chain_l, addr_l)
        sources_dir.mkdir(parents=True, exist_ok=True)

        # Write individual source files
        for filename, content in source.sources.items():
            safe_name = filename.replace("/", "_").replace("\\", "_")
            file_path = sources_dir / safe_name
            try:
                file_path.write_text(content, encoding="utf-8")
            except OSError as exc:
                log.error("storage.source_write_error", path=str(file_path), error=str(exc))
                return False

        # Compute source hash
        all_content = "".join(sorted(source.sources.values()))
        source_hash = _content_hash(all_content)

        # Write metadata
        file_list = list(source.sources.keys())
        metadata = {
            "chain": chain_l,
            "address": addr_l,
            "provider": source.provider,
            "compiler_version": source.compiler_version,
            "license": source.license,
            "constructor_args": source.constructor_args,
            "file_count": len(source.sources),
            "files": file_list,
            "source_hash": source_hash,
            "lines_of_code": sum(len(c.splitlines()) for c in source.sources.values()),
            "fetched_at": datetime.now(UTC).isoformat(),
            "fetch_count": 1,
        }

        # Check if this is an update (already cached)
        existing = _read_json(self._metadata_path(chain_l, addr_l))
        if existing:
            metadata["fetch_count"] = existing.get("fetch_count", 0) + 1
            # Track upgrade if source changed
            if existing.get("source_hash") and existing["source_hash"] != source_hash:
                self._append_history(chain_l, addr_l, {
                    "event": "source_updated",
                    "old_hash": existing["source_hash"],
                    "new_hash": source_hash,
                    "old_provider": existing.get("provider"),
                    "new_provider": source.provider,
                    "timestamp": datetime.now(UTC).isoformat(),
                })
                metadata["upgrade_count"] = existing.get("upgrade_count", 0) + 1
            else:
                metadata["upgrade_count"] = existing.get("upgrade_count", 0)
            # Preserve original fetch time
            metadata["first_fetched_at"] = existing.get("first_fetched_at", metadata["fetched_at"])
        else:
            metadata["first_fetched_at"] = metadata["fetched_at"]
            metadata["upgrade_count"] = 0

        ok_ = _write_json(self._metadata_path(chain_l, addr_l), metadata)

        # Update indexes
        if ok_:
            self._update_indexes(chain_l, addr_l, metadata)
            if not existing:
                self._update_total_count(1)
            log.info(
                "storage.saved",
                chain=chain_l,
                address=addr_l,
                provider=source.provider,
                files=len(source.sources),
                is_update=bool(existing),
            )

        return ok_

    # ── Get Source ──────────────────────────────────────────

    def get_source(self, chain: str, address: str) -> SourceResult | None:
        """Return cached source for a contract, or None if not cached."""
        metadata = _read_json(self._metadata_path(chain, address))
        if not metadata:
            return None

        sources_dir = self._sources_dir(chain, address)
        if not sources_dir.is_dir():
            return None

        sources: dict[str, str] = {}
        for sol_file in sorted(sources_dir.iterdir()):
            if sol_file.suffix == ".sol" and sol_file.is_file():
                try:
                    sources[sol_file.name] = sol_file.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    log.warning("storage.read_error", path=str(sol_file), error=str(exc))

        if not sources:
            return None

        return SourceResult(
            sources=sources,
            compiler_version=metadata.get("compiler_version", ""),
            license=metadata.get("license"),
            provider=metadata.get("provider", "unknown"),
            constructor_args=metadata.get("constructor_args"),
        )

    def get_metadata(self, chain: str, address: str) -> ContractMetadata | None:
        """Return only metadata (without source content)."""
        meta = _read_json(self._metadata_path(chain, address))
        if not meta:
            return None
        return ContractMetadata(
            chain=meta.get("chain", chain),
            address=meta.get("address", address),
            provider=meta.get("provider", ""),
            compiler_version=meta.get("compiler_version", ""),
            license=meta.get("license"),
            constructor_args=meta.get("constructor_args"),
            file_count=meta.get("file_count", 0),
            files=meta.get("files", []),
            fetched_at=meta.get("fetched_at", ""),
            source_hash=meta.get("source_hash"),
            lines_of_code=meta.get("lines_of_code", 0),
            upgrade_count=meta.get("upgrade_count", 0),
        )

    # ── History ─────────────────────────────────────────────

    def _append_history(self, chain: str, address: str, entry: dict) -> None:
        """Append an entry to the contract's JSON Lines history file."""
        path = self._history_path(chain, address)
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError as exc:
            log.warning("storage.history_write_error", path=str(path), error=str(exc))

    def get_history(self, chain: str, address: str, limit: int = 50) -> list[dict]:
        """Read last N history entries (reverse chronological)."""
        path = self._history_path(chain, address)
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8").strip().split("\n")
            return [json.loads(l) for l in lines[-limit:][::-1]]
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("storage.history_read_error", path=str(path), error=str(exc))
            return []

    # ── Indexes ─────────────────────────────────────────────

    def _update_indexes(self, chain: str, address: str, metadata: dict) -> None:
        """Update all indexes with new contract data."""
        addr_key = self._address_key(chain, address)
        entry = {
            "address": address,
            "name": metadata.get("name", ""),
            "compiler_version": metadata.get("compiler_version", ""),
            "provider": metadata.get("provider", ""),
            "fetched_at": metadata.get("fetched_at", ""),
        }

        # By chain
        by_chain = _read_json(self.indexes_dir / "by_chain.json") or {}
        chain_list = by_chain.setdefault(chain, [])
        # Remove old entry if exists, add new
        chain_list[:] = [e for e in chain_list if e.get("address", "").lower() != address.lower()]
        chain_list.append(entry)
        _write_json(self.indexes_dir / "by_chain.json", by_chain)

        # By provider
        by_provider = _read_json(self.indexes_dir / "by_provider.json") or {}
        provider = metadata.get("provider", "unknown")
        prov_list = by_provider.setdefault(provider, [])
        if addr_key not in prov_list:
            prov_list.append(addr_key)
        _write_json(self.indexes_dir / "by_provider.json", by_provider)

        # By compiler
        by_compiler = _read_json(self.indexes_dir / "by_compiler.json") or {}
        compiler = metadata.get("compiler_version", "unknown")
        comp_list = by_compiler.setdefault(compiler, [])
        if addr_key not in comp_list:
            comp_list.append(addr_key)
        _write_json(self.indexes_dir / "by_compiler.json", by_compiler)

    def _update_total_count(self, delta: int = 1) -> None:
        """Update total contract count in metadata."""
        meta = self._read_meta()
        meta["total_contracts"] = meta.get("total_contracts", 0) + delta
        self._write_meta(**meta)

    # ── Search ──────────────────────────────────────────────

    def search_contracts(
        self,
        query: str | None = None,
        chain: str | None = None,
        provider: str | None = None,
        compiler: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search cached contracts by various filters."""

        # Determine which contracts to scan
        if chain:
            by_chain = _read_json(self.indexes_dir / "by_chain.json") or {}
            candidates = by_chain.get(chain, [])
        else:
            # Scan all contracts
            by_chain = _read_json(self.indexes_dir / "by_chain.json") or {}
            candidates = []
            for clist in by_chain.values():
                candidates.extend(clist)

        # Deduplicate by address
        seen: set[str] = set()
        unique: list[dict] = []
        for c in candidates:
            key = c.get("address", "").lower()
            if key not in seen:
                seen.add(key)
                unique.append(c)

        # Filter by provider
        if provider:
            unique = [c for c in unique if c.get("provider", "").lower() == provider.lower()]

        # Filter by compiler
        if compiler:
            unique = [c for c in unique if compiler in c.get("compiler_version", "")]

        # Filter by text query (search in metadata + source)
        if query:
            q = query.lower()
            filtered = []
            for c in unique:
                if q in c.get("address", "").lower() or q in c.get("name", "").lower():
                    filtered.append(c)
                    continue
                # Try searching in source content (expensive)
                addr = c.get("address", "")
                ch = c.get("chain", chain or "")
                if ch and addr:
                    src = self.get_source(ch, addr)
                    if src:
                        all_text = " ".join(src.sources.values())
                        if q in all_text.lower():
                            filtered.append(c)
                            continue
            unique = filtered

        # Sort by fetched_at descending
        unique.sort(key=lambda x: x.get("fetched_at", ""), reverse=True)

        # Apply limit
        return unique[:limit]

    # ── Cache Stats ─────────────────────────────────────────

    def get_cache_stats(self) -> dict[str, Any]:
        """Compute comprehensive cache statistics."""
        meta = self._read_meta()
        stats: dict[str, Any] = {
            "total_contracts": meta.get("total_contracts", 0),
            "total_files": 0,
            "total_lines": 0,
            "by_chain": {},
            "by_provider": {},
            "by_compiler": {},
            "cache_size_bytes": 0,
            "oldest_entry": None,
            "newest_entry": None,
        }

        oldest: str | None = None
        newest: str | None = None

        if not self.contracts_dir.is_dir():
            return stats

        for chain_dir in self.contracts_dir.iterdir():
            if not chain_dir.is_dir():
                continue
            chain_name = chain_dir.name
            chain_count = 0

            for addr_dir in chain_dir.iterdir():
                if not addr_dir.is_dir():
                    continue
                meta_path = addr_dir / "metadata.json"
                if not meta_path.exists():
                    continue

                metadata = _read_json(meta_path)
                if not metadata:
                    continue

                chain_count += 1
                stats["total_files"] += metadata.get("file_count", 0)
                stats["total_lines"] += metadata.get("lines_of_code", 0)

                # Provider count
                prov = metadata.get("provider", "unknown")
                stats["by_provider"][prov] = stats["by_provider"].get(prov, 0) + 1

                # Compiler count
                comp = metadata.get("compiler_version", "unknown")
                stats["by_compiler"][comp] = stats["by_compiler"].get(comp, 0) + 1

                # Entry age
                ft = metadata.get("fetched_at", "")
                if ft:
                    if oldest is None or ft < oldest:
                        oldest = ft
                    if newest is None or ft > newest:
                        newest = ft

                # Calculate directory size
                try:
                    for f in addr_dir.rglob("*"):
                        if f.is_file():
                            stats["cache_size_bytes"] += f.stat().st_size
                except OSError:
                    pass

            if chain_count > 0:
                stats["by_chain"][chain_name] = chain_count

        stats["oldest_entry"] = oldest
        stats["newest_entry"] = newest
        return stats

    # ── Clear Cache ─────────────────────────────────────────

    def clear_cache(self, chain: str, address: str) -> bool:
        """Remove cached source for a contract."""
        contract_dir = self._contract_dir(chain, address)
        if not contract_dir.is_dir():
            return False

        shutil.rmtree(contract_dir)
        log.info("storage.cache_cleared", chain=chain, address=address)
        self._update_total_count(-1)

        # Remove from indexes (rebuild approach)
        self._rebuild_indexes()
        return True

    def _rebuild_indexes(self) -> None:
        """Rebuild all indexes from scratch (after removal)."""
        by_chain: dict[str, list[dict]] = {}
        by_provider: dict[str, list[str]] = {}
        by_compiler: dict[str, list[str]] = {}
        total = 0

        if self.contracts_dir.is_dir():
            for chain_dir in self.contracts_dir.iterdir():
                if not chain_dir.is_dir():
                    continue
                chain_name = chain_dir.name
                for addr_dir in chain_dir.iterdir():
                    if not addr_dir.is_dir():
                        continue
                    meta = _read_json(addr_dir / "metadata.json")
                    if not meta:
                        continue
                    total += 1
                    addr_key = f"{chain_name}:{meta.get('address', addr_dir.name)}"

                    entry = {
                        "address": meta.get("address", addr_dir.name),
                        "name": meta.get("name", ""),
                        "compiler_version": meta.get("compiler_version", ""),
                        "provider": meta.get("provider", ""),
                        "fetched_at": meta.get("fetched_at", ""),
                    }
                    by_chain.setdefault(chain_name, []).append(entry)

                    prov = meta.get("provider", "unknown")
                    by_provider.setdefault(prov, []).append(addr_key)

                    comp = meta.get("compiler_version", "unknown")
                    by_compiler.setdefault(comp, []).append(addr_key)

        _write_json(self.indexes_dir / "by_chain.json", by_chain)
        _write_json(self.indexes_dir / "by_provider.json", by_provider)
        _write_json(self.indexes_dir / "by_compiler.json", by_compiler)
        self._write_meta(total_contracts=total)

    # ── Exists Check ────────────────────────────────────────

    def exists(self, chain: str, address: str) -> bool:
        """Check if a contract is cached."""
        return self._metadata_path(chain, address).exists()

    # ── List All Cached ─────────────────────────────────────

    def list_cached(self, chain: str | None = None) -> list[dict]:
        """List all cached contracts with basic metadata."""
        by_chain = _read_json(self.indexes_dir / "by_chain.json") or {}
        if chain:
            return by_chain.get(chain.lower(), [])
        result = []
        for clist in by_chain.values():
            result.extend(clist)
        return result

    # ── Count Cached ────────────────────────────────────────

    def count_cached(self) -> int:
        """Count total cached contracts."""
        meta = self._read_meta()
        return meta.get("total_contracts", 0)

    # ── Save ABI (Level 2) ──────────────────────────────────

    def save_abi(self, chain: str, address: str, abi_data: list | dict) -> bool:
        """Save extracted ABI for a contract."""
        return _write_json(self._abi_path(chain, address), abi_data)

    def get_abi(self, chain: str, address: str) -> list | dict | None:
        """Get cached ABI for a contract."""
        return _read_json(self._abi_path(chain, address))

    def has_abi(self, chain: str, address: str) -> bool:
        """Check if ABI exists for a contract."""
        return self._abi_path(chain, address).exists()
