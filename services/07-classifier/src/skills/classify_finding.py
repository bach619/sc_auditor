"""ClassifyFindingSkill — classify finding as TP/FP/FP-TN."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class ClassifyFindingSkill(BaseSkill):
    """Classify a single finding as true positive (TP), false positive (FP), or FP with true negative explanation (FP-TN)."""

    @property
    def name(self) -> str:
        return "classify_finding"

    @property
    def description(self) -> str:
        return (
            "Classify a security finding as TP (True Positive), FP (False Positive), "
            "or FP-TN (False Positive — True Negative with explanation). "
            "Uses the existing Classifier from the service."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "finding": {
                    "type": "object",
                    "description": "Finding object with type, description, severity, location",
                },
                "context": {
                    "type": "object",
                    "description": "Additional context (source code, tool name, etc.)",
                },
            },
            "required": ["finding"],
        }

    @property
    def category(self) -> str:
        return "classification"

    async def run(
        self,
        finding: dict[str, Any],
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        from ..classify import Classifier

        classifier = Classifier()
        result = await classifier.classify(finding)

        return {
            "skill": "classify_finding",
            "finding_id": finding.get("id", finding.get("address", "unknown")),
            "finding_type": finding.get("type", "unknown"),
            "classification": result.get("classification", result.get("label", "unknown")),
            "confidence": result.get("confidence", 0.0),
            "reason": result.get("reason", result.get("explanation", "")),
            "details": result,
        }
