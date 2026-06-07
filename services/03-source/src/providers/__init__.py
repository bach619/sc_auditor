"""Provider base protocol and re-exports."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.models import SourceResult


@runtime_checkable
class SourceProvider(Protocol):
    """Protocol that every source provider must implement.

    All providers are async, accept ``chain`` and ``address``,
    and return a ``SourceResult`` or ``None`` if the contract
    is not verified on that provider.
    """

    name: str

    async def fetch(self, chain: str, address: str) -> SourceResult | None:
        ...


# Re-export all providers for easy import
from .blockscout import BlockscoutProvider
from .eth_call import EthCallProvider
from .etherscan import EtherscanProvider
from .etherscan_chain import EtherscanChainProvider
from .fork_aware import ForkAwareGitHubProvider
from .github import GitHubProvider
from .routescan import RoutescanProvider
from .sourcify import SourcifyProvider
from .zksync import ZkSyncProvider

__all__ = [
    "SourceProvider",
    "BlockscoutProvider",
    "EtherscanProvider",
    "EtherscanChainProvider",
    "EthCallProvider",
    "ForkAwareGitHubProvider",
    "GitHubProvider",
    "RoutescanProvider",
    "SourcifyProvider",
    "ZkSyncProvider",
]
