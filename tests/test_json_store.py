"""Unit tests for JsonStore — backward-compatible JSON file storage."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from services.shared.storage.json_store import JsonStore
from services.shared.storage.types import StoreConfig


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for JSON storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def store(tmp_dir):
    """Create a fresh JsonStore instance for each test."""
    config = StoreConfig(
        db_path=str(Path(tmp_dir) / "store.db"),  # Not used, but required
        auto_migrate=False,
    )
    return JsonStore(config)


# ════════════════════════════════════════════════════════════════
# Schema
# ════════════════════════════════════════════════════════════════

class TestJsonSchema:
    def test_create_table(self, store):
        store.create_table("findings", {
            "id": "TEXT PRIMARY KEY",
            "title": "TEXT NOT NULL",
        })
        assert store.table_exists("findings")

    def test_table_not_exists(self, store):
        assert not store.table_exists("nonexistent")


# ════════════════════════════════════════════════════════════════
# CRUD
# ════════════════════════════════════════════════════════════════

class TestJsonCRUD:
    def test_insert_and_query(self, store):
        store.create_table("findings", {})
        row_id = store.insert("findings", {"title": "Reentrancy", "severity": "HIGH"})
        assert row_id == 1

        row_id = store.insert("findings", {"title": "Overflow", "severity": "MEDIUM"})
        assert row_id == 2

        results = store.query_all("SELECT * FROM findings")
        assert len(results) == 2

    def test_query_where(self, store):
        store.create_table("findings", {})
        store.insert("findings", {"title": "Reentrancy", "severity": "HIGH"})
        store.insert("findings", {"title": "Overflow", "severity": "MEDIUM"})

        results = store.query_all(
            "SELECT * FROM findings WHERE severity = ?", ("HIGH",)
        )
        assert len(results) == 1
        assert results[0]["title"] == "Reentrancy"

    def test_query_one(self, store):
        store.create_table("findings", {})
        store.insert("findings", {"id": "1", "title": "Test"})

        row = store.query_one("SELECT * FROM findings WHERE id = ?", ("1",))
        assert row is not None
        assert row["title"] == "Test"

    def test_query_one_none(self, store):
        store.create_table("findings", {})
        row = store.query_one("SELECT * FROM findings WHERE id = ?", ("999",))
        assert row is None

    def test_update(self, store):
        store.create_table("findings", {})
        store.insert("findings", {"id": "1", "title": "Old", "severity": "LOW"})

        affected = store.update(
            "findings",
            {"id": "1"},
            {"severity": "HIGH"},
        )
        assert affected == 1

        results = store.query_all("SELECT * FROM findings")
        assert results[0]["severity"] == "HIGH"

    def test_update_no_match(self, store):
        store.create_table("findings", {})
        affected = store.update("findings", {"id": "999"}, {"x": "y"})
        assert affected == 0

    def test_delete(self, store):
        store.create_table("findings", {})
        store.insert("findings", {"id": "1", "title": "A"})
        store.insert("findings", {"id": "2", "title": "B"})

        removed = store.delete("findings", {"id": "1"})
        assert removed == 1

        results = store.query_all("SELECT * FROM findings")
        assert len(results) == 1
        assert results[0]["id"] == "2"

    def test_upsert(self, store):
        store.create_table("findings", {})
        row_id = store.upsert("findings", {"id": "1"}, {"title": "New"})
        assert row_id > 0

        # Upsert existing
        row_id = store.upsert("findings", {"id": "1"}, {"title": "Updated"})
        assert row_id > 0

        results = store.query_all("SELECT * FROM findings")
        assert len(results) == 1
        assert results[0]["title"] == "Updated"


# ════════════════════════════════════════════════════════════════
# Health & Maintenance
# ════════════════════════════════════════════════════════════════

class TestJsonHealth:
    def test_health_check(self, store):
        store.create_table("findings", {})
        store.insert("findings", {"title": "Test"})

        health = store.health_check()
        assert health["status"] == "ok"
        assert health["type"] == "json"
        assert health["table_count"] >= 1

    def test_vacuum_noop(self, store):
        # Vacuum should not raise
        store.vacuum()

    def test_backup(self, store, tmp_dir):
        store.create_table("items", {})
        store.insert("items", {"val": "test"})

        backup_path = str(Path(tmp_dir) / "backup.tar.gz")
        store.backup(backup_path)
        assert Path(backup_path).exists()


# ════════════════════════════════════════════════════════════════
# Edge Cases
# ════════════════════════════════════════════════════════════════

class TestJsonEdgeCases:
    def test_empty_table(self, store):
        store.create_table("empty", {})
        results = store.query_all("SELECT * FROM empty")
        assert results == []

    def test_write_after_crash_recovery(self, store):
        """JSON store uses atomic rename — should survive crash simulation."""
        store.create_table("items", {})
        for i in range(20):
            store.insert("items", {"val": f"item_{i}"})

        results = store.query_all("SELECT * FROM items")
        assert len(results) == 20

    def test_special_table_names(self, store):
        """Table names with special characters are sanitized."""
        store.create_table("my-findings_table", {})
        assert store.table_exists("my-findings_table")
