"""Guided analysis engine — Slither → Mythril deep confirmation pipeline.

Alur:
  1. Contract dikirim via HTTP
  2. Call 04a-scanner-slither untuk daftar potensi bug (jika tersedia)
  3. Filter Slither findings: hanya HIGH/CRITICAL
  4. For each flagged function: jalankan Mythril dengan depth lebih dalam
  5. Konfirmasi/tolak temuan Slither dengan symbolic proof
  6. Tambahkan temuan Mythril yang Slither tidak detect
  7. Return findings dengan severity scoring + cross-reference
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import structlog

from .resource_guard import ResourceBudget, ResourceGuard
from .severity_scorer import SeverityScorer

log = structlog.get_logger()


class GuidedAnalyzer:
    """Orchestrates Mythril analysis guided by Slither output.

    Focus: HIGH/CRITICAL bug confirmation with deep symbolic execution.
    """

    def __init__(
        self,
        slither_url: str | None = None,
        ai_url: str | None = None,
        manticore_url: str | None = None,
        default_budget: ResourceBudget | None = None,
    ) -> None:
        self._slither_url = slither_url or os.environ.get(
            "SLITHER_URL", "http://04a-scanner-slither:8014"
        )
        self._ai_url = ai_url or os.environ.get(
            "AI_URL", "http://06-ai:8004"
        )
        self._manticore_url = manticore_url or os.environ.get(
            "MANTICORE_URL", "http://04e-scanner-manticore:8018"
        )
        self._budget = default_budget or ResourceBudget()
        self._resource_guard = ResourceGuard(self._budget)

    @property
    def resource_guard(self) -> ResourceGuard:
        return self._resource_guard

    async def analyze(
        self,
        source_files: dict[str, str],
        functions_to_test: list[str] | None = None,
        timeout: int = 300,
        depth: int = 42,
        use_slither_guide: bool = True,
        use_custom_plugins: bool = True,
    ) -> dict[str, Any]:
        """Run guided Mythril analysis.

        Args:
            source_files: Dict of path -> source code
            functions_to_test: Specific functions to analyze
            timeout: Max duration per function
            depth: Mythril analysis depth (default 42 vs standard 32)
            use_slither_guide: Call Slither first for guidance
            use_custom_plugins: Use custom Mythril modules

        Returns:
            dict with findings, summary, resource_usage
        """
        start_time = time.monotonic()
        audit_id = uuid.uuid4().hex[:12]
        work_dir = Path(tempfile.mkdtemp(prefix=f"mythril_guided_{audit_id}_"))

        self._resource_guard.start(
            contract_complexity=self._estimate_complexity(source_files)
        )

        mythril_findings: list[dict[str, Any]] = []
        slither_findings: list[dict[str, Any]] = []
        custom_findings: list[dict[str, Any]] = []

        try:
            # 1. Write sources
            sources_dir = await self._write_sources(work_dir, source_files)

            # 2. Call Slither for guidance
            if use_slither_guide:
                try:
                    slither_findings = await self._call_slither(source_files)
                    log.info("slither_guide_completed", count=len(slither_findings))
                except Exception as e:
                    log.warning("slither_guide_failed", error=str(e))

            # 3. Build target list
            targets = self._build_target_list(
                slither_findings, functions_to_test
            )

            # 4. Run standard Mythril analysis
            mythril_findings = await self._run_mythril(
                sources_dir=sources_dir,
                source_files=source_files,
                depth=depth,
                timeout=timeout,
            )

            # 5. Run custom Mythril plugins separately
            if use_custom_plugins:
                custom_findings = await self._run_custom_plugins(
                    sources_dir=sources_dir,
                    source_files=source_files,
                    targets=targets,
                    timeout=timeout,
                )

            # 6. Merge all findings
            all_findings = self._merge_findings(
                mythril_findings, custom_findings, slither_findings
            )

            # 7. Score and filter HIGH/CRITICAL
            scored_findings = SeverityScorer.filter_high_critical(all_findings)

            # 8. Cross-reference
            cross_ref = await self._cross_reference(
                scored_findings, source_files
            )

            # 9. Build summary
            summary = self._build_summary(
                scored_findings, cross_ref, slither_findings
            )

            elapsed = time.monotonic() - start_time

            return {
                "audit_id": audit_id,
                "duration_seconds": round(elapsed, 2),
                "findings": scored_findings,
                "summary": summary,
                "cross_reference": cross_ref,
                "resource_usage": self._resource_guard.usage.to_dict(),
                "errors": [],
            }

        except Exception as e:
            log.exception("guided_analysis_failed", error=str(e))
            return {
                "audit_id": audit_id,
                "error": str(e),
                "findings": [],
                "summary": {"total_findings": 0, "critical_count": 0, "high_count": 0},
                "cross_reference": {},
                "resource_usage": self._resource_guard.usage.to_dict(),
            }
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    # ── Private Helpers ──────────────────────────────────

    async def _write_sources(self, work_dir: Path, sources: dict[str, str]) -> Path:
        src_dir = work_dir / "sources"
        src_dir.mkdir(parents=True, exist_ok=True)
        for file_path, code in sources.items():
            target = src_dir / file_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(code, encoding="utf-8")
        return src_dir

    async def _call_slither(self, sources: dict[str, str]) -> list[dict[str, Any]]:
        """Call 04a-scanner-slither for static analysis guidance."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._slither_url}/analyze",
                json={"sources": sources},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", data.get("findings", []))
            return []

    def _build_target_list(
        self,
        slither_findings: list[dict[str, Any]],
        user_functions: list[str] | None,
    ) -> list[dict[str, Any]]:
        """Build analysis targets prioritizing HIGH/CRITICAL."""
        targets: list[dict[str, Any]] = []

        # From Slither
        high_impact = {"high", "critical"}
        for f in slither_findings:
            impact = (f.get("impact", "") or "").lower()
            func = f.get("function", "") or f.get("target", "")
            if impact in high_impact and func:
                targets.append({
                    "function": func,
                    "bug_type": f.get("check", "unknown"),
                    "priority": 10 if impact == "critical" else 8,
                    "source": "slither",
                })

        # From user
        if user_functions:
            for func in user_functions:
                existing = [t for t in targets if t["function"] == func]
                if existing:
                    existing[0]["priority"] = 10
                else:
                    targets.append({
                        "function": func,
                        "bug_type": "user_requested",
                        "priority": 9,
                        "source": "user",
                    })

        targets.sort(key=lambda t: t.get("priority", 0), reverse=True)
        return targets

    def _estimate_complexity(self, sources: dict[str, str]) -> str:
        total_lines = sum(len(code.split("\n")) for code in sources.values())
        if total_lines < 100:
            return "simple"
        elif total_lines < 500:
            return "medium"
        elif total_lines < 1000:
            return "complex"
        else:
            return "extreme"

    async def _run_mythril(
        self,
        sources_dir: Path,
        source_files: dict[str, str],
        depth: int = 42,
        timeout: int = 300,
    ) -> list[dict[str, Any]]:
        """Run standard mythril analyze CLI."""
        findings: list[dict[str, Any]] = []

        sol_files = list(sources_dir.rglob("*.sol"))
        if not sol_files:
            return findings

        # Write solc config
        config = {"remappings": [], "optimizer": {"enabled": False}}
        config_file = sources_dir / "solc.json"
        config_file.write_text(json.dumps(config))

        try:
            cmd = [
                "mythril",
                "analyze",
                "--solc-json", str(config_file),
                "--solc", "solc",
                "--out", "json",
                "--max-depth", str(depth),
                "--execution-timeout", str(timeout),
            ]

            for sol in sol_files:
                self._resource_guard.record_state()
                if not self._resource_guard.check():
                    break

                cmd.append(str(sol))
                log.info("running_mythril", file=str(sol), depth=depth)

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout + 30
                )

                if proc.returncode == 0 and stdout:
                    try:
                        lines = stdout.decode().strip().split("\n")
                        for line in lines:
                            if not line.strip():
                                continue
                            try:
                                finding = json.loads(line)
                                findings.append(finding)
                            except json.JSONDecodeError:
                                pass
                    except Exception:
                        pass

                cmd.pop()  # Remove sol file from cmd
                self._resource_guard.record_path()

        except FileNotFoundError:
            log.warning("mythril_cli_not_found")
        except TimeoutError:
            log.warning("mythril_timeout")
        except Exception as e:
            log.warning("mythril_execution_error", error=str(e))

        return findings

    async def _run_custom_plugins(
        self,
        sources_dir: Path,
        source_files: dict[str, str],
        targets: list[dict[str, Any]],
        timeout: int = 300,
    ) -> list[dict[str, Any]]:
        """Run Mythril with custom plugins loaded."""
        findings: list[dict[str, Any]] = []

        # Custom plugins path
        plugins_dir = Path(__file__).parent / "mythril_modules"

        sol_files = list(sources_dir.rglob("*.sol"))
        if not sol_files:
            return findings

        config = {"remappings": [], "optimizer": {"enabled": False}}
        config_file = sources_dir / "solc.json"
        config_file.write_text(json.dumps(config))

        try:
            cmd = [
                "mythril",
                "analyze",
                "--solc-json", str(config_file),
                "--solc", "solc",
                "--out", "json",
                "--max-depth", str(64),  # Deeper for custom analysis
                "--execution-timeout", str(timeout),
                "--plugins", str(plugins_dir),
            ]

            for sol in sol_files:
                if not self._resource_guard.check():
                    break

                target_funcs = [t["function"] for t in targets if t.get("priority", 0) >= 8]
                if target_funcs:
                    cmd.extend(["--functions", ",".join(target_funcs)])

                cmd.append(str(sol))
                log.info("running_mythril_plugins", file=str(sol))

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout + 30
                )

                if stdout:
                    try:
                        output = stdout.decode()
                        for line in output.strip().split("\n"):
                            if not line.strip():
                                continue
                            try:
                                finding = json.loads(line)
                                # Tag as custom plugin finding
                                finding["source"] = "custom_plugin"
                                findings.append(finding)
                            except json.JSONDecodeError:
                                pass
                    except Exception:
                        pass

                # Clean up added args
                cmd.pop()
                if target_funcs:
                    cmd.pop()

        except Exception as e:
            log.warning("custom_plugins_error", error=str(e))

        return findings

    def _merge_findings(
        self,
        mythril: list[dict[str, Any]],
        custom: list[dict[str, Any]],
        slither: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge findings from multiple sources, deduplicate by title."""
        seen_titles: set[str] = set()
        merged: list[dict[str, Any]] = []

        for finding in mythril + custom:
            title = finding.get("title", "")
            if title not in seen_titles:
                seen_titles.add(title)
                merged.append(finding)

        return merged

    async def _cross_reference(
        self,
        findings: list[dict[str, Any]],
        source_files: dict[str, str],
    ) -> dict[str, Any]:
        """Cross-reference Mythril findings with other scanners (async where possible)."""
        ref: dict[str, Any] = {
            "confirmed_by_slither": 0,
            "confirmed_by_manticore": 0,
            "unique_to_mythril": 0,
            "total_cross_refs": 0,
            "details": [],
        }

        for finding in findings:
            detail: dict[str, Any] = {
                "title": finding.get("title", ""),
                "bug_type": finding.get("bug_type", ""),
                "slither_match": False,
                "manticore_match": False,
            }

            # Try Manticore confirmation (if available)
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{self._manticore_url}/confirm",
                        json={
                            "sources": source_files,
                            "finding": finding,
                            "timeout": 60,
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        manticore_data = data.get("data", data)
                        detail["manticore_match"] = manticore_data.get("confirmed", False)
                        if detail["manticore_match"]:
                            ref["confirmed_by_manticore"] += 1
            except Exception:
                pass

            ref["details"].append(detail)

        ref["total_cross_refs"] = len(ref["details"])
        ref["unique_to_mythril"] = ref["total_cross_refs"] - ref["confirmed_by_slither"]
        return ref

    def _build_summary(
        self,
        findings: list[dict[str, Any]],
        cross_ref: dict[str, Any],
        slither_findings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        critical = [f for f in findings if f.get("severity") == "critical"]
        high = [f for f in findings if f.get("severity") == "high"]

        return {
            "total_findings": len(findings),
            "critical_count": len(critical),
            "high_count": len(high),
            "critical_findings": critical,
            "high_findings": high,
            "avg_confidence": round(
                sum(f.get("score", 0.5) for f in findings) / len(findings), 3
            ) if findings else 0.0,
            "cross_reference": cross_ref,
            "confirmed_from_slither": len(
                [f for f in findings if f.get("confirmed_by_slither", False)]
            ),
        }
