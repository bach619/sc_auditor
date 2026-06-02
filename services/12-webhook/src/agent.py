"""WebhookAgent — Backend Agent for webhook event management.

Receives delegations from Antonio, delivers webhook notifications
for audit events.
"""

from __future__ import annotations

from typing import Any

from shared.agent_protocol.base_agent import BaseAgent
from shared.agent_protocol.models import (
    AgentCapability,
    CapabilityDefinition,
    DelegationRequest,
)
from shared.skills.skill_registry import SkillRegistry

from .dispatcher import WebhookDispatcher
from .skills import create_registry


class WebhookAgent(BaseAgent):
    """Backend Agent for webhook delivery."""

    def __init__(self, dispatcher: WebhookDispatcher) -> None:
        self._dispatcher = dispatcher
        self.skill_registry = create_registry()
        super().__init__(
            service_name="12-webhook",
            agent_role="webhook_manager",
            version="0.1.0",
            skill_registry=self.skill_registry,
        )
        self._max_concurrent = 5

        self.register_capability(CapabilityDefinition(
            name=AgentCapability.MANAGE_WEBHOOK,
            description="Deliver webhook notifications and manage webhook endpoints",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "Action: deliver, list_logs, get_endpoints"},
                    "event_type": {"type": "string"},
                    "payload": {"type": "object"},
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

        if capability == AgentCapability.MANAGE_WEBHOOK:
            action = data.get("action", "deliver")
            if action == "deliver":
                event_type = data.get("event_type", "audit.completed")
                payload = data.get("payload", {})
                result = await self._dispatcher.dispatch(event_type, payload)
                return {"result": result}
            elif action == "list_logs":
                logs = self._dispatcher.read_delivery_log()
                return {"logs": logs[-50:]}
            else:
                raise ValueError(f"Unknown action: {action}")
        else:
            raise ValueError(f"Unknown capability: {capability}")
