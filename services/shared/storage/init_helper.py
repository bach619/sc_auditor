"""One-line SQLite store initialization for Vyper services.

Usage in any service's app.py startup:
    from shared.storage import init_sqlite_store
    store = init_sqlite_store("/data/my_service")

Returns a SimpleSQLiteStore if STORAGE_ENGINE is sqlite or dual, else None.
The store automatically creates a default `data` table.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("vyper.storage.init")


def init_sqlite_store(
    data_dir: str,
    db_name: str = "store.db",
    table_name: str = "data",
    extra_sql: str = "",
) -> Optional[object]:
    """Initialize SQLite store if STORAGE_ENGINE env var is sqlite or dual.

    Args:
        data_dir:   Path to service data directory (e.g., "/data/scanner")
        db_name:    Database file name (default: "store.db")
        table_name: Default table name (default: "data")
        extra_sql:  Additional SQL to run after table creation (indexes, etc.)

    Returns:
        SimpleSQLiteStore instance, or None if storage engine is json.
    """
    storage_engine = os.environ.get("STORAGE_ENGINE", "json")
    if storage_engine not in ("sqlite", "dual"):
        return None

    try:
        from .simple_store import SimpleSQLiteStore
        from pathlib import Path

        db_path = str(Path(data_dir) / db_name)
        Path(data_dir).mkdir(parents=True, exist_ok=True)

        store = SimpleSQLiteStore(db_path=db_path, table_name=table_name)
        store.ensure_table({
            "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
            "key": "TEXT",
            "value": "TEXT",
            "created_at": "TEXT NOT NULL DEFAULT (datetime('now'))",
        })

        if extra_sql:
            for stmt in extra_sql.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    store.raw_store().execute(stmt)

        logger.info(
            "sqlite_store_initialized",
            service=os.environ.get("SERVICE_NAME", "unknown"),
            db_path=db_path,
            engine=storage_engine,
        )
        return store
    except Exception as exc:
        logger.warning("sqlite_store_init_failed", error=str(exc))
        return None
