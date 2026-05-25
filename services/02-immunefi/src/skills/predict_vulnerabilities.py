"""PredictVulnerabilitiesSkill — ML-based vulnerability prediction."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class PredictVulnerabilitiesSkill(BaseSkill):
    """Predict likely vulnerability types for a program based on ML analysis."""

    name = "predict_vulnerabilities"
    description = "Predict likely vulnerability types and exploit vectors for a program's smart contracts"
    category = "prediction"

    parameters = {
        "slug": {"type": "string", "required": True, "description": "Program slug"},
    }

    def __init__(self, predictor_service: Any) -> None:
        super().__init__()
        self._predictor = predictor_service

    async def run(self, slug: str, **kwargs: Any) -> dict[str, Any]:
        prediction = await self._predictor.predict(slug)
        return prediction if isinstance(prediction, dict) else {"result": str(prediction)}
