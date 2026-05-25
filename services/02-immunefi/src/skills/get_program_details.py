"""GetProgramDetailsSkill — Full program details with intelligence."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class GetProgramDetailsSkill(BaseSkill):
    """Get comprehensive program details including intelligence scores, contracts, and competition."""

    name = "get_program_details"
    description = "Get full program details with intelligence score, contracts, and competition analysis"
    category = "intelligence"

    parameters = {
        "slug": {"type": "string", "required": True, "description": "Program slug identifier"},
        "include_intel": {"type": "boolean", "required": False, "description": "Include intelligence scores"},
    }

    def __init__(self, storage_service: Any, scorer: Any) -> None:
        super().__init__()
        self._storage = storage_service
        self._scorer = scorer

    async def run(
        self, slug: str, include_intel: bool = True, **kwargs: Any
    ) -> dict[str, Any]:
        program = await self._storage.get_program(slug)
        if not program:
            return {"error": f"Program '{slug}' not found"}

        result = {"program": program if isinstance(program, dict) else {"slug": slug}}

        if include_intel:
            score = await self._scorer.score(slug)
            result["intel_score"] = score if isinstance(score, dict) else {"score": 0}

        contracts = await self._storage.get_contracts(slug)
        result["contracts"] = contracts if isinstance(contracts, list) else []

        return result
