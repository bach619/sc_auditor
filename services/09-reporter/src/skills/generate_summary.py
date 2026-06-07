"""GenerateSummarySkill — Generate executive summary from audit data."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class GenerateSummarySkill(BaseSkill):
    """Generate a concise executive summary of audit results."""

    name = "generate_summary"
    description = "Generate a concise executive summary with key findings, risk score, and recommendations"
    category = "reporting"

    parameters = {
        "audit_data": {
            "type": "object",
            "required": True,
            "description": "Audit data with findings summary",
        },
        "max_length": {
            "type": "integer",
            "required": False,
            "description": "Maximum summary length in characters",
        },
    }

    async def run(
        self, audit_data: dict[str, Any], max_length: int | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        findings = audit_data.get("findings", [])
        total = len(findings)
        critical = sum(1 for f in findings if isinstance(f, dict) and f.get("severity") == "critical")
        high = sum(1 for f in findings if isinstance(f, dict) and f.get("severity") == "high")
        medium = sum(1 for f in findings if isinstance(f, dict) and f.get("severity") == "medium")
        low = sum(1 for f in findings if isinstance(f, dict) and f.get("severity") == "low")

        summary_parts = [
            "# Executive Summary\n",
            f"**Total Findings:** {total}\n",
            f"**Critical:** {critical} | **High:** {high} | **Medium:** {medium} | **Low:** {low}\n",
        ]

        risk_score = (critical * 10 + high * 5 + medium * 2 + low * 0.5) / max(total, 1)
        summary_parts.append(f"**Risk Score:** {risk_score:.1f}/10\n")

        if critical > 0:
            summary_parts.append(f"\n**⚠️ {critical} critical vulnerabilities require immediate attention.**")

        summary = "\n".join(summary_parts)

        if max_length and len(summary) > max_length:
            summary = summary[:max_length] + "\n...(truncated)"

        return {
            "report_type": "executive_summary",
            "format": "markdown",
            "content": summary,
            "risk_score": round(risk_score, 1),
            "finding_counts": {
                "total": total,
                "critical": critical,
                "high": high,
                "medium": medium,
                "low": low,
            },
        }
