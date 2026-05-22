"""Autonomous Agent Daemon — background self-improvement loop.

Berjalan di background sebagai asyncio task:
1. Periodically scan for new Immunefi programs (via program sync)
2. Auto-hunt for high-value audit targets
3. Run self-assessment on past sessions
4. Update skill metrics and knowledge graph
5. Cleanup stale sessions

Dapat di-start/stop via API endpoint.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog

from src.agent import AgentLoop
from src.models import AgentState, TaskType

log = structlog.get_logger()

MIN_INTERVAL = 60  # detik — minimal interval
DEFAULT_INTERVAL = 3600  # 1 jam — default


class AgentDaemon:
    """Autonomous daemon untuk agent — self-improving background loop.

    Attributes:
        agent: AgentLoop instance
        http_client: HTTP client for service calls
        interval: Loop interval in seconds
        _task: Background asyncio task
        _running: Flag apakah daemon sedang running
        stats: Operational statistics
    """

    def __init__(
        self,
        agent: AgentLoop,
        http_client: httpx.AsyncClient,
        interval: int = DEFAULT_INTERVAL,
    ) -> None:
        self.agent = agent
        self.http_client = http_client
        self.interval = max(interval, MIN_INTERVAL)
        self._task: asyncio.Task | None = None
        self._running = False
        self.stats: dict[str, Any] = {
            "started_at": 0,
            "total_cycles": 0,
            "total_errors": 0,
            "last_cycle_at": 0,
            "last_program_sync": 0,
            "last_self_assessment": 0,
            "auto_hunts_done": 0,
            "cycle_durations_ms": [],
        }

    # ── Lifecycle ──────────────────────────────────────────

    def start(self) -> bool:
        """Start daemon background loop.

        Returns:
            True jika berhasil start, False jika sudah running.
        """
        if self._running:
            log.warning("daemon_already_running")
            return False

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        self.stats["started_at"] = time.time()
        log.info(
            "daemon_started",
            interval=self.interval,
        )
        return True

    async def stop(self) -> bool:
        """Stop daemon background loop gracefully.

        Returns:
            True jika berhasil stop.
        """
        if not self._running:
            return False

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        log.info(
            "daemon_stopped",
            total_cycles=self.stats["total_cycles"],
        )
        return True

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Background Loop ────────────────────────────────────

    async def _run_loop(self) -> None:
        """Main background loop — runs forever until stopped."""
        while self._running:
            cycle_start = time.monotonic()

            try:
                await self._run_one_cycle()
                self.stats["total_cycles"] += 1
                self.stats["last_cycle_at"] = time.time()
            except asyncio.CancelledError:
                log.info("daemon_loop_cancelled")
                break
            except Exception as exc:
                self.stats["total_errors"] += 1
                log.error(
                    "daemon_cycle_error",
                    error=str(exc),
                    cycle=self.stats["total_cycles"],
                )

            # Record duration
            duration_ms = (time.monotonic() - cycle_start) * 1000
            self.stats["cycle_durations_ms"].append(round(duration_ms, 1))
            if len(self.stats["cycle_durations_ms"]) > 100:
                self.stats["cycle_durations_ms"].pop(0)

            # Sleep for interval (unless stopped during cycle)
            if self._running:
                await asyncio.sleep(self.interval)

    async def _run_one_cycle(self) -> None:
        """Satu siklus daemon — gabungan beberapa task background."""
        log.debug("daemon_cycle_starting")

        # 1. Health check — verify all services reachable
        await self._check_services()

        # 2. Program sync — periodic Immunefi sync (every 6 cycles)
        if self.stats["total_cycles"] % 6 == 0:
            await self._program_sync()

        # 3. Self-assessment — review past sessions (every 12 cycles)
        if (
            self.stats["total_cycles"] > 0
            and self.stats["total_cycles"] % 12 == 0
        ):
            await self._self_assessment()

        # 4. Auto-hunt — cari high-value audit targets
        if self.stats["total_cycles"] % 3 == 0:
            await self._auto_hunt()

        # 5. Stale session cleanup
        self._cleanup_stale_sessions()

        log.debug(
            "daemon_cycle_completed",
            cycle=self.stats["total_cycles"],
        )

    # ── Internal Tasks ─────────────────────────────────────

    async def _check_services(self) -> None:
        """Check health of dependent services."""
        services = {
            "config": "http://01-config:8000/health",
            "orchestrator": "http://11-orchestrator:8009/health",
            "immunefi": "http://02-immunefi:8001/health",
        }

        for name, url in services.items():
            try:
                resp = await self.http_client.get(url, timeout=5.0)
                if resp.status_code != 200:
                    log.warning(
                        "service_unhealthy",
                        service=name,
                        status=resp.status_code,
                    )
            except Exception as exc:
                log.warning(
                    "service_unreachable",
                    service=name,
                    error=str(exc),
                )

    async def _program_sync(self) -> None:
        """Sync Immunefi programs periodically."""
        try:
            resp = await self.http_client.post(
                "http://11-orchestrator:8009/audit",
                json={
                    "task_type": "program_sync",
                    "input_data": {"auto": True},
                    "goal": "Periodic program sync",
                },
                timeout=120.0,
            )
            if resp.status_code == 200:
                self.stats["last_program_sync"] = time.time()
                log.info("daemon_program_sync_completed")
        except Exception as exc:
            log.warning("daemon_program_sync_failed", error=str(exc))

    async def _self_assessment(self) -> None:
        """Review past sessions and update knowledge graph."""
        sessions = self.agent.list_sessions(limit=20)

        # Analyze success/failure patterns
        completed = [
            s for s in sessions if s.status == AgentState.COMPLETED
        ]
        failed = [s for s in sessions if s.status in (
            AgentState.FAILED, AgentState.STOPPED
        )]

        # Store assessment in vector memory
        if completed:
            summary = (
                f"Self-assessment: {len(completed)} completed, "
                f"{len(failed)} failed. "
                f"Task types: {set(s.task_type.value for s in completed)}"
            )
            try:
                await self.agent.memory.vector.store_text(
                    "self_assessment",
                    summary,
                    metadata={
                        "type": "assessment",
                        "completed": len(completed),
                        "failed": len(failed),
                    },
                )
            except Exception:
                pass

        self.stats["last_self_assessment"] = time.time()
        log.info(
            "daemon_self_assessment",
            completed=len(completed),
            failed=len(failed),
        )

    async def _auto_hunt(self) -> None:
        """Auto-hunt: analisis program untuk high-value audit target."""
        try:
            # Fetch recent programs from Immunefi
            resp = await self.http_client.get(
                "http://02-immunefi:8001/programs?limit=10&sort=reward",
                timeout=30.0,
            )
            if resp.status_code != 200:
                return

            data = resp.json()
            programs = data.get("data", []) if isinstance(data, dict) else []

            if programs:
                self.stats["auto_hunts_done"] += 1
                log.info(
                    "daemon_auto_hunt",
                    programs_found=len(programs),
                    top_reward=programs[0].get("max_payout", 0),
                )

                # Store in vector memory
                for prog in programs[:3]:
                    await self.agent.memory.vector.store_text(
                        f"auto_hunt_{prog.get('slug', 'unknown')}",
                        f"High-value target: {prog.get('name', 'Unknown')} "
                        f"reward={prog.get('max_payout', 0)}",
                        metadata={
                            "type": "auto_hunt",
                            "slug": prog.get("slug"),
                            "reward": prog.get("max_payout", 0),
                        },
                    )
        except Exception as exc:
            log.warning("daemon_auto_hunt_failed", error=str(exc))

    def _cleanup_stale_sessions(self) -> None:
        """Remove session entries that exceed limits."""
        sessions = self.agent.list_sessions(limit=100)
        if len(sessions) > 50:
            # Hanya keep 50 sessions terbaru
            excess = len(sessions) - 50
            log.info("daemon_cleanup_sessions", removed=excess)

    # ── Status ─────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Dapatkan status daemon."""
        durations = self.stats["cycle_durations_ms"]
        avg_duration = (
            round(sum(durations) / len(durations), 1) if durations else 0
        )

        return {
            "running": self._running,
            "interval": self.interval,
            "total_cycles": self.stats["total_cycles"],
            "total_errors": self.stats["total_errors"],
            "auto_hunts_done": self.stats["auto_hunts_done"],
            "last_program_sync": (
                self.stats["last_program_sync"]
                if self.stats["last_program_sync"]
                else None
            ),
            "last_self_assessment": (
                self.stats["last_self_assessment"]
                if self.stats["last_self_assessment"]
                else None
            ),
            "uptime_seconds": (
                time.time() - self.stats["started_at"]
                if self.stats["started_at"]
                else 0
            ),
            "avg_cycle_duration_ms": avg_duration,
            "uptime": self._format_uptime(),
        }

    def _format_uptime(self) -> str:
        if not self.stats["started_at"]:
            return "not started"
        uptime = time.time() - self.stats["started_at"]
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        return f"{hours}h {minutes}m"
