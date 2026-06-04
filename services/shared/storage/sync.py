"""Cross-service data sync protocol.

Replaces the shared Docker volume pattern (vyper_kb, vyper_cache,
vyper_learning) with HTTP-based data synchronization.

Instead of multiple containers writing to the same shared volume
(risk of silent data loss), each service owns its own SQLite database,
and cross-service data sharing happens via explicit sync protocols.

Usage:
    # Service A (producer) — push to service B
    syncer = DataSyncer(store, SyncConfig(
        source_url="http://classifier:8000",
        target_url="http://exploit:8006",
        mode=SyncMode.PUSH,
    ))
    await syncer.start()

    # Service B (consumer) — pull from service A
    syncer = DataSyncer(store, SyncConfig(
        source_url="http://classifier:8000",
        target_url="http://exploit:8006",
        mode=SyncMode.PULL,
    ))
    await syncer.start()
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger("vyper.storage.sync")


class SyncMode(str, Enum):
    """Sync direction mode."""
    PUSH = "push"           # Source pushes data to target
    PULL = "pull"           # Source pulls data from target
    BIDIRECTIONAL = "bidirectional"  # Both push and pull


@dataclass
class SyncConfig:
    """Configuration for cross-service data synchronization.

    Attributes:
        source_url:         HTTP endpoint of the source service
        target_url:         HTTP endpoint of the target service
        sync_interval_sec:   How often to sync (seconds)
        batch_size:         Max entries per sync batch
        max_retries:        Max retry attempts per batch
        mode:               Sync direction (push/pull/bidirectional)
        table_name:         Table to sync (default: "_sync_queue")
        timeout:            HTTP request timeout (seconds)
    """
    source_url: str
    target_url: str
    sync_interval_sec: int = 300       # 5 minutes
    batch_size: int = 50
    max_retries: int = 3
    mode: SyncMode = SyncMode.PUSH
    table_name: str = "_sync_queue"
    timeout: float = 30.0


class DataSyncer:
    """HTTP-based data synchronization between services.

    Replaces the shared volume pattern. Each service maintains its own
    `_sync_queue` table for tracking which entries need to be synced.

    Sync queue table schema:
        CREATE TABLE IF NOT EXISTS _sync_queue (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,        -- e.g., "finding", "exploit_result"
            entity_id   TEXT NOT NULL,
            payload     TEXT NOT NULL,        -- JSON-encoded data
            action      TEXT NOT NULL DEFAULT 'upsert',  -- upsert | delete
            synced      INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            synced_at   TEXT
        )
    """

    def __init__(self, store: Any, config: SyncConfig) -> None:
        """Initialize syncer with store and config.

        Args:
            store: BaseStore-compatible instance for queue management
            config: Sync configuration
        """
        import httpx
        self._store = store
        self._config = config
        self._client = httpx.AsyncClient(timeout=config.timeout)
        self._task: asyncio.Task[Any] | None = None
        self._running = False

        # Stats
        self.synced_count = 0
        self.error_count = 0
        self.last_sync_at: str | None = None

        self._ensure_queue_table()

    def _ensure_queue_table(self) -> None:
        """Create sync queue table if it doesn't exist."""
        self._store.execute(f"""
            CREATE TABLE IF NOT EXISTS {self._config.table_name} (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id   TEXT NOT NULL,
                payload     TEXT NOT NULL,
                action      TEXT NOT NULL DEFAULT 'upsert',
                synced      INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                synced_at   TEXT
            )
        """)
        self._store.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{self._config.table_name}_synced
            ON {self._config.table_name}(synced)
        """)

    # ── Queue Operations ─────────────────────────────────────

    def enqueue(self, entity_type: str, entity_id: str, payload: dict[str, Any], action: str = "upsert") -> None:
        """Add an entry to the sync queue."""
        import json
        self._store.insert(self._config.table_name, {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": json.dumps(payload, default=str),
            "action": action,
            "synced": 0,
        })

    def pending_count(self) -> int:
        """Get count of unsynced entries."""
        row = self._store.query_one(
            f"SELECT COUNT(*) as cnt FROM {self._config.table_name} WHERE synced = 0"
        )
        return row["cnt"] if row else 0

    # ── Sync Loop ────────────────────────────────────────────

    async def start(self) -> None:
        """Start periodic sync loop in background."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._sync_loop())
        logger.info("DataSyncer started: mode=%s interval=%ds", self._config.mode, self._config.sync_interval_sec)

    async def stop(self) -> None:
        """Stop the sync loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._client.aclose()
        logger.info("DataSyncer stopped")

    async def _sync_loop(self) -> None:
        """Main sync loop — runs periodically."""
        while self._running:
            try:
                if self._config.mode in (SyncMode.PUSH, SyncMode.BIDIRECTIONAL):
                    await self._push_pending()
                if self._config.mode in (SyncMode.PULL, SyncMode.BIDIRECTIONAL):
                    await self._pull_updates()
                self.last_sync_at = datetime.now(timezone.utc).isoformat()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Sync loop error — will retry in %ds", self._config.sync_interval_sec)

            await asyncio.sleep(self._config.sync_interval_sec)

    async def _push_pending(self) -> None:
        """Push unsynced entries to target service."""
        entries = self._store.query_all(
            f"SELECT * FROM {self._config.table_name} WHERE synced = 0 LIMIT ?",
            (self._config.batch_size,),
        )
        if not entries:
            return

        payload = {
            "source": self._config.source_url,
            "entries": [
                {
                    "entity_type": e["entity_type"],
                    "entity_id": e["entity_id"],
                    "payload": e["payload"],
                    "action": e["action"],
                }
                for e in entries
            ],
        }

        for attempt in range(self._config.max_retries):
            try:
                response = await self._client.post(
                    f"{self._config.target_url}/sync/receive",
                    json=payload,
                    timeout=self._config.timeout,
                )
                if response.status_code == 200:
                    # Mark as synced
                    ids = [e["id"] for e in entries]
                    placeholders = ",".join("?" * len(ids))
                    self._store.execute(
                        f"UPDATE {self._config.table_name} SET synced = 1, synced_at = datetime('now') WHERE id IN ({placeholders})",
                        tuple(ids),
                    )
                    self.synced_count += len(entries)
                    logger.debug("Synced %d entries to %s", len(entries), self._config.target_url)
                    return
                else:
                    logger.warning(
                        "Sync push attempt %d/%d failed: HTTP %d",
                        attempt + 1, self._config.max_retries, response.status_code,
                    )
            except Exception:
                logger.warning(
                    "Sync push attempt %d/%d failed", attempt + 1, self._config.max_retries
                )

        self.error_count += 1

    async def _pull_updates(self) -> None:
        """Pull updates from source service and apply locally."""
        try:
            response = await self._client.get(
                f"{self._config.source_url}/sync/updates?since={self.last_sync_at or ''}",
                timeout=self._config.timeout,
            )
            if response.status_code == 200:
                data = response.json()
                entries = data.get("entries", [])
                for entry in entries:
                    # Apply entry to local store based on action
                    # This is service-specific — override in subclass
                    pass
        except Exception:
            logger.debug("Sync pull skipped (source may not support /sync/updates)")

    # ── Stats ────────────────────────────────────────────────

    @property
    def stats(self) -> dict[str, Any]:
        """Return sync statistics."""
        return {
            "mode": self._config.mode,
            "synced_count": self.synced_count,
            "error_count": self.error_count,
            "pending_count": self.pending_count(),
            "last_sync_at": self.last_sync_at,
            "source_url": self._config.source_url,
            "target_url": self._config.target_url,
        }
