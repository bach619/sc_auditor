"""ClassifySingleSkill — Deep analysis of one finding via LLM.

Untuk critical/high severity findings — analisis satu per satu
dengan full source trace untuk akurasi maksimal.
"""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class ClassifySingleSkill(BaseSkill):
    """Analisis satu finding secara mendalam dengan LLM.

    Memanggil analyzer.analyze_single() untuk menentukan
    apakah finding adalah True Positive atau False Positive.
    """

    name = "classify_single"
    description = "Deep analysis of a single finding to determine True/False Positive using LLM"
    category = "analysis"

    parameters = {
        "finding": {
            "type": "object",
            "required": True,
            "description": "Finding object with id, severity, title, description",
        },
        "source": {
            "type": "object",
            "required": True,
            "description": "Source code dictionary {filename: content}",
        },
        "compiler": {
            "type": "string",
            "required": False,
            "description": "Compiler version (e.g. 0.8.20)",
        },
    }

    def __init__(self, analyzer: Any) -> None:
        super().__init__()
        self.analyzer = analyzer

    async def run(
        self,
        finding: dict[str, Any],
        source: dict[str, str],
        compiler: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        from src.models import Finding
        finding_obj = Finding(**finding)
        
        result = await self.analyzer.analyze_single(
            source=source,
            finding=finding_obj,
            compiler=compiler,
        )

        return result.model_dump() if hasattr(result, 'model_dump') else result
