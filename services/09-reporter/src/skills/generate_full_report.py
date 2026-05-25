"""GenerateFullReportSkill — Generate comprehensive audit report."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill

from src.models import Finding


class GenerateFullReportSkill(BaseSkill):
    """Generate full comprehensive audit report in Markdown format."""

    name = "generate_full_report"
    description = "Generate a comprehensive full audit report with all findings, analysis, and recommendations"
    category = "reporting"

    parameters = {
        "audit_data": {
            "type": "object",
            "required": True,
            "description": "Complete audit data with findings, analysis, and metadata",
        },
    }

    async def run(self, audit_data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        from src.full import FullReportGenerator

        generator = FullReportGenerator()

        findings_raw = audit_data.get("findings", [])
        findings = [
            Finding(**f) if isinstance(f, dict) else f for f in findings_raw
        ]

        report_md = generator.generate(
            audit_id=audit_data.get("audit_id", ""),
            program=audit_data.get("program", ""),
            chain=audit_data.get("chain", ""),
            address=audit_data.get("address", ""),
            findings=findings,
            metrics=audit_data.get("metrics"),
            exploit_results=audit_data.get("exploit_results"),
            source_info=audit_data.get("source_info"),
        )

        return {
            "report_type": "full",
            "format": "markdown",
            "content": report_md,
            "length": len(report_md),
        }
