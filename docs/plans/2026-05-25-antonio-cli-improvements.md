# Antonio CLI Improvements — Implementation Plan

> **Goal:** Give CLI users full visibility into Antonio (agent status, sessions, learning) plus diagnostic tools, async audit, and enhanced TUI monitor.

**Architecture:** All new CLI commands follow existing patterns in `cli/commands/` — each command is a standalone Typer function, uses `VyperClient` for HTTP, and `cli/output.py` for Rich-formatted display. TUI widgets go in `cli/monitor/widgets.py`.

**Tech Stack:** Typer, Rich, Textual, httpx, asyncio

---

## Task 1: Create `vyper agent status` command

**Objective:** Show Antonio agent overview — service status, active sessions, skills, memory stats, daemon state.

**Files:**
- Create: `cli/commands/agent_cmd.py`
- Modify: `cli/main.py` (register command)
- Uses: `cli/client.py` (add agent API methods)

**Implementation:**

```python
# cli/commands/agent_cmd.py
"""Agent commands — inspect Antonio AI agent status and sessions.

Usage:
    vyper agent status           Show agent overview
    vyper agent session <id>     Show session details
    vyper agent learn            Show learning insights
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cli.client import VyperClient
from cli.output import print_json, show_error, show_success

app = typer.Typer()
console = Console()
err_console = Console(stderr=True)


@app.callback()
def callback() -> None:
    """Inspect Antonio AI agent status and sessions."""


@app.command()
def status(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Show Antonio agent overview — service health, sessions, skills, memory."""
    async def _run() -> None:
        async with VyperClient() as client:
            console.print("[bold cyan]Fetching Antonio agent status...[/]")
            try:
                agent_url = client.cfg.get("agent_url") or "http://localhost:8021"
                
                # Gather data from multiple endpoints
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as http:
                    # Health
                    health_data = None
                    try:
                        r = await http.get(f"{agent_url}/health")
                        if r.status_code == 200:
                            health_data = r.json().get("data", r.json())
                    except Exception:
                        pass
                    
                    # Manifest
                    manifest = None
                    try:
                        r = await http.get(f"{agent_url}/agent/manifest")
                        if r.status_code == 200:
                            manifest = r.json().get("data", r.json())
                    except Exception:
                        pass
                    
                    # Sessions
                    sessions = []
                    try:
                        r = await http.get(f"{agent_url}/agent/sessions?limit=10")
                        if r.status_code == 200:
                            sessions = r.json().get("data", {}).get("sessions", [])
                    except Exception:
                        pass
                    
                    # Daemon
                    daemon = None
                    try:
                        r = await http.get(f"{agent_url}/daemon/status")
                        if r.status_code == 200:
                            daemon = r.json().get("data", r.json())
                    except Exception:
                        pass
                    
                    # Memory stats
                    memory_stats = None
                    try:
                        r = await http.get(f"{agent_url}/memory/stats")
                        if r.status_code == 200:
                            memory_stats = r.json().get("data", r.json())
                    except Exception:
                        pass
                
                if json_output:
                    import json as j
                    console.print(j.dumps({
                        "health": health_data,
                        "manifest": manifest,
                        "sessions": sessions,
                        "daemon": daemon,
                        "memory": memory_stats,
                    }, indent=2, default=str))
                    return
                
                # ── Status Panel ──
                if health_data:
                    svc_status = health_data.get("status", "unknown")
                    svc_color = "green" if svc_status == "ok" else "red"
                    info = Text.assemble(
                        ("Service:     ", "dim"), ("14-agent", "bold"), f" (v{health_data.get('version', '?')})", "\n",
                        ("Status:      ", "dim"), (f"🟢 RUNNING" if svc_status == "ok" else "🔴 DOWN", f"bold {svc_color}"), "\n",
                    )
                    active = health_data.get("active_sessions", 0)
                    info += Text.assemble(
                        ("Sessions:    ", "dim"), (f"{active} active", "bold green" if active > 0 else "dim"), "\n",
                    )
                    skills = health_data.get("skills_loaded", 0)
                    info += Text.assemble(
                        ("Skills:      ", "dim"), (f"{skills} registered", "bold"), "\n",
                    )
                    mem = health_data.get("memory_entries", 0)
                    info += Text.assemble(
                        ("Memory:      ", "dim"), (f"{mem} entries", "bold"), "\n",
                    )
                else:
                    info = Text("[red]Agent service unreachable[/]")
                
                console.print(Panel(info, title="[bold cyan]🤖 Antonio Agent[/]", border_style="cyan"))
                
                # ── Daemon Status ──
                if daemon:
                    d_info = Text.assemble(
                        ("Running:     ", "dim"), ("✅ YES" if daemon.get("running") else "❌ NO", "bold"),
                    )
                    if daemon.get("total_cycles") is not None:
                        d_info += Text.assemble(
                            "\n", ("Cycles:      ", "dim"), (f"{daemon.get('total_cycles', 0)} total", "bold"),
                            (f" ({daemon.get('total_errors', 0)} errors)", "red" if daemon.get('total_errors', 0) > 0 else "dim"),
                        )
                    if daemon.get("uptime"):
                        d_info += Text.assemble("\n", ("Uptime:      ", "dim"), (daemon["uptime"], "green"))
                    console.print(Panel(d_info, title="[bold]⏱️  Daemon[/]", border_style="blue"))
                
                # ── Active Sessions Table ──
                active_sessions = [s for s in sessions if s.get("status") in ("thinking", "acting", "observing")]
                if active_sessions:
                    table = Table(title="Active Sessions", box=None, header_style="bold cyan")
                    table.add_column("Session ID", width=20)
                    table.add_column("Task Type", width=16)
                    table.add_column("Status", width=14)
                    table.add_column("Goal", width=40)
                    table.add_column("Steps", width=6)
                    for s in active_sessions:
                        sid = s.get("session_id", "?")[:16]
                        stype = s.get("task_type", "?")
                        sstatus = s.get("status", "?")
                        sgoal = s.get("goal", "")[:38]
                        ssteps = str(s.get("steps", 0))
                        sc = "yellow" if sstatus == "thinking" else "green" if sstatus == "acting" else "cyan"
                        table.add_row(sid, stype, f"[{sc}]{sstatus}[/]", sgoal, ssteps)
                    console.print(table)
                
                # ── Manifest Info ──
                if manifest and manifest.get("capabilities"):
                    skills_list = manifest["capabilities"]
                    console.print(f"\n[bold]Registered Skills ({len(skills_list)}):[/]")
                    for sk in skills_list:
                        console.print(f"  [green]▪[/] [bold]{sk.get('name', '?')}[/] — {sk.get('description', '')[:80]}")
                
                # ── Memory Stats ──
                if memory_stats:
                    console.print(f"\n[bold]Memory Stats:[/]")
                    for k, v in memory_stats.items():
                        if isinstance(v, (int, float, str)):
                            console.print(f"  [dim]{k}:[/] {v}")
                
                if not health_data and not manifest:
                    show_error("Could not reach Antonio agent service (14-agent)")
                    raise typer.Exit(1)
                    
            except Exception as exc:
                show_error(f"Failed to get agent status: {exc}")
                raise typer.Exit(1)
    
    asyncio.run(_run())


@app.command()
def session(
    session_id: str = typer.Argument(..., help="Session ID to inspect"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch session in real-time"),
) -> None:
    """Show detailed Antonio session info with all steps."""
    async def _run() -> None:
        async with VyperClient() as client:
            agent_url = client.cfg.get("agent_url") or "http://localhost:8021"
            
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as http:
                try:
                    r = await http.get(f"{agent_url}/agent/{session_id}")
                    if r.status_code == 404:
                        show_error(f"Session not found: {session_id}")
                        raise typer.Exit(1)
                    r.raise_for_status()
                    data = r.json().get("data", r.json())
                except httpx.HTTPStatusError as e:
                    show_error(f"Agent API error: {e}")
                    raise typer.Exit(1)
                except httpx.ConnectError:
                    show_error("Cannot connect to Antonio agent service (14-agent)")
                    raise typer.Exit(1)
            
            if json_output:
                import json as j
                console.print(j.dumps(data, indent=2, default=str))
                return
            
            # Session header
            sess = data
            sid = sess.get("session_id", "?")
            sstatus = sess.get("status", "?")
            serror = sess.get("error")
            steps = sess.get("steps", [])
            output = sess.get("output", {})
            
            status_colors = {
                "completed": "green", "failed": "red", "stopped": "yellow",
                "thinking": "cyan", "acting": "green", "observing": "blue",
            }
            sc = status_colors.get(sstatus, "white")
            
            header = Text.assemble(
                ("Session:     ", "dim"), (sid[:20], "bold"), "\n",
                ("Status:      ", "dim"), (f"{sstatus.upper()}", f"bold {sc}"), "\n",
                ("Goal:        ", "dim"), (sess.get("goal", "?")[:80], "white"), "\n",
            )
            if output:
                summary = output.get("summary", "")
                if summary:
                    header += Text.assemble(("Summary:     ", "dim"), (summary[:120], "white"), "\n")
                findings = output.get("findings", [])
                header += Text.assemble(("Findings:    ", "dim"), (f"{len(findings)} total", "bold"))
                crit = sum(1 for f in findings if f.get("severity") == "critical")
                high = sum(1 for f in findings if f.get("severity") == "high")
                if crit:
                    header += Text.assemble(("", ""), (f"  ({crit} critical, {high} high)", "red bold"))
                header += Text.assemble("\n")
            if serror:
                header += Text.assemble(("Error:       ", "dim"), (f"{serror}", "red bold"), "\n")
            
            console.print(Panel(header, title=f"📋 Session {sid[:12]}", border_style=sc))
            
            # Steps table
            if steps:
                table = Table(title=f"Steps ({len(steps)})", box=None, header_style="bold cyan")
                table.add_column("#", width=4)
                table.add_column("Action", width=20)
                table.add_column("Status", width=12)
                table.add_column("Duration", width=10)
                table.add_column("Observation", width=60)
                
                for step in steps:
                    sn = step.get("step_number", "?")
                    action = step.get("action", "?")
                    st = step.get("status", "?")
                    dur = step.get("duration_ms", 0)
                    obs = step.get("observation", "")[:58]
                    
                    sc2 = "green" if st == "completed" else "red" if st == "failed" else "yellow"
                    dur_str = f"{dur:.0f}ms" if dur else "-"
                    
                    table.add_row(
                        str(sn),
                        action,
                        f"[{sc2}]{st}[/]",
                        dur_str,
                        obs,
                    )
                console.print(table)
            
            # Output summary
            if output:
                console.print(f"\n[bold]Output:[/]")
                for k, v in output.items():
                    if k == "summary":
                        continue
                    if isinstance(v, list):
                        console.print(f"  [dim]{k}:[/] {len(v)} items")
                    elif isinstance(v, dict):
                        console.print(f"  [dim]{k}:[/] {len(v)} fields")
                    elif v:
                        console.print(f"  [dim]{k}:[/] {str(v)[:100]}")
    
    asyncio.run(_run())
    if watch:
        console.print("[yellow]--watch: live refresh not yet implemented[/]")


@app.command()
def learn(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Show Antonio learning insights — patterns, success rates, recommendations."""
    async def _run() -> None:
        async with VyperClient() as client:
            agent_url = client.cfg.get("agent_url") or "http://localhost:8021"
            
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as http:
                try:
                    # Learning stats
                    r = await http.get(f"{agent_url}/learning/stats")
                    stats = r.json().get("data", {}) if r.status_code == 200 else {}
                    
                    # Recommendations
                    r2 = await http.get(f"{agent_url}/learning/recommendations")
                    recs = r2.json().get("data", {}) if r2.status_code == 200 else {}
                except httpx.ConnectError:
                    show_error("Cannot connect to Antonio agent service (14-agent)")
                    raise typer.Exit(1)
            
            if json_output:
                import json as j
                console.print(j.dumps({"stats": stats, "recommendations": recs}, indent=2, default=str))
                return
            
            # Stats
            analyzed = stats.get("total_sessions_analyzed", 0)
            patterns = stats.get("patterns_found", 0)
            
            info = Text.assemble(
                ("Sessions analyzed: ", "dim"), (f"{analyzed}", "bold"), "\n",
                ("Patterns found:    ", "dim"), (f"{patterns}", "bold"), "\n",
            )
            if stats.get("last_analysis"):
                info += Text.assemble(("Last analysis:    ", "dim"), (str(stats["last_analysis"])[:19], "dim"), "\n")
            console.print(Panel(info, title="[bold cyan]🧠 Antonio Learning[/]", border_style="cyan"))
            
            # Task type performance
            perf = stats.get("task_type_performance", {})
            if perf:
                table = Table(title="Success Rate by Task Type", box=None, header_style="bold cyan")
                table.add_column("Task Type", width=18)
                table.add_column("Total", width=8)
                table.add_column("Success", width=10)
                table.add_column("Failed", width=8)
                table.add_column("Avg Steps", width=10)
                table.add_column("Rate", width=8)
                
                for ttype, tdata in perf.items():
                    total = tdata.get("total", 0)
                    success = tdata.get("success", 0)
                    failed = tdata.get("failed", 0)
                    avg = tdata.get("avg_steps", 0)
                    rate = (success / total * 100) if total > 0 else 0
                    rc = "green" if rate >= 80 else "yellow" if rate >= 50 else "red"
                    table.add_row(
                        ttype, str(total), str(success), str(failed),
                        f"{avg:.1f}", f"[{rc}]{rate:.0f}%[/]",
                    )
                console.print(table)
            
            # Recommendations
            if recs:
                console.print(f"\n[bold]💡 Recommendations:[/]")
                for key, val in recs.items():
                    if isinstance(val, list):
                        for item in val[:5]:
                            if isinstance(item, dict):
                                name = item.get("name", item.get("skill", ""))
                                desc = item.get("description", item.get("reason", ""))
                                console.print(f"  [green]▪[/] [bold]{name}[/] — {desc[:100]}")
                            else:
                                console.print(f"  [green]▪[/] {str(item)[:100]}")
                    elif isinstance(val, (int, float, str)):
                        console.print(f"  [dim]{key}:[/] {val}")
            
            # Error patterns
            errors = stats.get("error_patterns", {})
            if errors:
                console.print(f"\n[bold]🔁 Recurring Errors:[/]")
                for err, count in sorted(errors.items(), key=lambda x: -x[1])[:5]:
                    console.print(f"  [red]▪[/] {err[:80]} — [bold]{count}x[/]")
    
    asyncio.run(_run())
