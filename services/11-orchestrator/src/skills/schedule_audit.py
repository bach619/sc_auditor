"""ScheduleAuditSkill — Schedule recurring audits."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class ScheduleAuditSkill(BaseSkill):
    name = "schedule_audit"
    description = "Schedule recurring audits for a contract or program"
    category = "orchestration"

    parameters = {
        "address": {"type": "string", "required": True, "description": "Contract address"},
        "chain": {"type": "string", "required": True, "description": "Blockchain network"},
        "interval_hours": {"type": "integer", "required": True, "description": "Interval in hours"},
    }

    def __init__(self, daemon: Any) -> None:
        super().__init__()
        self._daemon = daemon

    async def run(
        self, address: str, chain: str, interval_hours: int, **kwargs: Any
    ) -> dict[str, Any]:
        await self._daemon.schedule(
            address=address,
            chain=chain,
            interval_hours=interval_hours,
        )
        return {"scheduled": True, "address": address, "interval_hours": interval_hours}
