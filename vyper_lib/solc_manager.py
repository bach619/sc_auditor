"""Solidity compiler version manager.

Manages installation and selection of Solidity compiler versions via
``solc-select``. Caches binaries in ``/data/scanner/solc/{version}/``.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger()

# Default cache directory for solc binaries.
DEFAULT_CACHE_DIR = Path("/data/scanner/solc")


class SolcManager:
    """Manage Solidity compiler versions via ``solc-select``.

    Args:
        cache_dir: Directory where solc binaries are cached.
        solc_select_bin: Path to the ``solc-select`` executable.
        install_if_missing: Automatically install missing versions.
    """

    def __init__(
        self,
        cache_dir: str | Path = DEFAULT_CACHE_DIR,
        solc_select_bin: str = "solc-select",
        install_if_missing: bool = True,
    ) -> None:
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._solc_select_bin = solc_select_bin
        self._install_if_missing = install_if_missing

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ensure_version(self, version: str) -> bool:
        """Ensure a specific Solidity version is installed and activated.

        If the version is not installed and ``install_if_missing`` is
        ``True``, it will be installed automatically. After installation
        (or if already installed), the version is activated via
        ``solc-select use`` so that ``solc`` points to the requested
        version.

        Args:
            version: Solidity version string (e.g. ``"0.8.20"``).

        Returns:
            ``True`` if the version is available, ``False`` otherwise.

        Raises:
            RuntimeError: If installation or activation fails.
        """
        installed = self.list_versions()

        if version in installed:
            log.debug("solc.version_already_installed", version=version)
        else:
            if not self._install_if_missing:
                log.warning("solc.version_not_installed", version=version)
                return False

            log.info("solc.installing_version", version=version)
            success = self._install_version(version)
            if not success:
                raise RuntimeError(
                    f"Failed to install solc version {version}"
                )

        # Activate the version so solc binary points to the right one
        self.use_version(version)

        return True

    def use_version(self, version: str) -> bool:
        """Activate a specific Solidity version via ``solc-select use``.

        Args:
            version: Solidity version string (e.g. ``"0.8.20"``).

        Returns:
            ``True`` if the version was activated successfully.

        Raises:
            RuntimeError: If activation fails.
        """
        try:
            result = subprocess.run(
                [self._solc_select_bin, "use", version],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"solc-select use {version} failed: {result.stderr.strip()}"
                )
            log.info("solc.version_activated", version=version)
            return True
        except FileNotFoundError:
            log.error("solc_select.not_found", binary=self._solc_select_bin)
            raise RuntimeError(
                f"solc-select binary not found: {self._solc_select_bin}"
            )
        except subprocess.SubprocessError as exc:
            log.error("solc.use_failed", version=version, error=str(exc))
            raise RuntimeError(f"Failed to activate solc {version}: {exc}")

    def list_versions(self) -> list[str]:
        """List all currently installed Solidity versions.

        Returns:
            A sorted list of version strings (e.g. ``["0.8.20", "0.8.21"]``).
        """
        try:
            result = subprocess.run(
                [self._solc_select_bin, "versions"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                log.warning(
                    "solc_select.list_failed",
                    stderr=result.stderr.strip(),
                )
                return self._scan_cache_dir()

            versions = self._parse_version_list(result.stdout)
            if versions:
                return versions

        except FileNotFoundError:
            log.warning("solc_select.not_found", binary=self._solc_select_bin)

        # Fallback: scan cache directory
        return self._scan_cache_dir()

    def current_version(self) -> str | None:
        """Get the currently active Solidity version.

        Returns:
            Version string or ``None`` if no version is active.
        """
        try:
            result = subprocess.run(
                ["solc", "--version"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            match = re.search(r"(\d+\.\d+\.\d+)", result.stdout)
            if match:
                return match.group(1)
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
        return None

    def list_remote_versions(self) -> list[str]:
        """List all available Solidity versions from the remote index.

        Returns:
            A sorted list of version strings.
        """
        try:
            result = subprocess.run(
                [self._solc_select_bin, "versions", "--all"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                return self._parse_version_list(result.stdout)
        except (FileNotFoundError, subprocess.SubprocessError) as exc:
            log.warning("solc_select.list_all_failed", error=str(exc))

        return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    def _install_version(self, version: str) -> bool:
        """Install a Solidity version via ``solc-select install``.

        Uses tenacity for automatic retries on transient failures.
        """
        try:
            # solc-select install downloads the binary
            result = subprocess.run(
                [self._solc_select_bin, "install", version],
                capture_output=True,
                text=True,
                timeout=120,  # downloads can be slow
            )

            if result.returncode == 0:
                log.info("solc.install_success", version=version)
                return True

            # Check if the error is just "already installed"
            if "already installed" in result.stderr.lower():
                log.info("solc.already_installed", version=version)
                return True

            log.error(
                "solc.install_failed",
                version=version,
                stderr=result.stderr.strip()[:500],
            )
            return False

        except subprocess.TimeoutExpired:
            log.warning("solc.install_timeout", version=version)
            return False
        except subprocess.SubprocessError as exc:
            log.error("solc.install_error", version=version, error=str(exc))
            return False

    def _scan_cache_dir(self) -> list[str]:
        """Fallback: scan the cache directory for installed versions."""
        if not self._cache_dir.exists():
            return []

        versions: list[str] = []
        for entry in self._cache_dir.iterdir():
            if entry.is_dir() and re.match(r"^\d+\.\d+\.\d+$", entry.name):
                versions.append(entry.name)
            elif entry.is_file() and entry.name.startswith("solc-"):
                ver = entry.name.removeprefix("solc-")
                if re.match(r"^\d+\.\d+\.\d+$", ver):
                    versions.append(ver)

        return sorted(versions, key=lambda v: tuple(int(x) for x in v.split(".")))

    @staticmethod
    def _parse_version_list(output: str) -> list[str]:
        """Parse ``solc-select list`` output into version strings."""
        versions: list[str] = []
        for line in output.splitlines():
            stripped = line.strip()
            # Lines look like: "0.8.20" or "  0.8.20 (installed)"
            match = re.match(r"^[\s*]*(\d+\.\d+\.\d+)", stripped)
            if match:
                versions.append(match.group(1))
        return versions


# ------------------------------------------------------------------
# Convenience factory
# ------------------------------------------------------------------


def create_solc_manager(
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
) -> SolcManager:
    """Create a configured ``SolcManager`` instance."""
    return SolcManager(cache_dir=cache_dir)
