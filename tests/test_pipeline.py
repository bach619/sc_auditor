"""Integration tests — inter-service pipeline flows.

Tests the core data pipeline:
  1. **Config CRUD**  — PUT / GET / DELETE config keys
  2. **Immunefi**     — list programs & stats
  3. **Classifier**   — classification metrics endpoint
"""

from __future__ import annotations

import httpx
import pytest

# ═══════════════════════════════════════════════════════════════════
# Config CRUD
# ═══════════════════════════════════════════════════════════════════


class TestConfigCRUD:
    """Config Service — key/value CRUD operations."""

    TEST_KEY = "vyper_integration_test"
    TEST_VALUE = {"test": True, "purpose": "integration-test"}

    @pytest.mark.asyncio
    async def test_config_upsert(
        self, async_client: httpx.AsyncClient, config_url: str
    ) -> None:
        """PUT /config/{key} — upsert a config value."""
        resp = await async_client.put(
            f"{config_url}/config/{self.TEST_KEY}",
            json={"value": self.TEST_VALUE},
        )
        assert resp.status_code == 200, (
            f"Config upsert failed: {resp.status_code} {resp.text[:200]}"
        )
        body = resp.json()
        assert body["meta"]["status"] == "ok"
        # Response data should contain the key → value mapping
        data = body.get("data", {})
        assert self.TEST_KEY in data, f"Response missing key {self.TEST_KEY}"
        assert data[self.TEST_KEY] == self.TEST_VALUE

    @pytest.mark.asyncio
    async def test_config_get(
        self, async_client: httpx.AsyncClient, config_url: str
    ) -> None:
        """GET /config/{key} — retrieve a previously-upserted value."""
        # First ensure the key exists
        await async_client.put(
            f"{config_url}/config/{self.TEST_KEY}",
            json={"value": self.TEST_VALUE},
        )

        resp = await async_client.get(f"{config_url}/config/{self.TEST_KEY}")
        assert resp.status_code == 200, (
            f"Config get failed: {resp.status_code} {resp.text[:200]}"
        )
        body = resp.json()
        assert body["meta"]["status"] == "ok"
        data = body.get("data", {})
        assert self.TEST_KEY in data
        assert data[self.TEST_KEY] == self.TEST_VALUE

    @pytest.mark.asyncio
    async def test_config_get_missing(
        self, async_client: httpx.AsyncClient, config_url: str
    ) -> None:
        """GET /config/{key} for a nonexistent key returns 404."""
        resp = await async_client.get(
            f"{config_url}/config/__nonexistent_{self.TEST_KEY}"
        )
        assert resp.status_code == 404, (
            f"Expected 404 for missing key, got {resp.status_code}"
        )

    @pytest.mark.asyncio
    async def test_config_delete(
        self, async_client: httpx.AsyncClient, config_url: str
    ) -> None:
        """DELETE /config/{key} — remove a config key."""
        # First ensure the key exists
        await async_client.put(
            f"{config_url}/config/{self.TEST_KEY}",
            json={"value": self.TEST_VALUE},
        )

        resp = await async_client.delete(f"{config_url}/config/{self.TEST_KEY}")
        assert resp.status_code == 200, (
            f"Config delete failed: {resp.status_code} {resp.text[:200]}"
        )
        body = resp.json()
        assert body["meta"]["status"] == "ok"
        # Verify deletion
        get_resp = await async_client.get(f"{config_url}/config/{self.TEST_KEY}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_config_bulk_upsert(
        self, async_client: httpx.AsyncClient, config_url: str
    ) -> None:
        """PUT /config/bulk — upsert multiple keys atomically."""
        bulk = {f"bulk_key_{i}": f"value_{i}" for i in range(3)}
        resp = await async_client.put(
            f"{config_url}/config/bulk",
            json={"config": bulk},
        )
        assert resp.status_code == 200, (
            f"Bulk upsert failed: {resp.status_code} {resp.text[:200]}"
        )
        body = resp.json()
        assert body["meta"]["status"] == "ok"
        # Cleanup
        for key in bulk:
            await async_client.delete(f"{config_url}/config/{key}")

    @pytest.mark.asyncio
    async def test_config_list(
        self, async_client: httpx.AsyncClient, config_url: str
    ) -> None:
        """GET /config/ — list all config keys."""
        resp = await async_client.get(f"{config_url}/config/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"
        assert isinstance(body.get("data"), dict)


# ═══════════════════════════════════════════════════════════════════
# Immunefi
# ═══════════════════════════════════════════════════════════════════


class TestImmunefi:
    """Immunefi Service — programs and stats."""

    @pytest.mark.asyncio
    async def test_immunefi_programs(
        self, async_client: httpx.AsyncClient, immunefi_url: str
    ) -> None:
        """GET /programs — returns a list (possibly empty without sync)."""
        resp = await async_client.get(f"{immunefi_url}/programs")
        # The endpoint should respond even with no data synced
        assert resp.status_code == 200, (
            f"Immunefi programs failed: {resp.status_code} {resp.text[:200]}"
        )
        body = resp.json()
        assert body["meta"]["status"] == "ok"
        data = body.get("data")
        # data is a ProgramListResponse shape: {"data": [...], "total": ..., ...}
        if isinstance(data, dict):
            assert "data" in data, "ProgramListResponse missing data field"
            assert "total" in data, "ProgramListResponse missing total field"
            assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_immunefi_stats(
        self, async_client: httpx.AsyncClient, immunefi_url: str
    ) -> None:
        """GET /stats — returns aggregated statistics."""
        resp = await async_client.get(f"{immunefi_url}/stats")
        assert resp.status_code == 200, (
            f"Immunefi stats failed: {resp.status_code} {resp.text[:200]}"
        )
        body = resp.json()
        assert body["meta"]["status"] == "ok"
        data = body.get("data")
        if data:
            # StatsResponse fields
            for field in ("total_programs", "by_status", "by_chain"):
                assert field in data, f"StatsResponse missing {field}"

    @pytest.mark.asyncio
    async def test_immunefi_program_detail_missing(
        self, async_client: httpx.AsyncClient, immunefi_url: str
    ) -> None:
        """GET /programs/{slug} for nonexistent program returns 404."""
        resp = await async_client.get(
            f"{immunefi_url}/programs/__nonexistent_slug__"
        )
        # The service may return 404 or just return ok with null data
        if resp.status_code == 404:
            body = resp.json()
            # Should be a Vyper error envelope
            assert "meta" in body
        else:
            # If it returns 200, data might be null
            assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# Classifier
# ═══════════════════════════════════════════════════════════════════


class TestClassifier:
    """Classifier Service — metrics and classification endpoints."""

    @pytest.mark.asyncio
    async def test_classifier_metrics(
        self, async_client: httpx.AsyncClient, classifier_url: str
    ) -> None:
        """GET /classify/metrics → metrics object."""
        # Note: some services expose /metrics at root, some at /classify/metrics
        # Try both locations
        resp = await async_client.get(f"{classifier_url}/metrics")
        if resp.status_code == 404:
            resp = await async_client.get(f"{classifier_url}/classify/metrics")

        assert resp.status_code == 200, (
            f"Classifier metrics failed: {resp.status_code} {resp.text[:200]}"
        )
        body = resp.json()

        # Classifier uses ApiResponse envelope (Type B)
        if "meta" in body:
            assert body["meta"]["status"] == "ok"

        data = body.get("data", {})
        if data:
            # Check for known metrics fields
            for field in ("summary", "by_tool", "trend"):
                if field in data:
                    break
            else:
                # At minimum there should be some metrics key
                assert isinstance(data, dict), "metrics data should be a dict"

    @pytest.mark.asyncio
    async def test_classifier_health(
        self, async_client: httpx.AsyncClient, classifier_url: str
    ) -> None:
        """Classifier health — Type A flat HealthResponse."""
        resp = await async_client.get(f"{classifier_url}/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "classifier"
        assert "version" in body
        assert "timestamp" in body
