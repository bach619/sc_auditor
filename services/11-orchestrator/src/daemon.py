"""Daemon — continuous scanning loop that orchestrates the audit pipeline.

Daemon cycle:
  1. Sync Immunefi programs
  2. Calculate priority scores for un-audited contracts
  3. Pick top N contracts (configurable, default 3)
  4. Run pipeline for each
  5. Sleep for interval (configurable, default 60 min)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from src.batch import BatchProcessor
from src.config import config
from src.models import DaemonState, DaemonStatus, QueueItem
from src.pipeline import Pipeline
from src.priority import PriorityScorer

logger = logging.getLogger("vyper.orchestrator.daemon")


class Daemon:
    """Background daemon that continuously scans high-priority contracts.

    Usage:
        daemon = Daemon(pipeline, batch_processor, priority_scorer)
        await daemon.start()          # runs forever in background task
        await daemon.stop()           # cancels the loop
        status = daemon.get_status()  # current state
    """

    def __init__(
        self,
        pipeline: Pipeline,
        batch_processor: BatchProcessor,
        priority_scorer: PriorityScorer,
    ) -> None:
        self._pipeline = pipeline
        self._batch = batch_processor
        self._scorer = priority_scorer
        self._state = DaemonState()
        self._task: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None
        self._load_state()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client

    # ── State persistence ───────────────────────────────────────

    def _load_state(self) -> None:
        path = config.daemon_state_file
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text("utf-8"))
            self._state = DaemonState(**raw)
        except (json.JSONDecodeError, OSError, Exception) as exc:
            logger.warning("Failed to load daemon state: %s", exc)

    def _save_state(self) -> None:
        path = config.daemon_state_file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self._state.model_dump(mode="json"), indent=2, default=str),
            "utf-8",
        )

    # ── Lifecycle ───────────────────────────────────────────────

    async def start(self) -> DaemonState:
        """Start the daemon. If already running, returns current state."""
        if self._state.status == DaemonStatus.RUNNING:
            logger.warning("Daemon already running")
            return self._state

        self._state.status = DaemonStatus.RUNNING
        self._state.started_at = datetime.now(UTC)
        self._state.last_error = None
        self._save_state()

        self._task = asyncio.create_task(self._run_loop())
        logger.info("Daemon started — interval=%d min, batch=%d",
                     config.daemon_interval_minutes, config.daemon_batch_size)
        return self._state

    async def stop(self) -> DaemonState:
        """Gracefully stop the daemon."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        self._state.status = DaemonStatus.STOPPED
        self._state.stopped_at = datetime.now(UTC)
        self._save_state()
        logger.info("Daemon stopped")
        return self._state

    def get_status(self) -> DaemonState:
        return self._state

    # ── Main loop ───────────────────────────────────────────────

    async def _run_loop(self) -> None:
        """Continuously run scan cycles until cancelled."""
        try:
            while True:
                cycle_start = datetime.now(UTC)
                logger.info("Daemon cycle starting")

                try:
                    await self._run_cycle()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.exception("Daemon cycle failed")
                    self._state.last_error = str(exc)
                    self._state.status = DaemonStatus.ERROR
                    self._save_state()

                self._state.last_run_at = cycle_start
                self._state.total_cycles_completed += 1
                self._state.next_run_at = cycle_start + timedelta(
                    minutes=config.daemon_interval_minutes
                )
                self._state.status = DaemonStatus.RUNNING
                self._save_state()

                # Sleep until next cycle
                sleep_seconds = config.daemon_interval_minutes * 60
                logger.info(
                    "Daemon cycle complete. Next run at %s (sleep %ds)",
                    self._state.next_run_at.isoformat() if self._state.next_run_at else "?",
                    sleep_seconds,
                )
                await asyncio.sleep(sleep_seconds)

        except asyncio.CancelledError:
            logger.info("Daemon loop cancelled")
            raise

    async def _run_cycle(self) -> None:
        """Single daemon cycle: cleanup → sync → score → queue → process."""

        # 0. Recover stuck audits before processing new items
        try:
            result = await self._pipeline.resume_stuck_audits()
            if result["total_stuck"] > 0:
                logger.info("Stuck audit recovery: %s", result)
        except Exception as exc:
            logger.exception("Stuck audit recovery failed: %s", exc)

        # 1. Sync Immunefi programs
        programs = await self._sync_immunefi_programs()
        logger.info("Synced %d Immunefi programs", len(programs))

        # 2. Calculate priority scores for contracts and add to queue
        added_count = 0
        for program in programs[:50]:  # Limit to top 50 per cycle
            for contract in self._extract_contracts(program):
                score = self._scorer.score(
                    program=program,
                    chain=contract.get("chain", "ethereum"),
                    program_slug=program.get("slug", ""),
                    created_at=datetime.now(UTC),
                )
                contract_id = f"{contract.get('chain', 'ethereum')}:{contract.get('address', '')}"
                queue_item = QueueItem(
                    contract_id=contract_id,
                    chain=contract.get("chain", "ethereum"),
                    address=contract.get("address", ""),
                    program=program.get("slug", ""),
                    priority_score=score,
                )
                self._batch.add_to_queue(queue_item)
                added_count += 1

        logger.info("Added %d contracts to queue", added_count)

        # 3. Process top N from queue
        result = await self._batch.process_queue(count=config.daemon_batch_size)
        processed = result.get("processed", 0)
        self._state.total_contracts_audited += processed
        self._save_state()
        logger.info("Daemon cycle processed %d contracts", processed)

    # ── Immunefi sync ───────────────────────────────────────────

    async def _sync_immunefi_programs(self) -> list:
        """Fetch program list from Immunefi service.

        Response shape (wrapped in ApiResponse):
          { "data": { "data": [...programs...], "total": N, ... }, "meta": {...} }
        """
        try:
            resp = await self.client.get(f"{config.immunefi_url}/programs")
            resp.raise_for_status()
            data = resp.json()
            # Unwrap ApiResponse: data → inner → program list
            if isinstance(data, dict):
                inner = data.get("data") or {}
                if isinstance(inner, dict):
                    return inner.get("data") or []
                if isinstance(inner, list):
                    return inner
            return data if isinstance(data, list) else []
        except httpx.HTTPError as exc:
            logger.warning("Immunefi sync failed: %s", exc)
            return []

    @staticmethod
    def _extract_contracts(program: dict[str, Any]) -> list:
        """Extract contract addresses from an Immunefi program object."""
        contracts = []
        # Try various shapes of Immunefi API response
        targets = program.get("targets") or program.get("contracts") or []
        for t in targets:
            chain = t.get("chain") or t.get("network") or "ethereum"
            address = t.get("address") or t.get("contract_address") or ""
            if address:
                contracts.append({"chain": chain, "address": address})
        return contracts


__all__ = ["Daemon"]
