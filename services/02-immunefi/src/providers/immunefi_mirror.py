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
import re
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
    priority = 5  # Higher than web scraper (8) so GitHub mirror is tried first

    # API endpoint sudah tidak aktif (returns 404 sejak mid-2025)
    # Gunakan web scraping langsung sebagai gantinya.
    # ImmunefiWebScraper (immunefi_web_scraper.py) adalah pengganti resmi.
    # GitHub raw mirror (primary — reliable, 276+ programs)
    GITHUB_MIRROR_LIST = (
        "https://raw.githubusercontent.com/"
        "infosec-us-team/Immunefi-Bug-Bounty-Programs-Unofficial/main/projects.json"
    )
    GITHUB_MIRROR_DETAIL = (
        "https://raw.githubusercontent.com/"
        "infosec-us-team/Immunefi-Bug-Bounty-Programs-Unofficial/main/project/{slug}.json"
    )

    MIRROR_URL = "https://immunefi.com/bug-bounty/"
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
        """Fetch list program dari GitHub mirror Immunefi (primary) atau web scraping."""
        client = await self._get_client()

        log.info("immunefi_mirror.fetch_list.start")

        # Priority 1: GitHub raw mirror (paling reliable, 276+ programs)
        try:
            resp = await client.get(self.GITHUB_MIRROR_LIST)
            if resp.status_code == 200:
                raw = resp.json()
                if raw and len(raw) > 10:
                    log.info(
                        "immunefi_mirror.fetch_list.github_success",
                        count=len(raw),
                    )
                    self._save_cache(raw)
                    return self._normalize_programs(raw)
        except Exception as e:
            log.debug("immunefi_mirror.github_error", error=str(e)[:80])

        # Priority 2: Coba web scraping langsung
        try:
            from src.providers.immunefi_web_scraper import ImmunefiWebScraper  # noqa: PLC0415
            web = ImmunefiWebScraper()
            programs = await web.fetch_program_list()
            if programs:
                log.info(
                    "immunefi_mirror.fetch_list.web_success",
                    count=len(programs),
                )
                self._save_cache(programs)
                return self._normalize_programs(programs)
        except ImportError:
            pass
        except Exception as e:
            log.debug("immunefi_mirror.web_scraper_error", error=str(e)[:80])

        # Priority 3: Coba scrape dari HTML halaman explore
        try:
            resp = await client.get(
                self.MIRROR_URL,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            from bs4 import BeautifulSoup  # noqa: PLC0415
            soup = BeautifulSoup(resp.text, "lxml")

            programs = []
            for link in soup.find_all("a", href=re.compile(r"/bug-bounty/[^/]+/")):
                href = link.get("href", "")
                m = re.match(r"/bug-bounty/([^/]+)", href)
                if m:
                    slug = m.group(1)
                    if slug not in (p.get("slug") for p in programs):
                        programs.append({
                            "slug": slug,
                            "name": link.get_text(strip=True) or slug,
                            "status": "active",
                        })

            if programs:
                log.info(
                    "immunefi_mirror.fetch_list.html_success",
                    count=len(programs),
                )
                self._save_cache(programs)
                return self._normalize_programs(programs)

        except Exception as e:
            log.warning("immunefi_mirror.html_error", error=str(e)[:100])

        # Fallback: coba pakai cache
        cached = self._load_cache()
        if cached:
            log.info("immunefi_mirror.using_cache", count=len(cached))
            return self._normalize_programs(cached)

        return []

    async def fetch_program_detail(self, slug: str) -> dict[str, Any] | None:
        """Fetch detail program dari GitHub mirror (primary) atau web scraping."""
        client = await self._get_client()

        # Priority 1: GitHub raw mirror
        try:
            resp = await client.get(self.GITHUB_MIRROR_DETAIL.format(slug=slug))
            if resp.status_code == 200:
                log.info("immunefi_mirror.detail.github_success", slug=slug)
                return self._normalize_program(resp.json())
        except Exception as e:
            log.debug("immunefi_mirror.detail.github_error", slug=slug, error=str(e)[:80])

        # Fallback: scrape dari halaman web Immunefi
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
            log.debug("immunefi_mirror.detail.web_error", slug=slug, error=str(e)[:80])
            return None

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
            "assets": raw.get("assets", []),  # Preserve original assets for parse_contracts
            "social": raw.get("social", raw.get("links", [])),
            "rewards": raw.get("rewards", raw.get("rewardDetails", {})),
            "updatedAt": raw.get("updatedAt")
                          or raw.get("updated_at")
                          or raw.get("lastUpdated", ""),
        }

    def _extract_contracts(self, raw: dict) -> list[dict]:
        """Extract smart contract addresses from raw program data.

        Handles multiple formats:
        - assets[] (GitHub mirror format): has type, url, description
        - contracts[] (API format): has address, chain, name
        - targets[] (alternative): has address, chain, name

        Only includes smart_contract type assets with valid 0x addresses.
        Extracts address from the URL if no direct address field exists.
        """
        import re  # noqa: PLC0415

        contracts = raw.get("contracts", raw.get("assets", raw.get("targets", [])))
        if not isinstance(contracts, list):
            return []

        result: list[dict] = []
        seen: set[str] = set()

        for c in contracts:
            if not isinstance(c, dict):
                # Raw address string
                addr = str(c).strip()
                if addr.startswith("0x") and len(addr) == 42 and addr not in seen:
                    seen.add(addr)
                    result.append({"address": addr, "chain": "", "name": ""})
                continue

            # Filter by type: only smart_contract
            asset_type = str(c.get("type", "") or "").lower()
            if asset_type and asset_type != "smart_contract":
                continue

            # Extract address
            addr = str(c.get("address", "") or "")
            if not addr or len(addr) < 30:
                url = str(c.get("url", "") or "")
                addr_match = re.search(r"0x[a-fA-F0-9]{40}", url)
                if addr_match:
                    addr = addr_match.group(0)

            if addr and len(addr) == 42 and addr not in seen:
                seen.add(addr)
                # Detect chain from URL if not explicit
                chain = str(c.get("chain", "") or "")
                if not chain:
                    url = str(c.get("url", "") or "")
                    chain = self._detect_chain_from_url(url)
                name = str(c.get("description", "") or c.get("name", "") or "")
                result.append({
                    "address": addr,
                    "chain": chain,
                    "name": name.strip(),
                })

        return result

    @staticmethod
    def _detect_chain_from_url(url: str) -> str:
        """Detect blockchain dari explorer URL."""
        domain = url.lower()
        if "optimistic.etherscan.io" in domain:
            return "optimism"
        if "etherscan.io" in domain:
            return "ethereum"
        if "arbiscan.io" in domain:
            return "arbitrum"
        if "polygonscan.com" in domain:
            return "polygon"
        if "bscscan.com" in domain:
            return "bsc"
        if "snowtrace.io" in domain or "snowscan.xyz" in domain:
            return "avalanche"
        if "ftmscan.com" in domain:
            return "fantom"
        if "basescan.org" in domain:
            return "base"
        if "mantlescan.xyz" in domain:
            return "mantle"
        if "scrollscan.com" in domain:
            return "scroll"
        return "unknown"

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
