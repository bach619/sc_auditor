"""
VYPER TUI v2 — StateStore

Central reactive state — single source of truth untuk seluruh TUI.
Semua panel membaca dari AppState, tidak ada panel yang menyimpan
state sendiri.

Pattern Singleton:
    AppState.get()        → VyperState instance saat ini
    AppState.update(...)  → update fields + trigger notifikasi

Alur:
    EventBus → EventHandler → AppState.update() → StateUpdated → Panel.refresh()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, ClassVar

from cli.src.models.activity import ServiceActivity

logger = logging.getLogger("vyper_tui.state_store")


@dataclass
class DaemonStatus:
    """Status Antonio Daemon."""
    status: str = "idle"          # idle | running | error
    uptime: str = ""
    cycle: int = 0
    sessions_today: int = 0
    findings: int = 0
    tp: int = 0
    fp: int = 0


@dataclass
class AgentSession:
    """Sesi aktif Antonio ReAct."""
    session_id: str = ""
    task: str = ""
    step: int = 0
    total_steps: int = 0
    llm_model: str = ""


@dataclass
class MemoryStats:
    """Statistik memory Antonio."""
    working_keys: int = 0
    vector_entries: int = 0
    episodic_events: int = 0
    graph_nodes: int = 0
    last_stored: str = ""


@dataclass
class AuditRecord:
    """Satu record audit aktif."""
    audit_id: str = ""
    contract_address: str = ""
    chain: str = ""
    program: str = ""
    state: str = "pending"
    progress: int = 0
    findings_count: int = 0
    estimated_tp: int = 0


@dataclass
class QueueItem:
    """Item dalam priority queue."""
    rank: int = 0
    audit_id: str = ""
    contract_address: str = ""
    score: float = 0.0
    wait_time: str = ""
    program: str = ""


@dataclass
class ResourceSlots:
    """Slot resource governor."""
    scanner_used: int = 0
    scanner_max: int = 2
    ai_used: int = 0
    ai_max: int = 3
    exploit_used: int = 0
    exploit_max: int = 1
    timeout_scanner: int = 900
    timeout_ai: int = 120
    timeout_exploit: int = 300


@dataclass
class ToolMetrics:
    """Metrics per tool dalam confusion matrix."""
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0


@dataclass
class AgentProtocolState:
    """State Agent Protocol registry."""
    agents: list[dict] = field(default_factory=list)
    delegations: list[dict] = field(default_factory=list)


# ── Layer 4: Exploit & Output ────────────────────────────────────────────

@dataclass
class ExploitState:
    """State exploit engine untuk satu audit."""
    audit_id: str = ""
    finding_id: str = ""
    finding_type: str = ""
    status: str = "idle"               # idle | running | confirmed | failed | no_exploit
    current_phase: int = 0             # 1–5
    phase_results: dict = field(default_factory=dict)
    expected_profit_usd: float | None = None
    confirmed_profit_usd: float | None = None
    tx_hash: str | None = None
    attacker_contract: str | None = None
    fork_block: int | None = None
    chain: str = "ethereum"
    started_at: str | None = None
    duration_s: float | None = None


@dataclass
class ReportState:
    """State laporan audit."""
    audit_id: str = ""
    status: str = "idle"               # idle | generating | ready | failed
    files: list[str] = field(default_factory=list)
    progress: int = 0
    generated_at: str | None = None


@dataclass
class NotificationState:
    """State notifikasi untuk satu audit."""
    audit_id: str = ""
    status: str = "idle"               # idle | pending | sent | failed
    channels: dict = field(default_factory=dict)
    sent_at: str | None = None


# ── Layer 5: Orchestration & Agent ──────────────────────────────────────

@dataclass
class RetryItem:
    """Item dalam retry queue orchestrator."""
    audit_id: str = ""
    failed_stage: str = ""
    retry_number: int = 0
    scheduled_at: str = ""


@dataclass
class OrchestratorState:
    """State operasional 11-Orchestrator."""
    status: str = "idle"               # idle | busy | error
    active_audit_ids: list[str] = field(default_factory=list)
    queue_size: int = 0
    scanner_slots: tuple[int, int] = (0, 2)
    ai_slots: tuple[int, int] = (0, 3)
    exploit_slots: tuple[int, int] = (0, 1)
    retry_queue: list[RetryItem] = field(default_factory=list)
    uptime_s: float = 0.0


@dataclass
class TeamMember:
    """Sub-agent dalam team mode."""
    name: str = ""                     # "Code Analyst", "Exploit Spec", dll
    status: str = "idle"               # idle | running | done | failed
    current_task: str | None = None
    progress: int | None = None


@dataclass
class AgentOperationalState:
    """State operasional 14-Agent (berbeda dari AgentSession yg fokus ReAct)."""
    session_id: str | None = None
    mode: str = "idle"                 # idle | full_audit | team | daemon
    current_step: int | None = None
    total_steps: int | None = None
    current_skill: str | None = None
    skill_elapsed_s: int | None = None
    llm_model: str = "claude-sonnet-4-6"
    skills_used: list[str] = field(default_factory=list)
    daemon_status: DaemonStatus | None = None
    team_members: list[TeamMember] | None = None


# ── Layer 6: Infra & Delivery ──────────────────────────────────────────

@dataclass
class WebhookItem:
    """Satu item webhook inbound."""
    source: str = ""                   # immunefi | alchemy | custom
    event_type: str = ""
    summary: str = ""
    received_at: str = ""
    status: str = "pending"            # pending | processed | failed


@dataclass
class WebhookState:
    """State 12-Webhook service."""
    status: str = "idle"               # idle | busy | error
    pending_queue: list[WebhookItem] = field(default_factory=list)
    last_received: WebhookItem | None = None
    events_processed_today: int = 0


@dataclass
class UpkeepState:
    """State 13-Upkeep service."""
    status: str = "idle"               # idle | busy
    current_task: str | None = None
    task_progress: int | None = None
    disk_usage_pct: float = 0.0
    disk_freed_gb: float | None = None
    next_scheduled: dict = field(default_factory=dict)


@dataclass
class DashboardInfraState:
    """State infrastruktur 15-Dashboard (SSE hub)."""
    sse_client_count: int = 0
    events_published_hr: int = 0
    last_event_at: str | None = None
    health: bool = True


@dataclass
class SubmissionState:
    """State 16-Submission service."""
    audit_id: str | None = None
    status: str = "idle"               # idle | running | completed | failed
    current_step: int = 0              # 1–4
    step_results: dict = field(default_factory=dict)
    submission_id: str | None = None
    submitted_at: str | None = None
    error_msg: str | None = None
    queue: list[str] = field(default_factory=list)


@dataclass
class VyperState:
    """
    Central reactive state. Semua panel subscribe ke state ini.
    Tidak ada panel yang menyimpan state sendiri.
    """

    # ── Service states ──────────────────────────────────────────────────
    service_activities: dict[str, ServiceActivity] = field(default_factory=dict)
    service_health: dict[str, bool] = field(default_factory=dict)
    service_sparklines: dict[str, list[int]] = field(default_factory=dict)

    # ── Pipeline states ─────────────────────────────────────────────────
    active_audits: dict[str, AuditRecord] = field(default_factory=dict)
    pipeline_queue: list[QueueItem] = field(default_factory=list)

    # ── Antonio state ───────────────────────────────────────────────────
    active_session: AgentSession | None = None
    daemon_status: DaemonStatus | None = None
    memory_stats: MemoryStats | None = None
    agent_protocol: AgentProtocolState | None = None

    # ── ReAct steps buffer ──────────────────────────────────────────────
    react_steps: list[dict] = field(default_factory=list)

    # ── Resource governor ───────────────────────────────────────────────
    resource_slots: ResourceSlots | None = None

    # ── Metrics ─────────────────────────────────────────────────────────
    classifier_metrics: dict[str, ToolMetrics] = field(default_factory=dict)
    tool_metrics: dict[str, ToolMetrics] = field(default_factory=dict)

    # ── UI state ────────────────────────────────────────────────────────
    current_mode: str = "full"        # full | audit | agent | compact
    focused_panel: str = "chat"
    motion_enabled: bool = True
    spinner_frame: int = 0

    # ── Layer 4: Exploit & Output ────────────────────────────────────────
    active_exploits: dict[str, ExploitState] = field(default_factory=dict)
    report_states: dict[str, ReportState] = field(default_factory=dict)
    notification_states: dict[str, NotificationState] = field(default_factory=dict)

    # ── Layer 5: Orchestration & Agent ───────────────────────────────────
    orchestrator_state: OrchestratorState | None = None
    agent_operational: AgentOperationalState | None = None

    # ── Layer 6: Infra & Delivery ────────────────────────────────────────
    webhook_state: WebhookState | None = None
    upkeep_state: UpkeepState | None = None
    dashboard_infra: DashboardInfraState | None = None
    submission_state: SubmissionState | None = None

    # ── Config ──────────────────────────────────────────────────────────
    config: dict[str, Any] = field(default_factory=dict)


class AppState:
    """
    Singleton — satu instance per TUI.

    Usage:
        state = AppState.get()
        print(state.current_mode)

        AppState.update(current_mode="audit", motion_enabled=False)
    """

    _instance: VyperState | None = None
    _app: ClassVar[Any] = None
    _subscribers: ClassVar[list[Any]] = []

    @classmethod
    def initialize(cls, app: Any) -> None:
        """Set referensi Textual App dan reset state."""
        cls._app = app
        cls._instance = VyperState()
        cls._subscribers = []
        logger.debug("AppState initialized")

    @classmethod
    def get(cls) -> VyperState:
        """Dapatkan VyperState instance."""
        if cls._instance is None:
            cls._instance = VyperState()
        return cls._instance

    @classmethod
    def update(cls, **kwargs: Any) -> None:
        """
        Update fields di VyperState + trigger notifikasi ke subscriber.

        Args:
            **kwargs: Field name → value pairs untuk di-update
        """
        instance = cls._instance
        updated_fields = []

        for key, value in kwargs.items():
            if hasattr(instance, key):
                old_val = getattr(instance, key)
                setattr(instance, key, value)
                updated_fields.append(key)
                if old_val != value:
                    logger.debug("State updated: %s = %s", key, value)
            else:
                logger.warning("Unknown state field: %s", key)

        if updated_fields and cls._app:
            try:
                cls._app.post_message(
                    StateUpdated(fields=updated_fields)
                )
            except Exception:
                logger.exception("Failed to post StateUpdated message")

    @classmethod
    def subscribe(cls, panel: Any) -> None:
        """Daftarkan panel sebagai subscriber."""
        if panel not in cls._subscribers:
            cls._subscribers.append(panel)

    @classmethod
    def unsubscribe(cls, panel: Any) -> None:
        """Hapus panel dari subscriber."""
        if panel in cls._subscribers:
            cls._subscribers.remove(panel)


class StateUpdated:
    """
    Message yang dipost ke Textual app saat state berubah.
    Panel menerima ini di method on_state_updated().
    """

    def __init__(self, fields: list[str]):
        self.fields = fields
