#!/usr/bin/env python3
"""
VYPER TUI v2 — Terminal Command Center
=======================================
Terminal User Interface untuk memonitor, mengendalikan, dan berinteraksi
dengan seluruh ekosistem VYPER smart contract security platform.

6 Layer Panel memonitor 16 microservice:
  L1: Data & Config      — 01-Config, 02-Immunefi, 03-Source
  L2: Processing          — 04-Scanner, 04a-Slither, 04b-Echidna, 04c-Forge, 04d-Halmos, 05-Mythril
  L3: Intelligence        — 06-AI, 07-Classifier
  L4: Exploit & Output   — 08-Exploit, 09-Reporter, 10-Notifier
  L5: Orchestration      — 11-Orchestrator, 14-Agent
  L6: Infra & Delivery   — 12-Webhook, 13-Upkeep, 15-Dashboard, 16-Submission

Usage:
    python -m cli.app
    python -m cli.app --dashboard http://my-server:8000
    python -m cli.app --debug

Mode Layout:
    F1 = FULL      — 6-panel command center (default)
    F2 = AUDIT     — Pipeline focus
    F3 = AGENT     — Antonio full-screen
    F4 = COMPACT   — Headless/SSH minimal
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Header, Footer, Static

from cli.src.core.event_bus import EventBus
from cli.src.core.polling_fallback import PollingFallback
from cli.src.core.state_store import AppState
from cli.src.monitors.activity_monitor import ActivityMonitorV2
from cli.src.panels.chat_panel import ChatPanel
from cli.src.panels.layer1_data_config import DataConfigPanel
from cli.src.panels.layer2_processing import ProcessingPanel
from cli.src.panels.layer3_intelligence import IntelligencePanel
from cli.src.panels.layer4_exploit_output import ExploitOutputPanel
from cli.src.panels.layer5_orchestration_agent import OrchestrationAgentPanel
from cli.src.panels.layer6_infra_delivery import InfraDeliveryPanel

# ── Logging ──────────────────────────────────────────────────────────────
# Log ke FILE, bukan stderr — biar tidak mengganggu rendering TUI
_log_dir = Path.home() / ".vyper" / "tui"
_log_dir.mkdir(parents=True, exist_ok=True)
_log_file = _log_dir / "vyper-tui.log"

_file_handler = logging.FileHandler(_log_file, mode="a", encoding="utf-8")
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
))

logging.basicConfig(
    level=logging.INFO,
    handlers=[_file_handler],
)
logger = logging.getLogger("vyper_tui")


# ── CSS / TCSS ───────────────────────────────────────────────────────────
VYPER_CSS = """
Screen {
    background: $surface;
}

VyperTUI {
    layout: grid;
    grid-size: 3 5;          /* 3 kolom × 5 baris */
    grid-gutter: 0;
}

/* ── Header & Footer ─────────────────────────── */
Header {
    column-span: 3;
    dock: top;
    height: 1;
    background: $primary;
    color: $text;
}

Footer {
    column-span: 3;
    dock: bottom;
    height: 1;
}

/* ── Kolom Kiri: Layer 1-3 ──────────────────── */
DataConfigPanel {
    row-span: 1;
    border: solid $primary;
    height: 10;
    min-height: 8;
}

ProcessingPanel {
    row-span: 1;
    border: solid $secondary;
    height: 14;
    min-height: 12;
}

IntelligencePanel {
    row-span: 1;
    border: solid $accent;
    height: 10;
    min-height: 8;
}

/* ── Kolom Tengah: Placeholder panels ──────── */
#pipeline-placeholder {
    border: dashed $warning;
    height: 10;
    content-align: center middle;
}

#antonio-placeholder {
    border: dashed $success;
    height: 14;
    content-align: center middle;
}

#metrics-placeholder {
    border: dashed $accent;
    height: 10;
    content-align: center middle;
}

/* ── Kolom Kanan: Layer 4-6 ────────────────── */
ExploitOutputPanel {
    row-span: 1;
    border: solid $error;
    height: 10;
    min-height: 8;
}

OrchestrationAgentPanel {
    row-span: 1;
    border: solid $primary;
    height: 14;
    min-height: 12;
}

InfraDeliveryPanel {
    row-span: 1;
    border: solid grey;
    height: 10;
    min-height: 8;
}

/* ── Chat Panel ──────────────────────────────── */
ChatPanel {
    column-span: 3;
    border: solid $primary;
    height: 6;
    min-height: 4;
    background: $surface;
}

#chat-log {
    height: 3;
    min-height: 2;
    margin: 0;
    padding: 0 1;
    background: $surface;
}

#chat-input {
    height: 1;
    dock: bottom;
    background: $panel;
    color: $text;
    border: none;
    padding: 0 1;
}

/* ── Status Bar ─────────────────────────────── */
#status-bar {
    column-span: 3;
    height: 1;
    background: $panel;
    color: $text;
}
"""


class VyperTUI(App):
    """
    Aplikasi utama VYPER TUI v2.

    Mengelola:
      - 6 Layer Panel di layout grid 3×5
      - EventBus connection ke 15-Dashboard SSE
      - Layout multi-mode (F1-F4)
      - Status bar real-time
    """

    CSS = VYPER_CSS

    # ── Bindings ──────────────────────────────────────────────────────────
    BINDINGS = [
        Binding("f1", "set_mode('full')",    "FULL",    priority=True),
        Binding("f2", "set_mode('audit')",   "AUDIT",   priority=True),
        Binding("f3", "set_mode('agent')",   "AGENT",   priority=True),
        Binding("f4", "set_mode('compact')", "COMPACT", priority=True),
        Binding("q",  "quit",                "Quit",    priority=True),
        Binding("?",  "show_help",           "Help",    priority=True),
    ]

    # Reactive state
    current_mode: reactive[str] = reactive("full")

    def __init__(self, dashboard_url: str = "http://localhost:8000"):
        super().__init__()
        self.dashboard_url = dashboard_url
        # Init EventBus SEBELUM compose — panel butuh ini di on_mount()
        events_url = f"{self.dashboard_url}/events"
        self.event_bus = EventBus(app=self, url=events_url)
        self.polling_fallback = PollingFallback(event_bus=self.event_bus)
        self.activity_monitor: ActivityMonitorV2 | None = None
        self._background_tasks: list[asyncio.Task] = []

    # ── Lifecycle ────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """Build UI tree — 3 kolom × 5 baris."""
        yield Header(show_clock=True)

        # ── Kolom Kiri (Layer 1-3) ──
        yield DataConfigPanel(id="data-config")
        yield ProcessingPanel(id="processing")
        yield IntelligencePanel(id="intelligence")

        # ── Kolom Tengah (Pipeline, Antonio, Metrics) ──
        yield Static("  PIPELINE TRACKER\n  (coming soon)", id="pipeline-placeholder")
        yield Static("  ANTONIO ReAct LOOP\n  (coming soon)", id="antonio-placeholder")
        yield Static("  METRICS PANEL\n  (coming soon)", id="metrics-placeholder")

        # ── Kolom Kanan (Layer 4-6) ──
        yield ExploitOutputPanel(id="exploit-output")
        yield OrchestrationAgentPanel(id="orchestration-agent")
        yield InfraDeliveryPanel(id="infra-delivery")

        # ── Full Width: Chat Panel ──
        yield ChatPanel(id="chat-panel")
        yield Static("  connecting...", id="status-bar")

        yield Footer()

    def on_mount(self) -> None:
        """Setup infrastructure setelah compose."""
        # Initialize state (singleton)
        AppState.initialize(self)

        # Setup ActivityMonitor (auto-register handler ke EventBus)
        self.activity_monitor = ActivityMonitorV2(self.event_bus)

        # Start background tasks
        self._background_tasks.append(
            asyncio.create_task(
                self.event_bus.connect(),
                name="eventbus-connect",
            )
        )
        self._background_tasks.append(
            asyncio.create_task(
                self.polling_fallback.start(),
                name="polling-fallback",
            )
        )

        # Update status bar
        self._update_status_bar()

        logger.info(
            "VyperTUI v2 mounted — dashboard: %s, mode: %s",
            self.dashboard_url,
            self.current_mode,
        )

    def on_unmount(self) -> None:
        """Cleanup saat aplikasi ditutup."""
        logger.info("Shutting down VyperTUI...")

        if self.event_bus:
            self.event_bus.disconnect()

        if self.polling_fallback:
            asyncio.create_task(self.polling_fallback.stop())

        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()

    # ── Actions ──────────────────────────────────────────────────────────

    def action_set_mode(self, mode: str) -> None:
        """Ganti layout mode (F1-F4)."""
        if mode not in ("full", "audit", "agent", "compact"):
            logger.warning("Unknown mode: %s", mode)
            return

        self.current_mode = mode
        AppState.update(current_mode=mode)

        if mode == "full":
            self._apply_full_layout()
        elif mode == "audit":
            self._apply_audit_layout()
        elif mode == "agent":
            self._apply_agent_layout()
        elif mode == "compact":
            self._apply_compact_layout()

        self._update_status_bar()
        logger.info("Mode changed to: %s", mode)

    def action_quit(self) -> None:
        """Konfirmasi dan quit."""
        self.exit()

    def action_show_help(self) -> None:
        """Tampilkan quick help overlay."""
        logger.info("Help requested")

    # ── Layout Modes ─────────────────────────────────────────────────────

    def _show_all(self, show: bool = True) -> None:
        """Tampilkan/sembunyikan semua widget panel."""
        for widget_id in [
            "data-config", "processing", "intelligence",
            "pipeline-placeholder", "antonio-placeholder", "metrics-placeholder",
            "exploit-output", "orchestration-agent", "infra-delivery",
        ]:
            try:
                self.query_one(f"#{widget_id}").display = show
            except Exception:
                pass

    def _apply_full_layout(self) -> None:
        """Mode FULL — semua panel terlihat."""
        self._show_all(True)

    def _apply_audit_layout(self) -> None:
        """Mode AUDIT — pipeline focus."""
        self._show_all(False)
        for widget_id in ["pipeline-placeholder", "antonio-placeholder",
                          "processing", "exploit-output", "orchestration-agent"]:
            try:
                self.query_one(f"#{widget_id}").display = True
            except Exception:
                pass

    def _apply_agent_layout(self) -> None:
        """Mode AGENT — Antonio full-screen."""
        self._show_all(False)
        try:
            self.query_one("#antonio-placeholder").display = True
        except Exception:
            pass

    def _apply_compact_layout(self) -> None:
        """Mode COMPACT — headless/SSH minimal."""
        self._show_all(False)
        # Only status bar and chat visible

    # ── Status Bar ───────────────────────────────────────────────────────

    def _update_status_bar(self) -> None:
        """Update status bar dengan info real-time dari AppState."""
        state = AppState.get()
        mode = state.current_mode.upper()
        audit_count = len(state.active_audits)
        queue_count = len(state.pipeline_queue)
        slots = state.resource_slots
        orch = state.orchestrator_state
        uk = state.upkeep_state

        # ── Deteksi backend offline ──
        sse_connected = self.event_bus and self.event_bus.is_connected
        has_any_service = len(state.service_activities) > 0
        backend_online = sse_connected or has_any_service

        if not backend_online:
            status_bar = self.query_one("#status-bar", Static)
            status_bar.update(
                f"  \u26a0\ufe0f  BACKEND OFFLINE  \u25a0  "
                f"Menunggu koneksi ke 15-Dashboard di {self.dashboard_url}  \u25a0  "
                f"Jalankan 'docker compose up -d' untuk start services"
            )
            return

        # ── Slot info ──
        slot_parts = []
        if slots:
            slot_parts.append(f"Scan:{slots.scanner_used}/{slots.scanner_max}")
            slot_parts.append(f"AI:{slots.ai_used}/{slots.ai_max}")
            slot_parts.append(f"Exp:{slots.exploit_used}/{slots.exploit_max}")
        elif orch:
            slot_parts.append(
                f"Scan:{orch.scanner_slots[0]}/{orch.scanner_slots[1]}"
            )
            slot_parts.append(f"AI:{orch.ai_slots[0]}/{orch.ai_slots[1]}")
            slot_parts.append(f"Exp:{orch.exploit_slots[0]}/{orch.exploit_slots[1]}")

        slots_str = "  ".join(slot_parts)

        # ── Disk usage ──
        disk_str = ""
        if uk:
            disk_str = f"  Disk:{uk.disk_usage_pct:.0f}%"

        # ── SSE status ──
        sse_status = (
            "SSE \u2705"
            if sse_connected
            else "SSE \u274c"
        )

        # ── Services online count ──
        n_services = len(state.service_activities)
        n_idle = sum(
            1
            for a in state.service_activities.values()
            if getattr(a, "status", "") == "idle"
        )
        n_busy = sum(
            1
            for a in state.service_activities.values()
            if getattr(a, "status", "") == "busy"
        )

        status_bar = self.query_one("#status-bar", Static)
        status_bar.update(
            f"  VYPER v2  \u25a0  MODE: {mode}  \u25a0  "
            f"services:{n_services} (\U0001f4a4{n_idle} \u28fe{n_busy})"
            f"  audits:{audit_count}  queue:{queue_count}  \u25a0  "
            f"{slots_str}  \u25a0"
            f"{disk_str}  \u25a0  "
            f"LLM:claude-sonnet-4-6  \u25a0  "
            f"{sse_status}"
        )


# ── Entry Point ────────────────────────────────────────────────────────────
def main() -> None:
    """Entry point untuk `python -m cli.app` atau `vyper-tui`."""
    import argparse

    parser = argparse.ArgumentParser(
        description="VYPER TUI v2 — Terminal Command Center",
    )
    parser.add_argument(
        "--dashboard",
        default="http://localhost:8000",
        help="URL 15-Dashboard SSE hub (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Aktifkan debug logging",
    )
    args = parser.parse_args()

    if args.debug:
        # Debug mode: tambah console handler juga
        _console = logging.StreamHandler(sys.stderr)
        _console.setLevel(logging.DEBUG)
        _console.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        logging.getLogger("vyper_tui").addHandler(_console)
        logging.getLogger("vyper_tui").setLevel(logging.DEBUG)
        logging.getLogger("httpx").setLevel(logging.WARNING)

    app = VyperTUI(dashboard_url=args.dashboard)
    app.run()


if __name__ == "__main__":
    main()
