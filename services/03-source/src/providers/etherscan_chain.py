"""EtherscanChainProvider — Generic provider untuk semua chain Etherscan-like.

Mendukung chain-chain yang memiliki block explorer berbasis Etherscan API:
Arbitrum (Arbiscan), Optimism, Polygon (Polygonscan), BSC (BscScan),
Avalanche (Snowtrace), Base (Basescan).
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
from src.providers import SourceProvider

log = structlog.get_logger()

# ── Chain Config ───────────────────────────────────────────

CHAIN_CONFIGS: dict[str, dict[str, str]] = {
    "arbitrum": {
        "url": "https://api.arbiscan.io/api",
        "api_key_env": "ARBISCAN_API_KEY",
    },
    "optimism": {
        "url": "https://api-optimistic.etherscan.io/api",
        "api_key_env": "OPTIMISM_API_KEY",
    },
    "polygon": {
        "url": "https://api.polygonscan.com/api",
        "api_key_env": "POLYGONSCAN_API_KEY",
    },
    "bsc": {
        "url": "https://api.bscscan.com/api",
        "api_key_env": "BSCSCAN_API_KEY",
    },
    "avalanche": {
        "url": "https://api.snowtrace.io/api",
        "api_key_env": "SNOWTRACE_API_KEY",
    },
    "base": {
        "url": "https://api.basescan.org/api",
        "api_key_env": "BASESCAN_API_KEY",
    },
}

# Rate limit: 5 calls/second
_RATE_LIMIT_SLEEP = 0.21
_last_call: float = 0.0


async def _rate_limit() -> None:
    """Simple co-operative rate limiter."""
    global _last_call
    elapsed = time.monotonic() - _last_call
    if elapsed < _RATE_LIMIT_SLEEP:
        await asyncio.sleep(_RATE_LIMIT_SLEEP - elapsed)
    _last_call = time.monotonic()


class EtherscanChainProvider:
    """Generic Etherscan-like provider untuk berbagai chain.

    Satu instance per chain. Dibedakan dengan attribute ``name``.
    """

    def __init__(self, chain: str) -> None:
        """Initialize provider untuk chain tertentu.

        Args:
            chain: Nama chain (harus ada di CHAIN_CONFIGS).
        """
        self.chain = chain.lower()
        config = CHAIN_CONFIGS.get(self.chain)
        if not config:
            raise ValueError(f"Unsupported chain: {chain}. Supported: {list(CHAIN_CONFIGS.keys())}")

        self.base_url = config["url"]
        self._api_key_env = config["api_key_env"]

    @property
    def name(self) -> str:
        return f"etherscan_{self.chain}"

    @property
    def api_key(self) -> str:
        """Read API key from environment variable."""
        import os
        return os.getenv(self._api_key_env, "")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def fetch(self, chain: str, address: str) -> SourceResult | None:
        """Fetch verified source code via Etherscan-like API.

        Args:
            chain: Nama blockchain (harus match dengan chain instance ini).
            address: Contract address.

        Returns:
            SourceResult jika kontrak terverifikasi, None jika tidak.
        """
        if chain.lower() != self.chain:
            log.warning("etherscan_chain.chain_mismatch", expected=self.chain, got=chain)
            return None

        params: dict[str, str] = {
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
        }
        if self.api_key:
            params["apikey"] = self.api_key

        await _rate_limit()

        async with httpx.AsyncClient(timeout=30.0) as client:
            log.info("etherscan_chain.fetch", chain=self.chain, address=address, provider=self.name)
            try:
                resp = await client.get(self.base_url, params=params)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
            except (httpx.HTTPStatusError, httpx.RequestError, json.JSONDecodeError) as exc:
                log.warning("etherscan_chain.request_failed", chain=self.chain, address=address, error=str(exc))
                return None

        if data.get("status") != "1":
            log.info("etherscan_chain.not_verified", chain=self.chain, address=address)
            return None

        result = data.get("result")
        if not result or not isinstance(result, list) or len(result) == 0:
            return None

        contract = result[0]
        source_code_raw: str = (contract.get("SourceCode") or "").strip()
        if not source_code_raw:
            return None

        # Parse source code (single file or JSON standard input)
        sources: dict[str, str] = {}
        parsed_sources = parse_standard_input_json(source_code_raw)
        if parsed_sources is not None:
            sources = parsed_sources
        else:
            sources["Contract.sol"] = source_code_raw

        compiler_version: str = contract.get("CompilerVersion", "").lstrip("v")
        license_: str | None = contract.get("LicenseType") or None
        constructor_args: str | None = contract.get("ConstructorArguments") or None

        if constructor_args and constructor_args.strip() in ("", "-"):
            constructor_args = None

        return SourceResult(
            sources=sources,
            compiler_version=compiler_version,
            license=license_,
            provider=self.name,
            constructor_args=constructor_args,
        )
