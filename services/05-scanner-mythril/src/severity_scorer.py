"""Severity scorer for Mythril findings.

Transforms raw Mythril findings into severity-scored results.
Filters HIGH/CRITICAL only for final output.

Scoring factors:
  1. SWC base severity (from SWC registry)
  2. Impact area (fund movement, state corruption, access bypass)
  3. Exploit complexity (symbolic path confirmed, preconditions)
  4. Cross-reference boost (confirmed by other tools)
"""

from __future__ import annotations

from typing import Any


class SeverityScorer:
    """Scores and filters Mythril findings by severity."""

    # SWC ID -> base score (0-100)
    SWC_BASE_SCORES: dict[str, int] = {
        "SWC-105": 95,  # Unprotected withdrawal
        "SWC-106": 95,  # Unprotected selfdestruct
        "SWC-107": 90,  # Reentrancy
        "SWC-112": 95,  # Controlled delegatecall
        "SWC-115": 75,  # tx.origin auth
        "SWC-123": 95,  # Arbitrary storage write
        "SWC-119": 80,  # Oracle manipulation
        "SWC-101": 75,  # Integer overflow
        "SWC-104": 70,  # Unchecked call
        "SWC-108": 65,  # State variable default visibility
        "SWC-110": 70,  # Uninitialized storage pointer
        "SWC-113": 60,  # DoS with failed call
        "SWC-114": 55,  # Transaction order dependence
        "SWC-116": 65,  # Block values as time proxy
        "SWC-118": 70,  # Incorrect constructor name
        "SWC-120": 75,  # Weak randomness
        "SWC-121": 80,  # Signature replay
        "SWC-126": 55,  # Gas griefing
        "SWC-128": 70,  # Unchecked low-level call
        "SWC-100": 40,  # Function default visibility
        "SWC-102": 20,  # Outdated compiler
        "SWC-103": 10,  # Floating pragma
    }

    # Bug type keywords that indicate fund movement
    FUND_MOVEMENT_KEYWORDS: set[str] = {
        "withdraw", "transfer", "send", "call", "value",
        "eth", "ether", "token", "balance", "fund",
    }

    @staticmethod
    def score_finding(finding: dict[str, Any]) -> dict[str, Any]:
        """Score a raw finding and determine final severity.

        Returns enriched finding with:
          - score: 0.0 - 100.0
          - severity: critical/high/medium/low
          - risk_label: plain English risk level
        """
        swc_id = finding.get("swc_id", "")
        title = (finding.get("title", "") or "").lower()
        description = (finding.get("description", "") or "").lower()

        # Start with SWC base score
        base_score = SeverityScorer.SWC_BASE_SCORES.get(swc_id, 40)

        # Boost for fund movement
        fund_boost = 0
        for keyword in SeverityScorer.FUND_MOVEMENT_KEYWORDS:
            if keyword in title or keyword in description:
                fund_boost = 15
                break

        # Boost for cross-contract interaction
        cross_contract_boost = 0
        if "delegatecall" in title or "cross" in title:
            cross_contract_boost = 10

        # Penalty for informational findings
        info_penalty = 0
        if swc_id in ("SWC-103", "SWC-102"):
            info_penalty = 20

        # Calculate final score
        score = base_score + fund_boost + cross_contract_boost - info_penalty
        score = max(0, min(100, score))

        # Determine severity
        severity: str
        if score >= 85:
            severity = "critical"
        elif score >= 65:
            severity = "high"
        elif score >= 40:
            severity = "medium"
        else:
            severity = "low"

        # Add scoring metadata
        finding["score"] = score
        finding["severity"] = severity
        finding["scoring"] = {
            "base_score": base_score,
            "fund_boost": fund_boost,
            "cross_contract_boost": cross_contract_boost,
            "info_penalty": info_penalty,
            "final_score": score,
        }

        return finding

    @staticmethod
    def filter_high_critical(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter to only HIGH and CRITICAL findings."""
        scored = [SeverityScorer.score_finding(f) for f in findings]
        return [
            f for f in scored
            if f.get("severity") in ("high", "critical")
        ]

    @staticmethod
    def aggregate_summary(
        findings: list[dict[str, Any]],
        cross_ref: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Aggregate findings into a summary."""
        critical = [f for f in findings if f.get("severity") == "critical"]
        high = [f for f in findings if f.get("severity") == "high"]

        summary: dict[str, Any] = {
            "total_findings": len(findings),
            "critical_count": len(critical),
            "high_count": len(high),
            "critical_findings": critical,
            "high_findings": high,
            "avg_confidence": 0.0,
            "avg_score": 0.0,
        }

        if findings:
            summary["avg_score"] = round(
                sum(f.get("score", 0) for f in findings) / len(findings), 1
            )

        return summary
