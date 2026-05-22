"""Backup commands — create, list, restore, prune.

Usage:
    vyper backup create [--name <name>]
    vyper backup list [--json]
    vyper backup restore <name>
    vyper backup prune [--max-age 30] [--min-keep 5]
"""

from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.console import Console

from cli.client import VyperClient
from cli.output import print_json, show_error, show_success

console = Console()
err_console = Console(stderr=True)

# ── Typer sub-app ────────────────────────────────────────────────

backup_app = typer.Typer(
    name="backup",
    help="Manage backups",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


# ── Helpers ──────────────────────────────────────────────────────

def _async_run(coro):
    return asyncio.run(coro)


# ── Commands ─────────────────────────────────────────────────────

@backup_app.command()
def create(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Optional backup name"),
) -> None:
    """Create a new backup."""
    async def _run() -> None:
        async with VyperClient() as client:
            try:
                result = await client.create_backup(name)
            except Exception as exc:
                show_error(f"Backup creation failed: {exc}")
                raise typer.Exit(1)
            show_success(f"Backup created: {result}")

    _async_run(_run())


@backup_app.command()
def list_backups(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """List available backups."""
    async def _run() -> None:
        async with VyperClient() as client:
            try:
                backups = await client.list_backups()
            except Exception as exc:
                show_error(f"Failed to list backups: {exc}")
                raise typer.Exit(1)

            if not backups:
                console.print("[yellow]No backups found.[/]")
                return

            if json_output:
                print_json(backups)
                return

            console.print(f"\n{'Name':<35} {'Size':<12} {'Age':<10} {'Created':<25}")
            console.print("-" * 82)
            for b in backups:
                size = f"{b['size_bytes'] / 1024 / 1024:.1f} MB"
                console.print(
                    f"{b['name']:<35} {size:<12} {b.get('age_days', '?'):<10} {b.get('created_at', '?'):<25}"
                )

    _async_run(_run())


@backup_app.command()
def restore(
    name: str = typer.Argument(..., help="Backup name to restore"),
) -> None:
    """Restore from a backup."""
    async def _run() -> None:
        async with VyperClient() as client:
            try:
                success = await client.restore_backup(name)
            except Exception as exc:
                show_error(f"Restore failed: {exc}")
                raise typer.Exit(1)
            if success:
                show_success(f"Restored from backup: {name}")
            else:
                show_error(f"Restore failed: {name}")

    _async_run(_run())


@backup_app.command()
def prune(
    max_age: int = typer.Option(30, "--max-age", help="Max age in days"),
    min_keep: int = typer.Option(5, "--min-keep", help="Minimum backups to keep"),
) -> None:
    """Prune old backups."""
    async def _run() -> None:
        async with VyperClient() as client:
            try:
                removed = await client.prune_backups(max_age, min_keep)
            except Exception as exc:
                show_error(f"Prune failed: {exc}")
                raise typer.Exit(1)
            show_success(f"Pruned {removed} old backup(s)")

    _async_run(_run())
