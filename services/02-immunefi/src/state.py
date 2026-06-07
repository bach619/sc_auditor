"""Shared state for the Immunefi service.

All route modules import from here to avoid circular imports with app.py.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import structlog

from shared.cache import CacheLayer
from shared.storage.simple_store import SimpleSQLiteStore
from shared.storage.service_schemas import SCHEMA_SQL as IMMUNEFI_SCHEMA_SQL

from src.agent_loop import ImmunefiAgent
from src.models import ApiResponse, Meta
from src.sync import SyncManager

# ── Constants ──────────────────────────────────────────────

DATA_DIR = Path("/data/immunefi")
SERVICE_NAME = "immunefi"
SERVICE_VERSION = "0.2.0"

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://11-orchestrator:8000")
SOURCE_URL = os.getenv("SOURCE_URL", "http://03-source:8000")
CONFIG_URL = os.getenv("CONFIG_URL", "http://01-config:8000")

# ── Storage Engine ─────────────────────────────────────────
# STORAGE_ENGINE: json | sqlite | dual (write to both)
STORAGE_ENGINE = os.getenv("STORAGE_ENGINE", "json")

# ── Cache ───────────────────────────────────────────────────

immunefi_cache = CacheLayer(cache_dir="/data/cache/immunefi")

# ── Sync Manager (global singleton) ───────────────────────

sync_manager = SyncManager(DATA_DIR)

# Background sync task tracking
_sync_tasks: dict[str, asyncio.Task] = {}

# Immunefi Agent (initialized in lifespan)
_immunefi_agent: ImmunefiAgent | None = None

# ── SQLite Store (for programs, contracts, history) ────────
# Initialized at startup when STORAGE_ENGINE is sqlite or dual
immunefi_sqlite_store: SimpleSQLiteStore | None = None

def init_sqlite() -> SimpleSQLiteStore | None:
    """Initialize SQLite store for Immunefi data.
    
    Creates /data/immunefi/immunefi.db with tables:
      programs, program_chains, program_history
    
    Returns store instance or None if STORAGE_ENGINE is json.
    """
    global immunefi_sqlite_store
    if STORAGE_ENGINE not in ("sqlite", "dual"):
        return None
    try:
        db_path = str(DATA_DIR / "immunefi.db")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        immunefi_sqlite_store = SimpleSQLiteStore(
            db_path=db_path,
            schema_sql=IMMUNEFI_SCHEMA_SQL,
            table_name="programs",
        )
        logger = logging.getLogger("vyper.immunefi.storage")
        logger.info(
            "immunefi_sqlite_initialized",
            db_path=db_path,
            engine=STORAGE_ENGINE,
        )
        return immunefi_sqlite_store
    except Exception as exc:
        logger = logging.getLogger("vyper.immunefi.storage")
        logger.warning("immunefi_sqlite_init_failed", error=str(exc))
        return None

def get_sqlite_health() -> dict[str, Any]:
    """Return SQLite store health status."""
    if immunefi_sqlite_store is None:
        return {"status": "not_initialized", "engine": STORAGE_ENGINE}
    try:
        return immunefi_sqlite_store.health()
    except Exception as exc:
        return {"status": "error", "error": str(exc)}

# Logger — configured by app.py via setup_observability
log: structlog.BoundLogger = structlog.get_logger(service=SERVICE_NAME)


# ── Helper ─────────────────────────────────────────────────

def ok(data: object = None) -> ApiResponse:
    """Build a standard success response."""
    return ApiResponse(data=data, meta=Meta(status="ok"))
