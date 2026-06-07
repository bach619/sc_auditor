"""ImmunefiWebScraper — Scrape langsung dari immunefi.com/bug-bounty/ live site.

Mengambil semua program bug bounty beserta smart contract addresses
dengan cara:
  1. Scrape https://immunefi.com/bug-bounty/ → dapatkan daftar slug
  2. Scrape https://immunefi.com/bug-bounty/{slug}/information/ → detail
  3. Extract __NEXT_DATA__ (Next.js SSR JSON) untuk contract addresses
  4. Filter hanya assets bertipe "smart_contract" (in-scope untuk audit)

Priority: 8 (lebih tinggi dari mirror, lebih rendah dari official API).
Available: selalu true (tidak butuh API key).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

from src.providers import register_provider

log = structlog.get_logger()

# ── Rate Limiting ──────────────────────────────────────────
# Immunefi.com dilindungi Cloudflare. Kita batasi:
#   - Maks 3 req/detik (jauh di bawah threshold WAF)
#   - Maks 5 concurrent request
#   - Exponential backoff kalau kena 429

_RATE_LIMIT_REQUESTS_PER_SECOND = 3
_RATE_LIMIT_BURST = 5
_MAX_CONCURRENT = 5

_semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
_last_request_time: float = 0.0
_request_lock = asyncio.Lock()


async def _rate_limit() -> None:
    """Token-bucket rate limiter: maks 3 req/detik per instance."""
    global _last_request_time
    async with _request_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        min_interval = 1.0 / _RATE_LIMIT_REQUESTS_PER_SECOND
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        _last_request_time = time.monotonic()


@register_provider
class ImmunefiWebScraper:
    """Scrape data program bounty langsung dari website Immunefi live.

    Multi-layer scraping:
      Layer 1: __NEXT_DATA__ JSON (paling akurat)
      Layer 2: RSC streaming (Accept: text/x-component)
      Layer 3: BeautifulSoup HTML parsing (fallback)

    Hanya smart contract assets yang masuk scope yang diekstrak.

    Rate limiting:
      - Maks 3 request/detik (token bucket)
      - Maks 5 concurrent request (semaphore)
      - Exponential backoff + jitter kalau kena 429
    """

    name = "immunefi_web"
    priority = 8  # Higher than mirror (10), lower than official API (1)

    # ── URLs ─────────────────────────────────────────────────

    LISTING_URL = "https://immunefi.com/bug-bounty/"
    DETAIL_URL = "https://immunefi.com/bug-bounty/{slug}/information/"
    PROGRESS_URL = "https://immunefi.com/bug-bounty/{slug}/progress/"

    # ── Headers ──────────────────────────────────────────────

    HEADERS_HTML = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    HEADERS_RSC = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "RSC": "1",
        "Accept": "text/x-component",
        "Next-Action": "",
        "Next-Router-State-Tree": "%5B%22%22%2C%7B%22children%22%3A%5B%22bug-bounty%22%2C%7B%22children%22%3A%5B%22%5Bslug%5D%22%2C%7B%22children%22%3A%5B%22information%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%5D%7D%5D%7D%5D%7D%5D%7D%5D",
    }

    def __init__(self, cache_dir: str | None = None) -> None:
        self._client: httpx.AsyncClient | None = None
        self._cache_dir = cache_dir or os.getenv(
            "IMMUNEFI_WEB_CACHE",
            str(Path("/data/cache/immunefi_web")),
        )

    def is_available(self) -> bool:
        """Selalu available — tidak butuh API key."""
        return True

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            limits = httpx.Limits(max_keepalive_connections=5, max_connections=20)
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=15.0),
                limits=limits,
                follow_redirects=True,
            )
        return self._client

    async def _request(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str] | None = None,
        max_retries: int = 3,
    ) -> httpx.Response | None:
        """Rate-limited HTTP GET request dengan retry + backoff untuk 429.

        Args:
            client: HTTP client
            url: Target URL
            headers: Optional headers
            max_retries: Max retry kalau kena 429

        Returns:
            Response object atau None jika gagal setelah retry
        """
        async with _semaphore:
            for attempt in range(max_retries):
                await _rate_limit()
                try:
                    resp = await client.get(url, headers=headers or self.HEADERS_HTML)

                    if resp.status_code == 429:
                        retry_after = int(resp.headers.get("Retry-After", 5))
                        wait = retry_after + (attempt * 2)  # linear backoff
                        log.warning(
                            "web_scraper.rate_limited",
                            url=url,
                            attempt=attempt + 1,
                            retry_after=retry_after,
                            wait=wait,
                        )
                        await asyncio.sleep(wait)
                        continue

                    return resp

                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    if attempt == max_retries - 1:
                        log.warning(
                            "web_scraper.request_failed",
                            url=url,
                            error=str(e)[:80],
                        )
                        return None
                    await asyncio.sleep(1.5 ** attempt)  # exponential backoff
                    continue

            return None

    # ═══════════════════════════════════════════════════════════
    #  PUBLIC API
    # ═══════════════════════════════════════════════════════════

    async def fetch_program_list(self) -> list[dict[str, Any]]:
        """Fetch daftar semua program dari live site.

        Returns:
            List program dict dengan minimal fields:
                slug, name, maxBounty, status, chains, tags
        """
        client = await self._get_client()
        log.info("web_scraper.fetch_list.start")

        # Layer 1: Coba RSC streaming
        programs = await self._try_fetch_list_rsc(client)
        if programs:
            log.info("web_scraper.fetch_list.rsc_success", count=len(programs))
            self._save_cache(programs)
            return programs

        # Layer 2: HTML parsing dengan BeautifulSoup
        programs = await self._try_fetch_list_html(client)
        if programs:
            log.info("web_scraper.fetch_list.html_success", count=len(programs))
            self._save_cache(programs)
            return programs

        # Layer 3: Cache fallback
        cached = self._load_cache()
        if cached:
            log.info("web_scraper.fetch_list.cache_fallback", count=len(cached))
            return self._normalize_programs(cached)

        log.warning("web_scraper.fetch_list.no_data")
        return []

    async def fetch_program_detail(self, slug: str) -> dict[str, Any] | None:
        """Fetch detail satu program dari live site.

        Args:
            slug: Program slug (misal: "ethena")

        Returns:
            Dict dengan detail program termasuk contracts,
            atau None jika tidak ditemukan.
        """
        client = await self._get_client()
        log.info("web_scraper.fetch_detail.start", slug=slug)

        # Layer 1: __NEXT_DATA__ dari HTML (paling akurat)
        detail = await self._try_fetch_detail_next_data(client, slug)
        if detail and self._has_smart_contracts(detail):
            log.info("web_scraper.fetch_detail.next_data", slug=slug, contracts=len(detail.get("contracts", [])))
            return detail

        # Layer 2: RSC streaming
        detail = await self._try_fetch_detail_rsc(client, slug)
        if detail and self._has_smart_contracts(detail):
            log.info("web_scraper.fetch_detail.rsc", slug=slug, contracts=len(detail.get("contracts", [])))
            return detail

        # Layer 3: HTML scraping fallback
        detail = await self._try_fetch_detail_html(client, slug)
        if detail:
            log.info("web_scraper.fetch_detail.html", slug=slug, contracts=len(detail.get("contracts", [])))
            return detail

        log.warning("web_scraper.fetch_detail.not_found", slug=slug)
        return None

    # ═══════════════════════════════════════════════════════════
    #  LAYER 1: __NEXT_DATA__ Extraction
    # ═══════════════════════════════════════════════════════════

    async def _try_fetch_detail_next_data(
        self,
        client: httpx.AsyncClient,
        slug: str,
    ) -> dict[str, Any] | None:
        """Extract data dari <script id='__NEXT_DATA__'> di halaman detail.

        Ini adalah metode paling akurat karena Next.js merender
        semua props page ke dalam JSON tersebut.
        """
        urls = [
            self.DETAIL_URL.format(slug=slug),
            f"https://immunefi.com/explore/{slug}/",
        ]

        for url in urls:
            try:
                resp = await self._request(client, url, self.HEADERS_HTML)
                if resp is None or resp.status_code != 200:
                    continue

                html = resp.text
                next_data = self._extract_next_data(html)
                if not next_data:
                    continue

                # Navigate ke pageProps → program
                props = (
                    next_data
                    .get("props", {})
                    .get("pageProps", {})
                )

                # Format bisa berbeda:
                # 1. Langsung program object
                program = props.get("program", props.get("bounty", props))

                if program and isinstance(program, dict) and len(program) > 3:
                    return self._normalize_program(program, slug)

            except httpx.TimeoutException:
                continue
            except Exception as e:
                log.debug("web_scraper.next_data_error", slug=slug, error=str(e)[:80])
                continue

        return None

    async def _try_fetch_list_rsc(
        self,
        client: httpx.AsyncClient,
    ) -> list[dict[str, Any]] | None:
        """Coba fetch program list via RSC streaming protocol.

        RSC (React Server Components) streaming menggunakan format
        text/x-component. Data dikirim dalam format streaming
        yang bisa kita parse untuk extract JSON program objects.
        """
        try:
            resp = await self._request(client, self.LISTING_URL, self.HEADERS_RSC)
            if resp is None or resp.status_code != 200:
                return None

            text = resp.text

            # RSC format: array of tuples/data chunks
            # Coba extract JSON objects dari streaming data
            programs = self._extract_programs_from_rsc(text)
            if programs:
                return programs

            return None

        except Exception as e:
            log.debug("web_scraper.rsc_list_error", error=str(e)[:80])
            return None

    async def _try_fetch_detail_rsc(
        self,
        client: httpx.AsyncClient,
        slug: str,
    ) -> dict[str, Any] | None:
        """Coba fetch detail program via RSC streaming."""
        url = self.DETAIL_URL.format(slug=slug)
        tree = "%5B%22%22%2C%7B%22children%22%3A%5B%22bug-bounty%22%2C%7B%22children%22%3A%5B%22" + slug + "%22%2C%7B%22children%22%3A%5B%22information%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%5D%7D%5D%7D%5D%7D%5D%7D%5D"

        headers = {**self.HEADERS_RSC, "Next-Router-State-Tree": tree}

        try:
            resp = await self._request(client, url, headers)
            if resp is None or resp.status_code != 200:
                return None

            text = resp.text
            return self._extract_detail_from_rsc(text, slug)

        except Exception as e:
            log.debug("web_scraper.rsc_detail_error", slug=slug, error=str(e)[:80])
            return None

    # ═══════════════════════════════════════════════════════════
    #  LAYER 2: HTML Parsing dengan BeautifulSoup
    # ═══════════════════════════════════════════════════════════

    async def _try_fetch_list_html(
        self,
        client: httpx.AsyncClient,
    ) -> list[dict[str, Any]] | None:
        """Parse daftar program dari HTML listing page.

        Immunefi listing page memiliki tabel dengan kolom:
        NAME, VAULT TVL, MAX BOUNTY, TOTAL PAID, MED. RESOLUTION TIME, LAST UPDATED
        """
        try:
            resp = await self._request(client, self.LISTING_URL, self.HEADERS_HTML)
            if resp is None or resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "lxml")

            # Priority 1: Extract dari __NEXT_DATA__ di listing page
            next_data = self._extract_next_data(resp.text)
            if next_data:
                programs = self._extract_programs_from_next_data(next_data)
                if programs:
                    return programs

            # Priority 2: Parse dari HTML table
            programs = self._parse_listing_table(soup)
            if programs:
                return programs

            # Priority 3: Extract dari link/button elements
            programs = self._parse_listing_links(soup)
            if programs:
                return programs

            return None

        except Exception as e:
            log.debug("web_scraper.html_list_error", error=str(e)[:80])
            return None

    async def _try_fetch_detail_html(
        self,
        client: httpx.AsyncClient,
        slug: str,
    ) -> dict[str, Any] | None:
        """Parse detail program dari HTML halaman detail."""
        urls = [
            self.DETAIL_URL.format(slug=slug),
            self.PROGRESS_URL.format(slug=slug),
            f"https://immunefi.com/explore/{slug}/",
        ]

        for url in urls:
            try:
                resp = await self._request(client, url, self.HEADERS_HTML)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "lxml")

                # Extract contract info dari halaman
                info: dict[str, Any] = {"slug": slug}

                # Cari contract addresses di page
                contracts = self._parse_contracts_from_html(soup, url)
                if contracts:
                    info["contracts"] = contracts

                # Extract bounty
                bounty = self._parse_bounty_from_html(soup)
                if bounty:
                    info["maxBounty"] = bounty

                # Extract chain info
                chains = self._parse_chains_from_html(soup)
                if chains:
                    info["chains"] = chains

                if contracts or bounty:
                    return self._normalize_program(info, slug)

            except Exception as e:
                log.debug(
                    "web_scraper.detail_html_error",
                    slug=slug,
                    url=url,
                    error=str(e)[:80],
                )
                continue

        return None

    # ═══════════════════════════════════════════════════════════
    #  PARSING: __NEXT_DATA__
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _extract_next_data(html: str) -> dict | None:
        """Extract JSON dari <script id='__NEXT_DATA__'> tag.

        Returns parsed dict atau None jika tidak ditemukan.
        """
        # Pattern 1: <script id="__NEXT_DATA__" type="application/json">...</script>
        match = re.search(
            r'<script\s+id=["\']__NEXT_DATA__["\']\s+type=["\']application/json["\'][^>]*>'
            r'(.*?)</script>',
            html,
            re.DOTALL,
        )
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Pattern 2: <script id="__NEXT_DATA__" ...>...</script> (no type)
        match = re.search(
            r'<script\s+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        return None

    def _extract_programs_from_next_data(
        self,
        next_data: dict,
    ) -> list[dict[str, Any]] | None:
        """Extract program list dari __NEXT_DATA__ JSON.

        Navigasi struktur pageProps untuk menemukan array program.
        """
        try:
            props = next_data.get("props", {}).get("pageProps", {})

            # Common field names untuk program list
            for field in ("programs", "bounties", "items", "results", "data"):
                data = props.get(field)
                if isinstance(data, list) and len(data) > 0:
                    return self._normalize_programs(data)

            # Fallback: search recursive
            return self._find_programs_in_dict(props)

        except Exception as e:
            log.debug("web_scraper.extract_next_data_error", error=str(e)[:80])
            return None

    def _find_programs_in_dict(
        self,
        data: Any,
        depth: int = 0,
    ) -> list[dict[str, Any]] | None:
        """Cari array of program objects secara recursive dalam dict."""
        if depth > 5:
            return None

        if isinstance(data, list):
            # Check if this looks like a program list
            # First-pass heuristic: any non-empty list where items look like programs
            if data and all(
                isinstance(i, dict) and ("slug" in i or "name" in i)
                for i in data
            ):
                return self._normalize_programs(data)
            return None

        if isinstance(data, dict):
            for value in data.values():
                result = self._find_programs_in_dict(value, depth + 1)
                if result:
                    return result

        return None

    # ═══════════════════════════════════════════════════════════
    #  PARSING: RSC Streaming Data
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _extract_programs_from_rsc(text: str) -> list[dict[str, Any]] | None:
        """Extract program objects dari RSC streaming response.

        RSC format menggunakan $分隔符 dengan JSON objects.
        """
        programs = []

        # Pattern: Cari JSON objects dalam RSC stream
        # RSC sering mengandung stringified JSON arrays
        re.compile(r'\$(\d+)?[LSC]\s*(\{.*?\})\s*', re.DOTALL)

        # Cari array of program objects
        for match in re.finditer(r'\[.*?"slug".*?\]', text, re.DOTALL):
            try:
                chunk = match.group(0)
                items = json.loads(chunk)
                if isinstance(items, list):
                    valid = [
                        item for item in items
                        if isinstance(item, dict) and item.get("slug")
                    ]
                    programs.extend(valid)
            except (json.JSONDecodeError, ValueError):
                continue

        return programs if programs else None

    @staticmethod
    def _extract_detail_from_rsc(
        text: str,
        slug: str,
    ) -> dict[str, Any] | None:
        """Extract detail program dari RSC streaming response."""
        # Cari JSON object yang mengandung slug dan contracts
        pattern = re.compile(
            r'\{[^{}]*"' + re.escape(slug) + r'"[^{}]*contract[^{}]*\}',
            re.DOTALL,
        )

        for match in re.finditer(pattern, text):
            try:
                # Balance braces
                obj_str = match.group(0)
                obj = json.loads(obj_str)
                if isinstance(obj, dict) and len(obj) > 3:
                    return obj
            except json.JSONDecodeError:
                continue

        # Fallback: cari object terbesar di RSC
        try:
            for match in re.finditer(r'\{.*?\}', text, re.DOTALL):
                chunk = match.group(0)
                if slug in chunk and "address" in chunk:
                    obj = json.loads(chunk)
                    if isinstance(obj, dict):
                        return obj
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    # ═══════════════════════════════════════════════════════════
    #  PARSING: HTML Table & Elements
    # ═══════════════════════════════════════════════════════════

    def _parse_listing_table(self, soup: BeautifulSoup) -> list[dict[str, Any]] | None:
        """Parse program list dari HTML table di listing page."""
        programs: list[dict[str, Any]] = []

        # Cari semua link yang mengarah ke /bug-bounty/{slug}/information/
        for link in soup.find_all("a", href=re.compile(r"/bug-bounty/[^/]+/information/")):
            href = link.get("href", "")
            slug = href.split("/bug-bounty/")[1].split("/")[0].strip()
            if not slug or slug in (p.get("slug") for p in programs):
                continue

            program: dict[str, Any] = {
                "slug": slug,
                "name": link.get_text(strip=True) or slug,
                "status": "active",
            }

            # Cari parent row untuk extract bounty
            row = link.find_parent("tr")
            if row:
                cells = row.find_all("td")
                for cell in cells:
                    cell_text = cell.get_text(strip=True)

                    # Detect bounty (formatted as $X,XXX or $X.Xk)
                    bounty_match = re.search(r'\$\s*([0-9,.kmbKMB]+)', cell_text)
                    if bounty_match:
                        program["maxBounty"] = self._parse_bounty_string(
                            bounty_match.group(1),
                        )

            programs.append(program)

        return programs if len(programs) > 5 else None

    def _parse_listing_links(self, soup: BeautifulSoup) -> list[dict[str, Any]] | None:
        """Parse program list dari link/view buttons sebagai fallback."""
        programs: list[dict[str, Any]] = []
        seen_slugs: set[str] = set()

        # Cari semua link yang mengandung pola slug
        for link in soup.find_all("a", href=True):
            href = link["href"]

            # Pattern: /bug-bounty/{slug}/ atau /explore/{slug}/
            match = re.match(r"/(?:bug-bounty|explore)/([^/]+)", href)
            if not match:
                continue

            slug = match.group(1)
            if slug in seen_slugs or len(slug) < 2:
                continue

            seen_slugs.add(slug)
            program: dict[str, Any] = {
                "slug": slug,
                "name": link.get_text(strip=True) or slug,
                "status": "active",
            }

            # Extract bounty dari text sekitar
            parent = link.parent
            if parent:
                parent_text = parent.get_text()
                bounty_match = re.search(r'\$\s*([0-9,.kmbKMB]+)', parent_text)
                if bounty_match:
                    program["maxBounty"] = self._parse_bounty_string(
                        bounty_match.group(1),
                    )

            programs.append(program)

        return programs if len(programs) > 5 else None

    def _parse_contracts_from_html(
        self,
        soup: BeautifulSoup,
        page_url: str,
    ) -> list[dict[str, str]] | None:
        """Extract smart contract addresses dari HTML detail page.

        Mencari:
          1. Etherscan links (pola: etherscan.io/address/0x...)
          2. Contract address text (0x-prefixed hex)
          3. Asset/smart-contract sections
        """
        contracts: list[dict[str, str]] = []
        seen_addresses: set[str] = set()

        # Method 1: Cari semua Etherscan links
        for link in soup.find_all("a", href=re.compile(r"etherscan\.io/address/0x", re.I)):
            href = link.get("href", "")
            addr_match = re.search(r"0x[a-fA-F0-9]{40}", href)
            if not addr_match:
                continue

            address = addr_match.group(0)
            if address in seen_addresses:
                continue
            seen_addresses.add(address)

            # Detect chain dari URL
            chain = self._detect_chain_from_url(href)
            name = link.get_text(strip=True)

            contracts.append({
                "address": address,
                "chain": chain,
                "name": name,
                "source_type": "verified",
            })

        # Method 2: Cari text pola 0x address
        for tag in soup.find_all(["p", "span", "div", "td", "code"]):
            text = tag.get_text(strip=True)
            for addr in re.findall(r"0x[a-fA-F0-9]{40}", text):
                if addr not in seen_addresses:
                    seen_addresses.add(addr)
                    contracts.append({
                        "address": addr,
                        "chain": "",
                        "name": "",
                        "source_type": "verified",
                    })

        # Method 3: Cari section dengan class mengandung "contract" atau "asset"
        for section in soup.find_all(class_=re.compile(r"contract|asset|scope", re.I)):
            section_text = section.get_text()
            for addr in re.findall(r"0x[a-fA-F0-9]{40}", section_text):
                if addr not in seen_addresses:
                    seen_addresses.add(addr)
                    contracts.append({
                        "address": addr,
                        "chain": "",
                        "name": "",
                        "source_type": "verified",
                    })

        return contracts if contracts else None

    # ═══════════════════════════════════════════════════════════
    #  PARSING: HTML Helpers
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _parse_bounty_from_html(soup: BeautifulSoup) -> float | None:
        """Extract max bounty dari halaman detail."""
        text = soup.get_text()

        # Cari pola "max bounty" atau "$X,XXX,XXX"
        patterns = [
            r"(?:max|maximum|up to)\s*(?:bounty|reward)?\s*\$?\s*([0-9,]+(?:\.\d+)?)\s*(?:USD|USDC|USDT)?",
            r"\$\s*([0-9,]+(?:\.\d+)?)\s*(?:USD|USDC|USDT)?",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                try:
                    return float(match.group(1).replace(",", ""))
                except ValueError:
                    continue

        return None

    @staticmethod
    def _parse_chains_from_html(soup: BeautifulSoup) -> list[str] | None:
        """Extract blockchain names dari halaman detail."""
        chains: list[str] = []
        text = soup.get_text()

        # Known EVM chains
        known_chains = [
            "Ethereum", "Arbitrum", "Optimism", "Polygon", "BNB Chain",
            "Avalanche", "Fantom", "Base", "Mantle", "Linea", "Scroll",
            "zkSync", "StarkNet", "Solana", "TON", "Near", "Sui",
            "Aptos", "Celestia", "Blast", "Mode", "Metis", "Manta",
            "Kava", "Fraxtal", "Celo", "Moonbeam", "Moonriver",
        ]

        for chain in known_chains:
            if chain.lower() in text.lower() and chain not in chains:
                chains.append(chain)

        return chains if chains else None

    @staticmethod
    def _detect_chain_from_url(url: str) -> str:
        """Detect blockchain dari URL explorer."""
        domain = urlparse(url).netloc.lower()

        # Order matters: check specific subdomains before generic ones
        chain_map = [
            ("optimistic.etherscan.io", "optimism"),
            ("etherscan.io", "ethereum"),
            ("arbiscan.io", "arbitrum"),
            ("polygonscan.com", "polygon"),
            ("bscscan.com", "bsc"),
            ("snowtrace.io", "avalanche"),
            ("snowscan.xyz", "avalanche"),
            ("ftmscan.com", "fantom"),
            ("basescan.org", "base"),
            ("mantlescan.xyz", "mantle"),
            ("lineascan.build", "linea"),
            ("scrollscan.com", "scroll"),
            ("zksync.io", "zksync"),
        ]

        for key, chain in chain_map:
            if key in domain:
                return chain

        return "ethereum"  # default

    @staticmethod
    def _parse_bounty_string(s: str) -> float | None:
        """Parse formatted bounty string ke float.

        Contoh: "250k" → 250000, "3M" → 3000000, "1,500" → 1500
        Handles: $ prefix, whitespace, commas, empty strings.
        """
        s = s.strip()
        if not s:
            return None

        # Strip leading currency symbols ($, €, etc.)
        s = s.lstrip("$€£¥₿")

        s = s.replace(",", "").strip().lower()
        if not s:
            return None

        multipliers = {"k": 1000, "m": 1000000, "b": 1000000000}

        if s[-1] in multipliers:
            try:
                return float(s[:-1]) * multipliers[s[-1]]
            except ValueError:
                return None

        try:
            return float(s)
        except ValueError:
            return None

    # ═══════════════════════════════════════════════════════════
    #  SMART CONTRACT FILTERING
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _has_smart_contracts(detail: dict) -> bool:
        """Check apakah program memiliki smart contract assets."""
        contracts = detail.get("contracts", [])
        assets = detail.get("assets", [])

        # Check contracts list
        if isinstance(contracts, list):
            for c in contracts:
                if isinstance(c, dict) and len(c.get("address", "")) > 30:
                    return True
                if isinstance(c, str) and len(c) > 30:
                    return True

        # Check assets list with type filter
        if isinstance(assets, list):
            for a in assets:
                if isinstance(a, dict):
                    asset_type = str(a.get("type", "") or "").lower()
                    url = str(a.get("url", "") or "")
                    if asset_type == "smart_contract" or "etherscan" in url.lower():
                        return True

        return False

    def _filter_smart_contracts(
        self,
        contracts: list[Any],
    ) -> list[dict[str, str]]:
        """Filter hanya smart contract addresses.

        Menghapus:
        - Non-address items (web-app URLs, etc.)
        - Duplicate addresses
        - Invalid addresses (too short)
        """
        seen: set[str] = set()
        result: list[dict[str, str]] = []

        for c in contracts:
            if isinstance(c, str):
                # Raw address string
                addrs = re.findall(r"0x[a-fA-F0-9]{40}", c)
                for addr in addrs:
                    if addr not in seen:
                        seen.add(addr)
                        result.append({
                            "address": addr,
                            "chain": "",
                            "name": "",
                        })
            elif isinstance(c, dict):
                addr = str(c.get("address", "") or "")
                asset_type = str(c.get("type", "") or "").lower()
                url = str(c.get("url", "") or "")

                # Extract address from URL if not provided directly
                if not addr or len(addr) < 30:
                    addr_match = re.search(r"0x[a-fA-F0-9]{40}", url)
                    if addr_match:
                        addr = addr_match.group(0)

                # Skip if no valid address
                if not addr or len(addr) < 30:
                    continue

                # Skip if not smart contract
                if asset_type and asset_type != "smart_contract":
                    continue

                if addr not in seen:
                    seen.add(addr)
                    chain = str(c.get("chain", "") or "")
                    name = str(c.get("name", "") or "")
                    result.append({
                        "address": addr,
                        "chain": chain or self._detect_chain_from_url(url),
                        "name": name,
                    })

        return result

    # ═══════════════════════════════════════════════════════════
    #  NORMALIZATION
    # ═══════════════════════════════════════════════════════════

    def _normalize_programs(self, raw: list[dict]) -> list[dict]:
        """Normalisasi list program ke format internal."""
        return [self._normalize_program(p, p.get("slug", "")) for p in raw]

    def _normalize_program(self, raw: dict, slug_hint: str = "") -> dict:
        """Map field names dari Immunefi site ke format internal.

        Internal format yang konsisten dengan Program model:
            slug, name, chains, maxBounty, minBounty, currency,
            status, description, project_url, logo, tags, contracts,
            assets, rewards, updatedAt
        """
        slug = raw.get("slug") or raw.get("id", "") or slug_hint

        # Extract contracts dengan filtering smart contract only
        raw_contracts = raw.get("contracts", raw.get("assets", raw.get("targets", [])))
        if isinstance(raw_contracts, list):
            contracts = self._filter_smart_contracts(raw_contracts)
        else:
            contracts = []

        # Extract assets (unfiltered, for reference)
        assets = raw.get("assets", raw.get("targets", []))

        return {
            "slug": slug,
            "name": raw.get("name", slug),
            "chains": raw.get("chains", raw.get("blockchains", [])),
            "maxBounty": raw.get("maxBounty") or raw.get("max_bounty"),
            "minBounty": raw.get("minBounty") or raw.get("min_bounty"),
            "currency": raw.get("currency", "USD"),
            "status": raw.get("status", "active"),
            "description": raw.get("description", ""),
            "project_url": (
                raw.get("projectUrl")
                or raw.get("project_url")
                or f"https://immunefi.com/bug-bounty/{slug}/information/"
            ),
            "logo": raw.get("logo") or raw.get("logoUrl", ""),
            "tags": raw.get("tags", raw.get("technologies", [])),
            "contracts": contracts,
            "assets": assets,
            "social": raw.get("social", raw.get("links", [])),
            "rewards": raw.get("rewards", raw.get("rewardDetails", {})),
            "updatedAt": (
                raw.get("updatedAt")
                or raw.get("updated_at")
                or raw.get("lastUpdated", "")
            ),
            "source": "immunefi_web",
            "slug_hint": slug_hint,
        }

    # ═══════════════════════════════════════════════════════════
    #  CACHE
    # ═══════════════════════════════════════════════════════════

    def _cache_path(self) -> Path:
        return Path(self._cache_dir) / "programs_list.json"

    def _save_cache(self, programs: list[dict]) -> None:
        try:
            path = self._cache_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(programs, indent=2))
            log.info("web_scraper.cache_saved", path=str(path), count=len(programs))
        except Exception as e:
            log.warning("web_scraper.cache_save_error", error=str(e)[:100])

    def _load_cache(self) -> list[dict]:
        try:
            path = self._cache_path()
            if path.exists():
                data = json.loads(path.read_text())
                log.info("web_scraper.cache_loaded", path=str(path), count=len(data))
                return data if isinstance(data, list) else data.get("data", [])
        except Exception as e:
            log.warning("web_scraper.cache_load_error", error=str(e)[:100])
        return []

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
