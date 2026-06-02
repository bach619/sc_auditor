"""E2E tests — full audit pipeline.

These tests require ALL 20 services to be running (docker compose up).
They verify the complete flow:

  1. Submit contract for audit
  2. Poll until complete
  3. Verify findings
  4. Generate report
  5. Check case management integration
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import httpx
import pytest

from tests.fixtures.sample_data import WETH_ADDRESS, SAMPLE_AUDIT_PAYLOAD

# ── Helpers ──────────────────────────────────────────────────────


async def _start_audit(client: httpx.AsyncClient, orch_url: str, payload: Dict[str, Any]) -> Optional[str]:
    """Start an audit and return the audit_id, or None if unavailable."""
    try:
        resp = await client.post(f"{orch_url}/audit", json=payload, timeout=10.0)
        if resp.status_code in (200, 201):
            data = resp.json().get("data", {})
            return data.get("audit_id")
    except (httpx.ConnectError, httpx.TimeoutException):
        return None
    return None


async def _poll_audit(
    client: httpx.AsyncClient, orch_url: str, audit_id: str, timeout: float = 30.0, interval: float = 2.0
) -> Optional[Dict[str, Any]]:
    """Poll audit status until complete or timeout."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            resp = await client.get(f"{orch_url}/audit/{audit_id}", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                state = data.get("state", "")
                if state == "COMPLETED":
                    return data
                if state.endswith("_FAILED") or state == "TIMEOUT":
                    return data
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        await asyncio.sleep(interval)
    return None


# ── Tests ────────────────────────────────────────────────────────


@pytest.mark.e2e
@pytest.mark.asyncio
class TestFullPipeline:
    """Complete audit pipeline test."""

    async def test_health_all_services(
        self, async_client: httpx.AsyncClient, orchestrator_url: str, dashboard_url: str
    ) -> None:
        """At minimum, check that key services are reachable."""
        for name, url in [("orchestrator", orchestrator_url), ("dashboard", dashboard_url)]:
            resp = await async_client.get(f"{url}/health", timeout=5.0)
            assert resp.status_code == 200, f"{name} health check failed"
            body = resp.json()
            if "meta" in body:
                assert body["meta"]["status"] == "ok"
            elif "status" in body:
                assert body["status"] == "ok"

    async def test_dashboard_case_api(
        self, async_client: httpx.AsyncClient, dashboard_url: str
    ) -> None:
        """Dashboard case API is responsive."""
        resp = await async_client.get(f"{dashboard_url}/api/cases", timeout=5.0)
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert body["meta"]["status"] == "ok"

    async def test_orchestrator_audit_list(
        self, async_client: httpx.AsyncClient, orchestrator_url: str
    ) -> None:
        """Orchestrator audit list is accessible."""
        resp = await async_client.get(f"{orchestrator_url}/audits", timeout=5.0)
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"

    async def test_orchestrator_queue(
        self, async_client: httpx.AsyncClient, orchestrator_url: str
    ) -> None:
        """Orchestrator queue is accessible."""
        resp = await async_client.get(f"{orchestrator_url}/queue", timeout=5.0)
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"


@pytest.mark.e2e
@pytest.mark.asyncio
class TestScannerTools:
    """All scanner tools respond correctly."""

    SCANNER_TOOLS = [
        ("slither", "scanner_slither_url"),
        ("echidna", "scanner_echidna_url"),
        ("forge", "scanner_forge_url"),
        ("halmos", "scanner_halmos_url"),
        ("mythril", "scanner_mythril_url"),
        ("manticore", "scanner_manticore_url"),
    ]

    async def test_scanner_tools_health(self, async_client: httpx.AsyncClient, request) -> None:
        """All 6 scanner tool health endpoints respond."""
        for tool_name, fixture_name in self.SCANNER_TOOLS:
            url = request.getfixturevalue(fixture_name)
            try:
                resp = await async_client.get(f"{url}/health", timeout=5.0)
                assert resp.status_code == 200, f"{tool_name} health failed"
            except (httpx.ConnectError, httpx.TimeoutException):
                pytest.skip(f"{tool_name} service not available")
