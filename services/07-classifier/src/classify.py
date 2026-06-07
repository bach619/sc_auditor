"""Classification engine for the Vyper Classifier Service.

Implements the 4-quadrant detection matrix (TP/FP/TN/FN) and the 5-stage
finding lifecycle defined in the architecture specification §7.1–§7.2.

Classification rules:
  1. AI confidence > 0.9 AND severity critical/high → TP
  2. AI confidence < 0.3 → FP
  3. Matches known FN pattern → escalate (FN)
  4. Matches known FP pattern → downgrade (FP)
  5. Default: trust the AI verdict
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from src.improver import PatternLearner
from src.models import (
    Classification,
    ClassificationLayer,
    ClassificationSource,
    ClassificationStage,
    Finding,
    Severity,
)

log = structlog.get_logger()

# ── Constants ────────────────────────────────────────────────────────────

CLASSIFIER_DATA_DIR = Path("/data/classifier")
FINDINGS_FILE = CLASSIFIER_DATA_DIR / "findings.json"

# Confidence thresholds for classification rules
HIGH_CONFIDENCE_THRESHOLD: float = 0.9
LOW_CONFIDENCE_THRESHOLD: float = 0.3
MEDIUM_CONFIDENCE_THRESHOLD: float = 0.5

# Severities eligible for auto-TP on high confidence
AUTO_TP_SEVERITIES: frozenset[str] = frozenset({"critical", "high"})


# ── Helpers ──────────────────────────────────────────────────────────────


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def _load_findings() -> dict[str, dict[str, Any]]:
    """Load stored findings from disk."""
    if FINDINGS_FILE.exists():
        try:
            with open(FINDINGS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            log.error("findings_load_error", error=str(exc))
    return {}


def _save_findings(findings: dict[str, dict[str, Any]]) -> bool:
    """Persist findings atomically to disk."""
    FINDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FINDINGS_FILE.with_suffix(".tmp")
    try:
        with open(tmp, "w") as f:
            json.dump(findings, f, indent=2, default=str)
        tmp.replace(FINDINGS_FILE)
        return True
    except OSError as exc:
        log.error("findings_save_error", error=str(exc))
        if tmp.exists():
            tmp.unlink()
        return False


# ── Classifier ───────────────────────────────────────────────────────────


class Classifier:
    """Classification engine that applies rules and historical patterns.

    The classifier is the core decision-making component. It:
    - Applies deterministic rules to classify findings
    - Consults learned patterns from the PatternLearner
    - Maintains confidence scores at each classification stage
    - Preserves raw findings and appends classification layers (non-destructive)
    """

    def __init__(self, pattern_learner: PatternLearner | None = None) -> None:
        self._pattern_learner = pattern_learner or PatternLearner()
        self._findings: dict[str, dict[str, Any]] = _load_findings()
        log.info("classifier_initialized", stored_findings=len(self._findings))

    # ── Public API ───────────────────────────────────────────────────────

    def classify(self, finding: Finding) -> Finding:
        """Apply classification rules to a single finding.

        The classification pipeline:
        1. Checks for known pattern matches (FN/FP patterns from feedback)
        2. Applies confidence-based rules
        3. Falls back to trusting the AI verdict
        4. Records the decision as a new classification layer
        """
        # ── Stage 0: Check Knowledge Base for confirmed matches ──
        try:
            from shared.knowledge_base import KnowledgeRepository
            kb = KnowledgeRepository()
            # Check if this or similar finding was already confirmed
            matches = kb.find_matching_pattern(
                attack_type=finding.title[:50],
            )
            if matches:
                layer = ClassificationLayer(
                    stage=ClassificationStage.EXPLOIT_CONFIRMED,
                    classification=Classification.TRUE_POSITIVE,
                    source=ClassificationSource.EXPLOIT,
                    confidence=1.0,
                    reasoning=(
                        f"Knowledge Base match: {len(matches)} prior confirmation(s) "
                        f"for similar finding type '{matches[0].attack_type}'. "
                        f"Auto-classified as TRUE POSITIVE."
                    ),
                )
                finding.add_layer(layer)
                log.info(
                    "classified_by_kb",
                    finding_id=finding.finding_id,
                    matches=len(matches),
                )
                return finding
        except ImportError:
            pass
        except Exception as exc:
            log.warning("classify.kb_error", error=str(exc))

        # ── Stage 1: Pattern match ────────────────────────────────────────
        matched_pattern = self._pattern_learner.match_pattern(finding)
        if matched_pattern is not None:
            layer = ClassificationLayer(
                stage=ClassificationStage.CLASSIFIED,
                classification=matched_pattern.classification,
                source=ClassificationSource.CLASSIFIER,
                confidence=matched_pattern.effectiveness_score,
                reasoning=(
                    f"Matched pattern '{matched_pattern.name}' "
                    f"(score={matched_pattern.effectiveness_score:.2f})"
                ),
            )
            finding.add_layer(layer)
            log.info(
                "classified_by_pattern",
                finding_id=finding.finding_id,
                classification=layer.classification.value,
                pattern=matched_pattern.name,
            )
            return finding

        # ── Stage 2: Confidence-based rules ──────────────────────────────
        ai_confidence = finding.ai_confidence or 0.0
        severity = finding.severity.value if finding.severity else Severity.INFO.value

        # Rule 1: High-confidence critical/high → TP
        if ai_confidence >= HIGH_CONFIDENCE_THRESHOLD and severity in AUTO_TP_SEVERITIES:
            layer = ClassificationLayer(
                stage=ClassificationStage.CLASSIFIED,
                classification=Classification.TRUE_POSITIVE,
                source=ClassificationSource.CLASSIFIER,
                confidence=ai_confidence,
                reasoning=(
                    f"AI confidence {ai_confidence:.2f} ≥ {HIGH_CONFIDENCE_THRESHOLD} "
                    f"with {severity} severity → auto TP"
                ),
            )
            finding.add_layer(layer)
            log.info(
                "classified_tp_high_confidence",
                finding_id=finding.finding_id,
                confidence=ai_confidence,
            )
            return finding

        # Rule 2: Low confidence → FP
        if ai_confidence <= LOW_CONFIDENCE_THRESHOLD:
            layer = ClassificationLayer(
                stage=ClassificationStage.CLASSIFIED,
                classification=Classification.FALSE_POSITIVE,
                source=ClassificationSource.CLASSIFIER,
                confidence=1.0 - ai_confidence,
                reasoning=(
                    f"AI confidence {ai_confidence:.2f} ≤ {LOW_CONFIDENCE_THRESHOLD} "
                    "→ auto FP"
                ),
            )
            finding.add_layer(layer)
            log.info(
                "classified_fp_low_confidence",
                finding_id=finding.finding_id,
                confidence=ai_confidence,
            )
            return finding

        # Rule 3: Medium confidence critical/high → flag for review as potential TP
        if (
            ai_confidence >= MEDIUM_CONFIDENCE_THRESHOLD
            and severity in AUTO_TP_SEVERITIES
        ):
            layer = ClassificationLayer(
                stage=ClassificationStage.CLASSIFIED,
                classification=Classification.TRUE_POSITIVE,
                source=ClassificationSource.CLASSIFIER,
                confidence=ai_confidence,
                reasoning=(
                    f"Medium-high confidence ({ai_confidence:.2f}) "
                    f"with {severity} severity → TP (needs confirmation)"
                ),
            )
            finding.add_layer(layer)
            log.info(
                "classified_tp_medium_confidence",
                finding_id=finding.finding_id,
                confidence=ai_confidence,
            )
            return finding

        # ── Stage 3: Default — trust the AI verdict ──────────────────────
        if finding.ai_verdict is not None and finding.ai_verdict != Classification.UNKNOWN:
            verdict = finding.ai_verdict
            layer = ClassificationLayer(
                stage=ClassificationStage.CLASSIFIED,
                classification=verdict,
                source=ClassificationSource.CLASSIFIER,
                confidence=ai_confidence,
                reasoning=f"Trusting AI verdict: {verdict.value} (confidence={ai_confidence:.2f})",
            )
            finding.add_layer(layer)
            log.info(
                "classified_trust_ai",
                finding_id=finding.finding_id,
                classification=verdict.value,
            )
            return finding

        # ── Fallback: Unknown ────────────────────────────────────────────
        layer = ClassificationLayer(
            stage=ClassificationStage.CLASSIFIED,
            classification=Classification.UNKNOWN,
            source=ClassificationSource.CLASSIFIER,
            confidence=0.0,
            reasoning="Insufficient data to classify — no AI verdict, no pattern match",
        )
        finding.add_layer(layer)
        log.warning("classified_unknown", finding_id=finding.finding_id)
        return finding

    def classify_all(self, findings: list[Finding]) -> list[Finding]:
        """Batch classify multiple findings.

        Each finding is classified independently. Results are persisted
        to the findings store.
        """
        classified: list[Finding] = []
        for finding in findings:
            result = self.classify(finding)
            classified.append(result)
            self._store_finding(result)

        log.info(
            "batch_classify_complete",
            total=len(findings),
            classified=len(classified),
        )
        return classified

    def reclassify(
        self,
        audit_id: str | None = None,
        finding_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Reclassify findings using the latest patterns.

        This is called when new patterns have been learned from feedback
        or FN discoveries. It reapplies the entire classification pipeline
        to the specified findings.

        Args:
            audit_id: If provided, reclassify all findings for this audit.
            finding_ids: If provided, reclassify only these specific findings.

        Returns:
            List of reclassification records.
        """
        self._findings = _load_findings()
        reclassified: list[dict[str, Any]] = []

        for fid, fdata in self._findings.items():
            # Filter by audit_id if provided
            if audit_id and fdata.get("audit_id") != audit_id:
                continue
            # Filter by finding_ids if provided
            if finding_ids and fid not in finding_ids:
                continue

            finding = Finding(**fdata)
            old_class = finding.current_classification.value
            old_layers = len(finding.classification_layers)

            # Re-classify from the raw state (clear previous classifier layers)
            finding.classification_layers = [
                layer for layer in finding.classification_layers
                if layer.source == ClassificationSource.TOOL_RAW
                or layer.source == ClassificationSource.AI_VERDICT
            ]

            result = self.classify(finding)
            new_class = result.current_classification.value

            record = {
                "finding_id": fid,
                "previous_classification": old_class,
                "new_classification": new_class,
                "previous_layers": old_layers,
                "new_layers": len(result.classification_layers),
                "reclassified_at": _now_iso(),
                "changed": old_class != new_class,
            }
            reclassified.append(record)
            self._store_finding(result)

        log.info(
            "reclassification_complete",
            total=len(reclassified),
            changed=sum(1 for r in reclassified if r["changed"]),
        )
        return reclassified

    def receive_exploit_feedback(
        self,
        finding_id: str,
        exploit_successful: bool,
        tx_hash: str | None = None,
    ) -> dict[str, Any]:
        """Process exploit feedback and update classification to Stage 2.

        This is the core of the Exploit-as-Truth architecture.
        Stage 2 reclassifies the finding based on real exploit results.

        Args:
            finding_id: The finding identifier.
            exploit_successful: Whether the exploit was successfully executed.
            tx_hash: Transaction hash of the successful exploit (if any).

        Returns:
            Dict with reclassification details.

        Raises:
            ValueError: If finding_id not found.
        """
        # Load findings from disk to get latest state
        self._findings = _load_findings()
        fdata = self._findings.get(finding_id)
        if fdata is None:
            raise ValueError(f"Finding not found: {finding_id}")

        finding = Finding(**fdata)
        old_class = finding.current_classification

        # Determine Stage 2 classification based on exploit result
        if exploit_successful:
            # Exploit WORKED → TRUE POSITIVE CONFIRMED
            new_class = Classification.TRUE_POSITIVE
            confidence = 1.0  # Absolute certainty — exploit proved it
            reasoning = (
                f"Exploit successfully executed (tx: {tx_hash or 'N/A'}). "
                f"Stage 1: {old_class.value}. Confirmed: TRUE POSITIVE."
            )
            log.info(
                "exploit.confirmed_tp",
                finding_id=finding_id,
                tx_hash=tx_hash,
                original_classification=old_class.value,
            )
        else:
            # Exploit FAILED → downgrade
            new_class = Classification.FALSE_POSITIVE
            confidence = finding.current_confidence * 0.5  # Penalty: cut confidence in half
            reasoning = (
                f"Exploit execution failed. "
                f"Stage 1: {old_class.value}. Downgraded to FALSE POSITIVE (suspected)."
            )
            log.info(
                "exploit.failed_downgrade",
                finding_id=finding_id,
                original_classification=old_class.value,
            )

        # Add Stage 2 classification layer
        layer = ClassificationLayer(
            stage=ClassificationStage.EXPLOIT_CONFIRMED,
            classification=new_class,
            source=ClassificationSource.EXPLOIT,
            confidence=confidence,
            reasoning=reasoning,
        )
        finding.add_layer(layer)

        # Persist
        self._store_finding(finding)

        return {
            "finding_id": finding_id,
            "original_classification": old_class.value,
            "new_classification": new_class.value,
            "confidence": confidence,
            "exploit_successful": exploit_successful,
            "stage": ClassificationStage.EXPLOIT_CONFIRMED.value,
            "reclassified_at": _now_iso(),
        }

    def get_finding(self, finding_id: str) -> dict[str, Any] | None:
        """Retrieve a stored finding by ID."""
        return self._findings.get(finding_id)

    def get_all_findings(self) -> list[dict[str, Any]]:
        """Return all stored findings."""
        return list(self._findings.values())

    # ── Internal helpers ─────────────────────────────────────────────────

    def _store_finding(self, finding: Finding) -> None:
        """Persist a classified finding to the findings store."""
        self._findings[finding.finding_id] = finding.model_dump()
        _save_findings(self._findings)

    def _to_finding(self, raw: dict[str, Any], audit_id: str) -> Finding:
        """Convert a raw finding dict into a Finding model."""
        return Finding(
            finding_id=raw.get("finding_id", str(uuid.uuid4())),
            audit_id=audit_id,
            title=raw.get("title", "Untitled Finding"),
            description=raw.get("description"),
            severity=Severity(raw.get("severity", "info").lower()),
            tool=raw.get("tool"),
            file=raw.get("file"),
            line_start=raw.get("line_start"),
            line_end=raw.get("line_end"),
            code_snippet=raw.get("code_snippet"),
            swc_id=raw.get("swc_id"),
            cwe_id=raw.get("cwe_id"),
            impact=raw.get("impact"),
            recommendation=raw.get("recommendation"),
            ai_confidence=raw.get("ai_confidence"),
            ai_verdict=(
                Classification(raw["ai_verdict"])
                if raw.get("ai_verdict")
                else None
            ),
        )
