"""Pydantic v2 models for the Orchestrator Service."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class PipelineState(str, Enum):
    """All possible pipeline states — both active and failure."""

    # ── Workflow states ──
    PENDING = "PENDING"
    FETCHING_PROGRAM = "FETCHING_PROGRAM"
    FETCHING_SOURCE = "FETCHING_SOURCE"
    SCANNING = "SCANNING"
    INTELLIGENCE_CORRELATION = "INTELLIGENCE_CORRELATION"
    AI_ANALYSIS = "AI_ANALYSIS"
    CLASSIFYING = "CLASSIFYING"
    EXPLOITING = "EXPLOITING"
    REPORTING = "REPORTING"
    NOTIFYING = "NOTIFYING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARN = "COMPLETED_WITH_WARN"

    # ── Failure states ──
    FETCH_FAILED = "FETCH_FAILED"
    SCAN_FAILED = "SCAN_FAILED"
    INTEL_CORRELATION_FAILED = "INTEL_CORRELATION_FAILED"
    AI_FAILED = "AI_FAILED"
    CLASSIFY_FAILED = "CLASSIFY_FAILED"
    EXPLOIT_FAILED = "EXPLOIT_FAILED"
    REPORT_FAILED = "REPORT_FAILED"
    NOTIFY_FAILED = "NOTIFY_FAILED"
    TIMEOUT = "TIMEOUT"
    UNKNOWN_FAILED = "UNKNOWN_FAILED"

    @property
    def is_terminal(self) -> bool:
        return self in {
            PipelineState.COMPLETED,
            PipelineState.COMPLETED_WITH_WARN,
            PipelineState.FETCH_FAILED,
            PipelineState.SCAN_FAILED,
            PipelineState.INTEL_CORRELATION_FAILED,
            PipelineState.AI_FAILED,
            PipelineState.CLASSIFY_FAILED,
            PipelineState.EXPLOIT_FAILED,
            PipelineState.REPORT_FAILED,
            PipelineState.NOTIFY_FAILED,
            PipelineState.TIMEOUT,
            PipelineState.UNKNOWN_FAILED,
        }

    @property
    def is_failure(self) -> bool:
        return self.is_terminal and self not in (PipelineState.COMPLETED, PipelineState.COMPLETED_WITH_WARN)


class AuditPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DaemonStatus(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


# ──────────────────────────────────────────────
# Pipeline step record
# ──────────────────────────────────────────────

class PipelineStep(BaseModel):
    name: str
    state: PipelineState
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    retry_count: int = 0
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

    @property
    def elapsed(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


# ──────────────────────────────────────────────
# Audit record
# ──────────────────────────────────────────────

class AuditRequest(BaseModel):
    chain: str = Field(..., description="Blockchain name, e.g. ethereum")
    address: str = Field(..., description="Contract address (0x-prefixed)")
    program: str = Field(default="", description="Immunefi program slug")
    priority: int = Field(default=5, ge=0, le=10, description="Priority 0-10")
    use_ai: bool = Field(default=True, description="Enable LLM-based AI analysis via 06-ai")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AuditRecord(BaseModel):
    audit_id: str = Field(default_factory=lambda: str(uuid4()))
    chain: str
    address: str
    program: str = ""
    priority: int = 5
    use_ai: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    state: PipelineState = PipelineState.PENDING
    steps: List[PipelineStep] = Field(default_factory=list)
    error: Optional[str] = None
    findings: Optional[Dict[str, Any]] = None
    report_path: Optional[str] = None
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    partial_results: Dict[str, str] = Field(
        default_factory=dict,
        description="Maps step name → success|skipped|degraded|failed",
    )

    def add_step(self, step: PipelineStep) -> None:
        self.steps.append(step)
        self.state = step.state
        self.updated_at = datetime.utcnow()

    def fail(self, state: PipelineState, error: str) -> None:
        self.state = state
        self.error = error
        self.updated_at = datetime.utcnow()

    def complete(self, duration: float) -> None:
        self.state = PipelineState.COMPLETED
        self.duration_seconds = duration
        self.updated_at = datetime.utcnow()


# ──────────────────────────────────────────────
# Queue items
# ──────────────────────────────────────────────

class QueueItem(BaseModel):
    contract_id: str  # chain:address
    chain: str
    address: str
    program: str = ""
    priority_score: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_audited_at: Optional[datetime] = None
    skip_reason: Optional[str] = None


# ──────────────────────────────────────────────
# Daemon state
# ──────────────────────────────────────────────

class DaemonState(BaseModel):
    status: DaemonStatus = DaemonStatus.STOPPED
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    total_contracts_audited: int = 0
    total_cycles_completed: int = 0
    last_error: Optional[str] = None


# ──────────────────────────────────────────────
# Response envelope
# ──────────────────────────────────────────────

class ApiResponse(BaseModel):
    data: Any = None
    meta: Dict[str, Any] = Field(
        default_factory=lambda: {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
    )


# ──────────────────────────────────────────────
# Statistics
# ──────────────────────────────────────────────

class PipelineStats(BaseModel):
    total_audits: int = 0
    completed: int = 0
    failed: int = 0
    in_progress: int = 0
    success_rate: float = 0.0
    avg_duration_seconds: Optional[float] = None
    by_state: Dict[str, int] = Field(default_factory=dict)
    by_program: Dict[str, int] = Field(default_factory=dict)
    timeouts: int = 0
    last_updated: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# Rerun request
# ──────────────────────────────────────────────

class RerunRequest(BaseModel):
    audit_ids: List[str] = Field(default_factory=list)
    address: Optional[str] = None
    chain: Optional[str] = None
    pattern_type: Optional[str] = None  # e.g. "false_negative", "reentrancy"
    reason: str = "manual_rerun"
