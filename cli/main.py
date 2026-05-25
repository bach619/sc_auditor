"""Vyper CLI — Smart Contract Bug Hunter.

Usage:
    vyper audit <address>          Full audit pipeline (--async, --watch)
    vyper scan <file>              Quick scan (slither + mythril + echidna)
    vyper exploit <finding-id>     Generate PoC exploit
    vyper status <audit-id>        Check audit status
    vyper list                     List all audits
    vyper stats                    Pipeline statistics
    vyper queue                    View priority queue
    vyper health                   Check all service health
    vyper agent status             Show Antonio agent overview
    vyper agent session <id>       Show agent session details
    vyper agent learn              Show agent learning insights
    vyper doctor                   Run system diagnostic
    vyper watch                    Watch real-time events (--level, --notify)
    vyper benchmark <address>      Benchmark pipeline (--runs, --service)
    vyper up                       Start all Docker services
    vyper down                     Stop all Docker services
    vyper logs [service]           View service logs
    vyper ps                       Show running services
    vyper restart [service]        Restart services
    vyper dashboard                [removed] use 'vyper monitor' instead
    vyper daemon <action>          Manage daemon (start/stop/status)
    vyper config                   Show/edit configuration
    vyper version                  Show version
    vyper --completion SHELL       Generate shell completion script (bash|zsh|fish)
"""

from __future__ import annotations

import os
import sys
from typing import Optional

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

from cli.commands.agent_cmd import app as agent_cmd
from cli.commands.doctor import app as doctor_cmd
from cli.commands.watch import app as watch_cmd
from cli.commands.benchmark import app as benchmark_cmd

console = Console()

# ── Global state ─────────────────────────────────────────────────

_COLOR_MODE: str = "auto"  # "always", "never", "auto"


def resolve_color() -> bool:
    """Return True if color output is enabled based on global --color flag."""
    if _COLOR_MODE == "never":
        return False
    if _COLOR_MODE == "always":
        return True
    # auto — respect NO_COLOR env var
    return os.environ.get("NO_COLOR", "").strip() != "true"


def _completion_callback(shell: Optional[str] = None) -> None:
    """Generate shell completion script for the given shell."""
    if shell is None:
        typer.echo(
            "Usage: vyper --completion bash|zsh|fish\n"
            "Examples:\n"
            "  eval \"$(vyper --completion zsh)\"    # activate in current shell\n"
            "  vyper --completion bash > ~/.vyper-completion.sh  # save to file\n"
        )
        raise typer.Exit()

    shell = shell.lower().strip()
    if shell == "bash":
        script = _bash_completion()
    elif shell == "zsh":
        script = _zsh_completion()
    elif shell == "fish":
        script = _fish_completion()
    else:
        typer.echo(f"Error: unknown shell '{shell}'. Use bash, zsh, or fish.", err=True)
        raise typer.Exit(code=1)

    typer.echo(script)
    raise typer.Exit()


def _bash_completion() -> str:
    return """_vyper_completion() {
    local cur prev words cword
    _init_completion || return

    local commands="audit scan exploit status list stats queue health agent doctor watch benchmark up down logs ps restart daemon config version monitor chat backup"

    if [[ $cword -eq 1 ]]; then
        COMPREPLY=($(compgen -W "$commands" -- "$cur"))
        return
    fi

    case "${words[1]}" in
        agent)
            if [[ $cword -eq 2 ]]; then
                COMPREPLY=($(compgen -W "status session learn" -- "$cur"))
            fi
            ;;
        doctor)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=($(compgen -W "--fix --json" -- "$cur"))
            fi
            ;;
        watch)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=($(compgen -W "--level --json --notify --interval" -- "$cur"))
            fi
            ;;
        benchmark)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=($(compgen -W "--runs --service --json" -- "$cur"))
            fi
            ;;
        audit)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=($(compgen -W "--async --watch --json --output" -- "$cur"))
            fi
            ;;
        daemon)
            if [[ $cword -eq 2 ]]; then
                COMPREPLY=($(compgen -W "start stop status" -- "$cur"))
            fi
            ;;
        logs)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=($(compgen -W "--follow --tail" -- "$cur"))
            fi
            ;;
    esac
} &&
complete -F _vyper_completion vyper
"""


def _zsh_completion() -> str:
    return """#compdef vyper

_vyper_commands() {
    local -a commands
    commands=(
        'audit:Run full audit pipeline on a contract address'
        'scan:Quick scan a Solidity file'
        'exploit:Generate PoC exploit for a finding'
        'status:Check audit status'
        'list:List all audits'
        'stats:Show pipeline statistics'
        'queue:View priority queue'
        'health:Check all service health'
        'agent:Inspect Antonio AI agent'
        'doctor:Run system diagnostic'
        'watch:Watch real-time events'
        'benchmark:Benchmark pipeline performance'
        'up:Start all Docker services'
        'down:Stop all Docker services'
        'logs:View service logs'
        'ps:Show running services'
        'restart:Restart services'
        'daemon:Manage background daemon'
        'config:Show/edit configuration'
        'version:Show version'
        'monitor:Open live terminal dashboard'
        'chat:Open AI Chat'
        'backup:Backup management'
    )
    _describe 'command' commands
}

_vyper() {
    local context state state_descr line
    typeset -A opt_args

    _arguments \\
        '--completion[Generate shell completion]:shell:(bash zsh fish)' \\
        '--color[Color output mode]:mode:(auto never always)' \\
        '(--help)--help[Show help]' \\
        '*::command:->command'

    case $state in
        command)
            _vyper_commands
            ;;
    esac
}

_vyper "$@"
"""


def _fish_completion() -> str:
    return """# vyper completion for fish shell
# eval "$(vyper --completion fish)" | source

function __fish_vyper_needs_command
    set cmd (commandline -opc)
    test (count $cmd) -eq 1
end

function __fish_vyper_using_command
    set cmd (commandline -opc)
    test (count $cmd) -gt 1
    and string match -q -- $argv[1] $cmd[2]
end

# Global options
complete -c vyper -l completion -d 'Generate shell completion' -xa 'bash zsh fish'
complete -c vyper -l color -d 'Color output mode' -xa 'auto never always'
complete -c vyper -l help -d 'Show help'

# Top-level commands
complete -c vyper -f -n '__fish_vyper_needs_command' -a audit -d 'Run full audit pipeline'
complete -c vyper -f -n '__fish_vyper_needs_command' -a scan -d 'Quick scan a Solidity file'
complete -c vyper -f -n '__fish_vyper_needs_command' -a exploit -d 'Generate PoC exploit'
complete -c vyper -f -n '__fish_vyper_needs_command' -a status -d 'Check audit status'
complete -c vyper -f -n '__fish_vyper_needs_command' -a list -d 'List all audits'
complete -c vyper -f -n '__fish_vyper_needs_command' -a stats -d 'Pipeline statistics'
complete -c vyper -f -n '__fish_vyper_needs_command' -a queue -d 'View priority queue'
complete -c vyper -f -n '__fish_vyper_needs_command' -a health -d 'Check all service health'
complete -c vyper -f -n '__fish_vyper_needs_command' -a agent -d 'Inspect Antonio agent'
complete -c vyper -f -n '__fish_vyper_needs_command' -a doctor -d 'Run system diagnostic'
complete -c vyper -f -n '__fish_vyper_needs_command' -a watch -d 'Watch real-time events'
complete -c vyper -f -n '__fish_vyper_needs_command' -a benchmark -d 'Benchmark pipeline'
complete -c vyper -f -n '__fish_vyper_needs_command' -a up -d 'Start Docker services'
complete -c vyper -f -n '__fish_vyper_needs_command' -a down -d 'Stop Docker services'
complete -c vyper -f -n '__fish_vyper_needs_command' -a logs -d 'View service logs'
complete -c vyper -f -n '__fish_vyper_needs_command' -a ps -d 'Show running services'
complete -c vyper -f -n '__fish_vyper_needs_command' -a restart -d 'Restart services'
complete -c vyper -f -n '__fish_vyper_needs_command' -a daemon -d 'Manage daemon'
complete -c vyper -f -n '__fish_vyper_needs_command' -a config -d 'Show/edit configuration'
complete -c vyper -f -n '__fish_vyper_needs_command' -a version -d 'Show version'
complete -c vyper -f -n '__fish_vyper_needs_command' -a monitor -d 'Open terminal dashboard'
complete -c vyper -f -n '__fish_vyper_needs_command' -a chat -d 'Open AI Chat'

# Subcommand completions
complete -c vyper -f -n '__fish_vyper_using_command agent' -a 'status session learn' -d 'Agent subcommands'
complete -c vyper -f -n '__fish_vyper_using_command daemon' -a 'start stop status' -d 'Daemon subcommands'
complete -c vyper -f -n '__fish_vyper_using_command doctor' -l fix -d 'Auto-fix failed services'
complete -c vyper -f -n '__fish_vyper_using_command doctor' -l json -d 'JSON output'
complete -c vyper -f -n '__fish_vyper_using_command watch' -l level -d 'Minimum event level' -xa 'CRITICAL ERROR WARNING INFO SUCCESS'
complete -c vyper -f -n '__fish_vyper_using_command watch' -l json -d 'JSON output'
complete -c vyper -f -n '__fish_vyper_using_command watch' -l notify -d 'Notification method'
complete -c vyper -f -n '__fish_vyper_using_command watch' -l interval -d 'Poll interval seconds'
complete -c vyper -f -n '__fish_vyper_using_command benchmark' -l runs -d 'Number of runs'
complete -c vyper -f -n '__fish_vyper_using_command benchmark' -l service -d 'Single service only'
complete -c vyper -f -n '__fish_vyper_using_command benchmark' -l json -d 'JSON output'
"""

# ── Typer App ────────────────────────────────────────────────────

app = typer.Typer(
    name="vyper",
    help="Smart Contract Bug Hunter — analyze, exploit, and report on Solidity contracts",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    context_settings={"help_option_names": ["--help", "-h"]},
)


# ── Global Callbacks ─────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    completion: Optional[str] = typer.Option(
        None,
        "--completion",
        help="Generate shell completion script (bash|zsh|fish)",
        callback=_completion_callback,
        is_eager=True,
        expose_value=False,
        rich_help_panel="Global Options",
    ),
    color: str = typer.Option(
        "auto",
        "--color",
        help="Color output mode: auto, never, always",
        rich_help_panel="Global Options",
        case_sensitive=False,
    ),
) -> None:
    """Vyper CLI — Smart Contract Bug Hunter.

    Analyze, exploit, and report on Solidity contracts with AI-powered audit pipeline.
    """
    global _COLOR_MODE
    _COLOR_MODE = color.lower()

    # Apply color mode
    if _COLOR_MODE == "never":
        os.environ["NO_COLOR"] = "true"
        os.environ["FORCE_COLOR"] = "0"
    elif _COLOR_MODE == "always":
        os.environ.pop("NO_COLOR", None)
        os.environ["FORCE_COLOR"] = "1"

    if ctx.invoked_subcommand is None:
        # Show help if no subcommand (no_args_is_help handles this)
        pass

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

# ── Agent commands ───────────────────────────────────────────────

app.add_typer(agent_cmd, name="agent", help="Inspect Antonio AI agent status and sessions")
app.add_typer(doctor_cmd, name="doctor", help="Run system diagnostic — services, agent, filesystem")
app.add_typer(watch_cmd, name="watch", help="Watch Vyper events in real-time — audits, state changes, service health")
app.add_typer(benchmark_cmd, name="benchmark", help="Benchmark pipeline performance — measure and detect bottlenecks")

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
