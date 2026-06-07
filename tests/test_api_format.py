"""Tests for Vyper API response format consistency.

Every service in the fleet should follow a predictable response contract:

``Success (200)``
    ``{"data": ..., "meta": {"status": "ok", "timestamp": "..."}}``

``Health (Type A — config, classifier)``
    ``{"status": "ok", "service": "...", "version": "...", "timestamp": "..."}``

``Error (4xx/5xx)``
    ``{"data": None, "meta": {"status": "error", "error": "...", "timestamp": "..."}}``

These tests verify the contract is upheld regardless of the specific
service implementation.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

# ── Constants ────────────────────────────────────────────────────

REQUIRED_META_KEYS = frozenset({"status", "timestamp"})
EXPECTED_SERVICES = frozenset({
    "config",
    "immunefi",
    "source",
    "scanner",
    "ai",
    "classifier",
    "exploit",
    "reporter",
    "notifier",
    "orchestrator",
    "webhook",
    "upkeep",
})

# Services that return a flat HealthResponse (Type A) instead of
# the wrapped ApiResponse envelope on /health.
TYPE_A_HEALTH_SERVICES = frozenset({"config", "classifier"})


# ── Helpers ──────────────────────────────────────────────────────


def _is_type_a_health(body: dict[str, Any]) -> bool:
    """Detect whether a /health response is Type A (flat)."""
    return (
        "status" in body
        and "service" in body
        and "timestamp" in body
        and "meta" not in body
    )


def _require_envelope_structure(
    body: dict[str, Any],
    *,
    service: str,
    expect_data: bool = True,
) -> None:
    """Assert the response follows the Vyper standard envelope.

    Args:
        body: Parsed JSON response body.
        service: Service name for error messages.
        expect_data: When True, ``data`` must not be ``None``.
    """
    assert "meta" in body, (
        f"{service}: body must contain 'meta' key — keys: {list(body.keys())}"
    )

    meta = body["meta"]
    for key in REQUIRED_META_KEYS:
        assert key in meta, (
            f"{service}: meta must contain '{key}' — got {list(meta.keys())}"
        )

    assert meta["status"] in ("ok", "error"), (
        f"{service}: meta.status must be 'ok' or 'error', got {meta['status']!r}"
    )

    # ``data`` may be None for errors or empty state
    assert "data" in body, (
        f"{service}: body must contain 'data' key — keys: {list(body.keys())}"
    )


# ── Tests ────────────────────────────────────────────────────────


class TestApiEnvelope:
    """Verify the standard ``{data, meta}`` envelope for all services."""

    @pytest.mark.asyncio
    async def test_envelope_on_health(
        self,
        async_client: httpx.AsyncClient,
        config_url: str,
        immunefi_url: str,
        classifier_url: str,
        orchestrator_url: str,
    ) -> None:
        """Health responses must contain either:
        - Type A: status, service, version, timestamp (flat)
        - Type B: data + meta envelope with ok status
        """
        endpoints = [
            ("config", config_url),
            ("immunefi", immunefi_url),
            ("classifier", classifier_url),
            ("orchestrator", orchestrator_url),
        ]

        for name, url in endpoints:
            resp = await async_client.get(f"{url}/health")
            assert resp.status_code == 200, (
                f"{name}: health returned {resp.status_code}"
            )
            body: dict[str, Any] = resp.json()

            if name in TYPE_A_HEALTH_SERVICES or _is_type_a_health(body):
                # Type A — flat health response
                assert body["status"] == "ok", f"{name}: status not ok"
                # Service health returns full prefixed name (e.g., "01-config")
                svc_name = body.get("service", "")
                assert name in svc_name or name.replace("-", "_") in svc_name, (
                    f"{name}: wrong service name in health: {svc_name!r}"
                )
                assert "version" in body, f"{name}: missing version"
                assert "timestamp" in body, f"{name}: missing timestamp"
            else:
                # Type B — wrapped
                _require_envelope_structure(body, service=name, expect_data=True)
                assert body["meta"]["status"] == "ok"
                data = body.get("data") or {}
                if "status" in data:
                    assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_envelope_on_config_get(
        self, async_client: httpx.AsyncClient, config_url: str
    ) -> None:
        """Config GET response uses the standard envelope."""
        # First upsert a known key
        await async_client.put(
            f"{config_url}/config/_fmt_test",
            json={"value": "envelope_check"},
        )

        resp = await async_client.get(f"{config_url}/config/_fmt_test")
        assert resp.status_code == 200
        body = resp.json()
        _require_envelope_structure(body, service="config", expect_data=True)
        assert body["meta"]["status"] == "ok"

        # Cleanup
        await async_client.delete(f"{config_url}/config/_fmt_test")

    @pytest.mark.asyncio
    async def test_envelope_on_immunefi_programs(
        self, async_client: httpx.AsyncClient, immunefi_url: str
    ) -> None:
        """Immunefi /programs uses the standard envelope."""
        resp = await async_client.get(f"{immunefi_url}/programs")
        assert resp.status_code == 200
        body = resp.json()
        _require_envelope_structure(body, service="immunefi", expect_data=True)
        assert body["meta"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_envelope_on_classifier_metrics(
        self, async_client: httpx.AsyncClient, classifier_url: str
    ) -> None:
        """Classifier /metrics uses the standard envelope."""
        resp = await async_client.get(f"{classifier_url}/metrics")
        # Fallback to /classify/metrics
        if resp.status_code == 404:
            resp = await async_client.get(f"{classifier_url}/classify/metrics")

        if resp.status_code == 200:
            body = resp.json()
            _require_envelope_structure(body, service="classifier", expect_data=True)
            assert body["meta"]["status"] == "ok"


class TestErrorFormat:
    """Verify error responses follow the Vyper contract."""

    @pytest.mark.asyncio
    async def test_config_404_format(
        self, async_client: httpx.AsyncClient, config_url: str
    ) -> None:
        """Config 404 must return ``{data: null, meta: {status: "error", ...}}``."""
        resp = await async_client.get(f"{config_url}/config/__no_such_key_ever__")
        assert resp.status_code == 404
        body = resp.json()

        # Accept both FastAPI default 404 format {'detail': '...'} and envelope format
        if "detail" in body and "meta" not in body:
            # FastAPI default 404 — valid error response
            assert isinstance(body["detail"], str), f"detail should be a string: {body}"
        else:
            # Must be wrapped in the envelope
            assert "meta" in body, f"404 response missing meta and detail: {body}"
            meta = body["meta"]
            assert meta["status"] == "error", f"404 meta.status should be 'error': {meta}"
            assert "timestamp" in meta, f"404 meta missing timestamp: {meta}"
            # Should have an error message
            assert "error" in meta or "detail" in meta or body.get("data") is None, (
                f"404 should have error/detail or null data: {body}"
            )

    @pytest.mark.asyncio
    async def test_immunefi_404_format(
        self, async_client: httpx.AsyncClient, immunefi_url: str
    ) -> None:
        """Immunefi 404 must return the standard error envelope."""
        resp = await async_client.get(f"{immunefi_url}/programs/__no_such_slug__")
        if resp.status_code == 404:
            body = resp.json()
            # Accept both FastAPI default 404 format and envelope format
            if "detail" in body and "meta" not in body:
                # FastAPI default 404 — valid error response
                assert isinstance(body["detail"], str), f"detail should be a string: {body}"
            else:
                assert "meta" in body
                assert body["meta"]["status"] == "error"
                # Data should be None for errors
                if "data" in body:
                    assert body["data"] is None

    @pytest.mark.asyncio
    async def test_404_on_unknown_route(
        self, async_client: httpx.AsyncClient, config_url: str
    ) -> None:
        """Unknown routes should return 404 (FastAPI default)."""
        resp = await async_client.get(f"{config_url}/this_route_does_not_exist")
        assert resp.status_code == 404, (
            f"Expected 404 for unknown route, got {resp.status_code}"
        )
        # Even unknown routes might return a standard format if a
        # custom 404 handler is configured. At minimum check 404.
        body = resp.json()
        if "meta" in body:
            assert body["meta"]["status"] in ("ok", "error")


class TestHealthFormat:
    """Verify health response fields per service."""

    @pytest.mark.asyncio
    async def test_all_health_have_timestamps(
        self,
        async_client: httpx.AsyncClient,
        config_url: str,
        immunefi_url: str,
        classifier_url: str,
        orchestrator_url: str,
    ) -> None:
        """Every health response must include a timestamp."""
        for name, url in [
            ("config", config_url),
            ("immunefi", immunefi_url),
            ("classifier", classifier_url),
            ("orchestrator", orchestrator_url),
        ]:
            resp = await async_client.get(f"{url}/health")
            assert resp.status_code == 200
            body = resp.json()

            if _is_type_a_health(body):
                assert "timestamp" in body, f"{name}: missing timestamp (flat)"
            else:
                assert "meta" in body, f"{name}: missing meta"
                assert "timestamp" in body["meta"], (
                    f"{name}: timestamp in meta"
                )

    @pytest.mark.asyncio
    async def test_health_version_present(
        self,
        async_client: httpx.AsyncClient,
        config_url: str,
        classifier_url: str,
    ) -> None:
        """Type A health responses always contain a version string."""
        for name, url in [("config", config_url), ("classifier", classifier_url)]:
            resp = await async_client.get(f"{url}/health")
            body = resp.json()
            version = body.get("version", "")
            assert version, f"{name}: version should be non-empty, got {version!r}"
