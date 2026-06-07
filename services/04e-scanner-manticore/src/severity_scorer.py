"""Severity scorer for Manticore findings.

Transforms raw detector findings into severity-scored results.
Only HIGH and CRITICAL findings are surfaced; others are filtered.

Scoring logic:
  - CRITICAL: Direct fund loss, contract compromise, arbitrary code execution
  - HIGH: State manipulation leading to potential fund loss
  - MEDIUM: State inconsistency without direct exploit path (filtered)
  - LOW: Informational (filtered)

Additional scoring factors:
  - Exploit path confirmed? (concrete transaction data)
  - Is the vulnerability reachable? (symbolic path exists)
  - Preconditions required? (flash loan, specific caller)
"""

from __future__ import annotations

from typing import Any


class SeverityScorer:
    """Scores and filters Manticore findings by severity.

    Only HIGH and CRITICAL findings are returned by default.
    """

    # Weights for confidence calculation
    WEIGHTS = {
        "has_proof_path": 0.30,
        "confirmed_by_symbolic": 0.25,
        "fund_movement_involved": 0.20,
        "reachable_without_special_prereq": 0.15,
        "state_change_direct": 0.10,
    }

    @staticmethod
    def score_finding(finding: dict[str, Any]) -> dict[str, Any]:
        """Score a raw finding and determine final severity.

        Returns the finding with added:
          - score: 0.0 - 1.0 confidence score
          - severity: 'critical' or 'high'
          - reasoning: why this score was assigned
        """
        finding.get("severity", "high")
        metadata = finding.get("metadata", {})
        proof = finding.get("proof", {})

        score_components: dict[str, float] = {}
        total_score = 0.0

        # 1. Has concrete proof path?
        has_proof = bool(proof.get("calldata") or proof.get("tx_count", 0) > 0)
        score_components["has_proof_path"] = 1.0 if has_proof else 0.3

        # 2. Fund movement involved?
        fund_movement = metadata.get("effects", {}).get("value_transferred", False) or \
                        metadata.get("profit_extracted", False)
        score_components["fund_movement_involved"] = 1.0 if fund_movement else 0.5

        # 3. Reachable from any caller?
        anyone_can_call = not metadata.get("caller_dependent", True)
        score_components["reachable_without_special_prereq"] = 1.0 if anyone_can_call else 0.6

        # 4. Direct state modification?
        state_change = metadata.get("effects", {}).get("state_modified", False) or \
                       metadata.get("storage_collision_potential", False)
        score_components["state_change_direct"] = 1.0 if state_change else 0.4

        # 5. Confirmed by symbolic execution
        confirmed = finding.get("confidence", 0.5)
        score_components["confirmed_by_symbolic"] = confirmed

        # Calculate weighted score
        for key, weight in SeverityScorer.WEIGHTS.items():
            component_score = score_components.get(key, 0.5)
            total_score += component_score * weight

        # Determine final severity
        if total_score >= 0.75:
            final_severity = "critical"
        elif total_score >= 0.50:
            final_severity = "high"
        else:
            final_severity = "medium"

        finding["score"] = round(total_score, 3)
        finding["severity"] = final_severity
        finding["score_components"] = score_components
        finding["reasoning"] = SeverityScorer._build_reasoning(
            final_severity, total_score, score_components, finding
        )

        return finding

    @staticmethod
    def _build_reasoning(
        severity: str, score: float, components: dict[str, float], finding: dict[str, Any]
    ) -> str:
        """Build human-readable reasoning for the severity assignment."""
        reasons: list[str] = []

        if components.get("has_proof_path", 0) > 0.5:
            reasons.append("exploit path confirmed")
        if components.get("fund_movement_involved", 0) > 0.5:
            reasons.append("fund movement involved")
        if components.get("confirmed_by_symbolic", 0) > 0.7:
            reasons.append("high symbolic confidence")
        if components.get("reachable_without_special_prereq", 0) > 0.5:
            reasons.append("exploitable by any caller")
        if components.get("state_change_direct", 0) > 0.5:
            reasons.append("direct state modification")

        if not reasons:
            reasons.append("potential vulnerability detected")

        reasoning = f"Severity {severity.upper()} (score: {score:.2f}): {', '.join(reasons)}."
        return reasoning

    @staticmethod
    def filter_high_critical(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter findings to only HIGH and CRITICAL."""
        scored = [SeverityScorer.score_finding(f) for f in findings]
        return [
            f for f in scored
            if f.get("severity") in ("high", "critical")
        ]

    @staticmethod
    def aggregate_summary(
        findings: list[dict[str, Any]],
        slither_findings: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Aggregate findings into a summary report."""
        critical = [f for f in findings if f.get("severity") == "critical"]
        high = [f for f in findings if f.get("severity") == "high"]

        summary: dict[str, Any] = {
            "total_findings": len(findings),
            "critical_count": len(critical),
            "high_count": len(high),
            "critical_findings": critical,
            "high_findings": high,
            "confirmed_from_slither": 0,
            "new_findings": 0,
            "avg_confidence": 0.0,
        }

        if findings:
            summary["avg_confidence"] = round(
                sum(f.get("score", 0) for f in findings) / len(findings), 3
            )

        # Cross-reference with Slither if available
        if slither_findings:
            manticore_bug_types = {f.get("bug_type") for f in findings}
            slither_bug_types = {f.get("check") or f.get("bug_type") for f in slither_findings}

            confirmed = len(manticore_bug_types & slither_bug_types)
            new = len(manticore_bug_types - slither_bug_types)

            summary["confirmed_from_slither"] = confirmed
            summary["new_findings"] = new

        return summary
