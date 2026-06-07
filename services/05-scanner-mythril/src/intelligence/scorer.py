"""Mythril Composite Scorer — L4 Intelligence.

Scoring berdasarkan:
1. SWC severity
2. Function context (critical function? admin? public?)
3. Exploitability path (Mythril output)
4. Business impact (kategori SWC)
"""

from __future__ import annotations

from typing import Any

SEVERITY_BASE: dict[str, float] = {
    "critical": 90.0,
    "high": 65.0,
    "medium": 40.0,
    "low": 20.0,
    "informational": 5.0,
}

# Kategori dengan business impact tinggi
HIGH_IMPACT_CATEGORIES: set[str] = {
    "reentrancy", "access_control", "arithmetic",
    "low_level", "oracle",
}

FUNCTIONS_HIGH_RISK: list[str] = [
    "withdraw", "transfer", "send", "call", "delegatecall",
    "mint", "burn", "destroy", "selfdestruct", "kill",
    "setOwner", "changeOwner", "updateAdmin",
    "upgradeTo", "upgrade",
]


class MythrilScorer:
    """Score Mythril findings."""

    def score_finding(
        self,
        finding: dict[str, Any],
    ) -> dict[str, Any]:
        """Score single finding."""
        severity = finding.get("severity", "medium").lower()
        category = finding.get("category", "unknown")
        function = finding.get("function", "") or ""
        swc_id = finding.get("swc_id", "unknown")

        base = SEVERITY_BASE.get(severity, 40.0)

        # Business impact boost
        impact_boost = 1.3 if category in HIGH_IMPACT_CATEGORIES else 1.0

        # Function context boost
        fn_boost = 1.0
        for high_risk_fn in FUNCTIONS_HIGH_RISK:
            if high_risk_fn.lower() in function.lower():
                fn_boost = 1.5
                break

        # Adjusted score
        adjusted = base * impact_boost * fn_boost
        adjusted = max(0, min(100, adjusted))

        # Label
        if adjusted >= 80:
            label, priority = "critical", 1
        elif adjusted >= 60:
            label, priority = "high", 2
        elif adjusted >= 35:
            label, priority = "medium", 3
        elif adjusted >= 15:
            label, priority = "low", 4
        else:
            label, priority = "info", 5

        rec = self._recommendation(category, severity, adjusted)

        return {
            "title": finding.get("title", ""),
            "swc_id": swc_id,
            "severity": severity,
            "base_score": base,
            "impact_boost": impact_boost,
            "fn_boost": fn_boost,
            "adjusted_score": round(adjusted, 2),
            "risk_label": label,
            "priority": priority,
            "recommendation": rec,
        }

    def score_findings(
        self,
        findings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        scores = [self.score_finding(f) for f in findings]
        scores.sort(key=lambda s: s["adjusted_score"], reverse=True)
        return scores

    def compute_aggregate(self, scores: list[dict[str, Any]]) -> dict[str, Any]:
        if not scores:
            return {"overall_score": 0, "overall_label": "none", "total": 0}

        top3 = scores[:3]
        weights = [3, 2, 1][:len(top3)]
        overall = sum(s["adjusted_score"] * w for s, w in zip(top3, weights)) / sum(weights)

        return {
            "overall_score": round(overall, 2),
            "overall_label": self._label(overall),
            "total": len(scores),
            "critical_count": sum(1 for s in scores if s["risk_label"] == "critical"),
            "high_count": sum(1 for s in scores if s["risk_label"] == "high"),
            "top_findings": [
                {"title": s["title"], "swc_id": s["swc_id"], "score": s["adjusted_score"]}
                for s in scores[:5]
            ],
        }

    @staticmethod
    def _label(score: float) -> str:
        if score >= 80:
            return "critical"
        if score >= 60:
            return "high"
        if score >= 35:
            return "medium"
        if score >= 15:
            return "low"
        return "info"

    @staticmethod
    def _recommendation(category: str, severity: str, score: float) -> str:
        if score >= 80:
            return f"CRITICAL: {category} — immediate action required. This vulnerability is highly exploitable."
        if score >= 60:
            return f"HIGH: {category} — address in next update. Could be chained with other issues."
        if score >= 35:
            return f"MEDIUM: {category} — review recommended based on business context."
        return f"LOW: {category} — best practice improvement, address if feasible."


def create_scorer() -> MythrilScorer:
    return MythrilScorer()
