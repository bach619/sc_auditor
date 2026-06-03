"""Skill: Fetch smart contract source code from multiple providers."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

from src.skills.base import BaseSkill

log = structlog.get_logger()

SOURCE_URL = "http://03-source:8000"
IMMUNEFI_URL = "http://02-immunefi:8000"

MAX_FETCH_RETRIES = 3


class FetchSourceSkill(BaseSkill):
    """Mengambil source code smart contract dari Etherscan, Sourcify, GitHub, dll."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client

    @property
    def name(self) -> str:
        return "fetch_source"

    @property
    def description(self) -> str:
        return (
            "Mengambil source code smart contract dari berbagai provider. "
            "Bisa fetch dari contract address + chain, atau dari URL GitHub. "
            "Hasilnya berupa file-file .sol beserta metadata compiler."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "address": {
                "type": "string",
                "description": "Contract address (0x...) — required jika fetch dari blockchain",
                "required": False,
            },
            "chain": {
                "type": "string",
                "description": "Chain name: ethereum, arbitrum, polygon, etc",
                "required": False,
            },
            "url": {
                "type": "string",
                "description": "URL GitHub atau Sourcify — alternatif dari address+chain",
                "required": False,
            },
            "program_slug": {
                "type": "string",
                "description": "Immunefi program slug — untuk ambil source dari repositori program",
                "required": False,
            },
        }

    async def _verify_address_for_program(
        self, address: str, program_slug: str
    ) -> dict[str, Any] | None:
        """Verify that an address belongs to a known Immunefi program.

        If program_slug is provided, checks against that program's contracts.

        Returns:
            Dict with match info if found/not-found, None if verification skipped.
        """
        if not program_slug:
            return None

        try:
            resp = await self._client.get(
                f"{IMMUNEFI_URL}/programs/{program_slug}/contracts"
            )
            if resp.status_code != 200:
                return None

            data = resp.json().get("data", {})
            contracts = data.get("contracts", [])

            address_lower = address.lower()
            for contract in contracts:
                if contract.get("address", "").lower() == address_lower:
                    return {
                        "match": True,
                        "program_slug": program_slug,
                        "contract_name": contract.get("name", ""),
                        "chain": contract.get("chain", ""),
                    }

            # No match found
            valid_addresses = [c.get("address", "") for c in contracts[:5]]
            return {
                "match": False,
                "program_slug": program_slug,
                "message": (
                    f"Address {address} is NOT a registered contract for {program_slug}. "
                    f"Valid contracts include: {', '.join(valid_addresses)}"
                ),
            }
        except Exception as exc:
            log.warning("address_verification_failed", error=str(exc))
            return None  # Non-blocking — proceed with fetch anyway

    async def run(self, **kwargs: Any) -> Any:
        address = kwargs.get("address", "")
        program_slug = kwargs.get("program_slug", "")

        # ── Address verification ──
        if address and program_slug:
            verification = await self._verify_address_for_program(address, program_slug)
            if verification and not verification.get("match"):
                return {
                    "warning": verification["message"],
                    "_verification": verification,
                    "suggestion": "Use fetch_program to get the correct contract addresses",
                }
            if verification and verification.get("match"):
                log.info(
                    "address_verified",
                    address=address,
                    program=program_slug,
                    contract_name=verification.get("contract_name"),
                )

        body: dict[str, Any] = {}

        if address and kwargs.get("chain"):
            body["address"] = address
            body["chain"] = kwargs["chain"]
        elif kwargs.get("url"):
            body["url"] = kwargs["url"]
        elif kwargs.get("program_slug"):
            body["program_slug"] = kwargs["program_slug"]
        else:
            return {"error": "Provide address+chain, url, or program_slug"}

        if kwargs.get("contract_name"):
            body["contract_name"] = kwargs["contract_name"]

        # ── Retry with exponential backoff ──
        last_error: str | None = None

        for attempt in range(1, MAX_FETCH_RETRIES + 1):
            try:
                resp = await self._client.post(f"{SOURCE_URL}/fetch", json=body)
                resp.raise_for_status()
                data = resp.json()

                result: dict[str, Any] = {
                    "files": {},
                    "compiler": None,
                    "contract_name": None,
                }

                source_data = data.get("data", {})
                if isinstance(source_data, dict):
                    result["files"] = source_data.get("files", {})
                    result["compiler"] = source_data.get("compiler_version")
                    result["contract_name"] = source_data.get("contract_name")
                    result["source_path"] = source_data.get("source_path")

                file_count = len(result["files"])
                file_names = list(result["files"].keys())
                result["_summary"] = f"Found {file_count} file(s): {', '.join(file_names[:5])}"

                return result

            except httpx.HTTPStatusError as exc:
                last_error = str(exc)
                if exc.response.status_code == 404:
                    # Not found — no point retrying
                    return {"error": f"Contract not found: {exc}"}
                if exc.response.status_code == 429:
                    # Rate limited — wait longer (use Retry-After header if present)
                    retry_after = int(exc.response.headers.get("Retry-After", str(2 ** attempt)))
                    log.warning(
                        "fetch_source_rate_limited",
                        attempt=attempt,
                        retry_after=retry_after,
                    )
                    if attempt < MAX_FETCH_RETRIES:
                        await asyncio.sleep(retry_after)
                    continue
                # Other HTTP errors — retry with backoff
                log.warning(
                    "fetch_source_http_error",
                    attempt=attempt,
                    status=exc.response.status_code,
                    error=str(exc),
                )
                if attempt < MAX_FETCH_RETRIES:
                    await asyncio.sleep(2 ** attempt)  # 2s, 4s, 8s
                continue

            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_error = str(exc)
                log.warning(
                    "fetch_source_connection_error",
                    attempt=attempt,
                    error=str(exc),
                )
                if attempt < MAX_FETCH_RETRIES:
                    await asyncio.sleep(2 ** attempt)  # 2s, 4s, 8s
                continue

        return {"error": f"Failed after {MAX_FETCH_RETRIES} retries: {last_error}"}
