# Vyper Storage Layer — SQLite-based Data Persistence

> Zero-dependency, thread-safe, ACID-compliant storage for Vyper microservices.

## Quick Start

```python
from services.shared.storage import SqliteStore, StoreConfig

# 1. Configure
config = StoreConfig(
    db_path="/data/my_service/store.db",
    journal_mode="WAL",          # Concurrent reads + 1 writer
    synchronous="NORMAL",        # Good performance, safe on crash
    cache_size=-20000,           # 20 MB page cache
)

# 2. Initialize
store = SqliteStore(config)

# 3. Create tables
store.create_table("findings", {
    "id": "TEXT PRIMARY KEY",
    "title": "TEXT NOT NULL",
    "severity": "TEXT NOT NULL",
    "created_at": "TEXT NOT NULL DEFAULT (datetime('now'))",
})

# 4. CRUD
row_id = store.insert("findings", {
    "id": "abc-123",
    "title": "Reentrancy in Vault.withdraw()",
    "severity": "HIGH",
})

findings = store.query_all(
    "SELECT * FROM findings WHERE severity = ? ORDER BY created_at DESC",
    ("HIGH",),
)

# 5. Maintenance
health = store.health_check()  # {"status": "ok", "table_count": 1, ...}
store.backup("/data/backups/store_backup.db")
store.vacuum()
store.close()
```

## Architecture

```
services/shared/storage/
├── __init__.py          # Public API: SqliteStore, JsonStore, BaseStore
├── types.py             # StoreConfig, QueryResult, StoreMode
├── base.py              # Abstract BaseStore interface (ABC)
├── sqlite_store.py      # Primary: SQLite + WAL mode
├── json_store.py        # Backward compat: JSON files
├── migrations.py        # Schema migration engine
└── sync.py              # Cross-service data sync (HTTP)
```

## Running Tests

```bash
# All storage tests
pytest tests/test_sqlite_store.py tests/test_json_store.py tests/test_migrations.py -v

# Specific test
pytest tests/test_sqlite_store.py::TestCRUD::test_insert_and_query_all -v
```

## Cross-Service Sync

Replace shared Docker volumes with HTTP sync protocol:

```python
from services.shared.storage import DataSyncer, SyncConfig

syncer = DataSyncer(store, SyncConfig(
    source_url="http://classifier:8000",
    target_url="http://exploit:8006",
    sync_interval_sec=300,      # Every 5 minutes
    batch_size=50,
    mode=SyncMode.PUSH,
))
syncer.enqueue("finding", "abc-123", {"severity": "HIGH", "title": "..."})
await syncer.start()
```

## Migration from JSON

Use dual-write mode during transition:

```python
import os
from services.shared.storage import SqliteStore, JsonStore, StoreConfig, StoreMode

mode = StoreMode(os.getenv("STORAGE_ENGINE", "dual"))

sqlite = SqliteStore(StoreConfig(db_path="/data/service/store.db", mode=mode))
json = JsonStore(StoreConfig(db_path="/data/service/store.db", mode=mode))

# Write to both during migration
if mode in (StoreMode.SQLITE, StoreMode.DUAL):
    sqlite.insert("findings", data)
if mode in (StoreMode.JSON, StoreMode.DUAL):
    json.insert("findings", data)
```

## Configuration Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `db_path` | (required) | Full path to `.db` file |
| `journal_mode` | `WAL` | WAL / DELETE / MEMORY |
| `synchronous` | `NORMAL` | OFF(0) / NORMAL(1) / FULL(2) |
| `cache_size` | `-20000` | Page cache in KB (negative = KB) |
| `busy_timeout` | `5000` | Wait time in ms |
| `foreign_keys` | `True` | Enforce FK constraints |
| `auto_migrate` | `True` | CREATE TABLE IF NOT EXISTS |

## Design Decisions

1. **SQLite per service** — not centralized. Same pattern as existing JSON volumes: 1 service = 1 volume = 1 `.db` file. Zero additional Docker services.

2. **Threading.local()** — thread-safe connections without connection pooling overhead. Each thread gets its own `sqlite3.Connection`.

3. **Write lock + WAL mode** — `BEGIN IMMEDIATE` with `threading.Lock` prevents SQLITE_BUSY within the same process. WAL allows concurrent reads without blocking.

4. **No cross-process write** — each DB file is mounted by exactly ONE container. No shared volume write contention.
