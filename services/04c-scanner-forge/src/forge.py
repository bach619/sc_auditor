"""Foundry Forge build runner (standalone service).

Executes ``forge build`` to verify that Solidity source code compiles
successfully.
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

import structlog

from vyper_lib.models import ForgeResult
from vyper_lib.solc_manager import SolcManager

log = structlog.get_logger()


class ForgeRunner:
    """Run Foundry Forge to compile and verify Solidity source code.

    Args:
        forge_bin: Path to the ``forge`` executable (default: ``forge``).
        solc_manager: Optional ``SolcManager`` instance.
        working_dir: Base working directory for temporary files.
    """

    def __init__(
        self,
        forge_bin: str = "forge",
        solc_manager: SolcManager | None = None,
        working_dir: str | Path = "/data/scanner",
    ) -> None:
        self._bin = forge_bin
        self._solc_mgr = solc_manager or SolcManager()
        self._working_dir = Path(working_dir)
        self._working_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        source_dir: str | Path,
        compiler_version: str | None = None,
        timeout: int = 300,
        extra_args: list[str] | None = None,
    ) -> ForgeResult:
        """Run ``forge build`` on the given source directory.

        Args:
            source_dir: Directory containing a Foundry project.
            compiler_version: Solidity compiler version to use.
            timeout: Maximum build time in seconds.
            extra_args: Additional CLI arguments passed to ``forge build``.

        Returns:
            A ``ForgeResult`` with compilation status.
        """
        start = time.monotonic()
        source_path = Path(source_dir)

        if not source_path.is_dir():
            return ForgeResult(
                success=False,
                errors=[f"Source directory not found: {source_dir}"],
            )

        # Ensure compiler version
        resolved_version = compiler_version or self._detect_pragma(source_path)
        if resolved_version:
            try:
                self._solc_mgr.ensure_version(resolved_version)
                self._solc_mgr.use_version(resolved_version)
                log.info("forge.solc_version_set", version=resolved_version)
            except RuntimeError as exc:
                log.warning("forge.solc_version_failed", error=str(exc))

        # Build command
        cmd = [self._bin, "build", "--json"]
        if extra_args:
            cmd.extend(extra_args)

        out_dir = self._working_dir / f"forge_out_{int(start)}"
        cmd.extend(["--out", str(out_dir)])

        log.info("forge.run.start", source_dir=source_dir, compiler=resolved_version, timeout=timeout)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, cwd=str(source_path),
            )
        except subprocess.TimeoutExpired:
            log.warning("forge.timeout", source_dir=source_dir, timeout=timeout)
            return ForgeResult(success=False, errors=[f"Forge build timed out after {timeout}s"])
        except FileNotFoundError:
            log.error("forge.not_found", binary=self._bin)
            return ForgeResult(success=False, errors=[f"Forge binary not found: {self._bin}"])
        except OSError as exc:
            log.error("forge.os_error", error=str(exc))
            return ForgeResult(success=False, errors=[f"OS error running Forge: {exc}"])

        # Clean up build artifacts
        if out_dir.exists():
            try:
                for p in out_dir.rglob("*"):
                    if p.is_file():
                        p.unlink()
                out_dir.rmdir()
            except OSError:
                log.warning("forge.cleanup_failed", path=str(out_dir))

        forge_result = self._parse_output(result.stdout, result.stderr, result.returncode)

        detected_version = self._detect_version_from_output(result.stdout, result.stderr)
        if detected_version:
            forge_result.compiler_version = detected_version

        elapsed = time.monotonic() - start
        log.info(
            "forge.run.complete",
            success=forge_result.success,
            errors=len(forge_result.errors),
            warnings=len(forge_result.warnings),
            compiler=forge_result.compiler_version,
            duration=round(elapsed, 2),
        )

        return forge_result

    @staticmethod
    def _parse_output(stdout: str, stderr: str, return_code: int) -> ForgeResult:
        errors: list[str] = []
        warnings: list[str] = []

        for line in stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                import json
                entry = json.loads(stripped)
                if not entry.get("success", True):
                    msg = entry.get("message", "") or entry.get("reason", "")
                    if msg:
                        errors.append(msg)
            except (json.JSONDecodeError, ValueError):
                pass

        for line in stderr.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if "Error" in stripped or "error" in stripped.lower():
                errors.append(stripped)
            elif "Warning" in stripped or "warning" in stripped.lower():
                warnings.append(stripped)

        if not errors and stderr.strip() and return_code != 0:
            errors.append(stderr.strip()[:1000])

        return ForgeResult(
            success=return_code == 0 or not errors,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def _detect_pragma(source_dir: Path) -> str | None:
        sol_files = list(source_dir.rglob("*.sol"))
        versions: set[str] = set()
        for sol_file in sol_files:
            try:
                content = sol_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            pragma_match = re.search(
                r"pragma\s+solidity\s+[\^~>=]*\s*(\d+\.\d+\.\d+)", content,
            )
            if pragma_match:
                versions.add(pragma_match.group(1))
        if not versions:
            return None

        def _sort_key(v: str) -> tuple[int, ...]:
            return tuple(int(x) for x in v.split("."))
        return max(versions, key=_sort_key)

    @staticmethod
    def _detect_version_from_output(stdout: str, stderr: str) -> str | None:
        combined = stdout + "\n" + stderr
        match = re.search(r"(?:Solidity|solc)\s*:\s*v?(\d+\.\d+\.\d+)", combined, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r'"compiler_version"\s*:\s*"(\d+\.\d+\.\d+)"', combined)
        if match:
            return match.group(1)
        return None


def create_forge_runner(
    working_dir: str | Path = "/data/scanner",
) -> ForgeRunner:
    return ForgeRunner(working_dir=working_dir)
