"""Code4rena Service — FastAPI application.

Integrates with the Code4rena audit contest platform via GraphQL API.
Serves contest data via REST API using the Vyper standard envelope.

Port: 8000 (mapped externally to 8022)
"""

from __future__ import annotations

import asyncio
import os
import uuid

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from shared.observability import setup_observability
from src.client import Code4renaClient
from src.models import ApiResponse, HealthData, Meta, SyncStatus
from src.sync import SyncManager

SERVICE_NAME = "18-code4rena"
SERVICE_VERSION = "0.1.0"

sync_manager = SyncManager()
_sync_tasks: dict[str, asyncio.Task] = {}
_sync_results: dict[str, SyncStatus] = {}

# ── App Factory ────────────────────────────────────────────

app = FastAPI(
    title="Vyper Code4rena Service",
    description="Integrates with Code4rena audit contest platform via GraphQL API",
    version=SERVICE_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

log = setup_observability(app, SERVICE_NAME, SERVICE_VERSION)
from services.shared.storage import init_sqlite_store; init_sqlite_store("/data/code4rena")


# ── Helper ─────────────────────────────────────────────────

def ok(data: object = None) -> ApiResponse:
    """Build a standard Vyper API response envelope."""
    return ApiResponse(data=data, meta=Meta(status="ok"))


# ── Endpoints ──────────────────────────────────────────────

@app.get("/health")
async def health() -> ApiResponse:
    """Health check endpoint."""
    return ok(
        HealthData(
            status="ok",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
        )
    )


@app.get("/contests")
async def list_contests(
    offset: int = Query(0, ge=0, description="Number of contests to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max contests to return"),
    status: str | None = Query(None, description="Filter by status: active, upcoming, closed"),
) -> ApiResponse:
    """List all active/upcoming Code4rena contests."""
    contests = sync_manager.get_all_contests()

    if status:
        contests = [c for c in contests if c.get("status", "").lower() == status.lower()]

    total = len(contests)
    paginated = contests[offset:offset + limit]

    return ok({
        "total": total,
        "offset": offset,
        "limit": limit,
        "contests": paginated,
    })


@app.get("/contests/{contest_id}")
async def get_contest(contest_id: str) -> ApiResponse:
    """Get contest details including scope contracts and repos."""
    detail = sync_manager.get_contest_by_id(contest_id)
    if detail is None:
        # Try fetching live from API
        client = Code4renaClient()
        try:
            detail = await client.fetch_contest_detail(contest_id)
        finally:
            await client.close()

    if detail is None:
        raise HTTPException(status_code=404, detail=f"Contest '{contest_id}' not found")

    return ok(detail)


@app.post("/sync")
async def trigger_sync() -> ApiResponse:
    """Trigger a sync of Code4rena data (async).

    Dispatches a background task and returns a sync_id
    that can be polled via GET /sync/{sync_id}.
    """
    sync_id = str(uuid.uuid4())

    async def _run_sync(sid: str) -> None:
        try:
            status = await sync_manager.run_sync()
            _sync_results[sid] = status
        except Exception as e:
            log.error("sync.background_failed", sync_id=sid, error=str(e))
            _sync_results[sid] = SyncStatus(
                sync_id=sid,
                status="failed",
                errors=[str(e)],
            )

    _sync_results[sync_id] = SyncStatus(sync_id=sync_id, status="running")

    task = asyncio.create_task(_run_sync(sync_id))
    _sync_tasks[sync_id] = task
    task.add_done_callback(lambda _: _sync_tasks.pop(sync_id, None))

    return ok({"sync_id": sync_id, "status": "running"})


@app.get("/sync/{sync_id}")
async def get_sync(sync_id: str) -> ApiResponse:
    """Check the status of a sync operation."""
    status = _sync_results.get(sync_id)
    if status is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sync '{sync_id}' not found.",
        )
    return ok(status)
