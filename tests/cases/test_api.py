"""Integration tests for Case Management API endpoints.

These tests require a running Dashboard service (15-dashboard).
They verify the API contract: request/response format, status codes.
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.integration
class TestCaseAPI:
    """Case Management API endpoint tests."""

    @pytest.mark.asyncio
    async def test_list_cases(self, async_client: httpx.AsyncClient, dashboard_url: str) -> None:
        """GET /api/cases returns case list with meta envelope."""
        resp = await async_client.get(f"{dashboard_url}/api/cases")
        assert resp.status_code == 200
        body = resp.json()
        assert "meta" in body
        assert body["meta"]["status"] == "ok"
        assert "data" in body

    @pytest.mark.asyncio
    async def test_case_stats(self, async_client: httpx.AsyncClient, dashboard_url: str) -> None:
        """GET /api/cases/stats returns statistics."""
        resp = await async_client.get(f"{dashboard_url}/api/cases/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"
        data = body.get("data", {})
        assert "open_cases" in data

    @pytest.mark.asyncio
    async def test_get_case_missing(self, async_client: httpx.AsyncClient, dashboard_url: str) -> None:
        """GET /api/cases/{id} with nonexistent ID returns 404."""
        resp = await async_client.get(f"{dashboard_url}/api/cases/CASE-99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_archive_list(self, async_client: httpx.AsyncClient, dashboard_url: str) -> None:
        """GET /api/cases/archive returns closed cases."""
        resp = await async_client.get(f"{dashboard_url}/api/cases/archive")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_create_case(self, async_client: httpx.AsyncClient, dashboard_url: str) -> None:
        """POST /api/cases creates a new case."""
        payload = {
            "project": "integration-test",
            "title": "Integration test case",
            "description": "Created by automated test",
            "severity": "Low",
            "contract": "TestContract",
            "function": "testFunc",
            "scanners": [{"name": "pytest", "detector": "pytest", "confidence": 0.5}],
            "recommendation": "Review and delete this test case.",
        }
        resp = await async_client.post(f"{dashboard_url}/api/cases", json=payload)
        # May be 200 or 201
        assert resp.status_code in (200, 201), f"Create case failed: {resp.status_code} {resp.text[:200]}"
        body = resp.json()
        assert "data" in body
