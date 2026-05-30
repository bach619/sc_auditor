"""
VYPER TUI v2 — Panel 5: Orchestration & Agent Layer

2 service kontrol pipeline, masing-masing sebagai mini-window:
  - 11-Orchestrator  (8009) — State machine pipeline, priority queue, retry
  - 14-Agent         (8021) — Antonio ReAct agent, team mode, daemon scheduler

Fitur per-window: queue depth, slot usage, daemon cycle, team tree.
"""

from __future__ import annotations

import logging
from typing import Any

from cli.src.core.state_store import AppState, DaemonStatus, TeamMember
from cli.src.panels.base_layer_panel import LayerPanel

logger = logging.getLogger("vyper_tui.panels.layer5")


class OrchestrationAgentPanel(LayerPanel):
    """
    Layer 5 — Orchestration & Agent Panel.
    Dual-service: orchestrator (11) dan agent (14).
    """

    PANEL_TITLE = "L5: ORCHESTRATION & AGENT"
    SERVICES = [
        ("11-orchestrator", 8009),
        ("14-agent",        8021),
    ]

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._is_expanded = False
        self._is_team_mode = False

    def on_mount(self) -> None:
        super().on_mount()
        if self._event_bus:
            self._register_orchestration_handlers()

    # ── Event Handlers ──────────────────────────────────────────────────

    def _register_orchestration_handlers(self) -> None:
        """Register semua event handler untuk Layer 5."""

        @self._event_bus.on("service.activity")
        async def _on_activity(event: Any) -> None:
            if event.service in ("11-orchestrator", "14-agent"):
                self.refresh()

        @self._event_bus.on("resource.slot_change")
        async def _on_slots(event: Any) -> None:
            orch = AppState.get().orchestrator_state
            if orch:
                slot_type = event.payload.get("slot_type", "")
                used = event.payload.get("used", 0)
                max_val = event.payload.get("max", 2)
                if slot_type == "scanner":
                    orch.scanner_slots = (used, max_val)
                elif slot_type == "ai":
                    orch.ai_slots = (used, max_val)
                elif slot_type == "exploit":
                    orch.exploit_slots = (used, max_val)
            self.refresh()

        @self._event_bus.on("agent.step")
        async def _on_step(event: Any) -> None:
            ops = AppState.get().agent_operational
            if ops:
                ops.current_step = event.payload.get("step_number")
                ops.total_steps = event.payload.get("total_steps")
            self.refresh()

        @self._event_bus.on("agent.skill_call")
        async def _on_skill(event: Any) -> None:
            ops = AppState.get().agent_operational
            if ops:
                ops.current_skill = event.payload.get("skill_name")
                ops.skill_elapsed_s = 0
            self.refresh()

        @self._event_bus.on("agent.observation")
        async def _on_observe(event: Any) -> None:
            ops = AppState.get().agent_operational
            if ops:
                ops.current_skill = None
                ops.skill_elapsed_s = None
            self.refresh()

        @self._event_bus.on("agent.delegation")
        async def _on_delegation(event: Any) -> None:
            ops = AppState.get().agent_operational
            if ops and ops.team_members:
                target = event.payload.get("target_agent", "")
                task = event.payload.get("task_summary", "")
                for member in ops.team_members:
                    if member.name.lower() in target.lower():
                        member.status = "running"
                        member.current_task = task
                self._is_team_mode = True
            self.refresh()

        @self._event_bus.on("agent.team_started")
        async def _on_team_start(event: Any) -> None:
            self._is_team_mode = True
            self._is_expanded = True
            members_data = event.payload.get("team_members", [])
            ops = AppState.get().agent_operational
            if ops and members_data:
                ops.team_members = [
                    TeamMember(name=m.get("name", "?"), status="idle")
                    for m in members_data
                ]
            self.refresh()

        @self._event_bus.on("agent.team_completed")
        async def _on_team_complete(event: Any) -> None:
            self._is_team_mode = False
            self._is_expanded = False
            self.refresh()

        @self._event_bus.on("daemon.cycle")
        async def _on_daemon(event: Any) -> None:
            ops = AppState.get().agent_operational
            if ops:
                if not ops.daemon_status:
                    ops.daemon_status = DaemonStatus()
                ops.daemon_status.cycle = event.payload.get("cycle", 0)
                ops.daemon_status.status = event.payload.get("status", "running")
            self.refresh()

    # ── Keyboard ────────────────────────────────────────────────────────

    def on_key(self, event: Any) -> None:
        """Extended: Enter toggle expand, q, d, m, b, p."""
        super().on_key(event)
        key = getattr(event, "key", None)

        if key == "enter":
            self._is_expanded = not self._is_expanded
            self.refresh()
        elif key == "q":
            logger.info("Queue overlay requested")
        elif key == "d":
            logger.info("Delegation chain requested")
        elif key == "m":
            logger.info("Memory panel requested")
        elif key == "b":
            logger.info("Boost priority requested")
        elif key == "p":
            logger.info("Pause queue requested")

    # ── Extra Lines per Service ─────────────────────────────────────────

    def _orchestrator_extra(self) -> list[str]:
        """Extra lines untuk 11-Orchestrator."""
        state = AppState.get()
        orch = state.orchestrator_state
        if not orch:
            return []

        lines: list[str] = []

        if not self._is_expanded:
            n_active = len(orch.active_audit_ids)
            slots_str = (
                f"scan:{orch.scanner_slots[0]}/{orch.scanner_slots[1]}  "
                f"ai:{orch.ai_slots[0]}/{orch.ai_slots[1]}  "
                f"exp:{orch.exploit_slots[0]}/{orch.exploit_slots[1]}"
            )
            lines.append(f"{orch.status.upper()}  {n_active} audit(s)  q:{orch.queue_size}")
            lines.append(f"Slots: {slots_str}")
            return lines

        # ── Expanded view ──
        lines.append(f"\u250c\u2500 {orch.status.upper()} \u2500\u2500\u2500\u2510")

        # Active pipelines
        for aid in orch.active_audit_ids[:3]:
            record = state.active_audits.get(aid)
            if record:
                bar = self._render_progress_bar(record.progress, width=8)
                addr_short = (record.contract_address or "?")[:8]
                lines.append(
                    f"\u2502  {aid}  [{record.state:<15}] "
                    f"{bar} {record.progress}%  {addr_short}"
                )

        # Retry queue
        if orch.retry_queue:
            lines.append(f"RETRY QUEUE:")
            for item in orch.retry_queue[:2]:
                lines.append(
                    f"  {item.audit_id}  {item.failed_stage} "
                    f"\u2192 retry #{item.retry_number}"
                )

        return lines

    def _agent_extra(self) -> list[str]:
        """Extra lines untuk 14-Agent."""
        state = AppState.get()
        ops = state.agent_operational
        if not ops:
            return []

        lines: list[str] = []

        # ── Daemon Mode ──
        if ops.mode == "daemon" and ops.daemon_status:
            ds = ops.daemon_status
            task = getattr(ds, "current_task", "monitoring") or "monitoring"
            lines.append(f"DAEMON Cycle #{ds.cycle}  {task}")
            return lines

        # ── Team Mode ──
        if ops.mode == "team" and self._is_team_mode and ops.team_members:
            lines.append(f"LEAD Coordinating team audit")
            for m in ops.team_members:
                m_icon = {"idle": "\U0001f4a4", "running": "\u28fe",
                          "done": "\u2705"}.get(m.status, "?")
                task_str = f"  {m.current_task[:30]}" if m.current_task else ""
                lines.append(f"\u251c {m.name:<15} {m_icon}{task_str}")
            return lines

        # ── Full Audit / Idle ──
        if ops.mode in ("full_audit", "idle") and ops.session_id:
            step_str = (
                f"step:{ops.current_step}/{ops.total_steps}"
                if ops.current_step else "idle"
            )
            skill_str = ""
            if ops.current_skill:
                skill_str = f"  skill:{ops.current_skill} \u28fe"
            lines.append(f"{ops.session_id}  {step_str}{skill_str}")
        else:
            lines.append(f"LLM: {ops.llm_model}")

        return lines

    # ── Render ──────────────────────────────────────────────────────────

    def render(self) -> str:
        lines: list[str] = []

        suffix = ""
        if self._is_expanded:
            suffix += " \u25b2 EXPANDED"
        if self._is_team_mode:
            suffix += " \U0001f916 TEAM MODE"

        lines.append(self._render_panel_header(self.PANEL_TITLE, suffix))

        # ── 11-Orchestrator ──
        activity11 = AppState.get().service_activities.get("11-orchestrator")
        healthy11 = AppState.get().service_health.get("11-orchestrator")
        spark11 = AppState.get().service_sparklines.get("11-orchestrator", [])
        w11 = self._render_service_window(
            "11-orchestrator", 8009, activity11, healthy11, spark11,
            is_focused=(0 == self._focused_idx),
            extra_lines=self._orchestrator_extra() or None,
        )
        lines.extend(w11)

        # ── 14-Agent ──
        activity14 = AppState.get().service_activities.get("14-agent")
        healthy14 = AppState.get().service_health.get("14-agent")
        spark14 = AppState.get().service_sparklines.get("14-agent", [])
        w14 = self._render_service_window(
            "14-agent", 8021, activity14, healthy14, spark14,
            is_focused=(1 == self._focused_idx),
            extra_lines=self._agent_extra() or None,
        )
        lines.extend(w14)

        lines.append(self._render_panel_footer())
        return "\n".join(lines)
