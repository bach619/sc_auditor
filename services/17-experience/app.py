"""17-Experience — Central Experience Service.

Menerima sync dari semua agent, menyediakan global query & learning.
Port: 8019
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .src.global_store import GlobalExperienceStore

logger = structlog.get_logger(service="17-experience")

# ── Global state ───────────────────────────────────────────
store: GlobalExperienceStore | None = None
_start_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    global store, _start_time
    _start_time = time.monotonic()
    store = GlobalExperienceStore()
    logger.info("experience_service_started", db_path=str(store._db_path))
    yield
    logger.info("experience_service_shutdown")


app = FastAPI(
    title="Experience Service",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ────────────────────────────────────────────────

def _ok(data: Any = None, meta: dict | None = None) -> dict:
    resp = {"status": "ok", "data": data}
    if meta:
        resp["meta"] = meta
    return resp


def _err(msg: str, code: int = 400) -> dict:
    return {"status": "error", "error": msg, "code": code}


# ── Health ─────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return _ok({
        "service": "17-experience",
        "uptime_seconds": time.monotonic() - _start_time,
        "total_experiences": store.count() if store else 0,
        "unique_agents": len(store.query(limit=1, offset=0)) if store else 0,
    })


# ── Sync (dari agent) ──────────────────────────────────────

@app.post("/sync")
async def sync_experiences(body: dict) -> dict:
    """Terima batch experiences dari agent.

    Body:
      agent_service: str
      experiences: list[dict]
    """
    if store is None:
        raise HTTPException(status_code=503, detail="Store not initialized")

    agent = body.get("agent_service", "unknown")
    exps = body.get("experiences", [])
    if not exps:
        return _ok({"synced": 0, "message": "No experiences to sync"})

    count = store.sync_batch(exps)
    total = store.count()
    logger.info("experiences_synced", agent=agent, count=count, total=total)
    return _ok({"synced": count, "total": total})


# ── Query ──────────────────────────────────────────────────

@app.get("/experience/query")
async def query_experiences(
    agent_service: str | None = Query(None),
    capability: str | None = Query(None),
    success: bool | None = Query(None),
    severity: str | None = Query(None),
    contract_name: str | None = Query(None),
    chain: str | None = Query(None),
    finding_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    past_days: int | None = Query(None),
) -> dict:
    if store is None:
        raise HTTPException(status_code=503, detail="Store not initialized")

    results = store.query(
        agent_service=agent_service,
        capability=capability,
        success=success,
        severity=severity,
        contract_name=contract_name,
        chain=chain,
        finding_type=finding_type,
        limit=limit,
        offset=offset,
        past_days=past_days,
    )
    total = len(results)
    return _ok(
        data=results,
        meta={"total": total, "limit": limit, "offset": offset},
    )


# ── Stats ──────────────────────────────────────────────────

@app.get("/experience/stats")
async def global_stats() -> dict:
    if store is None:
        raise HTTPException(status_code=503, detail="Store not initialized")
    return _ok(data=store.get_global_stats())


@app.get("/experience/stats/success-rate")
async def success_rate(
    agent_service: str | None = Query(None),
) -> dict:
    if store is None:
        raise HTTPException(status_code=503, detail="Store not initialized")
    return _ok(data={
        "success_rate": store.get_success_rate(agent_service),
        "agent_service": agent_service or "all",
    })


# ── Learning / Insights ────────────────────────────────────

@app.get("/experience/learn")
async def cross_agent_learnings(limit: int = Query(10, ge=1, le=50)) -> dict:
    """Dapatkan insight pembelajaran lintas-agent."""
    if store is None:
        raise HTTPException(status_code=503, detail="Store not initialized")
    return _ok(data={
        "learnings": store.get_learnings(limit),
        "patterns": store.detect_cross_agent_patterns(),
        "total_agents": store._conn.execute(
            "SELECT COUNT(DISTINCT agent_service) as c FROM experiences"
        ).fetchone()["c"],
    })


@app.get("/experience/consolidations")
async def global_consolidations(limit: int = Query(20, ge=1, le=100)) -> dict:
    """Dapatkan consolidations global."""
    if store is None:
        raise HTTPException(status_code=503, detail="Store not initialized")
    rows = store._conn.execute(
        "SELECT * FROM consolidations ORDER BY confidence DESC LIMIT ?", (limit,)
    ).fetchall()
    return _ok(data=[dict(r) for r in rows])


# ── Admin ──────────────────────────────────────────────────

@app.post("/experience/prune")
async def prune_experiences(keep_days: int = Query(365, ge=30)) -> dict:
    """Hapus experiences tua yang tidak penting."""
    if store is None:
        raise HTTPException(status_code=503, detail="Store not initialized")
    deleted = store.prune(keep_days)
    return _ok({"deleted": deleted, "keep_days": keep_days})


@app.get("/experience/count")
async def count_experiences(agent_service: str | None = Query(None)) -> dict:
    if store is None:
        raise HTTPException(status_code=503, detail="Store not initialized")
    return _ok({"count": store.count(agent_service), "agent_service": agent_service or "all"})
