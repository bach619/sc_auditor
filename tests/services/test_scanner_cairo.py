"""Tests for Cairo Scanner Service (23-scanner-cairo).

Endpoints:
  GET /health
  POST /scan
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.integration
class TestScannerCairoHealth:
    """Health endpoint tests."""

    @pytest.mark.asyncio
    async def test_health(
        self, async_client: httpx.AsyncClient, scanner_cairo_url: str
    ) -> None:
        """GET /health returns 200."""
        resp = await async_client.get(f"{scanner_cairo_url}/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"


@pytest.mark.integration
class TestScannerCairoScan:
    """Scan endpoint tests."""

    @pytest.mark.asyncio
    async def test_scan_requires_payload(
        self, async_client: httpx.AsyncClient, scanner_cairo_url: str
    ) -> None:
        """POST /scan without payload returns 422 (validation error)."""
        resp = await async_client.post(f"{scanner_cairo_url}/scan", json={})
        assert resp.status_code in (422, 400)
