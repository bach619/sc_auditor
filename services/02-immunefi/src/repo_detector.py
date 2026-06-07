"""RepoDetector — Extracts GitHub repository URLs from program data."""

from __future__ import annotations

import re
from typing import Any

import structlog

from src.models import Repo

log = structlog.get_logger()

# ── GitHub URL Patterns ────────────────────────────────────

GITHUB_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?github\.com/([a-zA-Z0-9._-]+)/([a-zA-Z0-9._-]+)"
    r"(?:\.git)?/?",
    re.IGNORECASE,
)

GITHUB_IO_PATTERN = re.compile(
    r"https?://([a-zA-Z0-9_-]+)\.github\.io/([a-zA-Z0-9._-]+)/?",
    re.IGNORECASE,
)

KNOWN_GITHUB_DOMAINS = {"github.com", "www.github.com", "raw.githubusercontent.com"}


# ── RepoDetector ───────────────────────────────────────────

class RepoDetector:
    """Detect and extract GitHub repositories from program detail data.

    Sources checked (in order):
      1. project_url field
      2. Social/links fields
      3. Documentation URLs
      4. Contract source scanning (optional, stub)
    """

    def detect(self, program_detail: dict[str, Any]) -> list[Repo]:
        """Extract all unique GitHub repos from a program detail dict.

        Returns a list of Repo models with deduplication by canonical URL.
        """
        seen: set[str] = set()
        repos: list[Repo] = []

        # 1. Check project_url
        project_url = program_detail.get("project_url", "") or program_detail.get("url", "")
        if project_url:
            parsed = self._parse_github_url(project_url)
            if parsed:
                canonical = self._canonical_url(parsed["owner"], parsed["repo"])
                if canonical not in seen:
                    seen.add(canonical)
                    repos.append(Repo(
                        url=canonical,
                        owner=parsed["owner"],
                        repo=parsed["repo"],
                        source="project_url",
                    ))

        # 2. Check social / links
        social_fields = ["social", "links", "urls", "social_links"]
        for field in social_fields:
            items = program_detail.get(field, []) or program_detail.get(field.capitalize(), [])
            if isinstance(items, list):
                for item in items:
                    url = ""
                    if isinstance(item, dict):
                        url = item.get("url", "") or item.get("link", "") or item.get("value", "")
                    elif isinstance(item, str):
                        url = item
                    if url:
                        self._add_repo(url, "social_link", seen, repos)

        # 3. Check documentation URLs
        doc_url = program_detail.get("documentation", "") or program_detail.get("docs", "")
        if doc_url:
            self._add_repo(doc_url, "documentation", seen, repos)

        # 4. Check contracts for source code URLs (via source field)
        contracts = program_detail.get("contracts", [])
        if isinstance(contracts, list):
            for c in contracts:
                if isinstance(c, dict):
                    source_url = c.get("source", "") or c.get("sourceUrl", "")
                    if source_url:
                        self._add_repo(source_url, "contract_source", seen, repos)

        log.info("repo_detector.complete", repos_found=len(repos))
        return repos

    # ── Internal Helpers ────────────────────────────────────

    def _add_repo(
        self,
        url: str,
        source: str,
        seen: set[str],
        repos: list[Repo],
    ) -> None:
        """Parse a URL and add it to repos if valid and unique."""
        parsed = self._parse_github_url(url)
        if not parsed:
            return
        canonical = self._canonical_url(parsed["owner"], parsed["repo"])
        if canonical not in seen:
            seen.add(canonical)
            repos.append(Repo(
                url=canonical,
                owner=parsed["owner"],
                repo=parsed["repo"],
                source=source,
            ))

    @staticmethod
    def _parse_github_url(url: str) -> dict[str, str] | None:
        """Parse a GitHub URL into owner/repo components.

        Handles formats:
          - https://github.com/owner/repo
          - https://github.com/owner/repo.git
          - https://www.github.com/owner/repo
          - git@github.com:owner/repo.git  (not common in JSON, but handled)
          - https://owner.github.io/repo
        """
        url = url.strip()

        # Try main GitHub URL pattern
        match = GITHUB_URL_PATTERN.search(url)
        if match:
            return {"owner": match.group(1), "repo": match.group(2).rstrip(".git")}

        # Try github.io pattern
        match = GITHUB_IO_PATTERN.search(url)
        if match:
            return {"owner": match.group(1), "repo": match.group(2).rstrip(".git")}

        # Try git@ SSH format
        ssh_match = re.search(r"git@github\.com:([a-zA-Z0-9._-]+)/([a-zA-Z0-9._-]+?)(?:\.git)?$", url)
        if ssh_match:
            return {"owner": ssh_match.group(1), "repo": ssh_match.group(2).rstrip(".git")}

        return None

    @staticmethod
    def _canonical_url(owner: str, repo: str) -> str:
        """Build canonical GitHub URL."""
        return f"https://github.com/{owner}/{repo}"

    @staticmethod
    def parse_github_url(url: str) -> dict[str, str] | None:
        """Public parsing method for external use."""
        return RepoDetector._parse_github_url(url)
