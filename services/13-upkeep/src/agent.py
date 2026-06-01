"""UpkeepAgent — Backend Agent for scheduler and platform maintenance.

Receives delegations from Antonio, manages scheduled tasks,
backups, and platform metrics.
"""

from __future__ import annotations

from typing import Any

from shared.agent_protocol.base_agent import BaseAgent
from shared.agent_protocol.models import (
    AgentCapability,
    CapabilityDefinition,
    DelegationRequest,
)

from .backup import BackupManager
from .metrics import MetricsAggregator
from .update import UpdateManager


class UpkeepAgent(BaseAgent):
    """Backend Agent for scheduler and maintenance tasks."""

    def __init__(
        self,
        update_mgr: UpdateManager,
        backup_mgr: BackupManager,
        metrics_mgr: MetricsAggregator,
    ) -> None:
        self._update_mgr = update_mgr
        self._backup_mgr = backup_mgr
        self._metrics_mgr = metrics_mgr
        super().__init__(
            service_name="13-upkeep",
            agent_role="platform_maintenance",
            version="0.1.0",
        )
        self._max_concurrent = 3

        self.register_capability(CapabilityDefinition(
            name=AgentCapability.SCHEDULE_TASKS,
            description="Manage scheduled tasks, backups, and platform metrics",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "Action: status, backup, metrics, update"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "result": {"type": "object"},
                },
            },
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        capability = request.capability
        data = request.input_data

        if capability == AgentCapability.SCHEDULE_TASKS:
            action = data.get("action", "status")
            if action == "status":
                return {
                    "uptime_seconds": self._update_mgr.uptime_seconds if hasattr(self._update_mgr, 'uptime_seconds') else 0,
                    "backup_count": len(self._backup_mgr.list_backups()) if hasattr(self._backup_mgr, 'list_backups') else 0,
                }
            elif action == "backup":
                result = await self._backup_mgr.create_backup()
                return {"backup": result}
            elif action == "metrics":
                metrics = await self._metrics_mgr.aggregate_all()
                return {"metrics": metrics}
            else:
                raise ValueError(f"Unknown action: {action}")
        else:
            raise ValueError(f"Unknown capability: {capability}")
