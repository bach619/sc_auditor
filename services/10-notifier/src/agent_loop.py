"""NotifierAgent — Backend Agent for multi-channel notifications with skill registry.

Receives delegations from Antonio, routes to registered skills:
- send_email — email notifications
- send_telegram — Telegram bot messages
- send_discord — Discord webhook embeds
- send_channel — route to specific/all channels
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

from .skills import (
    SendChannelSkill,
    SendDiscordSkill,
    SendEmailSkill,
    SendTelegramSkill,
)


class NotifierAgent(BaseAgent):
    """Backend Agent for multi-channel notifications."""

    def __init__(
        self,
        email_notifier: Any,
        telegram_notifier: Any,
        discord_notifier: Any,
        notifier_service: Any,
    ) -> None:
        self.skill_registry = SkillRegistry()
        self.skill_registry.register(SendEmailSkill(email_notifier))
        self.skill_registry.register(SendTelegramSkill(telegram_notifier))
        self.skill_registry.register(SendDiscordSkill(discord_notifier))
        self.skill_registry.register(SendChannelSkill(notifier_service))

        super().__init__(
            service_name="10-notifier",
            agent_role="notification_dispatcher",
            version="0.2.0",
            skill_registry=self.skill_registry,
        )
        self._max_concurrent = 10

        self.register_capability(CapabilityDefinition(
            name=AgentCapability.SEND_NOTIFICATION,
            description="Send notifications via configured channels (email, telegram, discord)",
            input_schema={},
            output_schema={},
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        input_data = request.input_data
        channel = input_data.get("channel", "all")

        if channel == "email" or channel == "all":
            result = await self.skill_registry.execute(
                "send_email",
                subject=input_data.get("subject", "Audit Notification"),
                body=input_data.get("message", ""),
                recipient=input_data.get("recipient"),
            )
            if result.success:
                return result.output

        if channel == "telegram" or channel == "all":
            result = await self.skill_registry.execute(
                "send_telegram",
                message=input_data.get("message", ""),
            )
            if result.success:
                return result.output

        if channel == "discord" or channel == "all":
            result = await self.skill_registry.execute(
                "send_discord",
                title=input_data.get("title", "Audit Alert"),
                description=input_data.get("message", ""),
            )
            if result.success:
                return result.output

        result = await self.skill_registry.execute(
            "send_channel",
            message=input_data.get("message", ""),
            channel=channel,
            subject=input_data.get("subject"),
            title=input_data.get("title"),
        )
        return result.output if result.success else {"error": result.error}
