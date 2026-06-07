"""Pydantic models for the Vyper Classifier Service.

Implements the 4-quadrant detection matrix (TP/FP/TN/FN) as defined in the
architecture specification §7.1, the finding lifecycle stages from §7.2, and
the classification data model from §7.3.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════════════════════════
# Classification Enums
# ═══════════════════════════════════════════════════════════════════════════


class Classification(StrEnum):
    """The 4-quadrant detection matrix."""

    UNKNOWN = "unknown"
    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    TRUE_NEGATIVE = "true_negative"
    FALSE_NEGATIVE = "false_negative"


class ClassificationSource(StrEnum):
    """Source of a classification decision."""

    TOOL_RAW = "tool_raw"
    AI_VERDICT = "ai_verdict"
    CLASSIFIER = "classifier"
    EXPLOIT = "exploit"
    HUMAN_REVIEW = "human_review"
    IMMUNEFI_FEEDBACK = "immunefi_feedback"
    RECLASSIFICATION = "reclassification"


class ClassificationStage(StrEnum):
    """Finding lifecycle stages from §7.2."""

    RAW = "raw"
    AI_ANALYZED = "ai_analyzed"
    CLASSIFIED = "classified"
    EXPLOIT_CONFIRMED = "exploit_confirmed"
    HUMAN_REVIEWED = "human_reviewed"
    IMMUNEFI_SUBMITTED = "immunefi_submitted"


class Severity(StrEnum):
    """Finding severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class PatternType(StrEnum):
    """Types of vulnerability patterns the learner can detect."""

    CODE_PATTERN = "code_pattern"
    KEYWORD_PATTERN = "keyword_pattern"
    SEVERITY_PATTERN = "severity_pattern"
    TOOL_PATTERN = "tool_pattern"


# ═══════════════════════════════════════════════════════════════════════════
# Finding Models
# ═══════════════════════════════════════════════════════════════════════════


class ClassificationLayer(BaseModel):
    """A single classification layer appended to a finding.

    Each classification is non-destructive — the raw finding is preserved and
    classification layers are stacked on top.
    """

    stage: ClassificationStage
    classification: Classification
    source: ClassificationSource
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str | None = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class ToolInfo(BaseModel):
    """Information about the tool that produced a finding."""

    name: str
    version: str | None = None


class Finding(BaseModel):
    """A single finding from the scan pipeline.

    Preserves the raw finding data and appends classification layers.
    """

    finding_id: str
    audit_id: str | None = None
    title: str
    description: str | None = None
    severity: Severity
    tool: ToolInfo | None = None
    file: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    code_snippet: str | None = None
    swc_id: str | None = None
    cwe_id: str | None = None
    impact: str | None = None
    recommendation: str | None = None
    ai_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    ai_verdict: Classification | None = None
    classification_layers: list[ClassificationLayer] = Field(default_factory=list)

    @property
    def current_classification(self) -> Classification:
        """Return the most recent classification, or UNKNOWN."""
        if not self.classification_layers:
            return Classification.UNKNOWN
        return self.classification_layers[-1].classification

    @property
    def current_confidence(self) -> float:
        """Return the confidence of the most recent classification layer."""
        if not self.classification_layers:
            return 0.0
        return self.classification_layers[-1].confidence

    @property
    def current_stage(self) -> ClassificationStage:
        """Return the current lifecycle stage."""
        if not self.classification_layers:
            return ClassificationStage.RAW
        return self.classification_layers[-1].stage

    def add_layer(self, layer: ClassificationLayer) -> None:
        """Append a classification layer (non-destructive)."""
        self.classification_layers.append(layer)


# ═══════════════════════════════════════════════════════════════════════════
# Pattern Models
# ═══════════════════════════════════════════════════════════════════════════


class Pattern(BaseModel):
    """A learned vulnerability pattern for classification improvement."""

    pattern_id: str
    name: str
    pattern_type: PatternType
    classification: Classification
    description: str
    rules: dict[str, Any] = Field(default_factory=dict)
    effectiveness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    match_count: int = 0
    correct_count: int = 0
    source_feedback_id: str | None = None
    is_active: bool = True
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


# ═══════════════════════════════════════════════════════════════════════════
# Feedback Models
# ═══════════════════════════════════════════════════════════════════════════


class FeedbackStatus(StrEnum):
    """Status of a feedback entry in the confirmation workflow."""

    INITIAL = "initial"
    REVIEWED = "reviewed"
    FINALIZED = "finalized"


class Feedback(BaseModel):
    """Human feedback on a classification decision."""

    feedback_id: str
    finding_id: str
    audit_id: str | None = None
    correct_classification: Classification
    original_classification: Classification | None = None
    notes: str | None = None
    status: FeedbackStatus = FeedbackStatus.INITIAL
    reviewed_by: str | None = None
    source: ClassificationSource = ClassificationSource.HUMAN_REVIEW
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


# ═══════════════════════════════════════════════════════════════════════════
# Metrics Models
# ═══════════════════════════════════════════════════════════════════════════


class MetricsSnapshot(BaseModel):
    """A single point-in-time snapshot of classification metrics."""

    date: str
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    accuracy: float = 0.0
    overall_score: float = 0.0


class ToolMetrics(BaseModel):
    """Metrics broken down by scanning tool."""

    tool: str
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════
# API Request / Response Models
# ═══════════════════════════════════════════════════════════════════════════


class ClassifyRequest(BaseModel):
    """Request body for POST /classify."""

    audit_id: str
    findings: list[dict[str, Any]]


class FeedbackRequest(BaseModel):
    """Request body for POST /feedback."""

    finding_id: str
    correct_classification: Classification
    notes: str | None = None
    audit_id: str | None = None


class ReclassifyRequest(BaseModel):
    """Request body for POST /reclassify."""

    audit_id: str | None = None
    finding_ids: list[str] | None = None


class ExploitStatus(StrEnum):
    """Status exploit untuk Stage 2 classification."""
    CONFIRMED = "confirmed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class ExploitConfirmRequest(BaseModel):
    """Request body untuk POST /confirm — menerima exploit feedback dari Orchestrator."""
    audit_id: str
    finding_id: str
    exploit_successful: bool
    tx_hash: str | None = None
    exploit_duration: float | None = None
    attack_type: str | None = None
    hypotheses_tried: int | None = None


class ExploitFeedbackRecord(BaseModel):
    """Record of exploit feedback for learning."""
    feedback_id: str
    finding_id: str
    audit_id: str
    exploit_successful: bool
    original_classification: str
    new_classification: str
    tx_hash: str | None = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class Meta(BaseModel):
    """Standard response metadata."""

    status: Literal["ok", "error"] = "ok"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class ApiResponse(BaseModel):
    """Standard Vyper API response envelope."""

    data: Any
    meta: Meta = Field(default_factory=Meta)


class ErrorResponse(BaseModel):
    """Error response envelope."""

    data: None = None
    meta: Meta


class HealthResponse(BaseModel):
    """Response model for the health check endpoint."""

    status: str = "ok"
    service: str = "classifier"
    version: str = "0.1.0"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
