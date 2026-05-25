"""MergeFindingsSkill — Merge and deduplicate findings from multiple tools."""

from __future__ import annotations

from typing import Any
from shared.skills.base_skill import BaseSkill


class MergeFindingsSkill(BaseSkill):
    name = "merge_findings"
    description = "Merge and deduplicate findings from multiple scanning tools"
    category = "processing"

    parameters = {
        "tool_outputs": {"type": "object", "required": True, "description": "Dict of {tool_name: {findings: [...]}}"},
        "tools_run": {"type": "array", "required": True, "description": "List of tools that were run"},
        "reasoning": {"type": "array", "required": False, "description": "Tool selection reasoning"},
    }

    async def run(
        self,
        tool_outputs: dict[str, Any],
        tools_run: list[str],
        reasoning: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        all_findings = []
        for tool_name, output in tool_outputs.items():
            if isinstance(output, dict) and output.get("success", False):
                tool_findings = output.get("findings", [])
                for f in tool_findings:
                    if isinstance(f, dict):
                        f["_source_tool"] = tool_name
                all_findings.extend(tool_findings)

        seen_titles = set()
        unique_findings = []
        for f in all_findings:
            title = (f.get("title") or f.get("name", "")).lower() if isinstance(f, dict) else ""
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_findings.append(f)

        return {
            "findings": unique_findings,
            "tools_run": tools_run,
            "reasoning": reasoning or [],
            "summary": (
                f"Ran {len(tools_run)} tools: {', '.join(tools_run)}. "
                f"Found {len(unique_findings)} unique findings (from {len(all_findings)} raw)."
            ),
        }
