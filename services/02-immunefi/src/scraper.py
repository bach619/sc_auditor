"""ImmunefiScraper — Fetches bug bounty programs from the Immunefi GitHub mirror.

Now with multi-source fallback:
  1. GitHub mirror (primary — reliable, structured)
  2. ImmunefiWebScraper (fallback — live immunefi.com)
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = structlog.get_logger()

# ── Constants ──────────────────────────────────────────────

PROGRAM_LIST_URL = (
    "https://raw.githubusercontent.com/"
    "infosec-us-team/Immunefi-Bug-Bounty-Programs-Unofficial/main/projects.json"
)
PROGRAM_DETAIL_URL = (
    "https://raw.githubusercontent.com/"
    "infosec-us-team/Immunefi-Bug-Bounty-Programs-Unofficial/main/project/{slug}.json"
)

TIMEOUT = httpx.Timeout(30.0, connect=10.0)
MAX_RETRIES = 3


# ── Exceptions ─────────────────────────────────────────────

class ScraperError(Exception):
    """Base scraper exception."""
    pass


class ProgramNotFoundError(ScraperError):
    """Program slug not found on remote."""
    pass


# ── Retry Decorator ───────────────────────────────────────

scraper_retry = retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception_type(
        (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError)
    ),
    reraise=True,
)


# ── Scraper ────────────────────────────────────────────────

class ImmunefiScraper:
    """Fetch program data from the Immunefi GitHub mirror.

    Usage:
        async with ImmunefiScraper() as scraper:
            programs = await scraper.fetch_program_list()
            detail = await scraper.fetch_program_detail("some-slug")
    """

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = client

    async def __aenter__(self) -> ImmunefiScraper:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client is not None:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Scraper not initialized (use 'async with' or pass a client)")
        return self._client

    # ── Public Methods ──────────────────────────────────────

    @scraper_retry
    async def fetch_program_list(self) -> list[dict[str, Any]]:
        """Fetch the full program list from GitHub mirror (projects.json).

        ImmunefiWebScraper (live site) is handled by the provider registry
        in sync.py — not duplicated here.

        Returns a list of program dicts with keys:
            slug, name, chains, maxBounty, status, etc.
        """
        log.info("fetch_program_list.start")
        try:
            resp = await self.client.get(PROGRAM_LIST_URL)
            resp.raise_for_status()
            data: list[dict[str, Any]] = resp.json()
            log.info("fetch_program_list.success", count=len(data))
            return data
        except httpx.HTTPStatusError as e:
            log.warning("fetch_program_list.http_error", status=e.response.status_code)
            raise
        except Exception as e:
            log.warning("fetch_program_list.error", error=str(e))
            raise

    @scraper_retry
    async def fetch_program_detail(self, slug: str) -> dict[str, Any]:
        """Fetch detail for a single program by slug (from GitHub mirror).

        Returns the full program detail dict from project/{slug}.json.
        Raises ProgramNotFoundError if slug does not exist.

        Note: ImmunefiWebScraper (live site) is handled by the provider
        registry in sync.py — not duplicated here.
        """
        url = PROGRAM_DETAIL_URL.format(slug=slug)
        log.info("fetch_program_detail.start", slug=slug)
        try:
            resp = await self.client.get(url)
            if resp.status_code == 404:
                raise ProgramNotFoundError(f"Program '{slug}' not found")
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            log.info("fetch_program_detail.success", slug=slug)
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ProgramNotFoundError(f"Program '{slug}' not found")
            log.warning("fetch_program_detail.http_error", slug=slug, status=e.response.status_code)
            raise
        except ProgramNotFoundError:
            raise
        except Exception as e:
            log.warning("fetch_program_detail.error", slug=slug, error=str(e))
            raise

    # ── Parsing Helpers ─────────────────────────────────────

    @staticmethod
    def parse_contracts(detail: dict[str, Any]) -> list[dict[str, str]]:
        """Extract smart contract addresses from program detail.

        Handles multiple formats:
        - GitHub mirror: assets[] with {url, type, description}
        - Live API: contracts[] with {address, chain, name}
        - Raw: list of address strings

        Only returns assets where type='smart_contract' (in-scope).
        Detects chain from explorer URL when available.
        """
        contracts: list[dict[str, str]] = []
        seen: set[str] = set()

        # Format 1: assets[] (GitHub mirror format)
        raw_assets = detail.get("assets", [])
        if isinstance(raw_assets, list):
            for asset in raw_assets:
                if isinstance(asset, dict):
                    asset_type = str(asset.get("type", "") or "").lower()
                    url = str(asset.get("url", "") or "")

                    # Hanya smart contract type yang in-scope
                    if asset_type and asset_type != "smart_contract":
                        continue

                    # Extract address dari URL
                    addr = str(asset.get("address", "") or "")
                    if not addr or len(addr) < 30:
                        addr_match = re.search(r"0x[a-fA-F0-9]{40}", url)
                        if addr_match:
                            addr = addr_match.group(0)

                    if addr and len(addr) == 42 and addr not in seen:
                        seen.add(addr)
                        chain = ImmunefiScraper._detect_chain_from_url(url)
                        name = str(asset.get("description", "") or asset.get("name", ""))
                        contracts.append({
                            "address": addr,
                            "chain": chain,
                            "name": name,
                        })

        # Format 2: contracts[] (API format)
        raw_contracts = detail.get("contracts", [])
        if isinstance(raw_contracts, list):
            for c in raw_contracts:
                if isinstance(c, dict):
                    addr = str(c.get("address", "") or "")
                    if addr and len(addr) == 42 and addr not in seen:
                        seen.add(addr)
                        contracts.append({
                            "address": addr,
                            "chain": str(c.get("chain", "") or ""),
                            "name": str(c.get("name", "") or ""),
                        })
                elif isinstance(c, str):
                    addr = c.strip()
                    if addr.startswith("0x") and len(addr) == 42 and addr not in seen:
                        seen.add(addr)
                        contracts.append({"address": addr, "chain": "", "name": ""})

        # Format 3: targets[] (alternative format)
        raw_targets = detail.get("targets", [])
        if isinstance(raw_targets, list):
            for t in raw_targets:
                if isinstance(t, dict):
                    addr = str(t.get("address", "") or "")
                    if addr and len(addr) == 42 and addr not in seen:
                        seen.add(addr)
                        contracts.append({
                            "address": addr,
                            "chain": str(t.get("chain", "") or ""),
                            "name": str(t.get("name", "") or ""),
                        })

        return contracts

    @staticmethod
    def _detect_chain_from_url(url: str) -> str:
        """Detect blockchain dari explorer URL.

        Order matters: more specific subdomains (e.g. optimistic.etherscan.io)
        must be checked before their parent domain (etherscan.io).
        """
        domain = url.lower()
        # Check specific subdomain patterns FIRST (before generic etherscan.io)
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

    @staticmethod
    def parse_social_links(detail: dict[str, Any]) -> list[str]:
        """Extract all social/profile URLs from program detail."""
        links: list[str] = []
        urls = detail.get("social", []) or detail.get("links", []) or detail.get("urls", [])
        if isinstance(urls, list):
            for u in urls:
                if isinstance(u, dict):
                    url = u.get("url", "") or u.get("link", "")
                    if url:
                        links.append(url)
                elif isinstance(u, str):
                    links.append(u)
        return links
