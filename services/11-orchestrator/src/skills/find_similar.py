"""FindSimilarSkill — Find similar contracts by fingerprint."""

from __future__ import annotations

from typing import Any
from shared.skills.base_skill import BaseSkill


class FindSimilarSkill(BaseSkill):
    name = "find_similar"
    description = "Find similar contracts by structural fingerprint for cross-reference analysis"
    category = "analysis"

    parameters = {
        "contract_id": {"type": "string", "required": True, "description": "Contract ID to find similar"},
        "limit": {"type": "integer", "required": False, "description": "Max similar contracts to return"},
    }

    def __init__(self, similarity: Any) -> None:
        super().__init__()
        self._similarity = similarity

    async def run(self, contract_id: str, limit: int = 10, **kwargs: Any) -> dict[str, Any]:
        results = await self._similarity.find_similar(contract_id=contract_id, limit=limit)
        return {
            "contract_id": contract_id,
            "similar": results if isinstance(results, list) else [],
            "count": len(results) if isinstance(results, list) else 0,
        }
