"""ImmunefiOfficialProvider — Fetch langsung dari API resmi Immunefi.

Membutuhkan IMMUNEFI_API_KEY environment variable atau dari 01-config service.
Priority: 1 (tertinggi — API resmi lebih akurat daripada mirror).

API Reference (dokumentasi publik Immunefi):
  GET /v1/programs          — List semua program
  GET /v1/programs/{slug}   — Detail program
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

from src.providers import register_provider

log = structlog.get_logger()


@register_provider
class ImmunefiOfficialProvider:
    """Fetch program bounty langsung dari API resmi Immunefi.

    Membutuhkan IMMUNEFI_API_KEY. Jika tidak ada, provider ini tidak available.
    """

    name = "immunefi_official"
    priority = 1  # Highest — official API

    BASE_URL = "https://api.immunefi.com/v1"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._api_key: str | None = None

    def _get_api_key(self) -> str | None:
        """Dapatkan API key dari env var atau config service."""
        if self._api_key:
            return self._api_key

        # Priority 1: Environment variable
        key = os.getenv("IMMUNEFI_API_KEY")
        if key:
            self._api_key = key
            return key

        # Priority 2: Config Service 01 (kalau reachable)
        try:
            config_url = os.getenv("CONFIG_URL", "http://01-config:8000")
            resp = httpx.get(f"{config_url}/config/immunefi_api_key", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                key = data.get("data", {}).get("value")
                if key:
                    self._api_key = key
                    return key
        except Exception:
            pass

        return None

    def is_available(self) -> bool:
        """Available hanya jika API key tersedia."""
        return self._get_api_key() is not None

    async def _get_client(self) -> httpx.AsyncClient:
        """Dapatkan HTTP client (buat baru jika perlu)."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _headers(self) -> dict[str, str]:
        key = self._get_api_key()
        return {
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        }

    async def fetch_program_list(self) -> list[dict[str, Any]]:
        """GET /v1/programs — list semua program."""
        client = await self._get_client()
        headers = await self._headers()

        log.info("immunefi_official.fetch_list.start")

        try:
            resp = await client.get(f"{self.BASE_URL}/programs", headers=headers)
            resp.raise_for_status()
            data = resp.json()

            # API response format: { "data": [...] } or just [...]
            programs = data.get("data", data) if isinstance(data, dict) else data

            log.info("immunefi_official.fetch_list.success", count=len(programs))
            return self._normalize_programs(programs)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                log.warning("immunefi_official.unauthorized", detail="API key invalid")
            elif e.response.status_code == 403:
                log.warning("immunefi_official.forbidden")
            else:
                log.warning(
                    "immunefi_official.http_error",
                    status=e.response.status_code,
                )
            raise

    async def fetch_program_detail(self, slug: str) -> dict[str, Any] | None:
        """GET /v1/programs/{slug} — detail satu program."""
        client = await self._get_client()
        headers = await self._headers()

        try:
            resp = await client.get(
                f"{self.BASE_URL}/programs/{slug}",
                headers=headers,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            return self._normalize_program(
                data.get("data", data) if isinstance(data, dict) else data
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    # ── Normalization ────────────────────────────────────────

    def _normalize_programs(self, raw: list[dict]) -> list[dict]:
        """Normalisasi daftar program ke format internal."""
        return [self._normalize_program(p) for p in raw]

    def _normalize_program(self, raw: dict) -> dict:
        """Map API field names ke format internal yang konsisten.

        Immunefi API mungkin menggunakan camelCase.
        Internal kita pakai snake_case + field yang cocok dengan Program model.
        """
        return {
            "slug": raw.get("slug") or raw.get("id", ""),
            "name": raw.get("name", ""),
            "chains": raw.get("chains", raw.get("blockchains", [])),
            "maxBounty": raw.get("maxBounty") or raw.get("max_bounty"),
            "minBounty": raw.get("minBounty") or raw.get("min_bounty"),
            "currency": raw.get("currency", "USD"),
            "status": raw.get("status", "unknown"),
            "description": raw.get("description", ""),
            "project_url": raw.get("projectUrl") or raw.get("project_url", ""),
            "logo": raw.get("logo") or raw.get("logoUrl", ""),
            "tags": raw.get("tags", raw.get("categories", [])),
            "contracts": self._extract_contracts(raw),
            "social": raw.get("social", raw.get("links", [])),
            "rewards": raw.get("rewards", raw.get("rewardDetails", {})),
            "updatedAt": raw.get("updatedAt")
                          or raw.get("updated_at")
                          or raw.get("lastUpdated", ""),
        }

    def _extract_contracts(self, raw: dict) -> list[dict]:
        """Extract contract addresses from various possible field names."""
        contracts = raw.get("contracts", raw.get("assets", raw.get("targets", [])))
        if isinstance(contracts, list):
            normalized = []
            for c in contracts:
                if isinstance(c, dict):
                    normalized.append({
                        "address": c.get("address", ""),
                        "chain": c.get("chain", c.get("blockchain", "")),
                        "name": c.get("name", ""),
                    })
                elif isinstance(c, str):
                    normalized.append({"address": c, "chain": "", "name": ""})
            return normalized
        return []

    async def close(self) -> None:
        """Cleanup HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
