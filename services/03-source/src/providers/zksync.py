"""ZkSyncProvider — Fetch verified source from zkSync Era block explorer."""

from __future__ import annotations

import json

import httpx
import structlog

from src.models import SourceResult

log = structlog.get_logger()

ZKSYNC_API = "https://block-explorer-api.mainnet.zksync.io"
ZKSYNC_VERIFICATION_API = "https://zksync2-mainnet-explorer.zksync.io"


class ZkSyncProvider:
    """Source provider for zkSync Era."""

    name = "zksync"

    async def fetch(self, chain: str, address: str) -> SourceResult | None:
        """Fetch verified source code from zkSync explorer.

        Args:
            chain: Harus "zksync".
            address: Contract address.

        Returns:
            SourceResult jika terverifikasi, None jika tidak.
        """
        if chain.lower() not in ("zksync", "zksync_era", "era"):
            log.warning("zksync.unsupported_chain", chain=chain)
            return None

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Get contract info
            try:
                resp = await client.get(
                    f"{ZKSYNC_API}/api/v1/address/{address}",
                )
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                resp.json()
            except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as exc:
                log.warning("zksync.request_failed", address=address, error=str(exc))
                return None

            # Step 2: Try to get verification info
            try:
                verify_resp = await client.get(
                    f"{ZKSYNC_VERIFICATION_API}/contract_verification/info/{address}",
                )
                if verify_resp.status_code != 200:
                    return None
                verify_data = verify_resp.json()
            except (httpx.RequestError, json.JSONDecodeError):
                return None

        # Extract source code
        source_data = verify_data.get("source", {}) or verify_data
        sources: dict[str, str] = {}

        source_code = source_data.get("source_code", "")
        if source_code:
            # Try JSON multi-file format
            try:
                parsed = json.loads(source_code)
                if isinstance(parsed, dict):
                    for path, content in parsed.items():
                        if isinstance(content, str) and (path.endswith(".sol") or ".sol" in path):
                            sources[path] = content
            except (json.JSONDecodeError, TypeError):
                # Single file
                sources["Contract.sol"] = source_code

        if not sources:
            return None

        compiler_version = (source_data.get("compiler_version", "") or "").lstrip("v")
        license_ = source_data.get("license") or None

        return SourceResult(
            sources=sources,
            compiler_version=compiler_version,
            license=license_,
            provider=self.name,
            constructor_args=None,
        )
