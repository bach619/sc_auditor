"""Benchmark command — measure pipeline performance.

Usage:
    vyper benchmark 0x4c9e...                   # benchmark full pipeline
    vyper benchmark 0x4c9e... --runs 3          # 3 runs for avg
    vyper benchmark --service 04-scanner --runs 5  # benchmark one service
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cli.client import VyperClient
from cli.output import show_error, show_success

app = typer.Typer()
console = Console()
err_console = Console(stderr=True)


@app.callback()
def callback() -> None:
    """Benchmark pipeline performance."""


@app.command()
def benchmark(
    address: str = typer.Argument(default="", help="Contract address to benchmark"),
    service: str = typer.Option("", "--service", "-s", help="Single service to benchmark"),
    runs: int = typer.Option(3, "--runs", "-r", help="Number of benchmark runs"),
    chain: str = typer.Option("ethereum", "--chain", "-c", help="Blockchain name"),
    program: str = typer.Option("", "--program", "-p", help="Program slug"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Benchmark audit pipeline performance."""
    if not address and not service:
        show_error("Provide a contract address or use --service to benchmark a single service")
        raise typer.Exit(1)

    async def _run() -> None:
        async with VyperClient() as client:
            results: dict[str, list[float]] = defaultdict(list)
            total_times: list[float] = []

            for run_num in range(1, runs + 1):
                console.print(f"[bold cyan]Run {run_num}/{runs}...[/]")

                run_start = time.monotonic()

                if service:
                    # Benchmark single service
                    if service == "04-scanner" or service == "scanner":
                        sources = {"benchmark.sol": "contract A { function f() public {} }"}
                        try:
                            s = time.monotonic()
                            result = await client.scan_contract(
                                sources=sources, compiler="0.8.20",
                                tools=["slither"],
                            )
                            dur = time.monotonic() - s
                            results[f"scan_{service}"].append(dur)
                            console.print(f"  [green]✓[/] {service}: {dur:.2f}s")
                        except Exception as exc:
                            console.print(f"  [red]✗[/] {service}: FAILED — {exc}")
                    else:
                        show_error(f"Unknown service: {service}")
                        raise typer.Exit(1)
                else:
                    # Full pipeline benchmark
                    try:
                        result = await client.start_audit(
                            address=address, chain=chain,
                            program=program, priority=1,
                        )
                    except Exception as exc:
                        show_error(f"Failed to start audit (run {run_num}): {exc}")
                        continue

                    audit_id = result.get("audit_id", "")
                    start_time = time.monotonic()

                    # Poll until completion
                    while True:
                        elapsed = time.monotonic() - start_time
                        if elapsed > 600:
                            console.print(f"  [red]✗[/] Run {run_num}: TIMEOUT")
                            break

                        try:
                            status = await client.get_audit(audit_id)
                        except Exception:
                            await asyncio.sleep(2)
                            continue

                        state = status.get("state", "")
                        steps = status.get("steps", [])

                        for step in steps:
                            step_name = step.get("name", "?")
                            step_dur = step.get("duration_seconds")
                            step_state = step.get("state", "")
                            if step_name and step_dur and step_state == "completed":
                                results[step_name].append(step_dur)

                        if state in ("completed",) or "failed" in state or state in ("timeout", "aborted"):
                            total_dur = time.monotonic() - start_time
                            total_times.append(total_dur)
                            status_icon = "✅" if state == "completed" else "❌"
                            console.print(f"  {status_icon} Run {run_num}: {total_dur:.1f}s — {state}")
                            break

                        await asyncio.sleep(2)

                await asyncio.sleep(1)  # Cool-down between runs

            # ── Results ──
            if json_output:
                import json as j
                console.print(j.dumps({
                    "runs": runs,
                    "service": service or "full_pipeline",
                    "results": dict(results),
                }, indent=2, default=str))
                return

            console.print()
            title = f"Benchmark: {service or address[:20]} ({runs} runs)"
            table = Table(title=title, box=None, header_style="bold cyan")
            table.add_column("Step", width=24)
            table.add_column("Min", width=10)
            table.add_column("Max", width=10)
            table.add_column("Avg", width=10)
            table.add_column("Δ", width=8)
            table.add_column("Runs", width=6)

            for step_name, durs in sorted(results.items()):
                if not durs:
                    continue
                min_d = min(durs)
                max_d = max(durs)
                avg_d = sum(durs) / len(durs)
                delta = max_d - min_d
                delta_str = f"[yellow]{delta:.2f}s[/]" if delta > 2 else f"[green]{delta:.2f}s[/]"
                table.add_row(
                    step_name,
                    f"{min_d:.2f}s",
                    f"{max_d:.2f}s",
                    f"[bold]{avg_d:.2f}s[/]",
                    delta_str,
                    str(len(durs)),
                )

            console.print(table)

            # Overall
            if total_times:
                avg_total = sum(total_times) / len(total_times)
                console.print(f"\n[bold]Overall:[/] avg {avg_total:.1f}s across {len(total_times)} runs")

            # Bottleneck detection
            if results:
                avg_times = {
                    step: sum(durs) / len(durs)
                    for step, durs in results.items() if durs
                }
                if avg_times:
                    bottleneck = max(avg_times, key=avg_times.get)  # type: ignore[arg-type]
                    b_time = avg_times[bottleneck]
                    console.print(f"\n[bold]🔍 Bottleneck:[/] [red]{bottleneck}[/] ({b_time:.1f}s avg)")

    asyncio.run(_run())
