"""Unit tests for MigrationEngine — schema migration management."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from services.shared.storage.migrations import Migration, MigrationEngine
from services.shared.storage.sqlite_store import SqliteStore
from services.shared.storage.types import StoreConfig


@pytest.fixture
def tmp_db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_migrations.db"


@pytest.fixture
def store(tmp_db_path):
    config = StoreConfig(
        db_path=str(tmp_db_path),
        journal_mode="WAL",
        cache_size=-2000,
        auto_migrate=False,
    )
    s = SqliteStore(config)
    yield s
    s.close()


@pytest.fixture
def engine(store):
    return MigrationEngine(store)


# ════════════════════════════════════════════════════════════════
# Basic migration
# ════════════════════════════════════════════════════════════════

class TestBasicMigrations:
    def test_single_migration(self, store, engine):
        def create_findings(s):
            s.execute("""
                CREATE TABLE IF NOT EXISTS findings (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL
                )
            """)

        migrations = [
            Migration(1, "create_findings_table", up=create_findings),
        ]

        applied = engine.run_pending(migrations)
        assert applied == [1]
        assert store.table_exists("findings")

    def test_multiple_migrations(self, store, engine):
        def m1(s):
            s.execute("CREATE TABLE IF NOT EXISTS t1 (id INTEGER PRIMARY KEY)")

        def m2(s):
            s.execute("CREATE TABLE IF NOT EXISTS t2 (id INTEGER PRIMARY KEY)")

        migrations = [
            Migration(1, "create_t1", up=m1),
            Migration(2, "create_t2", up=m2),
        ]

        applied = engine.run_pending(migrations)
        assert applied == [1, 2]
        assert store.table_exists("t1")
        assert store.table_exists("t2")

    def test_idempotent(self, store, engine):
        """Running migrations twice should only apply them once."""
        def m1(s):
            s.execute("CREATE TABLE IF NOT EXISTS t1 (id INTEGER PRIMARY KEY)")

        migrations = [Migration(1, "create_t1", up=m1)]

        engine.run_pending(migrations)
        applied = engine.run_pending(migrations)
        assert applied == []  # Nothing to apply

    def test_out_of_order_versions(self, store, engine):
        """Migrations should be applied in version order regardless of input order."""
        applied_order = []

        def make_migration(version, name):
            def _m(s):
                s.execute(f"CREATE TABLE IF NOT EXISTS t{version} (id INTEGER PRIMARY KEY)")
                applied_order.append(version)
            return Migration(version, name, up=_m)

        # Insert in reverse order — engine should sort ascending
        migrations = [
            make_migration(3, "create_t3"),
            make_migration(1, "create_t1"),
            make_migration(2, "create_t2"),
        ]

        engine.run_pending(migrations)
        assert applied_order == [1, 2, 3]


# ════════════════════════════════════════════════════════════════
# Rollback
# ════════════════════════════════════════════════════════════════

class TestRollback:
    def test_rollback_single(self, store, engine):
        def up(s):
            s.execute("CREATE TABLE IF NOT EXISTS t1 (id INTEGER PRIMARY KEY)")
        def down(s):
            s.execute("DROP TABLE IF EXISTS t1")

        migrations = [
            Migration(1, "create_t1", up=up, down=down),
        ]

        engine.run_pending(migrations)
        assert store.table_exists("t1")

        engine.rollback_to(migrations, 0)  # Rollback everything
        assert not store.table_exists("t1")

    def test_rollback_to_version(self, store, engine):
        def make_up(version):
            def _up(s):
                s.execute(f"CREATE TABLE IF NOT EXISTS t{version} (id INTEGER PRIMARY KEY)")
            return _up

        def make_down(version):
            def _down(s):
                s.execute(f"DROP TABLE IF EXISTS t{version}")
            return _down

        migrations = [
            Migration(1, "v1", up=make_up(1), down=make_down(1)),
            Migration(2, "v2", up=make_up(2), down=make_down(2)),
            Migration(3, "v3", up=make_up(3), down=make_down(3)),
        ]

        engine.run_pending(migrations)
        assert store.table_exists("t1")
        assert store.table_exists("t2")
        assert store.table_exists("t3")

        # Rollback to version 1 (keep t1, remove t2, t3)
        engine.rollback_to(migrations, 1)
        assert store.table_exists("t1")
        assert not store.table_exists("t2")
        assert not store.table_exists("t3")

    def test_rollback_without_down_skips(self, store, engine):
        def up(s):
            s.execute("CREATE TABLE IF NOT EXISTS t1 (id INTEGER PRIMARY KEY)")

        # Migration with no `down` callback
        migrations = [Migration(1, "v1", up=up, down=None)]

        engine.run_pending(migrations)
        # Should not raise — just skip
        engine.rollback_to(migrations, 0)
        # Table still exists because no `down` to drop it
        assert store.table_exists("t1")


# ════════════════════════════════════════════════════════════════
# Error handling
# ════════════════════════════════════════════════════════════════

class TestErrorHandling:
    def test_failing_migration_does_not_record(self, store, engine):
        def bad_up(s):
            raise ValueError("Intentional failure")

        migrations = [Migration(1, "bad_migration", up=bad_up)]

        with pytest.raises(RuntimeError, match="bad_migration"):
            engine.run_pending(migrations)

        # Should NOT be recorded as applied
        status = engine.status(migrations)
        assert status["applied_count"] == 0

    def test_failing_migration_with_rollback(self, store, engine):
        def up(s):
            s.execute("CREATE TABLE IF NOT EXISTS t1 (id INTEGER PRIMARY KEY)")
            s.execute("INSERT INTO t1 (id) VALUES (1)")
            raise ValueError("Intentional failure after partial work")

        def down(s):
            s.execute("DROP TABLE IF EXISTS t1")

        migrations = [Migration(1, "partial_fail", up=up, down=down)]

        with pytest.raises(RuntimeError, match="partial_fail"):
            engine.run_pending(migrations)

        # Down should have cleaned up
        assert not store.table_exists("t1")


# ════════════════════════════════════════════════════════════════
# Status reporting
# ════════════════════════════════════════════════════════════════

class TestStatus:
    def test_status_empty(self, engine):
        def m1(s):
            s.execute("CREATE TABLE IF NOT EXISTS t1 (id INTEGER PRIMARY KEY)")

        migrations = [Migration(1, "m1", up=m1)]
        status = engine.status(migrations)
        assert status["current_version"] == 0
        assert status["total_migrations"] == 1
        assert status["applied_count"] == 0
        assert status["pending_count"] == 1

    def test_status_after_apply(self, store, engine):
        def m1(s):
            s.execute("CREATE TABLE IF NOT EXISTS t1 (id INTEGER PRIMARY KEY)")
        def m2(s):
            s.execute("CREATE TABLE IF NOT EXISTS t2 (id INTEGER PRIMARY KEY)")

        migrations = [
            Migration(1, "m1", up=m1),
            Migration(2, "m2", up=m2),
        ]

        engine.run_pending(migrations)

        status = engine.status(migrations)
        assert status["current_version"] == 2
        assert status["total_migrations"] == 2
        assert status["applied_count"] == 2
        assert status["pending_count"] == 0

    def test_status_json_serializable(self, store, engine):
        """Status dict should be JSON-serializable."""
        import json

        migrations = [Migration(1, "m1", up=lambda s: None)]
        status = engine.status(migrations)
        # Should not raise
        json.dumps(status)
