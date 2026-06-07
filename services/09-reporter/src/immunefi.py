"""Immunefi Report Generator for Vyper Reporter Service.

Generates Immunefi-compatible Markdown audit reports containing only
True Positive (TP) findings with exploit Proofs of Concept. This is the
primary deliverable for Immunefi bug bounty submissions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.filters import register_filters
from src.models import ExploitResult, Finding

log = structlog.get_logger()

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
REPORTS_BASE = Path("/data/reporter/reports")


class ImmunefiReportGenerator:
    """Generates Immunefi-compatible Markdown audit reports.

    The report includes only True Positive findings (Immunefi expects
    actionable, verified vulnerability reports — not noise). Each finding
    includes a detailed description, vulnerability analysis, and a working
    Proof of Concept from the Exploit Service.

    Attributes:
        env: Jinja2 environment loaded with the immunefi template.
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
        self.template = self.env.get_template("immunefi.md.j2")
        log.info("immunefi_generator.initialized", templates_dir=str(templates_dir))

    def generate(
        self,
        audit_id: str,
        program: str,
        chain: str,
        address: str,
        findings: list[Finding],
        exploit_results: list[ExploitResult] | None = None,
    ) -> str:
        """Generate the Immunefi submission report.

        Only True Positive findings are included. Critical-severity
        findings are listed first, followed by high, medium, and low.

        Args:
            audit_id: Audit session identifier.
            program: Immunefi program name (e.g. ``"ethena"``).
            chain: Blockchain name (e.g. ``"ethereum"``).
            address: Contract address being audited.
            findings: All classified findings (will be filtered to TP).
            exploit_results: Results from the Exploit Service.

        Returns:
            The Markdown content as a string.
        """
        # Filter to TP-only findings, sorted by severity
        tp_findings = self._filter_true_positives(findings, exploit_results)

        # Build exploit lookup map
        exploit_map: dict[str, ExploitResult] = {}
        if exploit_results:
            for er in exploit_results:
                exploit_map[er.finding_id] = er

        # Severity distribution (TP only)
        severity_counts = self._severity_distribution(tp_findings)
        critical_count = sum(
            c for sev, c in severity_counts if sev.lower() == "critical"
        )
        high_count = sum(c for sev, c in severity_counts if sev.lower() == "high")

        generated_at = datetime.now(UTC).isoformat()

        content = self.template.render(
            audit_id=audit_id,
            program=program,
            chain=chain,
            address=address,
            findings=tp_findings,
            exploit_map=exploit_map,
            severity_counts=severity_counts,
            tp_count=len(tp_findings),
            critical_count=critical_count,
            high_count=high_count,
            generated_at=generated_at,
        )

        self._save_report(audit_id, content, "immunefi.md")

        log.info(
            "immunefi_report.generated",
            audit_id=audit_id,
            program=program,
            tp_count=len(tp_findings),
            critical_count=critical_count,
        )

        return content

    def _save_report(self, audit_id: str, content: str, filename: str) -> Path:
        """Persist the report to disk.

        Args:
            audit_id: Audit identifier used as the subdirectory name.
            content: Markdown content to write.
            filename: Report filename (``"immunefi.md"`` or ``"full.md"``).

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
    def _filter_true_positives(
        findings: list[Finding],
        exploit_results: list[ExploitResult] | None = None,
    ) -> list[Finding]:
        """Filter findings to only True Positives and sort by severity.

        NOW WITH EXPLOIT-AS-TRUTH:
        - Hanya finding yang terverifikasi exploit yang masuk ke laporan
        - Jika exploit_results tidak disediakan, fallback ke classification biasa

        Args:
            findings: All classified findings.
            exploit_results: Results from Exploit Service (optional).

        Returns:
            Filtered and sorted list of TP findings.
        """
        SEVERITY_ORDER = {
            "critical": 0,
            "high": 1,
            "medium": 2,
            "low": 3,
            "informational": 4,
            "info": 4,
        }

        # Build set of finding IDs that have successful exploit
        confirmed_ids: set[str] = set()
        if exploit_results:
            for er in exploit_results:
                if er.success:
                    confirmed_ids.add(er.finding_id)

        tp = []
        for f in findings:
            is_tp = f.classification.lower() in ("true_positive", "tp", "true positive")

            if is_tp:
                # Exploit-as-Truth filter:
                # If exploit results are available, only include confirmed ones
                if exploit_results:
                    if f.id in confirmed_ids:
                        tp.append(f)
                    else:
                        log.info(
                            "filter.excluded_no_exploit",
                            finding_id=f.id,
                            title=f.title,
                        )
                else:
                    # Fallback: no exploit data, trust classification
                    tp.append(f)

        tp.sort(key=lambda f: SEVERITY_ORDER.get(f.severity.lower(), 99))
        return tp

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
