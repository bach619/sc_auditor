"""ForkAwareGitHubProvider — Source provider yang cek fork dulu.

Sebelum mencari source di seluruh GitHub, provider ini ngecek:
  1. Apakah contract address ini ada di repo yang sudah di-fork?
  2. Kalau iya, fetch dari fork (lebih cepat, unlimited)
  3. Kalau tidak, fallback ke GitHubProvider biasa

Priority: lebih tinggi dari GitHubProvider biasa (harus dipanggil duluan).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx
import structlog

from src.models import SourceResult
from src.providers.github import GitHubProvider, _detect_compiler_from_source, _detect_license_from_source

log = structlog.get_logger()

GITHUB_TOKEN: str | None = os.getenv("GITHUB_TOKEN") or None

# Path ke fork index dari Service 02 Immunefi
FORK_INDEX_PATH = Path(os.getenv("FORK_INDEX_PATH", "/data/immunefi/indexes/forks.json"))


class ForkAwareGitHubProvider:
    """GitHub provider yang cek fork dulu sebelum search global.

    Membaca fork index dari Service 02. Kalau repo yang cocok sudah di-fork,
    fetch langsung dari fork — lebih cepat dan tidak kena rate limit.
    """

    name = "fork_aware_github"
    priority = -1  # Lebih tinggi dari github (priority=0)

    def __init__(self) -> None:
        self._fallback = GitHubProvider()
        self._fork_index: dict[str, Any] = {}
        self._fork_index_loaded = False

    def _load_fork_index(self) -> dict[str, Any]:
        """Load fork index dari file JSON Service 02."""
        if self._fork_index_loaded:
            return self._fork_index

        try:
            if FORK_INDEX_PATH.exists():
                self._fork_index = json.loads(FORK_INDEX_PATH.read_text())
                log.info(
                    "fork_aware.index_loaded",
                    path=str(FORK_INDEX_PATH),
                    entries=len(self._fork_index),
                )
            else:
                log.info("fork_aware.index_not_found", path=str(FORK_INDEX_PATH))
        except Exception as e:
            log.warning("fork_aware.index_load_error", error=str(e)[:100])
            self._fork_index = {}

        self._fork_index_loaded = True
        return self._fork_index

    def _find_fork_for_address(self, address: str) -> dict | None:
        """Cari di fork index apakah address ini ada di repo yang sudah di-fork.

        Returns:
            Dict dengan fork_info (clone_url, dll) atau None.
        """
        fork_index = self._load_fork_index()
        addr_lower = address.lower().replace("0x", "")

        for repo_key, fork_info in fork_index.items():
            if not isinstance(fork_info, dict):
                continue
            if fork_info.get("status") != "success":
                continue

            fork_url = fork_info.get("fork_url", "")
            if not fork_url:
                continue

            # Extract owner/repo dari fork_url
            # https://github.com/owner/repo
            parts = fork_url.rstrip("/").split("/")
            if len(parts) >= 2:
                fork_owner = parts[-2]
                fork_repo = parts[-1]

                # Return fork info — nanti kita search di repo ini
                return {
                    "owner": fork_owner,
                    "repo": fork_repo,
                    "fork_url": fork_url,
                    "original": repo_key,
                }

        return None

    async def _fetch_from_fork(
        self,
        fork_info: dict,
        address: str,
    ) -> SourceResult | None:
        """Coba fetch source dari forked repo via GitHub code search.

        Search dalam repo fork aja (repo:{owner}/{repo} qualifier).
        """
        owner = fork_info["owner"]
        repo = fork_info["repo"]
        addr_stripped = address.lower().replace("0x", "")

        query = f"repo:{owner}/{repo} {addr_stripped} language:solidity"

        headers: dict[str, str] = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "vyper-source-service/0.1.0",
        }
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            log.info(
                "fork_aware.search_in_fork",
                repo=f"{owner}/{repo}",
                address=address,
            )

            try:
                search_resp = await client.get(
                    f"https://api.github.com/search/code",
                    params={"q": query, "per_page": 5, "sort": "indexed"},
                )
                if search_resp.status_code == 403:
                    log.warning("fork_aware.rate_limited")
                    return None
                search_resp.raise_for_status()
                search_data = search_resp.json()
            except Exception as e:
                log.warning("fork_aware.search_failed", error=str(e)[:100])
                return None

            items = search_data.get("items", [])
            if not items:
                log.info("fork_aware.no_results_in_fork", repo=f"{owner}/{repo}")
                return None

            # Fetch file pertama yang cocok
            for item in items[:3]:
                file_path = item.get("path", "")

                # Coba main dulu, fallback ke master
                for branch in ["main", "master"]:
                    raw_url = (
                        f"https://raw.githubusercontent.com/"
                        f"{owner}/{repo}/{branch}/{file_path}"
                    )
                    try:
                        raw_resp = await client.get(raw_url)
                        if raw_resp.status_code == 200:
                            content = raw_resp.text
                            compiler = _detect_compiler_from_source(content)
                            license_ = _detect_license_from_source(content)
                            filename = file_path.rsplit("/", 1)[-1]

                            log.info(
                                "fork_aware.success",
                                repo=f"{owner}/{repo}",
                                path=file_path,
                                branch=branch,
                            )

                            return SourceResult(
                                sources={filename: content},
                                compiler_version=compiler,
                                license=license_,
                                provider=self.name,
                                constructor_args=None,
                            )
                    except Exception:
                        continue

        return None

    async def fetch(self, chain: str, address: str) -> SourceResult | None:
        """Coba fork dulu, fallback ke GitHub search biasa.

        Args:
            chain: Blockchain name.
            address: Contract address.

        Returns:
            SourceResult dari fork atau GitHub, None jika tidak ditemukan.
        """
        # 1. Cek apakah ada fork yang relevan
        fork_info = self._find_fork_for_address(address)
        if fork_info:
            result = await self._fetch_from_fork(fork_info, address)
            if result:
                return result

        # 2. Fallback ke GitHub search biasa
        log.info("fork_aware.fallback_to_github", address=address)
        return await self._fallback.fetch(chain, address)
