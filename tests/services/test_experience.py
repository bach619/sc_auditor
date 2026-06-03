"""Tests for Experience Service (17-experience).

Endpoints:
  GET /health
  POST /learn
  GET /stats
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.integration
class TestExperienceHealth:
    """Health endpoint tests."""

    @pytest.mark.asyncio
    async def test_health(
        self, async_client: httpx.AsyncClient, experience_url: str
    ) -> None:
        """GET /health returns 200."""
        resp = await async_client.get(f"{experience_url}/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"


@pytest.mark.integration
class TestExperienceEndpoints:
    """Experience API endpoints."""

    @pytest.mark.asyncio
    async def test_stats(
        self, async_client: httpx.AsyncClient, experience_url: str
    ) -> None:
        """GET /stats returns experience statistics."""
        resp = await async_client.get(f"{experience_url}/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"
