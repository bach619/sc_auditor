"""SimpleSQLiteStore — Lightweight SQLite wrapper for simple CRUD services.

Used by: Scanner sub-services (04a-04e, 05), Reporter (09), Notifier (10),
         Webhook (12), Upkeep (13), Submission (16), Bounty platforms (18-21),
         StarkNet services (22-23).

Pattern: These services write simple records (one entity type per service)
and need basic CRUD + search + health check. No complex relationships.
"""

from __future__ import annotations

import logging
from typing import Any

from services.shared.storage import SqliteStore, StoreConfig

logger = logging.getLogger("vyper.storage.simple")


class SimpleSQLiteStore:
    """Minimal SQLite store for services with simple data models.

    Usage:
        store = SimpleSQLiteStore(
            db_path="/data/my_service/store.db",
            schema_sql=MY_SCHEMA,
        )
        store.insert({"job_id": "123", "status": "done"})
        results = store.query("status = ?", ("done",))

    For even simpler usage (single-table services), use create_table()
    and the CRUD helpers directly.
    """

    def __init__(self, db_path: str, schema_sql: str = "", table_name: str = "data") -> None:
        self._store = SqliteStore(StoreConfig(
            db_path=db_path,
            journal_mode="WAL",
            cache_size=-5000,
            auto_migrate=False,
        ))
        self._table = table_name
        if schema_sql:
            self._execute_schema(schema_sql)

    def _execute_schema(self, schema_sql: str) -> None:
        for stmt in schema_sql.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                self._store.execute(stmt)

    # ── Auto-table creation ────────────────────────────────

    def ensure_table(self, columns: dict[str, str]) -> None:
        """Create table if not exists. Simple key-value schema."""
        self._store.create_table(self._table, columns)

    # ── CRUD ───────────────────────────────────────────────

    def insert(self, data: dict) -> int:
        return self._store.insert(self._table, data)

    def insert_batch(self, rows: list[dict]) -> int:
        count = 0
        for row in rows:
            self.insert(row)
            count += 1
        return count

    def get(self, key: str, value: Any) -> dict | None:
        return self._store.query_one(
            f"SELECT * FROM {self._table} WHERE {key} = ?", (value,)
        )

    def query(self, where: str = "", params: tuple = (), order: str = "", limit: int = 100) -> list[dict]:
        sql = f"SELECT * FROM {self._table}"
        if where:
            sql += f" WHERE {where}"
        if order:
            sql += f" ORDER BY {order}"
        if limit:
            sql += f" LIMIT {limit}"
        return self._store.query_all(sql, params)

    def query_one(self, where: str, params: tuple) -> dict | None:
        return self._store.query_one(
            f"SELECT * FROM {self._table} WHERE {where}", params
        )

    def update(self, where: dict, data: dict) -> int:
        return self._store.update(self._table, where, data)

    def upsert(self, where: dict, data: dict) -> int:
        """UPDATE or INSERT — checks existence first.

        Uses UPDATE-then-INSERT pattern since SimpleSQLiteStore tables
        may not have UNIQUE constraints on arbitrary columns.
        """
        existing = self._store.query_one(
            f"SELECT rowid FROM {self._table} WHERE {' AND '.join(f'{k} = ?' for k in where)}",
            tuple(where.values()),
        )
        if existing:
            return self._store.update(self._table, where, data)
        else:
            merged = {**where, **data}
            return self._store.insert(self._table, merged)

    def delete(self, where: dict) -> int:
        return self._store.delete(self._table, where)

    def count(self, where: str = "", params: tuple = ()) -> int:
        sql = f"SELECT COUNT(*) as cnt FROM {self._table}"
        if where:
            sql += f" WHERE {where}"
        row = self._store.query_one(sql, params)
        return row["cnt"] if row else 0

    def all(self) -> list[dict]:
        return self._store.query_all(f"SELECT * FROM {self._table}")

    def clear(self) -> None:
        self._store.execute(f"DELETE FROM {self._table}")

    # ── Maintenance ────────────────────────────────────────

    def health(self) -> dict:
        return self._store.health_check()

    def raw_store(self) -> SqliteStore:
        """Access underlying SqliteStore for advanced queries."""
        return self._store
