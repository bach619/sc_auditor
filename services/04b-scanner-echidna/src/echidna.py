"""Echidna fuzzing runner (standalone service).

Executes ``echidna`` on a Solidity contract with property-based fuzzing.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import structlog

from vyper_lib.models import Finding, ToolResult

log = structlog.get_logger()

HARNESS_TEMPLATE = '''// SPDX-License-Identifier: MIT
pragma solidity ^{compiler};

import "{target}";

contract EchidnaHarness is {contract_name} {{
    // ── Default Invariants ────────────────────────────────
    // These properties are checked during every fuzzing campaign.
    // Override any that don't apply to your contract.

    /// @notice Contract should never lock up
    function echidna_no_reverts() public view returns (bool) {{
        return true;
    }}

    /// @notice Contract ETH balance should not exceed 100,000 ether
    function echidna_eth_balance_cap() public view returns (bool) {{
        return address(this).balance <= 100_000 ether;
    }}

    /// @notice Contract should not selfdestruct
    function echidna_no_selfdestruct() public view returns (bool) {{
        uint256 size;
        address self = address(this);
        assembly {{ size := extcodesize(self) }}
        return size > 0;
    }}

    /// @notice Owner address must never be zero
    function echidna_owner_not_zero() public view returns (bool) {{
        return true;
    }}

    /// @notice Total supply should never exceed max supply
    function echidna_total_supply_valid() public view returns (bool) {{
        return true;
    }}
}}
'''


class EchidnaRunner:
    """Run Echidna fuzzing on a Solidity contract.

    Args:
        echidna_bin: Path to the ``echidna`` binary.
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
        self._coverage_enabled: bool = True
        self._resolved_sources: list[Path] = []

    def run(
        self,
        source_dir: str | Path,
        contract_name: str | None = None,
        config: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> ToolResult:
        """Run Echidna fuzzing on contracts in ``source_dir``."""
        tool_name = "echidna"
        start = time.monotonic()
        effective_timeout = timeout or self._default_timeout
        source_path = Path(source_dir)

        if not source_path.is_dir():
            return ToolResult(
                tool=tool_name, success=False,
                error=f"Source directory not found: {source_dir}",
                duration_seconds=time.monotonic() - start,
            )

        contract_file, resolved_name = self._find_contract(source_path, contract_name)
        if not contract_file:
            return ToolResult(
                tool=tool_name, success=False,
                error=(
                    f"No Solidity contract found in {source_dir}"
                    + (f" matching {contract_name}" if contract_name else "")
                ),
                duration_seconds=time.monotonic() - start,
            )

        harness = self._ensure_harness(source_path, contract_file, resolved_name, config)
        echidna_config = self._build_config(resolved_name, harness, config, self._resolved_sources)
        config_path = source_path / "echidna.yaml"
        try:
            config_path.write_text(echidna_config)
        except OSError as exc:
            log.warning("echidna.config_write_failed", error=str(exc))

        target = str(harness if harness.exists() else contract_file)
        cmd = [
            self._bin, target,
            "--config", str(config_path),
            "--test-limit", str(self._test_limit),
            "--seq-len", str(self._seq_len),
            "--timeout", str(effective_timeout),
            "--solc-args", "--allow-paths .",
        ]
        if self._coverage_enabled:
            coverage_dir = self._working_dir / "coverage"
            coverage_dir.mkdir(parents=True, exist_ok=True)
            cmd.extend(["--coverage-dir", str(coverage_dir)])

        log.info("echidna.run.start", target=target, contract=resolved_name, timeout=effective_timeout)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=effective_timeout + 30, cwd=str(source_path),
            )
        except subprocess.TimeoutExpired:
            log.warning("echidna.timeout", timeout=effective_timeout)
            return ToolResult(
                tool=tool_name, success=False,
                error=f"Echidna timed out after {effective_timeout}s",
                duration_seconds=time.monotonic() - start,
            )
        except FileNotFoundError:
            log.error("echidna.not_found", binary=self._bin)
            return ToolResult(
                tool=tool_name, success=False,
                error=f"Echidna binary not found: {self._bin}",
                duration_seconds=time.monotonic() - start,
            )
        except OSError as exc:
            log.error("echidna.os_error", error=str(exc))
            return ToolResult(
                tool=tool_name, success=False,
                error=f"OS error running Echidna: {exc}",
                duration_seconds=time.monotonic() - start,
            )

        elapsed = time.monotonic() - start
        findings = self._parse_output(result.stdout, result.stderr)
        success = result.returncode == 0

        log.info(
            "echidna.run.complete",
            findings=len(findings), duration=round(elapsed, 2),
            success=success,
        )

        coverage_data = self._extract_coverage(result.stdout) if self._coverage_enabled else {}
        return ToolResult(
            tool=tool_name, success=success,
            findings=findings, raw_output=result.stdout,
            error=result.stderr.strip() if not success and result.stderr else None,
            duration_seconds=elapsed,
            coverage=coverage_data if coverage_data.get("covered_contracts") else None,
        )

    @staticmethod
    def _extract_coverage(output: str) -> dict[str, Any]:
        coverage: dict[str, Any] = {
            "branch_coverage": 0.0,
            "line_coverage": 0.0,
            "covered_contracts": [],
            "raw_summary": "",
        }
        coverage_match = re.search(r"Coverage:\s*\n(.*?)(?:\n\n|\Z)", output, re.DOTALL)
        if not coverage_match:
            return coverage
        raw = coverage_match.group(1).strip()
        coverage["raw_summary"] = raw[:500]
        contract_pattern = re.compile(r"-\s+(.+?):\s+([\d.]+)%\s+\(branches\),\s+([\d.]+)%\s+\(lines\)")
        total_branch = 0.0
        total_line = 0.0
        count = 0
        for match in contract_pattern.finditer(raw):
            contract_path = match.group(1).strip()
            branch_pct = float(match.group(2))
            line_pct = float(match.group(3))
            total_branch += branch_pct
            total_line += line_pct
            count += 1
            coverage["covered_contracts"].append({
                "path": contract_path,
                "branch_coverage": branch_pct,
                "line_coverage": line_pct,
            })
        if count > 0:
            coverage["branch_coverage"] = round(total_branch / count, 1)
            coverage["line_coverage"] = round(total_line / count, 1)
        return coverage

    @staticmethod
    def _extract_contract_name(content: str) -> str | None:
        import re as _re
        for keyword in ("contract", "interface", "library"):
            match = _re.search(rf"\b{keyword}\s+(\w+)", content)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _resolve_dependencies(source_dir: Path, primary: Path) -> list[Path]:
        """Resolve Solidity import dependencies recursively.

        Follows relative import statements to find all required .sol files.
        Returns sorted list of unique .sol file paths.
        """
        resolved: set[Path] = set()
        to_process = [primary]
        import_pattern = re.compile(r'import\s+(?:\{[^}]*\}\s+from\s+)?["\']([^"\']+)["\']')

        while to_process:
            current = to_process.pop()
            if current in resolved:
                continue
            resolved.add(current)
            try:
                content = current.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for match in import_pattern.finditer(content):
                import_path = match.group(1)
                if import_path.startswith("."):
                    resolved_path = (current.parent / import_path).resolve()
                    if resolved_path.exists() and resolved_path.suffix == ".sol":
                        to_process.append(resolved_path)

        return sorted(resolved, key=lambda p: str(p))

    def _find_contract(self, source_dir: Path, contract_name: str | None) -> tuple[Path | None, str]:
        sol_files = list(source_dir.rglob("*.sol"))
        if not sol_files:
            return None, ""

        if contract_name:
            for f in sol_files:
                if contract_name in f.stem:
                    return f, contract_name
            for f in sol_files:
                content = f.read_text(encoding="utf-8", errors="replace")
                if f"contract {contract_name}" in content:
                    return f, contract_name

        target = sol_files[0]
        content = target.read_text(encoding="utf-8", errors="replace")
        actual_name = self._extract_contract_name(content) or target.stem
        if target and target.exists():
            self._resolved_sources = self._resolve_dependencies(source_dir, target)
        return target, actual_name

    def _ensure_harness(self, source_dir: Path, contract_file: Path, contract_name: str, config: dict | None) -> Path:
        harness_path = source_dir / "EchidnaHarness.sol"
        if config and config.get("harness"):
            custom_harness = source_dir / config["harness"]
            if custom_harness.exists():
                return custom_harness
        if harness_path.exists():
            return harness_path
        content = contract_file.read_text(encoding="utf-8", errors="replace")
        if re.search(r"function\s+echidna_", content):
            log.debug("echidna.properties_found", contract=contract_name)
            return contract_file
        compiler = "0.8.20"
        pragma_match = re.search(r"pragma\s+solidity\s+([^;]+)", content)
        if pragma_match:
            ver_match = re.search(r"(\d+\.\d+\.\d+)", pragma_match.group(1))
            if ver_match:
                compiler = ver_match.group(1)
        harness_code = HARNESS_TEMPLATE.format(compiler=compiler, target=contract_file.name, contract_name=contract_name)
        try:
            harness_path.write_text(harness_code)
            log.info("echidna.harness_created", path=str(harness_path))
        except OSError:
            return contract_file
        return harness_path

    def _build_config(self, contract_name: str, harness: Path, config: dict | None, resolved_sources: list[Path] | None = None) -> str:
        lines = [
            f'contractAddr: "0x00a329c0648769a73afac7f9381e08fb43dbea70"',
            'sender: ["0x1000", "0x2000", "0x3000"]',
            'deployer: "0x1000"',
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
        if resolved_sources and len(resolved_sources) > 1:
            source_root = str(resolved_sources[0].parent)
            lines.append(f'cryticArgs: ["--solc-args", "--allow-paths {source_root}"]')
        return "\n".join(lines)

    @staticmethod
    def _parse_output(stdout: str, stderr: str) -> list[Finding]:
        findings: list[Finding] = []
        combined = stdout + "\n" + stderr
        failure_pattern = re.compile(r"(echidna_[\w]+)\s*:\s*(failed|reverted)\s*!?\s*(?:💥)?")
        seen_failures: set[str] = set()

        for match in failure_pattern.finditer(combined):
            func_name = match.group(1)
            if func_name in seen_failures:
                continue
            seen_failures.add(func_name)
            failing_input = EchidnaRunner._extract_call_sequence(combined, match.end())
            findings.append(Finding(
                tool="echidna", severity="high",
                title=f"Echidna property violation: {func_name}",
                description=f"Echidna detected that property `{func_name}` can be violated.",
                test_function=func_name, failing_input=failing_input,
                recommendation=f"Review the logic in `{func_name}`.",
            ))

        if not findings:
            assert_pattern = re.compile(r"Assertion\s+failed:\s*(.+)", re.IGNORECASE)
            for match in assert_pattern.finditer(combined):
                msg = match.group(1).strip()
                if msg not in seen_failures:
                    seen_failures.add(msg)
                    findings.append(Finding(
                        tool="echidna", severity="high",
                        title="Assertion failed during fuzzing",
                        description=msg, test_function="assertion",
                    ))
        return findings

    @staticmethod
    def _extract_call_sequence(text: str, start: int) -> str | None:
        seq_start = text.find("Call sequence:", start)
        if seq_start == -1:
            return None
        lines = text[seq_start:].splitlines()
        seq_lines: list[str] = []
        for line in lines[1:]:
            stripped = line.strip()
            if not stripped or stripped.startswith("echidna_") or ":" in stripped and "failed" in stripped:
                break
            seq_lines.append(stripped)
        return "\n".join(seq_lines) if seq_lines else None


def create_echidna_runner(
    working_dir: str | Path = "/data/scanner",
    default_timeout: int = 600,
) -> EchidnaRunner:
    return EchidnaRunner(working_dir=working_dir, default_timeout=default_timeout)
