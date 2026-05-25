"""Doctor command — diagnostic tool for Vyper system health.

Usage:
    vyper doctor                  Run full diagnostic
    vyper doctor --fix            Auto-fix issues where possible
    vyper doctor --json           Output as JSON
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from cli.client import VyperClient
from cli.output import print_json, show_error, show_success

app = typer.Typer()
console = Console()
err_console = Console(stderr=True)


# ── Service Registry ────────────────────────────────────────

ALL_SERVICES: list[dict[str, Any]] = [
    {"name": "01-config",         "port": 8011, "required": True},
    {"name": "02-immunefi",       "port": 8001, "required": True},
    {"name": "03-source",         "port": 8002, "required": True},
    {"name": "04-scanner",        "port": 8000, "required": True},
    {"name": "04a-scanner-slither", "port": 8014, "required": False},
    {"name": "04b-scanner-echidna", "port": 8015, "required": False},
    {"name": "04c-scanner-forge",   "port": 8016, "required": False},
    {"name": "04d-scanner-halmos",  "port": 8017, "required": False},
    {"name": "05-scanner-mythril",  "port": 8013, "required": False},
    {"name": "06-ai",             "port": 8004, "required": True},
    {"name": "07-classifier",     "port": 8005, "required": True},
    {"name": "08-exploit",        "port": 8006, "required": True},
    {"name": "09-reporter",       "port": 8007, "required": True},
    {"name": "10-notifier",       "port": 8008, "required": False},
    {"name": "11-orchestrator",   "port": 8009, "required": True},
    {"name": "12-webhook",        "port": 8010, "required": False},
    {"name": "13-upkeep",         "port": 8012, "required": False},
    {"name": "14-agent",          "port": 8021, "required": True},
    {"name": "16-submission",     "port": 8018, "required": False},
]


async def _check_service(name: str, port: int) -> dict[str, Any]:
    """Check if a service is reachable via HTTP health endpoint."""
    base = f"http://localhost:{port}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            r = await http.get(f"{base}/health")
            if r.status_code == 200:
                body = r.json()
                data = body.get("data", body) if isinstance(body, dict) else {}
                return {
                    "name": name,
                    "status": "healthy",
                    "version": data.get("version", "?"),
                    "detail": "",
                }
            return {
                "name": name,
                "status": "error",
                "version": "?",
                "detail": f"HTTP {r.status_code}",
            }
    except httpx.ConnectError:
        return {"name": name, "status": "not_found", "version": "?", "detail": "Service not running"}
    except httpx.TimeoutException:
        return {"name": name, "status": "timeout", "version": "?", "detail": "Connection timed out"}
    except Exception as exc:
        return {"name": name, "status": "error", "version": "?", "detail": str(exc)}


async def _check_agent_config(client: VyperClient) -> list[dict[str, Any]]:
    """Check Antonio agent configuration."""
    items: list[dict[str, Any]] = []
    base = client.cfg.get("agent_url") or "http://localhost:8021"

    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            # Health
            r = await http.get(f"{base}/health")
            if r.status_code == 200:
                body = r.json().get("data", r.json())
                items.append({
                    "check": "LLM provider",
                    "status": "ok",
                    "detail": body.get("service", "?")
                })
                items.append({
                    "check": "Skills loaded",
                    "status": "ok",
                    "detail": f"{body.get('skills_loaded', '?')} skills"
                })
            else:
                items.append({"check": "Agent service", "status": "error", "detail": f"HTTP {r.status_code}"})

            # Manifest
            r2 = await http.get(f"{base}/agent/manifest")
            if r2.status_code == 200:
                manifest = r2.json().get("data", r2.json())
                constraints = manifest.get("constraints", {})
                items.append({
                    "check": "Max concurrent tasks",
                    "status": "ok",
                    "detail": str(constraints.get("max_concurrent_tasks", "?"))
                })
                items.append({
                    "check": "API key configured",
                    "status": "ok" if not constraints.get("requires_api_key") else "warn",
                    "detail": "Required but not verified"
                })
            else:
                items.append({"check": "Agent manifest", "status": "error", "detail": "Unreachable"})

            # Daemon
            r3 = await http.get(f"{base}/daemon/status")
            if r3.status_code == 200:
                daemon = r3.json().get("data", r3.json())
                items.append({
                    "check": "Daemon running",
                    "status": "ok" if daemon.get("running") else "warn",
                    "detail": "Active" if daemon.get("running") else "Not running (use `vyper daemon start`)"
                })
            else:
                items.append({"check": "Daemon status", "status": "error", "detail": "Unreachable"})

    except httpx.ConnectError:
        items.append({"check": "Agent service", "status": "error", "detail": "14-agent is not running"})
    except Exception as exc:
        items.append({"check": "Agent check", "status": "error", "detail": str(exc)})

    return items


def _format_fix(name: str, status: str) -> str | None:
    """Suggest or execute a fix for a service based on status."""
    if status == "healthy":
        return None
    if status == "not_found":
        return f"docker compose up -d {name} 2>/dev/null || docker-compose up -d {name} 2>/dev/null"
    if status == "timeout":
        return f"docker compose restart {name} 2>/dev/null || docker-compose restart {name} 2>/dev/null"
    if status == "error":
        return f"docker compose restart {name} 2>/dev/null || docker-compose restart {name} 2>/dev/null"
    return None


# ── Commands ────────────────────────────────────────────────


@app.callback()
def callback() -> None:
    """Diagnose Vyper system health and configuration."""


@app.command()
def doctor(
    fix: bool = typer.Option(False, "--fix", "-f", help="Attempt auto-fix of issues"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Run full system diagnostic — services, agent, config, filesystem."""
    async def _run() -> None:
        async with VyperClient() as client:
            console.print("[bold cyan]🔍 Vyper System Diagnostic[/]")
            console.print()

            # ── 1. Docker Services ──
            console.print("[bold]1. Checking Docker services...[/]")
            service_results = await asyncio.gather(*[
                _check_service(s["name"], s["port"]) for s in ALL_SERVICES
            ])

            service_tree = Tree("Services")
            down_count = 0
            for sr in service_results:
                status = sr["status"]
                name = sr["name"]
                detail = sr["detail"]
                required = any(s["name"] == name and s["required"] for s in ALL_SERVICES)

                if status == "healthy":
                    icon = "✅"
                    label = f"[green]{name}[/] — running (v{sr.get('version', '?')})"
                elif status == "not_found":
                    icon = "❌" if required else "⚠️"
                    label = f"[red]{name}[/] — NOT RUNNING" if required else f"[yellow]{name}[/] — not running (optional)"
                    down_count += 1
                elif status == "timeout":
                    icon = "❌"
                    label = f"[red]{name}[/] — TIMEOUT"
                    down_count += 1
                else:
                    icon = "❌" if required else "⚠️"
                    label = f"[red]{name}[/] — {detail}" if required else f"[yellow]{name}[/] — {detail}"
                    down_count += 1

                branch = service_tree.add(f"{icon} {label}")
                fix_suggestion = _format_fix(name, status)
                if fix_suggestion:
                    branch.add(f"[dim]Fix: {fix_suggestion}[/dim]")

            console.print(service_tree)

            # ── 2. Agent Configuration ──
            console.print("\n[bold]2. Checking Antonio configuration...[/]")
            agent_checks = await _check_agent_config(client)

            agent_tree = Tree("Antonio Agent")
            for ac in agent_checks:
                check = ac["check"]
                status = ac["status"]
                detail = ac["detail"]
                if status == "ok":
                    agent_tree.add(f"✅ [green]{check}[/] — {detail}")
                elif status == "warn":
                    agent_tree.add(f"⚠️  [yellow]{check}[/] — {detail}")
                else:
                    agent_tree.add(f"❌ [red]{check}[/] — {detail}")
            console.print(agent_tree)

            # ── 3. Filesystem ──
            console.print("\n[bold]3. Checking filesystem...[/]")
            fs_tree = Tree("Filesystem")

            import os
            from pathlib import Path

            # Report dir
            report_dir = Path.cwd() / "reports"
            report_ok = report_dir.exists() or report_dir.is_dir()
            fs_tree.add(
                f"{'✅' if report_ok else '⚠️'} "
                f"{'[green]' if report_ok else '[yellow]'}Reports dir: {report_dir}"
            )

            # Logs dir
            log_dir = Path.cwd() / "logs"
            log_ok = log_dir.exists() or log_dir.is_dir()
            fs_tree.add(
                f"{'✅' if log_ok else '⚠️'} "
                f"{'[green]' if log_ok else '[yellow]'}Logs dir: {log_dir}"
            )

            # Disk space
            try:
                usage = os.statvfs(".")
                free_gb = usage.f_frsize * usage.f_bavail / (1024**3)
                if free_gb > 5:
                    fs_tree.add(f"✅ [green]Disk space: {free_gb:.1f} GB free[/]")
                else:
                    fs_tree.add(f"⚠️  [yellow]Disk space: {free_gb:.1f} GB free (low!)[/]")
            except Exception:
                pass

            console.print(fs_tree)

            # ── Summary ──
            console.print()
            required_total = sum(1 for s in ALL_SERVICES if s["required"])
            required_up = sum(
                1 for sr in service_results
                if any(s["name"] == sr["name"] and s["required"] for s in ALL_SERVICES)
                and sr["status"] == "healthy"
            )

            if required_up == required_total and down_count == 0:
                show_success("All systems healthy!")
            elif required_up == required_total:
                console.print(f"[yellow]⚠️  All required services up, but {down_count} optional service(s) down.[/]")
            else:
                console.print(f"[red]❌ {required_total - required_up} required service(s) down![/]")
                if fix:
                    console.print("\n[bold]Attempting auto-fix...[/]")
                    fixed_any = False
                    for sr in service_results:
                        if sr["status"] != "healthy":
                            fix_cmd = _format_fix(sr["name"], sr["status"])
                            if fix_cmd:
                                console.print(f"  [yellow]→ Running: {fix_cmd}[/]")
                                try:
                                    import subprocess
                                    proc = await asyncio.create_subprocess_shell(
                                        fix_cmd,
                                        stdout=asyncio.subprocess.PIPE,
                                        stderr=asyncio.subprocess.PIPE,
                                    )
                                    stdout, stderr = await asyncio.wait_for(
                                        proc.communicate(), timeout=60
                                    )
                                    if proc.returncode == 0:
                                        console.print(f"    [green]✅ {sr['name']} fixed![/]")
                                        fixed_any = True
                                    else:
                                        error_msg = stderr.decode()[:200] if stderr else "unknown error"
                                        console.print(f"    [red]❌ Fix failed: {error_msg}[/]")
                                except FileNotFoundError:
                                    console.print(f"    [yellow]⚠️  Docker not found — install Docker or run manually[/]")
                                except asyncio.TimeoutError:
                                    console.print(f"    [red]⏱️  Fix timed out after 60s[/]")
                                except Exception as exc:
                                    console.print(f"    [red]❌ Fix error: {exc}[/]")
                                await asyncio.sleep(1)  # cooldown between restarts

                    if fixed_any:
                        # Re-check health after fixes
                        console.print("\n[bold]Re-checking service health...[/]")
                        service_results = await asyncio.gather(*[
                            _check_service(s["name"], s["port"]) for s in ALL_SERVICES
                        ])
                        fixed_up = sum(
                            1 for sr in service_results if sr["status"] == "healthy"
                        )
                        console.print(f"  Services up: {fixed_up}/{len(ALL_SERVICES)}")
                else:
                    console.print("[dim]Use --fix to auto-restart failed services[/dim]")

            if json_output:
                print_json({
                    "services": service_results,
                    "agent": agent_checks,
                    "summary": {
                        "required_up": required_up,
                        "required_total": required_total,
                        "optional_down": down_count,
                    },
                })

    asyncio.run(_run())
