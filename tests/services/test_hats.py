"""Tests for Hats Finance Service (21-hats).

Endpoints:
  GET /health
  POST /sync
  GET /bounties
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.integration
class TestHatsHealth:
    """Health endpoint tests."""

    @pytest.mark.asyncio
    async def test_health(
        self, async_client: httpx.AsyncClient, hats_url: str
    ) -> None:
        """GET /health returns 200."""
        resp = await async_client.get(f"{hats_url}/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"


@pytest.mark.integration
class TestHatsEndpoints:
    """Hats Finance API endpoints."""

    @pytest.mark.asyncio
    async def test_bounties(
        self, async_client: httpx.AsyncClient, hats_url: str
    ) -> None:
        """GET /bounties returns bounty list."""
        resp = await async_client.get(f"{hats_url}/bounties")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"
