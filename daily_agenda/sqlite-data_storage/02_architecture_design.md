# 02 — Architecture Design: SQLite Store Abstraction & Schemas

> **Agenda**: 27 — SQLite Data Storage
> **Bagian**: 2 dari 4
> **Tipe**: Technical Design → Implementation Blueprint
> **Tanggal**: 2026-06-04

---

## 1. Shared Library: `services/shared/storage/`

### 1.1 File Structure

```
services/shared/storage/
├── __init__.py              # Public API exports
├── base.py                  # Abstract BaseStore (interface)
├── sqlite_store.py          # SqliteStore implementation (primary)
├── json_store.py            # JsonStore adapter (backward compat)
├── migrations.py            # Schema migration engine
├── sync.py                  # Cross-service sync protocol
├── types.py                 # Shared types (StoreConfig, QueryResult, etc.)
└── README.md                # Usage documentation
```

### 1.2 Abstract Interface: `base.py`

```python
"""BaseStore — Abstract interface untuk semua storage backend."""

from abc import ABC, abstractmethod
from typing import Any, Optional, Generator
from dataclasses import dataclass, field

@dataclass
class StoreConfig:
    """Konfigurasi per service."""
    db_path: str                           # /data/{service}/store.db
    journal_mode: str = "WAL"              # WAL | DELETE | MEMORY
    synchronous: str = "NORMAL"            # OFF | NORMAL | FULL
    cache_size: int = -20000               # 20MB cache (negative = KB)
    busy_timeout: int = 5000               # 5 detik timeout
    foreign_keys: bool = True
    auto_migrate: bool = True              # CREATE TABLE IF NOT EXISTS
    backup_enabled: bool = False
    backup_path: Optional[str] = None

@dataclass
class QueryResult:
    rows: list[dict[str, Any]]
    row_count: int
    last_row_id: Optional[int] = None
    query_time_ms: float = 0.0

class BaseStore(ABC):
    """Interface abstrak — semua storage backend implement ini."""

    @abstractmethod
    def execute(self, sql: str, params: tuple = ()) -> QueryResult:
        """Execute arbitrary SQL. Return result + metadata."""
        ...

    @abstractmethod
    def execute_many(self, sql: str, params_list: list[tuple]) -> int:
        """Batch execute. Return row count affected."""
        ...

    @abstractmethod
    def query_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Return single row or None."""
        ...

    @abstractmethod
    def query_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """Return all matching rows."""
        ...

    @abstractmethod
    def insert(self, table: str, data: dict) -> int:
        """INSERT INTO table VALUES (data). Return last row id."""
        ...

    @abstractmethod
    def update(self, table: str, where: dict, data: dict) -> int:
        """UPDATE table SET data WHERE where. Return rows affected."""
        ...

    @abstractmethod
    def delete(self, table: str, where: dict) -> int:
        """DELETE FROM table WHERE where. Return rows affected."""
        ...

    @abstractmethod
    def table_exists(self, table: str) -> bool:
        """Check if table exists."""
        ...

    @abstractmethod
    def health_check(self) -> dict:
        """Return store health: size, table count, integrity check."""
        ...

    @abstractmethod
    def vacuum(self) -> None:
        """Reclaim storage space after deletes."""
        ...

    @abstractmethod
    def backup(self, backup_path: str) -> None:
        """Create backup via sqlite3 .backup API."""
        ...
```

### 1.3 SQLite Implementation: `sqlite_store.py`

```python
"""SqliteStore — SQLite implementation of BaseStore.

Thread-safe via threading.local(). WAL mode for concurrent reads.
Designed for single-service, single-writer pattern.
"""

import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

from .base import BaseStore, StoreConfig, QueryResult


class SqliteStore(BaseStore):
    """Production-grade SQLite store for VYPER services."""

    def __init__(self, config: StoreConfig):
        self._config = config
        self._local = threading.local()
        self._write_lock = threading.Lock()
        self._migrations_applied = set()
        
        # Ensure directory exists
        Path(config.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize connection pool & schema
        self._init_connection()
        if config.auto_migrate:
            self._auto_migrate()

    # ─── Connection Management ───────────────────────────

    def _init_connection(self):
        """Initialize the thread-local connection with PRAGMA settings."""
        conn = self._get_conn()  # Triggers lazy init
        self._apply_pragmas(conn)

    def _get_conn(self) -> sqlite3.Connection:
        """Thread-safe connection factory. Lazy init per thread."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                self._config.db_path,
                timeout=self._config.busy_timeout / 1000.0,
                check_same_thread=False,  # threading.local() handles this
            )
            conn.row_factory = sqlite3.Row
            conn.execute(f"PRAGMA journal_mode={self._config.journal_mode}")
            conn.execute(f"PRAGMA synchronous={self._config.synchronous}")
            conn.execute(f"PRAGMA cache_size={self._config.cache_size}")
            if self._config.foreign_keys:
                conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return self._local.conn

    def _apply_pragmas(self, conn: sqlite3.Connection):
        """Apply performance & safety PRAGMAs."""
        conn.execute("PRAGMA busy_timeout = 5000")       # Wait up to 5s
        conn.execute("PRAGMA mmap_size = 268435456")      # 256MB memory map
        conn.execute("PRAGMA temp_store = MEMORY")         # Temp tables in RAM
        conn.execute("PRAGMA optimize")                    # Run optimizations

    def _get_conn_write(self) -> sqlite3.Connection:
        """Get connection for write operations (uses lock for safety)."""
        return self._get_conn()

    # ─── CRUD Operations ────────────────────────────────

    def execute(self, sql: str, params: tuple = ()) -> QueryResult:
        start = time.perf_counter()
        conn = self._get_conn()
        with self._write_lock:  # Single writer at a time
            conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = conn.execute(sql, params)
                rows = [dict(r) for r in cursor.fetchall()]
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        
        elapsed = (time.perf_counter() - start) * 1000
        return QueryResult(
            rows=rows,
            row_count=len(rows),
            last_row_id=cursor.lastrowid,
            query_time_ms=round(elapsed, 2)
        )

    def execute_many(self, sql: str, params_list: list[tuple]) -> int:
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

    def query_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        conn = self._get_conn()
        conn.execute("BEGIN")
        cursor = conn.execute(sql, params)
        row = cursor.fetchone()
        conn.commit()
        return dict(row) if row else None

    def query_all(self, sql: str, params: tuple = ()) -> list[dict]:
        conn = self._get_conn()
        conn.execute("BEGIN")
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        conn.commit()
        return [dict(r) for r in rows]

    def insert(self, table: str, data: dict) -> int:
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        result = self.execute(sql, tuple(data.values()))
        return result.last_row_id

    def update(self, table: str, where: dict, data: dict) -> int:
        set_clause = ", ".join(f"{k} = ?" for k in data)
        where_clause = " AND ".join(f"{k} = ?" for k in where)
        sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        result = self.execute(sql, tuple(data.values()) + tuple(where.values()))
        return result.row_count

    def delete(self, table: str, where: dict) -> int:
        where_clause = " AND ".join(f"{k} = ?" for k in where)
        sql = f"DELETE FROM {table} WHERE {where_clause}"
        result = self.execute(sql, tuple(where.values()))
        return result.row_count

    def table_exists(self, table: str) -> bool:
        row = self.query_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        return row is not None

    # ─── Maintenance ─────────────────────────────────────

    def health_check(self) -> dict:
        db_path = Path(self._config.db_path)
        integrity = self.query_one("PRAGMA integrity_check")
        size_bytes = db_path.stat().st_size if db_path.exists() else 0
        table_count = self.query_one(
            "SELECT COUNT(*) as cnt FROM sqlite_master WHERE type='table'"
        )
        wal_size = (
            Path(f"{self._config.db_path}-wal").stat().st_size
            if Path(f"{self._config.db_path}-wal").exists() else 0
        )
        return {
            "status": "ok" if integrity["integrity_check"] == "ok" else "corrupt",
            "db_size_mb": round(size_bytes / (1024 * 1024), 2),
            "wal_size_mb": round(wal_size / (1024 * 1024), 2),
            "table_count": table_count["cnt"],
            "journal_mode": self._config.journal_mode,
        }

    def vacuum(self):
        """Reclaim space after heavy delete operations."""
        self.execute("PRAGMA optimize")
        self.execute("VACUUM")

    def backup(self, backup_path: str):
        """Atomic backup using SQLite backup API."""
        import shutil
        tmp = backup_path + ".tmp"
        source = sqlite3.connect(self._config.db_path)
        dest = sqlite3.connect(tmp)
        source.backup(dest)
        dest.close()
        source.close()
        shutil.move(tmp, backup_path)

    # ─── Schema Migration ────────────────────────────────

    def _auto_migrate(self):
        """Run any pending migrations."""
        from .migrations import MigrationEngine
        engine = MigrationEngine(self)
        engine.run_pending()

    def close(self):
        """Close all thread-local connections."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
```

### 1.4 JSON Compatibility Adapter: `json_store.py`

```python
"""JsonStore — JSON adapter implementing BaseStore for backward compat."""

import json
from pathlib import Path
from typing import Optional
from .base import BaseStore, StoreConfig, QueryResult


class JsonStore(BaseStore):
    """JSON-based store for backward compatibility & dual-write.
    
    Not meant for production queries — only for migration fallback.
    """

    def __init__(self, config: StoreConfig):
        self._data_dir = Path(config.db_path).parent / "json"
        self._data_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, table: str) -> Path:
        return self._data_dir / f"{table}.json"

    def _read_table(self, table: str) -> list[dict]:
        path = self._file_path(table)
        if not path.exists():
            return []
        return json.loads(path.read_text())

    def _write_table(self, table: str, rows: list[dict]):
        path = self._file_path(table)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rows, indent=2, default=str))
        tmp.replace(path)

    # Implement BaseStore methods (simplified)
    def insert(self, table: str, data: dict) -> int:
        rows = self._read_table(table)
        row_id = len(rows) + 1
        data["_rowid"] = row_id
        rows.append(data)
        self._write_table(table, rows)
        return row_id

    # ... (other BaseStore methods follow same pattern)
```

---

## 2. Schema Migration Engine: `migrations.py`

```python
"""Schema migration engine — auto-apply pending migrations."""

import re
from datetime import datetime
from typing import Callable


class Migration:
    def __init__(self, version: int, name: str, up: Callable, down: Callable):
        self.version = version
        self.name = name
        self.up = up
        self.down = down


class MigrationEngine:
    def __init__(self, store):
        self.store = store
        self._ensure_migrations_table()

    def _ensure_migrations_table(self):
        self.store.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                version     INTEGER PRIMARY KEY,
                name        TEXT NOT NULL,
                applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
                checksum    TEXT
            )
        """)

    def applied_versions(self) -> set[int]:
        rows = self.store.query_all("SELECT version FROM _migrations")
        return {r["version"] for r in rows}

    def run_pending(self, migrations: list[Migration]) -> list[int]:
        applied = self.applied_versions()
        new = []
        for m in sorted(migrations, key=lambda x: x.version):
            if m.version not in applied:
                m.up(self.store)
                self.store.insert("_migrations", {
                    "version": m.version,
                    "name": m.name,
                    "checksum": None
                })
                new.append(m.version)
        return new
```

---

## 3. Cross-Service Sync Protocol: `sync.py`

```python
"""Cross-service data sync — replaces shared volume pattern."""

import asyncio
import httpx
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass
from enum import Enum


class SyncMode(str, Enum):
    PUSH = "push"       # Service pushes data to target
    PULL = "pull"       # Service pulls data from target
    BIDIRECTIONAL = "bidirectional"


@dataclass
class SyncConfig:
    source_url: str          # HTTP endpoint of source service
    target_url: str          # HTTP endpoint of target service
    sync_interval_sec: int = 300    # 5 minutes
    batch_size: int = 50
    mode: SyncMode = SyncMode.PUSH


class DataSyncer:
    """Replaces shared volume writes with HTTP-based sync."""

    def __init__(self, store, config: SyncConfig):
        self.store = store
        self.config = config
        self._client = httpx.AsyncClient(timeout=30.0)
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start periodic sync loop."""
        self._task = asyncio.create_task(self._sync_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()

    async def _sync_loop(self):
        while True:
            try:
                await self._flush_pending()
            except Exception as e:
                # Log error, continue loop
                pass
            await asyncio.sleep(self.config.sync_interval_sec)

    async def _flush_pending(self):
        """Push pending entries to target service."""
        entries = self.store.query_all(
            "SELECT * FROM _sync_queue WHERE synced = 0 LIMIT ?",
            (self.config.batch_size,)
        )
        if not entries:
            return
        
        response = await self._client.post(
            f"{self.config.target_url}/sync/receive",
            json={"entries": entries}
        )
        if response.status_code == 200:
            ids = [e["id"] for e in entries]
            self.store.execute(
                f"UPDATE _sync_queue SET synced = 1 WHERE id IN ({','.join('?'*len(ids))})",
                tuple(ids)
            )
```

---

## 4. Per-Service Database Schemas

### 4.1 01-config: `config.db`

```sql
-- Runtime configuration (replaces /data/config/config.json)
CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,      -- JSON-encoded value
    category    TEXT NOT NULL DEFAULT 'general',
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS api_keys (
    provider    TEXT PRIMARY KEY,    -- openai | anthropic | infura | alchemy
    key_hash    TEXT NOT NULL,       -- SHA256 hash of key
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_settings_category ON settings(category);
```

### 4.2 02-immunefi: `programs.db`

```sql
CREATE TABLE IF NOT EXISTS programs (
    slug            TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    url             TEXT NOT NULL,
    max_bounty      TEXT,           -- "$2,500,000" as string
    platform        TEXT DEFAULT 'immunefi',
    last_updated    TEXT NOT NULL DEFAULT (datetime('now')),
    chain           TEXT,
    status          TEXT DEFAULT 'active',  -- active | inactive | archived
    metadata_json   TEXT            -- Full JSON blob for extra fields
);

CREATE TABLE IF NOT EXISTS program_chains (
    program_slug    TEXT NOT NULL,
    chain           TEXT NOT NULL,   -- ethereum | arbitrum | polygon | ...
    PRIMARY KEY (program_slug, chain),
    FOREIGN KEY (program_slug) REFERENCES programs(slug)
);

CREATE TABLE IF NOT EXISTS program_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    program_slug    TEXT NOT NULL,
    change_type     TEXT NOT NULL,  -- created | updated | new_contract | status_change
    old_value       TEXT,
    new_value       TEXT,
    changed_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (program_slug) REFERENCES programs(slug)
);

CREATE INDEX IF NOT EXISTS idx_programs_chain ON programs(chain);
CREATE INDEX IF NOT EXISTS idx_programs_status ON programs(status);
CREATE INDEX IF NOT EXISTS idx_history_slug ON program_history(program_slug);
```

### 4.3 07-classifier: `findings.db`

```sql
CREATE TABLE IF NOT EXISTS findings (
    id              TEXT PRIMARY KEY,   -- UUID
    audit_id        TEXT NOT NULL,
    scanner         TEXT NOT NULL,      -- slither | mythril | echidna | halmos | manticore
    title           TEXT NOT NULL,
    description     TEXT,
    severity        TEXT NOT NULL,      -- CRITICAL | HIGH | MEDIUM | LOW | INFO
    contract_file   TEXT NOT NULL,
    line_start      INTEGER,
    line_end        INTEGER,
    confidence      REAL DEFAULT 0.0,   -- 0.0 - 1.0
    raw_output      TEXT,               -- Raw scanner output (JSON)
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (audit_id) REFERENCES audits(id)
);

CREATE TABLE IF NOT EXISTS classifications (
    finding_id      TEXT PRIMARY KEY,
    verdict         TEXT NOT NULL,      -- TP | FP | TN | FN
    ai_verdict      TEXT,               -- AI initial verdict
    ai_confidence   REAL,
    human_verdict   TEXT,               -- After human review
    human_reviewed  INTEGER DEFAULT 0,
    exploit_tested  INTEGER DEFAULT 0,
    exploit_result  TEXT,               -- JSON: {success, tx_hash, profit, ...}
    classified_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (finding_id) REFERENCES findings(id)
);

CREATE TABLE IF NOT EXISTS metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id        TEXT NOT NULL,
    metric_name     TEXT NOT NULL,       -- true_positive_rate | precision | f1_score
    metric_value    REAL NOT NULL,
    calculated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
CREATE INDEX IF NOT EXISTS idx_findings_audit ON findings(audit_id);
CREATE INDEX IF NOT EXISTS idx_findings_scanner ON findings(scanner);
CREATE INDEX IF NOT EXISTS idx_findings_confidence ON findings(confidence);
CREATE INDEX IF NOT EXISTS idx_classifications_verdict ON classifications(verdict);
```

### 4.4 11-orchestrator: `audits.db`

```sql
CREATE TABLE IF NOT EXISTS audits (
    id              TEXT PRIMARY KEY,
    program_slug    TEXT NOT NULL,
    status          TEXT NOT NULL,       -- PENDING | FETCHING | ... | COMPLETED
    chain           TEXT NOT NULL,
    contract_address TEXT NOT NULL,
    priority        INTEGER DEFAULT 0,
    retry_count     INTEGER DEFAULT 0,
    max_retries     INTEGER DEFAULT 3,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS pipeline_steps (
    audit_id        TEXT NOT NULL,
    step_name       TEXT NOT NULL,       -- FETCHING_SOURCE | SCANNING | AI_ANALYSIS | ...
    status          TEXT NOT NULL,       -- PENDING | RUNNING | COMPLETED | FAILED
    started_at      TEXT,
    completed_at    TEXT,
    error_message   TEXT,
    attempt         INTEGER DEFAULT 1,
    PRIMARY KEY (audit_id, step_name),
    FOREIGN KEY (audit_id) REFERENCES audits(id)
);

CREATE TABLE IF NOT EXISTS audit_data (
    audit_id        TEXT PRIMARY KEY,
    source_code     TEXT,                -- Full Solidity source
    scanner_results TEXT,                -- JSON: aggregated scanner findings
    ai_analysis     TEXT,                -- JSON: AI analysis output
    exploit_results TEXT,                -- JSON: PoC exploit results
    report_json     TEXT,                -- JSON: report structure
    FOREIGN KEY (audit_id) REFERENCES audits(id)
);

CREATE TABLE IF NOT EXISTS scan_metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id        TEXT,
    scanner         TEXT NOT NULL,
    duration_ms     INTEGER NOT NULL,
    findings_count  INTEGER DEFAULT 0,
    scanned_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (audit_id) REFERENCES audits(id)
);

CREATE INDEX IF NOT EXISTS idx_audits_status ON audits(status);
CREATE INDEX IF NOT EXISTS idx_audits_program ON audits(program_slug);
CREATE INDEX IF NOT EXISTS idx_audits_created ON audits(created_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_step_status ON pipeline_steps(status);
```

### 4.5 08-exploit: `exploit.db`

```sql
CREATE TABLE IF NOT EXISTS exploit_attempts (
    id              TEXT PRIMARY KEY,
    finding_id      TEXT NOT NULL,
    audit_id        TEXT NOT NULL,
    status          TEXT NOT NULL,       -- PENDING | FORKING | EXPLOITING | SUCCESS | FAILED
    chain           TEXT NOT NULL,
    rpc_url         TEXT NOT NULL,
    block_number    INTEGER,
    impersonate_addr TEXT,
    profit_wei      TEXT,               -- Big number as string
    tx_hash         TEXT,
    contract_addr   TEXT NOT NULL,
    exploit_code    TEXT,               -- Solidity exploit code
    error_message   TEXT,
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_exploit_finding ON exploit_attempts(finding_id);
CREATE INDEX IF NOT EXISTS idx_exploit_status ON exploit_attempts(status);
```

### 4.6 06-ai: `ai_cache.db`

```sql
CREATE TABLE IF NOT EXISTS analysis_cache (
    content_hash    TEXT PRIMARY KEY,    -- SHA256 hash of input
    prompt_template TEXT NOT NULL,
    model           TEXT NOT NULL,       -- gpt-4 | claude-3-opus
    response        TEXT NOT NULL,       -- JSON-encoded AI response
    tokens_used     INTEGER,
    cost_usd        REAL,
    ttl_seconds     INTEGER DEFAULT 604800,  -- 7 days
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at      TEXT GENERATED ALWAYS AS (datetime(created_at, '+' || ttl_seconds || ' seconds')) STORED
);

CREATE INDEX IF NOT EXISTS idx_ai_cache_expires ON analysis_cache(expires_at);
```

---

## 5. Usage Pattern: Service Implementation

### 5.1 Standard Service Bootstrap

```python
# services/XX-service/app.py

from shared.storage import SqliteStore, StoreConfig

# One-time store initialization at module level
store_cfg = StoreConfig(
    db_path="/data/scanner/store.db",
    journal_mode="WAL",
    synchronous="NORMAL",
    cache_size=-20000,      # 20MB
    busy_timeout=5000,
    auto_migrate=True,
)

store = SqliteStore(store_cfg)

# Define migrations
migrations = [
    Migration(1, "create_findings_table", up_create, down_drop),
    Migration(2, "add_confidence_index", up_add_index, down_drop_index),
]

@app.on_event("startup")
async def startup():
    store._auto_migrate()  # or: engine.run_pending(migrations)
    logger.info("SQLite store initialized", health=store.health_check())

@app.on_event("shutdown")
async def shutdown():
    store.vacuum()
    store.backup("/data/scanner/backups/latest.db")
    store.close()

# Usage in endpoints
@app.post("/findings")
async def create_finding(finding: FindingCreate):
    row_id = store.insert("findings", finding.dict())
    return {"id": row_id}

@app.get("/findings")
async def list_findings(severity: str = None):
    if severity:
        return store.query_all(
            "SELECT * FROM findings WHERE severity = ? ORDER BY created_at DESC",
            (severity,)
        )
    return store.query_all("SELECT * FROM findings ORDER BY created_at DESC LIMIT 100")
```

### 5.2 Dual-Write Pattern (Migration Phase)

```python
# services/XX-service/store_dual.py

class DualWriteStore:
    """Write to SQLite (primary) + JSON (fallback) during migration."""

    def __init__(self, sqlite_store: SqliteStore, json_store: JsonStore):
        self.sqlite = sqlite_store
        self.json = json_store
        self.mode = os.getenv("STORAGE_MODE", "sqlite")  # sqlite | json | dual

    async def insert(self, table: str, data: dict) -> int:
        row_id = None
        if self.mode in ("sqlite", "dual"):
            try:
                row_id = self.sqlite.insert(table, data)
            except Exception as e:
                logger.error("sqlite_insert_failed", table=table, error=str(e))
                if self.mode == "sqlite":
                    raise
        
        if self.mode in ("json", "dual"):
            try:
                self.json.insert(table, data)
            except Exception as e:
                logger.error("json_insert_failed", table=table, error=str(e))
        
        return row_id

    async def query_all(self, sql: str, params: tuple = ()) -> list[dict]:
        if self.mode in ("sqlite", "dual"):
            try:
                return self.sqlite.query_all(sql, params)
            except Exception:
                pass
        # Fallback to JSON
        return self._json_fallback_query(sql, params)
```

---

## 6. Docker Compose Changes (Minimal)

```yaml
# docker-compose.yml — ONLY add environment variable per service
services:
  07-classifier:
    build: ./services/07-classifier
    volumes:
      - vyper_classifier:/data/classifier  # ← Sama seperti JSON — file .db di sini
    environment:
      - STORAGE_ENGINE=sqlite              # ← Satu-satunya perubahan
      # - STORAGE_ENGINE=dual             # Selama migrasi
      # - STORAGE_ENGINE=json             # Rollback instant
```

---

*Agenda 27 — Bagian 2/4 | Architecture Design*
