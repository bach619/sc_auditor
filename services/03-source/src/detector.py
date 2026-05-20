"""SourceDetector — orchestrates multiple providers to fetch and cache contract source code.

Menggunakan EnhancedJSONStorage untuk caching dengan indexing, history,
dan atomic operations. Mendukung 10+ provider untuk berbagai chain.
"""

from __future__ import annotations

from typing import Any

import structlog

from src.models import ContractMetadata, SourceResult
from src.providers import SourceProvider
from src.providers.blockscout import BlockscoutProvider
from src.providers.etherscan import EtherscanProvider
from src.providers.etherscan_chain import EtherscanChainProvider
from src.providers.eth_call import EthCallProvider
from src.providers.fork_aware import ForkAwareGitHubProvider
from src.providers.github import GitHubProvider
from src.providers.routescan import RoutescanProvider
from src.providers.sourcify import SourcifyProvider
from src.providers.zksync import ZkSyncProvider
from src.storage import EnhancedJSONStorage

log = structlog.get_logger()


# ── Provider Registry ──────────────────────────────────────

_PROVIDER_REGISTRY: dict[str, SourceProvider] = {}

# Fork-aware GitHub (prioritas tertinggi — cek fork dulu)
_PROVIDER_REGISTRY["fork_aware_github"] = ForkAwareGitHubProvider()

# Etherscan utama
_PROVIDER_REGISTRY["etherscan"] = EtherscanProvider()

# Etherscan chain-specific (generik untuk 6 chain)
_PROVIDER_REGISTRY["etherscan_arbitrum"] = EtherscanChainProvider("arbitrum")
_PROVIDER_REGISTRY["etherscan_optimism"] = EtherscanChainProvider("optimism")
_PROVIDER_REGISTRY["etherscan_polygon"] = EtherscanChainProvider("polygon")
_PROVIDER_REGISTRY["etherscan_bsc"] = EtherscanChainProvider("bsc")
_PROVIDER_REGISTRY["etherscan_avalanche"] = EtherscanChainProvider("avalanche")
_PROVIDER_REGISTRY["etherscan_base"] = EtherscanChainProvider("base")

# Specialized providers
_PROVIDER_REGISTRY["zksync"] = ZkSyncProvider()
_PROVIDER_REGISTRY["routescan"] = RoutescanProvider()

# Public explorers
_PROVIDER_REGISTRY["sourcify"] = SourcifyProvider()
_PROVIDER_REGISTRY["blockscout"] = BlockscoutProvider()

# GitHub fallback
_PROVIDER_REGISTRY["github"] = GitHubProvider()

# RPC fallback (terakhir — hanya bytecode)
_PROVIDER_REGISTRY["eth_call"] = EthCallProvider()

# Default provider priority order (highest to lowest priority)
DEFAULT_PROVIDERS: list[str] = [
    "fork_aware_github",
    "etherscan",
    "etherscan_arbitrum",
    "etherscan_optimism",
    "etherscan_polygon",
    "etherscan_bsc",
    "etherscan_avalanche",
    "etherscan_base",
    "zksync",
    "routescan",
    "sourcify",
    "blockscout",
    "github",
    "eth_call",
]


# ── SourceDetector ─────────────────────────────────────────


class SourceDetector:
    """Orchestrates source fetching across multiple providers with Enhanced JSON Storage.

    Usage::

        detector = SourceDetector()
        result = await detector.fetch("ethereum", "0x...")
        cached = detector.get_cached("ethereum", "0x...")
    """

    def __init__(
        self,
        storage: EnhancedJSONStorage | None = None,
        storage_override: str | None = None,
    ) -> None:
        """Initialize detector with Enhanced JSON Storage.

        Args:
            storage: Pre-configured storage instance.
            storage_override: Optional data directory path for new storage.
        """
        if storage:
            self.storage = storage
        else:
            self.storage = EnhancedJSONStorage(data_dir=storage_override) if storage_override else EnhancedJSONStorage()
        log.info(
            "detector.initialized",
            providers=len(_PROVIDER_REGISTRY),
            cached=self.storage.count_cached(),
        )

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
                log.error(
                    "detector.provider_error",
                    provider=name,
                    chain=chain,
                    address=addr_key,
                    error=str(exc),
                )
                continue

            if result is not None:
                log.info(
                    "detector.provider_success",
                    provider=name,
                    chain=chain,
                    address=addr_key,
                )
                # Cache using EnhancedJSONStorage
                self.storage.save_source(chain, addr_key, result)
                return result

        log.info("detector.all_providers_failed", chain=chain, address=addr_key)
        return None

    def get_cached(self, chain: str, address: str) -> SourceResult | None:
        """Return cached source for a contract, or None if not cached."""
        return self.storage.get_source(chain, address)

    def get_metadata(self, chain: str, address: str) -> ContractMetadata | None:
        """Return only metadata (without source content)."""
        return self.storage.get_metadata(chain, address)

    def cache_source(self, chain: str, address: str, source: SourceResult) -> None:
        """Persist a SourceResult to disk via EnhancedJSONStorage."""
        self.storage.save_source(chain, address, source)

    def clear_cache(self, chain: str, address: str) -> bool:
        """Remove cached source for a contract."""
        return self.storage.clear_cache(chain, address)

    def list_providers(self) -> list[dict[str, Any]]:
        """Return metadata about all registered providers."""
        results: list[dict[str, Any]] = []
        for idx, name in enumerate(DEFAULT_PROVIDERS):
            provider = _PROVIDER_REGISTRY.get(name)
            if provider:
                results.append({
                    "name": provider.name,
                    "available": True,
                    "priority": idx,
                })
        return results

    def count_cached(self) -> int:
        """Count the number of cached contracts."""
        return self.storage.count_cached()

    def get_cache_stats(self) -> dict[str, Any]:
        """Get comprehensive cache statistics."""
        return self.storage.get_cache_stats()

    def search_contracts(
        self,
        query: str | None = None,
        chain: str | None = None,
        provider: str | None = None,
        compiler: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search cached contracts by various filters."""
        return self.storage.search_contracts(
            query=query,
            chain=chain,
            provider=provider,
            compiler=compiler,
            limit=limit,
        )

    def list_cached(self, chain: str | None = None) -> list[dict]:
        """List all cached contracts with basic metadata."""
        return self.storage.list_cached(chain)

    def get_provider(self, name: str) -> SourceProvider | None:
        """Get a provider instance by name."""
        return _PROVIDER_REGISTRY.get(name)
