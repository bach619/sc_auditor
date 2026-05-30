"""
VYPER TUI v2 — Activity Models

ServiceActivity: dataclass untuk state cache aktivitas tiap service.
Digunakan oleh ActivityMonitorV2 dan semua LayerPanel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class ServiceActivity:
    """State aktivitas satu service pada satu titik waktu."""

    status: Literal["idle", "busy", "pending", "error", "unknown"] = "unknown"
    task: str = ""
    progress: int | None = None          # 0-100 jika service mendukung
    started_at: str | None = None        # ISO 8601
    trace_id: str | None = None          # link ke distributed trace
    p95_latency_ms: float | None = None  # dari Prometheus jika tersedia
    updated_at: datetime = field(default_factory=datetime.now)

    # Detail opsional dari service yang support /activity?detail=true
    sub_tasks: list[dict] = field(default_factory=list)

    @property
    def is_busy(self) -> bool:
        return self.status == "busy"

    @property
    def is_error(self) -> bool:
        return self.status == "error"

    @property
    def short_task(self, max_len: int = 28) -> str:
        """Task description yang dipotong untuk tampilan panel."""
        if not self.task:
            return ""
        if len(self.task) <= max_len:
            return self.task
        return self.task[: max_len - 3] + "..."
