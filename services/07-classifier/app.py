"""Vyper Classifier Service — FastAPI microservice.

Classifies AI-analyzed findings as TP/FP/TN/FN using rules, historical
patterns, and human feedback. Tracks accuracy metrics and continuously
improves via the PatternLearner.

Endpoints
──────────
- GET  /health       — Health check
- POST /classify      — Classify findings
- GET  /metrics       — Classification accuracy metrics
- POST /feedback      — Submit human feedback
- GET  /patterns      — List learned vulnerability patterns
- POST /reclassify    — Reclassify using latest patterns

Data stored at ``/data/classifier/`` (findings, patterns, metrics).
Learning data shared at ``/data/learning/`` (feedback, FN/FP records).
"""

from __future__ import annotations

import asyncio
import signal
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Any

from shared.observability import setup_observability
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


from src.classify import Classifier
from src.improver import PatternLearner
from src.metrics import MetricsTracker
from src.models import (
    ApiResponse,
    Classification,
    ClassificationLayer,
    ClassificationSource,
    ClassificationStage,
    ErrorResponse,
    Feedback,
    FeedbackStatus,
    FeedbackRequest,
    Finding,
    HealthResponse,
    Meta,
    ClassifyRequest,
    ReclassifyRequest,
)




# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------


class AppState:
    """Shared application state injected via ``request.app.state``."""

    def __init__(self) -> None:
        self.pattern_learner: PatternLearner = PatternLearner()
        self.classifier: Classifier = Classifier(
            pattern_learner=self.pattern_learner
        )
        self.metrics_tracker: MetricsTracker = MetricsTracker()
        self._shutdown_requested: bool = False

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def request_shutdown(self) -> None:
        self._shutdown_requested = True


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Handle startup and shutdown lifecycle."""
    # ---- startup ----
    state = AppState()
    app.state.vyper = state

    log.info(
        "classifier_service_started",
        version="0.1.0",
        patterns=len(state.pattern_learner.get_patterns()),
    )

    # Register signal handlers for graceful shutdown
    loop = None
    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):

            def _handler(sig: int, frame: Any = None) -> None:
                log.info("received_signal", signal=sig)
                state.request_shutdown()

            loop.add_signal_handler(sig, _handler, sig)
    except NotImplementedError:
        log.info("signal_handlers_not_available_on_windows")

    yield  # ---- application runs here ----

    # ---- shutdown ----
    log.info("classifier_service_shutting_down")
    # Metrics and patterns are persisted on every write, no flush needed
    log.info("classifier_service_stopped")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Vyper Classifier Service",
    description=(
        "Classifies AI-analyzed findings as True/False Positive/Negative, "
        "tracks accuracy metrics, and learns from human feedback."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# -- Middleware --------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


log = setup_observability(app, "07-classifier", "0.1.0")

# -- Exception handlers -----------------------------------------------------
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions — return a Vyper error envelope."""
    log.exception("unhandled_exception", path=str(request.url))
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(meta=Meta(status="error")).model_dump(),
    )


# ===========================================================================
# Routes
# ===========================================================================


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint.

    Returns a simple status payload indicating the service is alive.
    """
    return HealthResponse()


@app.post("/classify", response_model=ApiResponse)
async def classify_endpoint(
    request: Request, body: ClassifyRequest
) -> ApiResponse:
    """Classify audit findings.

    Accepts a list of raw findings from the scan pipeline and returns
    each finding with its TP/FP/TN/FN classification appended as a new
    classification layer.

    The original finding data is preserved (non-destructive classification).
    """
    state: AppState = request.app.state.vyper
    classifier: Classifier = state.classifier
    metrics: MetricsTracker = state.metrics_tracker

    # Convert raw dicts to Finding models
    findings = [
        _raw_to_finding(raw, body.audit_id)
        for raw in body.findings
    ]

    # Classify all findings
    classified = classifier.classify_all(findings)

    # Record metrics for each classification
    results: list[dict[str, Any]] = []
    for finding in classified:
        tool_name = finding.tool.name if finding.tool else None

        results.append({
            "finding_id": finding.finding_id,
            "title": finding.title,
            "severity": finding.severity.value if finding.severity else None,
            "current_stage": finding.current_stage.value,
            "classification": finding.current_classification.value,
            "confidence": finding.current_confidence,
            "layers": [
                {
                    "stage": l.stage.value,
                    "classification": l.classification.value,
                    "confidence": l.confidence,
                    "reasoning": l.reasoning,
                    "timestamp": l.timestamp,
                }
                for l in finding.classification_layers
            ],
        })

    log.info(
        "classify_complete",
        audit_id=body.audit_id,
        findings=len(results),
    )

    return ApiResponse(data={"audit_id": body.audit_id, "findings": results})


@app.get("/metrics", response_model=ApiResponse)
async def get_metrics(request: Request) -> ApiResponse:
    """Return classification accuracy metrics.

    Includes TP/FP/TN/FN counts, precision, recall, F1 score, accuracy,
    overall quality score, per-tool breakdowns, and 30-day trend data.
    """
    state: AppState = request.app.state.vyper
    metrics: MetricsTracker = state.metrics_tracker

    return ApiResponse(
        data={
            "summary": metrics.get_metrics(),
            "by_tool": metrics.get_tool_metrics(),
            "trend": metrics.get_trend(days=30),
        }
    )


@app.post("/feedback", response_model=ApiResponse)
async def submit_feedback(
    request: Request, body: FeedbackRequest
) -> ApiResponse:
    """Submit human feedback on a classification.

    Feedback follows a confirmation workflow:
    1. Initial — feedback is recorded but not yet applied
    2. Reviewed — Orchestrator has reviewed the feedback
    3. Finalized — Feedback is accepted and triggers learning

    When feedback is submitted, the PatternLearner extracts patterns from
    corrections (especially FN and FP discoveries) to improve future
    classifications.
    """
    state: AppState = request.app.state.vyper
    pattern_learner: PatternLearner = state.pattern_learner
    metrics: MetricsTracker = state.metrics_tracker
    classifier: Classifier = state.classifier

    # Retrieve the original finding to compare
    original_finding_data = classifier.get_finding(body.finding_id)
    original_classification: Classification | None = None
    tool_name: str | None = None

    if original_finding_data:
        original_finding = Finding(**original_finding_data)
        original_classification = original_finding.current_classification
        if original_finding.tool:
            tool_name = original_finding.tool.name

    # Create feedback record
    feedback = Feedback(
        feedback_id=str(uuid.uuid4()),
        finding_id=body.finding_id,
        audit_id=body.audit_id,
        correct_classification=body.correct_classification,
        original_classification=original_classification,
        notes=body.notes,
        status=FeedbackStatus.INITIAL,
    )

    # Update metrics with this feedback (assume feedback is ground truth)
    is_correct = (
        original_classification == body.correct_classification
    )
    metrics.record(
        finding_id=body.finding_id,
        classification=original_classification or Classification.UNKNOWN,
        is_correct=is_correct,
        tool_name=tool_name,
    )

    # Trigger learning from feedback
    if not is_correct and original_classification is not None:
        # This is a correction — learn from it
        created_pattern = pattern_learner.learn_from_feedback(feedback)
        if created_pattern:
            log.info(
                "pattern_created_from_feedback",
                pattern_id=created_pattern.pattern_id,
                classification=created_pattern.classification.value,
            )

    log.info(
        "feedback_submitted",
        feedback_id=feedback.feedback_id,
        finding_id=body.finding_id,
        classification=body.correct_classification.value,
        is_correction=not is_correct,
    )

    return ApiResponse(
        data={
            "feedback_id": feedback.feedback_id,
            "finding_id": body.finding_id,
            "correct_classification": body.correct_classification.value,
            "original_classification": (
                original_classification.value if original_classification else None
            ),
            "is_correction": not is_correct,
            "pattern_created": created_pattern is not None if not is_correct else False,
            "status": feedback.status.value,
        }
    )


@app.get("/patterns", response_model=ApiResponse)
async def list_patterns(request: Request) -> ApiResponse:
    """List all learned vulnerability patterns.

    Returns patterns sorted by effectiveness score (descending), with
    match counts, accuracy, and activation status.
    """
    state: AppState = request.app.state.vyper
    pattern_learner: PatternLearner = state.pattern_learner

    patterns = pattern_learner.get_patterns()
    return ApiResponse(
        data={
            "total_patterns": len(patterns),
            "active_patterns": sum(1 for p in patterns if p["is_active"]),
            "patterns": patterns,
        }
    )


@app.post("/reclassify", response_model=ApiResponse)
async def reclassify_endpoint(
    request: Request, body: ReclassifyRequest | None = None
) -> ApiResponse:
    """Reclassify findings using the latest learned patterns.

    Triggered when new patterns have been learned. Can be scoped to a
    specific audit or set of finding IDs. Returns reclassification records
    showing what changed.
    """
    state: AppState = request.app.state.vyper
    classifier: Classifier = state.classifier

    audit_id = body.audit_id if body else None
    finding_ids = body.finding_ids if body else None

    reclassified = classifier.reclassify(
        audit_id=audit_id,
        finding_ids=finding_ids,
    )

    changed = sum(1 for r in reclassified if r["changed"])
    log.info(
        "reclassification_triggered",
        total=len(reclassified),
        changed=changed,
    )

    return ApiResponse(
        data={
            "total_reclassified": len(reclassified),
            "changed": changed,
            "unchanged": len(reclassified) - changed,
            "details": reclassified,
        }
    )


# ===========================================================================
# Internal helpers
# ===========================================================================


def _raw_to_finding(raw: dict[str, Any], audit_id: str) -> Finding:
    """Convert a raw finding dict from the API into a Finding model."""
    from src.models import Severity

    finding_id = raw.get("finding_id", str(uuid.uuid4()))
    ai_confidence = raw.get("ai_confidence") or raw.get("confidence")

    return Finding(
        finding_id=finding_id,
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
        ai_confidence=ai_confidence,
        ai_verdict=(
            Classification(raw["ai_verdict"]) if raw.get("ai_verdict") else None
        ),
    )


# ===========================================================================
# Entry point
# ===========================================================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8005,
        log_level="info",
        reload=False,
    )
