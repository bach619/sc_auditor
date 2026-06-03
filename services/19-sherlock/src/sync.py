"""SyncManager for Sherlock — fetches and persists contest data."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from src.client import SherlockClient
from src.models import SyncStatus
from src.storage import load_contests, save_contest_detail, save_contests

log = structlog.get_logger()


class SyncManager:
    """Manages sync of Sherlock contest data from REST API to JSON files.

    Usage:
        mgr = SyncManager()
        status = await mgr.run_sync()
    """

    def __init__(self) -> None:
        self._syncs: dict[str, SyncStatus] = {}

    async def run_sync(self) -> SyncStatus:
        """Fetch all contests from Sherlock REST API and store as JSON files."""
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
            async with SherlockClient() as client:
                contests = await client.fetch_contests()

            existing_contests = {c["id"]: c for c in load_contests()}
            status.contests_fetched = len(contests)
            contests_new = 0
            contests_updated = 0

            serialized = []
            for unified in contests:
                item = unified.model_dump(mode="json", exclude_none=True)
                contest_id = unified.platform_id

                # Track new vs updated
                if contest_id in existing_contests:
                    contests_updated += 1
                else:
                    contests_new += 1

                serialized.append(item)

                # Also fetch detail for each contest and store separately
                try:
                    async with SherlockClient() as detail_client:
                        detail = await detail_client.fetch_contest_detail(contest_id)
                        if detail:
                            save_contest_detail(
                                contest_id,
                                detail.model_dump(mode="json", exclude_none=True),
                            )
                except Exception as e:
                    log.warning("sync.detail_error", contest_id=contest_id, error=str(e)[:80])

            # Save full list
            save_contests(serialized)

            status.contests_new = contests_new
            status.contests_updated = contests_updated
            status.status = "completed"
            status.completed_at = datetime.now(timezone.utc).isoformat()
            status.duration_seconds = round(time.monotonic() - start_time, 2)

            log.info(
                "sync.complete",
                sync_id=sync_id,
                fetched=status.contests_fetched,
                new=contests_new,
                updated=contests_updated,
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
