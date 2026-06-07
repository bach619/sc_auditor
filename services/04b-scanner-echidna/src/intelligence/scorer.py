"""Echidna Fuzzing Scorer — L4 Intelligence.

Scoring fuzzing findings berdasarkan:
1. Reproducibility — apakah failure dapat direproduksi? berapa kali?
2. Call sequence complexity — complexity of the call sequence that triggered it
3. Fund movement — apakah ETH/token terlibat dalam sequence?
4. Category severity — severity dari FailureCategory
5. Fuzzing health score — overall fuzzing campaign health
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FailureScore:
    """Skor untuk satu finding fuzzing."""

    finding_title: str
    test_function: str
    category: str
    severity: str

    # Faktor (0.0 – 1.0)
    reproducibility: float = 0.5
    sequence_complexity: float = 0.5
    fund_movement: float = 0.0
    category_weight: float = 0.5

    # Skor (0–100)
    raw_score: float = 0.0
    normalized_score: float = 0.0

    # Label
    risk_label: str = "medium"
    priority: int = 3


SEVERITY_WEIGHTS: dict[str, float] = {
    "critical": 1.0,
    "high": 0.8,
    "medium": 0.5,
    "low": 0.3,
    "informational": 0.1,
}

# Keywords dalam call sequence yang menandakan fund movement
FUND_KEYWORDS: list[str] = [
    "transfer", "send", "call", "delegatecall",
    "0x", "value", "amount", "eth", "ether",
    "token", "balance", "withdraw", "deposit",
]


class EchidnaScorer:
    """Compute scores for fuzzing findings."""

    def score_finding(
        self,
        finding: dict[str, Any],
    ) -> FailureScore:
        """Score a single fuzzing finding.

        Args:
            finding: Finding dict dengan minimal 'title', 'test_function',
                     'failing_input', 'failure_severity'.

        Returns:
            FailureScore dataclass.
        """
        title = finding.get("title", "")
        test_fn = finding.get("test_function", "")
        category = finding.get("failure_category", "unknown")
        severity = finding.get("failure_severity", finding.get("severity", "medium"))
        call_seq = finding.get("failing_input", "") or ""

        severity = severity.lower()

        # 1. Reproducibility
        # Jika ada call sequence terperinci → high reproducibility
        # Jika hanya "assertion failed" → medium
        # Jika ambiguous → low
        if call_seq and len(call_seq) > 50:
            reproducibility = 0.9
        elif call_seq:
            reproducibility = 0.6
        else:
            reproducibility = 0.3

        # 2. Sequence complexity
        # Hitung jumlah langkah dalam call sequence
        if call_seq:
            steps = call_seq.count("\n") + 1
            sequence_complexity = min(1.0, steps / 10)
        else:
            sequence_complexity = 0.3

        # 3. Fund movement
        combined = call_seq.lower() + title.lower() + test_fn.lower()
        fund_hits = sum(1 for kw in FUND_KEYWORDS if kw in combined)
        fund_movement = min(1.0, fund_hits / 5)

        # 4. Category weight
        category_weight = SEVERITY_WEIGHTS.get(severity, 0.5)

        # 5. Raw score
        raw_score = (
            reproducibility * 40
            + sequence_complexity * 20
            + fund_movement * 25
            + category_weight * 15
        )

        # Normalize to 0–100
        normalized_score = max(0, min(100, raw_score))

        # Determine label and priority
        if normalized_score >= 80:
            risk_label, priority = "critical", 1
        elif normalized_score >= 60:
            risk_label, priority = "high", 2
        elif normalized_score >= 35:
            risk_label, priority = "medium", 3
        elif normalized_score >= 15:
            risk_label, priority = "low", 4
        else:
            risk_label, priority = "info", 5

        return FailureScore(
            finding_title=title,
            test_function=test_fn,
            category=category,
            severity=severity,
            reproducibility=round(reproducibility, 3),
            sequence_complexity=round(sequence_complexity, 3),
            fund_movement=round(fund_movement, 3),
            category_weight=round(category_weight, 3),
            raw_score=round(raw_score, 2),
            normalized_score=round(normalized_score, 2),
            risk_label=risk_label,
            priority=priority,
        )

    def score_findings(
        self,
        findings: list[dict[str, Any]],
    ) -> list[FailureScore]:
        scores = [self.score_finding(f) for f in findings]
        scores.sort(key=lambda s: s.normalized_score, reverse=True)
        return scores

    def compute_aggregate(
        self,
        scores: list[FailureScore],
    ) -> dict[str, Any]:
        """Compute fuzzing campaign health."""
        if not scores:
            return {
                "overall_score": 0,
                "overall_label": "none",
                "total_failures": 0,
                "health": "unknown",
            }

        top_3 = scores[:3]
        weights = [3, 2, 1][:len(top_3)]
        overall = sum(s.normalized_score * w for s, w in zip(top_3, weights)) / sum(weights)

        critical = sum(1 for s in scores if s.risk_label == "critical")
        high = sum(1 for s in scores if s.risk_label == "high")

        if critical > 0:
            health = "critical"
        elif high > 1:
            health = "poor"
        elif overall < 30:
            health = "good"
        else:
            health = "fair"

        return {
            "overall_score": round(overall, 2),
            "overall_label": "critical" if critical > 0 else "high" if health == "poor" else "medium",
            "total_failures": len(scores),
            "critical_count": critical,
            "high_count": high,
            "health": health,
            "top_failures": [
                {
                    "title": s.finding_title,
                    "function": s.test_function,
                    "score": s.normalized_score,
                    "label": s.risk_label,
                }
                for s in scores[:3]
            ],
        }


def create_scorer() -> EchidnaScorer:
    return EchidnaScorer()
