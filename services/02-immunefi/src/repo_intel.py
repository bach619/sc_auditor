"""RepoIntel — Deep intelligence for detected GitHub repositories.

Menggunakan GitHub API (tanpa auth untuk public repos, dengan token opsional)
untuk mengumpulkan data tambahan tentang repositori yang terdeteksi:
  - Star count, fork count
  - Last commit / last push
  - Language, topics
  - Open issues count
  - Apakah repo sudah di-archive
  - README content (untuk keyword analysis)

Data di-cache di EnhancedJSONStorage agar tidak rate-limit GitHub API.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from src.models import Program
from src.storage import EnhancedJSONStorage

log = structlog.get_logger()


class RepoIntel:
    """Fetch and cache intelligence data for GitHub repos.

    Usage:
        intel = RepoIntel(storage, client)
        await intel.enrich_program(program)
        report = await intel.bulk_enrich(programs)
    """

    GITHUB_API = "https://api.github.com"

    def __init__(
        self,
        storage: EnhancedJSONStorage,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.storage = storage
        self._client = client
        self._token = os.getenv("GITHUB_TOKEN", "")

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    def _cache_key(self, repo_owner: str, repo_name: str) -> str:
        return f"repo_intel:{repo_owner}/{repo_name}"

    # ── Fetch Repo Data ────────────────────────────────────

    async def fetch_repo_data(
        self,
        owner: str,
        repo: str,
    ) -> dict[str, Any] | None:
        """Fetch repo metadata from GitHub API.

        Caches result in storage index for 24 hours.
        Returns None if repo not found.
        """
        cache_key = self._cache_key(owner, repo)
        cached = self.storage.get_index(cache_key)
        if isinstance(cached, dict) and cached.get("_cached_at"):
            # Check cache freshness (24h)
            try:
                cached_at = datetime.fromisoformat(cached["_cached_at"])
                if cached_at.tzinfo is None:
                    cached_at = cached_at.replace(tzinfo=UTC)
                age = datetime.now(UTC) - cached_at
                if age.total_seconds() < 86400:  # 24h
                    return cached
            except (ValueError, TypeError):
                pass

        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.GITHUB_API}/repos/{owner}/{repo}",
                headers=self._headers(),
            )
            if resp.status_code == 404:
                self._cache_repo_data(cache_key, {"_error": "not_found", "_cached_at": datetime.now(UTC).isoformat()})  # noqa: E501
                return None
            if resp.status_code == 403:
                log.warning("repo_intel.rate_limited", repo=f"{owner}/{repo}")
                # Return stale cache if available
                return cached if isinstance(cached, dict) else None
            resp.raise_for_status()

            data = resp.json()
            enriched = self._extract_repo_info(data)
            self._cache_repo_data(cache_key, enriched)
            return enriched

        except httpx.TimeoutException:
            log.warning("repo_intel.timeout", repo=f"{owner}/{repo}")
            return cached if isinstance(cached, dict) else None
        except httpx.HTTPStatusError as e:
            log.warning("repo_intel.http_error", repo=f"{owner}/{repo}", status=e.response.status_code)  # noqa: E501
            return None

    def _extract_repo_info(self, data: dict) -> dict:
        """Extract relevant fields from GitHub API response."""
        return {
            "owner": data.get("owner", {}).get("login", ""),
            "name": data.get("name", ""),
            "full_name": data.get("full_name", ""),
            "description": data.get("description", ""),
            "url": data.get("html_url", ""),
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "open_issues": data.get("open_issues_count", 0),
            "language": data.get("language", ""),
            "topics": data.get("topics", []),
            "license": data.get("license", {}).get("spdx_id", "") if data.get("license") else "",
            "archived": data.get("archived", False),
            "disabled": data.get("disabled", False),
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
            "pushed_at": data.get("pushed_at", ""),
            "size_kb": data.get("size", 0),
            "default_branch": data.get("default_branch", "main"),
            "_cached_at": datetime.now(UTC).isoformat(),
        }

    def _cache_repo_data(self, cache_key: str, data: dict) -> None:
        """Store repo intel in storage index."""
        try:
            self.storage.rebuild_indexes({cache_key: data}, index_name=cache_key)
        except Exception:
            pass  # cache failure is non-critical

    # ── Enrich Programs ────────────────────────────────────

    async def enrich_program(self, program: Program) -> dict[str, Any]:
        """Fetch intel for all repos in a program.

        Returns {repo_key: repo_data} mapping.
        """
        results: dict[str, Any] = {}
        for repo in program.repos:
            repo_key = f"{repo.owner}/{repo.repo}"
            data = await self.fetch_repo_data(repo.owner, repo.repo)
            if data:
                results[repo_key] = data
            else:
                results[repo_key] = {"error": "not_found"}
        return results

    async def bulk_enrich(
        self,
        programs: dict[str, Program],
        max_programs: int = 20,
    ) -> list[dict[str, Any]]:
        """Enrich all programs with repo intel (limited per call)."""
        enriched = []
        count = 0

        for slug, prog in programs.items():
            if count >= max_programs:
                break
            if not prog.repos:
                continue

            repo_data = await self.enrich_program(prog)
            enriched.append({
                "slug": slug,
                "name": prog.name,
                "repos": repo_data,
            })
            count += 1

        return enriched

    # ── Assessment ─────────────────────────────────────────

    def assess_repo_health(self, repo_data: dict) -> dict[str, Any]:
        """Assess repository health based on GitHub metadata.

        Returns health score (0–100) and flags.
        """
        score = 50  # baseline
        flags: list[str] = []

        if repo_data.get("archived"):
            score -= 30
            flags.append("archived")

        if repo_data.get("disabled"):
            score -= 40
            flags.append("disabled")

        stars = repo_data.get("stars", 0)
        if stars >= 1000:
            score += 20
            flags.append("popular")
        elif stars >= 100:
            score += 10

        forks = repo_data.get("forks", 0)
        if forks >= 100:
            score += 10

        if repo_data.get("pushed_at"):
            try:
                pushed = datetime.fromisoformat(repo_data["pushed_at"].replace("Z", "+00:00"))
                age_days = (datetime.now(UTC) - pushed).days
                if age_days < 30:
                    score += 15
                    flags.append("active_development")
                elif age_days < 180:
                    score += 5
                else:
                    score -= 10
                    flags.append("stale")
            except (ValueError, TypeError):
                pass

        if repo_data.get("license"):
            score += 5

        if repo_data.get("language"):
            score += 5  # has a primary language

        return {
            "health_score": max(0, min(100, score)),
            "flags": flags,
            "stars": stars,
            "forks": forks,
        }

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# ── Compatibility alias ────────────────────────────────────
# RepoDeepAnalyzer adalah alias untuk RepoIntel, sesuai dengan
# nama class yang digunakan di daily_agenda document.
RepoDeepAnalyzer = RepoIntel
