"""ExplainFindingSkill — AI-enhanced explanation of Mythril findings."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class ExplainFindingSkill(BaseSkill):
    """AI-enhanced explanation of Mythril analysis findings."""

    @property
    def name(self) -> str:
        return "explain_finding"

    @property
    def description(self) -> str:
        return (
            "Provide AI-enhanced explanation of Mythril findings. "
            "Describes the vulnerability, impact, exploit scenario, "
            "and recommended fix in natural language."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "finding": {
                    "type": "object",
                    "description": "Mythril finding object to explain",
                },
                "source_code": {
                    "type": "string",
                    "description": "Relevant source code snippet for context",
                },
                "language": {
                    "type": "string",
                    "description": "Output language (default: english)",
                },
            },
            "required": ["finding"],
        }

    @property
    def category(self) -> str:
        return "analysis"

    async def run(
        self,
        finding: dict[str, Any],
        source_code: str = "",
        language: str = "english",
        **kwargs: Any,
    ) -> dict[str, Any]:
        finding_type = finding.get("type", finding.get("issue", "unknown"))
        finding_desc = finding.get("description", finding.get("message", ""))
        severity = finding.get("severity", "medium")
        address = finding.get("address", finding.get("function", "unknown"))

        explanation_lines = [
            f"**Finding Type:** {finding_type}",
            f"**Severity:** {severity.upper()}",
            f"**Location:** {address}",
            "",
            "**Description:**",
            f"  {finding_desc}",
        ]

        if source_code:
            explanation_lines.extend([
                "",
                "**Affected Code:**",
                "  ```solidity",
                f"  {source_code[:2000]}",
                "  ```",
            ])

        severity_map = {
            "critical": "Immediate action required. This vulnerability can lead to loss of funds.",
            "high": "Should be fixed before deployment. High risk of exploitation.",
            "medium": "Address in next update. Moderate risk.",
            "low": "Informational. Follow best practices.",
            "informational": "No action needed. For awareness only.",
        }
        impact = severity_map.get(severity.lower(), "Evaluate based on context.")

        explanation_lines.extend([
            "",
            "**Potential Impact:**",
            f"  {impact}",
            "",
            "**Recommended Fix:**",
            self._generate_fix_suggestion(finding_type, finding_desc),
        ])

        return {
            "skill": "explain_finding",
            "finding_type": finding_type,
            "severity": severity,
            "location": address,
            "explanation": "\n".join(explanation_lines),
            "language": language,
        }

    def _generate_fix_suggestion(self, finding_type: str, description: str) -> str:
        desc_lower = description.lower()
        if "reentrancy" in desc_lower or finding_type == "reentrancy":
            return "Apply checks-effects-interactions pattern. Use reentrancy guard (OpenZeppelin)."
        if "overflow" in desc_lower or "underflow" in desc_lower:
            return "Use Solidity >= 0.8 for built-in overflow protection, or SafeMath library."
        if "unchecked" in desc_lower:
            return "Verify unchecked blocks are intentional. Add input validation."
        if "access" in desc_lower or "owner" in desc_lower:
            return "Implement proper access control (Ownable, RBAC). Review onlyOwner modifiers."
        if "tx.origin" in desc_lower:
            return "Replace tx.origin with msg.sender for authentication."
        if "delegatecall" in desc_lower:
            return "Ensure delegatecall target is trusted. Never delegatecall to user-supplied address."
        return (
            "Review the finding details and apply standard security best practices. "
            "Consult relevant SWC registry entry for specific remediation steps."
        )
