"""GenerateImmunefiReportSkill — Generate Immunefi-ready submission report."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill

from src.models import Finding


class GenerateImmunefiReportSkill(BaseSkill):
    """Generate audit report in Immunefi submission format."""

    name = "generate_immunefi_report"
    description = "Generate an Immunefi-ready audit report for bug bounty submission"
    category = "reporting"

    parameters = {
        "audit_data": {
            "type": "object",
            "required": True,
            "description": "Audit data formatted for Immunefi submission",
        },
    }

    async def run(self, audit_data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        from src.immunefi import ImmunefiReportGenerator

        generator = ImmunefiReportGenerator()

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
            exploit_results=audit_data.get("exploit_results"),
        )

        return {
            "report_type": "immunefi",
            "format": "markdown",
            "content": report_md,
            "length": len(report_md),
        }
