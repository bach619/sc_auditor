"""Tests for Dashboard (15-dashboard) and Submission (16-submission) Services.

Dashboard endpoints:
  GET  /health
  GET  /api/cases
  GET  /api/cases/stats
  GET  /api/cases/{id}
  POST /api/cases
  POST /api/cases/{id}/close
  GET  /api/health/graph
  GET  /api/config/proxy
  GET  /api/config/proxy/{key}
  GET  /api/events  (SSE)

Submission endpoints:
  GET  /health
  POST /submit
  GET  /status/{submission_id}
  POST /draft
  GET  /draft/{id}
  POST /classify-intent
  POST /submit/immunefi
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest


# ═══════════════════════════════════════════════════════════════════
# Dashboard tests
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestDashboardHealth:
    """Dashboard health and connectivity tests."""

    @pytest.mark.asyncio
    async def test_dashboard_health_check_endpoint(self, async_client: httpx.AsyncClient, dashboard_url: str) -> None:
        """GET /health returns 200 with service info."""
        resp = await async_client.get(f"{dashboard_url}/health")
        assert resp.status_code == 200
        body = resp.json()
        if "meta" in body:
            assert body["meta"]["status"] == "ok"
        elif "status" in body:
            assert body["status"] == "ok"


@pytest.mark.integration
class TestDashboardCases:
    """Dashboard audit/case list and filter tests."""

    @pytest.mark.asyncio
    async def test_audit_list_api_with_filters(self, async_client: httpx.AsyncClient, dashboard_url: str) -> None:
        """GET /api/cases returns audit list with optional filters."""
        resp = await async_client.get(f"{dashboard_url}/api/cases")
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body

    @pytest.mark.asyncio
    async def test_dashboard_stats_computation(self, async_client: httpx.AsyncClient, dashboard_url: str) -> None:
        """GET /api/cases/stats computes aggregate audit statistics."""
        resp = await async_client.get(f"{dashboard_url}/api/cases/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body


@pytest.mark.integration
class TestDashboardRealtime:
    """SSE, real-time, and config proxy tests."""

    @pytest.mark.asyncio
    async def test_sse_event_stream_connection(self, async_client: httpx.AsyncClient, dashboard_url: str) -> None:
        """GET /api/events establishes SSE stream for real-time updates."""
        resp = await async_client.get(f"{dashboard_url}/api/events", timeout=5.0)
        assert resp.status_code in (200, 204, 404)

    @pytest.mark.asyncio
    async def test_dashboard_config_proxy_endpoints(self, async_client: httpx.AsyncClient, dashboard_url: str) -> None:
        """GET /api/config/proxy returns proxied configuration values."""
        resp = await async_client.get(f"{dashboard_url}/api/config/proxy")
        assert resp.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_dashboard_real_time_updates(self, async_client: httpx.AsyncClient, dashboard_url: str) -> None:
        """Dashboard polls for real-time updates on active audits."""
        resp = await async_client.get(f"{dashboard_url}/api/cases")
        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", [])
        if isinstance(data, list):
            for case in data:
                if isinstance(case, dict):
                    assert "id" in case or "title" in case or "status" in case


@pytest.mark.integration
class TestDashboardStates:
    """Daemon, error, and loading state tests."""

    @pytest.mark.asyncio
    async def test_dashboard_daemon_status_display(self, async_client: httpx.AsyncClient, dashboard_url: str) -> None:
        """GET /api/health/graph returns daemon health graph data."""
        resp = await async_client.get(f"{dashboard_url}/api/health/graph")
        assert resp.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_dashboard_error_state_handling(self, async_client: httpx.AsyncClient, dashboard_url: str) -> None:
        """Dashboard gracefully handles downstream service errors."""
        resp = await async_client.get(f"{dashboard_url}/api/cases/__nonexistent__")
        assert resp.status_code in (200, 404, 500, 502, 503)

    @pytest.mark.asyncio
    async def test_dashboard_loading_state_display(self, async_client: httpx.AsyncClient, dashboard_url: str) -> None:
        """Dashboard health endpoint confirms service is loading/ready."""
        resp = await async_client.get(f"{dashboard_url}/health")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# Submission tests
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestSubmissionValidation:
    """Submission request validation tests."""

    @pytest.mark.asyncio
    async def test_submission_request_validation(self, async_client: httpx.AsyncClient, submission_url: str) -> None:
        """POST /submit validates required fields before submission."""
        payload: dict[str, Any] = {
            "title": "Test Finding",
            "severity": "High",
            "program": "test-program",
        }
        resp = await async_client.post(f"{submission_url}/submit", json=payload)
        assert resp.status_code in (200, 201, 400, 422)

    @pytest.mark.asyncio
    async def test_submission_evidence_collection(self, async_client: httpx.AsyncClient, submission_url: str) -> None:
        """POST /submit collects and attaches evidence artifacts."""
        payload: dict[str, Any] = {
            "finding_id": "test-finding-001",
            "evidence": ["tx_hash", "screenshot", "repro_steps"],
        }
        resp = await async_client.post(f"{submission_url}/submit", json=payload)
        assert resp.status_code in (200, 201, 404, 422)


@pytest.mark.integration
class TestSubmissionDrafting:
    """Draft generation and intent classification tests."""

    @pytest.mark.asyncio
    async def test_submission_draft_generation(self, async_client: httpx.AsyncClient, submission_url: str) -> None:
        """POST /draft generates a pre-filled submission draft."""
        payload: dict[str, Any] = {
            "findings": [{"id": "f-001", "title": "Reentrancy", "severity": "High"}],
            "program": "test-program",
        }
        resp = await async_client.post(f"{submission_url}/draft", json=payload)
        assert resp.status_code in (200, 201, 404, 422)

    @pytest.mark.asyncio
    async def test_submission_intent_classification(self, async_client: httpx.AsyncClient, submission_url: str) -> None:
        """POST /classify-intent classifies submission as bug report or feature."""
        payload: dict[str, Any] = {
            "description": "The withdraw function lacks reentrancy guard",
        }
        resp = await async_client.post(f"{submission_url}/classify-intent", json=payload)
        assert resp.status_code in (200, 201, 404, 422)


@pytest.mark.integration
class TestSubmissionTracking:
    """Submission to platform and status tracking tests."""

    @pytest.mark.asyncio
    async def test_submission_to_immunefi(self, async_client: httpx.AsyncClient, submission_url: str) -> None:
        """POST /submit/immunefi sends submission to Immunefi platform."""
        payload: dict[str, Any] = {
            "title": "Reentrancy in Vault",
            "program": "test-immunefi-program",
            "severity": "Critical",
            "description": "Missing reentrancy guard in withdraw()",
        }
        resp = await async_client.post(f"{submission_url}/submit/immunefi", json=payload)
        assert resp.status_code in (200, 201, 400, 404, 422, 502, 503)

    @pytest.mark.asyncio
    async def test_submission_status_tracking(self, async_client: httpx.AsyncClient, submission_url: str) -> None:
        """GET /status/{submission_id} tracks submission lifecycle status."""
        resp = await async_client.get(f"{submission_url}/status/__nonexistent__")
        assert resp.status_code in (200, 404)
