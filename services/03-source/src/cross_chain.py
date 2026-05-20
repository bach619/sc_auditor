"""CrossChainCorrelator — Korelasi source code di berbagai chain.

Mencari kontrak dengan bytecode/source yang sama di chain berbeda
untuk deteksi fork, clone, dan multi-chain deployment.
"""

from __future__ import annotations

import hashlib
from typing import Any

import structlog

from src.storage import EnhancedJSONStorage

log = structlog.get_logger()


class CrossChainCorrelator:
    """Korelasi source code antar chain.

    Mencari kontrak yang sama (bytecode hash match) atau mirip
    (source similarity) di berbagai chain.

    Usage::

        correlator = CrossChainCorrelator(storage)
        siblings = await correlator.find_siblings("ethereum", "0x...")
        forks = await correlator.find_forks(source_hash)
    """

    def __init__(self, storage: EnhancedJSONStorage) -> None:
        self.storage = storage

    async def find_siblings(
        self,
        chain: str,
        address: str,
    ) -> list[dict[str, Any]]:
        """Cari kontrak dengan source yang sama di chain lain.

        Args:
            chain: Blockchain name.
            address: Contract address.

        Returns:
            List of sibling contracts.
        """
        source = self.storage.get_source(chain, address)
        if not source:
            return []

        # Compute source hash
        content = "".join(sorted(source.sources.values()))
        source_hash = hashlib.sha256(content.encode()).hexdigest()

        siblings: list[dict] = []
        all_contracts = self.storage.list_cached()

        for entry in all_contracts:
            addr = entry.get("address", "").lower()
            ch = entry.get("chain", "")

            # Skip self
            if ch == chain.lower() and addr == address.lower():
                continue

            # Get source and compare hash
            other_source = self.storage.get_source(ch, addr)
            if not other_source:
                continue

            other_content = "".join(sorted(other_source.sources.values()))
            other_hash = hashlib.sha256(other_content.encode()).hexdigest()

            if other_hash == source_hash:
                siblings.append({
                    "chain": ch,
                    "address": addr,
                    "compiler_version": other_source.compiler_version,
                    "provider": other_source.provider,
                    "match_type": "exact",
                    "similarity": 1.0,
                    "estimated_relation": "same_deployment",
                })

        return siblings

    async def find_forks(
        self,
        source_hash: str,
        exclude: tuple[str, str] | None = None,
        threshold: float = 0.8,
    ) -> list[dict[str, Any]]:
        """Cari fork/salinan kontrak berdasarkan source hash.

        Args:
            source_hash: SHA-256 hash dari source content.
            exclude: (chain, address) tuple untuk exclude self.
            threshold: Minimum similarity threshold.

        Returns:
            List of fork contracts.
        """
        forks: list[dict] = []
        all_contracts = self.storage.list_cached()

        for entry in all_contracts:
            ch = entry.get("chain", "")
            addr = entry.get("address", "")

            # Skip excluded
            if exclude and ch == exclude[0].lower() and addr == exclude[1].lower():
                continue

            other_source = self.storage.get_source(ch, addr)
            if not other_source:
                continue

            other_content = "".join(sorted(other_source.sources.values()))
            other_hash = hashlib.sha256(other_content.encode()).hexdigest()

            # Compute simple similarity
            if other_hash == source_hash:
                similarity = 1.0
                relation = "exact_fork"
            else:
                # Simple character-level similarity
                len1 = len(source_hash)
                len2 = len(other_hash)
                if len1 == 0 or len2 == 0:
                    continue
                matches = sum(1 for a, b in zip(source_hash, other_hash) if a == b)
                similarity = matches / max(len1, len2)
                relation = "similar" if similarity >= threshold else "different"

            if similarity >= threshold:
                forks.append({
                    "chain": ch,
                    "address": addr,
                    "compiler_version": other_source.compiler_version,
                    "provider": other_source.provider,
                    "similarity": round(similarity, 4),
                    "estimated_relation": relation,
                })

        # Sort by similarity descending
        forks.sort(key=lambda x: x["similarity"], reverse=True)
        return forks
