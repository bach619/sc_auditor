"""Full Report Generator for Vyper Reporter Service.

Generates comprehensive Markdown audit reports containing all findings
(TP, FP, TN, FN), performance metrics, tool breakdowns, file statistics,
and appendices. Designed for internal review and record-keeping.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.filters import ascii_severity_chart, register_filters
from src.models import (
    ExploitResult,
    Finding,
    Metrics,
    SourceInfo,
    ToolMetrics,
)

log = structlog.get_logger()

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
REPORTS_BASE = Path("/data/reporter/reports")


class FullReportGenerator:
    """Generates comprehensive Markdown audit reports.

    Unlike the Immunefi report, the full report includes ALL findings
    regardless of classification, along with metrics, ASCII charts,
    tool performance breakdowns, file statistics, and detailed
    appendices covering configurations and exploit details.

    Attributes:
        env: Jinja2 environment loaded with the full report template.
    """

    def __init__(self, templates_dir: str | Path = TEMPLATES_DIR) -> None:
        """Initialize the generator with a Jinja2 environment.

        Args:
            templates_dir: Path to the Jinja2 templates directory.
                           Defaults to ``src/templates/``.
        """
        loader = FileSystemLoader(str(templates_dir))
        self.env = Environment(
            loader=loader,
            autoescape=select_autoescape(default=False),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        register_filters(self.env)
        self.template = self.env.get_template("full.md.j2")
        log.info("full_generator.initialized", templates_dir=str(templates_dir))

    def generate(
        self,
        audit_id: str,
        program: str,
        chain: str,
        address: str,
        findings: list[Finding],
        metrics: Metrics | None = None,
        exploit_results: list[ExploitResult] | None = None,
        source_info: SourceInfo | None = None,
    ) -> str:
        """Generate the comprehensive full audit report.

        All findings are included and sorted by severity. The report
        includes metrics, tool performance, file statistics, and
        configuration appendices.

        Args:
            audit_id: Audit session identifier.
            program: Immunefi program name.
            chain: Blockchain name.
            address: Contract address.
            findings: All findings (all classifications).
            metrics: Audit performance metrics.
            exploit_results: Exploit Service results.
            source_info: Source code metadata.

        Returns:
            The full Markdown content as a string.
        """
        # Sort all findings by severity
        sorted_findings = self._sort_by_severity(findings)

        # Build exploit lookup map
        exploit_map: dict[str, ExploitResult] = {}
        if exploit_results:
            for er in exploit_results:
                exploit_map[er.finding_id] = er

        # Severity distribution (all findings)
        severity_counts = self._severity_distribution(sorted_findings)

        # ASCII bar chart of severity distribution
        ascii_chart = ascii_severity_chart(severity_counts)

        # Per-tool metrics breakdown
        tool_metrics = self._compute_tool_metrics(sorted_findings)

        # Counts by status
        tp_count = sum(
            1
            for f in sorted_findings
            if f.classification.lower() in ("true_positive", "tp", "true positive")
        )
        fp_count = sum(
            1
            for f in sorted_findings
            if f.classification.lower() in ("false_positive", "fp", "false positive")
        )

        generated_at = datetime.now(UTC).isoformat()

        content = self.template.render(
            audit_id=audit_id,
            program=program,
            chain=chain,
            address=address,
            findings=sorted_findings,
            exploit_map=exploit_map,
            exploit_results=exploit_results or [],
            metrics=metrics or Metrics(),
            source_info=source_info,
            severity_counts=severity_counts,
            ascii_chart=ascii_chart,
            tool_metrics=tool_metrics,
            tp_count=tp_count,
            fp_count=fp_count,
            generated_at=generated_at,
            config_tier="default",
            mythril_timeout=300,
            echidna_timeout=600,
        )

        self._save_report(audit_id, content, "full.md")

        log.info(
            "full_report.generated",
            audit_id=audit_id,
            program=program,
            total_findings=len(sorted_findings),
            tp=tp_count,
            fp=fp_count,
        )

        return content

    def _save_report(self, audit_id: str, content: str, filename: str) -> Path:
        """Persist the report to disk.

        Args:
            audit_id: Audit identifier used as the subdirectory name.
            content: Markdown content to write.
            filename: Report filename (``"full.md"``).

        Returns:
            The path to the saved file.
        """
        report_dir = REPORTS_BASE / audit_id
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / filename
        report_path.write_text(content, encoding="utf-8")

        log.debug(
            "report.saved",
            path=str(report_path),
            size_bytes=len(content.encode("utf-8")),
        )
        return report_path

    @staticmethod
    def _sort_by_severity(findings: list[Finding]) -> list[Finding]:
        """Sort findings by severity (critical → informational).

        Within the same severity, findings maintain their original order.

        Args:
            findings: List of findings to sort.

        Returns:
            Sorted list of findings.
        """
        SEVERITY_ORDER = {
            "critical": 0,
            "high": 1,
            "medium": 2,
            "low": 3,
            "informational": 4,
            "info": 4,
        }
        return sorted(
            findings,
            key=lambda f: SEVERITY_ORDER.get(f.severity.lower(), 99),
        )

    @staticmethod
    def _severity_distribution(
        findings: list[Finding],
    ) -> list[tuple[str, int]]:
        """Compute severity distribution for a list of findings.

        Args:
            findings: List of findings to aggregate.

        Returns:
            List of ``(severity, count)`` tuples in severity order.
        """
        SEVERITY_ORDER = [
            "critical",
            "high",
            "medium",
            "low",
            "informational",
        ]
        counts: dict[str, int] = {}
        for f in findings:
            sev = f.severity.lower()
            if sev == "info":
                sev = "informational"
            counts[sev] = counts.get(sev, 0) + 1
        return [(sev, counts.get(sev, 0)) for sev in SEVERITY_ORDER]

    @staticmethod
    def _compute_tool_metrics(findings: list[Finding]) -> list[ToolMetrics]:
        """Compute per-tool TP/FP/precision metrics.

        Args:
            findings: All classified findings.

        Returns:
            List of ``ToolMetrics``, one per tool, sorted by TP count.
        """
        tool_data: dict[str, dict[str, int]] = {}

        for f in findings:
            if f.tool not in tool_data:
                tool_data[f.tool] = {"tp": 0, "fp": 0}

            if f.classification.lower() in ("true_positive", "tp", "true positive"):
                tool_data[f.tool]["tp"] += 1
            elif f.classification.lower() in ("false_positive", "fp", "false positive"):
                tool_data[f.tool]["fp"] += 1

        result: list[ToolMetrics] = []
        for tool, counts in tool_data.items():
            precision = (
                counts["tp"] / (counts["tp"] + counts["fp"])
                if (counts["tp"] + counts["fp"]) > 0
                else 0.0
            )
            result.append(
                ToolMetrics(
                    tool=tool,
                    tp=counts["tp"],
                    fp=counts["fp"],
                    precision=precision,
                )
            )

        result.sort(key=lambda tm: tm.tp, reverse=True)
        return result
