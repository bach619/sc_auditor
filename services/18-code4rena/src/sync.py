"""SyncManager — orchestrates Code4rena data sync via GraphQL."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog

from src.client import Code4renaClient
from src.models import SyncStatus
from src.storage import (
    load_contest_detail,
    load_contests,
    save_contest_detail,
    save_contests,
)

log = structlog.get_logger()


class SyncManager:
    """Manages syncing Code4rena audit contest data via GraphQL API.

    Usage:
        mgr = SyncManager()
        status = await mgr.run_sync()
        current_status = mgr.get_status()
    """

    def __init__(self) -> None:
        self._latest_sync: SyncStatus | None = None
        self._contests_cache: list[dict] = []
        self._detail_cache: dict[str, dict] = {}

    # ── Public API ──────────────────────────────────────────

    async def run_sync(self) -> SyncStatus:
        """Fetch contests from Code4rena GraphQL API and persist to JSON files.

        Workflow:
          1. Fetch all active/upcoming contests
          2. Fetch detail (scope) for each contest
          3. Save contest list + per-contest detail files
          4. Track new vs updated contests
        """
        sync_id = uuid.uuid4().hex[:12]
        started = datetime.now(timezone.utc)
        errors: list[str] = []
        contests_new = 0
        contests_updated = 0

        status = SyncStatus(
            sync_id=sync_id,
            status="running",
            started_at=started.isoformat(),
        )
        self._latest_sync = status

        client = Code4renaClient()
        try:
            # Step 1: Load existing contests for diffing
            existing = load_contests()
            existing_ids = {c.get("id") for c in existing}

            # Step 2: Fetch contests from GraphQL (active + upcoming)
            all_contests: list[dict] = []

            active_contests = await client.fetch_contests(status="active")
            all_contests.extend(active_contests)
            log.info("sync.fetched_active", count=len(active_contests))

            upcoming_contests = await client.fetch_contests(status="upcoming")
            all_contests.extend(upcoming_contests)
            log.info("sync.fetched_upcoming", count=len(upcoming_contests))

            # Deduplicate by id
            seen: dict[str, dict] = {}
            for c in all_contests:
                cid = c.get("id")
                if cid:
                    seen[cid] = c
            all_contests = list(seen.values())

            status.contests_fetched = len(all_contests)

            # Step 3: Count new vs updated
            for c in all_contests:
                cid = c.get("id")
                if cid in existing_ids:
                    contests_updated += 1
                else:
                    contests_new += 1

            status.contests_new = contests_new
            status.contests_updated = contests_updated

            # Step 4: Fetch detail for each contest and save
            self._contests_cache = all_contests
            self._detail_cache = {}
            for contest in all_contests:
                cid = contest.get("id")
                if not cid:
                    continue
                try:
                    detail = await client.fetch_contest_detail(cid)
                    if detail:
                        self._detail_cache[cid] = detail
                        save_contest_detail(cid, detail)
                    else:
                        self._detail_cache[cid] = contest
                        save_contest_detail(cid, contest)
                except Exception as e:
                    msg = f"Detail fetch failed for {cid}: {e}"
                    errors.append(msg)
                    log.warning("sync.detail_failed", contest_id=cid, error=str(e))

            # Step 5: Save contest list
            save_contests(all_contests)

            now = datetime.now(timezone.utc)
            status.status = "completed"
            status.completed_at = now.isoformat()
            status.errors = errors

        except Exception as e:
            log.error("sync.failed", error=str(e))
            now = datetime.now(timezone.utc)
            status.status = "failed"
            status.completed_at = now.isoformat()
            status.errors.append(str(e))
        finally:
            await client.close()

        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        status.duration_seconds = round(elapsed, 2)

        self._latest_sync = status
        log.info(
            "sync.complete",
            sync_id=sync_id,
            fetched=status.contests_fetched,
            new=status.contests_new,
            updated=status.contests_updated,
            duration=status.duration_seconds,
        )

        return status

    def get_status(self) -> SyncStatus | None:
        """Return the latest sync status."""
        return self._latest_sync

    def get_contest_by_id(self, contest_id: str) -> dict | None:
        """Get a contest by ID, preferring cached detail over list data."""
        if contest_id in self._detail_cache:
            return self._detail_cache[contest_id]
        detail = load_contest_detail(contest_id)
        if detail:
            self._detail_cache[contest_id] = detail
            return detail
        return None

    def get_all_contests(self) -> list[dict]:
        """Get all cached contests (list-level data)."""
        if self._contests_cache:
            return self._contests_cache
        self._contests_cache = load_contests()
        return self._contests_cache
