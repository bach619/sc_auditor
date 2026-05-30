"""
VYPER TUI v2 — Panel 2: Processing Layer

6 service processing, masing-masing sebagai mini-window:
  - 04-Scanner    (8003) — Delegasi ke sub-scanner
  - 04a-Slither   (8014) — Static analysis
  - 04b-Echidna   (8015) — Fuzzing
  - 04c-Forge     (8016) — Build & test runner
  - 04d-Halmos    (8017) — Formal verification
  - 05-Mythril    (8013) — Symbolic execution

Fitur khusus per-window: sub-task checklist, bottleneck ⚡SLOW, slot awareness
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from cli.src.core.state_store import AppState
from cli.src.panels.base_layer_panel import LayerPanel

logger = logging.getLogger("vyper_tui.panels.layer2")


class ProcessingPanel(LayerPanel):
    """
    Layer 2 — Processing Panel.
    6 service dengan sub-task checklist, bottleneck, slot awareness.
    """

    PANEL_TITLE = "PROCESSING"
    SERVICES = [
        ("04-scanner",   8003),
        ("04a-slither",  8014),
        ("04b-echidna",  8015),
        ("04c-forge",    8016),
        ("04d-halmos",   8017),
        ("05-mythril",   8013),
    ]

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._sub_tasks: dict[str, list[dict]] = {}
        self._bottleneck_service: str | None = None
        self._active_audit_id: str | None = None

    def on_mount(self) -> None:
        super().on_mount()
        if self._event_bus:
            self._register_processing_handlers()

    def _register_processing_handlers(self) -> None:
        """Handler tambahan: sub-task, bottleneck, audit stage."""

        @self._event_bus.on("service.activity")
        async def _on_scan_detail(event: Any) -> None:
            if event.service in [s[0] for s in self.SERVICES]:
                sub = event.payload.get("sub_tasks", [])
                if sub:
                    self._sub_tasks[event.service] = sub
                self._update_bottleneck()
                self.refresh()

        @self._event_bus.on("audit.state_change")
        async def _on_scan_stage(event: Any) -> None:
            if event.payload.get("state") == "scanning":
                self._active_audit_id = event.payload.get("audit_id")
                self.refresh()

    # ── Bottleneck Detection ────────────────────────────────────────────

    def _update_bottleneck(self) -> None:
        """Tandai service paling lama running sebagai bottleneck."""
        state = AppState.get()
        longest: str | None = None
        longest_duration: float = 0

        for svc_name, _ in self.SERVICES:
            activity = state.service_activities.get(svc_name)
            if activity and activity.status == "busy" and activity.started_at:
                try:
                    started = datetime.fromisoformat(
                        activity.started_at.replace("Z", "+00:00")
                    )
                    duration = (datetime.now().astimezone() - started).total_seconds()
                    if duration > longest_duration:
                        longest_duration = duration
                        longest = svc_name
                except Exception:
                    continue

        self._bottleneck_service = longest

    # ── Sub-Task & Slot ─────────────────────────────────────────────────

    def _render_sub_tasks(self, service: str) -> str:
        """Sub-task checklist: compile ✓  reentrancy ✓  overflow ⣾"""
        tasks = self._sub_tasks.get(service, [])
        if not tasks:
            return ""
        parts: list[str] = []
        for t in tasks:
            name = t.get("name", "?")[:12]
            done = t.get("done", False)
            icon = "\u2713" if done else "\u28fe"
            parts.append(f"{name} {icon}")
        return "  ".join(parts)[:42]

    def _check_slot_full(self, svc_name: str) -> bool:
        """Cek apakah service terhalang slot governor."""
        state = AppState.get()
        slots = state.resource_slots
        if not slots:
            return False
        scanner_services = {"04-scanner", "04a-slither", "04b-echidna",
                            "04c-forge", "04d-halmos", "05-mythril"}
        if svc_name in scanner_services and slots.scanner_used >= slots.scanner_max:
            return True
        return False

    # ── Render ──────────────────────────────────────────────────────────

    def render(self) -> str:
        state = AppState.get()
        lines: list[str] = []

        # ── Header ──
        lines.append(self._render_panel_header(self.PANEL_TITLE))

        for idx, (svc_name, port) in enumerate(self.SERVICES):
            activity  = state.service_activities.get(svc_name)
            healthy   = state.service_health.get(svc_name)
            sparkline = state.service_sparklines.get(svc_name, [])

            is_focused = (idx == self._focused_idx)

            # Extra lines spesifik untuk processing
            extra: list[str] = []

            # Bottleneck label
            if svc_name == self._bottleneck_service:
                extra.append("\u26a1 BOTTLENECK — service paling lambat")

            # Sub-task checklist
            sub = self._render_sub_tasks(svc_name)
            if sub:
                extra.append(f"Tasks: {sub}")

            # Slot warning
            if activity and activity.status == "pending" and self._check_slot_full(svc_name):
                extra.append("\u23f3 Queued — semua scanner slot penuh")

            window = self._render_service_window(
                svc_name, port, activity, healthy, sparkline,
                is_focused=is_focused,
                extra_lines=extra if extra else None,
            )
            lines.extend(window)

        # ── Footer ──
        lines.append(self._render_panel_footer())

        return "\n".join(lines)
