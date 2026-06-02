"""DeliverWebhookSkill — send webhook notifications."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class DeliverWebhookSkill(BaseSkill):
    """Deliver webhook notifications for audit events."""

    @property
    def name(self) -> str:
        return "deliver_webhook"

    @property
    def description(self) -> str:
        return (
            "Send webhook notifications to registered endpoints "
            "for audit events such as scan completion, finding detected, "
            "or classification finished."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "event_type": {
                    "type": "string",
                    "description": "Event type (e.g. audit.completed, finding.detected)",
                },
                "payload": {
                    "type": "object",
                    "description": "Event payload data",
                },
                "endpoint_url": {
                    "type": "string",
                    "description": "Specific endpoint URL (optional, uses registered endpoints otherwise)",
                },
            },
            "required": ["event_type", "payload"],
        }

    @property
    def category(self) -> str:
        return "notifications"

    async def run(
        self,
        event_type: str,
        payload: dict[str, Any],
        endpoint_url: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        from ..dispatcher import WebhookDispatcher

        dispatcher = WebhookDispatcher()
        result = await dispatcher.dispatch(event_type, payload, endpoint=endpoint_url)

        return {
            "skill": "deliver_webhook",
            "event_type": event_type,
            "delivered": result.get("success", False),
            "endpoints_contacted": result.get("endpoints_count", 0),
            "responses": result.get("responses", []),
            "errors": result.get("errors", []),
        }
