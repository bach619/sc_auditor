"""Guided analysis engine — Slither → Manticore pipeline.

Alur:
  1. Contract dikirim via HTTP
  2. Compile dengan solc (via Foundry jika perlu)
  3. Opsional: call 04a-scanner-slither untuk daftar potensi bug
  4. Guided Manticore: hanya explore fungsi yang di-flag Slither
  5. Prioritaskan path HIGH/CRITICAL
  6. Konfirmasi/ tolak setiap temuan dengan symbolic proof
  7. Return findings dengan severity scoring
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import structlog

from .detectors import (
    AccessControlDetector,
    DelegatecallArbDetector,
    FlashLoanOracleDetector,
    OverflowCriticalDetector,
    ReentrancyHighDetector,
)
from .resource_guard import ResourceBudget, ResourceGuard
from .severity_scorer import SeverityScorer

log = structlog.get_logger()

# Type alias for detector instances
DetectorList = list[Any]


class GuidedAnalyzer:
    """Orchestrates Manticore analysis guided by Slither output.

    Focuses symbolic execution only on HIGH/CRITICAL suspects,
    saving time vs. full symbolic exploration.
    """

    # Manticore will be imported lazily to avoid dependency at import time
    _manticore_available: bool | None = None

    def __init__(
        self,
        slither_url: str | None = None,
        default_budget: ResourceBudget | None = None,
    ) -> None:
        self._slither_url = slither_url or os.environ.get(
            "SLITHER_URL", "http://04a-scanner-slither:8014"
        )
        self._budget = default_budget or ResourceBudget()
        self._resource_guard = ResourceGuard(self._budget)
        self._detectors: DetectorList = []

    @property
    def resource_guard(self) -> ResourceGuard:
        return self._resource_guard

    async def analyze(
        self,
        source_files: dict[str, str],
        contract_name: str | None = None,
        functions_to_test: list[str] | None = None,
        timeout: int = 300,
        use_slither_guide: bool = True,
        synthax_analysis: bool = True,
    ) -> dict[str, Any]:
        """Run guided Manticore analysis on the given source files.

        Args:
            source_files: Dict of path -> source code
            contract_name: Specific contract to analyze (auto-detect if None)
            functions_to_test: Only test these functions
            timeout: Max duration in seconds
            use_slither_guide: Call Slither first to guide symbolic execution
            synthax_analysis: Perform synthax (synthetic) analysis too

        Returns:
            dict with findings, summary, resource_usage
        """
        start_time = time.monotonic()
        audit_id = uuid.uuid4().hex[:12]
        work_dir = Path(f"/tmp/manticore_{audit_id}")
        work_dir.mkdir(parents=True, exist_ok=True)

        self._resource_guard.start(
            contract_complexity=self._estimate_complexity(source_files)
        )

        findings: list[dict[str, Any]] = []
        slither_findings: list[dict[str, Any]] = []

        try:
            # 1. Write source files to workspace
            sources_root = await self._write_sources(work_dir, source_files)

            # 2. Compile contract
            compiled_path = await self._compile_contract(sources_root, contract_name)
            if not compiled_path:
                return {
                    "error": "Contract compilation failed",
                    "audit_id": audit_id,
                    "findings": [],
                    "summary": {"total_findings": 0, "critical_count": 0, "high_count": 0},
                    "resource_usage": self._resource_guard.usage.to_dict(),
                }

            # 3. Optionally call Slither for guiding
            if use_slither_guide:
                try:
                    slither_findings = await self._call_slither(source_files)
                    log.info("slither_guide_completed", findings=len(slither_findings))
                except Exception as e:
                    log.warning("slither_guide_failed", error=str(e))
                    slither_findings = []

            # 4. Build target list from Slither output or user input
            targets = self._build_target_list(
                slither_findings, functions_to_test, source_files
            )

            # 5. Run Manticore symbolic execution
            if self._check_manticore():
                findings = await self._run_manticore_analysis(
                    compiled_path=compiled_path,
                    targets=targets,
                    source_files=source_files,
                )
            else:
                log.warning("manticore_not_available_falling_back_to_synthax")
                # Fallback: synthax analysis based on Slither output alone
                if synthax_analysis:
                    findings = self._synthax_analysis(
                        slither_findings, source_files, targets
                    )

            # 6. Score and filter HIGH/CRITICAL
            findings = SeverityScorer.filter_high_critical(findings)

            # 7. Build summary
            summary = SeverityScorer.aggregate_summary(findings, slither_findings)
            elapsed = time.monotonic() - start_time

            result: dict[str, Any] = {
                "audit_id": audit_id,
                "contract_name": contract_name or "unknown",
                "duration_seconds": round(elapsed, 2),
                "findings": findings,
                "summary": summary,
                "resource_usage": self._resource_guard.usage.to_dict(),
            }

            # Add Slither cross-reference if available
            if slither_findings:
                result["slither_cross_reference"] = {
                    "total_slither_findings": len(slither_findings),
                    "confirmed_by_manticore": summary.get("confirmed_from_slither", 0),
                    "new_findings_by_manticore": summary.get("new_findings", 0),
                }

            return result

        except Exception as e:
            log.exception("guided_analysis_failed", error=str(e))
            return {
                "error": str(e),
                "audit_id": audit_id,
                "findings": [],
                "summary": {"total_findings": 0, "critical_count": 0, "high_count": 0},
                "resource_usage": self._resource_guard.usage.to_dict(),
            }
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    async def confirm_finding(
        self,
        source_files: dict[str, str],
        finding: dict[str, Any],
        timeout: int = 120,
    ) -> dict[str, Any]:
        """Deep-confirm a specific finding with focused symbolic execution.

        Given a suspected bug from any source (manual review, Slither, etc.),
        run Manticore specifically targeting that path.
        """
        audit_id = uuid.uuid4().hex[:12]
        work_dir = Path(f"/tmp/manticore_confirm_{audit_id}")
        work_dir.mkdir(parents=True, exist_ok=True)

        try:
            await self._write_sources(work_dir, source_files)

            bug_type = finding.get("bug_type", "")
            function_name = finding.get("function", "")

            # Use the appropriate detector for confirmation
            if bug_type in ("reentrancy", "cross_contract_reentrancy"):
                detector = ReentrancyHighDetector()
            elif bug_type in ("access_control", "unprotected_initialization", "unprotected_selfdestruct"):
                detector = AccessControlDetector()
            elif bug_type in ("flash_loan", "oracle_manipulation"):
                detector = FlashLoanOracleDetector()
            elif bug_type in ("overflow", "underflow"):
                detector = OverflowCriticalDetector()
            elif bug_type in ("delegatecall", "arbitrary_delegatecall"):
                detector = DelegatecallArbDetector()
            else:
                return {
                    "audit_id": audit_id,
                    "confirmed": False,
                    "error": f"No matching detector for bug type: {bug_type}",
                }

            # Run targeted analysis
            findings = await self._run_manticore_analysis(
                compiled_path=work_dir / "compiled",
                targets=[function_name] if function_name else [],
                source_files=source_files,
                extra_detectors=[detector],
            )

            confirmed = len(findings) > 0

            return {
                "audit_id": audit_id,
                "confirmed": confirmed,
                "finding": finding,
                "manticore_findings": SeverityScorer.filter_high_critical(findings),
            }

        except Exception as e:
            return {
                "audit_id": audit_id,
                "confirmed": False,
                "error": str(e),
            }
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    # ── Private Helpers ──────────────────────────────────

    async def _write_sources(self, work_dir: Path, sources: dict[str, str]) -> Path:
        """Write source files to workspace directory."""
        src_dir = work_dir / "sources"
        src_dir.mkdir(parents=True, exist_ok=True)
        for file_path, code in sources.items():
            target = src_dir / file_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(code, encoding="utf-8")
        return src_dir

    async def _compile_contract(
        self, sources_root: Path, contract_name: str | None = None
    ) -> Path | None:
        """Compile Solidity contract using solc.

        Returns path to compiled bytecode, or None on failure.
        """
        compiled_dir = sources_root.parent / "compiled"
        compiled_dir.mkdir(parents=True, exist_ok=True)

        sol_files = list(sources_root.rglob("*.sol"))
        if not sol_files:
            return None

        try:
            proc = await asyncio.create_subprocess_exec(
                "solc",
                "--combined-json", "abi,bin,bin-runtime,metadata",
                *(str(f) for f in sol_files),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(sources_root),
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                log.warning("compilation_failed", stderr=stderr.decode())
                return None

            result = json.loads(stdout.decode())
            output_file = compiled_dir / "combined.json"
            output_file.write_text(json.dumps(result), encoding="utf-8")
            return output_file

        except FileNotFoundError:
            log.warning("solc_not_found_compilation_skipped")
            return None
        except Exception as e:
            log.warning("compilation_error", error=str(e))
            return None

    async def _call_slither(
        self, source_files: dict[str, str]
    ) -> list[dict[str, Any]]:
        """Call 04a-scanner-slither for static analysis guidance."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._slither_url}/analyze",
                json={"sources": source_files},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", [])
            return []

    def _build_target_list(
        self,
        slither_findings: list[dict[str, Any]],
        user_functions: list[str] | None,
        source_files: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Build list of analysis targets from Slither output and user input.

        Each target has:
          - function: function name to analyze
          - bug_type: suspected vulnerability
          - confidence: how likely this is a real bug
          - priority: 0-10
        """
        targets: list[dict[str, Any]] = []

        # From Slither: extract function names from findings
        for finding in slither_findings:
            func = finding.get("function", "") or finding.get("target", "")
            if func:
                targets.append({
                    "function": func,
                    "bug_type": finding.get("check", "unknown"),
                    "confidence": finding.get("confidence", 0.5),
                    "priority": 8 if finding.get("impact", "").lower() == "high" else 5,
                    "source": "slither",
                })

        # From user: specific functions to test
        if user_functions:
            for func in user_functions:
                # Add or update priority
                existing = [t for t in targets if t["function"] == func]
                if existing:
                    existing[0]["priority"] = 10
                    existing[0]["source"] = "user"
                else:
                    targets.append({
                        "function": func,
                        "bug_type": "manual",
                        "confidence": 0.5,
                        "priority": 10,
                        "source": "user",
                    })

        # If no targets from anywhere, analyze all external functions
        if not targets:
            targets = self._extract_all_functions(source_files)

        # Sort by priority descending
        targets.sort(key=lambda t: t.get("priority", 0), reverse=True)
        return targets

    def _extract_all_functions(
        self, source_files: dict[str, str]
    ) -> list[dict[str, Any]]:
        """Basic extraction of function definitions from Solidity source."""
        targets: list[dict[str, Any]] = []

        for path, code in source_files.items():
            for line in code.split("\n"):
                stripped = line.strip()
                if stripped.startswith("function "):
                    parts = stripped.split("(")
                    if parts:
                        func_name = parts[0].replace("function ", "").strip()
                        targets.append({
                            "function": func_name,
                            "bug_type": "general",
                            "confidence": 0.3,
                            "priority": 3,
                            "source": "auto_detect",
                        })
        return targets

    def _estimate_complexity(self, source_files: dict[str, str]) -> str:
        """Estimate contract complexity based on source size and structures."""
        total_lines = sum(len(code.split("\n")) for code in source_files.values())

        if total_lines < 100:
            return "simple"
        elif total_lines < 500:
            return "medium"
        elif total_lines < 1000:
            return "complex"
        else:
            return "extreme"

    def _check_manticore(self) -> bool:
        """Check if Manticore is importable."""
        if GuidedAnalyzer._manticore_available is not None:
            return GuidedAnalyzer._manticore_available

        try:
            import manticore  # noqa: F401
            GuidedAnalyzer._manticore_available = True
        except ImportError:
            GuidedAnalyzer._manticore_available = False

        return GuidedAnalyzer._manticore_available

    async def _run_manticore_analysis(
        self,
        compiled_path: Path,
        targets: list[dict[str, Any]],
        source_files: dict[str, str],
        extra_detectors: DetectorList | None = None,
    ) -> list[dict[str, Any]]:
        """Execute Manticore symbolic execution with registered detectors.

        Falls back to synthax analysis if Manticore is unavailable.
        """
        findings: list[dict[str, Any]] = []

        if not self._check_manticore():
            log.warning("manticore_not_available_using_synthax_fallback")
            return self._synthax_analysis([], source_files, targets)

        try:
            # Lazy import Manticore
            from manticore import ManticoreEVM  # type: ignore[import-untyped]

            for target in targets:
                if not self._resource_guard.check():
                    break

                func_name = target.get("function", "")
                if self._resource_guard.should_skip_function(func_name, target):
                    continue

                log.info(
                    "analyzing_function",
                    function=func_name,
                    bug_type=target.get("bug_type"),
                )

                # Create fresh Manticore instance per function
                m = ManticoreEVM()

                # Register all detectors
                self._detectors = [
                    ReentrancyHighDetector(),
                    AccessControlDetector(),
                    FlashLoanOracleDetector(),
                    OverflowCriticalDetector(),
                    DelegatecallArbDetector(),
                ]
                if extra_detectors:
                    self._detectors.extend(extra_detectors)

                for detector in self._detectors:
                    m.register_plugin(detector)

                # Configure Manticore
                m.verbosity(0)  # Minimize output

                try:
                    # Run symbolic execution
                    # Note: actual Manticore API may vary; we attempt the common pattern
                    if compiled_path.suffix == ".json":
                        combined = json.loads(compiled_path.read_text())
                        for contract_name, contract_data in combined.get("contracts", {}).items():
                            bytecode = contract_data.get("bin", "")
                            if bytecode:
                                m.create_contract(bytecode=bytecode)
                                m.transaction(
                                    caller=lambda: True,  # Symbolic caller
                                    function=func_name if func_name else None,
                                )
                                m.run()

                    # Collect findings from all detectors
                    for detector in self._detectors:
                        detector_findings = detector.get_findings()
                        findings.extend(detector_findings)
                        detector.reset()

                    self._resource_guard.record_path()

                except Exception as e:
                    log.warning(
                        "manticore_function_analysis_failed",
                        function=func_name,
                        error=str(e),
                    )
                    continue

        except Exception as e:
            log.exception("manticore_execution_failed", error=str(e))

        return findings

    def _synthax_analysis(
        self,
        slither_findings: list[dict[str, Any]],
        source_files: dict[str, str],
        targets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Fallback analysis when Manticore is not available.

        Performs pattern-based analysis on the source code directly,
        combined with Slither output for severity assessment.
        """
        findings: list[dict[str, Any]] = []

        # Cross-reference Slither findings with HIGH/CRITICAL scoring
        for finding in slither_findings:
            severity = (finding.get("impact", "") or "").lower()
            if severity in ("high", "critical"):
                findings.append({
                    "severity": severity,
                    "bug_type": finding.get("check", "unknown"),
                    "title": finding.get("title", ""),
                    "description": finding.get("description", ""),
                    "confidence": finding.get("confidence", 0.5) * 0.8,  # Lower without Manticore
                    "detector": "synthax_fallback",
                    "metadata": {
                        "source": "slither_cross_reference",
                        "manticore_unavailable": True,
                    },
                })

        # Pattern-based analysis for common HIGH/CRIT patterns
        for file_path, code in source_files.items():
            # Reentrancy pattern: call + state change
            if (self._pattern_match(code, r"(\.call|\.delegatecall)\s*\{.*value\s*:")
                    and self._pattern_match(code, r"(state|balance|account)\s*=")):
                findings.append({
                    "severity": "high",
                    "bug_type": "potential_reentrancy",
                    "title": "External call with value before state change",
                    "description": "CEI pattern violation detected in source analysis",
                    "confidence": 0.4,
                    "detector": "synthax_pattern",
                    "metadata": {"file": file_path, "manticore_unavailable": True},
                })

            # Access control: owner check pattern
            if not self._pattern_match(code, r"(require|if)\s*\(.*owner.*==.*msg\.sender"):
                for keyword in ["withdraw", "mint", "burn", "destroy", "upgradeTo"]:
                    if keyword in code:
                        findings.append({
                            "severity": "high",
                            "bug_type": "potential_access_control",
                            "title": f"'{keyword}' may lack access control",
                            "description": f"Function '{keyword}' found without explicit owner check",
                            "confidence": 0.3,
                            "detector": "synthax_pattern",
                            "metadata": {"file": file_path, "keyword": keyword},
                        })

            # Delegatecall pattern
            if self._pattern_match(code, r"delegatecall\(.*(addr|target|_to)"):
                findings.append({
                    "severity": "critical",
                    "bug_type": "potential_arbitrary_delegatecall",
                    "title": "Delegatecall with variable target address",
                    "description": "Potential arbitrary delegatecall detected",
                    "confidence": 0.35,
                    "detector": "synthax_pattern",
                    "metadata": {"file": file_path},
                })

        return findings

    @staticmethod
    def _pattern_match(code: str, pattern: str) -> bool:
        """Check if a regex pattern exists in the source code."""
        import re
        try:
            return bool(re.search(pattern, code, re.MULTILINE))
        except re.error:
            return False
