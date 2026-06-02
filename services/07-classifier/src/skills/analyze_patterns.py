"""AnalyzePatternsSkill — pattern learning from classifications."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class AnalyzePatternsSkill(BaseSkill):
    """Analyze classification patterns to learn and improve future classifications."""

    @property
    def name(self) -> str:
        return "analyze_patterns"

    @property
    def description(self) -> str:
        return (
            "Analyze historical classification results to detect patterns, "
            "identify systematic misclassifications, and suggest improvements "
            "to the classifier model or rules."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "classifications": {
                    "type": "array",
                    "description": "List of past classification results to analyze",
                },
                "min_confidence": {
                    "type": "number",
                    "description": "Minimum confidence threshold for inclusion (0.0 - 1.0)",
                },
            },
            "required": ["classifications"],
        }

    @property
    def category(self) -> str:
        return "classification"

    async def run(
        self,
        classifications: list[dict[str, Any]],
        min_confidence: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        total = len(classifications)
        if total == 0:
            return {"skill": "analyze_patterns", "total": 0, "patterns": [], "message": "No classifications to analyze"}

        filtered = [c for c in classifications if c.get("confidence", 1.0) >= min_confidence]
        tp_count = sum(1 for c in filtered if c.get("classification", "").upper() == "TP")
        fp_count = sum(1 for c in filtered if c.get("classification", "").upper() == "FP")
        fptn_count = sum(1 for c in filtered if c.get("classification", "").upper() == "FP-TN")

        from collections import Counter
        type_counter: Counter[str] = Counter()
        for c in filtered:
            ft = c.get("finding_type", c.get("finding", {}).get("type", "unknown"))
            type_counter[ft] += 1

        patterns = []
        for finding_type, count in type_counter.most_common(5):
            type_classifications = [c for c in filtered if c.get("finding_type", c.get("finding", {}).get("type", "")) == finding_type]
            tp_in_type = sum(1 for c in type_classifications if c.get("classification", "").upper() == "TP")
            fp_in_type = sum(1 for c in type_classifications if c.get("classification", "").upper() != "TP")
            rate = tp_in_type / len(type_classifications) if type_classifications else 0
            patterns.append({
                "finding_type": finding_type,
                "total": len(type_classifications),
                "tp_count": tp_in_type,
                "fp_count": fp_in_type,
                "tp_rate": round(rate, 3),
                "suggestion": self._suggest_for_type(finding_type, rate),
            })

        return {
            "skill": "analyze_patterns",
            "total_classifications": total,
            "filtered_count": len(filtered),
            "tp_count": tp_count,
            "fp_count": fp_count,
            "fptn_count": fptn_count,
            "patterns": patterns,
            "dominant_classification": "TP" if tp_count > fp_count else "FP",
        }

    def _suggest_for_type(self, finding_type: str, tp_rate: float) -> str:
        if tp_rate >= 0.9:
            return f"High confidence for {finding_type} — classifier performing well"
        if tp_rate >= 0.7:
            return f"Good accuracy for {finding_type} — minor tuning may help"
        if tp_rate >= 0.5:
            return f"Moderate accuracy for {finding_type} — review FP cases and update rules"
        return f"Low accuracy for {finding_type} — consider retraining with more TP examples"
