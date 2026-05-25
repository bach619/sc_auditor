"""Vyper Monitor TUI App — live terminal dashboard using Textual.

Copy-paste & text selection:
  y            → Copy all events to clipboard
  Y            → Copy only visible (filtered) events to clipboard
  F2 / ctrl+s  → Toggle SELECT MODE (free mouse for terminal text selection)
"""

from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Input, Static
from textual import work

from cli.monitor.client import MonitorClient
from cli.monitor.widgets import (
    StatusBar, EventLog, SummaryBar, ShortcutsBar,
    AgentPanel, MemoryPanel, CircuitBreakerPanel,
)

# ── Mouse escape sequences ─────────────────────────────────────

_MOUSE_DISABLE = "\x1b[?1000l\x1b[?1003l\x1b[?1006l\x1b[?1015l"
_MOUSE_ENABLE = "\x1b[?1000h\x1b[?1003h\x1b[?1006h\x1b[?1015h"


def _disable_mouse_mode() -> None:
    """Disable application mouse mode → enable native terminal text selection."""
    import sys
    sys.stdout.write(_MOUSE_DISABLE)
    sys.stdout.flush()


def _enable_mouse_mode() -> None:
    """Re-enable application mouse mode → normal TUI interaction."""
    import sys
    sys.stdout.write(_MOUSE_ENABLE)
    sys.stdout.flush()


class VyperMonitorApp(App):
    """Vyper Monitor Terminal UI — live dashboard for all 19 services."""

    CSS = """
    Screen {
        background: $surface;
    }

    StatusBar {
        height: 3;
        dock: top;
    }

    /* ── Main layout: agent sidebar + event log ── */
    Horizontal {
        height: 1fr;
    }

    #agent-column {
        width: 38;
        min-width: 30;
        max-width: 50;
        dock: left;
    }

    AgentPanel {
        height: 10;
        border: solid $secondary;
        margin: 0 0 1 0;
    }

    MemoryPanel {
        height: 8;
        border: solid $secondary;
        margin: 0 0 1 0;
    }

    CircuitBreakerPanel {
        height: 5;
        border: solid $secondary;
    }

    EventLog {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }

    SummaryBar {
        height: 3;
        dock: bottom;
    }

    ShortcutsBar {
        height: 3;
        dock: bottom;
    }

    Input#search {
        dock: top;
        height: 3;
        margin: 0 1;
        display: none;
    }

    #clipboard-msg {
        height: 1;
        padding: 0 1;
        color: $success;
        dock: bottom;
        display: none;
    }

    #selection-indicator {
        height: 1;
        padding: 0 1;
        background: $warning-lighten-1;
        color: $text;
        dock: bottom;
        display: none;
        text-align: center;
    }
    """

    BINDINGS = [
        ("q", "exit", "Exit"),
        ("space", "toggle_pause", "Pause/Resume"),
        ("/", "search", "Search"),
        ("escape", "close_search", "Close search"),
        ("1", "filter_all", "All"),
        ("2", "filter_success", "Success"),
        ("3", "filter_info", "Info"),
        ("4", "filter_warning", "Warning"),
        ("5", "filter_error", "Error"),
        ("6", "filter_critical", "Critical"),
        ("r", "refresh", "Refresh"),
        ("a", "toggle_agent", "Toggle agent panel"),
        # Copy-paste
        ("y", "copy_events", "Copy events"),
        ("Y", "copy_visible", "Copy visible"),
        # Text selection toggle
        ("f2", "toggle_selection", "Toggle select mode"),
        ("ctrl+s", "toggle_selection", "Toggle select mode"),
    ]

    selection_mode: reactive[bool] = reactive(False)
    show_agent_panel: reactive[bool] = reactive(True)

    def __init__(self, poll_interval: int = 5) -> None:
        super().__init__()
        self.poll_interval = poll_interval
        self.client = MonitorClient()
        self._paused = False

    # ── Selection mode ─────────────────────────────────────────

    def watch_selection_mode(self, old: bool, new: bool) -> None:
        """React to selection_mode changes: toggle mouse capture."""
        indicator = self.query_one("#selection-indicator", Static)
        if new:
            _disable_mouse_mode()
            indicator.display = "block"
            indicator.update(
                "[bold yellow]\U0001f4dd SELECT MODE[/bold yellow]  \u2014  "
                "[dim]Select text with mouse, press F2 to return[/dim]"
            )
        else:
            _enable_mouse_mode()
            indicator.display = "none"

    def action_toggle_selection(self) -> None:
        """Toggle selection mode on/off."""
        self.selection_mode = not self.selection_mode

    # ── Agent panel toggle ─────────────────────────────────────

    def watch_show_agent_panel(self, old: bool, new: bool) -> None:
        """Show/hide the agent column."""
        col = self.query_one("#agent-column")
        col.display = "block" if new else "none"

    def action_toggle_agent(self) -> None:
        """Toggle agent panel on/off."""
        self.show_agent_panel = not self.show_agent_panel

    def compose(self) -> ComposeResult:
        yield StatusBar()
        with Horizontal():
            with Vertical(id="agent-column"):
                yield AgentPanel()
                yield MemoryPanel()
                yield CircuitBreakerPanel()
            yield EventLog()
        yield SummaryBar()
        yield ShortcutsBar()
        yield Input(id="search", placeholder="Search events...")
        yield Static(id="clipboard-msg")
        yield Static(id="selection-indicator")

    def on_mount(self) -> None:
        """Start background polling tasks."""
        self._poll_health()
        self._poll_events()
        self._poll_stats()
        self._poll_agent()

    def _flash_clipboard(self, msg: str) -> None:
        """Show a brief clipboard message at the bottom."""
        w = self.query_one("#clipboard-msg", Static)
        w.update(f"[green]\u2705 {msg}[/]")
        w.display = "block"
        self.set_timer(2.5, lambda: w.update("") or setattr(w, "display", "none"))

    # ── Background polling ──────────────────────────────────────

    @work(thread=False, group="polling", exit_on_error=False)
    async def _poll_health(self) -> None:
        while True:
            try:
                data = await self.client.health_all()
                sb = self.query_one(StatusBar)
                sb.health_data = data
                sm = self.query_one(SummaryBar)
                sm.health_data = data
            except Exception:
                pass
            await asyncio.sleep(self.poll_interval)

    @work(thread=False, group="polling", exit_on_error=False)
    async def _poll_events(self) -> None:
        while True:
            if not self._paused:
                try:
                    events = await self.client.get_events()
                    self.query_one(EventLog).add_events(events)
                except Exception:
                    pass
            await asyncio.sleep(3)

    @work(thread=False, group="polling", exit_on_error=False)
    async def _poll_stats(self) -> None:
        while True:
            try:
                stats = await self.client.get_stats()
                sm = self.query_one(SummaryBar)
                sm.stats = stats
                pipeline_active = stats.get("in_progress", 0)
                sb = self.query_one(StatusBar)
                sb.pipeline_active = pipeline_active
                sb.queue_size = await self.client.get_queue_size()
            except Exception:
                pass
            await asyncio.sleep(10)

    @work(thread=False, group="polling", exit_on_error=False)
    async def _poll_agent(self) -> None:
        """Poll Antonio agent data for the side panels."""
        while True:
            try:
                agent_data = await self.client.get_agent_status()
                if agent_data:
                    self.query_one(AgentPanel).agent_data = agent_data
                    self.query_one(MemoryPanel).agent_data = agent_data
                    cb_panel = self.query_one(CircuitBreakerPanel)
                    cb_panel.agent_data = agent_data
                    # Also try to fetch real CB data
                    cb_data = await self.client.get_circuit_breakers()
                    if cb_data:
                        cb_panel.circuit_breakers = cb_data
            except Exception:
                pass
            await asyncio.sleep(5)

    # ── Key handlers ────────────────────────────────────────────

    def action_exit(self) -> None:
        """Exit — cancel workers first, then let Textual restore terminal."""
        _enable_mouse_mode()
        self.workers.cancel_all()
        self.exit()

    def action_toggle_pause(self) -> None:
        self._paused = not self._paused
        log = self.query_one(EventLog)
        log.paused = self._paused
        if self._paused:
            log.write("[dim]\u23f8 PAUSED \u2014 press Space to resume[/dim]")
        else:
            log.write("[dim]\u25b6 RESUMED[/dim]")

    def action_search(self) -> None:
        inp = self.query_one(Input)
        inp.display = "block"
        inp.focus()

    def action_close_search(self) -> None:
        inp = self.query_one(Input)
        inp.display = "none"
        inp.value = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        val = event.value.strip().upper()
        event.input.display = "none"
        event.input.value = ""
        valid = {"ALL", "SUCCESS", "INFO", "WARNING", "ERROR", "CRITICAL"}
        self.query_one(EventLog).filter_level = val if val in valid else "ALL"

    def action_filter_all(self) -> None:
        self.query_one(EventLog).filter_level = "ALL"

    def action_filter_success(self) -> None:
        self.query_one(EventLog).filter_level = "SUCCESS"

    def action_filter_info(self) -> None:
        self.query_one(EventLog).filter_level = "INFO"

    def action_filter_warning(self) -> None:
        self.query_one(EventLog).filter_level = "WARNING"

    def action_filter_error(self) -> None:
        self.query_one(EventLog).filter_level = "ERROR"

    def action_filter_critical(self) -> None:
        self.query_one(EventLog).filter_level = "CRITICAL"

    def action_refresh(self) -> None:
        log = self.query_one(EventLog)
        log.clear()
        self.client._prev_audits.clear()

    # ── Copy actions ────────────────────────────────────────────

    def action_copy_events(self) -> None:
        """Copy all events to clipboard."""
        log = self.query_one(EventLog)
        success = log.copy_events(visible_only=False)
        if success:
            self._flash_clipboard(f"Copied {len(log._event_store)} events to clipboard")
        else:
            self._flash_clipboard("No events to copy or clipboard unavailable")

    def action_copy_visible(self) -> None:
        """Copy only visible (filtered) events to clipboard."""
        log = self.query_one(EventLog)
        success = log.copy_events(visible_only=True)
        if success:
            self._flash_clipboard("Copied visible events to clipboard")
        else:
            self._flash_clipboard("No visible events to copy or clipboard unavailable")

    async def on_shutdown(self) -> None:
        _enable_mouse_mode()
        await self.client.close()
        import os
        os._exit(0)
