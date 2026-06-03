"""Skill: Send notifications via Discord, Telegram, Email, or Desktop."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.skills.base import BaseSkill

log = structlog.get_logger()

NOTIFIER_URL = "http://10-notifier:8000"


class NotifySkill(BaseSkill):
    """Mengirim notifikasi — Discord, Telegram, Email, Desktop toast."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client

    @property
    def name(self) -> str:
        return "notify"

    @property
    def description(self) -> str:
        return (
            "Mengirim notifikasi ke berbagai channel: Discord webhook, "
            "Telegram bot, Email SMTP, atau Desktop notification. "
            "Mendukung level severity dan format rich embed untuk Discord."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "channel": {
                "type": "string",
                "description": "Channel: 'discord', 'telegram', 'email', 'desktop', atau 'all'",
                "required": True,
            },
            "title": {
                "type": "string",
                "description": "Judul notifikasi",
                "required": True,
            },
            "message": {
                "type": "string",
                "description": "Isi notifikasi",
                "required": True,
            },
            "severity": {
                "type": "string",
                "description": "Severity: critical, high, medium, low, info",
                "required": False,
            },
            "metadata": {
                "type": "object",
                "description": "Data tambahan (finding IDs, contract address, dll)",
                "required": False,
            },
        }

    async def run(self, **kwargs: Any) -> Any:
        body = {
            "channel": kwargs.get("channel", "discord"),
            "title": kwargs.get("title", "Antonio Notification"),
            "message": kwargs.get("message", ""),
            "severity": kwargs.get("severity", "info"),
            "metadata": kwargs.get("metadata", {}),
        }

        resp = await self._client.post(f"{NOTIFIER_URL}/notify", json=body)
        resp.raise_for_status()
        data = resp.json()

        return {
            "sent": data.get("data", {}).get("delivered", False),
            "channel": body["channel"],
            "result": data.get("data", {}),
        }
