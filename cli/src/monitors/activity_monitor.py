"""
VYPER TUI v2 — ActivityMonitorV2

State cache untuk activity semua service.
Tidak lagi melakukan polling — diperbarui oleh EventBus via SSE events.

Setiap service memiliki:
  - ServiceActivity (status, task, progress, dll.)
  - Sparkline 60-sample (1 menit activity history sebagai proxy CPU load)

Sparkline encoding:
  0=idle, 50=pending, 100=busy, 0=error
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING

from cli.src.core.state_store import AppState
from cli.src.models.activity import ServiceActivity

if TYPE_CHECKING:
    from cli.src.core.event_bus import EventBus, VyperEvent

logger = logging.getLogger("vyper_tui.activity_monitor")

CPU_PROXY_MAP = {
    "busy": 100,
    "idle": 0,
    "pending": 50,
    "error": 0,
    "unknown": 0,
}


class ActivityMonitorV2:
    """
    State cache event-driven untuk semua service.

    Tidak melakukan polling. Hanya memproses event dari EventBus
    dan memelihara state cache + sparkline generator.

    Usage:
        monitor = ActivityMonitorV2(event_bus)
        # otomatis register handler via constructor

        state = monitor.get("04-scanner")
        sparkline = monitor.get_sparkline("04-scanner")
        busy_services = monitor.get_busy_services()
    """

    SPARKLINE_WINDOW = 60  # 60 samples ≈ 1 menit

    def __init__(self, event_bus: EventBus):
        self._cache: dict[str, ServiceActivity] = {}
        self._sparklines: dict[str, deque[int]] = {}

        # Register handler ke EventBus
        @event_bus.on("service.activity")
        async def handle_activity(event: VyperEvent) -> None:
            self._update(event)

        @event_bus.on("service.health")
        async def handle_health(event: VyperEvent) -> None:
            self._update_health(event)

        logger.debug("ActivityMonitorV2 initialized")

    # ── Public API ──────────────────────────────────────────────────────

    def get(self, service: str) -> ServiceActivity | None:
        """Dapatkan activity terakhir untuk satu service."""
        return self._cache.get(service)

    def get_all(self) -> dict[str, ServiceActivity]:
        """Dapatkan semua activity."""
        return dict(self._cache)

    def get_busy_services(self) -> list[str]:
        """Dapatkan daftar service yang sedang busy."""
        return [
            s for s, a in self._cache.items()
            if a.status == "busy"
        ]

    def get_error_services(self) -> list[str]:
        """Dapatkan daftar service yang error."""
        return [
            s for s, a in self._cache.items()
            if a.status == "error"
        ]

    def get_sparkline(self, service: str) -> list[int]:
        """Dapatkan sparkline 60-sample untuk satu service."""
        return list(self._sparklines.get(service, []))

    def get_idle_count(self) -> int:
        """Hitung service yang sedang idle."""
        return sum(1 for a in self._cache.values() if a.status == "idle")

    def get_busy_count(self) -> int:
        """Hitung service yang sedang busy."""
        return sum(1 for a in self._cache.values() if a.status == "busy")

    def get_error_count(self) -> int:
        """Hitung service yang error."""
        return sum(1 for a in self._cache.values() if a.status == "error")

    # ── Internal ────────────────────────────────────────────────────────

    def _update(self, event: VyperEvent) -> None:
        """Update state cache + sparkline dari service.activity event."""
        svc = event.service
        payload = event.payload

        activity = ServiceActivity(
            status=payload.get("status", "unknown"),
            task=payload.get("task", ""),
            progress=payload.get("progress"),
            started_at=payload.get("started_at"),
            trace_id=event.trace_id,
            sub_tasks=payload.get("sub_tasks", []),
            updated_at=datetime.now(),
        )
        self._cache[svc] = activity

        # Update sparkline
        cpu_proxy = CPU_PROXY_MAP.get(activity.status, 0)
        self._sparklines.setdefault(svc, deque(maxlen=self.SPARKLINE_WINDOW))
        self._sparklines[svc].append(cpu_proxy)

        # Sync ke AppState
        AppState.update(
            service_activities={**AppState.get().service_activities, svc: activity},
            service_sparklines={
                **AppState.get().service_sparklines,
                svc: list(self._sparklines[svc]),
            },
        )

        logger.debug(
            "Activity updated: %s → %s (task: %s)",
            svc,
            activity.status,
            activity.task[:40],
        )

    def _update_health(self, event: VyperEvent) -> None:
        """Update health status dari service.health event."""
        svc = event.service
        healthy = event.payload.get("healthy", None)

        AppState.update(
            service_health={
                **AppState.get().service_health,
                svc: healthy,
            }
        )

        logger.debug("Health updated: %s → %s", svc, healthy)
