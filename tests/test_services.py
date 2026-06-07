"""Integration tests — individual Vyper service health endpoints.

Each test verifies that the service is alive by hitting ``GET /health``
and checking the response indicates ``ok``.

Two health response styles exist across the fleet:

* **Type A — flat HealthResponse** (config, classifier)::

      {"status": "ok", "service": "...", "version": "...", "timestamp": "..."}

* **Type B — wrapped ApiResponse** (all other services)::

      {"data": {"status": "ok", "service": "...", ...},
       "meta": {"status": "ok", "timestamp": "..."}}
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _assert_health_ok(data: dict[str, Any], *, expected_service: str) -> None:
    """Assert a health response indicates a healthy service.

    Handles both flat and wrapped response styles transparently.
    """
    # Type A — flat HealthResponse (config, classifier)
    if "service" in data and "status" in data:
        assert data["status"] == "ok", f"{expected_service}: status not ok"
        assert data["service"] == expected_service, (
            f"{expected_service}: wrong service name"
        )
        assert "version" in data, f"{expected_service}: missing version"
        assert "timestamp" in data, f"{expected_service}: missing timestamp"
        return

    # Type B — wrapped ApiResponse
    assert "meta" in data, f"{expected_service}: missing meta envelope"
    assert data["meta"]["status"] == "ok", f"{expected_service}: meta status not ok"
    assert "timestamp" in data["meta"], f"{expected_service}: meta missing timestamp"

    inner = data.get("data")
    assert inner is not None, f"{expected_service}: data is None"
    assert "status" in inner, f"{expected_service}: inner missing status"
    assert inner["status"] == "ok", f"{expected_service}: inner status not ok"
    if "service" in inner:
        assert inner["service"] == expected_service, (
            f"{expected_service}: wrong service name"
        )


@pytest.mark.asyncio
async def _check_health(
    client: httpx.AsyncClient,
    url: str,
    service: str,
) -> dict[str, Any]:
    """Helper: hit /health and return parsed JSON."""
    resp = await client.get(f"{url}/health")
    assert resp.status_code == 200, (
        f"{service}: expected 200, got {resp.status_code}"
    )
    body: dict[str, Any] = resp.json()
    _assert_health_ok(body, expected_service=service)
    return body


# ═══════════════════════════════════════════════════════════════════
# Tests — one per service
# ═══════════════════════════════════════════════════════════════════


class TestHealthEndpoints:
    """All 12 Vyper microservice health endpoints."""

    @pytest.mark.asyncio
    async def test_config_health(
        self, async_client: httpx.AsyncClient, config_url: str
    ) -> None:
        """Config Service — Type A flat HealthResponse."""
        await _check_health(async_client, config_url, "config")

    @pytest.mark.asyncio
    async def test_immunefi_health(
        self, async_client: httpx.AsyncClient, immunefi_url: str
    ) -> None:
        """Immunefi Service — Type B wrapped ApiResponse."""
        await _check_health(async_client, immunefi_url, "immunefi")

    @pytest.mark.asyncio
    async def test_source_health(
        self, async_client: httpx.AsyncClient, source_url: str
    ) -> None:
        """Source Service — Type B wrapped."""
        await _check_health(async_client, source_url, "source")

    @pytest.mark.asyncio
    async def test_scanner_health(
        self, async_client: httpx.AsyncClient, scanner_url: str
    ) -> None:
        """Scanner Service (legacy monolith) — Type B wrapped."""
        await _check_health(async_client, scanner_url, "scanner")

    @pytest.mark.asyncio
    async def test_scanner_slither_health(
        self, async_client: httpx.AsyncClient, scanner_slither_url: str
    ) -> None:
        """Scanner Slither Service."""
        await _check_health(async_client, scanner_slither_url, "scanner-slither")

    @pytest.mark.asyncio
    async def test_scanner_echidna_health(
        self, async_client: httpx.AsyncClient, scanner_echidna_url: str
    ) -> None:
        """Scanner Echidna Service."""
        await _check_health(async_client, scanner_echidna_url, "scanner-echidna")

    @pytest.mark.asyncio
    async def test_scanner_forge_health(
        self, async_client: httpx.AsyncClient, scanner_forge_url: str
    ) -> None:
        """Scanner Forge Service."""
        await _check_health(async_client, scanner_forge_url, "scanner-forge")

    @pytest.mark.asyncio
    async def test_scanner_halmos_health(
        self, async_client: httpx.AsyncClient, scanner_halmos_url: str
    ) -> None:
        """Scanner Halmos Service."""
        await _check_health(async_client, scanner_halmos_url, "scanner-halmos")

    @pytest.mark.asyncio
    async def test_ai_health(
        self, async_client: httpx.AsyncClient, ai_url: str
    ) -> None:
        """AI Service — Type B wrapped."""
        await _check_health(async_client, ai_url, "ai")

    @pytest.mark.asyncio
    async def test_classifier_health(
        self, async_client: httpx.AsyncClient, classifier_url: str
    ) -> None:
        """Classifier Service — Type A flat HealthResponse."""
        await _check_health(async_client, classifier_url, "classifier")

    @pytest.mark.asyncio
    async def test_exploit_health(
        self, async_client: httpx.AsyncClient, exploit_url: str
    ) -> None:
        """Exploit Service — Type B wrapped."""
        await _check_health(async_client, exploit_url, "exploit")

    @pytest.mark.asyncio
    async def test_reporter_health(
        self, async_client: httpx.AsyncClient, reporter_url: str
    ) -> None:
        """Reporter Service — Type B wrapped."""
        await _check_health(async_client, reporter_url, "reporter")

    @pytest.mark.asyncio
    async def test_notifier_health(
        self, async_client: httpx.AsyncClient, notifier_url: str
    ) -> None:
        """Notifier Service — Type B wrapped."""
        await _check_health(async_client, notifier_url, "notifier")

    @pytest.mark.asyncio
    async def test_orchestrator_health(
        self, async_client: httpx.AsyncClient, orchestrator_url: str
    ) -> None:
        """Orchestrator Service — Type B wrapped with daemon/pipeline stats."""
        body = await _check_health(async_client, orchestrator_url, "orchestrator")
        # Orchestrator health has rich inner data
        if "data" in body and body["data"]:
            inner = body["data"]
            for field in ("daemon", "pipeline", "queue_size"):
                assert field in inner, f"orchestrator: missing {field}"

    @pytest.mark.asyncio
    async def test_webhook_health(
        self, async_client: httpx.AsyncClient, webhook_url: str
    ) -> None:
        """Webhook Service — Type B wrapped."""
        await _check_health(async_client, webhook_url, "webhook")

    @pytest.mark.asyncio
    async def test_upkeep_health(
        self, async_client: httpx.AsyncClient, upkeep_url: str
    ) -> None:
        """Upkeep Service — Type B wrapped."""
        await _check_health(async_client, upkeep_url, "upkeep")
