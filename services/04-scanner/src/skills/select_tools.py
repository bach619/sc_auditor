"""SelectToolsSkill — Intelligent tool selection based on contract analysis.

Menganalisis source code dan memilih tools terbaik:
- Slither: selalu dijalankan (paling cepat)
- Mythril: untuk kontrak > 500 baris
- Echidna: jika ada delegatecall/selfdestruct
- Halmos: untuk symbolic execution
"""

from __future__ import annotations

from typing import Any
from shared.skills.base_skill import BaseSkill


class SelectToolsSkill(BaseSkill):
    name = "select_tools"
    description = "Analyze contract complexity and select optimal scanning tools"
    category = "intelligence"

    parameters = {
        "sources": {"type": "object", "required": True, "description": "Source code to analyze"},
    }

    async def run(self, sources: dict[str, str], **kwargs: Any) -> dict[str, Any]:
        tools = ["slither"]
        reasoning = ["slither: fastest, catches common issues"]

        total_lines = sum(
            len(s.split("\n")) for s in sources.values()
        ) if isinstance(sources, dict) else 0

        if total_lines > 500:
            tools.append("mythril")
            reasoning.append(f"mythril: large contract ({total_lines} lines)")

        source_text = "\n".join(sources.values()) if isinstance(sources, dict) else str(sources)
        if "delegatecall" in source_text or "selfdestruct" in source_text:
            tools.append("echidna")
            reasoning.append("echidna: delegatecall/selfdestruct detected")

        return {
            "tools": tools,
            "reasoning": reasoning,
            "total_lines": total_lines,
        }
