"""SendChannelSkill — Route notification to specific or all channels."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class SendChannelSkill(BaseSkill):
    """Send notification to a specific channel or all configured channels."""

    name = "send_channel"
    description = "Send notification to a specific channel (email, telegram, discord) or all channels"
    category = "notification"

    parameters = {
        "message": {"type": "string", "required": True, "description": "Notification message"},
        "channel": {
            "type": "string",
            "required": False,
            "description": "Target channel: email, telegram, discord, or all",
        },
        "subject": {"type": "string", "required": False, "description": "Email subject (if channel=email)"},
        "title": {"type": "string", "required": False, "description": "Discord embed title (if channel=discord)"},
    }

    def __init__(self, notifier_service: Any) -> None:
        super().__init__()
        self._notifier_service = notifier_service

    async def run(
        self,
        message: str,
        channel: str = "all",
        subject: str | None = None,
        title: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload = {
            "message": message,
            "channel": channel,
        }
        if subject:
            payload["subject"] = subject
        if title:
            payload["title"] = title

        results = await self._notifier_service.send_notification(**payload)
        return {
            "channel": channel,
            "results": results if isinstance(results, list) else [results],
        }
