"""Agent commands — inspect Antonio AI agent status and sessions.

Usage:
    vyper agent status           Show agent overview
    vyper agent session <id>     Show session details
    vyper agent learn            Show learning insights
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cli.client import VyperClient
from cli.output import print_json, show_error

app = typer.Typer()
console = Console()
err_console = Console(stderr=True)


def _agent_url(client: VyperClient) -> str:
    """Get agent service URL from config."""
    return client.cfg.get("agent_url") or "http://localhost:8021"


async def _agent_get(url: str, path: str) -> dict[str, Any] | None:
    """GET from agent service, return data dict or None."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            r = await http.get(f"{url}{path}")
            if r.status_code == 200:
                body = r.json()
                if isinstance(body, dict) and "data" in body:
                    return body["data"]
                return body
            return None
    except Exception:
        return None


# ── Callback ────────────────────────────────────────────────


@app.callback()
def callback() -> None:
    """Inspect Antonio AI agent status and sessions."""


# ── Status ──────────────────────────────────────────────────


@app.command()
def status(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Show Antonio agent overview — service health, sessions, skills, memory."""
    async def _run() -> None:
        async with VyperClient() as client:
            console.print("[bold cyan]Fetching Antonio agent status...[/]")
            base = _agent_url(client)

            health = await _agent_get(base, "/health")
            manifest = await _agent_get(base, "/agent/manifest")
            daemon = await _agent_get(base, "/daemon/status")
            memory_stats = await _agent_get(base, "/memory/stats")

            # Sessions
            sessions: list[dict] = []
            sess_data = await _agent_get(base, "/agent/sessions?limit=20")
            if sess_data and isinstance(sess_data, dict):
                sessions = sess_data.get("sessions", [])

            # Learning
            learning = await _agent_get(base, "/learning/stats")

            if json_output:
                import json as j
                console.print(j.dumps({
                    "health": health,
                    "manifest": manifest,
                    "sessions": sessions,
                    "daemon": daemon,
                    "memory": memory_stats,
                    "learning": learning,
                }, indent=2, default=str))
                return

            # ── Status Panel ──
            if health:
                svc_status = health.get("status", "unknown")
                svc_color = "green" if svc_status == "ok" else "red"
                info = Text.assemble(
                    ("Service:     ", "dim"),
                    ("14-agent", "bold"),
                    f" (v{health.get('version', '?')})", "\n",
                )
                info += Text.assemble(
                    ("Status:      ", "dim"),
                    ("🟢 RUNNING" if svc_status == "ok" else "🔴 DOWN", f"bold {svc_color}"), "\n",
                )
                active = health.get("active_sessions", 0)
                info += Text.assemble(
                    ("Active:      ", "dim"),
                    (f"{active} session(s)", "bold green" if active > 0 else "dim"), "\n",
                )
                skills = health.get("skills_loaded", 0)
                info += Text.assemble(
                    ("Skills:      ", "dim"), (f"{skills} registered", "bold"), "\n",
                )
                mem = health.get("memory_entries", 0)
                info += Text.assemble(
                    ("Memory:      ", "dim"), (f"{mem} entries", "bold"), "\n",
                )

                # Provider info from manifest
                if manifest:
                    constraints = manifest.get("constraints", {})
                    load = manifest.get("current_load", {})
                    info += Text.assemble("\n", ("Constraints: ", "dim"),
                                          (f"max {constraints.get('max_concurrent_tasks', '?')} tasks", "dim"), "\n")
                    info += Text.assemble(
                        ("Load:        ", "dim"),
                        (f"{load.get('status', '?')}", "bold green" if load.get('status') == 'idle' else "bold yellow"),
                    )
            else:
                info = Text("[red]❌ Agent service unreachable on {base}[/]")

            console.print(Panel(info, title="[bold cyan]🤖 Antonio Agent[/]", border_style="cyan"))

            # ── Daemon ──
            if daemon:
                d_info = Text.assemble(
                    ("Running:     ", "dim"),
                    ("✅ YES" if daemon.get("running") else "❌ NO", "bold"),
                )
                if daemon.get("total_cycles") is not None:
                    d_info += Text.assemble(
                        "\n", ("Cycles:      ", "dim"),
                        (f"{daemon.get('total_cycles', 0)} total", "bold"),
                        (f" ({daemon.get('total_errors', 0)} errors)",
                         "red" if daemon.get('total_errors', 0) > 0 else "dim"),
                    )
                if daemon.get("uptime"):
                    d_info += Text.assemble("\n", ("Uptime:      ", "dim"), (daemon["uptime"], "green"))
                console.print(Panel(d_info, title="[bold]⏱️  Daemon[/]", border_style="blue"))

            # ── Active Sessions ──
            active_sessions = [
                s for s in sessions
                if s.get("status") in ("thinking", "acting", "observing")
            ]
            if active_sessions:
                table = Table(title="Active Sessions", box=None, header_style="bold cyan")
                table.add_column("Session ID", width=18)
                table.add_column("Task Type", width=14)
                table.add_column("Status", width=12)
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

            # ── Skills ──
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

            # ── Learning Stats ──
            if learning:
                analyzed = learning.get("total_sessions_analyzed", 0)
                patterns = learning.get("patterns_found", 0)
                console.print(f"\n[bold]Learning:[/] {analyzed} sessions analyzed, {patterns} patterns found")

            if not health and not manifest:
                show_error("Could not reach Antonio agent service (14-agent)")
                raise typer.Exit(1)

    asyncio.run(_run())


# ── Session Detail ──────────────────────────────────────────


@app.command()
def session(
    session_id: str = typer.Argument(..., help="Session ID to inspect"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch session in real-time (polls every 3s)"),
) -> None:
    """Show detailed Antonio session info with all steps."""
    async def _run() -> None:
        async with VyperClient() as client:
            base = _agent_url(client)

            try:
                data = await _agent_get(base, f"/agent/{session_id}")
                if data is None:
                    show_error(f"Session not found: {session_id}")
                    raise typer.Exit(1)
            except Exception as exc:
                show_error(f"Cannot connect to Antonio agent service: {exc}")
                raise typer.Exit(1)

            if json_output:
                import json as j
                console.print(j.dumps(data, indent=2, default=str))
                return

            sid = data.get("session_id", "?")
            sstatus = data.get("status", "?")
            serror = data.get("error")
            steps = data.get("steps", [])
            output = data.get("output", {})

            status_colors = {
                "completed": "green", "failed": "red", "stopped": "yellow",
                "thinking": "cyan", "acting": "green", "observing": "blue",
            }
            sc = status_colors.get(sstatus, "white")

            header = Text.assemble(
                ("Session:     ", "dim"), (sid[:20], "bold"), "\n",
                ("Status:      ", "dim"), (f"{sstatus.upper()}", f"bold {sc}"), "\n",
                ("Goal:        ", "dim"), (data.get("goal", "?")[:80], "white"), "\n",
            )
            if output:
                summary = output.get("summary", "")
                if summary:
                    header += Text.assemble(("Summary:     ", "dim"), (summary[:120], "white"), "\n")
                findings = output.get("findings", [])
                header += Text.assemble(("Findings:    ", "dim"), (f"{len(findings)} total", "bold"))
                crit = sum(1 for f in findings if isinstance(f, dict) and f.get("severity") == "critical")
                high = sum(1 for f in findings if isinstance(f, dict) and f.get("severity") == "high")
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
                table.add_column("Action", width=22)
                table.add_column("Status", width=12)
                table.add_column("Duration", width=10)
                table.add_column("Observation", width=56)

                for step in steps:
                    sn = step.get("step_number", "?")
                    action = step.get("action", "?")
                    st = step.get("status", "?")
                    dur = step.get("duration_ms", 0)
                    obs = step.get("observation", "")[:54]

                    sc2 = "green" if st == "completed" else "red" if st == "failed" else "yellow"
                    dur_str = f"{dur:.0f}ms" if dur else "-"

                    table.add_row(str(sn), action, f"[{sc2}]{st}[/]", dur_str, obs)
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

    if watch and not json_output:
        # ── WATCH MODE ── Live polling
        import hashlib
        base = _agent_url(await VyperClient().__aenter__())
        last_state = ""
        last_hash = ""

        try:
            while True:
                data = await _agent_get(base, f"/agent/{session_id}")
                if data is None:
                    show_error(f"Session lost: {session_id}")
                    break

                sstatus = data.get("status", "?")
                steps = data.get("steps", [])

                current_hash = hashlib.md5(
                    f"{sstatus}:{len(steps)}:{len(steps) > 0 and steps[-1].get('observation', '')}".encode()
                ).hexdigest()[:8]

                if sstatus != last_state or current_hash != last_hash:
                    console.clear()
                    # Re-render session header
                    header = Text.assemble(
                        ("Session:     ", "dim"), (session_id[:20], "bold"), "\n",
                        ("Status:      ", "dim"), (f"{sstatus.upper()}", f"bold {status_colors.get(sstatus, 'white')}"), "\n",
                        ("Goal:        ", "dim"), (data.get("goal", "?")[:80], "white"), "\n",
                    )
                    output = data.get("output", {})
                    if output:
                        findings = output.get("findings", [])
                        header += Text.assemble(("Findings:    ", "dim"), (f"{len(findings)} total", "bold"))
                    console.print(Panel(header, title=f"📋 Session {session_id[:12]} — WATCHING", border_style="cyan"))

                    if steps:
                        table = Table(box=None, header_style="dim")
                        table.add_column("#", width=3)
                        table.add_column("Action", width=20)
                        table.add_column("Status", width=12)
                        table.add_column("Duration", width=10)
                        table.add_column("Observation", width=50)
                        for step in steps:
                            sn = step.get("step_number", "?")
                            action = step.get("action", "?")
                            st = step.get("status", "?")
                            dur = step.get("duration_ms", 0)
                            obs = step.get("observation", "")[:48]
                            sc2 = "green" if st == "completed" else "red" if st == "failed" else "yellow"
                            dur_str = f"{dur:.0f}ms" if dur else "-"
                            table.add_row(str(sn), action, f"[{sc2}]{st}[/]", dur_str, obs)
                        console.print(table)
                    last_state = sstatus
                    last_hash = current_hash

                if sstatus in ("completed", "failed", "stopped"):
                    break
                await asyncio.sleep(3)

        except KeyboardInterrupt:
            pass

    asyncio.run(_run())


# ── Learning Insights ───────────────────────────────────────


@app.command()
def learn(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Show Antonio learning insights — patterns, success rates, recommendations."""
    async def _run() -> None:
        async with VyperClient() as client:
            base = _agent_url(client)

            stats = await _agent_get(base, "/learning/stats") or {}
            recs = await _agent_get(base, "/learning/recommendations") or {}

            if json_output:
                import json as j
                console.print(j.dumps({"stats": stats, "recommendations": recs}, indent=2, default=str))
                return

            analyzed = stats.get("total_sessions_analyzed", 0)
            patterns = stats.get("patterns_found", 0)

            info = Text.assemble(
                ("Sessions analyzed: ", "dim"), (f"{analyzed}", "bold"), "\n",
                ("Patterns found:    ", "dim"), (f"{patterns}", "bold"), "\n",
            )
            if stats.get("last_analysis"):
                info += Text.assemble(
                    ("Last analysis:    ", "dim"),
                    (str(stats["last_analysis"])[:19], "dim"), "\n",
                )
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
