"""Pydantic models for Antonio Agent Service."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum, StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

# ── Agent Task & Session ───────────────────────────────────


class AgentRole(StrEnum):
    """Roles in the Vyper Audit Team organization."""

    LEAD_AUDITOR = "lead_auditor"
    INTEL_AGENT = "intel_agent"
    SCANNER_OPERATOR = "scanner_operator"
    VULNERABILITY_ANALYST = "vulnerability_analyst"
    EXPLOIT_ENGINEER = "exploit_engineer"
    QA_REVIEWER = "qa_reviewer"
    REPORT_MANAGER = "report_manager"


class TaskType(StrEnum):
    """Jenis task yang bisa dikerjakan agent."""

    CHAT = "chat"                    # Natural language chat — general ReAct
    FULL_AUDIT = "full_audit"
    SOURCE_SCAN = "source_scan"
    FINDING_ANALYSIS = "finding_analysis"
    EXPLOIT_TEST = "exploit_test"
    REPORT_GENERATE = "report_generate"
    PROGRAM_SYNC = "program_sync"


class AgentState(StrEnum):
    """State dalam ReAct loop."""

    PENDING = "pending"
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class AgentSession(BaseModel):
    """Satu session eksekusi agent — dari task sampai selesai."""

    session_id: str
    task_type: TaskType
    status: AgentState = AgentState.PENDING
    goal: str = ""  # Deskripsi tujuan dalam natural language
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    steps: list[AgentStep] = Field(default_factory=list)
    error: str | None = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class SubAgentState(BaseModel):
    """State of a sub-agent within a team session."""

    role: AgentRole
    status: AgentState = AgentState.PENDING
    task: str = ""
    summary: str = ""
    steps: list[AgentStep] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class TeamSession(BaseModel):
    """A team-based audit session with Lead Auditor + sub-agents."""

    team_session_id: str
    task_type: str  # Not TaskType enum to allow free-form
    goal: str = ""
    input_data: dict[str, Any] = Field(default_factory=dict)
    status: AgentState = AgentState.PENDING
    lead_steps: list[AgentStep] = Field(default_factory=list)
    sub_agents: dict[str, SubAgentState] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class AgentStep(BaseModel):
    """Satu langkah dalam agent loop: Think → Act → Observe."""

    step_number: int
    thought: str  # Apa yang agent pikirkan sebelum bertindak
    action: str  # Nama skill yang dipanggil
    action_input: dict[str, Any] = Field(default_factory=dict)
    observation: str = ""  # Hasil dari skill
    action_output: dict[str, Any] = Field(default_factory=dict)
    status: AgentState = AgentState.COMPLETED
    duration_ms: float = 0.0
    error: str | None = None


# ── Skill Definition ───────────────────────────────────────


class SkillDefinition(BaseModel):
    """Definisi sebuah skill yang bisa digunakan agent."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    examples: list[str] = Field(default_factory=list)


class SkillCall(BaseModel):
    """Panggilan ke sebuah skill."""

    skill_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class SkillResult(BaseModel):
    """Hasil dari eksekusi skill."""

    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0


# ── Memory ─────────────────────────────────────────────────


class MemoryEntry(BaseModel):
    """Satu entri dalam memory agent."""

    key: str
    content: Any
    type: Literal["episodic", "semantic", "working"] = "working"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── API Request/Response ───────────────────────────────────


class AgentRequest(BaseModel):
    """Request untuk memulai agent task."""

    task_type: TaskType
    input_data: dict[str, Any] = Field(default_factory=dict)
    goal: str = ""
    max_steps: int = 25


class AgentResponse(BaseModel):
    """Response dari agent task."""

    session_id: str
    status: AgentState
    steps: list[AgentStep] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


# ── Chat ────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    """Satu pesan dalam percakapan chat."""

    role: Literal["user", "assistant"] = "user"
    content: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class ChatRequest(BaseModel):
    """Request untuk chat dengan Antonio."""

    message: str = Field(..., min_length=1, description="Pesan natural language dari user")
    session_id: str | None = Field(None, description="Resume session yang sudah ada")


class ChatResponse(BaseModel):
    """Response dari chat Antonio."""

    session_id: str
    response: str                          # Natural language response
    steps_taken: int = 0                   # Jumlah ReAct steps
    status: AgentState = AgentState.COMPLETED
    error: str | None = None


# ── Standard Vyper Envelope ────────────────────────────────


class Meta(BaseModel):
    status: Literal["ok", "error"] = "ok"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    error: str | None = None


class ApiResponse(BaseModel):
    data: Any = None
    meta: Meta = Field(default_factory=Meta)


class HealthData(BaseModel):
    status: str = "ok"
    service: str = "agent"
    version: str = "0.1.0"
    active_sessions: int = 0
    skills_loaded: int = 0
    memory_entries: int = 0


class ErrorResponse(BaseModel):
    data: None = None
    meta: Meta


# ── Helpers ──────────────────────────────────────────────────


def to_serializable(obj: Any) -> Any:
    """Recursively convert objects to serializable dicts/lists."""
    if obj is None:
        return None
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_serializable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)
