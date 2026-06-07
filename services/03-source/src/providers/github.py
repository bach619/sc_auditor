"""GitHub provider — best-effort source discovery via GitHub search.

This provider searches GitHub public repositories for Solidity files
that contain the target contract address. It is a best-effort provider
and may fail to find sources even when they exist on GitHub.

Without a ``GITHUB_TOKEN`` environment variable, the unauthenticated
rate limit is 60 requests/hour.
"""

from __future__ import annotations

import os
import re
from typing import Any

import httpx
import structlog

from src.models import SourceResult

log = structlog.get_logger()

# Default token — prefer env var at runtime
GITHUB_TOKEN: str | None = os.getenv("GITHUB_TOKEN") or None
GITHUB_API = "https://api.github.com"


class GitHubProvider:
    """Source provider for GitHub — searches public repos for contract source.

    This is a *best-effort* provider. It searches GitHub for Solidity files
    matching the contract address, then tries to fetch the file content.
    """

    name = "github"

    async def fetch(self, chain: str, address: str) -> SourceResult | None:
        """Search GitHub for verified source code of the given contract.

        Args:
            chain: Blockchain name (used for logging only).
            address: Contract address to search for.

        Returns:
            SourceResult if a matching Solidity file was found, None otherwise.
        """
        # Normalise address for searching (case-insensitive)
        addr = address.lower()
        # Strip 0x prefix for broader matching
        addr_stripped = addr.replace("0x", "")

        # Build search query — look for the address in Solidity files
        query = f"{addr_stripped} language:solidity"

        headers: dict[str, str] = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "vyper-source-service/0.1.0",
        }
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        else:
            log.warning("github.no_token", detail="Rate limited to 60 req/hr. Set GITHUB_TOKEN for higher limits.")

        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            # Step 1: Search code
            log.info("github.search", chain=chain, address=address, query=query)
            try:
                search_resp = await client.get(
                    f"{GITHUB_API}/search/code",
                    params={"q": query, "per_page": 5, "sort": "indexed"},
                )
                if search_resp.status_code == 403:
                    log.warning("github.rate_limited", chain=chain, address=address)
                    return None
                search_resp.raise_for_status()
                search_data: dict[str, Any] = search_resp.json()
            except httpx.RequestError as exc:
                log.warning("github.search_failed", chain=chain, address=address, error=str(exc))
                return None
            except httpx.HTTPStatusError as exc:
                log.warning("github.http_error", chain=chain, address=address, status=exc.response.status_code)
                return None

            items = search_data.get("items", [])
            if not items:
                log.info("github.no_results", chain=chain, address=address)
                return None

            # Step 2: Try to fetch the first matching file's raw content
            for item in items[:3]:
                repo_full_name = item.get("repository", {}).get("full_name", "")
                file_path = item.get("path", "")
                item.get("html_url", "")

                log.info("github.found_file", repo=repo_full_name, path=file_path)

                # Construct raw URL
                raw_url = f"https://raw.githubusercontent.com/{repo_full_name}/main/{file_path}"

                try:
                    raw_resp = await client.get(raw_url)
                    if raw_resp.status_code == 404:
                        # Try 'master' branch
                        raw_url = raw_url.replace("/main/", "/master/")
                        raw_resp = await client.get(raw_url)
                    if raw_resp.status_code != 200:
                        continue
                    raw_resp.raise_for_status()
                    content: str = raw_resp.text

                    compiler_version = _detect_compiler_from_source(content)
                    license_ = _detect_license_from_source(content)

                    # Use the last path component as the filename
                    filename = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path

                    return SourceResult(
                        sources={filename: content},
                        compiler_version=compiler_version,
                        license=license_,
                        provider=self.name,
                        constructor_args=None,
                    )
                except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                    log.warning("github.fetch_failed", repo=repo_full_name, path=file_path, error=str(exc))
                    continue

        log.info("github.no_sources_after_search", chain=chain, address=address)
        return None


# ── Helper: detect compiler version from pragma ────────────

_PRAGMA_RE = re.compile(r"pragma\s+solidity\s+[^;]+;", re.IGNORECASE)
_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)")
_LICENSE_RE = re.compile(r"//\s*SPDX-License-Identifier:\s*(\S+)")


def _detect_compiler_from_source(source: str) -> str:
    """Extract compiler version from pragma solidity directive."""
    match = _PRAGMA_RE.search(source)
    if match:
        version_match = _VERSION_RE.search(match.group())
        if version_match:
            return version_match.group(1)
    return ""


def _detect_license_from_source(source: str) -> str | None:
    """Extract SPDX license identifier from source file."""
    match = _LICENSE_RE.search(source)
    return match.group(1) if match else None
