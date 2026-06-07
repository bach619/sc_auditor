"""Hats Finance Service — FastAPI application.

Integrates with the Hats Finance bug bounty platform via REST API.
Pulls vault listings, scope details, and stores them locally.

Port: 8024 (external), 8000 (internal container)
"""

from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from shared.observability import setup_observability

from shared.api_errors import register_error_handlers
from src.models import (
    ApiResponse,
    HatsVault,
    HealthData,
    Meta,
    SyncStatus,
    VaultListResponse,
)
from src.storage import load_vaults, load_vault_detail
from src.sync import SyncManager

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://11-orchestrator:8000")

DATA_DIR = Path("/data/hats")
SERVICE_NAME = "21-hats"
SERVICE_VERSION = "0.1.0"

sync_manager = SyncManager()

_sync_tasks: dict[str, asyncio.Task] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    log.info("app.startup", service=SERVICE_NAME)

    if not DATA_DIR.exists():
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            log.error("app.data_dir_error", error=str(e))
    from shared.storage import init_sqlite_store; init_sqlite_store("/data/hats")

    existing = load_vaults()
    log.info("app.vaults_loaded", count=len(existing))

    async def _check_deps() -> None:
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                r = await c.get(f"{ORCHESTRATOR_URL}/health")
                if r.status_code < 500:
                    log.info("app.dependency_ok", service="orchestrator")
                else:
                    log.warning("app.dependency_unhealthy", service="orchestrator", status=r.status_code)
        except Exception as e:
            log.warning("app.dependency_unreachable", service="orchestrator", error=str(e)[:80])

    asyncio.create_task(_check_deps())

    yield

    log.info("app.shutdown", service=SERVICE_NAME)


app = FastAPI(
    title="Vyper Hats Finance Service",
    description="Fetches bug bounty vaults from the Hats Finance platform and stores scope data",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


log = setup_observability(app, "21-hats", "0.1.0")


def ok(data: object = None) -> ApiResponse:
    return ApiResponse(data=data, meta=Meta(status="ok"))


# ── Endpoints ──────────────────────────────────────────────


@app.get("/health")
async def health() -> ApiResponse:
    vaults = load_vaults()
    return ok(HealthData(
        status="ok",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        tools_available=len(vaults),
    ))


@app.get("/vaults")
async def list_vaults(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    status: str | None = Query(None),
) -> ApiResponse:
    raw = load_vaults()
    vaults = []
    for item in raw:
        vaults.append(HatsVault(
            id=item.get("platform_id", item.get("id", "")),
            title=item.get("title", ""),
            description=item.get("description", ""),
            status=item.get("status", ""),
            chain=item.get("chains", [None])[0] if item.get("chains") else "",
            max_bounty_usd=float(item.get("max_bounty_usd", 0)),
            total_deposited_usd=float(item.get("total_pool_usd", 0)),
            start_date=str(item.get("start_date", "")) if item.get("start_date") else None,
            end_date=str(item.get("end_date", "")) if item.get("end_date") else None,
            committee_address=item.get("metadata", {}).get("committee_address", ""),
            url=item.get("url", ""),
        ))

    if status:
        vaults = [v for v in vaults if v.status.lower() == status.lower()]

    total = len(vaults)
    paginated = vaults[offset:offset + limit]

    return ok(VaultListResponse(
        data=paginated,
        total=total,
        offset=offset,
        limit=limit,
    ))


@app.get("/vaults/{vault_id}")
async def get_vault(vault_id: str) -> ApiResponse:
    raw = load_vaults()
    match = None
    for item in raw:
        if item.get("platform_id") == vault_id or item.get("id") == f"hats-{vault_id}":
            match = item
            break

    detail = load_vault_detail(vault_id)
    if detail:
        match = detail
    elif not match:
        raise HTTPException(status_code=404, detail=f"Vault '{vault_id}' not found")

    scope_contracts = match.get("scope_contracts", [])
    scope_repos = match.get("scope_repos", [])

    return ok({
        "id": vault_id,
        "title": match.get("title", ""),
        "description": match.get("description", ""),
        "status": match.get("status", ""),
        "chain": match.get("chains", [None])[0] if match.get("chains") else "",
        "max_bounty_usd": float(match.get("max_bounty_usd", 0)),
        "total_deposited_usd": float(match.get("total_pool_usd", 0)),
        "start_date": str(match.get("start_date", "")) if match.get("start_date") else None,
        "end_date": str(match.get("end_date", "")) if match.get("end_date") else None,
        "committee_address": match.get("metadata", {}).get("committee_address", ""),
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
