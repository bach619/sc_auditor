"""ManageQueueSkill — Manage priority queue."""

from __future__ import annotations

from typing import Any
from shared.skills.base_skill import BaseSkill


class ManageQueueSkill(BaseSkill):
    name = "manage_queue"
    description = "Add contracts to priority queue or view current queue status"
    category = "orchestration"

    parameters = {
        "action": {"type": "string", "required": True, "description": "Action: add, list, or clear"},
        "address": {"type": "string", "required": False, "description": "Contract address (for add action)"},
        "chain": {"type": "string", "required": False, "description": "Blockchain network (for add action)"},
        "priority": {"type": "integer", "required": False, "description": "Priority level 1-10"},
    }

    def __init__(self, priority_service: Any) -> None:
        super().__init__()
        self._priority = priority_service

    async def run(
        self,
        action: str,
        address: str | None = None,
        chain: str | None = None,
        priority: int = 5,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if action == "add" and address and chain:
            result = await self._priority.enqueue(address=address, chain=chain, priority=priority)
            return {"action": "added", "address": address, "chain": chain, "priority": priority}
        elif action == "list":
            queue = await self._priority.get_queue()
            return {"action": "listed", "queue": queue if isinstance(queue, list) else []}
        elif action == "clear":
            await self._priority.clear()
            return {"action": "cleared"}
        return {"error": f"Invalid action: {action}"}
