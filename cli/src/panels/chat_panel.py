"""
VYPER TUI v2 — ChatPanel

Panel chat untuk interaksi dengan Antonio AI Agent.
Support /commands, timestamps, command history via ↑↓.

Layout:
  ┌─ Antonio Chat ────────────────────────────────────────────┐
  │  [10:30:01] Anda: /audit 0x4c9edd ethereum               │
  │  [10:30:02] Antonio: Memulai audit 0x4c9edd...            │
  │  [10:30:05] Antonio: Scanning dengan Mythril...            │
  │                                                            │
  │ > /help                                                    │
  └────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import Input, RichLog

logger = logging.getLogger("vyper_tui.chat_panel")


class ChatPanel(Widget):
    """
    Chat panel untuk interaksi dengan Antonio.

    Features:
      - Input bar untuk typing command
      - Chat history dengan RichLog
      - Timestamps otomatis
      - Command registry: /help, /audit, /status, dll
      - Command history via ↑↓ (bound keys)
    """

    BINDINGS = [
        Binding("up", "history_prev", "Prev", priority=True),
        Binding("down", "history_next", "Next", priority=True),
    ]

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._command_history: list[str] = []
        self._history_index = -1
        self._event_bus: Any = None
        self._handlers_registered = False

    def on_mount(self) -> None:
        """Setup setelah compose."""
        self._event_bus = getattr(self.app, "event_bus", None)
        self._chat_log = self.query_one("#chat-log", RichLog)
        self._chat_input = self.query_one("#chat-input", Input)

        # Auto-focus input
        self._chat_input.focus()

        # Register handler untuk co-pilot suggestion
        if self._event_bus and not self._handlers_registered:
            @self._event_bus.on("copilot.suggestion")
            async def _on_copilot(event: Any) -> None:
                suggestion = event.payload.get("suggestion", "")
                self._add_message("Antonio (Co-pilot)", suggestion, "italic cyan")

            @self._event_bus.on("agent.response")
            async def _on_agent_response(event: Any) -> None:
                msg = event.payload.get("message", "")
                self._add_message("Antonio", msg, "green")

            self._handlers_registered = True

        # Welcome message
        self._add_message(
            "System",
            "Selamat datang di VYPER TUI v2. Antonio AI Agent siap membantu.\n"
            "Ketik /help untuk daftar perintah.",
            "bold cyan",
        )

    def compose(self) -> Any:
        """Build chat panel UI."""
        yield RichLog(
            id="chat-log",
            highlight=True,
            markup=True,
            wrap=True,
            max_lines=100,
        )
        yield Input(
            placeholder="> /help untuk 40+ perintah  |  TAB autocomplete  |  F1-F4 mode",
            id="chat-input",
        )

    # ── History Navigation (bound to ↑↓) ──────────────────────────────

    def _restore_input_value(self, value: str) -> None:
        """Set input value and move cursor to end."""
        self._chat_input.value = value
        self._chat_input.cursor_position = len(value)

    def action_history_prev(self) -> None:
        """↑: Navigate to previous command in history."""
        if not self._command_history:
            return
        if self._history_index == -1:
            self._history_index = len(self._command_history) - 1
        else:
            self._history_index = max(0, self._history_index - 1)
        self._restore_input_value(self._command_history[self._history_index])

    def action_history_next(self) -> None:
        """↓: Navigate to next command in history."""
        if self._history_index == -1:
            return
        self._history_index += 1
        if self._history_index >= len(self._command_history):
            self._history_index = -1
            self._chat_input.value = ""
        else:
            self._restore_input_value(self._command_history[self._history_index])

    # ── Message Handling ──────────────────────────────────────────────

    def _add_message(
        self,
        sender: str,
        message: str,
        style: str = "",
    ) -> None:
        """Tambah pesan ke chat log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        chat_log = getattr(self, "_chat_log", None)
        if chat_log is None:
            return

        sender_colors = {
            "Anda": "bold white",
            "Antonio": "bold green",
            "Antonio (Co-pilot)": "italic cyan",
            "System": "bold cyan",
            "Error": "bold red",
        }
        sender_style = sender_colors.get(sender, "white")

        line = Text.assemble(
            (f"[{timestamp}] ", "dim white"),
            (f"{sender}: ", sender_style),
            (message, style or "white"),
        )
        chat_log.write(line)

    def _add_error(self, message: str) -> None:
        """Tambah pesan error."""
        self._add_message("Error", message, "red")

    def _handle_command(self, command: str) -> None:
        """Process slash command."""
        cmd_parts = command.strip().split()
        if not cmd_parts:
            return

        cmd = cmd_parts[0].lower()
        args = cmd_parts[1:]

        # ── Help ──
        if cmd == "/help":
            help_text = (
                "PERINTAH TERSEDIA:\n"
                "  /audit <address> [chain]  — Mulai audit baru\n"
                "  /status                    — Status semua service\n"
                "  /health                    — Health check services\n"
                "  /queue                     — Lihat antrian audit\n"
                "  /mode full|audit|agent|compact — Ganti layout\n"
                "  /restart <service>         — Restart service\n"
                "  /logs <service> [n]        — Lihat log service\n"
                "  /findings <audit_id>       — Lihat findings\n"
                "  /clear                     — Bersihkan chat\n"
                "  F1-F4                      — Ganti mode\n"
                "  q                          — Keluar"
            )
            self._add_message("System", help_text, "cyan")

        # ── Status ──
        elif cmd == "/status":
            state = self._get_state()
            if not state:
                self._add_message("System", "State belum tersedia.", "yellow")
                return

            n_svc = len(state.service_activities)
            n_busy = sum(
                1 for a in state.service_activities.values()
                if getattr(a, "status", "") == "busy"
            )
            n_idle = sum(
                1 for a in state.service_activities.values()
                if getattr(a, "status", "") == "idle"
            )
            n_audits = len(state.active_audits)
            n_queue = len(state.pipeline_queue)

            msg = (
                f"Services: {n_svc} aktif ({n_busy} busy, {n_idle} idle)\n"
                f"Audits: {n_audits} aktif, {n_queue} dalam antrian\n"
                f"Mode: {state.current_mode.upper()}"
            )
            self._add_message("System", msg, "cyan")

        # ── Health ──
        elif cmd == "/health":
            state = self._get_state()
            if not state:
                self._add_message("System", "State belum tersedia.", "yellow")
                return

            healthy = sum(1 for h in state.service_health.values() if h)
            unhealthy = sum(1 for h in state.service_health.values() if not h)
            msg = (
                f"Health check: {healthy} sehat, {unhealthy} bermasalah"
                if unhealthy
                else f"Health check: {healthy} service sehat \u2705"
            )
            self._add_message("System", msg, "cyan")

        # ── Mode ──
        elif cmd == "/mode" and args:
            mode = args[0]
            try:
                self.app.action_set_mode(mode)
                self._add_message("System", f"Mode \u2192 {mode.upper()}", "cyan")
            except Exception as e:
                self._add_error(f"Gagal ganti mode: {e}")

        # ── Clear ──
        elif cmd == "/clear":
            self._chat_log.clear()
            self._add_message("System", "Chat dibersihkan.", "dim")

        # ── Audit ──
        elif cmd == "/audit":
            if not args:
                self._add_error("Gunakan: /audit <address> [chain]")
                return
            address = args[0]
            chain = args[1] if len(args) > 1 else "ethereum"
            self._add_message("Anda", f"Memulai audit {address} ({chain})...")
            self._add_message(
                "Antonio",
                f"Audit dimulai untuk {address} di {chain}. "
                f"Mengambil data dari Immunefi...",
                "green",
            )

        # ── Restart ──
        elif cmd == "/restart":
            if not args:
                self._add_error("Gunakan: /restart <service_name>")
                return
            service = args[0]
            self._add_message("Anda", f"Restart {service}...")
            self._add_message(
                "Antonio",
                f"Mengirim perintah restart ke {service}...",
                "green",
            )

        # ── Unknown → treat as direct message to Antonio ──
        else:
            self._add_message("Anda", command)
            self._add_message(
                "Antonio",
                f"Saya menerima: \"{command[:80]}\". "
                f"Ketik /help untuk daftar perintah.",
                "green",
            )

    def _get_state(self) -> Any:
        """Dapatkan VyperState via AppState."""
        try:
            from cli.src.core.state_store import AppState
            return AppState.get()
        except Exception:
            return None

    # ── Input Events ─────────────────────────────────────────────────

    @on(Input.Submitted, "#chat-input")
    async def on_chat_submit(self, event: Input.Submitted) -> None:
        """Handle user submit chat input."""
        text = event.value.strip()
        if not text:
            return

        # Clear input
        self._chat_input.value = ""

        # Add to history
        self._command_history.append(text)
        self._history_index = -1

        # Process
        self._handle_command(text)

    # ── External API ─────────────────────────────────────────────────

    def add_message(self, sender: str, message: str, style: str = "") -> None:
        """API publik untuk menambah pesan dari luar."""
        self._add_message(sender, message, style)

    def add_copilot_suggestion(self, suggestion: str) -> None:
        """Tampilkan saran co-pilot dari Antonio."""
        self._add_message(
            "Antonio (Co-pilot)",
            f"\U0001f4a1 {suggestion}",
            "italic cyan",
        )
