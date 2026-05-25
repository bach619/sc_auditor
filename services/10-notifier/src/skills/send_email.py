"""SendEmailSkill — Send email notification."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class SendEmailSkill(BaseSkill):
    """Send notification via email."""

    name = "send_email"
    description = "Send an email notification about audit results or alerts"
    category = "notification"

    parameters = {
        "subject": {"type": "string", "required": True, "description": "Email subject"},
        "body": {"type": "string", "required": True, "description": "Email body (plain text or HTML)"},
        "recipient": {"type": "string", "required": False, "description": "Override recipient email"},
    }

    def __init__(self, email_notifier: Any) -> None:
        super().__init__()
        self._notifier = email_notifier

    async def run(
        self, subject: str, body: str, recipient: str | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        result = await self._notifier.send(
            subject=subject,
            body=body,
            to_email=recipient,
        )
        return {"channel": "email", "success": result.success, "subject": subject}
