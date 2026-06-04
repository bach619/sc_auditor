"""Cantina Service — FastAPI application.

Integrates with the Cantina audit contest platform via REST API.
Pulls contest listings, scope details, and stores them locally.

Port: 8000 (internal container)
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from shared.observability import setup_observability

from src.models import (
    ApiResponse,
    CantinaContest,
    ContestListResponse,
    HealthData,
    Meta,
    SyncStatus,
)
from src.storage import load_contests, load_contest_detail
from src.sync import SyncManager

DATA_DIR = Path("/data/cantina")
SERVICE_NAME = "20-cantina"
SERVICE_VERSION = "0.1.0"

sync_manager = SyncManager()

_sync_tasks: dict[str, asyncio.Task] = {}


app = FastAPI(
    title="Vyper Cantina Service",
    description="Fetches audit contests from the Cantina platform and stores scope data",
    version=SERVICE_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

log = setup_observability(app, "20-cantina", "0.1.0")
from services.shared.storage import init_sqlite_store; init_sqlite_store("/data/cantina")


# ── Helper ─────────────────────────────────────────────────

def ok(data: object = None) -> ApiResponse:
    return ApiResponse(data=data, meta=Meta(status="ok"))


# ── Endpoints ──────────────────────────────────────────────


@app.get("/health")
async def health() -> ApiResponse:
    contests = load_contests()
    return ok(HealthData(
        status="ok",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        tools_available=len(contests),
    ))


@app.get("/contests")
async def list_contests(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    status: str | None = Query(None),
) -> ApiResponse:
    raw = load_contests()
    contests = []
    for item in raw:
        contests.append(CantinaContest(
            id=item.get("platform_id", item.get("id", "")),
            title=item.get("title", ""),
            description=item.get("description", ""),
            status=item.get("status", ""),
            start_date=str(item.get("start_date", "")) if item.get("start_date") else "",
            end_date=str(item.get("end_date", "")) if item.get("end_date") else "",
            total_pool_usd=float(item.get("total_pool_usd", 0)),
            platform_id=item.get("platform_id", item.get("id", "")),
            url=item.get("url", ""),
        ))

    if status:
        contests = [c for c in contests if c.status.lower() == status.lower()]

    total = len(contests)
    paginated = contests[offset:offset + limit]

    return ok(ContestListResponse(
        data=paginated,
        total=total,
        offset=offset,
        limit=limit,
    ))


@app.get("/contests/{contest_id}")
async def get_contest(contest_id: str) -> ApiResponse:
    raw = load_contests()
    match = None
    for item in raw:
        if item.get("platform_id") == contest_id or item.get("id") == f"cantina-{contest_id}":
            match = item
            break

    detail = load_contest_detail(contest_id)
    if detail:
        match = detail
    elif not match:
        raise HTTPException(status_code=404, detail=f"Contest '{contest_id}' not found")

    scope_contracts = match.get("scope_contracts", [])
    scope_repos = match.get("scope_repos", [])

    return ok({
        "id": contest_id,
        "title": match.get("title", ""),
        "description": match.get("description", ""),
        "status": match.get("status", ""),
        "start_date": str(match.get("start_date", "")) if match.get("start_date") else None,
        "end_date": str(match.get("end_date", "")) if match.get("end_date") else None,
        "total_pool_usd": float(match.get("total_pool_usd", 0)),
        "platform_id": match.get("platform_id", contest_id),
        "url": match.get("url", ""),
        "scope": {
            "contracts": scope_contracts,
            "repos": scope_repos,
        },
    })


@app.post("/sync")
async def trigger_sync() -> ApiResponse:
    sync_id = str(uuid.uuid4())

    async def _run_sync(sid: str) -> None:
        try:
            await sync_manager.run_sync()
        except Exception as e:
            log.error("sync.background_failed", sync_id=sid, error=str(e))

    task = asyncio.create_task(_run_sync(sync_id))
    _sync_tasks[sync_id] = task
    task.add_done_callback(lambda _: _sync_tasks.pop(sync_id, None))

    return ok({"sync_id": sync_id, "status": "running"})


@app.get("/sync/{sync_id}")
async def get_sync(sync_id: str) -> ApiResponse:
    status = sync_manager.get_status(sync_id)
    if not status:
        raise HTTPException(
            status_code=404,
            detail=f"Sync '{sync_id}' not found.",
        )
    return ok(status)
