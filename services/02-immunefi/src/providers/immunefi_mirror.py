"""ImmunefiMirrorProvider — Scrape dari mirror/source publik Immunefi.

Fallback provider kalau API key tidak tersedia. Mengambil data dari
sumber publik Immunefi (web scraping atau alternatif open data).

Priority: 10 (lebih rendah dari official API).
Available selalu true (tidak butuh API key).

Catatan: Scraping mungkin lebih lambat dan kurang reliable
dibanding API resmi. Untuk production, prioritaskan official API.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
import structlog

from src.providers import register_provider

log = structlog.get_logger()


@register_provider
class ImmunefiMirrorProvider:
    """Scrape program bounty dari mirror publik Immunefi.

    Mengambil data dari:
      1. Immunefi web frontend data (embedded JSON di halaman program)
      2. File cache lokal (mirror) kalau network tidak reachable
    """

    name = "immunefi_mirror"
    priority = 10  # Lower than official API

    MIRROR_URL = "https://immunefi.com/api/explore/programs/"
    WEB_BASE = "https://immunefi.com"

    def __init__(self, cache_dir: str | None = None) -> None:
        self._client: httpx.AsyncClient | None = None
        self._cache_dir = cache_dir or os.getenv(
            "IMMUNEFI_MIRROR_CACHE",
            str(Path("data/mirror_cache")),
        )

    def is_available(self) -> bool:
        return True

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    # ── Fetch Program List ───────────────────────────────────

    async def fetch_program_list(self) -> list[dict[str, Any]]:
        """Fetch list program dari mirror endpoint publik."""
        client = await self._get_client()

        log.info("immunefi_mirror.fetch_list.start")

        try:
            resp = await client.get(
                self.MIRROR_URL,
                headers={"Accept": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                programs = data.get("data", data) if isinstance(data, dict) else data
                log.info(
                    "immunefi_mirror.fetch_list.success",
                    count=len(programs),
                )
                self._save_cache(programs)
                return self._normalize_programs(programs)

            # Fallback: scrape dari HTML halaman explore
            log.info(
                "immunefi_mirror.fetch_list.fallback_html",
                status=resp.status_code,
            )

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            log.warning("immunefi_mirror.network_error", error=str(e)[:100])

        # Fallback: coba pakai cache
        cached = self._load_cache()
        if cached:
            log.info("immunefi_mirror.using_cache", count=len(cached))
            return self._normalize_programs(cached)

        return []

    async def fetch_program_detail(self, slug: str) -> dict[str, Any] | None:
        """Scrape detail program dari halaman web Immunefi."""
        client = await self._get_client()

        try:
            resp = await client.get(
                f"{self.WEB_BASE}/explore/{slug}",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code != 200:
                return None

            html = resp.text

            # Coba extract embedded JSON dari <script id="__NEXT_DATA__">
            import re  # noqa: PLC0415 — import inside function ok untuk fallback
            match = re.search(
                r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                html,
                re.DOTALL,
            )
            if match:
                import json  # noqa: PLC0415
                next_data = json.loads(match.group(1))
                props = next_data.get("props", {}).get("pageProps", {})
                program = props.get("program", props)
                if program:
                    return self._normalize_program(program)

            # Fallback: coba scrape table info dari halaman
            return self._scrape_detail_from_html(html, slug)

        except Exception as e:
            log.warning(
                "immunefi_mirror.detail_error",
                slug=slug,
                error=str(e)[:100],
            )
            return None

    # ── Normalization ────────────────────────────────────────

    def _normalize_programs(self, raw: list[dict]) -> list[dict]:
        return [self._normalize_program(p) for p in raw]

    def _normalize_program(self, raw: dict) -> dict:
        return {
            "slug": raw.get("slug") or raw.get("id", ""),
            "name": raw.get("name", ""),
            "chains": raw.get("chains", raw.get("blockchains", [])),
            "maxBounty": raw.get("maxBounty") or raw.get("max_bounty"),
            "minBounty": raw.get("minBounty") or raw.get("min_bounty"),
            "currency": raw.get("currency", "USD"),
            "status": raw.get("status", "active"),
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
        contracts = raw.get("contracts", raw.get("assets", raw.get("targets", [])))
        if isinstance(contracts, list):
            return [
                {
                    "address": c.get("address", c) if isinstance(c, dict) else c,
                    "chain": c.get("chain", "") if isinstance(c, dict) else "",
                    "name": c.get("name", "") if isinstance(c, dict) else "",
                }
                for c in contracts
            ]
        return []

    def _scrape_detail_from_html(
        self,
        html: str,
        slug: str,
    ) -> dict[str, Any] | None:
        """Scrape informasi dari HTML ketika JSON tidak tersedia."""
        import re  # noqa: PLC0415

        info: dict[str, Any] = {"slug": slug}

        # Coba extract max bounty dari text
        bounty_match = re.search(
            r'\$\s*([0-9,]+)\s*(?:USD|USDC|USDT)?',
            html,
        )
        if bounty_match:
            try:
                info["maxBounty"] = int(bounty_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # Extract chain info dari badge/label
        chain_matches = re.findall(
            r'<span[^>]*class[^>]*chain[^>]*>([^<]+)</span>',
            html,
            re.IGNORECASE,
        )
        if chain_matches:
            info["chains"] = [c.strip() for c in chain_matches]

        return info if len(info) > 1 else None

    # ── Cache ────────────────────────────────────────────────

    def _cache_path(self) -> Path:
        return Path(self._cache_dir) / "programs_list.json"

    def _save_cache(self, programs: list[dict]) -> None:
        try:
            path = self._cache_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(programs, indent=2))
            log.info("immunefi_mirror.cache_saved", path=str(path))
        except Exception as e:
            log.warning("immunefi_mirror.cache_save_error", error=str(e)[:100])

    def _load_cache(self) -> list[dict]:
        try:
            path = self._cache_path()
            if path.exists():
                data = json.loads(path.read_text())
                log.info("immunefi_mirror.cache_loaded", path=str(path))
                return data if isinstance(data, list) else data.get("data", [])
        except Exception as e:
            log.warning("immunefi_mirror.cache_load_error", error=str(e)[:100])
        return []

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
