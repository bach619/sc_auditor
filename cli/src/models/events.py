"""
VYPER TUI v2 — Event Models

VyperEvent: struktur data standar untuk semua event yang
melewati EventBus dari SSE stream 15-Dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class VyperEvent:
    """
    Event standar dari SSE stream 15-Dashboard.

    Semua event type terdefinisi di arsitektur:
      service.activity / service.health / audit.state_change
      agent.thought / agent.skill_call / agent.observation
      resource.slot_change / metric.update / memory.stored
      daemon.cycle / audit.finding / audit.completed
      agent.delegation / agent.step
    """

    event_type: str                         # "service.activity" | "audit.state_change" ...
    service: str                            # "04-scanner" | "11-orchestrator" ...
    payload: dict                           # Data event — bervariasi per type
    timestamp: str = ""                     # ISO 8601 — diisi otomatis jika kosong
    trace_id: str | None = None             # OpenTelemetry trace ID
    source: str = "sse"                     # "sse" | "polling_fallback" | "internal"

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    @classmethod
    def from_sse_line(cls, raw_data: str) -> "VyperEvent":
        """
        Parse baris 'data: {...}' dari SSE stream menjadi VyperEvent.

        Args:
            raw_data: String JSON setelah prefix 'data: '

        Returns:
            VyperEvent instance

        Raises:
            json.JSONDecodeError jika format tidak valid
        """
        import json

        parsed = json.loads(raw_data)
        return cls(
            event_type=parsed.get("event_type", "unknown"),
            service=parsed.get("service", "unknown"),
            payload=parsed.get("payload", {}),
            timestamp=parsed.get("timestamp", ""),
            trace_id=parsed.get("trace_id"),
        )
