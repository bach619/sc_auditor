"""Shared types for the Vyper storage layer.

Defines configuration, query results, and storage mode enums
used across all storage implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StoreMode(str, Enum):
    """Storage engine selection mode.

    Used via STORAGE_ENGINE environment variable:
        sqlite  — SQLite only (production)
        json    — JSON only (legacy / rollback)
        dual    — Write to both SQLite + JSON (migration)
    """

    SQLITE = "sqlite"
    JSON = "json"
    DUAL = "dual"


@dataclass
class StoreConfig:
    """Per-service storage configuration.

    Attributes:
        db_path:         Full path to the SQLite database file
        journal_mode:    SQLite journal mode (WAL recommended)
        synchronous:     Sync level (NORMAL good balance, FULL safest)
        cache_size:      Page cache in KB (negative = KB, default -20000 = 20MB)
        busy_timeout:    Wait time in ms before giving up on locked DB
        foreign_keys:    Enable foreign key constraint enforcement
        auto_migrate:    Run CREATE TABLE IF NOT EXISTS at startup
        backup_enabled:  Enable automatic backup via sqlite3 .backup API
        backup_path:     Directory for backup files
        mode:            Storage engine mode (sqlite / json / dual)
    """

    db_path: str
    journal_mode: str = "WAL"
    synchronous: str = "NORMAL"
    cache_size: int = -20000          # 20 MB
    busy_timeout: int = 5000           # 5 seconds
    foreign_keys: bool = True
    auto_migrate: bool = True
    backup_enabled: bool = False
    backup_path: str = ""
    mode: StoreMode = StoreMode.SQLITE


@dataclass
class QueryResult:
    """Result container for storage queries.

    Attributes:
        rows:          List of result rows as dictionaries
        row_count:     Number of rows returned
        last_row_id:   Last inserted row ID (for INSERT)
        query_time_ms: Execution time in milliseconds
    """

    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    last_row_id: int | None = None
    query_time_ms: float = 0.0

    def first(self) -> dict[str, Any] | None:
        """Return first row or None."""
        return self.rows[0] if self.rows else None

    def as_list(self) -> list[dict[str, Any]]:
        """Return all rows as list of dicts."""
        return self.rows

    def as_scalar(self) -> Any | None:
        """Return first column of first row, or None."""
        if not self.rows:
            return None
        return next(iter(self.rows[0].values()), None)
