"""
VYPER TUI v2 — Panel 6: Infra & Delivery Layer

4 service infrastruktur, masing-masing sebagai mini-window:
  - 12-Webhook    (8010) — Inbound webhook handler
  - 13-Upkeep     (8012) — Scheduled maintenance, cleanup, backup
  - 15-Dashboard  (8000) — SSE event hub, /metrics aggregator
  - 16-Submission (8018) — Immunefi submission automation

Fitur per-window: webhook queue, disk warning >85%, SSE disconnect, 4-step submission.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from cli.src.core.state_store import (
    AppState,
    DashboardInfraState,
    SubmissionState,
    UpkeepState,
    WebhookItem,
    WebhookState,
)
from cli.src.panels.base_layer_panel import LayerPanel

logger = logging.getLogger("vyper_tui.panels.layer6")

DISK_WARNING_THRESHOLD = 85.0


class InfraDeliveryPanel(LayerPanel):
    """
    Layer 6 — Infra & Delivery Panel.
    4 service: 12-Webhook, 13-Upkeep, 15-Dashboard, 16-Submission.
    """

    PANEL_TITLE = "L6: INFRA & DELIVERY"
    SERVICES = [
        ("12-webhook",    8010),
        ("13-upkeep",     8012),
        ("15-dashboard",  8000),
        ("16-submission", 8018),
    ]

    SUBMISSION_STEPS = [
        "Auth check",
        "Format report",
        "Upload attachments",
        "Submit form",
    ]

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._webhook_pending = False
        self._submission_running = False
        self._upkeep_running = False
        self._sse_disconnected = False

    def on_mount(self) -> None:
        super().on_mount()
        if self._event_bus:
            self._register_infra_handlers()

    # ── Event Handlers ──────────────────────────────────────────────────

    def _register_infra_handlers(self) -> None:
        """Register semua event handler untuk Layer 6."""

        @self._event_bus.on("service.activity")
        async def _on_activity(event: Any) -> None:
            if event.service in ("12-webhook", "13-upkeep", "15-dashboard", "16-submission"):
                self.refresh()

        @self._event_bus.on("service.health")
        async def _on_health(event: Any) -> None:
            if event.service == "15-dashboard":
                healthy = event.payload.get("healthy", True)
                self._sse_disconnected = not healthy
                infra = AppState.get().dashboard_infra
                if infra:
                    infra.health = healthy
                self.refresh()

        @self._event_bus.on("webhook.received")
        async def _on_webhook_recv(event: Any) -> None:
            wh = AppState.get().webhook_state
            if wh is None:
                wh = WebhookState()
                AppState.update(webhook_state=wh)

            item = WebhookItem(
                source=event.payload.get("source", "?"),
                event_type=event.payload.get("event_type", "?"),
                summary=event.payload.get("summary", ""),
                received_at=event.timestamp or datetime.now().isoformat(),
                status="pending",
            )
            wh.pending_queue.append(item)
            wh.last_received = item
            wh.status = "busy"
            self._webhook_pending = True
            self.refresh()

        @self._event_bus.on("webhook.processed")
        async def _on_webhook_proc(event: Any) -> None:
            wh = AppState.get().webhook_state
            if wh and wh.pending_queue:
                wh.pending_queue.pop(0)
                wh.events_processed_today += 1
            if wh:
                wh.status = "idle" if not wh.pending_queue else "busy"
            self._webhook_pending = bool(wh and wh.pending_queue)
            self.refresh()

        @self._event_bus.on("upkeep.task_started")
        async def _on_upkeep_start(event: Any) -> None:
            uk = AppState.get().upkeep_state
            if uk is None:
                uk = UpkeepState()
                AppState.update(upkeep_state=uk)
            uk.current_task = event.payload.get("task", "?")
            uk.task_progress = 0
            uk.status = "busy"
            self._upkeep_running = True
            self.refresh()

        @self._event_bus.on("upkeep.task_completed")
        async def _on_upkeep_done(event: Any) -> None:
            uk = AppState.get().upkeep_state
            if uk:
                uk.current_task = None
                uk.task_progress = None
                uk.disk_freed_gb = event.payload.get("freed_gb")
                uk.disk_usage_pct = event.payload.get("disk_pct", uk.disk_usage_pct)
                uk.status = "idle"
            self._upkeep_running = False
            self.refresh()

        @self._event_bus.on("upkeep.disk_warning")
        async def _on_disk_warn(event: Any) -> None:
            uk = AppState.get().upkeep_state
            if uk:
                uk.disk_usage_pct = event.payload.get("disk_pct", uk.disk_usage_pct)
            self.refresh()

        @self._event_bus.on("submission.step_update")
        async def _on_submit_step(event: Any) -> None:
            sub = AppState.get().submission_state
            if sub is None:
                sub = SubmissionState()
                AppState.update(submission_state=sub)
            step = event.payload.get("step", 1)
            done = event.payload.get("done", False)
            dur = event.payload.get("duration_s")
            sub.current_step = step
            sub.step_results[step] = {"done": done, "duration": dur}
            sub.status = "running"
            self._submission_running = True
            self.refresh()

        @self._event_bus.on("submission.completed")
        async def _on_submit_done(event: Any) -> None:
            sub = AppState.get().submission_state
            if sub:
                sub.status = "completed"
                sub.submission_id = event.payload.get("submission_id")
                sub.submitted_at = datetime.now().isoformat()
            self._submission_running = False
            self.refresh()

        @self._event_bus.on("submission.failed")
        async def _on_submit_fail(event: Any) -> None:
            sub = AppState.get().submission_state
            if sub:
                sub.status = "failed"
                sub.error_msg = event.payload.get("error", "Unknown error")
            self._submission_running = False
            self.refresh()

    # ── Keyboard ────────────────────────────────────────────────────────

    def on_key(self, event: Any) -> None:
        """Extended: Enter, w, u, s, d."""
        super().on_key(event)
        key = getattr(event, "key", None)
        if key == "enter":
            logger.info("Service detail requested")
        elif key == "w":
            logger.info("Webhook log requested")
        elif key == "u":
            logger.info("Upkeep schedule requested")
        elif key == "s":
            logger.info("Submission status requested")
        elif key == "d":
            logger.info("Dashboard metrics requested")

    # ── Helpers ─────────────────────────────────────────────────────────

    def _time_ago_str(self, timestamp_str: str | None) -> str:
        if not timestamp_str:
            return ""
        try:
            dt = datetime.fromisoformat(timestamp_str)
            diff = (datetime.now() - dt).seconds
            if diff < 60:
                return f"{diff}s ago"
            elif diff < 3600:
                return f"{diff // 60}m ago"
            return f"{diff // 3600}h ago"
        except Exception:
            return ""

    # ── Extra Lines per Service ─────────────────────────────────────────

    def _webhook_extra(self) -> list[str]:
        """Extra lines untuk 12-Webhook."""
        wh = AppState.get().webhook_state
        if wh is None:
            return []

        lines: list[str] = []
        if wh.pending_queue:
            lines.append(f"Queue: {len(wh.pending_queue)} pending")
            for item in wh.pending_queue[:2]:
                lines.append(
                    f"  [{item.received_at[-8:]}] "
                    f"{item.source}.{item.event_type}  {item.summary[:35]}"
                )
        if wh.last_received and not wh.pending_queue:
            ago = self._time_ago_str(wh.last_received.received_at)
            lines.append(
                f"Last: {wh.last_received.source}.{wh.last_received.event_type} ({ago})"
            )
        return lines

    def _upkeep_extra(self) -> list[str]:
        """Extra lines untuk 13-Upkeep."""
        uk = AppState.get().upkeep_state
        if uk is None:
            return []

        lines: list[str] = []

        disk_str = f"Disk: {uk.disk_usage_pct:.0f}%"
        if uk.disk_usage_pct > DISK_WARNING_THRESHOLD:
            disk_str += " \U0001f534 WARNING!"
        lines.append(disk_str)

        if uk.status == "busy" and uk.current_task and self._upkeep_running:
            prog = uk.task_progress or 0
            bar = self._render_progress_bar(prog, width=8)
            lines.append(f"Task: {uk.current_task} [{bar}] {prog}%")
            if uk.disk_freed_gb:
                lines.append(f"Freed: {uk.disk_freed_gb:.1f}GB")
        else:
            if uk.next_scheduled:
                tasks = []
                for task_name, dt in list(uk.next_scheduled.items())[:2]:
                    tasks.append(f"{task_name}@{dt}")
                lines.append("Next: " + ", ".join(tasks))

        return lines

    def _dashboard_extra(self) -> list[str]:
        """Extra lines untuk 15-Dashboard."""
        infra = AppState.get().dashboard_infra
        if self._sse_disconnected:
            return ["\u274c SSE hub unreachable — reconnecting..."]

        if infra is None:
            return []

        lines: list[str] = []
        lines.append(f"SSE clients: {infra.sse_client_count}")
        if infra.events_published_hr:
            lines.append(f"Events: {infra.events_published_hr}/hr")
        return lines

    def _submission_extra(self) -> list[str]:
        """Extra lines untuk 16-Submission (4-step progress)."""
        sub = AppState.get().submission_state
        if sub is None:
            return []

        lines: list[str] = []

        if sub.status == "running":
            for i, step_name in enumerate(self.SUBMISSION_STEPS, 1):
                result = sub.step_results.get(i, {})
                if result and result.get("done"):
                    dur = result.get("duration", 0)
                    lines.append(f"  [{i}/4] {step_name} \u2705 {dur:.1f}s")
                elif sub.current_step == i:
                    lines.append(f"  [{i}/4] {step_name} \u28fe running")
                else:
                    lines.append(f"  [{i}/4] {step_name} \u25cb waiting")

        if sub.status == "completed":
            lines.append(f"\u2705 Submitted: {sub.submission_id or 'OK'}")

        if sub.status == "failed":
            lines.append(f"\u274c Failed: {(sub.error_msg or '?')[:40]}")

        if sub.queue:
            lines.append(f"Queue: {len(sub.queue)} waiting")

        return lines

    # ── Render ──────────────────────────────────────────────────────────

    def render(self) -> str:
        lines: list[str] = []

        suffix = ""
        if self._sse_disconnected:
            suffix = "\u26a0\ufe0f SSE DISCONNECTED"
        elif self._webhook_pending:
            suffix = "\U0001f4e8 WEBHOOK"
        elif self._submission_running:
            suffix = "\U0001f4e4 SUBMITTING"

        lines.append(self._render_panel_header(self.PANEL_TITLE, suffix))

        # ── 12-Webhook ──
        activity12 = AppState.get().service_activities.get("12-webhook")
        healthy12 = AppState.get().service_health.get("12-webhook")
        spark12 = AppState.get().service_sparklines.get("12-webhook", [])
        w12 = self._render_service_window(
            "12-webhook", 8010, activity12, healthy12, spark12,
            is_focused=(0 == self._focused_idx),
            extra_lines=self._webhook_extra() or None,
        )
        lines.extend(w12)

        # ── 13-Upkeep ──
        activity13 = AppState.get().service_activities.get("13-upkeep")
        healthy13 = AppState.get().service_health.get("13-upkeep")
        spark13 = AppState.get().service_sparklines.get("13-upkeep", [])
        w13 = self._render_service_window(
            "13-upkeep", 8012, activity13, healthy13, spark13,
            is_focused=(1 == self._focused_idx),
            extra_lines=self._upkeep_extra() or None,
        )
        lines.extend(w13)

        # ── 15-Dashboard ──
        activity15 = AppState.get().service_activities.get("15-dashboard")
        healthy15 = AppState.get().service_health.get("15-dashboard")
        spark15 = AppState.get().service_sparklines.get("15-dashboard", [])
        w15 = self._render_service_window(
            "15-dashboard", 8000, activity15, healthy15, spark15,
            is_focused=(2 == self._focused_idx),
            extra_lines=self._dashboard_extra() or None,
        )
        lines.extend(w15)

        # ── 16-Submission ──
        activity16 = AppState.get().service_activities.get("16-submission")
        healthy16 = AppState.get().service_health.get("16-submission")
        spark16 = AppState.get().service_sparklines.get("16-submission", [])
        w16 = self._render_service_window(
            "16-submission", 8018, activity16, healthy16, spark16,
            is_focused=(3 == self._focused_idx),
            extra_lines=self._submission_extra() or None,
        )
        lines.extend(w16)

        lines.append(self._render_panel_footer())
        return "\n".join(lines)
