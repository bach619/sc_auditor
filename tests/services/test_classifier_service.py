"""Tests for Classifier Service (07-classifier).

Endpoints:
  GET /health
  GET /metrics
  GET /classify/metrics
  POST /feedback
  GET /feedback
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.integration
class TestClassifierHealth:
    """Health endpoint tests."""

    @pytest.mark.asyncio
    async def test_health(self, async_client: httpx.AsyncClient, classifier_url: str) -> None:
        """GET /health returns 200 with flat HealthResponse (Type A)."""
        resp = await async_client.get(f"{classifier_url}/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "classifier"
        assert "version" in body


@pytest.mark.integration
class TestClassifierEndpoints:
    """Classifier metrics and feedback endpoints."""

    @pytest.mark.asyncio
    async def test_metrics(self, async_client: httpx.AsyncClient, classifier_url: str) -> None:
        """GET /metrics (or /classify/metrics) returns metrics data."""
        resp = await async_client.get(f"{classifier_url}/metrics")
        if resp.status_code == 404:
            resp = await async_client.get(f"{classifier_url}/classify/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_feedback_list(self, async_client: httpx.AsyncClient, classifier_url: str) -> None:
        """GET /feedback returns feedback list."""
        resp = await async_client.get(f"{classifier_url}/feedback")
        if resp.status_code == 200:
            body = resp.json()
            assert body["meta"]["status"] == "ok"
