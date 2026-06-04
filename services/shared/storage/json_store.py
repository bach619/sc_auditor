"""JsonStore — JSON file adapter implementing BaseStore for backward compatibility.

This store is NOT meant for production use. Its purpose is:
1. Backward compatibility — existing services can use it as drop-in
2. Dual-write fallback — during SQLite migration, both stores are written
3. Rollback safety — instant switch back to JSON if SQLite has issues

Performance: O(n) for queries (file scan). Not suitable for >1K records.
DO NOT use for new development — use SqliteStore instead.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .base import BaseStore
from .types import StoreConfig, QueryResult

logger = logging.getLogger("vyper.storage.json")


class JsonStore(BaseStore):
    """JSON file-based storage adapter.

    Schema: One JSON file per "table". Each file contains a JSON array
    of row objects. No indexing, no transactions, no concurrency safety.

    Layout:
        /data/service/json/
        ├── findings.json       ← [{"id": "1", "title": "..."}, ...]
        ├── classifications.json
        └── metrics.json
    """

    def __init__(self, config: StoreConfig) -> None:
        self._data_dir = Path(config.db_path).parent / "json"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        logger.info("JsonStore initialized: dir=%s", self._data_dir)

    # ── File I/O ─────────────────────────────────────────────

    def _file_path(self, table: str) -> Path:
        """Get JSON file path for a table name."""
        safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in table)
        return self._data_dir / f"{safe_name}.json"

    def _read_table(self, table: str) -> list[dict[str, Any]]:
        """Read entire table from JSON file."""
        path = self._file_path(table)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text())
            if not isinstance(data, list):
                logger.warning("Corrupted JSON in %s — expected list, resetting", table)
                return []
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read %s: %s", table, exc)
            return []

    def _write_table(self, table: str, rows: list[dict[str, Any]]) -> None:
        """Atomically write entire table to JSON file."""
        path = self._file_path(table)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
        tmp.replace(path)  # Atomic on POSIX

    # ── Core Operations ──────────────────────────────────────

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        """Execute basic SQL subset. Only supports simple patterns."""
        logger.warning("JsonStore.execute() is limited — use query_one/query_all instead")
        return QueryResult(rows=[], row_count=0)

    def execute_many(self, sql: str, params_list: list[tuple[Any, ...]]) -> int:
        """Batch insert. Parses INSERT INTO ... VALUES (...) pattern only."""
        # Try to parse table name from SQL
        import re
        match = re.match(r"INSERT\s+INTO\s+(\w+)", sql, re.IGNORECASE)
        if not match:
            raise ValueError(f"Cannot parse table name from: {sql}")
        table = match.group(1)
        rows = self._read_table(table)
        start_count = len(rows)
        _rowid = start_count

        for params in params_list:
            _rowid += 1
            row = {"_rowid": _rowid}
            # FIXME: Properly parse column names from SQL
            row["data"] = list(params)
            rows.append(row)

        self._write_table(table, rows)
        return len(rows) - start_count

    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        """Query single row using simple filter logic."""
        results = self.query_all(sql, params)
        return results[0] if results else None

    def query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Query all rows — OPTIMIZED for JsonStore.

        Supports basic patterns:
        - "SELECT * FROM table"
        - "SELECT * FROM table WHERE col = ?"
        - "SELECT * FROM table WHERE col = ? AND col2 = ?"
        """
        import re

        match = re.match(
            r"SELECT\s+\*\s+FROM\s+(\w+)(?:\s+WHERE\s+(.+?))?(?:\s+(?:ORDER|LIMIT).*)?$",
            sql, re.IGNORECASE | re.DOTALL,
        )
        if not match:
            logger.warning("Complex SQL, returning all rows: %s", sql[:80])
            # Fall back to simple table name extraction
            match = re.match(r"SELECT.+?FROM\s+(\w+)", sql, re.IGNORECASE)

        if not match:
            return []

        table = match.group(1)
        all_rows = self._read_table(table)

        # Apply WHERE filter if present
        where_clause = match.group(2) if match.lastindex and match.lastindex >= 2 else None
        if where_clause and params:
            filtered = []
            for row in all_rows:
                # Simple AND filter: col = ?
                conditions = [c.strip() for c in re.split(r"\s+AND\s+", where_clause, flags=re.IGNORECASE)]
                matches = True
                param_idx = 0
                for cond in conditions:
                    col_match = re.match(r"(\w+)\s*=\s*\?", cond)
                    if col_match:
                        col = col_match.group(1)
                        if param_idx < len(params):
                            try:
                                row_val = row.get(col)
                                expected = params[param_idx]
                                # Type-coerce comparison
                                if row_val != expected and str(row_val) != str(expected):
                                    matches = False
                                    break
                            except Exception:
                                matches = False
                                break
                        param_idx += 1
                if matches:
                    filtered.append(row)
            return filtered

        return all_rows

    # ── CRUD Helpers ─────────────────────────────────────────

    def insert(self, table: str, data: dict[str, Any]) -> int:
        """Insert a row into JSON table."""
        rows = self._read_table(table)
        row_id = len(rows) + 1
        data["_rowid"] = row_id
        rows.append(data)
        self._write_table(table, rows)
        return row_id

    def update(self, table: str, where: dict[str, Any], data: dict[str, Any]) -> int:
        """Update rows matching WHERE clause."""
        rows = self._read_table(table)
        updated = 0
        for row in rows:
            if all(row.get(k) == v for k, v in where.items()):
                row.update(data)
                updated += 1
        if updated > 0:
            self._write_table(table, rows)
        return updated

    def delete(self, table: str, where: dict[str, Any]) -> int:
        """Delete rows matching WHERE clause."""
        rows = self._read_table(table)
        original = len(rows)
        filtered = [r for r in rows if not all(r.get(k) == v for k, v in where.items())]
        removed = original - len(filtered)
        if removed > 0:
            self._write_table(table, filtered)
        return removed

    def upsert(self, table: str, where: dict[str, Any], data: dict[str, Any]) -> int:
        """Insert or update (simple implementation)."""
        rows = self._read_table(table)
        for i, row in enumerate(rows):
            if all(row.get(k) == v for k, v in where.items()):
                rows[i].update(data)
                self._write_table(table, rows)
                return rows[i].get("_rowid", i + 1)
        return self.insert(table, {**where, **data})

    # ── Schema ───────────────────────────────────────────────

    def table_exists(self, table: str) -> bool:
        """Check if JSON file for table exists."""
        return self._file_path(table).exists()

    def create_table(self, table: str, columns: dict[str, str]) -> bool:
        """Create empty JSON table file if not exists."""
        if not self.table_exists(table):
            self._write_table(table, [])
        return True

    # ── Maintenance ──────────────────────────────────────────

    def health_check(self) -> dict[str, Any]:
        """Return health status."""
        files = list(self._data_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files)
        return {
            "status": "ok",
            "type": "json",
            "data_dir": str(self._data_dir),
            "table_count": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }

    def vacuum(self) -> None:
        """No-op for JSON store."""
        pass

    def backup(self, backup_path: str) -> None:
        """Copy entire JSON directory to a tar.gz backup archive."""
        import shutil
        # shutil.make_archive(base_name, format, root_dir)
        # Creates: base_name.tar.gz (if format='gztar')
        # So strip .tar.gz from backup_path for base_name
        base = backup_path.replace(".tar.gz", "").replace(".tgz", "")
        shutil.make_archive(base, "gztar", str(self._data_dir))
