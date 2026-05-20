"""Code4renaProvider — Fetch audit contests dari Code4rena.

Code4rena (https://code4rena.com/) is a leading audit competition
platform. They have a public API endpoint for contests.

Reference: https://code4rena.com/api/v1/contests
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.providers import register_provider

log = structlog.get_logger()


@register_provider
class Code4renaProvider:
    """Fetch audit contests dari Code4rena."""

    name = "code4rena"
    priority = 40

    API_URL = "https://code4rena.com/api/v1"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def is_available(self) -> bool:
        return True

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def fetch_program_list(self) -> list[dict[str, Any]]:
        """GET /api/v1/contests — list semua contest."""
        client = await self._get_client()
        log.info("code4rena.fetch_list.start")

        try:
            resp = await client.get(
                f"{self.API_URL}/contests",
                headers={"Accept": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                contests = data if isinstance(data, list) else data.get("data", [])
                log.info("code4rena.fetch_list.success", count=len(contests))
                return [self._normalize_contest(c) for c in contests]

        except httpx.TimeoutException:
            log.warning("code4rena.timeout")
        except Exception as e:
            log.warning("code4rena.error", error=str(e)[:100])

        return []

    async def fetch_program_detail(self, slug: str) -> dict[str, Any] | None:
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.API_URL}/contests/{slug}")
            if resp.status_code == 404:
                return None
            if resp.status_code == 200:
                data = resp.json()
                contest = data.get("data", data) if isinstance(data, dict) else data
                return self._normalize_contest(contest)
        except Exception:
            return None
        return None

    def _normalize_contest(self, raw: dict) -> dict:
        return {
            "slug": raw.get("slug") or str(raw.get("id", "")),
            "name": raw.get("name", ""),
            "chains": raw.get("chains", []),
            "maxBounty": raw.get("prizePool") or raw.get("max_bounty"),
            "minBounty": raw.get("min_bounty"),
            "currency": "USD",
            "status": raw.get("status", "active"),
            "description": raw.get("description", ""),
            "project_url": raw.get("url", ""),
            "tags": raw.get("tags", []),
            "contracts": [],
            "updatedAt": raw.get("updatedAt") or raw.get("endDate", ""),
        }

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
