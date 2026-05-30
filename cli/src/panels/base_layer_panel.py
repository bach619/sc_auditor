"""
VYPER TUI v2 — LayerPanel Base Class

Base class untuk semua 6 Layer Panel.
Menyediakan infrastruktur umum:
  - Koneksi EventBus (service.activity & service.health)
  - Akses AppState reaktif
  - Helper render: status icon, warna, sparkline, health icon
  - Drill-down shortcut (Enter → Service Detail)
  - Keyboard nav: ↑/↓/r/l
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from rich.style import Style
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from cli.src.core.event_bus import EventBus
from cli.src.core.state_store import AppState, VyperState
from cli.src.models.activity import ServiceActivity

logger = logging.getLogger("vyper_tui.panels.base")

SPARKLINE_CHARS = " ▁▂▃▄▅▆▇█"


class LayerPanel(Widget):
    """
    Abstract base class untuk Layer Panel 1-6.

    Override di subclass:
        PANEL_TITLE: str          — Judul panel (e.g. "DATA & CONFIG")
        SERVICES: list[tuple]     — [(name, port), ...]

        render() -> str           — Method render utama

    Tersedia:
        self.event_bus            — Referensi EventBus
        self._focused_idx         — Index service yang sedang di-focus
        self._focused_service     — Nama service yang di-focus
    """

    PANEL_TITLE: ClassVar[str] = "LAYER"
    SERVICES: ClassVar[list[tuple[str, int]]] = []

    # Reactive: otomatis trigger refresh saat berubah
    _focused_idx: reactive[int] = reactive(0)

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._event_bus: EventBus | None = None
        self._active_for_audit: str | None = None
        self._handlers_registered = False

    def on_mount(self) -> None:
        """Setup koneksi EventBus dan register handlers."""
        self._event_bus = getattr(self.app, "event_bus", None)
        if self._event_bus and not self._handlers_registered:
            self._register_default_handlers()
            self._handlers_registered = True

    # ── Event Handlers ──────────────────────────────────────────────────

    def _register_default_handlers(self) -> None:
        """Daftarkan handler default untuk activity & health events."""

        @self._event_bus.on("service.activity")
        async def _on_activity(event: Any) -> None:
            if event.service in [s[0] for s in self.SERVICES]:
                self.refresh()

        @self._event_bus.on("service.health")
        async def _on_health(event: Any) -> None:
            if event.service in [s[0] for s in self.SERVICES]:
                self.refresh()

    # ── Render Helpers ──────────────────────────────────────────────────

    def _status_icon(self, status: str) -> str:
        """
        Konversi status → visual icon sesuai Motion System v2.

        idle → 💤, busy → ⣾ (spinner rotation via tick),
        pending → ⏳, error → ⚠️, unknown → ?
        """
        icons = {
            "idle":    "\U0001f4a4",   # 💤
            "busy":    "\u28fe",        # ⣾  akan dirotasi oleh spinner tick
            "pending": "\u23f3",        # ⏳
            "error":   "\u26a0\ufe0f",  # ⚠️
            "unknown": "?",
        }
        return icons.get(status, "?")

    def _status_color(self, status: str) -> str:
        """Konversi status → CSS color class untuk Textual."""
        colors = {
            "idle":    "dim",
            "busy":    "success",
            "pending": "warning",
            "error":   "error",
            "unknown": "muted",
        }
        return colors.get(status, "muted")

    def _status_rich_style(self, status: str) -> Style:
        """Konversi status → Rich Style untuk render kustom."""
        style_map = {
            "idle":    Style(dim=True, color="grey"),
            "busy":    Style(color="green", bold=True),
            "pending": Style(color="yellow"),
            "error":   Style(color="red", bold=True),
            "unknown": Style(dim=True, color="grey35"),
        }
        return style_map.get(status, Style())

    def _health_icon(self, healthy: bool | None) -> str:
        """✅ / ❌ / ❓ berdasarkan health status."""
        if healthy is True:
            return "\u2705"      # ✅
        if healthy is False:
            return "\u274c"      # ❌
        return "\u2753"          # ❓

    def _health_color(self, healthy: bool | None) -> str:
        if healthy is True:
            return "success"
        if healthy is False:
            return "error"
        return "muted"

    def _render_sparkline(self, samples: list[int], width: int = 20) -> str:
        """
        Render list[0-100] → ASCII sparkline bar.

        Args:
            samples: List nilai 0-100 (contoh: CPU proxy)
            width:   Jumlah karakter output

        Returns:
            String sparkline (e.g. " ▁▂▃▅▇████▇▅▃▂▁")

        Contoh:
            [0, 0, 50, 100, 100, 50, 0] → " ▁▃▇██▇▃"
        """
        if not samples:
            return " " * width

        step = max(1, len(samples) // width)
        selected = samples[-width::step] if step > 0 else samples[-width:]

        return "".join(
            SPARKLINE_CHARS[min(8, max(0, int(s * 8 // 101)))]
            for s in selected
        )

    def _render_progress_bar(self, progress: int, width: int = 14) -> str:
        """
        Render progress bar: [██████░░░░░░]

        Args:
            progress: 0-100
            width:    Total lebar bar

        Returns:
            String progress bar
        """
        filled = max(0, min(width, int(progress / 100 * width)))
        return "\u2588" * filled + "\u2591" * (width - filled)

    # ── Keyboard Navigation ─────────────────────────────────────────────

    @property
    def _focused_service(self) -> str | None:
        """Nama service yang sedang di-focus."""
        if not self.SERVICES or self._focused_idx >= len(self.SERVICES):
            return None
        return self.SERVICES[self._focused_idx][0]

    def on_key(self, event: Any) -> None:
        """Panel-level keyboard shortcuts."""
        key = getattr(event, "key", None)

        if key == "up":
            self._focus_prev()
        elif key == "down":
            self._focus_next()
        elif key == "enter":
            self._open_service_detail()
        elif key == "r":
            self._restart_focused()
        elif key == "l":
            self._open_logs()

    def _focus_next(self) -> None:
        """Pindah fokus ke service berikutnya (wrap-around)."""
        if not self.SERVICES:
            return
        self._focused_idx = (self._focused_idx + 1) % len(self.SERVICES)

    def _focus_prev(self) -> None:
        """Pindah fokus ke service sebelumnya (wrap-around)."""
        if not self.SERVICES:
            return
        self._focused_idx = (self._focused_idx - 1) % len(self.SERVICES)

    def _open_service_detail(self) -> None:
        """Buka Service Detail Overlay (drill-down). Default: no-op."""
        logger.debug(
            "Drill-down: %s → %s",
            self.PANEL_TITLE,
            self._focused_service,
        )
        # Override di subclass atau gunakan app-level screen push
        # self.app.push_screen("service_detail", service=self._focused_service)

    def _restart_focused(self) -> None:
        """Trigger restart service terfokus."""
        svc = self._focused_service
        if svc:
            logger.info("Restart requested: %s", svc)
            # self.app.command_router.execute(f"/restart {svc}")

    def _open_logs(self) -> None:
        """Buka logs panel untuk service terfokus."""
        svc = self._focused_service
        if svc:
            logger.info("Logs requested: %s", svc)
            # self.app.command_router.execute(f"/logs {svc}")

    # ── Service Window Renderer ────────────────────────────────────────

    WINDOW_WIDTH: ClassVar[int] = 49   # lebar total service window
    TASK_WIDTH: ClassVar[int] = 20     # lebar kolom task description
    LABEL_WIDTH: ClassVar[int] = 10    # lebar kolom label service

    def _render_service_window(
        self,
        svc_name: str,
        port: int,
        activity: ServiceActivity | None,
        healthy: bool | None,
        sparkline: list[int],
        is_focused: bool = False,
        extra_lines: list[str] | None = None,
    ) -> list[str]:
        """
        Render SATU service sebagai bordered "mini-window".

        Format:
          ┌─ 01-Config ─────────────────────┐
          │ ▶ ✅ 💤  Config  :8011  task... │
          │   ▁▂▃▅▇████▇▅▃▂▁               │
          │   [████████░░░░] 62%           │
          └──────────────────────────────────┘

        Width calculation (W=49, T=20, L=10):
          │ + space + focus(2) + health(1) + space + icon(1) + 2sp
          + label(L) + port(6) + space + task(T) + │
          = 1+1+2+1+1+1+2+L+6+1+T+1 = 16+L+T = 16+10+20 = 46
          → 49 total (3 spare for emoji width compensation)
        """
        status = getattr(activity, "status", "unknown") if activity else "unknown"
        task = getattr(activity, "short_task", lambda w: "")(self.TASK_WIDTH) if activity else ""

        icon = self._status_icon(status)
        health = self._health_icon(healthy)

        # Focus indicator (▶ + space, or 2 spaces)
        focus_marker = "\u25b6 " if is_focused else "  "

        # ── Title bar: ┌─ 01-config ──────────────────────────────────┐
        title_str = f" {svc_name} "
        # ┌(1) + title_str + dashes + ┐(1) = WINDOW_WIDTH
        dash_count = self.WINDOW_WIDTH - 2 - len(title_str)
        title_bar = (
            "\u250c" + title_str + "\u2500" * max(0, dash_count) + "\u2510"
        )

        # ── Status line: │ ▶ ✅ 💤  Config  :8011  task... │
        svc_label = svc_name.split("-", 1)[1][:self.LABEL_WIDTH].capitalize()
        port_str = f":{port}"
        # Pad port_str to exactly 6 chars (":8011" → ":8011 ")
        port_str = f"{port_str:<6}"

        # Content available for task after fixed overhead
        # │(1) sp(1) focus(2) health(1) sp(1) icon(1) sp(2) label(10) port(6) sp(1) │(1) = 26
        # Available = WINDOW_WIDTH - 26 = 49 - 26 = 23
        avail_task = self.WINDOW_WIDTH - 1 - 1 - 2 - 1 - 1 - 1 - 2 - self.LABEL_WIDTH - 6 - 1 - 1
        task_part = task[:avail_task].ljust(avail_task)

        status_line = (
            f"\u2502 {focus_marker}{health} {icon}  "
            f"{svc_label:<{self.LABEL_WIDTH}}{port_str}"
            f"{task_part}\u2502"
        )

        # ── Content lines ──
        lines: list[str] = [title_bar, status_line]

        # Sparkline (indented 3 spaces from left)
        spark_inner = self.WINDOW_WIDTH - 7  # │ + 3sp + content + 3sp + │
        spark = self._render_sparkline(sparkline, width=spark_inner)
        lines.append(f"\u2502   {spark}{' ' * 3}\u2502")

        # Progress bar (jika ada)
        progress = getattr(activity, "progress", None) if activity else None
        if progress is not None:
            bar = self._render_progress_bar(progress, width=14)
            pct = f"{progress:3d}%"
            line = f"\u2502   [{bar}] {pct}{' ' * 20}\u2502"
            lines.append(line[:self.WINDOW_WIDTH])

        # Extra lines (subclass-specific: sub-tasks, metrics, etc.)
        inner_width = self.WINDOW_WIDTH - 6  # │ + 3sp + content + 2sp + wait... 
        # Actually: │ + 3sp + content + │ = WINDOW_WIDTH, so content = WINDOW_WIDTH - 5
        inner_width = self.WINDOW_WIDTH - 5
        if extra_lines:
            for el in extra_lines:
                padded = el[:inner_width]
                lines.append(f"\u2502   {padded:<{inner_width}}\u2502")

        # ── Bottom border ──
        lines.append(
            f"\u2514{'\u2500' * (self.WINDOW_WIDTH - 2)}\u2518"
        )

        return lines

    def _render_panel_header(self, title: str, suffix: str = "") -> str:
        """Render header panel: ╭─ TITLE ──────────────────────────────╮"""
        full_title = f" {title} "
        if suffix:
            full_title += f" {suffix} "
        # ╭(1) + full_title + dashes + ╮(1) = WINDOW_WIDTH
        dash_count = self.WINDOW_WIDTH - 2 - len(full_title)
        return (
            "\u256d" + full_title + "\u2500" * max(0, dash_count) + "\u256e"
        )

    def _render_panel_footer(self) -> str:
        """Render footer panel: ╰──────────────────────────────────────╯"""
        return f"\u2570{'\u2500' * (self.WINDOW_WIDTH - 2)}\u256f"

    # ── Render ──────────────────────────────────────────────────────────

    def render(self) -> str:
        """Override di subclass."""
        return f"{self.PANEL_TITLE} — {len(self.SERVICES)} services"
