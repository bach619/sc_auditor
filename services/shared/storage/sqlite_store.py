"""SqliteStore — Production-grade SQLite implementation of BaseStore.

Features:
- WAL (Write-Ahead Logging) mode: concurrent reads + single writer
- Thread-safe: threading.local() per-thread connections
- Performance: 20MB page cache, MEMORY temp store, optimized pragmas
- ACID: BEGIN IMMEDIATE transactions, auto-rollback on error
- Migration: Auto CREATE TABLE IF NOT EXISTS at startup
- Maintenance: VACUUM, integrity_check, backup API

Design decisions:
- Single writer lock (threading.Lock): protects against concurrent writes
  within the same process. Cross-process writes are handled by the
  "one service owns its DB" architecture — only ONE container mounts
  each SQLite file.
- No connection pool needed: threading.local() is efficient enough
  for <50 concurrent threads per service.
- WAL mode: allows readers to run concurrently with a single writer.
  No performance penalty compared to DELETE journal mode.

Reference:
- 17-experience uses identical pattern (WAL, threading.local, sync=NORMAL)
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .base import BaseStore
from .types import StoreConfig, QueryResult, StoreMode

logger = logging.getLogger("vyper.storage.sqlite")


class SqliteStore(BaseStore):
    """SQLite-backed data store with WAL mode and thread-safe connections.

    Usage:
        config = StoreConfig(db_path="/data/my_service/store.db")
        store = SqliteStore(config)

        row_id = store.insert("findings", {"title": "Reentrancy", "severity": "HIGH"})
        results = store.query_all("SELECT * FROM findings WHERE severity = ?", ("HIGH",))
        store.backup("/data/my_service/backups/latest.db")
    """

    def __init__(self, config: StoreConfig) -> None:
        self._config = config
        self._local = threading.local()
        self._write_lock = threading.Lock()
        self._closed = False

        # Ensure directory exists
        db_dir = Path(config.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        # Initialize connection
        self._init_connections()

        logger.info(
            "SqliteStore initialized: path=%s journal=%s sync=%s cache=%dKB",
            config.db_path,
            config.journal_mode,
            config.synchronous,
            abs(config.cache_size),
        )

    # ── Connection Management ────────────────────────────────────

    def _init_connections(self) -> None:
        """Trigger lazy connection creation to validate config early."""
        try:
            conn = self._get_conn()
            self._apply_pragmas(conn)
        except sqlite3.Error as exc:
            logger.error("Failed to initialize SQLite: %s", exc)
            raise

    def _get_conn(self) -> sqlite3.Connection:
        """Thread-safe connection factory with lazy init.

        Each thread gets its own connection via threading.local().
        This is safe because SQLite serializes writes internally
        in WAL mode, and we use an additional write_lock for
        BEGIN IMMEDIATE transactions.
        """
        if self._closed:
            raise RuntimeError("SqliteStore is closed")

        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                self._config.db_path,
                timeout=self._config.busy_timeout / 1000.0,
                check_same_thread=False,   # We manage threading ourselves
            )
            conn.row_factory = sqlite3.Row
            self._apply_pragmas(conn)
            self._local.conn = conn

            num_threads = getattr(self._local, "thread_count", 0) + 1
            self._local.thread_count = num_threads

        return self._local.conn

    def _apply_pragmas(self, conn: sqlite3.Connection) -> None:
        """Apply performance and safety PRAGMA settings."""
        conn.execute(f"PRAGMA journal_mode={self._config.journal_mode}")
        conn.execute(f"PRAGMA synchronous={self._config.synchronous}")
        conn.execute(f"PRAGMA cache_size={self._config.cache_size}")
        conn.execute("PRAGMA busy_timeout = 5000")          # 5s wait
        conn.execute("PRAGMA mmap_size = 268435456")         # 256 MB memory-map
        conn.execute("PRAGMA temp_store = MEMORY")            # Temp tables in RAM
        if self._config.foreign_keys:
            conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA optimize")                       # Run optimizations

    # ── Core Operations ──────────────────────────────────────────

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> QueryResult:
        """Execute SQL with auto-transaction and write lock.

        READ queries use BEGIN (shared lock).
        WRITE queries use BEGIN IMMEDIATE (reserved lock) to prevent
        SQLITE_BUSY when multiple threads try to start transactions.
        """
        start = time.perf_counter()
        is_write = self._is_write_query(sql)

        conn = self._get_conn()

        if is_write:
            with self._write_lock:
                return self._execute_internal(conn, sql, params, start)
        else:
            return self._execute_internal(conn, sql, params, start)

    def _execute_internal(
        self,
        conn: sqlite3.Connection,
        sql: str,
        params: tuple[Any, ...],
        start: float,
    ) -> QueryResult:
        """Internal execution with BEGIN/COMMIT/ROLLBACK.

        VACUUM is handled specially — it cannot run inside a transaction.
        """
        is_write = self._is_write_query(sql)
        is_vacuum = sql.strip().upper().startswith("VACUUM")

        if is_vacuum:
            # VACUUM must NOT run inside a transaction
            cursor = conn.execute(sql, params)
            rows: list[dict[str, Any]] = []
        else:
            begin_stmt = "BEGIN IMMEDIATE" if is_write else "BEGIN"
            conn.execute(begin_stmt)
            try:
                cursor = conn.execute(sql, params)
                rows = [dict(r) for r in cursor.fetchall()]
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        row_count = cursor.rowcount if is_write else len(rows)

        elapsed = (time.perf_counter() - start) * 1000
        return QueryResult(
            rows=rows,
            row_count=row_count,
            last_row_id=cursor.lastrowid,
            query_time_ms=round(elapsed, 2),
        )

    def execute_many(self, sql: str, params_list: list[tuple[Any, ...]]) -> int:
        """Batch execute parameterized SQL. Returns total rows affected."""
        conn = self._get_conn()
        with self._write_lock:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = conn.executemany(sql, params_list)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return cursor.rowcount

    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        """Execute query and return single row, or None."""
        conn = self._get_conn()
        conn.execute("BEGIN")
        try:
            cursor = conn.execute(sql, params)
            row = cursor.fetchone()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return dict(row) if row else None

    def query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Execute query and return all matching rows."""
        conn = self._get_conn()
        conn.execute("BEGIN")
        try:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return [dict(r) for r in rows]

    @staticmethod
    def _is_write_query(sql: str) -> bool:
        """Heuristic: detect if SQL statement modifies data."""
        sql_upper = sql.strip().upper()
        write_keywords = (
            "INSERT", "UPDATE", "DELETE", "REPLACE",
            "CREATE", "ALTER", "DROP", "VACUUM",
        )
        return any(sql_upper.startswith(kw) for kw in write_keywords)

    # ── CRUD Helpers ─────────────────────────────────────────────

    def insert(self, table: str, data: dict[str, Any]) -> int:
        """INSERT row and return last_row_id."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        result = self.execute(sql, tuple(data.values()))
        return result.last_row_id if result.last_row_id else 0

    def update(self, table: str, where: dict[str, Any], data: dict[str, Any]) -> int:
        """UPDATE rows matching WHERE clause."""
        if not where:
            raise ValueError("UPDATE requires a WHERE clause")
        set_clause = ", ".join(f"{k} = ?" for k in data)
        where_clause = " AND ".join(f"{k} = ?" for k in where)
        sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        result = self.execute(sql, tuple(data.values()) + tuple(where.values()))
        return result.row_count

    def delete(self, table: str, where: dict[str, Any]) -> int:
        """DELETE rows matching WHERE clause."""
        if not where:
            raise ValueError("DELETE requires a WHERE clause")
        where_clause = " AND ".join(f"{k} = ?" for k in where)
        sql = f"DELETE FROM {table} WHERE {where_clause}"
        result = self.execute(sql, tuple(where.values()))
        return result.row_count

    def upsert(self, table: str, where: dict[str, Any], data: dict[str, Any]) -> int:
        """INSERT OR REPLACE. Returns last_row_id."""
        merged = {**where, **data}
        columns = ", ".join(merged.keys())
        placeholders = ", ".join("?" for _ in merged)
        sql = f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})"
        result = self.execute(sql, tuple(merged.values()))
        return result.last_row_id if result.last_row_id else 0

    # ── Schema Management ────────────────────────────────────────

    def table_exists(self, table: str) -> bool:
        """Check if table exists."""
        row = self.query_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        return row is not None

    def create_table(self, table: str, columns: dict[str, str]) -> bool:
        """CREATE TABLE IF NOT EXISTS with column definitions."""
        col_defs = ", ".join(f"{name} {dtype}" for name, dtype in columns.items())
        sql = f"CREATE TABLE IF NOT EXISTS {table} ({col_defs})"
        self.execute(sql)
        return True

    def create_index(self, index_name: str, table: str, columns: list[str], unique: bool = False) -> bool:
        """Create an index on the specified columns."""
        unique_kw = "UNIQUE " if unique else ""
        cols = ", ".join(columns)
        sql = f"CREATE {unique_kw}INDEX IF NOT EXISTS {index_name} ON {table} ({cols})"
        self.execute(sql)
        return True

    # ── Maintenance ──────────────────────────────────────────────

    def health_check(self) -> dict[str, Any]:
        """Return store health diagnosis."""
        db_path = Path(self._config.db_path)

        # Integrity
        try:
            integrity = self.query_one("PRAGMA integrity_check")
            status = "ok" if integrity and integrity.get("integrity_check") == "ok" else "corrupt"
        except Exception as exc:
            status = f"error: {exc}"

        # Size
        db_size = db_path.stat().st_size if db_path.exists() else 0
        wal_path = Path(f"{self._config.db_path}-wal")
        wal_size = wal_path.stat().st_size if wal_path.exists() else 0

        # Table count
        table_count = self.query_one(
            "SELECT COUNT(*) as cnt FROM sqlite_master WHERE type='table'"
        )

        # Row counts for top tables
        table_sizes: dict[str, int] = {}
        tables = self.query_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '_%'"
        )
        for t in tables:
            try:
                row = self.query_one(f'SELECT COUNT(*) as cnt FROM "{t["name"]}"')
                if row:
                    table_sizes[t["name"]] = row.get("cnt", 0)
            except Exception:
                table_sizes[t["name"]] = -1

        return {
            "status": status,
            "db_path": str(db_path),
            "db_size_mb": round(db_size / (1024 * 1024), 2),
            "wal_size_mb": round(wal_size / (1024 * 1024), 2),
            "total_size_mb": round((db_size + wal_size) / (1024 * 1024), 2),
            "table_count": table_count.get("cnt", 0) if table_count else 0,
            "table_sizes": table_sizes,
            "journal_mode": self._config.journal_mode,
            "synchronous": self._config.synchronous,
        }

    def vacuum(self) -> None:
        """Reclaim storage space and optimize database."""
        self.execute("PRAGMA optimize")
        self.execute("VACUUM")

    def backup(self, backup_path: str) -> None:
        """Create atomic backup using SQLite backup API.

        Writes to a .tmp file first, then atomically renames to
        the final path — prevents corruption if interrupted.
        """
        tmp_path = backup_path + ".tmp"
        try:
            source = sqlite3.connect(f"file:{self._config.db_path}?mode=ro", uri=True)
            dest = sqlite3.connect(tmp_path)
            source.backup(dest)
            dest.close()
            source.close()
            shutil.move(tmp_path, backup_path)  # Atomic rename
            logger.info("Backup created: %s", backup_path)
        except Exception as exc:
            Path(tmp_path).unlink(missing_ok=True)
            logger.error("Backup failed: %s", exc)
            raise

    def close(self) -> None:
        """Close all thread-local connections."""
        self._closed = True
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None
