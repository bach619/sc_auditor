"""Sync management routes."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query

from shared.cache import IMMUNEFI_PROGS_CACHE, TTL_IMMUNEFI_PROGS

from src.models import ApiResponse, SyncStatus
from src.state import _sync_tasks, immunefi_cache, log, ok, sync_manager

router = APIRouter()


@router.post("/sync")
async def trigger_sync() -> ApiResponse:
    """Trigger a full sync from Immunefi GitHub mirror (async).

    Dispatches a background task and returns a sync_id
    that can be polled via GET /sync/{sync_id}.
    """
    sync_id = str(uuid.uuid4())

    async def _run_sync(sid: str) -> None:
        """Background sync task."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                status = await sync_manager.sync_all(client=client)
                sync_manager._syncs[sid] = status
        except Exception as e:
            log.error("sync.background_failed", sync_id=sid, error=str(e))
            if sid in sync_manager._syncs:
                sync_manager._syncs[sid].status = "failed"

    # Track the in-progress sync
    sync_manager._syncs[sync_id] = SyncStatus(
        sync_id=sync_id,
        status="running",
        programs_synced=0,
        total=0,
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=None,
    )

    task = asyncio.create_task(_run_sync(sync_id))
    _sync_tasks[sync_id] = task
    # Cleanup old task ref on completion
    task.add_done_callback(lambda _: _sync_tasks.pop(sync_id, None))

    return ok({"sync_id": sync_id, "status": "running"})


@router.post("/sync/run")
async def run_sync() -> ApiResponse:
    """Execute a full sync synchronously (blocking — may take minutes).

    Returns the completed SyncStatus.
    """
    # Check cache
    cached = await immunefi_cache.get(IMMUNEFI_PROGS_CACHE, {"programs": "list"})
    if cached is not None:
        log.info("immunefi.cache_hit", source="programs")
        return ok(cached)

    log.info("sync.manual_trigger")
    async with httpx.AsyncClient(timeout=60.0) as client:
        status = await sync_manager.sync_all(client=client)

    # Cache the results (convert SyncStatus → dict for JSON serialization)
    status_dict = status.model_dump() if hasattr(status, "model_dump") else status
    await immunefi_cache.set(IMMUNEFI_PROGS_CACHE, {"programs": "list"}, status_dict, ttl_seconds=TTL_IMMUNEFI_PROGS)

    return ok(status)


@router.get("/sync/{sync_id}")
async def get_sync(sync_id: str) -> ApiResponse:
    """Check the status of a sync operation."""
    status = sync_manager.get_sync_status(sync_id)
    if not status:
        raise HTTPException(
            status_code=404,
            detail=f"Sync '{sync_id}' not found. Sync IDs are only valid during a running sync.",
        )
    return ok(status)


@router.get("/sync/schedule")
async def get_sync_schedule() -> ApiResponse:
    """View current sync schedule configuration."""
    return ok({
        "interval_minutes": sync_manager.interval_minutes,
        "background_running": sync_manager.background_sync_running,
        "next_sync_at": sync_manager.next_sync_at,
        "last_synced": sync_manager.last_synced,
    })


@router.put("/sync/schedule")
async def update_sync_schedule(interval_minutes: int = Query(30, ge=1, le=1440)) -> ApiResponse:
    """Update sync interval (1–1440 minutes).

    Restarts the background task if running.
    """
    if not 1 <= interval_minutes <= 1440:
        raise HTTPException(status_code=422, detail="interval_minutes must be 1–1440")

    was_running = sync_manager.background_sync_running
    if was_running:
        sync_manager.stop_background_sync()

    sync_manager.set_interval(interval_minutes)

    if was_running:
        sync_manager.start_background_sync()

    log.info("sync.schedule_updated", interval=interval_minutes)
    return ok({
        "interval_minutes": sync_manager.interval_minutes,
        "background_running": sync_manager.background_sync_running,
        "message": f"Sync interval updated to {interval_minutes} minutes",
    })


@router.get("/sync/status")
async def get_latest_sync_status() -> ApiResponse:
    """Get the latest sync information from the stored data."""
    return ok({
        "last_synced": sync_manager.last_synced,
        "programs_cached": len(sync_manager.programs),
    })
