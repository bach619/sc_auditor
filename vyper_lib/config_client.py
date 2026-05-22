"""Config Client — HTTP client for Vyper Config Service."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("vyper_lib.config_client")

CONFIG_URL = "http://01-config:8000"

# ── Shared HTTP Client (connection pooling) ────────────────

_SHARED_CLIENT: httpx.AsyncClient | None = None


def _get_shared_client() -> httpx.AsyncClient:
    """Return a shared httpx client with connection pooling."""
    global _SHARED_CLIENT
    if _SHARED_CLIENT is None:
        _SHARED_CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=50),
        )
    return _SHARED_CLIENT


class ConfigClient:
    """HTTP client to fetch config from Config Service.
    Uses a shared httpx.AsyncClient for connection pooling.
    """

    def __init__(self, base_url: str = CONFIG_URL):
        self.base_url = base_url

    async def get_config(self, key: str, default: Any = None) -> Any:
        """Get a config value by key."""
        client = _get_shared_client()
        try:
            resp = await client.get(f"{self.base_url}/config/{key}")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", {}).get(key, default)
        except httpx.RequestError as e:
            logger.warning("config_unreachable", key=key, error=str(e))
        return default

    async def get_all(self) -> dict:
        """Get all config."""
        client = _get_shared_client()
        try:
            resp = await client.get(f"{self.base_url}/config/")
            if resp.status_code == 200:
                return resp.json()
        except httpx.RequestError:
            pass
        return {}
