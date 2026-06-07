"""BatchProcessor — runs multiple audits concurrently with debounce support."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from src.config import config
from src.models import PipelineState, QueueItem
from src.pipeline import Pipeline

logger = logging.getLogger("vyper.orchestrator.batch")


class BatchProcessor:
    """Process multiple audits in parallel with debounce and queue support.

    Usage:
        batch = BatchProcessor(pipeline)
        results = await batch.batch_run(["audit-1", "audit-2"])
        await batch.process_queue()
    """

    def __init__(self, pipeline: Pipeline) -> None:
        self._pipeline = pipeline
        self._queue: list[QueueItem] = []
        self._lock = asyncio.Lock()
        self._load_queue()

    # ── Queue persistence ───────────────────────────────────────

    def _load_queue(self) -> None:
        path = config.queue_file
        if not path.exists():
            return
        import json
        try:
            raw = json.loads(path.read_text("utf-8"))
            self._queue = [QueueItem(**item) for item in raw]
        except (json.JSONDecodeError, OSError, Exception) as exc:
            logger.warning("Failed to load queue: %s", exc)

    def _save_queue(self) -> None:
        path = config.queue_file
        path.parent.mkdir(parents=True, exist_ok=True)
        import json
        payload = [item.model_dump(mode="json") for item in self._queue]
        path.write_text(json.dumps(payload, indent=2, default=str), "utf-8")

    # ── Queue management ────────────────────────────────────────

    def add_to_queue(self, item: QueueItem) -> None:
        """Add a contract to the priority queue. Updates score if re-added."""
        existing = next(
            (q for q in self._queue if q.contract_id == item.contract_id), None
        )
        if existing:
            existing.priority_score = max(existing.priority_score, item.priority_score)
            existing.program = item.program or existing.program
            logger.info("Updated queue item %s (score=%.1f)", item.contract_id, existing.priority_score)
        else:
            self._queue.append(item)
            logger.info("Added to queue: %s (score=%.1f)", item.contract_id, item.priority_score)
        self._save_queue()

    def remove_from_queue(self, contract_id: str) -> bool:
        before = len(self._queue)
        self._queue = [q for q in self._queue if q.contract_id != contract_id]
        removed = len(self._queue) < before
        if removed:
            self._save_queue()
        return removed

    def get_queue(self, sorted_: bool = True) -> list[QueueItem]:
        if sorted_:
            return sorted(
                self._queue,
                key=lambda q: q.priority_score,
                reverse=True,
            )
        return list(self._queue)

    def clear_queue(self) -> None:
        self._queue.clear()
        self._save_queue()

    def queue_size(self) -> int:
        return len(self._queue)

    def get_debounce_status(self, chain: str, address: str) -> tuple[bool, str | None]:
        """Check if a contract was recently audited (debounce window).

        Returns:
            (is_debounced, reason_string)
        """
        contract_id = f"{chain}:{address}".lower()
        for record_list in [self._pipeline.get_all_records()]:
            records, _ = record_list
            for r in records:
                cid = f"{r.chain}:{r.address}".lower()
                if cid == contract_id and r.state == PipelineState.COMPLETED:
                    if r.updated_at:
                        elapsed = datetime.now(UTC) - r.updated_at
                        if elapsed < timedelta(hours=config.debounce_hours):
                            remaining = timedelta(hours=config.debounce_hours) - elapsed
                            return (
                                True,
                                f"Skipped (debounced {int(remaining.total_seconds()//60)}m remaining)",
                            )
        return False, None

    # ── Batch execution ────────────────────────────────────────

    async def batch_run(self, audit_ids: list[str]) -> dict[str, Any]:
        """Run multiple audits concurrently.

        Returns:
            {audit_id: AuditRecord or error_message}
        """
        semaphore = asyncio.Semaphore(config.batch_default_size)
        results: dict[str, Any] = {}

        async def _run_one(audit_id: str) -> None:
            async with semaphore:
                try:
                    record = await self._pipeline.run(audit_id)
                    results[audit_id] = record
                except Exception as exc:
                    logger.exception("Batch run failed for %s", audit_id)
                    results[audit_id] = {"error": str(exc)}

        tasks = [_run_one(aid) for aid in audit_ids]
        await asyncio.gather(*tasks)
        return results

    async def process_queue(self, count: int | None = None) -> dict[str, Any]:
        """Process the next N items from the priority queue.

        Args:
            count: Number of items to process. Defaults to batch_default_size.

        Returns:
            Dict with keys: processed, skipped, results
        """
        count = count or config.batch_default_size
        async with self._lock:
            if not self._queue:
                return {"processed": 0, "skipped": 0, "results": []}

            # Sort and pick top N
            sorted_queue = sorted(
                self._queue, key=lambda q: q.priority_score, reverse=True
            )
            to_process = sorted_queue[:count]

            audit_ids: list[str] = []
            skipped: list[str] = []

            for item in to_process:
                # Debounce check
                is_debounced, reason = self.get_debounce_status(item.chain, item.address)
                if is_debounced:
                    item.skip_reason = reason
                    skipped.append(item.contract_id)
                    logger.info("Skipped debounced item: %s — %s", item.contract_id, reason)
                    continue

                # Register audit
                aid = self._pipeline.register_audit(
                    chain=item.chain,
                    address=item.address,
                    program=item.program,
                    priority=int(item.priority_score),
                )
                audit_ids.append(aid)
                # Remove from queue
                self._queue = [q for q in self._queue if q.contract_id != item.contract_id]

            self._save_queue()

        if not audit_ids:
            return {"processed": 0, "skipped": len(skipped), "results": []}

        logger.info("Processing %d audits from queue (skipped %d)", len(audit_ids), len(skipped))
        results = await self.batch_run(audit_ids)
        return {
            "processed": len(audit_ids),
            "skipped": len(skipped),
            "results": results,
        }


__all__ = ["BatchProcessor"]
