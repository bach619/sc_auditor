"""GenerateFixSkill — Generate code fix recommendations for confirmed vulnerabilities.
"""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class GenerateFixSkill(BaseSkill):
    """Generate suggested code fix untuk vulnerability.

    Menggunakan LLM untuk menghasilkan perbaikan kode
    berdasarkan source code dan finding.
    """

    name = "generate_fix"
    description = "Generate code fix recommendation for a confirmed vulnerability using LLM"
    category = "fix"

    parameters = {
        "source": {
            "type": "object",
            "required": True,
            "description": "Source code dictionary {filename: content}",
        },
        "finding": {
            "type": "object",
            "required": True,
            "description": "Finding object with vulnerability details",
        },
        "compiler": {
            "type": "string",
            "required": False,
            "description": "Compiler version",
        },
    }

    def __init__(self, llm_client: Any) -> None:
        super().__init__()
        self.llm = llm_client

    async def run(
        self,
        source: dict[str, str],
        finding: dict[str, Any],
        compiler: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        # Build full source text
        if isinstance(source, dict):
            full_source = "\n\n".join(
                f"// File: {name}\n{content}"
                for name, content in source.items()
            )
        else:
            full_source = str(source)

        from src.models import Finding
        finding_obj = Finding(**finding)

        from src.fixer import FixSuggester
        fixer = FixSuggester(llm=self.llm)

        suggestion = await fixer.suggest_fix(
            source_code=full_source,
            finding=finding_obj,
            compiler=compiler,
        )

        return {
            "fix": suggestion.model_dump() if hasattr(suggestion, 'model_dump') else suggestion,
            "finding_id": finding.get("id"),
        }
