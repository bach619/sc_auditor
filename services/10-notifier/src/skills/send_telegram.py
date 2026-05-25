"""SendTelegramSkill — Send Telegram notification."""

from __future__ import annotations

import os
from typing import Any

from shared.skills.base_skill import BaseSkill


class SendTelegramSkill(BaseSkill):
    """Send notification via Telegram bot."""

    name = "send_telegram"
    description = "Send a Telegram message with audit alerts or results"
    category = "notification"

    parameters = {
        "message": {"type": "string", "required": True, "description": "Message text"},
        "parse_mode": {"type": "string", "required": False, "description": "Parse mode: Markdown or HTML"},
    }

    def __init__(self, telegram_notifier: Any) -> None:
        super().__init__()
        self._notifier = telegram_notifier

    async def run(
        self, message: str, parse_mode: str = "Markdown", **kwargs: Any
    ) -> dict[str, Any]:
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        result = await self._notifier.send_simple(text=message, chat_id=chat_id)
        return {"channel": "telegram", "success": result.success}
