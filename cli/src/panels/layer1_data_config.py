"""
VYPER TUI v2 — Panel 1: Data & Config Layer

Memonitor 3 service input pipeline, masing-masing sebagai mini-window:
  - 01-Config    (8011) — Konfigurasi global VYPER
  - 02-Immunefi  (8001) — Fetching program info dari Immunefi API
  - 03-Source    (8002) — Fetching source code kontrak
"""

from __future__ import annotations

import logging
from typing import Any

from cli.src.core.state_store import AppState
from cli.src.panels.base_layer_panel import LayerPanel

logger = logging.getLogger("vyper_tui.panels.layer1")


class DataConfigPanel(LayerPanel):
    """
    Layer 1 — Data & Config Panel.
    3 service input pipeline, masing-masing bordered window.
    """

    PANEL_TITLE = "DATA & CONFIG"
    SERVICES = [
        ("01-config",     8011),
        ("02-immunefi",   8001),
        ("03-source",     8002),
    ]

    def on_mount(self) -> None:
        super().on_mount()
        if self._event_bus:
            @self._event_bus.on("audit.state_change")
            async def _on_audit_state(event: Any) -> None:
                """Highlight service yang relevan dengan stage audit."""
                stage = event.payload.get("state", "")
                stage_map = {
                    "fetching_program": "02-immunefi",
                    "fetching_source":  "03-source",
                }
                if stage in stage_map:
                    self._active_for_audit = stage_map[stage]
                else:
                    self._active_for_audit = None
                self.refresh()

    def on_key(self, event: Any) -> None:
        """Extended keyboard: c → Config Quick Viewer."""
        super().on_key(event)
        key = getattr(event, "key", None)
        if key == "c" and self._focused_service == "01-config":
            self._open_config_viewer()

    def _open_config_viewer(self) -> None:
        """Buka Config Quick Viewer overlay untuk 01-Config."""
        logger.info("Config Viewer opened for 01-config")

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

            # Extra lines spesifik
            extra: list[str] = []
            if activity:
                status = activity.status or "unknown"
                if status == "busy" and activity.task:
                    extra.append(f"Task: {activity.task[:40]}")

            window = self._render_service_window(
                svc_name, port, activity, healthy, sparkline,
                is_focused=is_focused,
                extra_lines=extra if extra else None,
            )
            lines.extend(window)

        # ── Footer ──
        lines.append(self._render_panel_footer())

        return "\n".join(lines)
