"""Tests for Code4rena Service (18-code4rena).

Endpoints:
  GET /health
  POST /sync
  GET /contests
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.integration
class TestCode4renaHealth:
    """Health endpoint tests."""

    @pytest.mark.asyncio
    async def test_health(
        self, async_client: httpx.AsyncClient, code4rena_url: str
    ) -> None:
        """GET /health returns 200."""
        resp = await async_client.get(f"{code4rena_url}/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"


@pytest.mark.integration
class TestCode4renaEndpoints:
    """Code4rena API endpoints."""

    @pytest.mark.asyncio
    async def test_contests(
        self, async_client: httpx.AsyncClient, code4rena_url: str
    ) -> None:
        """GET /contests returns contest list."""
        resp = await async_client.get(f"{code4rena_url}/contests")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"
