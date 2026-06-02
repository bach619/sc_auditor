"""ManageEndpointsSkill — manage webhook endpoints."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class ManageEndpointsSkill(BaseSkill):
    """Manage webhook endpoint registrations: add, remove, list, test."""

    @property
    def name(self) -> str:
        return "manage_endpoints"

    @property
    def description(self) -> str:
        return (
            "Manage registered webhook endpoints. Supports adding new endpoints, "
            "removing existing ones, listing all endpoints, and testing connectivity."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "add", "remove", "test"],
                    "description": "Action to perform",
                },
                "url": {
                    "type": "string",
                    "description": "Endpoint URL (required for add, remove, test)",
                },
                "events": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Event types to subscribe to (required for add)",
                },
                "secret": {
                    "type": "string",
                    "description": "HMAC secret for webhook signing (optional)",
                },
            },
            "required": ["action"],
        }

    @property
    def category(self) -> str:
        return "notifications"

    async def run(
        self,
        action: str,
        url: str | None = None,
        events: list[str] | None = None,
        secret: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        from ..dispatcher import WebhookDispatcher

        dispatcher = WebhookDispatcher()

        if action == "list":
            endpoints = dispatcher.list_endpoints() if hasattr(dispatcher, "list_endpoints") else []
            return {
                "skill": "manage_endpoints",
                "action": "list",
                "endpoints": endpoints,
                "total": len(endpoints),
            }

        elif action == "add":
            if not url:
                raise ValueError("url is required for add action")
            result = dispatcher.add_endpoint(url, events=events or [], secret=secret) if hasattr(dispatcher, "add_endpoint") else None
            return {
                "skill": "manage_endpoints",
                "action": "add",
                "url": url,
                "events": events or [],
                "success": result is not None if result is not None else True,
                "message": f"Endpoint {url} registered" if result or result is None else "Failed to register endpoint",
            }

        elif action == "remove":
            if not url:
                raise ValueError("url is required for remove action")
            removed = dispatcher.remove_endpoint(url) if hasattr(dispatcher, "remove_endpoint") else False
            return {
                "skill": "manage_endpoints",
                "action": "remove",
                "url": url,
                "success": removed,
                "message": f"Endpoint {url} removed" if removed else f"Endpoint {url} not found",
            }

        elif action == "test":
            if not url:
                raise ValueError("url is required for test action")
            import aiohttp
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json={"test": True, "timestamp": __import__("time").time()}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        status = resp.status
                        body = await resp.text()
                        return {
                            "skill": "manage_endpoints",
                            "action": "test",
                            "url": url,
                            "reachable": status < 500,
                            "status_code": status,
                            "response_body": body[:500],
                        }
            except Exception as exc:
                return {
                    "skill": "manage_endpoints",
                    "action": "test",
                    "url": url,
                    "reachable": False,
                    "error": str(exc),
                }
        else:
            raise ValueError(f"Unknown action: {action}")
