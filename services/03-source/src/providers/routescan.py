"""RoutescanProvider — Fetch verified source via Routescan (multi-chain explorer).

Routescan mendukung: arbitrum, optimism, polygon, bsc, avalanche, base,
celo, gnosis, fantom, moonbeam, cronos, dan banyak chain EVM lainnya.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

from vyper_lib.utils import parse_standard_input_json
from src.models import SourceResult
from src.providers import SourceProvider

log = structlog.get_logger()

ROUTESCAN_API = "https://api.routescan.io/v1"
CHAIN_IDS: dict[str, int] = {
    "arbitrum": 42161,
    "optimism": 10,
    "polygon": 137,
    "bsc": 56,
    "avalanche": 43114,
    "base": 8453,
    "celo": 42220,
    "gnosis": 100,
    "fantom": 250,
    "moonbeam": 1284,
    "cronos": 25,
    "linea": 59144,
    "scroll": 534352,
    "blast": 81457,
    "mantle": 5000,
}


class RoutescanProvider:
    """Source provider for Routescan (multi-chain explorer)."""

    name = "routescan"

    async def fetch(self, chain: str, address: str) -> SourceResult | None:
        """Fetch verified source code via Routescan API.

        Args:
            chain: Blockchain name (harus ada di CHAIN_IDS).
            address: Contract address.

        Returns:
            SourceResult jika terverifikasi, None jika tidak.
        """
        chain_id = CHAIN_IDS.get(chain.lower())
        if not chain_id:
            log.warning("routescan.unsupported_chain", chain=chain)
            return None

        url = f"{ROUTESCAN_API}/contract/{chain_id}/address/{address}/verification"

        async with httpx.AsyncClient(timeout=30.0) as client:
            log.info("routescan.fetch", chain=chain, address=address)
            try:
                resp = await client.get(url)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
            except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as exc:
                log.warning("routescan.request_failed", chain=chain, address=address, error=str(exc))
                return None

        if not data.get("verified"):
            return None

        # Parse source code
        source_raw = data.get("sourceCode", "") or data.get("source_code", "")
        if not source_raw:
            return None

        sources: dict[str, str] = {}
        parsed = parse_standard_input_json(source_raw)
        if parsed is not None:
            sources = parsed
        else:
            sources["Contract.sol"] = source_raw

        if not sources:
            return None

        compiler_version = (data.get("compilerVersion", "") or data.get("compiler_version", "")).lstrip("v")
        license_ = data.get("license") or None

        return SourceResult(
            sources=sources,
            compiler_version=compiler_version,
            license=license_,
            provider=self.name,
            constructor_args=None,
        )
