"""Vyper Chat TUI — Textual-based AI Chatbot for pipeline monitoring.

Copy-paste & text selection:
  y / ctrl+y  → Copy last AI response to clipboard
  Y            → Copy entire conversation to clipboard
  p            → Copy last AI response as plain text (no markdown)
  P            → Copy entire conversation as plain text
  F2 / ctrl+s  → Toggle SELECT MODE (free mouse for terminal text selection)
  Mouse        → Hold Alt while selecting for native terminal selection

Slash Commands:
  /connect    → Set API key for an AI provider
  /provider   → Choose / switch AI provider
  /model      → Change model for active provider
  /providers  → List all available AI providers
  /models     → List models for a specific provider
  /help       → Show help
  /clear      → Clear chat history
  Type "/" to show the menu, arrows to navigate, Enter to select.
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Any

from textual.app import App, ComposeResult
from textual import events, work
from textual.reactive import reactive
from textual.widgets import Header, Input, RichLog, Static

from cli.chat.engine import ChatEngine

# ── Custom Input with slash-menu arrow interception ────────────

class SlashInput(Input):
    """Input widget that intercepts arrow keys when the slash menu is active.

    Overrides cursor-up/cursor-down actions so the menu takes precedence
    over cursor movement while the menu is visible.
    """

    def action_cursor_up(self) -> None:
        app = self.app
        if app._slash_active:  # type: ignore[union-attr]
            app.action_slash_up()  # type: ignore[union-attr]
        else:
            super().action_cursor_up()

    def action_cursor_down(self) -> None:
        app = self.app
        if app._slash_active:  # type: ignore[union-attr]
            app.action_slash_down()  # type: ignore[union-attr]
        else:
            super().action_cursor_down()


# ── Slash Commands ──────────────────────────────────────────────

SLASH_COMMANDS: list[dict[str, str]] = [
    {
        "command": "/connect",
        "label": "Connect AI",
        "description": "Set API key untuk provider AI",
        "icon": "\u26a1",
    },
    {
        "command": "/provider",
        "label": "Provider AI",
        "description": "Pilih atau ganti AI provider yang aktif",
        "icon": "\u2699",
    },
    {
        "command": "/model",
        "label": "Model",
        "description": "Ganti model untuk provider aktif",
        "icon": "\u2699",
    },
    {
        "command": "/providers",
        "label": "Providers",
        "description": "Lihat semua provider AI tersedia",
        "icon": "\u2139",
    },
    {
        "command": "/models",
        "label": "Models",
        "description": "Lihat daftar model per provider",
        "icon": "\u2139",
    },
    {
        "command": "/help",
        "label": "Help",
        "description": "Tampilkan bantuan perintah",
        "icon": "\u2753",
    },
    {
        "command": "/clear",
        "label": "Clear",
        "description": "Hapus riwayat chat",
        "icon": "\u2702",
    },
]

# ── Mouse escape sequences ─────────────────────────────────────
# Application Mouse Mode: when active, the terminal captures mouse
# events for the TUI, preventing native text selection.
# We send these directly to stdout/stdin to toggle.

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


# ── Clipboard ─────────────────────────────────────────────────

_RICH_TAG_RE = re.compile(r"\[/?\w+(?:[^\]]*)?\]")


def _strip_rich_markup(text: str) -> str:
    """Remove Rich markup tags like [bold], [dim], [green], [/], etc."""
    return _RICH_TAG_RE.sub("", text)


def _copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard. Returns True on success.

    Tries pyperclip first, then falls back to platform-specific commands.
    """
    if not text.strip():
        return False

    # Try pyperclip (best, cross-platform)
    try:
        import pyperclip  # type: ignore

        pyperclip.copy(text)
        return True
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: platform-specific clip commands
    try:
        if sys.platform == "win32":
            proc = subprocess.Popen(
                ["clip"], stdin=subprocess.PIPE, shell=True,
                text=True, encoding="utf-8", errors="replace",
            )
            proc.communicate(input=text)
            return proc.returncode == 0
        elif sys.platform == "darwin":
            proc = subprocess.Popen(
                ["pbcopy"], stdin=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
            )
            proc.communicate(input=text)
            return proc.returncode == 0
        else:
            for cmd in (["xclip", "-selection", "clipboard"], ["xsel", "-i", "-b"]):
                try:
                    proc = subprocess.Popen(
                        cmd, stdin=subprocess.PIPE,
                        text=True, encoding="utf-8", errors="replace",
                    )
                    proc.communicate(input=text)
                    if proc.returncode == 0:
                        return True
                except FileNotFoundError:
                    continue
    except Exception:
        pass

    return False


# ── Chat App ──────────────────────────────────────────────────


class ChatApp(App):
    """Vyper AI Chat — interactive pipeline chatbot."""

    TITLE = "VYPER AI Chat"
    CSS = """
    Screen {
        background: $surface;
    }

    Header {
        dock: top;
    }

    #chat-area {
        height: 1fr;
        border: solid $primary;
        margin: 0 1;
        padding: 0 1;
        overflow-y: auto;
    }

    #input-row {
        dock: bottom;
        height: 5;
        padding: 0 1 1 1;
    }

    Input {
        width: 100%;
    }

    .message-user {
        color: $text;
    }

    .message-bot {
        color: $accent;
    }

    #status-bar {
        dock: top;
        height: 1;
        padding: 0 1;
    }

    #typing {
        height: 1;
        padding: 0 1;
        color: $secondary;
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

    /* ── Slash Command Menu ──────────────────────────────── */
    #slash-menu {
        height: auto;
        max-height: 10;
        margin: 0 1;
        padding: 0 1;
        border: tall $primary;
        background: $surface;
        display: none;
        overflow-y: auto;
    }
    """

    BINDINGS = [
        ("q", "exit", "Exit"),
        ("escape", "clear_input", "Clear input"),
        ("c", "clear_chat", "Clear chat"),
        # ── Copy-paste bindings ──
        ("y", "copy_last", "Copy last response"),
        ("ctrl+y", "copy_all", "Copy all chat"),
        ("p", "copy_last_plain", "Copy last (plain)"),
        ("ctrl+p", "copy_all_plain", "Copy all (plain)"),
        # ── Text selection toggle ──
        ("f2", "toggle_selection", "Toggle select mode"),
        ("ctrl+s", "toggle_selection", "Toggle select mode"),
    ]

    selection_mode: reactive[bool] = reactive(False)

    def __init__(self) -> None:
        super().__init__()
        self.engine = ChatEngine()
        # Conversation history: list of {"role": "user"|"assistant", "content": str}
        self._history: list[dict[str, str]] = []
        # Slash menu state
        self._slash_active = False
        self._slash_index = 0  # currently highlighted item index
        self._slash_matched_commands: list[dict[str, str]] = []

    # ── Selection mode ─────────────────────────────────────────

    def watch_selection_mode(self, old: bool, new: bool) -> None:
        """React to selection_mode changes: toggle mouse capture."""
        indicator = self.query_one("#selection-indicator", Static)
        if new:
            _disable_mouse_mode()
            indicator.display = "block"
            indicator.update(
                "[bold yellow]\U0001f4dd SELECT MODE[/bold yellow]  —  "
                "[dim]Select text with mouse, press F2 to return[/dim]"
            )
        else:
            _enable_mouse_mode()
            indicator.display = "none"

    def action_toggle_selection(self) -> None:
        """Toggle selection mode on/off."""
        self.selection_mode = not self.selection_mode

    # ── Lifecycle ─────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="status-bar")
        yield RichLog(id="chat-area", highlight=True, markup=True, max_lines=1000)
        yield Static(id="typing")
        # Single Static widget — only Static.update() and display toggle,
        # NO widget tree mutations (safe on Windows during message phase).
        yield Static(id="slash-menu", markup=True)
        yield SlashInput(id="chat-input", placeholder="Ketik pertanyaan atau ketik / untuk menu...")
        yield Static(id="clipboard-msg")
        yield Static(id="selection-indicator")

    async def on_mount(self) -> None:
        """Initialize engine and show welcome message."""
        welcome = await self.engine.initialize()
        log = self.query_one("#chat-area", RichLog)
        log.write("[bold green]\U0001f916 VYPER AI Assistant[/bold green]")
        log.write("")
        log.write(welcome)
        log.write("")
        log.write("[dim]\u2500" * 50 + "[/dim]")
        self._update_status(
            "Ready \u2705  |  "
            "[bold]y[/] copy  [bold]Y[/] all  "
            "[bold]p[/] plain  [bold]F2[/] select  [bold]q[/] quit"
        )
        # Ensure slash menu is hidden initially
        self.query_one("#slash-menu", Static).display = "none"
        self.query_one("#chat-input", Input).focus()

    def _update_status(self, text: str) -> None:
        self.query_one("#status-bar", Static).update(f"[dim]{text}[/dim]")

    def _flash_clipboard(self, msg: str) -> None:
        """Show a brief clipboard message at the bottom."""
        w = self.query_one("#clipboard-msg", Static)
        w.update(f"[green]\u2705 {msg}[/]")
        w.display = "block"
        self.set_timer(2.5, lambda: w.update("") or setattr(w, "display", "none"))

    def _show_typing(self, visible: bool = True) -> None:
        self.query_one("#typing", Static).update(
            "[dim italic]\U0001f916 VYPER AI sedang mengetik...[/dim italic]" if visible else ""
        )

    # ── Slash Command Menu ──────────────────────────────────────

    def _build_menu_text(self) -> str:
        """Build the menu text with a marker (▸) on the selected item."""
        lines: list[str] = []
        visible = self._slash_matched_commands
        for idx, cmd in enumerate(visible):
            marker = "[bold yellow]▸[/] " if idx == self._slash_index else "  "
            lines.append(
                f"{marker}[bold]{cmd['command']}[/bold]  "
                f"{cmd['label']}  "
                f"[dim]{cmd['description']}[/dim]"
            )
        return "\n".join(lines)

    def _rebuild_slash_menu(self) -> None:
        """Refresh the menu text after index change."""
        menu = self.query_one("#slash-menu", Static)
        if not self._slash_matched_commands:
            menu.display = "none"
            self._slash_active = False
            return
        menu.update(self._build_menu_text())
        menu.display = "block"
        self._slash_active = True

    def on_input_changed(self, event: Input.Changed) -> None:
        """Detect '/' at start of input to show slash command menu.

        Uses only Static.update() and display toggle — no widget tree
        mutations (no mount/remove/clear/append), safe during message phase.
        """
        value = event.value
        menu = self.query_one("#slash-menu", Static)

        if not value.startswith("/") or " " in value:
            menu.display = "none"
            self._slash_active = False
            self._slash_matched_commands = []
            return

        prefix = value.rstrip()

        # Filter commands matching the typed prefix
        matched: list[dict[str, str]] = []
        for cmd in SLASH_COMMANDS:
            if cmd["command"].startswith(prefix):
                matched.append(cmd)

        if matched:
            self._slash_matched_commands = matched
            self._slash_index = 0
            menu.update(self._build_menu_text())
            menu.display = "block"
            self._slash_active = True
        else:
            self._slash_matched_commands = []
            menu.display = "none"
            self._slash_active = False

    def _hide_slash_menu(self) -> None:
        """Hide the slash command menu."""
        menu = self.query_one("#slash-menu", Static)
        menu.display = "none"
        self._slash_active = False
        self._slash_matched_commands = []
        # Refocus input so user can keep typing
        self.query_one("#chat-input", Input).focus()

    def action_slash_up(self) -> None:
        """Move selection up in the slash menu."""
        if not self._slash_matched_commands:
            return
        self._slash_index = max(0, self._slash_index - 1)
        self._rebuild_slash_menu()

    def action_slash_down(self) -> None:
        """Move selection down in the slash menu."""
        if not self._slash_matched_commands:
            return
        self._slash_index = min(len(self._slash_matched_commands) - 1, self._slash_index + 1)
        self._rebuild_slash_menu()

    def action_slash_select(self) -> None:
        """Select the currently highlighted slash command and insert it."""
        if not self._slash_matched_commands:
            return
        cmd_name = self._slash_matched_commands[self._slash_index]["command"]
        inp = self.query_one("#chat-input", Input)
        inp.value = f"{cmd_name} "
        inp.cursor_position = len(inp.value)
        self._hide_slash_menu()

    def action_slash_hide(self) -> None:
        """Hide the slash menu (bound to Escape)."""
        if self._slash_active:
            self._hide_slash_menu()

    def on_key(self, event: events.Key) -> None:
        """Intercept Enter/Escape when slash menu is active.

        Arrow up/down is handled by SlashInput subclass. Only uses
        Static.update() and display toggle — no widget tree mutations.
        """
        if not self._slash_active:
            return

        key = event.key

        if key == "enter":
            # Only intercept Enter if the input is a pure slash command prefix
            inp = self.query_one("#chat-input", Input)
            if "/" in inp.value and " " not in inp.value:
                event.stop()
                self.action_slash_select()
        elif key == "escape":
            event.stop()
            self.action_slash_hide()
        elif key == "up":
            # Safety net in case SlashInput didn't catch it
            event.stop()
            self.action_slash_up()
        elif key == "down":
            event.stop()
            self.action_slash_down()

    # ── Message handling ──────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission."""
        question = event.value.strip()
        if not question:
            return

        # If a slash command is active and Enter was not intercepted by on_key,
        # the user typed a full command with arguments (has space).
        if self._slash_active:
            self._hide_slash_menu()
            # Fall through to submit

        # Clear input
        event.input.value = ""

        self._submit_question(question)

    def _submit_question(self, question: str) -> None:
        """Submit a question to the chat engine."""
        if not question.strip():
            return

        self._history.append({"role": "user", "content": question})
        log = self.query_one("#chat-area", RichLog)
        log.write("")
        log.write("[bold cyan]\U0001f9d1 You:[/bold cyan]")
        log.write(question)
        log.write("")

        self._update_status("Processing...")
        self._show_typing(True)

        self._process_question(question)

    @work(thread=False, exit_on_error=False)
    async def _process_question(self, question: str) -> None:
        """Process question asynchronously."""
        try:
            answer = await self.engine.answer(question)
        except Exception as exc:
            answer = f"\u26a0\ufe0f Error: {exc}"

        self._show_typing(False)
        self._history.append({"role": "assistant", "content": answer})
        log = self.query_one("#chat-area", RichLog)
        log.write("[bold green]\U0001f916 VYPER AI:[/bold green]")
        log.write(answer)
        log.write("")
        log.write("[dim]\u2500" * 50 + "[/dim]")

        sel_indicator = "  [bold yellow]\U0001f4dd SELECT[/bold yellow]" if self.selection_mode else ""
        self._update_status(
            "Ready \u2705  |  "
            "[bold]y[/] copy  [bold]Y[/] all  "
            "[bold]p[/] plain  [bold]F2[/] select  [bold]q[/] quit"
            f"{sel_indicator}"
        )

        # Scroll to bottom
        log.scroll_end()

    # ── Clipboard actions ─────────────────────────────────────

    def _get_last_response(self) -> str:
        """Get the last assistant response text (stripped of Rich markup)."""
        for msg in reversed(self._history):
            if msg["role"] == "assistant":
                return _strip_rich_markup(msg["content"])
        return ""

    def _get_all_text(self) -> str:
        """Get full conversation as formatted text."""
        lines: list[str] = []
        for msg in self._history:
            role = "You" if msg["role"] == "user" else "VYPER AI"
            content = _strip_rich_markup(msg["content"])
            lines.append(f"[{role}]")
            lines.append(content)
            lines.append("")
        return "\n".join(lines)

    def _get_last_response_raw(self) -> str:
        """Get the last assistant response WITHOUT stripping Rich markup."""
        for msg in reversed(self._history):
            if msg["role"] == "assistant":
                return msg["content"]
        return ""

    def _get_all_text_raw(self) -> str:
        """Get full conversation as plain text (Rich tags stripped only)."""
        lines: list[str] = []
        for msg in self._history:
            role = "You" if msg["role"] == "user" else "VYPER AI"
            content = _strip_rich_markup(msg["content"])
            lines.append(f"[{role}]")
            lines.append(content)
            lines.append("")
        return "\n".join(lines)

    def action_copy_last(self) -> None:
        """Copy last AI response (Rich-stripped) to clipboard."""
        text = self._get_last_response()
        if not text:
            self._flash_clipboard("No response to copy")
            return
        if _copy_to_clipboard(text):
            self._flash_clipboard(f"Copied last response ({len(text)} chars)")
        else:
            self._flash_clipboard("Clipboard not available \u2014 select text manually")

    def action_copy_all(self) -> None:
        """Copy entire conversation to clipboard."""
        text = self._get_all_text()
        if not text:
            self._flash_clipboard("No chat history to copy")
            return
        if _copy_to_clipboard(text):
            self._flash_clipboard(f"Copied entire chat ({len(text)} chars)")
        else:
            self._flash_clipboard("Clipboard not available \u2014 select text manually")

    def action_copy_last_plain(self) -> None:
        """Copy last AI response as-is (with markdown, no Rich tags)."""
        text = self._get_last_response_raw()
        if not text:
            self._flash_clipboard("No response to copy")
            return
        plain = _strip_rich_markup(text)
        if _copy_to_clipboard(plain):
            self._flash_clipboard(f"Copied last response (plain, {len(plain)} chars)")
        else:
            self._flash_clipboard("Clipboard not available \u2014 select text manually")

    def action_copy_all_plain(self) -> None:
        """Copy entire conversation as plain text."""
        text = self._get_all_text_raw()
        if not text:
            self._flash_clipboard("No chat history to copy")
            return
        if _copy_to_clipboard(text):
            self._flash_clipboard(f"Copied entire chat (plain, {len(text)} chars)")
        else:
            self._flash_clipboard("Clipboard not available \u2014 select text manually")

    # ── Other actions ─────────────────────────────────────────

    def action_clear_input(self) -> None:
        self.query_one("#chat-input", Input).value = ""

    def action_clear_chat(self) -> None:
        self._history.clear()
        log = self.query_one("#chat-area", RichLog)
        log.clear()
        log.write("[dim]Chat cleared. Ketik pertanyaan baru![/dim]")
        self._update_status(
            "Cleared \u2705  |  "
            "[bold]y[/] copy  [bold]Y[/] all  "
            "[bold]p[/] plain  [bold]F2[/] select  [bold]q[/] quit"
        )

    def action_exit(self) -> None:
        """Exit — cancel workers, let Textual restore terminal."""
        _enable_mouse_mode()  # restore terminal state
        self.exit()

    async def on_shutdown(self) -> None:
        _enable_mouse_mode()  # ensure terminal is restored
        await self.engine.close()
        # Force exit AFTER Textual restores terminal state
        import os
        os._exit(0)
