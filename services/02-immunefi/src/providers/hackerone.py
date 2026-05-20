"""HackerOneProvider — Fetch bounty programs dari HackerOne API.

Membutuhkan HACKERONE_API_KEY dan HACKERONE_API_SECRET environment variable.
Menggunakan HackerOne API v2 (GraphQL).

Reference: https://api.hackerone.com/
"""

from __future__ import annotations

import base64
import os
from typing import Any

import httpx
import structlog

from src.providers import register_provider

log = structlog.get_logger()


@register_provider
class HackerOneProvider:
    """Fetch bounty programs dari HackerOne."""

    name = "hackerone"
    priority = 20

    BASE_URL = "https://api.hackerone.com/v2"
    GRAPHQL_URL = "https://api.hackerone.com/graphql"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._token: str | None = None

    def _get_credentials(self) -> tuple[str | None, str | None]:
        username = os.getenv("HACKERONE_API_KEY")
        password = os.getenv("HACKERONE_API_SECRET")
        return username, password

    def is_available(self) -> bool:
        username, password = self._get_credentials()
        return bool(username and password)

    def _get_auth_header(self) -> dict[str, str]:
        username, password = self._get_credentials()
        if username and password:
            token = base64.b64encode(f"{username}:{password}".encode()).decode()
            return {"Authorization": f"Basic {token}"}
        return {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def fetch_program_list(self) -> list[dict[str, Any]]:
        """Fetch list bounty programs via HackerOne API.

        HackerOne API v2 uses paginated REST endpoints.
        For MVP, we fetch the first page only.
        """
        client = await self._get_client()
        headers = {
            **self._get_auth_header(),
            "Accept": "application/json",
        }

        log.info("hackerone.fetch_list.start")

        try:
            # HackerOne API v1 for program list
            resp = await client.get(
                f"{self.BASE_URL}/programs",
                headers=headers,
                params={"page[size]": 50},
            )
            if resp.status_code == 401:
                log.warning("hackerone.unauthorized")
                return []
            resp.raise_for_status()

            data = resp.json()
            programs = data.get("data", [])
            log.info("hackerone.fetch_list.success", count=len(programs))
            return self._normalize_programs(programs)

        except httpx.TimeoutException:
            log.warning("hackerone.timeout")
            return []
        except Exception as e:
            log.warning("hackerone.error", error=str(e)[:100])
            return []

    async def fetch_program_detail(self, slug: str) -> dict[str, Any] | None:
        """Fetch detail satu program dari HackerOne."""
        client = await self._get_client()
        headers = {
            **self._get_auth_header(),
            "Accept": "application/json",
        }

        try:
            resp = await client.get(
                f"{self.BASE_URL}/programs/{slug}",
                headers=headers,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()

            data = resp.json()
            attributes = data.get("attributes", {})
            return {
                "slug": slug,
                "name": attributes.get("name", ""),
                "chains": [],
                "maxBounty": self._parse_bounty(
                    attributes.get("max_bounty", "")
                ),
                "minBounty": self._parse_bounty(
                    attributes.get("min_bounty", "")
                ),
                "currency": "USD",
                "status": attributes.get("state", "active"),
                "description": attributes.get("description", ""),
                "project_url": attributes.get("url", ""),
                "tags": attributes.get("tags", []),
                "contracts": [],
                "updatedAt": attributes.get("updated_at", ""),
            }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    def _normalize_programs(self, raw: list[dict]) -> list[dict]:
        """Normalize HackerOne API response to internal format.

        HackerOne API v2 returns:
        {
            "data": [
                {
                    "id": "1",
                    "type": "program",
                    "attributes": { ... }
                }
            ]
        }
        """
        result = []
        for item in raw:
            attrs = item.get("attributes", {})
            result.append({
                "slug": item.get("id", ""),
                "name": attrs.get("name", ""),
                "chains": [],
                "maxBounty": self._parse_bounty(
                    attrs.get("max_bounty", "")
                ),
                "minBounty": self._parse_bounty(
                    attrs.get("min_bounty", "")
                ),
                "currency": "USD",
                "status": attrs.get("state", "active"),
                "description": attrs.get("description", ""),
                "project_url": attrs.get("url", ""),
                "tags": attrs.get("tags", []),
                "contracts": [],
                "updatedAt": attrs.get("updated_at", ""),
            })
        return result

    def _parse_bounty(self, value: str | None) -> int | None:
        """Parse bounty string to int (strip $ and commas)."""
        if not value:
            return None
        try:
            return int(value.replace("$", "").replace(",", "").strip())
        except (ValueError, AttributeError):
            return None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
