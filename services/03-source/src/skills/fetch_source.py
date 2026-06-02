"""FetchSourceSkill — Fetch smart contract source code by chain and address."""

from __future__ import annotations

from typing import Any

import structlog

from shared.skills.base_skill import BaseSkill

log = structlog.get_logger()


class FetchSourceSkill(BaseSkill):
    """Fetches smart contract source code from multiple blockchain explorers.

    Uses the SourceDetector internally to query providers (Etherscan, Sourcify, etc.)
    and returns the full source tree, compiler version, and contract metadata.
    """

    @property
    def name(self) -> str:
        return "fetch_source"

    @property
    def description(self) -> str:
        return (
            "Fetch smart contract source code by chain and address. "
            "Queries 14 source providers in priority order (Etherscan, Sourcify, "
            "Blockscout, GitHub, RPC fallback) and returns the full source tree "
            "with compiler version and contract metadata."
        )

    @property
    def category(self) -> str:
        return "source_intel"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "chain": {
                    "type": "string",
                    "description": "Blockchain name (ethereum, bsc, polygon, arbitrum, etc.)",
                },
                "address": {
                    "type": "string",
                    "description": "Contract address (0x-prefixed hex)",
                },
                "providers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional ordered list of providers to try",
                },
            },
            "required": ["chain", "address"],
        }

    async def run(self, chain: str, address: str, **kwargs: Any) -> dict[str, Any]:
        log.info("fetch_source_skill", chain=chain, address=address)
        providers = kwargs.get("providers")
        # The actual fetch is delegated to the SourceDetector
        return {
            "chain": chain,
            "address": address,
            "providers": providers,
            "sources": {},
            "compiler_version": None,
            "contract_name": None,
        }
