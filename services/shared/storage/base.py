"""Abstract BaseStore interface for Vyper storage backends.

All storage implementations (SqliteStore, JsonStore, etc.) MUST
implement this interface to guarantee drop-in compatibility.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseStore(ABC):
    """Abstract interface for all storage backends.

    Implementations:
        - SqliteStore:  Primary SQLite-based persistence
        - JsonStore:    JSON file-based (backward compat / fallback)

    Each method must be re-entrant and thread-safe.
    Write methods return row count / last_row_id.
    Read methods return dict or list[dict].
    """

    # ── Core Operations ─────────────────────────────────────

    @abstractmethod
    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        """Execute arbitrary SQL. Return result + metadata.

        The return type is implementation-specific (QueryResult for
        SqliteStore, compatible structure for others).
        """
        ...

    @abstractmethod
    def execute_many(self, sql: str, params_list: list[tuple[Any, ...]]) -> int:
        """Batch execute parameterized SQL. Return total rows affected."""
        ...

    @abstractmethod
    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        """Execute query, return single row or None."""
        ...

    @abstractmethod
    def query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Execute query, return all matching rows."""
        ...

    # ── CRUD Helpers ─────────────────────────────────────────

    @abstractmethod
    def insert(self, table: str, data: dict[str, Any]) -> int:
        """INSERT INTO table VALUES (data). Return last row id."""
        ...

    @abstractmethod
    def update(self, table: str, where: dict[str, Any], data: dict[str, Any]) -> int:
        """UPDATE table SET data WHERE where. Return rows affected."""
        ...

    @abstractmethod
    def delete(self, table: str, where: dict[str, Any]) -> int:
        """DELETE FROM table WHERE where. Return rows affected."""
        ...

    @abstractmethod
    def upsert(self, table: str, where: dict[str, Any], data: dict[str, Any]) -> int:
        """INSERT OR REPLACE. Return last row id."""
        ...

    # ── Schema ────────────────────────────────────────────────

    @abstractmethod
    def table_exists(self, table: str) -> bool:
        """Check if table exists in storage."""
        ...

    @abstractmethod
    def create_table(self, table: str, columns: dict[str, str]) -> bool:
        """CREATE TABLE IF NOT EXISTS with column definitions.
        
        Example:
            store.create_table("findings", {
                "id": "TEXT PRIMARY KEY",
                "title": "TEXT NOT NULL",
                "severity": "TEXT NOT NULL",
                "created_at": "TEXT NOT NULL DEFAULT (datetime('now'))",
            })
        """
        ...

    # ── Maintenance ───────────────────────────────────────────

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Return store health: status, size, table count, integrity."""
        ...

    @abstractmethod
    def vacuum(self) -> None:
        """Reclaim storage space after heavy delete operations."""
        ...

    @abstractmethod
    def backup(self, backup_path: str) -> None:
        """Create atomic backup of entire storage."""
        ...

    def close(self) -> None:
        """Release resources. Override if needed."""
        pass
