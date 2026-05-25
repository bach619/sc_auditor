"""ClassifyBatchSkill — Batch analysis of low/medium findings.

Menggabungkan multiple findings dan memprosesnya bersama
untuk menghemat biaya LLM.
"""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class ClassifyBatchSkill(BaseSkill):
    """Batch analysis — memproses banyak finding bersama.

    Untuk low/medium/informational severity — lebih hemat
    diproses secara batch daripada satu per satu.
    """

    name = "classify_batch"
    description = "Batch analysis of multiple low/medium findings to classify TP/FP"
    category = "analysis"

    parameters = {
        "findings": {
            "type": "array",
            "required": True,
            "description": "List of finding objects to classify",
        },
        "source": {
            "type": "object",
            "required": True,
            "description": "Source code dictionary {filename: content}",
        },
        "compiler": {
            "type": "string",
            "required": False,
            "description": "Compiler version",
        },
        "contract_name": {
            "type": "string",
            "required": False,
            "description": "Contract name for context",
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
        contract_name: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        from src.models import Finding
        finding_objs = [Finding(**f) for f in findings]
        
        results = await self.analyzer.analyze_all(
            source=source,
            findings=finding_objs,
            compiler=compiler,
            contract_name=contract_name or "unknown",
        )

        return [
            r.model_dump() if hasattr(r, 'model_dump') else r
            for r in results
        ]
