"""SendDiscordSkill — Send Discord webhook notification."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class SendDiscordSkill(BaseSkill):
    """Send notification via Discord webhook."""

    name = "send_discord"
    description = "Send a Discord embed message with audit findings or alerts"
    category = "notification"

    parameters = {
        "title": {"type": "string", "required": True, "description": "Embed title"},
        "description": {"type": "string", "required": True, "description": "Embed description"},
        "color": {"type": "integer", "required": False, "description": "Embed color hex (e.g. 0xff0000)"},
        "fields": {"type": "array", "required": False, "description": "Additional embed fields"},
    }

    def __init__(self, discord_notifier: Any) -> None:
        super().__init__()
        self._notifier = discord_notifier

    async def run(
        self,
        title: str,
        description: str,
        color: int | None = None,
        fields: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        result = await self._notifier.send_embed(
            title=title,
            description=description,
            color=color or 0x00ff00,
            fields=fields or [],
        )
        return {"channel": "discord", "success": result.success}
