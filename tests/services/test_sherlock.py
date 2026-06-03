"""Tests for Sherlock Service (19-sherlock).

Endpoints:
  GET /health
  POST /sync
  GET /contests
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.integration
class TestSherlockHealth:
    """Health endpoint tests."""

    @pytest.mark.asyncio
    async def test_health(
        self, async_client: httpx.AsyncClient, sherlock_url: str
    ) -> None:
        """GET /health returns 200."""
        resp = await async_client.get(f"{sherlock_url}/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"


@pytest.mark.integration
class TestSherlockEndpoints:
    """Sherlock API endpoints."""

    @pytest.mark.asyncio
    async def test_contests(
        self, async_client: httpx.AsyncClient, sherlock_url: str
    ) -> None:
        """GET /contests returns contest list."""
        resp = await async_client.get(f"{sherlock_url}/contests")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"
