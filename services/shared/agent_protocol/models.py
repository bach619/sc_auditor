from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AgentCapability(str, Enum):
    FETCH_PROGRAM = "fetch_program"
    FETCH_SOURCE = "fetch_source"
    RUN_STATIC_ANALYSIS = "run_static_analysis"
    RUN_FUZZING = "run_fuzzing"
    RUN_SYMBOLIC = "run_symbolic"
    RUN_FORGE = "run_forge"
    CLASSIFY_FINDINGS = "classify_findings"
    GENERATE_FIX = "generate_fix"
    DEEP_ANALYSIS = "deep_analysis"
    TEST_EXPLOIT = "test_exploit"
    GENERATE_POC = "generate_poc"
    GENERATE_REPORT = "generate_report"
    EXPORT_REPORT = "export_report"
    SEND_NOTIFICATION = "send_notification"
    MANAGE_WEBHOOK = "manage_webhook"
    SCHEDULE_TASKS = "schedule_tasks"
    SUBMIT_FINDING = "submit_finding"
    RUN_MANTICORE = "run_manticore"
    RUN_MYTHRIL_DEEP = "run_mythril_deep"
    EXPERIENCE_QUERY = "experience_query"


class AgentStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"
    STARTING = "starting"


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEFERRED = "deferred"


@dataclass
class CapabilityDefinition:
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    estimated_duration_ms: int = 0
    estimated_cost_usd: float = 0.0
    confidence: float = 0.0


@dataclass
class AgentManifest:
    service_name: str
    agent_role: str
    version: str
    capabilities: list[CapabilityDefinition] = field(default_factory=list)
    constraints: dict = field(default_factory=dict)
    current_load: dict = field(default_factory=dict)
    skills: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Convert capabilities from JSON dicts to CapabilityDefinition objects."""
        converted: list[CapabilityDefinition] = []
        for cap in self.capabilities:
            if isinstance(cap, dict):
                converted.append(CapabilityDefinition(**cap))
            elif isinstance(cap, CapabilityDefinition):
                converted.append(cap)
        self.capabilities = converted


@dataclass
class DelegationRequest:
    task_id: str
    goal: str
    capability: AgentCapability
    input_data: dict = field(default_factory=dict)
    constraints: dict = field(default_factory=dict)
    parent_session_id: str = ""
    priority: TaskPriority = TaskPriority.NORMAL


@dataclass
class DelegationResponse:
    task_id: str
    status: TaskStatus
    output: Any = None
    error: str | None = None
    confidence: float = 0.0
    cost_usd: float = 0.0
    duration_ms: int = 0
    steps_taken: list[dict] = field(default_factory=list)
    reflection: str = ""

    def __post_init__(self) -> None:
        """Convert status from string to TaskStatus enum if needed."""
        if isinstance(self.status, str):
            self.status = TaskStatus(self.status)


@dataclass
class NegotiationRequest:
    task_description: str
    required_capability: AgentCapability
    estimated_complexity: str = "medium"
    budget_usd: float = 0.0
    deadline_seconds: int = 0


@dataclass
class NegotiationResponse:
    can_handle: bool
    alternative_suggestion: str = ""
    estimated_duration_ms: int = 0
    estimated_cost_usd: float = 0.0
    estimated_confidence: float = 0.0
    reasoning: str = ""


@dataclass
class PeerRequest:
    request_id: str
    need: str
    context: dict = field(default_factory=dict)
    urgency: str = "normal"
    parent_session_id: str = ""


@dataclass
class PeerResponse:
    request_id: str
    success: bool
    result: Any = None
    error: str | None = None
    duration_ms: int = 0


@dataclass
class DelegationStep:
    step_number: int
    task_id: str
    target_agent: str
    capability: AgentCapability
    goal: str
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str | None = None
    duration_ms: int = 0
    cost_usd: float = 0.0
    started_at: str | None = None
    completed_at: str | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_task_id() -> str:
    return uuid.uuid4().hex[:12]


def agent_http_client(base_url: str, timeout: float = 30.0) -> Any:
    """Create an HTTP client for agent-to-agent communication.

    Note:
        ``httpx`` and ``structlog`` are imported lazily here so that
        the pure data-model definitions can be imported without needing
        those dependencies installed (important for test environments
        and import-time validation).
    """
    import httpx
    import structlog

    structlog.get_logger(__name__).debug(
        "creating_agent_http_client", base_url=base_url, timeout=timeout
    )
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(timeout),
        headers={"Content-Type": "application/json"},
    )
