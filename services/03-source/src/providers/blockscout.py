"""Blockscout provider — fetches verified source from Blockscout explorers.

Blockscout is an open-source block explorer. This provider supports
the hosted Blockscout instances for major chains.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from vyper_lib.utils import parse_standard_input_json
from src.models import SourceResult

log = structlog.get_logger()

# ── Chain → Blockscout URL mapping ────────────────────────

BLOCKSCOUT_URLS: dict[str, str] = {
    "ethereum": "https://eth.blockscout.com",
    "optimism": "https://optimism.blockscout.com",
    "polygon": "https://polygon.blockscout.com",
    "avalanche": "https://avalanche.blockscout.com",
    "base": "https://base.blockscout.com",
}


class BlockscoutProvider:
    """Source provider for Blockscout block explorers."""

    name = "blockscout"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def fetch(self, chain: str, address: str) -> SourceResult | None:
        """Fetch verified source code from Blockscout.

        Args:
            chain: Blockchain name. Must be in ``BLOCKSCOUT_URLS``.
            address: Contract address (0x-prefixed hex).

        Returns:
            SourceResult if the contract is verified, None otherwise.
        """
        base_url = BLOCKSCOUT_URLS.get(chain.lower())
        if not base_url:
            log.warning("blockscout.unsupported_chain", chain=chain)
            return None

        params: dict[str, str] = {
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
        }

        url = f"{base_url}/api"

        async with httpx.AsyncClient(timeout=30.0) as client:
            log.info("blockscout.fetch", chain=chain, address=address)
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 404:
                    log.info("blockscout.not_verified", chain=chain, address=address)
                    return None
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    return None
                log.warning("blockscout.http_error", chain=chain, address=address, status=exc.response.status_code)
                return None
            except (httpx.RequestError, json.JSONDecodeError) as exc:
                log.warning("blockscout.request_failed", chain=chain, address=address, error=str(exc))
                return None

        if data.get("status") != "1":
            log.info("blockscout.not_verified", chain=chain, address=address, message=data.get("message"))
            return None

        result = data.get("result")
        if not result or not isinstance(result, list) or len(result) == 0:
            return None

        contract = result[0]

        source_code_raw: str = (contract.get("SourceCode") or "").strip()
        if not source_code_raw:
            # Blockscout returns "SourceCode":"" when not verified
            return None

        sources: dict[str, str] = {}

        # Blockscout uses the same JSON standard-input format as Etherscan
        parsed_sources = parse_standard_input_json(source_code_raw)
        if parsed_sources is not None:
            sources = parsed_sources
        else:
            sources["Contract.sol"] = source_code_raw

        compiler_version: str = (contract.get("CompilerVersion") or "").lstrip("v")
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
