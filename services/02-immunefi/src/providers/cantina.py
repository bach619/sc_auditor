"""CantinaProvider — Fetch audit competitions dari Cantina (Spearbit).

Cantina (https://cantina.xyz) adalah platform audit competition
yang berkembang cepat. API endpoint masih undocumented untuk publik.

Saat ini implementasi menggunakan web scraping dasar.
Akan di-update kalau API resmi dirilis.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.providers import register_provider

log = structlog.get_logger()


@register_provider
class CantinaProvider:
    """Fetch audit programs dari Cantina / Spearbit."""

    name = "cantina"
    priority = 30

    BASE_URL = "https://cantina.xyz"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def is_available(self) -> bool:
        return True

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def fetch_program_list(self) -> list[dict[str, Any]]:
        client = await self._get_client()
        log.info("cantina.fetch_list.start")

        try:
            resp = await client.get(
                f"{self.BASE_URL}/api/competitions",
                headers={"Accept": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                competitions = data if isinstance(data, list) else data.get("data", [])
                log.info("cantina.fetch_list.success", count=len(competitions))
                return self._normalize_programs(competitions)

            # Fallback: scrape competitions page
            html_resp = await client.get(
                f"{self.BASE_URL}/competitions",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if html_resp.status_code == 200:
                log.info("cantina.fetch_list.html_fallback")
                return self._scrape_from_html(html_resp.text)

        except Exception as e:
            log.warning("cantina.error", error=str(e)[:100])

        return []

    async def fetch_program_detail(self, slug: str) -> dict[str, Any] | None:
        try:
            client = await self._get_client()
            resp = await client.get(
                f"{self.BASE_URL}/api/competitions/{slug}",
                headers={"Accept": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return self._normalize_program(
                    data.get("data", data) if isinstance(data, dict) else data
                )
        except Exception:
            pass
        return None

    def _normalize_programs(self, raw: list[dict]) -> list[dict]:
        return [self._normalize_program(p) for p in raw]

    def _normalize_program(self, raw: dict) -> dict:
        return {
            "slug": raw.get("slug") or raw.get("id", ""),
            "name": raw.get("name", ""),
            "chains": raw.get("chains", []),
            "maxBounty": raw.get("maxBounty") or raw.get("prizePool", 0),
            "minBounty": raw.get("minBounty"),
            "currency": raw.get("currency", "USD"),
            "status": raw.get("status", "active"),
            "description": raw.get("description", ""),
            "project_url": raw.get("projectUrl") or raw.get("url", ""),
            "tags": raw.get("tags", []),
            "contracts": [],
            "updatedAt": raw.get("updatedAt") or raw.get("updated_at", ""),
        }

    def _scrape_from_html(self, html: str) -> list[dict]:
        """Fallback scrape dari HTML jika API tidak tersedia."""
        import re  # noqa: PLC0415

        programs = []
        # Extract competition cards from HTML
        cards = re.findall(
            r'<div[^>]*class="[^"]*competition-card[^"]*"[^>]*>(.*?)</div>',
            html,
            re.DOTALL,
        )
        for card in cards:
            name_match = re.search(r'<h[23][^>]*>(.*?)</h[23]>', card)
            slug_match = re.search(r'href="[^"]*/([^/"]+)"', card)
            if name_match:
                programs.append({
                    "slug": slug_match.group(1) if slug_match else "",
                    "name": name_match.group(1).strip(),
                    "chains": [],
                    "maxBounty": None,
                    "status": "active",
                })
        return programs

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
