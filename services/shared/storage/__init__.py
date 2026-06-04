"""Vyper shared storage layer — SQLite-based data persistence.

Provides:
- SqliteStore:   Primary SQLite implementation (WAL mode, thread-safe)
- JsonStore:     JSON adapter for backward compatibility
- BaseStore:     Abstract interface for all storage backends
- StoreConfig:   Per-service storage configuration
- MigrationEngine: Schema migration management
- DataSyncer:    Cross-service sync protocol

Usage:
    from shared.storage import SqliteStore, StoreConfig

    store = SqliteStore(StoreConfig(db_path="/data/my_service/store.db"))
    store.insert("findings", {"title": "Reentrancy", "severity": "HIGH"})
    results = store.query_all("SELECT * FROM findings WHERE severity = ?", ("HIGH",))
"""

from __future__ import annotations

from .types import StoreConfig, QueryResult, StoreMode
from .base import BaseStore
from .sqlite_store import SqliteStore
from .json_store import JsonStore
from .migrations import MigrationEngine
from .sync import DataSyncer, SyncConfig, SyncMode
from .simple_store import SimpleSQLiteStore
from .service_schemas import (
    SOURCE_SCHEMA_SQL,
    AI_SCHEMA_SQL,
    AGENT_SCHEMA_SQL,
    SCANNER_SCHEMA_SQL,
)
from .init_helper import init_sqlite_store

__all__ = [
    "StoreConfig",
    "QueryResult",
    "StoreMode",
    "BaseStore",
    "SqliteStore",
    "JsonStore",
    "MigrationEngine",
    "DataSyncer",
    "SyncConfig",
    "SyncMode",
    "SimpleSQLiteStore",
    "SOURCE_SCHEMA_SQL",
    "AI_SCHEMA_SQL",
    "AGENT_SCHEMA_SQL",
    "SCANNER_SCHEMA_SQL",
    "init_sqlite_store",
]
