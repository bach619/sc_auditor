"""Slither static analysis runner (standalone service).

Executes `slither` on a directory of Solidity source files and parses
the JSON output into structured ``Finding`` objects.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

import structlog

from vyper_lib.models import Finding, ToolResult

log = structlog.get_logger()

# Detectors that are too noisy for routine scans; disabled by default.
NOISY_DETECTORS: frozenset[str] = frozenset({
    "naming-convention",
    "pragma",
    "solc-version",
    "constable-states",
    "immutable-states",
    "too-many-digits",
    "conformance-to-solidity-naming-conventions",
})

# Severity mapping from Slither's checkseverity strings to our standard.
SEVERITY_MAP: dict[str, str] = {
    "high": "high",
    "medium": "medium",
    "low": "low",
    "informational": "informational",
    "optimization": "informational",
}


class SlitherRunner:
    """Run Slither static analysis on a directory of .sol files.

    Args:
        slither_bin: Path to the ``slither`` executable (default: ``slither``).
        working_dir: Base working directory for temporary files.
    """

    def __init__(
        self,
        slither_bin: str = "slither",
        working_dir: str | Path = "/data/scanner",
    ) -> None:
        self._bin = slither_bin
        self._working_dir = Path(working_dir)
        self._working_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        source_dir: str | Path,
        config: dict[str, Any] | None = None,
        timeout: int = 600,
    ) -> ToolResult:
        """Run Slither on the given source directory.

        Args:
            source_dir: Directory containing ``.sol`` files.
            config: Optional Slither config dict (see ``SlitherConfigBuilder``).
            timeout: Maximum execution time in seconds.

        Returns:
            A ``ToolResult`` with parsed findings.
        """
        tool_name = "slither"
        start = time.monotonic()
        source_path = Path(source_dir)

        if not source_path.is_dir():
            return ToolResult(
                tool=tool_name,
                success=False,
                error=f"Source directory not found: {source_dir}",
                duration_seconds=time.monotonic() - start,
            )

        sol_files = sorted(source_path.rglob("*.sol"))
        if not sol_files:
            return ToolResult(
                tool=tool_name,
                success=False,
                error=f"No .sol files found in {source_dir}",
                duration_seconds=time.monotonic() - start,
            )

        cmd = [
            self._bin,
            *[str(f) for f in sol_files],
            "--json",
            "-",
            "--solc-ast",
        ]

        if config:
            config_path = source_path / ".slither.config.json"
            try:
                config_path.write_text(json.dumps(config))
                log.debug("slither.config_written", path=str(config_path))
            except OSError as exc:
                log.warning("slither.config_write_failed", error=str(exc))

        log.info("slither.run.start", source_dir=source_dir, timeout=timeout)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            log.warning("slither.timeout", source_dir=source_dir, timeout=timeout)
            return ToolResult(
                tool=tool_name, success=False,
                error=f"Slither timed out after {timeout}s",
                duration_seconds=time.monotonic() - start,
            )
        except FileNotFoundError:
            log.error("slither.not_found", binary=self._bin)
            return ToolResult(
                tool=tool_name, success=False,
                error=f"Slither binary not found: {self._bin}",
                duration_seconds=time.monotonic() - start,
            )
        except OSError as exc:
            log.error("slither.os_error", error=str(exc))
            return ToolResult(
                tool=tool_name, success=False,
                error=f"OS error running Slither: {exc}",
                duration_seconds=time.monotonic() - start,
            )

        elapsed = time.monotonic() - start

        if result.returncode != 0 and not result.stdout.strip():
            log.warning("slither.no_output", stderr=result.stderr[:500])
            return ToolResult(
                tool=tool_name, success=False,
                error=result.stderr.strip() or "Slither produced no output",
                raw_output=result.stdout,
                duration_seconds=elapsed,
            )

        findings = self._parse_output(result.stdout)

        log.info(
            "slither.run.complete",
            findings=len(findings), duration=round(elapsed, 2),
            return_code=result.returncode,
        )

        return ToolResult(
            tool=tool_name, success=True,
            findings=findings, raw_output=result.stdout,
            duration_seconds=elapsed,
        )

    def _parse_output(self, raw: str) -> list[Finding]:
        """Parse Slither JSON output into a list of ``Finding``."""
        if not raw.strip():
            return []

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            log.warning("slither.json_parse_error", error=str(exc))
            return []

        results = data.get("results", {})
        if not results:
            return []

        findings: list[Finding] = []
        detectors = results.get("detectors", [])

        for det in detectors:
            severity = SEVERITY_MAP.get(
                det.get("impact", "").lower(), "informational",
            )
            elements = det.get("elements", [])
            first_elem = elements[0] if elements else {}
            src_info = self._parse_source_mapping(first_elem.get("source_mapping", {}))

            finding = Finding(
                tool="slither",
                severity=severity,
                title=det.get("check", "Unknown"),
                description=det.get("description", ""),
                contract=src_info.get("contract"),
                line=src_info.get("line"),
                line_end=src_info.get("line_end"),
                recommendation=self._build_recommendation(det),
                swc_id=det.get("swc_id") or self._extract_swc(det),
            )
            findings.append(finding)

        return findings

    @staticmethod
    def _parse_source_mapping(sm: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if not sm:
            return result
        filename = sm.get("filename", "")
        if filename:
            result["contract"] = filename
        lines = sm.get("lines")
        if lines and isinstance(lines, list) and len(lines) > 0:
            result["line"] = lines[0]
            result["line_end"] = lines[-1] if len(lines) > 1 else lines[0]
        return result

    @staticmethod
    def _build_recommendation(det: dict[str, Any]) -> str | None:
        extra = det.get("extra", {})
        if isinstance(extra, dict):
            rec = extra.get("recommendation") or extra.get("fix")
            if rec:
                return str(rec)
        swc_id = det.get("swc_id")
        if swc_id:
            return f"See SWC-{swc_id} for more details."
        return None

    @staticmethod
    def _extract_swc(det: dict[str, Any]) -> str | None:
        extra = det.get("extra", {})
        if isinstance(extra, dict):
            swc = extra.get("swc_id")
            if swc:
                return str(swc)
        refs = det.get("references", [])
        for ref in refs:
            if isinstance(ref, str) and "SWC-" in ref:
                return ref
        return None


def create_slither_runner(
    working_dir: str | Path = "/data/scanner",
) -> SlitherRunner:
    """Create a configured ``SlitherRunner`` instance."""
    return SlitherRunner(working_dir=working_dir)
