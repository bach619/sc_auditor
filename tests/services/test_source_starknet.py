"""Tests for StarkNet Source Service (22-source-starknet).

Endpoints:
  GET /health
  POST /fetch
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.integration
class TestStarkNetSourceHealth:
    """Health endpoint tests."""

    @pytest.mark.asyncio
    async def test_health(
        self, async_client: httpx.AsyncClient, source_starknet_url: str
    ) -> None:
        """GET /health returns 200."""
        resp = await async_client.get(f"{source_starknet_url}/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"


@pytest.mark.integration
class TestStarkNetSourceFetch:
    """Fetch endpoint tests."""

    @pytest.mark.asyncio
    async def test_fetch_requires_payload(
        self, async_client: httpx.AsyncClient, source_starknet_url: str
    ) -> None:
        """POST /fetch without payload returns 422 (validation error)."""
        resp = await async_client.post(f"{source_starknet_url}/fetch", json={})
        assert resp.status_code in (422, 400)
