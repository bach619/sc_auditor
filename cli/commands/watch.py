"""Watch command — real-time event watcher for Vyper services.

Usage:
    vyper watch                        Watch all events
    vyper watch --level ERROR          Only ERROR + CRITICAL
    vyper watch --notify discord        Send alerts to Discord
    vyper watch --json                 Output as NDJSON for piping
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
from datetime import datetime
from typing import Any

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cli.client import VyperClient
from cli.output import show_error

app = typer.Typer()
console = Console()
err_console = Console(stderr=True)

LEVEL_ORDER = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3, "SUCCESS": 4, "DEBUG": 5}

STYLES = {
    "CRITICAL": ("bold red", "⚡"),
    "ERROR": ("red", "❌"),
    "WARNING": ("yellow", "⚠️"),
    "INFO": ("green", "ℹ️"),
    "SUCCESS": ("green bold", "✅"),
    "DEBUG": ("dim", "🔍"),
}


def _send_notification(channel: str, title: str, message: str) -> None:
    """Send notification via configured channel."""
    if channel == "bell":
        sys.stdout.write("\a")
        sys.stdout.flush()
    elif channel == "desktop":
        try:
            if sys.platform == "darwin":
                subprocess.run(
                    ["osascript", "-e",
                     f'display notification "{message}" with title "{title}"'],
                    capture_output=True, timeout=2,
                )
            elif sys.platform == "linux":
                subprocess.run(
                    ["notify-send", title, message],
                    capture_output=True, timeout=2,
                )
        except Exception:
            pass
    elif channel == "discord":
        webhook = os.environ.get("VYPER_DISCORD_WEBHOOK")
        if webhook:
            try:
                import httpx
                httpx.post(webhook, json={
                    "content": f"**{title}**\n{message[:1900]}",
                }, timeout=5)
            except Exception:
                pass


async def _watch_loop(
    level: str,
    interval: float,
    notify: str,
    json_output: bool,
    stop_event: asyncio.Event,
) -> None:
    """Core watch loop — poll services and stream events."""
    async with VyperClient() as client:
        last_audits: dict[str, str] = {}
        healthy_services: set[str] = set()

        while not stop_event.is_set():
            now = datetime.now()

            # ── Poll audits ──
            try:
                audits = await client.get_audits(limit=20)
                for audit in audits:
                    if not isinstance(audit, dict):
                        continue
                    aid = audit.get("audit_id", "")
                    state = audit.get("state", "UNKNOWN")
                    prev_state = last_audits.get(aid)

                    if prev_state is None:
                        # New audit
                        level_tag = "SUCCESS" if state == "completed" else "INFO"
                        icon = "✅" if state == "completed" else "🆕"
                        event = {
                            "time": now.isoformat(),
                            "level": level_tag,
                            "icon": icon,
                            "message": f"Audit {aid[:8]} started — {state}",
                            "audit_id": aid,
                        }
                        last_audits[aid] = state
                    elif prev_state != state:
                        # State change
                        if "failed" in state or "timeout" in state:
                            level_tag, icon = "ERROR", "❌"
                        elif state == "completed":
                            level_tag, icon = "SUCCESS", "✅"
                        else:
                            level_tag, icon = "INFO", "🔄"

                        dur = audit.get("duration_seconds", 0)
                        dur_str = f" ({dur:.1f}s)" if dur else ""
                        event = {
                            "time": now.isoformat(),
                            "level": level_tag,
                            "icon": icon,
                            "message": f"Audit {aid[:8]} {prev_state} → {state}{dur_str}",
                            "audit_id": aid,
                        }
                        last_audits[aid] = state
                    else:
                        continue

                    # Filter by level
                    if LEVEL_ORDER.get(event["level"], 99) > LEVEL_ORDER.get(level, 99):
                        continue

                    if json_output:
                        print(json.dumps(event, default=str), flush=True)
                        continue

                    style, _ = STYLES.get(event["level"], ("white", "▪"))
                    ts = event["time"][11:19] if isinstance(event["time"], str) else ""
                    icon = event["icon"]
                    msg = event["message"]

                    console.print(f"  [dim]{ts}[/] {icon} [{style}]{event['level']:8}[/] {msg}")

                    # Send notification if configured
                    if notify and event["level"] in ("ERROR", "CRITICAL"):
                        _send_notification(
                            notify,
                            f"Vyper {event['level']}: {aid[:8]}",
                            event["message"],
                        )

                # ── Health check ──
                try:
                    health = await client.health_all()
                    for svc in health:
                        name = svc.get("name", "?")
                        status = svc.get("status", "unknown")
                        if status == "healthy":
                            if name not in healthy_services:
                                healthy_services.add(name)
                                event = {
                                    "time": now.isoformat(),
                                    "level": "SUCCESS",
                                    "icon": "✅",
                                    "message": f"{name} — service recovered",
                                }
                                if LEVEL_ORDER.get(event["level"], 99) <= LEVEL_ORDER.get(level, 99):
                                    if json_output:
                                        print(json.dumps(event, default=str), flush=True)
                                    else:
                                        console.print(
                                            f"  [dim]{now.strftime('%H:%M:%S')}[/] "
                                            f"✅ [green]SUCCESS  [/] {name} — service recovered"
                                        )
                                        if notify:
                                            _send_notification(notify, "Vyper Service Up", f"{name} recovered")
                        elif name in healthy_services:
                            healthy_services.discard(name)
                            event = {
                                "time": now.isoformat(),
                                "level": "ERROR",
                                "icon": "❌",
                                "message": f"{name} — service DOWN",
                            }
                            if LEVEL_ORDER.get(event["level"], 99) <= LEVEL_ORDER.get(level, 99):
                                if json_output:
                                    print(json.dumps(event, default=str), flush=True)
                                else:
                                    console.print(
                                        f"  [dim]{now.strftime('%H:%M:%S')}[/] "
                                        f"❌ [red]ERROR     [/] {name} — service DOWN"
                                    )
                                    if notify:
                                        _send_notification(notify, "Vyper Service Down", f"{name} is down")
                except Exception:
                    pass

            except Exception:
                pass

            await asyncio.sleep(interval)


@app.callback()
def callback() -> None:
    """Watch Vyper events in real-time."""


@app.command()
def watch(
    level: str = typer.Option("INFO", "--level", "-l",
                              help="Minimum event level (CRITICAL/ERROR/WARNING/INFO/SUCCESS)"),
    interval: float = typer.Option(3.0, "--interval", "-i",
                                   help="Polling interval in seconds"),
    notify: str = typer.Option("", "--notify", "-n",
                               help="Send notifications on ERROR/CRITICAL "
                                    "(bell/desktop/discord)"),
    json_output: bool = typer.Option(False, "--json", "-j",
                                     help="Output as NDJSON for piping"),
) -> None:
    """Watch Vyper events in real-time — audits, state changes, service health.

    Examples:
        vyper watch                                # all events
        vyper watch --level ERROR                  # only errors
        vyper watch --notify desktop               # desktop alerts on error
        vyper watch --json | jq '.message'         # pipe to jq
    """
    level = level.upper()
    if level not in LEVEL_ORDER:
        show_error(f"Invalid level: {level}. Choose from: {', '.join(LEVEL_ORDER.keys())}")
        raise typer.Exit(1)

    stop_event = asyncio.Event()

    # Handle Ctrl+C gracefully
    def _signal_handler(*_: Any) -> None:
        stop_event.set()

    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, _signal_handler)
        loop.add_signal_handler(signal.SIGTERM, _signal_handler)

    if not json_output:
        mode_desc = f"Watching events (level >= {level})"
        if notify:
            mode_desc += f", notify: {notify}"
        console.print(f"[bold cyan]👁️  {mode_desc}[/]")
        console.print(f"[dim]Press Ctrl+C to stop[/dim]\n")

    try:
        asyncio.run(_watch_loop(level, interval, notify, json_output, stop_event))
    except KeyboardInterrupt:
        pass
    finally:
        if not json_output:
            console.print("\n[dim]👁️  Watcher stopped[/dim]")
