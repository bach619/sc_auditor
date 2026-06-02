"""Composite Risk Scorer — L4 Intelligence.

Moves beyond simple severity labels to compute a multi-dimensional
risk score for each finding, taking into account:

1. Base severity (static analysis severity)
2. Exploitability (can the vulnerability actually be triggered?)
3. Business impact (what's at risk? ETH, tokens, governance?)
4. Contract context (is this a high-value DeFi contract?)
5. Historical TP rate (has this detector been accurate?)
6. Composite score (0-100) combining all factors
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import structlog

from src.intelligence.classifier import ContractType
from src.intelligence.fp_db import FalsePositiveDB

log = structlog.get_logger()


@dataclass
class RiskScore:
    """Composite risk score for a single finding."""

    finding_title: str
    finding_severity: str
    detector: str

    # Base score (from severity)
    base_score: float = 0.0

    # Individual factors (0.0 - 1.0)
    exploitability: float = 0.5
    business_impact: float = 0.5
    contract_risk_factor: float = 0.5
    historical_confidence: float = 0.5

    # Derived scores (0-100)
    raw_score: float = 0.0
    adjusted_score: float = 0.0
    normalized_score: float = 0.0

    # Labels
    risk_label: str = "medium"
    recommendation: str = ""
    priority: int = 3  # 1 (critical) to 5 (info)


# Severity → base score mapping
SEVERITY_BASE: dict[str, float] = {
    "critical": 90.0,
    "high": 65.0,
    "medium": 40.0,
    "low": 20.0,
    "informational": 5.0,
}

SEVERITY_WEIGHTS: dict[str, float] = {
    "critical": 1.0,
    "high": 0.8,
    "medium": 0.5,
    "low": 0.3,
    "informational": 0.1,
}


# Detector → exploitability score
# Based on how reliably each detector indicates actual exploitability
DETECTOR_EXPLOITABILITY: dict[str, float] = {
    "reentrancy-eth": 0.95,
    "reentrancy-no-eth": 0.85,
    "unchecked-lowlevel": 0.80,
    "controlled-delegatecall": 0.95,
    "arbitrary-send": 0.90,
    "tx-origin": 0.60,
    "incorrect-equality": 0.50,
    "shadowing-state": 0.30,
    "shadowing-abstract": 0.40,
    "uninitialized-state": 0.75,
    "uninitialized-storage": 0.70,
    "uninitialized-implementation": 0.90,
    "missing-zero-check": 0.40,
    "unused-return": 0.30,
    "timestamp": 0.35,
    "assembly": 0.20,
    "calls-loop": 0.55,
    "low-level-calls": 0.65,
    "suicidal": 0.85,
    "locked-ether": 0.50,
    "controlled-array-length": 0.70,
    "reentrancy-events": 0.30,
    "variable-scope": 0.10,
    "cyclomatic-complexity": 0.10,
    "naming-convention": 0.05,
    "pragma": 0.05,
    "solc-version": 0.05,
    "too-many-digits": 0.05,
    "constable-states": 0.10,
    "immutable-states": 0.10,
    "redundant-statements": 0.05,
    "similar-names": 0.05,
    "write-after-write": 0.30,
    "external-function": 0.10,
    "multiple-constructors": 0.20,
    "missing-inheritance": 0.15,
    "return-bomb": 0.40,
    "divide-before-multiply": 0.45,
    "encode-packed-collision": 0.60,
    "storage-order": 0.10,
    "unused-state": 0.05,
}


# Business impact per contract type
BUSINESS_IMPACT: dict[ContractType, float] = {
    ContractType.LENDING: 0.95,
    ContractType.BRIDGE: 0.95,
    ContractType.CROSS_CHAIN: 0.95,
    ContractType.DEX: 0.90,
    ContractType.UNISWAP_V2: 0.90,
    ContractType.UNISWAP_V3: 0.90,
    ContractType.VAULT: 0.85,
    ContractType.STAKING: 0.80,
    ContractType.GOVERNANCE: 0.75,
    ContractType.ERC20: 0.65,
    ContractType.ERC721: 0.60,
    ContractType.ERC1155: 0.60,
    ContractType.NFT_MARKETPLACE: 0.70,
    ContractType.MULTISIG: 0.85,
    ContractType.PROXY: 0.90,
    ContractType.ORACLE: 0.85,
    ContractType.DEFI_AGGREGATOR: 0.85,
    ContractType.OPTION: 0.80,
    ContractType.UNKNOWN: 0.50,
}


class CompositeScorer:
    """Compute multi-dimensional risk scores for findings.

    Usage:
        scorer = CompositeScorer(fp_db)
        score = scorer.score_finding(finding, contract_type, contract_address)
    """

    def __init__(self, fp_db: FalsePositiveDB | None = None) -> None:
        self._fp_db = fp_db

    def score_finding(
        self,
        finding: Any,
        contract_type: ContractType = ContractType.UNKNOWN,
        contract_address: str | None = None,
        ai_confidence: float | None = None,
    ) -> RiskScore:
        """Compute composite risk score for a single finding.

        Args:
            finding: Finding object (dict or Pydantic model) with at minimum
                     'title', 'severity', and 'tool' attributes.
            contract_type: Classified contract type.
            contract_address: Optional contract address for FP/DB lookup.
            ai_confidence: Optional AI verification confidence (0.0–1.0).

        Returns:
            A RiskScore dataclass with all computed scores.
        """
        title = getattr(finding, "title", str(finding.get("title", "")))
        severity = getattr(finding, "severity", str(finding.get("severity", "informational")))
        detector = title  # Slither uses detector name as title
        severity = severity.lower()

        # 1. Base score from severity
        base_score = SEVERITY_BASE.get(severity, 20.0)

        # 2. Exploitability
        exploitability = DETECTOR_EXPLOITABILITY.get(detector, 0.3)
        # Adjust: critical findings get exploitability boost regardless of detector
        if severity == "critical" and exploitability < 0.7:
            exploitability = max(exploitability, 0.7)
        if severity == "high" and exploitability < 0.4:
            exploitability = max(exploitability, 0.4)

        # 3. Business impact based on contract type
        business_impact = BUSINESS_IMPACT.get(contract_type, 0.5)

        # 4. Contract risk factor (DeFi protocols are higher value)
        contract_risk_factor = self._compute_contract_risk(contract_type)

        # 5. Historical confidence from FP/DB
        historical_confidence = 0.5
        if self._fp_db:
            stats = self._fp_db.get_detector_stats(detector)
            if stats["total_feedback"] > 0:
                historical_confidence = stats["tp_ratio"]
                # Check if should suppress
                if contract_address and self._fp_db.should_suppress(detector, contract_address):
                    historical_confidence = max(historical_confidence * 0.5, 0.1)

        # 5b. AI confidence factor (L5 integration)
        # If AI has verified this finding, use it to calibrate confidence
        if ai_confidence is not None:
            # Blend historical and AI confidence (AI weights more if confident)
            ai_weight = min(0.7, ai_confidence * 0.8)
            historical_confidence = (
                historical_confidence * (1.0 - ai_weight)
                + ai_confidence * ai_weight
            )

        # 6. Compute raw score
        raw_score = base_score

        # 7. Adjusted score with all factors
        adjusted_score = (
            base_score
            * (0.3 + 0.7 * exploitability)           # Exploitability weight
            * (0.5 + 0.5 * business_impact)            # Business impact weight
            * (0.7 + 0.3 * contract_risk_factor)       # Contract risk weight
            * (0.5 + 0.5 * historical_confidence)      # Historical confidence weight
        )

        # Cap to 0-100
        adjusted_score = max(0, min(100, adjusted_score))

        # 8. Normalize: compare to max possible for this severity
        max_possible = base_score * 1.4 * 1.0 * 1.0 * 1.0
        normalized_score = (adjusted_score / max_possible) * 100 if max_possible > 0 else 0
        normalized_score = max(0, min(100, normalized_score))

        # 9. Determine risk label and priority
        risk_label, priority = self._classify_risk(normalized_score)

        # 10. Generate recommendation
        recommendation = self._generate_recommendation(detector, severity, normalized_score)

        return RiskScore(
            finding_title=title,
            finding_severity=severity,
            detector=detector,
            base_score=base_score,
            exploitability=round(exploitability, 3),
            business_impact=round(business_impact, 3),
            contract_risk_factor=round(contract_risk_factor, 3),
            historical_confidence=round(historical_confidence, 3),
            raw_score=round(raw_score, 2),
            adjusted_score=round(adjusted_score, 2),
            normalized_score=round(normalized_score, 2),
            risk_label=risk_label,
            recommendation=recommendation,
            priority=priority,
        )

    def score_findings(
        self,
        findings: list[Any],
        contract_type: ContractType = ContractType.UNKNOWN,
        contract_address: str | None = None,
        ai_confidences: dict[str, float] | None = None,
    ) -> list[RiskScore]:
        """Score multiple findings in batch.

        Args:
            findings: List of finding objects with 'title' and 'severity'.
            contract_type: Classified contract type.
            contract_address: Optional contract address for FP DB lookup.
            ai_confidences: Optional dict mapping finding title → AI confidence.

        Returns:
            List of RiskScore objects sorted by normalized_score descending.
        """
        scores = []
        for f in findings:
            title = getattr(f, "title", str(f.get("title", "")))
            ai_conf = None
            if ai_confidences and title in ai_confidences:
                ai_conf = ai_confidences[title]
            scores.append(
                self.score_finding(f, contract_type, contract_address, ai_confidence=ai_conf)
            )
        scores.sort(key=lambda s: s.normalized_score, reverse=True)
        return scores

    def compute_aggregate_risk(
        self,
        scores: list[RiskScore],
    ) -> dict[str, Any]:
        """Compute aggregate risk metrics for a contract.

        Returns:
            Dict with overall risk score, counts by level, etc.
        """
        if not scores:
            return {
                "overall_risk_score": 0,
                "overall_risk_label": "none",
                "total_findings": 0,
                "critical_count": 0,
                "high_count": 0,
                "risk_distribution": {},
            }

        # Overall = weighted average of top 5 scores
        top_5 = scores[:5]
        weights = [5, 4, 3, 2, 1][:len(top_5)]
        overall = sum(s.normalized_score * w for s, w in zip(top_5, weights)) / sum(weights)

        overall_label, _ = self._classify_risk(overall)

        distribution = {
            "critical": sum(1 for s in scores if s.risk_label == "critical"),
            "high": sum(1 for s in scores if s.risk_label == "high"),
            "medium": sum(1 for s in scores if s.risk_label == "medium"),
            "low": sum(1 for s in scores if s.risk_label == "low"),
            "info": sum(1 for s in scores if s.risk_label == "info"),
        }

        return {
            "overall_risk_score": round(overall, 2),
            "overall_risk_label": overall_label,
            "total_findings": len(scores),
            "critical_count": distribution["critical"],
            "high_count": distribution["high"],
            "risk_distribution": distribution,
            "top_risks": [
                {
                    "title": s.finding_title,
                    "score": s.normalized_score,
                    "label": s.risk_label,
                    "priority": s.priority,
                }
                for s in scores[:3]
            ],
        }

    # ── Internal ────────────────────────────────────────────

    @staticmethod
    def _compute_contract_risk(contract_type: ContractType) -> float:
        """Compute inherent risk factor of the contract type."""
        high_risk = {
            ContractType.BRIDGE,
            ContractType.CROSS_CHAIN,
            ContractType.LENDING,
            ContractType.PROXY,
        }
        medium_risk = {
            ContractType.DEX,
            ContractType.UNISWAP_V2,
            ContractType.UNISWAP_V3,
            ContractType.VAULT,
            ContractType.MULTISIG,
            ContractType.GOVERNANCE,
        }
        if contract_type in high_risk:
            return 0.9
        if contract_type in medium_risk:
            return 0.7
        if contract_type == ContractType.UNKNOWN:
            return 0.5
        return 0.4

    @staticmethod
    def _classify_risk(score: float) -> tuple[str, int]:
        """Convert numeric score to risk label and priority."""
        if score >= 80:
            return "critical", 1
        if score >= 60:
            return "high", 2
        if score >= 35:
            return "medium", 3
        if score >= 15:
            return "low", 4
        return "info", 5

    @staticmethod
    def _generate_recommendation(detector: str, severity: str, score: float) -> str:
        """Generate context-aware recommendation text."""
        if score >= 80:
            return (
                f"CRITICAL: {detector} — immediate action required. "
                "This vulnerability is highly exploitable and puts user funds at risk. "
                "Review and fix before any mainnet deployment."
            )
        if score >= 60:
            return (
                f"HIGH: {detector} — address in next update. "
                "While not critical, this vulnerability could be chained with "
                "other issues for significant impact."
            )
        if score >= 35:
            return (
                f"MEDIUM: {detector} — review recommended. "
                "Moderate risk that may require attention depending on contract context."
            )
        if score >= 15:
            return (
                f"LOW: {detector} — best practice improvement. "
                "Low risk but addressing it improves overall code quality."
            )
        return (
            f"INFO: {detector} — informational only. "
            "No immediate action required."
        )


def create_scorer(fp_db: FalsePositiveDB | None = None) -> CompositeScorer:
    return CompositeScorer(fp_db=fp_db)
