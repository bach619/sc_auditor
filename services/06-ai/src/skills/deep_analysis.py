"""DeepAnalysisSkill — Full deep dive with exploit path verification.
"""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class DeepAnalysisSkill(BaseSkill):
    """Deep analysis — full source trace dan exploit path verification.

    Untuk temuan yang membutuhkan investigasi mendalam:
    - Source code trace
    - Exploit path analysis
    - Impact assessment
    """

    name = "deep_analysis"
    description = "Deep dive analysis with full source code trace and exploit path verification"
    category = "analysis"

    parameters = {
        "findings": {
            "type": "array",
            "required": True,
            "description": "List of findings for deep analysis",
        },
        "source": {
            "type": "object",
            "required": True,
            "description": "Source code dictionary",
        },
        "compiler": {
            "type": "string",
            "required": False,
            "description": "Compiler version",
        },
    }

    def __init__(self, analyzer: Any) -> None:
        super().__init__()
        self.analyzer = analyzer

    async def run(
        self,
        findings: list[dict[str, Any]],
        source: dict[str, str],
        compiler: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        from src.models import Finding
        
        results = []
        for finding in findings:
            finding_obj = Finding(**finding)
            result = await self.analyzer.analyze_single(
                source=source,
                finding=finding_obj,
                compiler=compiler,
            )
            results.append(
                result.model_dump() if hasattr(result, 'model_dump') else result
            )

        return {
            "findings": results,
            "_type": "deep",
        }
