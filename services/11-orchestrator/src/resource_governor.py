"""ResourceGovernor — prevents overloading the system with concurrent scans / AI calls."""

from __future__ import annotations

import asyncio
from enum import StrEnum


class ToolType(StrEnum):
    SCANNER = "scanner"
    AI = "ai"
    CLASSIFIER = "classifier"
    EXPLOIT = "exploit"
    SOURCE = "source"
    REPORTER = "reporter"


class ResourceGovernor:
    """Manages concurrency slots for each tool type via per-tool semaphores.

    Usage:
        governor = ResourceGovernor(max_concurrent_scans=2, max_concurrent_ai=1)
        async with governor.acquire(ToolType.SCANNER):
            ...  # safe to scan
    """

    def __init__(
        self,
        max_concurrent_scans: int = 2,
        max_concurrent_ai: int = 1,
    ) -> None:
        self._semaphores: dict[ToolType, asyncio.Semaphore] = {
            ToolType.SCANNER: asyncio.Semaphore(max_concurrent_scans),
            ToolType.AI: asyncio.Semaphore(max_concurrent_ai),
            ToolType.CLASSIFIER: asyncio.Semaphore(2),
            ToolType.EXPLOIT: asyncio.Semaphore(1),
            ToolType.SOURCE: asyncio.Semaphore(3),
            ToolType.REPORTER: asyncio.Semaphore(2),
        }
        self._max_counts: dict[ToolType, int] = {
            ToolType.SCANNER: max_concurrent_scans,
            ToolType.AI: max_concurrent_ai,
            ToolType.CLASSIFIER: 2,
            ToolType.EXPLOIT: 1,
            ToolType.SOURCE: 3,
            ToolType.REPORTER: 2,
        }

    # ── Public queries ─────────────────────────────────────────

    def can_start(self, tool_type: ToolType) -> bool:
        """Check whether a slot is available *without* acquiring it."""
        sem = self._semaphores[tool_type]
        return sem.locked() is False  # locked() returns True only if value is 0

    def available_slots(self, tool_type: ToolType) -> int:
        sem = self._semaphores[tool_type]
        return sem._value  # type: ignore[attr-defined]

    def max_slots(self, tool_type: ToolType) -> int:
        return self._max_counts[tool_type]

    # ── Context-manager based acquire / release ─────────────────

    async def acquire(self, tool_type: ToolType) -> ResourceGuard:
        """Acquire a slot; blocks until one is free. Returns an async context manager."""
        await self._semaphores[tool_type].acquire()
        return ResourceGuard(governor=self, tool_type=tool_type)

    def release(self, tool_type: ToolType) -> None:
        """Release a slot. Called by ResourceGuard on context exit."""
        self._semaphores[tool_type].release()

    async def __aenter__(self) -> ResourceGovernor:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass


class ResourceGuard:
    """Async context manager that releases the slot on exit."""

    def __init__(self, governor: ResourceGovernor, tool_type: ToolType) -> None:
        self._governor = governor
        self._tool_type = tool_type

    async def __aenter__(self) -> ResourceGuard:
        return self

    async def __aexit__(self, *args: object) -> None:
        self._governor.release(self._tool_type)


# Re-export for convenience
__all__ = ["ResourceGovernor", "ToolType", "ResourceGuard"]
