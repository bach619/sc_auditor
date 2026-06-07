"""Update Manager for Vyper Upkeep Service.

Checks for new versions on GitHub/PyPI, performs self-update via
``git pull`` and ``docker compose``, and manages version tracking.
"""

from __future__ import annotations

import asyncio
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from src.models import UpdateCheckResult, UpdateResult

log = structlog.get_logger()

# ── Constants ───────────────────────────────────────────────

GITHUB_API_URL = "https://api.github.com/repos/{repo}/releases/latest"
PYPI_JSON_URL = "https://pypi.org/pypi/{package}/json"
DEFAULT_REPO = "vyper/vyper"
DEFAULT_PACKAGE = "vyper-bug-hunter"

UPDATE_DIR = Path("/data/upkeep/update")
VERSION_FILE = UPDATE_DIR / "VERSION"
CHANGELOG_FILE = UPDATE_DIR / "changelog.md"
LAST_CHECK_FILE = UPDATE_DIR / "last_check.json"


# ── UpdateManager ────────────────────────────────────────────


class UpdateManager:
    """Manages Vyper self-update lifecycle.

    Responsibilities:
        - Check remote (GitHub / PyPI) for newer versions.
        - Perform self-update via git + docker compose.
        - Track current / previous version state.
        - Maintain changelog history.
    """

    def __init__(
        self,
        repo: str = DEFAULT_REPO,
        package: str = DEFAULT_PACKAGE,
        project_dir: Path | None = None,
    ) -> None:
        self.repo = repo
        self.package = package
        self.project_dir = project_dir or Path("/app")

        try:
            UPDATE_DIR.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            pass

        # Initialise VERSION file if missing
        if not VERSION_FILE.exists():
            try:
                VERSION_FILE.write_text("0.0.0\n", encoding="utf-8")
            except PermissionError:
                pass

        # Initialise changelog if missing
        if not CHANGELOG_FILE.exists():
            try:
                CHANGELOG_FILE.write_text("# Vyper Changelog\n\n", encoding="utf-8")
            except PermissionError:
                pass

    # ── Version Management ───────────────────────────────────

    def get_current_version(self) -> str:
        """Return the locally recorded version string."""
        try:
            return VERSION_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            return "0.0.0"

    def set_current_version(self, version: str) -> None:
        """Write version string to the VERSION file."""
        VERSION_FILE.write_text(f"{version.strip()}\n", encoding="utf-8")

    def append_changelog(self, version: str, notes: str) -> None:
        """Append a version entry to the changelog."""
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        entry = f"## {version} — {timestamp}\n\n{notes.strip()}\n\n"
        with open(CHANGELOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry)

    # ── Remote Check ─────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def _fetch_github_release(self) -> dict[str, Any] | None:
        """Fetch the latest release metadata from GitHub."""
        url = GITHUB_API_URL.format(repo=self.repo)
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "vyper-upkeep/1.0",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def _fetch_pypi_version(self) -> dict[str, Any] | None:
        """Fetch the latest version from PyPI JSON API."""
        url = PYPI_JSON_URL.format(package=self.package)
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()

    async def check_github_version(
        self, repo: str | None = None
    ) -> UpdateCheckResult:
        """Check for available updates via GitHub releases.

        Args:
            repo: GitHub repository in ``owner/repo`` format.
                  Defaults to ``vyper/vyper``.

        Returns:
            UpdateCheckResult with version comparison.
        """
        repo = repo or self.repo
        current = self.get_current_version()

        try:
            data = await self._fetch_github_release()
            if not data:
                return UpdateCheckResult(
                    current_version=current,
                    update_available=False,
                    changelog_summary="Could not reach GitHub API.",
                )

            latest = data.get("tag_name", "").lstrip("v")
            body = data.get("body", "")
            # First 500 chars of release notes
            changelog_summary = body[:500].strip() if body else ""
            update_available = self._is_newer(latest, current)

            # Persist last check
            _write_last_check(
                source="github",
                current_version=current,
                latest_version=latest,
                update_available=update_available,
            )

            return UpdateCheckResult(
                current_version=current,
                latest_version=latest,
                update_available=update_available,
                changelog_summary=changelog_summary,
            )

        except httpx.HTTPError as exc:
            log.warning("update.github_check_failed", error=str(exc))
            return UpdateCheckResult(
                current_version=current,
                update_available=False,
                changelog_summary=f"GitHub API error: {exc}",
            )

    async def check_pypi_version(self) -> UpdateCheckResult:
        """Check for available updates via PyPI JSON API."""
        current = self.get_current_version()

        try:
            data = await self._fetch_pypi_version()
            if not data:
                return UpdateCheckResult(
                    current_version=current,
                    update_available=False,
                    changelog_summary="Could not reach PyPI.",
                )

            info = data.get("info", {})
            latest = info.get("version", "")
            summary = info.get("summary", "")
            update_available = self._is_newer(latest, current)

            _write_last_check(
                source="pypi",
                current_version=current,
                latest_version=latest,
                update_available=update_available,
            )

            return UpdateCheckResult(
                current_version=current,
                latest_version=latest,
                update_available=update_available,
                changelog_summary=summary,
            )

        except httpx.HTTPError as exc:
            log.warning("update.pypi_check_failed", error=str(exc))
            return UpdateCheckResult(
                current_version=current,
                update_available=False,
                changelog_summary=f"PyPI API error: {exc}",
            )

    # ── Perform Update ───────────────────────────────────────

    async def perform_update(self) -> UpdateResult:
        """Execute self-update: git pull + docker compose rebuild.

        Steps:
            1. Record pre-update version.
            2. ``git pull`` to fetch latest code.
            3. ``docker compose build`` / ``docker compose pull``.
            4. ``docker compose up -d`` to restart services.
            5. Update VERSION file.

        Returns:
            UpdateResult with success/failure details.
        """
        previous = self.get_current_version()
        output_lines: list[str] = []

        try:
            # ── Step 1: git pull ─────────────────────
            log.info("update.starting", previous_version=previous)

            git_result = await _run_command(
                ["git", "pull", "--ff-only"],
                cwd=self.project_dir,
                timeout=120,
            )
            output_lines.append(f"--- git pull ---\n{git_result}")

            if "Already up to date" in git_result:
                log.info("update.already_current")
                return UpdateResult(
                    success=True,
                    previous_version=previous,
                    current_version=previous,
                    output="Already up to date.",
                )

            # ── Step 2: docker compose build/pull ────
            pull_result = await _run_command(
                ["docker", "compose", "pull"],
                cwd=self.project_dir,
                timeout=300,
            )
            output_lines.append(f"--- docker compose pull ---\n{pull_result}")

            # ── Step 3: docker compose up -d ─────────
            up_result = await _run_command(
                ["docker", "compose", "up", "-d", "--remove-orphans"],
                cwd=self.project_dir,
                timeout=120,
            )
            output_lines.append(f"--- docker compose up ---\n{up_result}")

            # ── Step 4: Determine new version ────────
            # Try to read from git tag first
            new_version = await self._detect_post_update_version()
            self.set_current_version(new_version)
            self.append_changelog(
                new_version,
                f"Updated via `docker compose pull && docker compose up -d`.\n\n"
                f"```\n{up_result[:1000]}\n```",
            )

            log.info(
                "update.complete",
                previous=previous,
                current=new_version,
            )

            return UpdateResult(
                success=True,
                previous_version=previous,
                current_version=new_version,
                output="\n".join(output_lines),
            )

        except (subprocess.SubprocessError, OSError, RuntimeError) as exc:
            log.exception("update.failed", error=str(exc))
            return UpdateResult(
                success=False,
                previous_version=previous,
                current_version=self.get_current_version(),
                error=str(exc),
                output="\n".join(output_lines) if output_lines else "",
            )

    async def _detect_post_update_version(self) -> str:
        """Detect the version after an update.

        Tries, in order:
            1. Git tag (``git describe --tags``).
            2. VERSION file in the project root.
            3. Fallback to previous version + ``-post`` suffix.
        """
        try:
            tag = await _run_command(
                ["git", "describe", "--tags", "--abbrev=0"],
                cwd=self.project_dir,
                timeout=15,
            )
            if tag:
                return tag.strip().lstrip("v")
        except (subprocess.SubprocessError, OSError):
            pass

        # Check project-level VERSION file
        project_version_file = self.project_dir / "VERSION"
        if project_version_file.exists():
            try:
                return project_version_file.read_text(encoding="utf-8").strip()
            except OSError:
                pass

        return f"{self.get_current_version()}-post"

    # ── Helpers ──────────────────────────────────────────────

    @staticmethod
    def _is_newer(latest: str, current: str) -> bool:
        """Compare two semver strings; return True if latest > current."""
        try:
            latest_parts = [int(x) for x in latest.split(".")[:3]]
            current_parts = [int(x) for x in current.split(".")[:3]]
            # Pad with zeros
            while len(latest_parts) < 3:
                latest_parts.append(0)
            while len(current_parts) < 3:
                current_parts.append(0)
            return latest_parts > current_parts
        except (ValueError, TypeError):
            # If semver parse fails, do string comparison
            return latest > current


# ── Factory ──────────────────────────────────────────────────


def create_update_manager(
    repo: str = DEFAULT_REPO,
    project_dir: str | None = None,
) -> UpdateManager:
    """Create an UpdateManager instance."""
    return UpdateManager(
        repo=repo,
        project_dir=Path(project_dir) if project_dir else None,
    )


# ── Internal Helpers ─────────────────────────────────────────


async def _run_command(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int = 60,
) -> str:
    """Run a shell command asynchronously and return its stdout+stderr."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return stdout.decode("utf-8", errors="replace").strip() if stdout else ""
    except TimeoutError:
        proc.kill()
        raise RuntimeError(f"Command timed out after {timeout}s: {' '.join(cmd)}")


def _write_last_check(
    source: str,
    current_version: str,
    latest_version: str,
    update_available: bool,
) -> None:
    """Write the last update check metadata to disk."""
    import json

    data = {
        "source": source,
        "current_version": current_version,
        "latest_version": latest_version,
        "update_available": update_available,
        "checked_at": datetime.now(UTC).isoformat(),
    }
    try:
        LAST_CHECK_FILE.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        log.warning("update.last_check_write_failed", error=str(exc))
