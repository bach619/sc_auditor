"""ConfigManagerSQLite — SQLite-backed configuration store for 01-config.

Drop-in replacement for the JSON-backed ConfigManager. Uses in-memory
cache for fast reads and SQLite for durable persistence.

Design:
- Reads: from in-memory cache (same as JSON version)
- Writes: to SQLite first, then update cache
- Thread-safe: threading.Lock for writes (same as JSON version)
- Defaults: auto-populated on first run
"""

from __future__ import annotations

import json
import threading
from typing import Any

import structlog
from shared.storage import SqliteStore, StoreConfig

from . import schema

log = structlog.get_logger()


class ConfigManagerSQLite:
    """SQLite-backed configuration manager — drop-in replacement for ConfigManager."""

    def __init__(self, db_path: str = "/data/config/config.db") -> None:
        self._lock = threading.Lock()
        self._config: dict[str, Any] = {}
        self._store = SqliteStore(StoreConfig(
            db_path=db_path,
            journal_mode="WAL",
            synchronous="NORMAL",
            cache_size=-2000,
            auto_migrate=False,
        ))
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables and seed defaults if needed."""
        for stmt in schema.SCHEMA_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                self._store.execute(stmt)

        # Check if defaults are already seeded
        count = self._store.query_one("SELECT COUNT(*) as cnt FROM settings")
        if count and count["cnt"] == 0:
            for key, value, category in schema.DEFAULT_SETTINGS:
                self._store.insert("settings", {
                    "key": key,
                    "value": value,
                    "category": category,
                })

    # ── Public API (identical to ConfigManager) ─────────────

    def load(self) -> dict[str, Any]:
        """Load all settings from SQLite into memory."""
        try:
            rows = self._store.query_all("SELECT key, value FROM settings")
            self._config = {}
            for row in rows:
                try:
                    self._config[row["key"]] = json.loads(row["value"])
                except (json.JSONDecodeError, TypeError):
                    self._config[row["key"]] = row["value"]
            log.info("config_loaded_from_sqlite", keys=len(self._config))
        except Exception as exc:
            log.error("config_sqlite_load_failed", error=str(exc))
            self._config = {}
        return dict(self._config)

    def get(self, key: str) -> Any:
        """Get a single config value from cache."""
        return self._config.get(key)

    def get_all(self) -> dict[str, Any]:
        """Return all config values."""
        return dict(self._config)

    def set(self, key: str, value: Any) -> None:
        """Set a config value — persists to SQLite then cache."""
        with self._lock:
            value_json = json.dumps(value, ensure_ascii=False)
            self._store.upsert("settings", {"key": key}, {
                "value": value_json,
                "updated_at": None,  # SQLite default will apply
            })
            self._config[key] = value

    def delete(self, key: str) -> bool:
        """Delete a config key."""
        with self._lock:
            if key not in self._config:
                return False
            self._store.delete("settings", {"key": key})
            del self._config[key]
            return True

    def reset(self) -> dict[str, Any]:
        """Reset all settings to defaults."""
        with self._lock:
            self._store.execute("DELETE FROM settings")
            for key, value, category in schema.DEFAULT_SETTINGS:
                self._store.insert("settings", {
                    "key": key,
                    "value": value,
                    "category": category,
                })
            self._config = {}
            self.load()
            log.info("config_reset_to_defaults_sqlite")
        return dict(self._config)

    def health_check(self) -> dict[str, Any]:
        """Return storage health info."""
        return self._store.health_check()
