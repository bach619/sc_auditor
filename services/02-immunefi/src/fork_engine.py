"""ForkEngine — Fork detected GitHub repos under your account.

Workflow:
  1. RepoDetector menemukan repo di program
  2. ForkEngine cek fork index: sudah di-fork?
  3. Kalau belum → POST /repos/{owner}/{repo}/forks ke GitHub API
  4. Simpan hasil (fork_url, status, timestamp) di fork index

Membutuhkan GITHUB_TOKEN dengan scope "repo" atau "public_repo".
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from src.models import Program
from src.storage import EnhancedJSONStorage

log = structlog.get_logger()


@dataclass
class ForkResult:
    """Result of a single fork operation."""
    repo_key: str  # owner/repo
    status: str  # success | skipped | failed
    fork_url: str = ""
    error: str = ""
    timestamp: str = ""
    slug: str = ""

    def to_dict(self) -> dict:
        return {
            "repo_key": self.repo_key,
            "status": self.status,
            "fork_url": self.fork_url,
            "error": self.error[:200] if self.error else "",
            "timestamp": self.timestamp or datetime.now(timezone.utc).isoformat(),
            "slug": self.slug,
        }


class ForkEngine:
    """Fork detected repos to your GitHub account.

    Usage:
        engine = ForkEngine(storage)
        results = await engine.fork_all_unforked(programs)
        status = engine.get_fork_status("owner/repo")
    """

    GITHUB_API = "https://api.github.com"

    def __init__(
        self,
        storage: EnhancedJSONStorage,
        client: httpx.AsyncClient | None = None,
        target_org: str | None = None,
    ) -> None:
        self.storage = storage
        self._client = client
        self._token = os.getenv("GITHUB_TOKEN", "")
        self._target_org = target_org or os.getenv("GITHUB_FORK_ORG", "")

    def is_available(self) -> bool:
        """ForkEngine available hanya jika GITHUB_TOKEN tersedia."""
        return bool(self._token)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    # ── Fork Index ──────────────────────────────────────────

    def _load_fork_index(self) -> dict[str, Any]:
        """Load fork index from storage."""
        data = self.storage.get_index("forks")
        return data if isinstance(data, dict) else {}

    def _save_fork_index(self, index: dict) -> None:
        """Save fork index to storage."""
        try:
            # Store as a special index
            import json  # noqa: PLC0415
            path = self.storage.data_dir / "indexes" / "forks.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(index, indent=2))
        except Exception as e:
            log.warning("fork.index_save_error", error=str(e)[:100])

    # ── Detection ───────────────────────────────────────────

    def find_unforked_repos(
        self,
        programs: dict[str, Program],
    ) -> list[dict[str, Any]]:
        """Find all repos that haven't been forked yet.

        Returns list of {slug, program_name, repo_key, repo_url, owner, repo}.
        """
        fork_index = self._load_fork_index()
        unforked: list[dict[str, Any]] = []

        for slug, prog in programs.items():
            for repo in prog.repos:
                repo_key = f"{repo.owner}/{repo.repo}"
                if repo_key not in fork_index:
                    unforked.append({
                        "slug": slug,
                        "program_name": prog.name,
                        "repo_key": repo_key,
                        "repo_url": repo.url,
                        "owner": repo.owner,
                        "repo": repo.repo,
                    })

        return unforked

    def get_fork_stats(
        self,
        programs: dict[str, Program],
    ) -> dict[str, Any]:
        """Get fork stats: total, forked, unforked, failed."""
        fork_index = self._load_fork_index()
        total_repos = 0
        for prog in programs.values():
            total_repos += len(prog.repos)

        forked = sum(
            1 for v in fork_index.values()
            if isinstance(v, dict) and v.get("status") == "success"
        )
        failed = sum(
            1 for v in fork_index.values()
            if isinstance(v, dict) and v.get("status") == "failed"
        )
        pending = sum(
            1 for v in fork_index.values()
            if isinstance(v, dict) and v.get("status") == "pending"
        )

        return {
            "total_repos_detected": total_repos,
            "forked": forked,
            "failed": failed,
            "pending": pending,
            "unforked": total_repos - forked - failed - pending,
            "token_available": bool(self._token),
        }

    # ── Fork Operations ─────────────────────────────────────

    async def fork_repo(
        self,
        owner: str,
        repo: str,
        slug: str = "",
    ) -> ForkResult:
        """Fork a single repo via GitHub API.

        POST /repos/{owner}/{repo}/forks
        Optional: POST /repos/{owner}/{repo}/forks?organization={target_org}
        """
        repo_key = f"{owner}/{repo}"
        client = await self._get_client()

        # Check if already forked
        fork_index = self._load_fork_index()
        existing = fork_index.get(repo_key)
        if existing and isinstance(existing, dict) and existing.get("status") == "success":
            return ForkResult(
                repo_key=repo_key,
                status="skipped",
                fork_url=existing.get("fork_url", ""),
                slug=slug,
                timestamp=existing.get("timestamp", ""),
            )

        # Update fork index to pending
        now = datetime.now(timezone.utc).isoformat()
        fork_index[repo_key] = {
            "status": "pending",
            "timestamp": now,
            "slug": slug,
        }
        self._save_fork_index(fork_index)

        log.info("fork.repo.start", repo=repo_key)

        try:
            url = f"{self.GITHUB_API}/repos/{owner}/{repo}/forks"
            params = {}
            if self._target_org:
                params["organization"] = self._target_org

            resp = await client.post(
                url,
                headers=self._headers(),
                params=params,
                json={},
            )

            if resp.status_code == 202:
                data = resp.json()
                fork_url = data.get("html_url", "")
                log.info("fork.repo.success", repo=repo_key, fork_url=fork_url)

                result = ForkResult(
                    repo_key=repo_key,
                    status="success",
                    fork_url=fork_url,
                    slug=slug,
                    timestamp=now,
                )

            elif resp.status_code == 403:
                error_msg = "rate_limited_or_forbidden"
                log.warning("fork.repo.forbidden", repo=repo_key)
                result = ForkResult(
                    repo_key=repo_key,
                    status="failed",
                    error=error_msg,
                    slug=slug,
                    timestamp=now,
                )

            else:
                resp.raise_for_status()
                # Shouldn't reach here
                result = ForkResult(
                    repo_key=repo_key,
                    status="failed",
                    error=f"unexpected_status:{resp.status_code}",
                    slug=slug,
                    timestamp=now,
                )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                error_msg = "rate_limited_or_forbidden"
            elif e.response.status_code == 404:
                error_msg = "repo_not_found"
            else:
                error_msg = f"http_{e.response.status_code}"
            log.warning("fork.repo.error", repo=repo_key, error=error_msg)
            result = ForkResult(
                repo_key=repo_key,
                status="failed",
                error=error_msg,
                slug=slug,
                timestamp=now,
            )

        except Exception as e:
            log.warning("fork.repo.exception", repo=repo_key, error=str(e)[:100])
            result = ForkResult(
                repo_key=repo_key,
                status="failed",
                error=str(e)[:100],
                slug=slug,
                timestamp=now,
            )

        # Update fork index
        fork_index[repo_key] = result.to_dict()
        self._save_fork_index(fork_index)

        return result

    async def fork_all_unforked(
        self,
        programs: dict[str, Program],
        max_forks: int = 10,
    ) -> list[dict]:
        """Fork all unforked repos (up to max_forks per call)."""
        if not self.is_available():
            log.warning("fork.not_available", action="skipped")
            return [{
                "repo_key": "N/A",
                "status": "skipped",
                "error": "GITHUB_TOKEN not set",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }]

        unforked = self.find_unforked_repos(programs)
        if not unforked:
            log.info("fork.all_unforked.none_found")
            return []

        # Sort: prioritize programs with highest bounty
        unforked.sort(
            key=lambda x: programs.get(x["slug"]).max_bounty or 0
            if programs.get(x["slug"]) else 0,
            reverse=True,
        )

        results: list[dict] = []
        for item in unforked[:max_forks]:
            result = await self.fork_repo(
                owner=item["owner"],
                repo=item["repo"],
                slug=item["slug"],
            )
            results.append(result.to_dict())

        return results

    async def fork_for_program(
        self,
        slug: str,
        program: Program,
    ) -> list[dict]:
        """Fork all unforked repos for a specific program."""
        if not self.is_available():
            return [{
                "repo_key": "N/A",
                "status": "skipped",
                "error": "GITHUB_TOKEN not set",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }]

        results: list[dict] = []
        for repo in program.repos:
            repo_key = f"{repo.owner}/{repo.repo}"
            fork_index = self._load_fork_index()
            if repo_key not in fork_index:
                result = await self.fork_repo(
                    owner=repo.owner,
                    repo=repo.repo,
                    slug=slug,
                )
                results.append(result.to_dict())

        return results

    # ── Status ──────────────────────────────────────────────

    def get_fork_status(self, repo_key: str) -> dict | None:
        """Get fork status for a specific repo."""
        fork_index = self._load_fork_index()
        entry = fork_index.get(repo_key)
        if isinstance(entry, dict):
            return entry
        return None

    def get_all_forks(self) -> dict[str, Any]:
        """Get complete fork index."""
        return self._load_fork_index()

    async def check_fork_completion(self, repo_key: str) -> dict | None:
        """Check if a forking repo is ready.

        GitHub forks are created asynchronously (202 Accepted).
        This polls the repo API to confirm the fork exists.
        """
        fork_index = self._load_fork_index()
        entry = fork_index.get(repo_key)
        if not entry or not isinstance(entry, dict):
            return None

        if entry.get("status") != "success":
            return entry

        fork_url = entry.get("fork_url", "")
        if not fork_url:
            return entry

        # Parse fork owner/name from URL
        # https://github.com/{owner}/{repo}
        parts = fork_url.rstrip("/").split("/")
        if len(parts) < 2:
            return entry

        fork_owner = parts[-2]
        fork_repo = parts[-1]

        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.GITHUB_API}/repos/{fork_owner}/{fork_repo}",
                headers=self._headers(),
            )
            if resp.status_code == 200:
                data = resp.json()
                entry["ready"] = True
                entry["fork_stars"] = data.get("stargazers_count", 0)
                entry["fork_default_branch"] = data.get("default_branch", "main")
                fork_index[repo_key] = entry
                self._save_fork_index(fork_index)
            elif resp.status_code == 404:
                entry["ready"] = False  # still cloning
                fork_index[repo_key] = entry
                self._save_fork_index(fork_index)
        except Exception:
            pass

        return entry

    # ── Fork L4: Management ─────────────────────────────────

    def _parse_fork_owner_repo(self, repo_key: str) -> tuple[str, str] | None:
        """Parse owner/repo dari repo_key atau fork_url di index."""
        fork_index = self._load_fork_index()
        entry = fork_index.get(repo_key)
        if not entry or not isinstance(entry, dict):
            return None

        fork_url = entry.get("fork_url", "")
        if fork_url:
            parts = fork_url.rstrip("/").split("/")
            if len(parts) >= 2:
                return parts[-2], parts[-1]

        # Fallback: guess from repo_key
        parts = repo_key.split("/")
        if len(parts) == 2:
            return parts[0], parts[1]
        return None

    async def delete_fork(self, slug: str) -> dict[str, Any]:
        """Hapus fork repo via GitHub API (DELETE).

        Cari fork entry dari slug, lalu DELETE /repos/{owner}/{repo}.
        """
        if not self.is_available():
            return {"status": "error", "error": "GITHUB_TOKEN not set"}

        fork_index = self._load_fork_index()
        # Find all entries for this slug
        deleted: list[dict] = []
        for repo_key, entry in fork_index.items():
            if not isinstance(entry, dict):
                continue
            if entry.get("slug") != slug:
                continue
            if entry.get("status") != "success":
                continue

            parsed = self._parse_fork_owner_repo(repo_key)
            if not parsed:
                continue
            fork_owner, fork_repo = parsed

            client = await self._get_client()
            try:
                resp = await client.delete(
                    f"{self.GITHUB_API}/repos/{fork_owner}/{fork_repo}",
                    headers=self._headers(),
                )
                if resp.status_code in (204, 404):
                    fork_index.pop(repo_key, None)
                    deleted.append({
                        "repo_key": repo_key,
                        "status": "deleted",
                    })
                    log.info("fork.deleted", repo=repo_key)
                else:
                    deleted.append({
                        "repo_key": repo_key,
                        "status": "failed",
                        "error": f"http_{resp.status_code}",
                    })
            except Exception as e:
                deleted.append({
                    "repo_key": repo_key,
                    "status": "error",
                    "error": str(e)[:100],
                })

        self._save_fork_index(fork_index)
        return {
            "slug": slug,
            "total_deleted": len(deleted),
            "forks": deleted,
        }

    async def sync_fork_upstream(self, slug: str) -> dict[str, Any]:
        """Sync fork dengan upstream via GitHub API.

        POST /repos/{fork_owner}/{fork_repo}/merge-upstream
        """
        if not self.is_available():
            return {"status": "error", "error": "GITHUB_TOKEN not set"}

        fork_index = self._load_fork_index()
        results: list[dict] = []

        for repo_key, entry in fork_index.items():
            if not isinstance(entry, dict):
                continue
            if entry.get("slug") != slug:
                continue
            if entry.get("status") != "success":
                continue

            parsed = self._parse_fork_owner_repo(repo_key)
            if not parsed:
                continue
            fork_owner, fork_repo = parsed

            client = await self._get_client()
            try:
                resp = await client.post(
                    f"{self.GITHUB_API}/repos/{fork_owner}/{fork_repo}/merge-upstream",
                    headers=self._headers(),
                    json={"branch": "main"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results.append({
                        "repo_key": repo_key,
                        "status": "synced",
                        "base_branch": data.get("base_branch", "main"),
                        "merge_commit": data.get("merge_commit_sha", ""),
                    })
                    log.info("fork.synced", repo=repo_key)
                elif resp.status_code == 409:
                    results.append({
                        "repo_key": repo_key,
                        "status": "up_to_date",
                        "message": "Already up to date or conflict",
                    })
                else:
                    results.append({
                        "repo_key": repo_key,
                        "status": "failed",
                        "error": f"http_{resp.status_code}",
                    })
            except Exception as e:
                results.append({
                    "repo_key": repo_key,
                    "status": "error",
                    "error": str(e)[:100],
                })

        return {
            "slug": slug,
            "total_synced": len(results),
            "results": results,
        }

    async def list_prs(self, slug: str) -> list[dict[str, Any]]:
        """List open PRs dari forked repo ke upstream.

        GET /repos/{fork_owner}/{fork_repo}/pulls?state=open&head={fork_owner}:{branch}
        """
        if not self.is_available():
            return [{"error": "GITHUB_TOKEN not set"}]

        fork_index = self._load_fork_index()
        all_prs: list[dict] = []

        for repo_key, entry in fork_index.items():
            if not isinstance(entry, dict):
                continue
            if entry.get("slug") != slug:
                continue
            if entry.get("status") != "success":
                continue

            parsed = self._parse_fork_owner_repo(repo_key)
            if not parsed:
                continue
            fork_owner, fork_repo = parsed

            client = await self._get_client()
            try:
                resp = await client.get(
                    f"{self.GITHUB_API}/repos/{fork_owner}/{fork_repo}/pulls",
                    headers=self._headers(),
                    params={"state": "open", "head": f"{fork_owner}:main"},
                )
                if resp.status_code == 200:
                    prs = resp.json()
                    for pr in prs:
                        all_prs.append({
                            "repo_key": repo_key,
                            "pr_number": pr.get("number"),
                            "title": pr.get("title"),
                            "state": pr.get("state"),
                            "created_at": pr.get("created_at"),
                            "html_url": pr.get("html_url"),
                        })
            except Exception:
                pass

        return all_prs

    async def create_pr(
        self,
        slug: str,
        head_branch: str,
        title: str = "Exploit PoC",
        body: str = "",
    ) -> dict[str, Any]:
        """Create PR dari forked repo ke upstream.

        POST /repos/{original_owner}/{original_repo}/pulls
        head = {fork_owner}:{head_branch}
        """
        if not self.is_available():
            return {"status": "error", "error": "GITHUB_TOKEN not set"}

        fork_index = self._load_fork_index()
        results: list[dict] = []

        for repo_key, entry in fork_index.items():
            if not isinstance(entry, dict):
                continue
            if entry.get("slug") != slug:
                continue
            if entry.get("status") != "success":
                continue

            # Original repo (upstream)
            parts = repo_key.split("/")
            if len(parts) != 2:
                continue
            orig_owner, orig_repo = parts

            # Fork owner (current user/org)
            parsed = self._parse_fork_owner_repo(repo_key)
            if not parsed:
                continue
            fork_owner = parsed[0]

            client = await self._get_client()
            try:
                resp = await client.post(
                    f"{self.GITHUB_API}/repos/{orig_owner}/{orig_repo}/pulls",
                    headers=self._headers(),
                    json={
                        "title": title,
                        "body": body,
                        "head": f"{fork_owner}:{head_branch}",
                        "base": "main",
                    },
                )
                if resp.status_code == 201:
                    pr_data = resp.json()
                    results.append({
                        "repo_key": repo_key,
                        "status": "created",
                        "pr_number": pr_data.get("number"),
                        "pr_url": pr_data.get("html_url", ""),
                    })
                    log.info("fork.pr_created", repo=repo_key, pr_url=pr_data.get("html_url"))
                elif resp.status_code == 422:
                    results.append({
                        "repo_key": repo_key,
                        "status": "no_changes",
                        "error": "No changes between branches",
                    })
                else:
                    results.append({
                        "repo_key": repo_key,
                        "status": "failed",
                        "error": f"http_{resp.status_code}",
                    })
            except Exception as e:
                results.append({
                    "repo_key": repo_key,
                    "status": "error",
                    "error": str(e)[:100],
                })

        return {
            "slug": slug,
            "title": title,
            "total_prs_created": len(results),
            "results": results,
        }

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
