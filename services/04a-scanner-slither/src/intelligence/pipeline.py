"""Quality Pipeline — end-to-end post-processing for Slither findings.

Pipeline stages (applied in order):
  1. FP_PATTERN  — Match findings against known false-positive patterns
  2. NOISE_FILTER — Drop noisy/informational findings per contract type
  3. AI_VERIFY   — Call 06-AI for context-aware TP/FP classification
  4. SCORE       — Multi-dimensional risk scoring (CompositeScorer)
  5. RANK        — Sort by adjusted confidence × severity
  6. ENRICH      — Add fix suggestions, exploit paths, metadata

Each stage can be independently enabled/disabled.
The pipeline produces a QualityReport with filtered, scored findings.

Architecture:
  Pipeline
    ├── Stage 1: FpPatternMatcher  (fast, no I/O)
    ├── Stage 2: NoiseFilter       (fast, no I/O)
    ├── Stage 3: AIVerifier        (slow, HTTP to 06-AI)
    ├── Stage 4: CompositeScorer   (fast, in-memory)
    ├── Stage 5: Ranker            (fast, in-memory)
    └── Stage 6: Enricher          (fast, in-memory)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

from src.intelligence.ai_verifier import AIVerificationResult, AIVerifier, create_ai_verifier
from src.intelligence.classifier import ContractClassifier, ContractType
from src.intelligence.fixer import FixGenerator, create_fixer
from src.intelligence.fp_db import FalsePositiveDB
from src.intelligence.fp_patterns import FpMatchResult, FpPatternMatcher, create_fp_pattern_matcher
from src.intelligence.path_predictor import ExploitPathPredictor, create_path_predictor
from src.intelligence.scorer import CompositeScorer, RiskScore, create_scorer

log = structlog.get_logger()


class PipelineStage(str, Enum):
    FP_PATTERN = "fp_pattern"
    NOISE_FILTER = "noise_filter"
    AI_VERIFY = "ai_verify"
    SCORE = "score"
    RANK = "rank"
    ENRICH = "enrich"


# ── Data Classes ────────────────────────────────────────────


@dataclass
class ProcessedFinding:
    """A finding that has passed through the pipeline."""

    # Original finding data
    title: str
    severity: str
    description: str
    contract: str | None
    line: int | None
    recommendation: str | None
    original_confidence: float = 0.5

    # Pipeline enrichments
    fp_match: FpMatchResult | None = None
    ai_verification: AIVerificationResult | None = None
    risk_score: RiskScore | None = None
    fix_suggestion: dict[str, Any] | None = None

    # Pipeline decisions
    dropped: bool = False
    drop_reason: str = ""
    adjusted_confidence: float = 0.5
    adjusted_severity: str = ""

    # Quality metadata
    pipeline_version: str = "2.0"
    processed_at: float = field(default_factory=time.time)

    @property
    def is_relevant(self) -> bool:
        """A finding is relevant if it wasn't dropped by the pipeline."""
        return not self.dropped

    @property
    def quality_score(self) -> float:
        """Compute overall quality score (0-100) for this finding."""
        # Base: adjust from confidence
        base = self.adjusted_confidence * 100

        # Penalty for being dropped by FP pattern
        if self.fp_match and self.fp_match.is_fp:
            base *= (1.0 - self.fp_match.confidence_penalty)

        # Boost if AI confirmed
        if self.ai_verification and self.ai_verification.is_true_positive:
            base *= (0.8 + 0.2 * self.ai_verification.ai_confidence)

        # Boost if risk score is high
        if self.risk_score:
            base = base * 0.5 + self.risk_score.normalized_score * 0.5

        return max(0, min(100, base))

    def to_output(self) -> dict[str, Any]:
        """Convert to output dict for API response."""
        result = {
            "title": self.title,
            "severity": self.adjusted_severity or self.severity,
            "description": self.description,
            "contract": self.contract or "",
            "line": self.line,
            "recommendation": self.recommendation or "",
            "confidence": round(self.adjusted_confidence, 3),
            "quality_score": round(self.quality_score, 2),
            "relevant": self.is_relevant,
        }

        if self.fp_match and self.fp_match.is_fp:
            result["fp_pattern"] = self.fp_match.to_dict()

        if self.ai_verification:
            result["ai_verification"] = {
                "verdict": self.ai_verification.ai_verdict,
                "confidence": self.ai_verification.ai_confidence,
                "severity": self.ai_verification.ai_severity,
                "reasoning": self.ai_verification.ai_reasoning,
            }

        if self.risk_score:
            result["risk_score"] = {
                "normalized_score": self.risk_score.normalized_score,
                "risk_label": self.risk_score.risk_label,
                "exploitability": self.risk_score.exploitability,
                "priority": self.risk_score.priority,
            }

        if self.fix_suggestion:
            result["fix_suggestion"] = self.fix_suggestion

        if self.dropped:
            result["dropped"] = True
            result["drop_reason"] = self.drop_reason

        return result


@dataclass
class QualityReport:
    """Complete pipeline output for an audit."""

    contract_type: str = "unknown"
    contract_address: str = ""
    total_raw_findings: int = 0
    total_relevant: int = 0
    total_dropped: int = 0
    findings: list[ProcessedFinding] = field(default_factory=list)
    relevant_findings: list[ProcessedFinding] = field(default_factory=list)
    dropped_findings: list[ProcessedFinding] = field(default_factory=list)
    aggregate_risk: dict[str, Any] = field(default_factory=dict)
    exploit_paths: list[dict[str, Any]] = field(default_factory=list)
    pipeline_duration_ms: float = 0.0
    stages_executed: list[str] = field(default_factory=list)
    overall_quality: float = 0.0

    @property
    def drop_rate(self) -> float:
        """Percentage of findings dropped by the pipeline."""
        if self.total_raw_findings == 0:
            return 0.0
        return round(self.total_dropped / self.total_raw_findings * 100, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": self.contract_type,
            "contract_address": self.contract_address,
            "total_raw_findings": self.total_raw_findings,
            "total_relevant": self.total_relevant,
            "total_dropped": self.total_dropped,
            "drop_rate_pct": self.drop_rate,
            "findings": [f.to_output() for f in self.findings],
            "relevant_findings": [f.to_output() for f in self.relevant_findings],
            "aggregate_risk": self.aggregate_risk,
            "exploit_paths": self.exploit_paths,
            "pipeline_duration_ms": round(self.pipeline_duration_ms, 1),
            "stages_executed": self.stages_executed,
            "overall_quality": round(self.overall_quality, 1),
        }


# ── Pipeline Orchestrator ────────────────────────────────────


class QualityPipeline:
    """End-to-end quality pipeline for Slither findings.

    Args:
        fp_matcher: FP pattern matcher instance.
        ai_verifier: AI verification instance.
        scorer: Composite scorer instance.
        fixer: Fix generator instance.
        path_predictor: Exploit path predictor instance.
        fp_db: False positive database (for historical confidence).
        classifier: Contract classifier (for noise filtering).
        enable_stages: Set of stages to enable (all by default).
        min_quality_score: Minimum quality score to keep a finding (0-100).
    """

    def __init__(
        self,
        fp_matcher: FpPatternMatcher | None = None,
        ai_verifier: AIVerifier | None = None,
        scorer: CompositeScorer | None = None,
        fixer: FixGenerator | None = None,
        path_predictor: ExploitPathPredictor | None = None,
        fp_db: FalsePositiveDB | None = None,
        classifier: ContractClassifier | None = None,
        enable_stages: set[PipelineStage] | None = None,
        min_quality_score: float = 10.0,
    ) -> None:
        self._fp_matcher = fp_matcher or create_fp_pattern_matcher()
        self._ai_verifier = ai_verifier or create_ai_verifier()
        self._scorer = scorer or create_scorer(fp_db=fp_db)
        self._fixer = fixer or create_fixer()
        self._path_predictor = path_predictor or create_path_predictor()
        self._fp_db = fp_db
        self._classifier = classifier or ContractClassifier()
        self._enable_stages = enable_stages or set(PipelineStage)
        self._min_quality_score = min_quality_score

    async def run(
        self,
        findings: list[dict[str, Any]],
        source_code: dict[str, str],
        contract_type: ContractType = ContractType.UNKNOWN,
        contract_address: str = "",
        contract_name: str = "",
        compiler: str = "",
        audit_id: str = "default",
    ) -> QualityReport:
        """Run the full quality pipeline on Slither findings.

        Args:
            findings: Raw Slither findings as dicts.
            source_code: Dict of file path → source code.
            contract_type: Classified contract type.
            contract_address: Contract address for FP DB lookup.
            contract_name: Contract name for fix personalization.
            compiler: Solidity compiler version.
            audit_id: Audit session identifier.

        Returns:
            QualityReport with processed findings.
        """
        start = time.monotonic()
        stages_run: list[str] = []
        combined_source = "\n".join(source_code.values()) if source_code else ""

        # 1. Convert raw dict findings to ProcessedFinding objects
        processed: list[ProcessedFinding] = [
            self._to_processed(f) for f in findings
        ]

        # 2. FP Pattern Match (Stage 1)
        if PipelineStage.FP_PATTERN in self._enable_stages:
            stages_run.append("fp_pattern")
            for pf in processed:
                result = self._fp_matcher.evaluate_finding(
                    {"title": pf.title, "description": pf.description},
                    combined_source,
                )
                pf.fp_match = result
                if result.is_fp:
                    pf.adjusted_confidence *= (1.0 - result.confidence_penalty)
                    pf.adjusted_severity = result.severity_reduction or pf.severity
                    pf.dropped = True
                    pf.drop_reason = f"FP pattern: {result.pattern_name} — {result.description}"

        # 3. Noise Filter (Stage 2)
        if PipelineStage.NOISE_FILTER in self._enable_stages:
            stages_run.append("noise_filter")
            noise_detectors = self._classifier.get_noise_detectors(contract_type)
            for pf in processed:
                if pf.title in noise_detectors and not pf.dropped:
                    pf.dropped = True
                    pf.drop_reason = f"Noise filter: {pf.title} suppressed for {contract_type.value}"

        # 4. AI Verify (Stage 3) — only for non-dropped findings
        if PipelineStage.AI_VERIFY in self._enable_stages:
            stages_run.append("ai_verify")
            non_dropped = [pf for pf in processed if not pf.dropped]
            if non_dropped:
                ai_results = await self._ai_verifier.verify_findings(
                    findings=[{"title": pf.title, "description": pf.description, "severity": pf.severity}
                              for pf in non_dropped],
                    source_code=source_code,
                    audit_id=audit_id,
                    contract_name=contract_name,
                    compiler=compiler,
                )
                for pf, ai_res in zip(non_dropped, ai_results):
                    pf.ai_verification = ai_res
                    if ai_res.is_false_positive:
                        pf.adjusted_confidence *= 0.3
                        pf.dropped = True
                        pf.drop_reason = f"AI flagged as FP (confidence={ai_res.ai_confidence:.2f}): {ai_res.ai_reasoning[:100]}"
                    elif ai_res.is_true_positive:
                        pf.adjusted_confidence *= (0.7 + 0.3 * ai_res.ai_confidence)
                        pf.adjusted_severity = ai_res.ai_severity

        # 5. Score (Stage 4)
        if PipelineStage.SCORE in self._enable_stages:
            stages_run.append("score")
            non_dropped = [pf for pf in processed if not pf.dropped]
            if non_dropped:
                score_inputs = [
                    {"title": pf.title, "severity": pf.adjusted_severity or pf.severity}
                    for pf in non_dropped
                ]
                scores = self._scorer.score_findings(
                    score_inputs,
                    contract_type=contract_type,
                    contract_address=contract_address or None,
                )
                for pf, score in zip(non_dropped, scores):
                    pf.risk_score = score
                    # Drop if score is too low
                    if score.normalized_score < self._min_quality_score:
                        pf.dropped = True
                        pf.drop_reason = f"Low quality score ({score.normalized_score:.1f} < {self._min_quality_score})"

        # 6. Rank (Stage 5)
        if PipelineStage.RANK in self._enable_stages:
            stages_run.append("rank")
            non_dropped = [pf for pf in processed if not pf.dropped]
            non_dropped.sort(
                key=lambda pf: pf.quality_score,
                reverse=True,
            )
            # Re-assign sorted list
            pf_map = {id(pf): pf for pf in processed}
            for pf in processed:
                if not pf.dropped and pf in non_dropped:
                    pass  # Already sorted by reference

        # 7. Enrich (Stage 6)
        if PipelineStage.ENRICH in self._enable_stages:
            stages_run.append("enrich")
            non_dropped = [pf for pf in processed if not pf.dropped]
            for pf in non_dropped:
                fix = self._fixer.generate_fix(
                    detector=pf.title,
                    title=pf.title,
                    severity=pf.adjusted_severity or pf.severity,
                    description=pf.description,
                    contract_name=contract_name,
                )
                pf.fix_suggestion = {
                    "description": fix.description,
                    "before": fix.before,
                    "after": fix.after,
                    "solidity_example": fix.solidity_example,
                    "references": fix.references,
                    "confidence": fix.confidence,
                }

        # ── Build Report ────────────────────────────────────
        elapsed = time.monotonic() - start
        relevant = [pf for pf in processed if not pf.dropped]
        dropped = [pf for pf in processed if pf.dropped]

        # Aggregate risk
        aggregate = {}
        if relevant:
            scores = [pf.risk_score for pf in relevant if pf.risk_score]
            if scores:
                aggregate = self._scorer.compute_aggregate_risk(scores)

        # Exploit paths
        exploit_paths = []
        if relevant:
            path_inputs = [
                {"title": pf.title, "severity": pf.adjusted_severity or pf.severity}
                for pf in relevant[:20]
            ]
            if path_inputs:
                exploit_paths = self._path_predictor.predict_paths(
                    path_inputs,
                    contract_type=contract_type.value,
                )

        # Overall quality: weighted average of relevant finding scores
        overall_quality = 0.0
        if relevant:
            quality_scores = [pf.quality_score for pf in relevant[:10]]
            if quality_scores:
                weights = [max(1, 10 - i) for i in range(len(quality_scores))]
                overall_quality = sum(q * w for q, w in zip(quality_scores, weights)) / sum(weights)

        report = QualityReport(
            contract_type=contract_type.value,
            contract_address=contract_address,
            total_raw_findings=len(findings),
            total_relevant=len(relevant),
            total_dropped=len(dropped),
            findings=processed,
            relevant_findings=relevant,
            dropped_findings=dropped,
            aggregate_risk=aggregate,
            exploit_paths=exploit_paths,
            pipeline_duration_ms=(elapsed * 1000),
            stages_executed=stages_run,
            overall_quality=overall_quality,
        )

        log.info(
            "pipeline.completed",
            raw=report.total_raw_findings,
            relevant=report.total_relevant,
            dropped=report.total_dropped,
            drop_rate=report.drop_rate,
            quality=round(overall_quality, 1),
            duration_ms=round(elapsed * 1000, 1),
            stages=stages_run,
        )

        return report

    # ── Helpers ─────────────────────────────────────────────

    @staticmethod
    def _to_processed(finding: dict[str, Any]) -> ProcessedFinding:
        """Convert a raw finding dict to a ProcessedFinding."""
        return ProcessedFinding(
            title=finding.get("title", "Unknown"),
            severity=finding.get("severity", "informational"),
            description=finding.get("description", ""),
            contract=finding.get("contract"),
            line=finding.get("line"),
            recommendation=finding.get("recommendation"),
            adjusted_confidence=0.5,
            adjusted_severity=finding.get("severity", "informational"),
        )


def create_pipeline(
    fp_matcher: FpPatternMatcher | None = None,
    ai_verifier: AIVerifier | None = None,
    scorer: CompositeScorer | None = None,
    fixer: FixGenerator | None = None,
    path_predictor: ExploitPathPredictor | None = None,
    fp_db: FalsePositiveDB | None = None,
    classifier: ContractClassifier | None = None,
    min_quality_score: float = 10.0,
) -> QualityPipeline:
    """Create a configured QualityPipeline instance."""
    return QualityPipeline(
        fp_matcher=fp_matcher,
        ai_verifier=ai_verifier,
        scorer=scorer,
        fixer=fixer,
        path_predictor=path_predictor,
        fp_db=fp_db,
        classifier=classifier,
        min_quality_score=min_quality_score,
    )
