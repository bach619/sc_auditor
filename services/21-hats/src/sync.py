"""SyncManager for Hats Finance — fetches and persists vault data."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from src.client import HatsFinanceClient
from src.models import SyncStatus
from src.storage import load_vaults, save_vault_detail, save_vaults

log = structlog.get_logger()


class SyncManager:
    """Manages sync of Hats Finance vault data from REST API to JSON files.

    Usage:
        mgr = SyncManager()
        status = await mgr.run_sync()
    """

    def __init__(self) -> None:
        self._syncs: dict[str, SyncStatus] = {}

    async def run_sync(self) -> SyncStatus:
        """Fetch all vaults from Hats Finance REST API and store as JSON files."""
        sync_id = uuid.uuid4().hex[:12]
        started_at = datetime.now(timezone.utc).isoformat()
        start_time = time.monotonic()

        status = SyncStatus(
            sync_id=sync_id,
            status="running",
            started_at=started_at,
        )
        self._syncs[sync_id] = status

        log.info("sync.start", sync_id=sync_id)

        try:
            async with HatsFinanceClient() as client:
                vaults = await client.fetch_vaults()

            existing_vaults = {v["id"]: v for v in load_vaults()}
            status.vaults_fetched = len(vaults)
            vaults_new = 0
            vaults_updated = 0

            serialized = []
            for unified in vaults:
                item = unified.model_dump(mode="json", exclude_none=True)
                vault_id = unified.platform_id

                if vault_id in existing_vaults:
                    vaults_updated += 1
                else:
                    vaults_new += 1

                serialized.append(item)

                try:
                    async with HatsFinanceClient() as detail_client:
                        detail = await detail_client.fetch_vault_detail(vault_id)
                        if detail:
                            save_vault_detail(
                                vault_id,
                                detail.model_dump(mode="json", exclude_none=True),
                            )
                except Exception as e:
                    log.warning("sync.detail_error", vault_id=vault_id, error=str(e)[:80])

            save_vaults(serialized)

            status.vaults_new = vaults_new
            status.vaults_updated = vaults_updated
            status.status = "completed"
            status.completed_at = datetime.now(timezone.utc).isoformat()
            status.duration_seconds = round(time.monotonic() - start_time, 2)

            log.info(
                "sync.complete",
                sync_id=sync_id,
                fetched=status.vaults_fetched,
                new=vaults_new,
                updated=vaults_updated,
                duration=status.duration_seconds,
            )

        except Exception as e:
            status.status = "failed"
            status.completed_at = datetime.now(timezone.utc).isoformat()
            status.errors.append(str(e))
            status.duration_seconds = round(time.monotonic() - start_time, 2)
            log.error("sync.failed", sync_id=sync_id, error=str(e))

        self._syncs[sync_id] = status
        return status

    def get_status(self, sync_id: str) -> SyncStatus | None:
        """Get the status of a sync operation by ID."""
        return self._syncs.get(sync_id)
