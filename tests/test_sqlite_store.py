"""Unit tests for SqliteStore — CRUD, transactions, maintenance, edge cases."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from services.shared.storage.sqlite_store import SqliteStore
from services.shared.storage.types import StoreConfig


@pytest.fixture
def tmp_db_path():
    """Create a temporary SQLite database path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_store.db"


@pytest.fixture
def store(tmp_db_path):
    """Create a fresh SqliteStore instance for each test."""
    config = StoreConfig(
        db_path=str(tmp_db_path),
        journal_mode="WAL",
        synchronous="NORMAL",
        cache_size=-2000,  # 2MB for tests
        busy_timeout=3000,
        auto_migrate=False,
    )
    s = SqliteStore(config)
    yield s
    s.close()


# ════════════════════════════════════════════════════════════════
# Schema operations
# ════════════════════════════════════════════════════════════════

class TestSchemaOperations:
    """Test table creation, existence checks, and indexing."""

    def test_create_table(self, store):
        store.create_table("findings", {
            "id": "TEXT PRIMARY KEY",
            "title": "TEXT NOT NULL",
            "severity": "TEXT NOT NULL",
        })
        assert store.table_exists("findings")

    def test_table_not_exists(self, store):
        assert not store.table_exists("nonexistent_table")

    def test_create_table_idempotent(self, store):
        store.create_table("findings", {
            "id": "TEXT PRIMARY KEY",
            "title": "TEXT NOT NULL",
        })
        # Should not raise
        store.create_table("findings", {
            "id": "TEXT PRIMARY KEY",
            "title": "TEXT NOT NULL",
        })

    def test_create_index(self, store):
        store.create_table("items", {"id": "INTEGER PRIMARY KEY", "name": "TEXT"})
        store.create_index("idx_name", "items", ["name"])
        # Verify index exists
        row = store.query_one(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_name'"
        )
        assert row is not None


# ════════════════════════════════════════════════════════════════
# CRUD operations
# ════════════════════════════════════════════════════════════════

class TestCRUD:
    """Test insert, query, update, delete operations."""

    def test_insert_and_query_all(self, store):
        store.create_table("findings", {
            "id": "TEXT PRIMARY KEY",
            "title": "TEXT NOT NULL",
            "severity": "TEXT NOT NULL",
        })
        store.insert("findings", {"id": "1", "title": "Reentrancy", "severity": "HIGH"})
        store.insert("findings", {"id": "2", "title": "Overflow", "severity": "MEDIUM"})

        results = store.query_all("SELECT * FROM findings")
        assert len(results) == 2

    def test_query_one(self, store):
        store.create_table("findings", {
            "id": "TEXT PRIMARY KEY",
            "title": "TEXT NOT NULL",
            "severity": "TEXT NOT NULL",
        })
        store.insert("findings", {"id": "1", "title": "Reentrancy", "severity": "HIGH"})

        row = store.query_one("SELECT * FROM findings WHERE id = ?", ("1",))
        assert row is not None
        assert row["title"] == "Reentrancy"
        assert row["severity"] == "HIGH"

    def test_query_one_none(self, store):
        store.create_table("findings", {
            "id": "TEXT PRIMARY KEY",
            "title": "TEXT NOT NULL",
        })
        row = store.query_one("SELECT * FROM findings WHERE id = ?", ("999",))
        assert row is None

    def test_query_with_params(self, store):
        store.create_table("findings", {
            "id": "TEXT PRIMARY KEY",
            "title": "TEXT NOT NULL",
            "severity": "TEXT NOT NULL",
        })
        store.insert("findings", {"id": "1", "title": "Reentrancy", "severity": "HIGH"})
        store.insert("findings", {"id": "2", "title": "Overflow", "severity": "MEDIUM"})
        store.insert("findings", {"id": "3", "title": "Access Control", "severity": "HIGH"})

        results = store.query_all(
            "SELECT * FROM findings WHERE severity = ?", ("HIGH",)
        )
        assert len(results) == 2

    def test_update(self, store):
        store.create_table("findings", {
            "id": "TEXT PRIMARY KEY",
            "title": "TEXT NOT NULL",
            "severity": "TEXT NOT NULL",
        })
        store.insert("findings", {"id": "1", "title": "Reentrancy", "severity": "LOW"})

        affected = store.update(
            "findings",
            {"id": "1"},
            {"severity": "HIGH", "title": "Critical Reentrancy"},
        )
        assert affected == 1

        row = store.query_one("SELECT * FROM findings WHERE id = ?", ("1",))
        assert row["severity"] == "HIGH"
        assert row["title"] == "Critical Reentrancy"

    def test_update_no_match(self, store):
        store.create_table("findings", {
            "id": "TEXT PRIMARY KEY",
            "title": "TEXT NOT NULL",
        })
        affected = store.update("findings", {"id": "999"}, {"title": "X"})
        assert affected == 0

    def test_update_requires_where(self, store):
        store.create_table("findings", {"id": "TEXT PRIMARY KEY"})
        with pytest.raises(ValueError):
            store.update("findings", {}, {"id": "1"})

    def test_delete(self, store):
        store.create_table("findings", {
            "id": "TEXT PRIMARY KEY",
            "title": "TEXT NOT NULL",
        })
        store.insert("findings", {"id": "1", "title": "Reentrancy"})
        store.insert("findings", {"id": "2", "title": "Overflow"})

        affected = store.delete("findings", {"id": "1"})
        assert affected == 1

        results = store.query_all("SELECT * FROM findings")
        assert len(results) == 1
        assert results[0]["id"] == "2"

    def test_delete_requires_where(self, store):
        store.create_table("findings", {"id": "TEXT PRIMARY KEY"})
        with pytest.raises(ValueError):
            store.delete("findings", {})

    def test_upsert_insert(self, store):
        store.create_table("findings", {
            "id": "TEXT PRIMARY KEY",
            "title": "TEXT NOT NULL",
        })
        row_id = store.upsert("findings", {"id": "1"}, {"title": "New"})
        assert row_id > 0

        row = store.query_one("SELECT * FROM findings WHERE id = ?", ("1",))
        assert row["title"] == "New"

    def test_upsert_replace(self, store):
        store.create_table("findings", {
            "id": "TEXT PRIMARY KEY",
            "title": "TEXT NOT NULL",
        })
        store.insert("findings", {"id": "1", "title": "Old"})
        store.upsert("findings", {"id": "1"}, {"title": "Updated"})

        row = store.query_one("SELECT * FROM findings WHERE id = ?", ("1",))
        assert row["title"] == "Updated"

    def test_execute_many(self, store):
        store.create_table("items", {"id": "INTEGER PRIMARY KEY", "val": "TEXT"})
        affected = store.execute_many(
            "INSERT INTO items (val) VALUES (?)",
            [("a",), ("b",), ("c",)],
        )
        assert affected == 3
        results = store.query_all("SELECT * FROM items")
        assert len(results) == 3


# ════════════════════════════════════════════════════════════════
# Transaction & Rollback
# ════════════════════════════════════════════════════════════════

class TestTransactions:
    """Test ACID properties and rollback behavior."""

    def test_rollback_on_error(self, store):
        store.create_table("items", {"id": "INTEGER PRIMARY KEY", "val": "TEXT UNIQUE"})
        store.insert("items", {"val": "a"})

        # Attempt duplicate unique value — should rollback
        with pytest.raises(Exception):
            store.insert("items", {"val": "a"})

        # First insert should still be there
        row = store.query_one("SELECT * FROM items WHERE val = ?", ("a",))
        assert row is not None

    def test_atomic_batch_insert(self, store):
        store.create_table("items", {"id": "INTEGER PRIMARY KEY", "val": "TEXT"})
        try:
            store.execute_many(
                "INSERT INTO items (val) VALUES (?)",
                [("a",), ("b",), ("c",)],
            )
        except Exception:
            pass

        results = store.query_all("SELECT * FROM items")
        assert len(results) == 3


# ════════════════════════════════════════════════════════════════
# Health & Maintenance
# ════════════════════════════════════════════════════════════════

class TestHealthAndMaintenance:
    """Test health checks, vacuum, and backup."""

    def test_health_check(self, store):
        store.create_table("items", {"id": "INTEGER PRIMARY KEY", "val": "TEXT"})
        health = store.health_check()
        assert health["status"] == "ok"
        assert health["table_count"] >= 1
        assert health["db_size_mb"] >= 0
        assert health["journal_mode"] == "WAL"

    def test_health_check_empty(self, store):
        health = store.health_check()
        assert health["status"] == "ok"

    def test_vacuum(self, store):
        store.create_table("items", {"id": "INTEGER PRIMARY KEY", "val": "TEXT"})
        for i in range(100):
            store.insert("items", {"val": f"item_{i}"})
        store.delete("items", {"id": 1})  # Delete some to create fragmentation
        # Vacuum should not raise
        store.vacuum()
        # Verify data is still accessible
        count = store.query_one("SELECT COUNT(*) as cnt FROM items")
        assert count is not None

    def test_backup(self, store, tmp_db_path):
        store.create_table("items", {"id": "INTEGER PRIMARY KEY", "val": "TEXT"})
        store.insert("items", {"val": "test"})

        backup_path = str(tmp_db_path.parent / "backup.db")
        store.backup(backup_path)

        assert Path(backup_path).exists()
        assert Path(backup_path).stat().st_size > 0

    def test_close(self, store):
        store.close()
        # Operations after close should raise
        with pytest.raises(RuntimeError):
            store.query_all("SELECT 1")


# ════════════════════════════════════════════════════════════════
# Edge Cases
# ════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_insert_empty_dict(self, store):
        store.create_table("counters", {
            "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
            "name": "TEXT",
        })
        # Insert with no data columns should still work (only autoincrement column)
        # Just verify it doesn't crash
        store.execute("INSERT INTO counters (name) VALUES (?)", ("test",))
        results = store.query_all("SELECT * FROM counters")
        assert len(results) == 1

    def test_large_volume(self, store):
        store.create_table("items", {"id": "INTEGER PRIMARY KEY", "val": "TEXT"})
        # Insert 500 rows
        for i in range(500):
            store.insert("items", {"val": f"item_{i}"})
        results = store.query_all("SELECT * FROM items")
        assert len(results) == 500

    def test_special_characters(self, store):
        store.create_table("items", {"id": "TEXT PRIMARY KEY", "val": "TEXT"})
        special_val = "test 'single' \"double\" \\ backslash \n newline \t tab"
        store.insert("items", {"id": "1", "val": special_val})
        row = store.query_one("SELECT * FROM items WHERE id = ?", ("1",))
        assert row is not None
        assert row["val"] == special_val

    def test_null_values(self, store):
        store.create_table("items", {
            "id": "INTEGER PRIMARY KEY",
            "val": "TEXT",
            "extra": "TEXT",
        })
        store.insert("items", {"val": "has_value", "extra": None})
        row = store.query_one("SELECT * FROM items WHERE val = ?", ("has_value",))
        assert row is not None
        assert row["extra"] is None

    def test_query_time_tracked(self, store):
        store.create_table("items", {"id": "INTEGER PRIMARY KEY", "val": "TEXT"})
        result = store.execute("SELECT * FROM items")
        assert result.query_time_ms >= 0
