"""Audit command — run the full Vyper audit pipeline.

Usage:
    vyper audit 0xdead... --chain ethereum --program ethena
    vyper audit 0xdead... --async                        # background mode
    vyper audit 0xdead... --watch                        # live streaming
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text

from cli.client import VyperClient
from cli.output import (
    get_progress,
    print_json,
    show_audit_started,
    show_audit_status,
    show_error,
    show_success,
)

console = Console()
err_console = Console(stderr=True)

# ── Step state tracking for --watch ───────────────────────

_PREV_STEPS: dict[str, list[dict]] = {}


def _watch_render(status: dict, elapsed: float) -> Panel:
    """Build live-updating panel for --watch mode."""
    aid = status.get("audit_id", "?")[:8]
    state = status.get("state", "?")
    steps = status.get("steps", [])

    state_colors = {
        "completed": "green", "pending": "yellow",
        "failed": "red", "timeout": "red", "aborted": "red",
    }
    sc = state_colors.get(state, "cyan")

    info = Text.assemble(
        ("Audit ID:  ", "dim"), (f"{aid}", "bold"), "\n",
        ("Status:    ", "dim"), (f"{state.upper()}", f"bold {sc}"), "\n",
        ("Elapsed:   ", "dim"), (f"{elapsed:.1f}s", "bold"), "\n",
    )

    # Steps table
    if steps:
        table = Table(box=None, header_style="dim")
        table.add_column("#", width=3)
        table.add_column("Step", width=20)
        table.add_column("Status", width=12)
        table.add_column("Duration", width=10)
        table.add_column("Result", width=40)

        for step in steps:
            sn = step.get("name", "?")
            st = step.get("state", "?")
            dur = step.get("duration_seconds")
            err = step.get("error", "")
            res = step.get("result", {})

            sc2 = "green" if st == "completed" else "red" if "failed" in str(st) else "yellow"
            icon = "✅" if st == "completed" else "❌" if "failed" in str(st) else "⏳"
            dur_str = f"{dur:.1f}s" if dur else "-"

            # Show result summary
            result_str = ""
            if isinstance(res, dict):
                findings = res.get("findings", [])
                if findings:
                    result_str = f"{len(findings)} findings"
                elif res.get("status") == "skipped":
                    result_str = f"[dim]skipped[/]"

            step_num = step.get("order", steps.index(step) + 1)
            table.add_row(str(step_num), sn, f"{icon} [{sc2}]{st}[/]", dur_str, result_str)

        info += Text("\n")
        info += Text(table.renderable)

    # Findings summary
    findings = status.get("findings", [])
    if findings:
        if isinstance(findings, list):
            crit = sum(1 for f in findings if isinstance(f, dict) and f.get("severity") == "critical")
            high = sum(1 for f in findings if isinstance(f, dict) and f.get("severity") == "high")
            info += Text(f"\nFindings: {len(findings)} total")
            if crit:
                info += Text(f"  🔴 {crit} critical", style="red bold")
            if high:
                info += Text(f"  🟠 {high} high", style="orange_red1 bold")

    return Panel(info, title=f"📋 Audit {aid}", border_style=sc)


def audit(
    address: str = typer.Argument(..., help="Contract address (0x-prefixed)"),
    chain: str = typer.Option("ethereum", "--chain", "-c", help="Blockchain name"),
    program: str = typer.Option("", "--program", "-p", help="Immunefi program slug"),
    priority: int = typer.Option(5, "--priority", min=0, max=10, help="Audit priority (0-10)"),
    async_mode: bool = typer.Option(False, "--async", "-a", help="Start in background, don't wait"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Live-stream audit progress"),
    timeout: int = typer.Option(600, "--timeout", help="Max wait time in seconds"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Run the full audit pipeline for a smart contract."""
    if not address.startswith("0x"):
        show_error("Address must be 0x-prefixed")
        raise typer.Exit(1)

    async def _run() -> None:
        async with VyperClient() as client:
            # Start the audit
            try:
                result = await client.start_audit(
                    address=address,
                    chain=chain,
                    program=program,
                    priority=priority,
                )
            except Exception as exc:
                show_error(f"Failed to start audit: {exc}")
                raise typer.Exit(1)

            audit_id = result.get("audit_id", "")
            show_audit_started(result)

            if json_output:
                print_json(result)
                return

            # ── ASYNC MODE ──
            if async_mode:
                show_success(f"Audit {audit_id[:8]} started in background")
                console.print(f"  Check status: [bold]vyper status {audit_id}[/]")
                console.print(f"  Live view:    [bold]vyper monitor[/]")
                return

            # ── WATCH MODE ──
            if watch:
                start_time = time.monotonic()
                last_state = ""
                last_steps_hash = ""

                import hashlib

                with Live(console=console, refresh_per_second=2, screen=False) as live:
                    while True:
                        elapsed = time.monotonic() - start_time
                        if elapsed > timeout:
                            live.update(Panel(
                                f"[red]Audit did not complete within {timeout}s timeout[/]\n"
                                f"[dim]Check status: vyper status {audit_id}[/]",
                                border_style="red",
                            ))
                            raise typer.Exit(1)

                        try:
                            status = await client.get_audit(audit_id)
                        except Exception:
                            await asyncio.sleep(2)
                            continue

                        state = status.get("state", "")
                        steps = status.get("steps", [])

                        # Only refresh if something changed
                        current_hash = hashlib.md5(
                            f"{state}:{len(steps)}".encode()
                        ).hexdigest()[:8]

                        if state != last_state or current_hash != last_steps_hash:
                            panel = _watch_render(status, elapsed)
                            live.update(panel)
                            last_state = state
                            last_steps_hash = current_hash

                        if state in ("completed",) or "failed" in state or state in ("timeout", "aborted"):
                            await asyncio.sleep(1)  # final refresh
                            status = await client.get_audit(audit_id)
                            panel = _watch_render(status, time.monotonic() - start_time)
                            live.update(panel)

                            if state == "completed":
                                console.print(f"\n[green]✅ Audit completed in {status.get('duration_seconds', 0):.1f}s[/]")
                            else:
                                console.print(f"\n[red]❌ Audit finished with state: {state}[/]")
                            return

                        await asyncio.sleep(2)

            # ── NORMAL MODE (progress bar) ──
            start_time = time.monotonic()

            with get_progress() as progress:
                task = progress.add_task(
                    f"[cyan]Audit {audit_id[:8]}...[/]",
                    total=None,
                )

                while True:
                    elapsed = time.monotonic() - start_time
                    if elapsed > timeout:
                        progress.stop()
                        show_error(f"Audit did not complete within {timeout}s timeout")
                        show_success(f"Check status later: vyper status {audit_id}")
                        raise typer.Exit(1)

                    try:
                        status = await client.get_audit(audit_id)
                    except Exception:
                        await asyncio.sleep(2)
                        continue

                    state = status.get("state", "")
                    steps = status.get("steps", [])

                    # Show current step if available
                    step_desc = ""
                    if steps:
                        last = steps[-1]
                        step_desc = f" — {last.get('name', '')}: {last.get('state', '')}"

                    progress.update(
                        task,
                        description=f"[cyan]{state.upper()}{step_desc}[/]",
                    )

                    if state in ("completed",) or "failed" in state or state in ("timeout", "aborted"):
                        progress.stop()
                        console.print()
                        show_audit_status(status)

                        if state == "completed":
                            show_success(f"Audit completed in {status.get('duration_seconds', 0):.1f}s")
                        else:
                            show_error(f"Audit finished with state: {state}")
                        return

                    await asyncio.sleep(2)

    asyncio.run(_run())
