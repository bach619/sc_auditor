"""
VYPER TUI v2 — Panel 3: Intelligence Layer

2 service quality-gate pipeline, masing-masing sebagai mini-window:
  - 06-AI          (8004) — LLM analysis (claude-sonnet-4-6)
  - 07-Classifier  (8005) — ML classifier TP/FP

Fitur per-window: model LLM, findings counter, cost, precision threshold
"""

from __future__ import annotations

import logging
from typing import Any

from cli.src.core.state_store import AppState
from cli.src.panels.base_layer_panel import LayerPanel

logger = logging.getLogger("vyper_tui.panels.layer3")

PRECISION_THRESHOLD = 80.0


class IntelligencePanel(LayerPanel):
    """
    Layer 3 — Intelligence Panel.
    06-AI (LLM analysis) dan 07-Classifier (ML TP/FP).
    """

    PANEL_TITLE = "INTELLIGENCE"
    SERVICES = [
        ("06-ai",         8004),
        ("07-classifier", 8005),
    ]

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._active_model: str = "\u2014"
        self._findings_progress: str = ""
        self._estimated_cost: str = ""
        self._tokens_used: int = 0
        self._classifier_metrics: dict[str, Any] = {}
        self._active_stage: str | None = None

    def on_mount(self) -> None:
        super().on_mount()
        if self._event_bus:
            self._register_intelligence_handlers()

    def _register_intelligence_handlers(self) -> None:
        """Handler spesifik untuk AI progress + classifier metrics."""

        @self._event_bus.on("service.activity")
        async def _on_ai_activity(event: Any) -> None:
            if event.service == "06-ai":
                self._active_model = event.payload.get("model", "\u2014")
                done = event.payload.get("findings_analyzed", 0)
                total = event.payload.get("findings_total", 0)
                if total:
                    self._findings_progress = f"{done}/{total}"
                tokens = event.payload.get("tokens_used", 0)
                cost = event.payload.get("estimated_cost_usd", 0)
                if tokens:
                    self._tokens_used = tokens
                if cost:
                    self._estimated_cost = f"~${cost:.2f}"
                self.refresh()

        @self._event_bus.on("metric.update")
        async def _on_metric(event: Any) -> None:
            tool = event.payload.get("tool", "")
            if tool in ("classifier", "07-classifier"):
                self._classifier_metrics = event.payload
                AppState.update(
                    classifier_metrics={
                        **AppState.get().classifier_metrics,
                        tool: event.payload,
                    }
                )
                self.refresh()

        @self._event_bus.on("audit.state_change")
        async def _on_intel_stage(event: Any) -> None:
            stage = event.payload.get("state", "")
            if stage in ("ai_analysis", "classifying"):
                self._active_stage = stage
            else:
                self._active_stage = None
            self.refresh()

    def on_key(self, event: Any) -> None:
        """Extended: m → MetricsPanel overlay."""
        super().on_key(event)
        key = getattr(event, "key", None)
        if key == "m":
            logger.info("Metrics overlay requested")

    # ── Render Helpers ──────────────────────────────────────────────────

    def _classifier_extra_lines(self) -> list[str]:
        """Extra lines untuk 07-Classifier metrics."""
        m = self._classifier_metrics
        if not m:
            return ["No metrics yet"]

        tp = m.get("tp", 0)
        fp = m.get("fp", 0)
        fn = m.get("fn", 0)
        precision = m.get("precision", 100.0)

        lines = [f"TP:{tp} FP:{fp} FN:{fn}  Precision:{precision:.1f}%"]

        if precision < PRECISION_THRESHOLD:
            lines.append(
                f"\u26a0\ufe0f PRECISION DROP: {precision:.1f}% "
                f"(threshold: {PRECISION_THRESHOLD:.0f}%)"
            )

        return lines

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

            # Extra lines spesifik
            extra: list[str] = []

            if svc_name == "06-ai":
                # Model + cost
                model_line = f"Model: {self._active_model}"
                if self._estimated_cost:
                    model_line += f"  {self._estimated_cost}"
                extra.append(model_line)

                if self._findings_progress:
                    extra.append(f"Findings: {self._findings_progress}")

            elif svc_name == "07-classifier":
                extra.extend(self._classifier_extra_lines())

            window = self._render_service_window(
                svc_name, port, activity, healthy, sparkline,
                is_focused=is_focused,
                extra_lines=extra if extra else None,
            )
            lines.extend(window)

        # ── Footer ──
        lines.append(self._render_panel_footer())

        return "\n".join(lines)
