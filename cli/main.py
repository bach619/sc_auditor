"""Vyper CLI — Smart Contract Bug Hunter.

Usage:
    vyper audit <address>          Full audit pipeline
    vyper scan <file>              Quick scan (slither + mythril + echidna)
    vyper exploit <finding-id>     Generate PoC exploit
    vyper status <audit-id>        Check audit status
    vyper list                     List all audits
    vyper stats                    Pipeline statistics
    vyper queue                    View priority queue
    vyper health                   Check all service health
    vyper up                       Start all Docker services
    vyper down                     Stop all Docker services
    vyper logs [service]           View service logs
    vyper ps                       Show running services
    vyper restart [service]        Restart services
    vyper dashboard                [removed] use 'vyper monitor' instead
    vyper daemon <action>          Manage daemon (start/stop/status)
    vyper config                   Show/edit configuration
    vyper version                  Show version
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel

from cli import __version__
from cli.commands.audit import audit
from cli.commands.config_cmd import config_cmd
from cli.commands.dashboard import dashboard
from cli.commands.docker import down, logs, ps, restart, up
from cli.commands.monitor_cmd import app as monitor_cmd
from cli.commands.chat_cmd import app as chat_cmd
from cli.commands.exploit import exploit
from cli.commands.backup import backup_app
from cli.commands.scan import scan
from cli.commands.status import daemon, health, list_audits, queue, stats, status

console = Console()

# ── Typer App ────────────────────────────────────────────────────

app = typer.Typer(
    name="vyper",
    help="Smart Contract Bug Hunter — analyze, exploit, and report on Solidity contracts",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
)

# ── Docker commands ──────────────────────────────────────────────

app.command("up")(up)
app.command("down")(down)
app.command("logs")(logs)
app.command("ps")(ps)
app.command("restart")(restart)

# ── Pipeline commands ────────────────────────────────────────────

app.command("audit")(audit)
app.command("scan")(scan)
app.command("exploit")(exploit)

# ── Status commands ──────────────────────────────────────────────

app.command("status")(status)
app.command("list")(list_audits)
app.command("stats")(stats)
app.command("queue")(queue)
app.command("health")(health)
app.command("daemon")(daemon)

# ── Utility commands ─────────────────────────────────────────────

app.command("dashboard")(dashboard)
app.command("config")(config_cmd)

# ── Monitor & Chat ───────────────────────────────────────────────

app.add_typer(monitor_cmd, name="monitor", help="Open Vyper Monitor — live terminal dashboard")
app.add_typer(chat_cmd, name="chat", help="Open Vyper AI Chat — pipeline-aware assistant")

# ── Backup subcommands ───────────────────────────────────────────

app.add_typer(backup_app)

# ── Version command ──────────────────────────────────────────────

@app.command()
def version() -> None:
    """Show the Vyper CLI version."""
    panel = Panel(
        f"[bold cyan]Vyper CLI[/] [green]v{__version__}[/]\n"
        "[dim]Smart Contract Bug Hunter[/]",
        border_style="cyan",
    )
    console.print(panel)


# ── Entrypoint ───────────────────────────────────────────────────

def entrypoint() -> None:
    """Entry point for the CLI (called from pyproject.toml)."""
    app()


if __name__ == "__main__":
    app()
