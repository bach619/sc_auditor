"""Async queue manager for Echidna scan requests.

Prevents resource exhaustion by limiting concurrent Echidna runs
and providing queue status/ordering.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine


@dataclass
class QueueItem:
    """A single scan request in the queue."""
    audit_id: str
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    status: str = "queued"  # queued, running, completed, failed
    result: Any = None
    error: str | None = None


class ScanQueue:
    """Manages concurrent Echidna scan executions.
    
    Usage:
        queue = ScanQueue(max_concurrent=1)
        result = await queue.enqueue("audit-123", runner.run, audit_dir, ...)
    """
    
    def __init__(self, max_concurrent: int = 1) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._items: dict[str, QueueItem] = {}
        self._max_concurrent = max_concurrent
    
    async def enqueue(
        self,
        audit_id: str,
        coro_factory: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Enqueue a scan request and wait for result.
        
        Args:
            audit_id: Unique identifier for this scan.
            coro_factory: Async callable that runs the scan.
            *args, **kwargs: Passed to coro_factory.
        
        Returns:
            The result from coro_factory.
        """
        item = QueueItem(audit_id=audit_id)
        self._items[audit_id] = item
        
        async with self._semaphore:
            item.status = "running"
            item.started_at = time.time()
            try:
                result = await coro_factory(*args, **kwargs)
                item.status = "completed"
                item.result = result
                return result
            except Exception as exc:
                item.status = "failed"
                item.error = str(exc)
                raise
    
    def get_status(self, audit_id: str) -> dict[str, Any] | None:
        """Get status of a queued item."""
        item = self._items.get(audit_id)
        if not item:
            return None
        return {
            "audit_id": item.audit_id,
            "status": item.status,
            "queued_at": item.created_at,
            "started_at": item.started_at,
            "wait_time_seconds": round(time.time() - item.created_at, 2) if item.status == "running" else None,
        }
    
    def get_queue_summary(self) -> dict[str, Any]:
        """Get summary of all queue items."""
        statuses: dict[str, int] = {}
        for item in self._items.values():
            statuses[item.status] = statuses.get(item.status, 0) + 1
        return {
            "total": len(self._items),
            "statuses": statuses,
            "max_concurrent": self._max_concurrent,
            "currently_running": sum(1 for i in self._items.values() if i.status == "running"),
        }
