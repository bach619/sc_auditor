"""Schema migration engine for Vyper storage layer.

Provides version tracking and incremental migration support.
Each migration has an `up` (apply) and `down` (rollback) function.

Migration table:
    CREATE TABLE IF NOT EXISTS _migrations (
        version     INTEGER PRIMARY KEY,
        name        TEXT NOT NULL,
        applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
        checksum    TEXT
    )

Usage:
    store = SqliteStore(config)
    engine = MigrationEngine(store)

    migrations = [
        Migration(1, "create_findings_table",
            up=lambda s: s.create_table("findings", {...}),
            down=lambda s: s.execute("DROP TABLE IF EXISTS findings"),
        ),
        Migration(2, "add_confidence_index",
            up=lambda s: s.create_index("idx_confidence", "findings", ["confidence"]),
            down=lambda s: s.execute("DROP INDEX IF EXISTS idx_confidence"),
        ),
    ]

    applied = engine.run_pending(migrations)  # Returns list of version numbers applied
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger("vyper.storage.migrations")


@dataclass
class Migration:
    """A single schema migration step.

    Attributes:
        version:  Monotonically increasing version number (unique)
        name:     Human-readable description of the migration
        up:       Function to apply the migration
        down:     Function to rollback the migration (optional)
        checksum: Optional integrity check hash
    """
    version: int
    name: str
    up: Callable[[Any], None]                 # Takes store as argument
    down: Callable[[Any], None] | None = None # Takes store as argument
    checksum: str | None = None
    applied_at: str | None = field(default=None, init=False)


class MigrationEngine:
    """Manages schema migrations for a storage instance.

    Tracks which migrations have been applied using a `_migrations`
    table. Only runs migrations that haven't been applied yet.
    Supports rollback to a specific version.
    """

    def __init__(self, store: Any) -> None:
        """Initialize migration engine.

        Args:
            store: BaseStore-compatible instance (SqliteStore, JsonStore, etc.)
        """
        self._store = store
        self._ensure_migrations_table()

    # ── Migration Table ──────────────────────────────────────

    def _ensure_migrations_table(self) -> None:
        """Create migrations tracking table if it doesn't exist."""
        self._store.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                version     INTEGER PRIMARY KEY,
                name        TEXT NOT NULL,
                applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
                checksum    TEXT
            )
        """)

    def _get_applied_versions(self) -> set[int]:
        """Get set of already-applied migration versions."""
        try:
            rows = self._store.query_all("SELECT version FROM _migrations")
            return {int(r["version"]) for r in rows}
        except Exception:
            # If table doesn't exist or query fails, assume nothing applied
            return set()

    def _record_migration(self, migration: Migration) -> None:
        """Record that a migration has been applied."""
        self._store.insert("_migrations", {
            "version": migration.version,
            "name": migration.name,
            "checksum": migration.checksum,
        })

    def _remove_migration_record(self, version: int) -> None:
        """Remove migration record (for rollback)."""
        self._store.delete("_migrations", {"version": version})

    # ── Migration Operations ─────────────────────────────────

    def run_pending(self, migrations: list[Migration]) -> list[int]:
        """Run all pending migrations in version order.

        Args:
            migrations: List of Migration objects to evaluate

        Returns:
            List of version numbers that were applied
        """
        applied_set = self._get_applied_versions()
        pending = [m for m in migrations if m.version not in applied_set]

        if not pending:
            logger.info("No pending migrations — all %d applied", len(migrations))
            return []

        # Sort by version number (should already be sorted, but be safe)
        pending.sort(key=lambda m: m.version)

        new_applied: list[int] = []
        for migration in pending:
            try:
                logger.info(
                    "Applying migration %03d: %s",
                    migration.version,
                    migration.name,
                )
                migration.up(self._store)
                self._record_migration(migration)
                new_applied.append(migration.version)
                logger.info(
                    "Migration %03d applied successfully: %s",
                    migration.version,
                    migration.name,
                )
            except Exception as exc:
                logger.error(
                    "Migration %03d FAILED: %s — %s",
                    migration.version,
                    migration.name,
                    exc,
                )
                # Attempt rollback of this migration if `down` is provided
                if migration.down:
                    try:
                        logger.info("Rolling back failed migration %03d", migration.version)
                        migration.down(self._store)
                    except Exception as rb_exc:
                        logger.error(
                            "Rollback of migration %03d also failed: %s",
                            migration.version,
                            rb_exc,
                        )
                raise RuntimeError(
                    f"Migration {migration.version} ({migration.name}) failed: {exc}"
                ) from exc

        return new_applied

    def rollback_to(self, migrations: list[Migration], target_version: int) -> list[int]:
        """Rollback migrations down to a specific version (inclusive).

        Args:
            migrations: Full list of migrations with `down` callbacks
            target_version: Rollback TO this version (migrations > target are rolled back)

        Returns:
            List of version numbers that were rolled back
        """
        applied_set = self._get_applied_versions()
        applied_migrations = [m for m in migrations if m.version in applied_set]
        applied_migrations.sort(key=lambda m: m.version, reverse=True)  # DESC

        rolled_back: list[int] = []
        for migration in applied_migrations:
            if migration.version <= target_version:
                continue

            if not migration.down:
                logger.warning(
                    "Migration %03d has no `down` callback — skipping rollback",
                    migration.version,
                )
                continue

            try:
                logger.info("Rolling back migration %03d: %s", migration.version, migration.name)
                migration.down(self._store)
                self._remove_migration_record(migration.version)
                rolled_back.append(migration.version)
            except Exception as exc:
                logger.error("Rollback of migration %03d failed: %s", migration.version, exc)
                raise RuntimeError(
                    f"Rollback of migration {migration.version} ({migration.name}) failed: {exc}"
                ) from exc

        return rolled_back

    def status(self, migrations: list[Migration]) -> dict[str, Any]:
        """Get migration status summary.

        Returns:
            Dict with current_version, total_migrations, applied_count, pending_count
        """
        applied = self._get_applied_versions()
        total = len(migrations)
        applied_count = len([m for m in migrations if m.version in applied])
        current_version = max(applied) if applied else 0

        return {
            "current_version": current_version,
            "total_migrations": total,
            "applied_count": applied_count,
            "pending_count": total - applied_count,
            "applied_versions": sorted(applied),
            "pending_versions": sorted([m.version for m in migrations if m.version not in applied]),
        }
