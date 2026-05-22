"""Etherscan API provider — fetches verified source from Etherscan-like block explorers.

Supports: Ethereum, Arbitrum, Optimism, Polygon, BSC, Avalanche, Base.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from vyper_lib.utils import parse_standard_input_json
from src.models import SourceResult

log = structlog.get_logger()

# ── Chain → API URL mapping ───────────────────────────────

ETHERSCAN_URLS: dict[str, str] = {
    "ethereum": "https://api.etherscan.io",
    "arbitrum": "https://api.arbiscan.io",
    "optimism": "https://api-optimistic.etherscan.io",
    "polygon": "https://api.polygonscan.com",
    "bsc": "https://api.bscscan.com",
    "avalanche": "https://api.snowtrace.io",
    "base": "https://api.basescan.org",
}

# Rate limit: 5 calls/second for free tier
_RATE_LIMIT_SLEEP = 0.21  # slightly above 200ms to be safe
_last_call: float = 0.0


async def _rate_limit() -> None:
    """Simple co-operative rate limiter — sleeps if called too fast."""
    global _last_call
    elapsed = time.monotonic() - _last_call
    if elapsed < _RATE_LIMIT_SLEEP:
        await asyncio.sleep(_RATE_LIMIT_SLEEP - elapsed)
    _last_call = time.monotonic()


class EtherscanProvider:
    """Source provider for Etherscan and its chain-specific mirrors."""

    name = "etherscan"

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize provider.

        Args:
            api_key: Etherscan API key. If None, reads from env or uses a
                     default free-tier key. Rate limits apply without a key.
        """
        self.api_key = api_key or ""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def fetch(self, chain: str, address: str) -> SourceResult | None:
        """Fetch verified source code from Etherscan.

        Args:
            chain: Blockchain name. Must be in ``ETHERSCAN_URLS``.
            address: Contract address (0x-prefixed hex).

        Returns:
            SourceResult if the contract is verified, None otherwise.
        """
        base_url = ETHERSCAN_URLS.get(chain.lower())
        if not base_url:
            log.warning("etherscan.unsupported_chain", chain=chain)
            return None

        params: dict[str, str] = {
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
        }
        if self.api_key:
            params["apikey"] = self.api_key

        await _rate_limit()

        url = f"{base_url}/api"

        async with httpx.AsyncClient(timeout=30.0) as client:
            log.info("etherscan.fetch", chain=chain, address=address)
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
            except (httpx.HTTPStatusError, httpx.RequestError, json.JSONDecodeError) as exc:
                log.warning("etherscan.request_failed", chain=chain, address=address, error=str(exc))
                return None

        if data.get("status") != "1":
            log.info("etherscan.not_verified", chain=chain, address=address, message=data.get("result"))
            return None

        result = data.get("result")
        if not result or not isinstance(result, list) or len(result) == 0:
            return None

        contract = result[0]

        # Etherscan may return ABI-only entries (no source code)
        source_code_raw: str = (contract.get("SourceCode") or "").strip()
        if not source_code_raw:
            return None

        # SourceCode can be:
        #   1. Plain Solidity code (single file)
        #   2. JSON-encoded standard input JSON (multiple files)
        sources: dict[str, str] = {}

        parsed_sources = parse_standard_input_json(source_code_raw)
        if parsed_sources is not None:
            sources = parsed_sources
        else:
            # Plain single-file contract
            sources["Contract.sol"] = source_code_raw

        compiler_version: str = contract.get("CompilerVersion", "").lstrip("v")
        license_: str | None = contract.get("LicenseType") or None
        constructor_args: str | None = contract.get("ConstructorArguments") or None

        # Clean empty constructor args
        if constructor_args and constructor_args.strip() in ("", "-"):
            constructor_args = None

        return SourceResult(
            sources=sources,
            compiler_version=compiler_version,
            license=license_,
            provider=self.name,
            constructor_args=constructor_args,
        )
