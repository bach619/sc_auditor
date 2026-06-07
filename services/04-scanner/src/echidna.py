"""Echidna fuzzing runner.

Executes ``echidna`` on a Solidity contract with property-based fuzzing.
Creates a test harness contract if none is provided and parses the corpus
and failure output into structured ``Finding`` objects.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import structlog

from src.models import Finding, ToolResult

log = structlog.get_logger()

# Default test harness template injected when no test contract exists.
HARNESS_TEMPLATE = '''// SPDX-License-Identifier: MIT
pragma solidity ^{compiler};

import "{target}";

contract EchidnaHarness is {contract_name} {{
    // ── Echidna properties ─────────────────────────────────
    // Echidna calls all functions that return bool and start with "echidna_" or
    // are explicitly named in the config. Add custom properties below.

    /// @notice Asserts that the contract never ends up in a locked state.
    function echidna_no_reverts() public view returns (bool) {{
        // Override this with actual invariant checks
        return true;
    }}
}}
'''


class EchidnaRunner:
    """Run Echidna fuzzing on a Solidity contract.

    Args:
        echidna_bin: Path to the ``echidna`` binary (default: ``echidna``).
        working_dir: Base working directory for temporary files.
        default_timeout: Default fuzzing timeout in seconds.
        test_limit: Number of test sequences per run.
        seq_len: Maximum length of each transaction sequence.
    """

    def __init__(
        self,
        echidna_bin: str = "echidna",
        working_dir: str | Path = "/data/scanner",
        default_timeout: int = 600,
        test_limit: int = 50000,
        seq_len: int = 100,
    ) -> None:
        self._bin = echidna_bin
        self._working_dir = Path(working_dir)
        self._working_dir.mkdir(parents=True, exist_ok=True)
        self._default_timeout = default_timeout
        self._test_limit = test_limit
        self._seq_len = seq_len

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        source_dir: str | Path,
        contract_name: str | None = None,
        config: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> ToolResult:
        """Run Echidna fuzzing on contracts in ``source_dir``.

        Args:
            source_dir: Directory containing ``.sol`` files.
            contract_name: Primary contract name for harness generation.
            config: Optional Echidna config dict (see Echidna docs).
            timeout: Maximum fuzzing time in seconds.

        Returns:
            A ``ToolResult`` with findings from failed assertions.
        """
        tool_name = "echidna"
        start = time.monotonic()
        effective_timeout = timeout or self._default_timeout
        source_path = Path(source_dir)

        if not source_path.is_dir():
            return ToolResult(
                tool=tool_name,
                success=False,
                error=f"Source directory not found: {source_dir}",
                duration_seconds=time.monotonic() - start,
            )

        # Locate the primary contract file
        contract_file, resolved_name = self._find_contract(
            source_path, contract_name
        )
        if not contract_file:
            return ToolResult(
                tool=tool_name,
                success=False,
                error=(
                    f"No Solidity contract found in {source_dir}"
                    + (f" matching {contract_name}" if contract_name else "")
                ),
                duration_seconds=time.monotonic() - start,
            )

        # Create test harness if the contract has no echidna_ properties
        harness = self._ensure_harness(
            source_path, contract_file, resolved_name, config
        )

        # Write Echidna config file
        echidna_config = self._build_config(
            resolved_name,
            harness,
            config,
        )
        config_path = source_path / "echidna.yaml"
        try:
            config_path.write_text(echidna_config)
        except OSError as exc:
            log.warning("echidna.config_write_failed", error=str(exc))

        # Build command
        target = str(harness if harness.exists() else contract_file)
        cmd = [
            self._bin,
            target,
            "--config",
            str(config_path),
            "--test-limit",
            str(self._test_limit),
            "--seq-len",
            str(self._seq_len),
            "--timeout",
            str(effective_timeout),
            "--solc-args",
            "--allow-paths .",
        ]

        log.info(
            "echidna.run.start",
            target=target,
            contract=resolved_name,
            timeout=effective_timeout,
            cwd=str(source_path),
        )

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=effective_timeout + 30,
                cwd=str(source_path),
            )
        except subprocess.TimeoutExpired:
            log.warning("echidna.timeout", timeout=effective_timeout)
            return ToolResult(
                tool=tool_name,
                success=False,
                error=f"Echidna timed out after {effective_timeout}s",
                duration_seconds=time.monotonic() - start,
            )
        except FileNotFoundError:
            log.error("echidna.not_found", binary=self._bin)
            return ToolResult(
                tool=tool_name,
                success=False,
                error=f"Echidna binary not found: {self._bin}",
                duration_seconds=time.monotonic() - start,
            )
        except OSError as exc:
            log.error("echidna.os_error", error=str(exc))
            return ToolResult(
                tool=tool_name,
                success=False,
                error=f"OS error running Echidna: {exc}",
                duration_seconds=time.monotonic() - start,
            )

        elapsed = time.monotonic() - start

        # Parse output
        findings = self._parse_output(result.stdout, result.stderr)
        success = result.returncode == 0

        log.info(
            "echidna.run.complete",
            findings=len(findings),
            duration=round(elapsed, 2),
            success=success,
            return_code=result.returncode,
        )

        return ToolResult(
            tool=tool_name,
            success=success,
            findings=findings,
            raw_output=result.stdout,
            error=(
                result.stderr.strip()
                if not success and result.stderr
                else None
            ),
            duration_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_contract_name(content: str) -> str | None:
        """Extract the first contract/interface/library name from Solidity source."""
        import re as _re
        for keyword in ("contract", "interface", "library"):
            match = _re.search(
                rf"\b{keyword}\s+(\w+)",
                content,
            )
            if match:
                return match.group(1)
        return None

    def _find_contract(
        self,
        source_dir: Path,
        contract_name: str | None,
    ) -> tuple[Path | None, str]:
        """Locate the primary contract file in the source directory.

        Returns the file path and the actual Solidity contract name
        (parsed from source, not the filename).
        """
        sol_files = list(source_dir.rglob("*.sol"))
        if not sol_files:
            return None, ""

        if contract_name:
            # Try to find a file whose name or content matches
            for f in sol_files:
                if contract_name in f.stem:
                    return f, contract_name
            # Fallback: search content of files
            for f in sol_files:
                content = f.read_text(encoding="utf-8", errors="replace")
                if f"contract {contract_name}" in content:
                    return f, contract_name

        # Default: use the first .sol file, parse actual contract name
        target = sol_files[0]
        content = target.read_text(encoding="utf-8", errors="replace")
        actual_name = self._extract_contract_name(content) or target.stem
        return target, actual_name

    def _ensure_harness(
        self,
        source_dir: Path,
        contract_file: Path,
        contract_name: str,
        config: dict[str, Any] | None,
    ) -> Path:
        """Create a test harness contract if the target has no properties."""
        harness_path = source_dir / "EchidnaHarness.sol"

        # If a custom harness is specified in config, use that
        if config and config.get("harness"):
            custom_harness = source_dir / config["harness"]
            if custom_harness.exists():
                return custom_harness

        # Don't overwrite existing harness
        if harness_path.exists():
            return harness_path

        # Check if the contract already has echidna_ functions
        content = contract_file.read_text(encoding="utf-8", errors="replace")
        if re.search(r"function\s+echidna_", content):
            log.debug("echidna.properties_found", contract=contract_name)
            return contract_file

        # Determine compiler version from pragma
        compiler = "0.8.20"
        pragma_match = re.search(
            r"pragma\s+solidity\s+([^;]+)", content
        )
        if pragma_match:
            raw = pragma_match.group(1).strip()
            # Extract a specific version from range like ^0.8.0 or >=0.8.0 <0.9.0
            ver_match = re.search(r"(\d+\.\d+\.\d+)", raw)
            if ver_match:
                compiler = ver_match.group(1)

        # Write harness
        harness_code = HARNESS_TEMPLATE.format(
            compiler=compiler,
            target=contract_file.name,
            contract_name=contract_name,
        )
        try:
            harness_path.write_text(harness_code)
            log.info("echidna.harness_created", path=str(harness_path))
        except OSError as exc:
            log.warning("echidna.harness_write_failed", error=str(exc))
            return contract_file

        return harness_path

    @staticmethod
    def _build_config(
        contract_name: str,
        harness: Path,
        config: dict[str, Any] | None,
    ) -> str:
        """Build an Echidna YAML config string."""
        lines = [
            "contractAddr: \"0x00a329c0648769a73afac7f9381e08fb43dbea70\"",
            "sender: [\"0x1000\", \"0x2000\", \"0x3000\"]",
            "deployer: \"0x1000\"",
            "testLimit: 50000",
        ]

        if config:
            for key, value in config.items():
                if key == "harness":
                    continue
                if isinstance(value, list):
                    lines.append(f"{key}: {json.dumps(value)}")
                elif isinstance(value, bool):
                    lines.append(f"{key}: {'true' if value else 'false'}")
                elif isinstance(value, int):
                    lines.append(f"{key}: {value}")
                else:
                    lines.append(f"{key}: {value}")

        return "\n".join(lines)

    @staticmethod
    def _parse_output(stdout: str, stderr: str) -> list[Finding]:
        """Parse Echidna output for failed assertions and unique calls."""
        findings: list[Finding] = []
        combined = stdout + "\n" + stderr

        # Pattern: Echidna reports failures like:
        #   "echidna_no_reverts: failed!💥"
        #   "  Call sequence:"
        #   "    Transaction: f(123)"
        failure_pattern = re.compile(
            r"(echidna_[\w]+)\s*:\s*(failed|reverted)\s*!?\s*(?:💥)?"
        )

        # Track unique failures to avoid duplicates
        seen_failures: set[str] = set()

        for match in failure_pattern.finditer(combined):
            func_name = match.group(1)
            if func_name in seen_failures:
                continue
            seen_failures.add(func_name)

            # Extract the call sequence that led to the failure
            failing_input = EchidnaRunner._extract_call_sequence(
                combined, match.end()
            )

            finding = Finding(
                tool="echidna",
                severity="high",
                title=f"Echidna property violation: {func_name}",
                description=(
                    f"Echidna detected that property `{func_name}` "
                    f"can be violated. This indicates a bug in the contract."
                ),
                test_function=func_name,
                failing_input=failing_input,
                recommendation=(
                    f"Review the logic in `{func_name}` and ensure the "
                    f"invariant holds under all state conditions."
                ),
            )
            findings.append(finding)

        # Check for unique call sequences (Echidna corpus summary)
        if not findings:
            # Check for assertion failures
            assert_pattern = re.compile(
                r"Assertion\s+failed:\s*(.+)", re.IGNORECASE
            )
            for match in assert_pattern.finditer(combined):
                msg = match.group(1).strip()
                if msg not in seen_failures:
                    seen_failures.add(msg)
                    findings.append(
                        Finding(
                            tool="echidna",
                            severity="high",
                            title="Assertion failed during fuzzing",
                            description=msg,
                            test_function="assertion",
                            recommendation=(
                                "Fix the failing assertion and re-run fuzzing."
                            ),
                        )
                    )

        return findings

    @staticmethod
    def _extract_call_sequence(text: str, start: int) -> str | None:
        """Extract the Echidna call sequence after a failure marker."""
        # Look for "Call sequence:" after the failure position
        seq_start = text.find("Call sequence:", start)
        if seq_start == -1:
            return None

        # Read lines until empty line or next test name
        lines = text[seq_start:].splitlines()
        seq_lines: list[str] = []
        for line in lines[1:]:  # skip "Call sequence:" header
            stripped = line.strip()
            if not stripped or stripped.startswith("echidna_") or ":" in stripped and "failed" in stripped:
                break
            seq_lines.append(stripped)

        return "\n".join(seq_lines) if seq_lines else None


# ------------------------------------------------------------------
# Convenience factory
# ------------------------------------------------------------------

def create_echidna_runner(
    working_dir: str | Path = "/data/scanner",
    default_timeout: int = 600,
) -> EchidnaRunner:
    """Create a configured ``EchidnaRunner`` instance."""
    return EchidnaRunner(
        working_dir=working_dir,
        default_timeout=default_timeout,
    )
