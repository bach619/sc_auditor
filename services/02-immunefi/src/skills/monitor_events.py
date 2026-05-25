"""MonitorEventsSkill — On-chain event monitoring for programs."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class MonitorEventsSkill(BaseSkill):
    """Monitor on-chain events for a program's contracts."""

    name = "monitor_events"
    description = "Monitor and fetch on-chain events for program contracts"
    category = "monitoring"

    parameters = {
        "slug": {"type": "string", "required": False, "description": "Program slug to monitor"},
        "since_hours": {"type": "integer", "required": False, "description": "Fetch events from last N hours"},
    }

    def __init__(self, onchain_service: Any) -> None:
        super().__init__()
        self._onchain = onchain_service

    async def run(
        self, slug: str | None = None, since_hours: int = 24, **kwargs: Any
    ) -> dict[str, Any]:
        if slug:
            events = await self._onchain.get_events(slug, hours=since_hours)
        else:
            events = await self._onchain.get_all_events(hours=since_hours)

        return {
            "program_slug": slug or "all",
            "events": events if isinstance(events, list) else [],
            "since_hours": since_hours,
        }
