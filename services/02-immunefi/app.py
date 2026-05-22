"""Immunefi Service — FastAPI application.

Fetches bug bounty programs from the Immunefi GitHub mirror,
detects associated GitHub repositories, and serves the data via REST API.

Port: 8001
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
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from shared.observability import setup_observability

from shared.cache import CacheLayer, IMMUNEFI_PROGS_CACHE, TTL_IMMUNEFI_PROGS

from src.models import (
    ApiResponse,
    HealthData,
    Meta,
    Program,
    ProgramListResponse,
    StatsResponse,
    SyncStatus,
)
from src.sync import SyncManager

# ── Dependent service URLs (for cross-service integration) ─

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://11-orchestrator:8009")
SOURCE_URL = os.getenv("SOURCE_URL", "http://03-source:8000")
CONFIG_URL = os.getenv("CONFIG_URL", "http://01-config:8000")




# ── Constants ──────────────────────────────────────────────

DATA_DIR = Path("/data/immunefi")
SERVICE_NAME = "immunefi"
SERVICE_VERSION = "0.2.0"

# ── Cache ───────────────────────────────────────────────────
immunefi_cache = CacheLayer(cache_dir="/data/cache/immunefi")

# ── Sync Manager (global singleton) ───────────────────────

sync_manager = SyncManager(DATA_DIR)

# Background sync task tracking
_sync_tasks: dict[str, asyncio.Task] = {}


# ── Lifespan ───────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Load programs on startup, clean up client on shutdown."""
    log.info("app.startup", service=SERVICE_NAME)

    # Load existing programs from disk
    count = len(sync_manager.load_programs())
    log.info("app.programs_loaded", count=count)

    # Start background periodic sync
    sync_manager.start_background_sync()

    # Start Web3 on-chain event polling (if configured)
    onchain = sync_manager.onchain_monitor
    if onchain.is_web3_available():
        onchain.start_background_polling(interval_seconds=300)
        log.info("app.onchain_polling_started")
    else:
        log.info("app.onchain_polling_skipped", reason="no_web3_rpc")

    # Check dependent services (non-blocking, log only)
    async def _check_deps() -> None:
        """Ping dependent services on startup."""
        deps = {
            "orchestrator": ORCHESTRATOR_URL,
            "source": SOURCE_URL,
            "config": CONFIG_URL,
        }
        for name, url in deps.items():
            try:
                async with httpx.AsyncClient(timeout=3.0) as c:
                    r = await c.get(f"{url}/health")
                    if r.status_code < 500:
                        log.info("app.dependency_ok", service=name)
                    else:
                        log.warning("app.dependency_unhealthy", service=name, status=r.status_code)
            except Exception as e:
                log.warning("app.dependency_unreachable", service=name, error=str(e)[:80])

    asyncio.create_task(_check_deps())

    yield

    # Shutdown: stop background sync + onchain polling
    sync_manager.stop_background_sync()
    sync_manager.onchain_monitor.stop_background_polling()
    log.info("app.shutdown", service=SERVICE_NAME)


# ── App Factory ────────────────────────────────────────────

app = FastAPI(
    title="Vyper Immunefi Service",
    description="Fetches bug bounty programs from Immunefi and detects GitHub repos",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

# CORS — permissive for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



log = setup_observability(app, "02-immunefi", "0.1.0")

# ── Helper ─────────────────────────────────────────────────

def ok(data: object = None) -> ApiResponse:
    """Build a standard success response."""
    return ApiResponse(data=data, meta=Meta(status="ok"))


# ── Endpoints ──────────────────────────────────────────────

@app.get("/health/dependencies")
async def health_dependencies() -> ApiResponse:
    """Check reachability of dependent services.

    Pings Orchestrator, Source, dan Config untuk memastikan
    seluruh pipeline reachable.
    """
    results: dict[str, Any] = {}

    async def _check(name: str, url: str, path: str = "/health") -> dict:
        """Ping a service and return status."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{url}{path}")
                return {
                    "reachable": resp.status_code < 500,
                    "status_code": resp.status_code,
                    "error": None,
                }
        except httpx.ConnectError:
            return {"reachable": False, "status_code": None, "error": "connection_refused"}
        except httpx.TimeoutException:
            return {"reachable": False, "status_code": None, "error": "timeout"}
        except Exception as e:
            return {"reachable": False, "status_code": None, "error": str(e)[:100]}

    results["orchestrator"] = await _check("orchestrator", ORCHESTRATOR_URL)
    results["source"] = await _check("source", SOURCE_URL)
    results["config"] = await _check("config", CONFIG_URL)

    all_reachable = all(r["reachable"] for r in results.values())
    reachable_count = sum(1 for r in results.values() if r["reachable"])

    return ok({
        "service": SERVICE_NAME,
        "all_reachable": all_reachable,
        "reachable_count": reachable_count,
        "total_dependencies": len(results),
        "dependencies": results,
    })


@app.get("/health")
async def health() -> ApiResponse:
    """Health check endpoint."""
    meta = sync_manager.storage.read_meta()
    return ok(
        HealthData(
            status="ok",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
            programs_cached=len(sync_manager.programs),
            last_synced=sync_manager.last_synced,
            schema_version=meta.get("schema_version"),
        )
    )


@app.get("/programs")
async def list_programs(
    offset: int = Query(0, ge=0, description="Number of programs to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max programs to return"),
    status: str | None = Query(None, description="Filter by status (active, inactive, etc.)"),
    chain: str | None = Query(None, description="Filter by blockchain"),
    search: str | None = Query(None, description="Search by name or slug"),
    sort: str = Query("name", description="Sort field: name, max_bounty, status"),
    order: str = Query("asc", description="Sort order: asc or desc"),
) -> ApiResponse:
    """List all synced programs with optional filtering."""
    programs = list(sync_manager.programs.values())

    # Filter by status
    if status:
        programs = [p for p in programs if p.status.lower() == status.lower()]

    # Filter by chain
    if chain:
        chain_lower = chain.lower()
        programs = [p for p in programs if any(c.lower() == chain_lower for c in p.chains)]

    # Search by name or slug
    if search:
        q = search.lower()
        programs = [
            p for p in programs
            if q in p.name.lower() or q in p.slug.lower()
        ]

    # Sort
    reverse = order.lower() == "desc"
    if sort == "max_bounty":
        programs.sort(key=lambda p: p.max_bounty or 0, reverse=reverse)
    elif sort == "status":
        programs.sort(key=lambda p: p.status, reverse=reverse)
    else:
        programs.sort(key=lambda p: p.name.lower(), reverse=reverse)

    total = len(programs)
    paginated = programs[offset:offset + limit]

    return ok(
        ProgramListResponse(
            data=paginated,
            total=total,
            offset=offset,
            limit=limit,
        )
    )


@app.get("/programs/{slug:path}/history")
async def get_program_history(
    slug: str,
    limit: int = Query(50, ge=1, le=500),
) -> ApiResponse:
    """Get change history for a specific program."""
    history = sync_manager.storage.get_history(slug, limit=limit)
    return ok({
        "slug": slug,
        "total": len(history),
        "history": history,
    })


@app.get("/programs/{slug:path}/contracts")
async def get_program_contracts(slug: str) -> ApiResponse:
    """Get smart contract addresses for a specific program."""
    program = sync_manager.programs.get(slug)
    if not program:
        raise HTTPException(status_code=404, detail=f"Program '{slug}' not found")
    return ok({
        "slug": slug,
        "total": len(program.contracts),
        "contracts": [c.model_dump() for c in program.contracts],
    })


# ── Alias endpoints (backward compat dengan daily_agenda) ──

@app.get("/programs/chains")
async def list_chains_alias() -> ApiResponse:
    """[Alias] Same as /chains — list unique chains across all programs."""
    return await list_chains()


@app.get("/programs/trends")
async def get_trends_alias() -> ApiResponse:
    """[Alias] Same as /intel/trends — full trend report."""
    return await get_trends()


@app.get("/programs/alerts")
async def get_alerts_alias() -> ApiResponse:
    """[Alias] Same as /intel/anomalies — anomaly alerts."""
    return await get_anomalies()


@app.get("/programs/{slug}/intelligence")
async def get_program_intelligence_alias(slug: str) -> ApiResponse:
    """[Alias] Same as /intel/scores/{slug} — intelligence score."""
    return await get_program_score(slug)


@app.get("/programs/{slug:path}")
async def get_program(slug: str) -> ApiResponse:
    """Get a single program by slug."""
    program = sync_manager.programs.get(slug)
    if not program:
        raise HTTPException(status_code=404, detail=f"Program '{slug}' not found")
    return ok(program)


@app.post("/sync")
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


@app.post("/sync/run")
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

    # Cache the results
    await immunefi_cache.set(IMMUNEFI_PROGS_CACHE, {"programs": "list"}, status, ttl_seconds=TTL_IMMUNEFI_PROGS)

    return ok(status)


@app.get("/sync/{sync_id}")
async def get_sync(sync_id: str) -> ApiResponse:
    """Check the status of a sync operation."""
    status = sync_manager.get_sync_status(sync_id)
    if not status:
        raise HTTPException(
            status_code=404,
            detail=f"Sync '{sync_id}' not found. Sync IDs are only valid during a running sync.",
        )
    return ok(status)


@app.get("/sync/schedule")
async def get_sync_schedule() -> ApiResponse:
    """View current sync schedule configuration."""
    return ok({
        "interval_minutes": sync_manager.interval_minutes,
        "background_running": sync_manager.background_sync_running,
        "next_sync_at": sync_manager.next_sync_at,
        "last_synced": sync_manager.last_synced,
    })


@app.put("/sync/schedule")
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


@app.get("/sync/status")
async def get_latest_sync_status() -> ApiResponse:
    """Get the latest sync information from the stored data."""
    return ok({
        "last_synced": sync_manager.last_synced,
        "programs_cached": len(sync_manager.programs),
    })


@app.get("/contracts")
async def list_all_contracts(
    chain: str | None = Query(None, description="Filter by blockchain"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> ApiResponse:
    """List all smart contracts across all synced programs."""
    all_contracts = []
    for program in sync_manager.programs.values():
        for contract in program.contracts:
            c = contract.model_dump()
            c["program_slug"] = program.slug
            c["program_name"] = program.name
            all_contracts.append(c)

    if chain:
        chain_lower = chain.lower()
        all_contracts = [c for c in all_contracts if c.get("chain", "").lower() == chain_lower]

    total = len(all_contracts)
    paginated = all_contracts[offset:offset + limit]

    return ok({
        "total": total,
        "offset": offset,
        "limit": limit,
        "contracts": paginated,
    })


@app.get("/chains")
async def list_chains() -> ApiResponse:
    """List all unique blockchains across synced programs."""
    chains: dict[str, int] = {}
    for program in sync_manager.programs.values():
        for chain in program.chains:
            c = chain or "unknown"
            chains[c] = chains.get(c, 0) + 1

    sorted_chains = sorted(chains.items(), key=lambda x: -x[1])
    return ok({
        "total": len(sorted_chains),
        "chains": [
            {"name": name, "program_count": count}
            for name, count in sorted_chains
        ],
    })


# ── Intelligence Endpoints ────────────────────────────────

@app.get("/intel/scores")
async def get_program_scores() -> ApiResponse:
    """Get intelligence scores for all programs (ranked)."""
    scores = sync_manager.get_scores()
    return ok(scores)


@app.get("/intel/scores/{slug}")
async def get_program_score(slug: str) -> ApiResponse:
    """Get intelligence score for a single program."""
    score = sync_manager.get_score_for(slug)
    if not score:
        raise HTTPException(status_code=404, detail=f"Program '{slug}' not found")
    return ok(score)


@app.get("/intel/trends")
async def get_trends() -> ApiResponse:
    """Get full trend report."""
    trends = sync_manager.get_trends()
    return ok(trends)


@app.get("/intel/trends/recent")
async def get_recent_changes(
    hours: int = Query(24, ge=1, le=720, description="Lookback hours"),
) -> ApiResponse:
    """Get recent changes summary."""
    changes = sync_manager.get_trends_recent(hours=hours)
    return ok(changes)


@app.get("/intel/anomalies")
async def get_anomalies() -> ApiResponse:
    """Detect anomalies across all programs."""
    anomalies = sync_manager.get_anomalies()
    return ok(anomalies)


@app.get("/intel/repos")
async def get_repo_intel(
    max_programs: int = Query(20, ge=1, le=100),
) -> ApiResponse:
    """Fetch GitHub repo intelligence for programs with repos."""
    intel = await sync_manager.get_repo_intel(max_programs=max_programs)
    return ok({
        "total": len(intel),
        "results": intel,
    })


# ── Level 3: Autonomous Endpoints ─────────────────────────

@app.post("/programs/{slug}/submit")
async def submit_finding(slug: str, body: dict) -> ApiResponse:
    """Auto-submit finding ke Immunefi via API.

    Body:
        title (str): Finding title
        description (str): Detailed description
        severity (str): critical/high/medium/low
        vulnerability_classification (str): reentrancy, access_control, etc.
        proof_of_concept (str): PoC code/text
        contract_address (str): 0x-prefixed address
    """
    prog = sync_manager.programs.get(slug)
    if not prog:
        raise HTTPException(404, f"Program '{slug}' not found")

    required = ["title", "description", "severity", "proof_of_concept", "contract_address"]
    missing = [f for f in required if f not in body]
    if missing:
        raise HTTPException(422, f"Missing fields: {', '.join(missing)}")

    result = await sync_manager.submit_finding(
        program_slug=slug,
        title=body["title"],
        description=body["description"],
        severity=body["severity"],
        vulnerability_classification=body.get("vulnerability_classification", "auto"),
        proof_of_concept=body["proof_of_concept"],
        contract_address=body["contract_address"],
    )
    return ok(result)


@app.get("/submissions")
async def list_submissions(
    status: str | None = Query(None, description="Filter by status"),
) -> ApiResponse:
    """List semua submission yang sudah dilakukan."""
    submissions = sync_manager.list_submissions(status=status)
    return ok({
        "total": len(submissions),
        "submissions": submissions,
    })


@app.get("/submissions/stats")
async def get_submission_stats() -> ApiResponse:
    """Statistik submission."""
    stats = sync_manager.get_submission_stats()
    return ok(stats)


@app.get("/submissions/{submission_id}")
async def get_submission(submission_id: str) -> ApiResponse:
    """Detail satu submission."""
    sub = sync_manager.get_submission(submission_id)
    if not sub:
        raise HTTPException(404, f"Submission '{submission_id}' not found")
    return ok(sub)


@app.get("/programs/{slug}/competition")
async def get_program_competition(slug: str) -> ApiResponse:
    """Analisis kompetisi untuk program bounty."""
    result = await sync_manager.analyze_competition(slug)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return ok(result)


@app.get("/programs/{slug}/prediction")
async def predict_bounty(slug: str) -> ApiResponse:
    """Prediksi perubahan bounty untuk program."""
    result = await sync_manager.predict_bounty(slug)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return ok(result)


# ── Level 2 Leftovers ─────────────────────────────────────

@app.get("/programs/recommendations")
async def get_program_recommendations(
    min_bounty: float = Query(10000, ge=0, description="Minimum bounty"),
    chain: str | None = Query(None, description="Filter by chain"),
    limit: int = Query(10, ge=1, le=50),
) -> ApiResponse:
    """Rekomendasi program terbaik berdasarkan preferensi.

    Menggabungkan intelligence score + bounty + chain preference.
    """
    programs = list(sync_manager.programs.values())

    # Filter by min bounty
    if min_bounty > 0:
        programs = [p for p in programs if (p.max_bounty or 0) >= min_bounty]

    # Filter by chain
    if chain:
        chain_lower = chain.lower()
        programs = [
            p for p in programs
            if any(c.lower() == chain_lower for c in p.chains)
        ]

    # Score + sort
    from src.scorer import ProgramScorer  # noqa: PLC0415
    scorer = ProgramScorer()
    scored = []
    for p in programs:
        score = scorer.score(p)
        scored.append({
            "slug": p.slug,
            "name": p.name,
            "score": score,
            "max_bounty": p.max_bounty,
            "chains": p.chains,
            "status": p.status,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)

    return ok({
        "total": len(scored),
        "returned": min(len(scored), limit),
        "recommendations": scored[:limit],
    })


@app.post("/programs/{slug}/contracts/scan")
async def scan_program_contracts(slug: str) -> ApiResponse:
    """Trigger full scan pipeline untuk semua kontrak di program.

    Fetch source dari Service 03 → Trigger scan ke Orchestrator 11.
    """
    prog = sync_manager.programs.get(slug)
    if not prog:
        raise HTTPException(404, f"Program '{slug}' not found")
    if not prog.contracts:
        raise HTTPException(400, f"Program '{slug}' has no contracts to scan")

    results = await sync_manager.fetch_program_contracts(
        slug=slug,
        trigger_scan=True,
    )
    return ok({
        "slug": slug,
        "name": prog.name,
        "contracts_count": len(prog.contracts),
        "results": results,
    })


# ── Contract Fetch + Scan Endpoints ───────────────────────

@app.get("/contracts/fetch/stats")
async def get_contract_fetch_stats() -> ApiResponse:
    """Get contract fetch cache statistics."""
    stats = sync_manager.get_contract_fetch_stats()
    return ok(stats)


@app.post("/contracts/fetch")
async def fetch_all_contracts(
    max_programs: int = Query(50, ge=1, le=200),
    trigger_scan: bool = Query(True, description="Trigger orchestrator scan after fetch"),
) -> ApiResponse:
    """Fetch contract source code from Service 03 for all programs.

    Optionally triggers orchestrator scan pipeline.
    """
    results = await sync_manager.fetch_contracts(
        max_programs=max_programs,
        trigger_scan=trigger_scan,
    )
    return ok(results)


@app.post("/programs/{slug}/contracts/fetch")
async def fetch_program_contracts(
    slug: str,
    trigger_scan: bool = Query(True),
) -> ApiResponse:
    """Fetch contract source for a specific program + trigger scan."""
    prog = sync_manager.programs.get(slug)
    if not prog:
        raise HTTPException(status_code=404, detail=f"Program '{slug}' not found")

    results = await sync_manager.fetch_program_contracts(
        slug=slug,
        trigger_scan=trigger_scan,
    )
    return ok({
        "slug": slug,
        "name": prog.name,
        "contracts_count": len(prog.contracts),
        "results": results,
    })


# ── Level 4: God-Tier Endpoints ──────────────────────────

@app.get("/tvl/{protocol_slug}")
async def fetch_protocol_tvl(protocol_slug: str) -> ApiResponse:
    """Fetch TVL data untuk protocol tertentu dari DeFiLlama."""
    result = await sync_manager.fetch_tvl(protocol_slug)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return ok(result)


@app.post("/tvl/refresh")
async def refresh_all_tvl(
    max_programs: int = Query(20, ge=1, le=100),
) -> ApiResponse:
    """Refresh TVL data for all programs that have valid slugs."""
    results = await sync_manager.fetch_all_tvl(max_programs=max_programs)
    return ok({
        "total": len(results),
        "results": results,
    })


@app.get("/tvl/stats")
async def get_tvl_stats() -> ApiResponse:
    """Get TVL cache statistics."""
    stats = sync_manager.get_tvl_stats()
    return ok(stats)


@app.get("/match")
async def match_programs(
    specialization: str = Query(..., description="Your specialization"),
    min_bounty: float = Query(0, ge=0),
    chain: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
) -> ApiResponse:
    """AI-powered program matching — cari program terbaik untuk skillmu."""
    results = await sync_manager.match_programs(
        specialization=specialization,
        min_bounty=min_bounty,
        chain=chain,
        limit=limit,
    )
    return ok({
        "specialization": specialization,
        "total": len(results),
        "matches": results,
    })


@app.get("/programs/{slug}/similar")
async def get_similar_programs(
    slug: str,
    limit: int = Query(5, ge=1, le=20),
) -> ApiResponse:
    """Cari program serupa berdasarkan embedding AI."""
    results = await sync_manager.find_similar_programs(slug, limit=limit)
    if isinstance(results, list) and len(results) > 0 and "error" in results[0]:
        raise HTTPException(404, results[0]["error"])
    return ok({
        "slug": slug,
        "total": len(results),
        "similar": results,
    })


@app.get("/programs/{slug}/predict-vulns")
async def predict_vulnerabilities(slug: str) -> ApiResponse:
    """Predict kemungkinan vulnerability type untuk program."""
    result = await sync_manager.predict_vulnerabilities(slug)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return ok(result)


@app.get("/web3/status")
async def get_web3_status() -> ApiResponse:
    """Cek status Web3 RPC connection."""
    return ok(sync_manager.get_web3_status())


@app.post("/events/poll")
async def poll_onchain_events() -> ApiResponse:
    """Manual trigger: poll on-chain events dari Immunefi contracts."""
    events = await sync_manager.poll_events()
    return ok({
        "new_events": len(events),
        "events": events,
    })


@app.get("/events")
async def get_onchain_events(
    program_slug: str | None = Query(None, description="Filter by program slug"),
    event_type: str | None = Query(None, description="Filter by event type"),
    limit: int = Query(50, ge=1, le=500),
) -> ApiResponse:
    """Get stored on-chain events with optional filters."""
    result = sync_manager.get_onchain_events(
        program_slug=program_slug,
        event_type=event_type,
        limit=limit,
    )
    return ok(result)


@app.get("/programs/{slug}/onchain/events")
async def get_program_onchain_events(
    slug: str,
    event_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> ApiResponse:
    """On-chain events untuk program tertentu."""
    result = sync_manager.get_onchain_events(
        program_slug=slug,
        event_type=event_type,
        limit=limit,
    )
    return ok(result)


@app.post("/scan/priority")
async def trigger_priority_scans(
    max_scans: int = Query(5, ge=1, le=20),
) -> ApiResponse:
    """Auto-trigger scan untuk program dengan priority tinggi."""
    results = await sync_manager.trigger_priority_scans(max_scans=max_scans)
    return ok({
        "total_triggered": len(results),
        "scans": results,
    })


@app.get("/dashboard")
async def get_dashboard() -> ApiResponse:
    """Full dashboard data: overview + chain heatmap + timeline."""
    dash = sync_manager.get_dashboard()
    return ok(dash)


@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint untuk real-time dashboard updates.

    Kirim:
      {"type": "ping"} → server akan reply {"type": "pong"}
      Listen: server otomatis kirim dashboard update setiap 30 detik.

    Client cukup connect dan listen — auto-update tiap 30s.
    """
    await websocket.accept()
    log.info("ws.dashboard.connected")

    async def _push_updates() -> None:
        """Periodic dashboard push."""
        while True:
            await asyncio.sleep(30)
            try:
                dash = sync_manager.get_dashboard()
                dash["type"] = "dashboard_update"
                await websocket.send_json(dash)
            except Exception:
                break

    push_task = asyncio.create_task(_push_updates())

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif data.get("type") == "refresh":
                dash = sync_manager.get_dashboard()
                dash["type"] = "dashboard_update"
                await websocket.send_json(dash)
    except WebSocketDisconnect:
        log.info("ws.dashboard.disconnected")
    except Exception as e:
        log.warning("ws.dashboard.error", error=str(e)[:100])
    finally:
        push_task.cancel()


# ── Fork L4: Fork Management ──────────────────────────────

@app.delete("/forks/{slug}")
async def delete_fork(slug: str) -> ApiResponse:
    """Hapus fork repo untuk program (via GitHub API).

    Body opsional:
      owner (str): GitHub owner of the fork (default: dari env GITHUB_USERNAME)
    """
    result = await sync_manager.fork_engine.delete_fork(slug)
    return ok(result)


@app.post("/forks/{slug}/sync")
async def sync_fork(slug: str) -> ApiResponse:
    """Sync fork dengan upstream (merge latest changes)."""
    result = await sync_manager.fork_engine.sync_fork_upstream(slug)
    return ok(result)


@app.get("/forks/{slug}/prs")
async def list_fork_prs(slug: str) -> ApiResponse:
    """List open pull requests dari forked repo."""
    prs = await sync_manager.fork_engine.list_prs(slug)
    return ok({
        "slug": slug,
        "total": len(prs),
        "prs": prs,
    })


@app.post("/forks/{slug}/pr")
async def create_fork_pr(
    slug: str,
    head_branch: str = Query(..., description="Branch with changes"),
    title: str = Query("Exploit PoC", description="PR title"),
    body: str = Query("", description="PR description"),
) -> ApiResponse:
    """Create a pull request dari forked repo ke upstream."""
    result = await sync_manager.fork_engine.create_pr(
        slug=slug,
        head_branch=head_branch,
        title=title,
        body=body,
    )
    return ok(result)


# ── Fork Endpoints ────────────────────────────────────────

@app.get("/forks")
async def get_fork_info() -> ApiResponse:
    """Get fork status: stats + list of unforked repos."""
    info = sync_manager.get_fork_info()
    return ok(info)


@app.post("/forks/all")
async def fork_all(
    max_forks: int = Query(10, ge=1, le=50, description="Max repos to fork"),
) -> ApiResponse:
    """Fork all unforked repos (up to max_forks)."""
    results = await sync_manager.fork_all_unforked(max_forks=max_forks)
    return ok({
        "total": len(results),
        "results": results,
    })


@app.post("/forks/{slug}")
async def fork_program(slug: str) -> ApiResponse:
    """Fork all unforked repos for a specific program."""
    results = await sync_manager.fork_program(slug)
    return ok({
        "slug": slug,
        "total": len(results),
        "results": results,
    })


# ── Cross-Service Integration ─────────────────────────────

@app.get("/service/info")
async def service_info() -> ApiResponse:
    """Return service metadata for orchestrator/service discovery.

    Orchestrator dan service lain bisa panggil endpoint ini
    untuk tau capabilities, endpoints, dan status provider.
    """
    return ok({
        "name": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "description": "Immunefi Bug Bounty Intelligence — fetches, scores, and enriches "
                       "bounty programs from multiple sources",
        "port": 8001,
        "capabilities": [
            "program_fetch",
            "program_scoring",
            "trend_analysis",
            "anomaly_detection",
            "repo_intelligence",
            "multi_source_sync",
            "incremental_sync",
            "background_sync",
            "history_tracking",
            "contract_fetch",
            "scan_trigger",
            "fork_engine",
            "fork_management",
            "auto_submission",
            "competition_analysis",
            "bounty_prediction",
            "tvl_monitoring",
            "onchain_event_monitor",
            "ai_program_matching",
            "predictive_exploit_planning",
            "dashboard_realtime",
        ],
        "endpoints": {
            "health": {"path": "/health", "method": "GET"},
            "health_deps": {"path": "/health/dependencies", "method": "GET"},
            "programs": {"path": "/programs", "method": "GET"},
            "program_detail": {"path": "/programs/{slug}", "method": "GET"},
            "program_history": {"path": "/programs/{slug}/history", "method": "GET"},
            "program_contracts": {"path": "/programs/{slug}/contracts", "method": "GET"},
            "contracts": {"path": "/contracts", "method": "GET"},
            "chains": {"path": "/chains", "method": "GET"},
            "providers": {"path": "/providers", "method": "GET"},
            "sync_trigger": {"path": "/sync", "method": "POST"},
            "sync_run": {"path": "/sync/run", "method": "POST"},
            "sync_status": {"path": "/sync/{sync_id}", "method": "GET"},
            "sync_schedule": {"path": "/sync/schedule", "method": "GET"},
            "sync_schedule_update": {"path": "/sync/schedule", "method": "PUT"},
            "intel_scores": {"path": "/intel/scores", "method": "GET"},
            "intel_score_detail": {"path": "/intel/scores/{slug}", "method": "GET"},
            "intel_trends": {"path": "/intel/trends", "method": "GET"},
            "intel_recent_changes": {"path": "/intel/trends/recent", "method": "GET"},
            "intel_anomalies": {"path": "/intel/anomalies", "method": "GET"},
            "intel_repos": {"path": "/intel/repos", "method": "GET"},
            "export_programs": {"path": "/export/programs", "method": "GET"},
            "stats": {"path": "/stats", "method": "GET"},
            "recommendations": {"path": "/programs/recommendations", "method": "GET"},
            "submit_finding": {"path": "/programs/{slug}/submit", "method": "POST"},
            "submissions": {"path": "/submissions", "method": "GET"},
            "submission_stats": {"path": "/submissions/stats", "method": "GET"},
            "submission_detail": {"path": "/submissions/{id}", "method": "GET"},
            "competition": {"path": "/programs/{slug}/competition", "method": "GET"},
            "prediction": {"path": "/programs/{slug}/prediction", "method": "GET"},
            "scan_contracts": {"path": "/programs/{slug}/contracts/scan", "method": "POST"},
            "contract_fetch": {"path": "/contracts/fetch", "method": "POST"},
            "contract_fetch_stats": {"path": "/contracts/fetch/stats", "method": "GET"},
            "contract_fetch_program": {"path": "/programs/{slug}/contracts/fetch", "method": "POST"},
            "tvl_protocol": {"path": "/tvl/{protocol_slug}", "method": "GET"},
            "tvl_refresh": {"path": "/tvl/refresh", "method": "POST"},
            "tvl_stats": {"path": "/tvl/stats", "method": "GET"},
            "web3_status": {"path": "/web3/status", "method": "GET"},
            "events": {"path": "/events", "method": "GET"},
            "events_poll": {"path": "/events/poll", "method": "POST"},
            "program_events": {"path": "/programs/{slug}/onchain/events", "method": "GET"},
            "match": {"path": "/match", "method": "GET"},
            "similar": {"path": "/programs/{slug}/similar", "method": "GET"},
            "predict_vulns": {"path": "/programs/{slug}/predict-vulns", "method": "GET"},
            "priority_scan": {"path": "/scan/priority", "method": "POST"},
            "dashboard": {"path": "/dashboard", "method": "GET"},
            "dashboard_ws": {"path": "/ws/dashboard", "method": "WEBSOCKET"},
            "forks": {"path": "/forks", "method": "GET"},
            "fork_all": {"path": "/forks/all", "method": "POST"},
            "fork_program": {"path": "/forks/{slug}", "method": "POST"},
            "fork_delete": {"path": "/forks/{slug}", "method": "DELETE"},
            "fork_sync": {"path": "/forks/{slug}/sync", "method": "POST"},
            "fork_prs": {"path": "/forks/{slug}/prs", "method": "GET"},
            "fork_create_pr": {"path": "/forks/{slug}/pr", "method": "POST"},
        },
        "providers": sync_manager.get_providers_status(),
        "background_sync": {
            "running": sync_manager.background_sync_running,
            "interval_minutes": sync_manager.interval_minutes,
        },
    })


@app.get("/providers")
async def list_providers() -> ApiResponse:
    """List all registered bounty providers and their availability."""
    statuses = sync_manager.get_providers_status()
    return ok({
        "providers": statuses,
        "total": len(statuses),
        "available": sum(1 for s in statuses if s.get("available")),
    })


@app.get("/export/programs")
async def export_programs() -> ApiResponse:
    """Export all programs in a format consumable by Source-Classifier and Orchestrator.

    Returns programs with their associated contracts and repos,
    siap dikonsumsi oleh service 03-source dan 11-orchestrator.
    """
    programs = sync_manager.programs.values()
    exported = []
    for p in programs:
        exported.append({
            "slug": p.slug,
            "name": p.name,
            "chains": p.chains,
            "max_bounty": p.max_bounty,
            "min_bounty": p.min_bounty,
            "currency": p.currency,
            "status": p.status,
            "project_url": p.project_url,
            "description": p.description[:500] if p.description else "",  # truncate
            "tags": p.tags,
            "updated_at": p.updated_at,
            "contracts": [
                {
                    "address": c.address,
                    "chain": c.chain,
                    "name": c.name,
                }
                for c in p.contracts
            ],
            "repos": [
                {
                    "url": r.url,
                    "owner": r.owner,
                    "repo": r.repo,
                    "source": r.source,
                }
                for r in p.repos
            ],
        })

    return ok({
        "total": len(exported),
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "programs": exported,
    })


@app.get("/stats")
async def get_stats() -> ApiResponse:
    """Return aggregated program statistics."""
    programs = sync_manager.programs.values()

    by_status: dict[str, int] = {}
    by_chain: dict[str, int] = {}
    bounty_ranges: dict[str, int] = {
        "0-1k": 0,
        "1k-10k": 0,
        "10k-100k": 0,
        "100k-1M": 0,
        "1M+": 0,
        "unknown": 0,
    }
    total_contracts = 0
    total_repos = 0

    for p in programs:
        # Status
        s = p.status or "unknown"
        by_status[s] = by_status.get(s, 0) + 1

        # Chain
        for c in p.chains:
            chain_key = c or "unknown"
            by_chain[chain_key] = by_chain.get(chain_key, 0) + 1

        # Bounty range
        bounty = p.max_bounty
        if bounty is None:
            bounty_ranges["unknown"] += 1
        elif bounty < 1000:
            bounty_ranges["0-1k"] += 1
        elif bounty < 10_000:
            bounty_ranges["1k-10k"] += 1
        elif bounty < 100_000:
            bounty_ranges["10k-100k"] += 1
        elif bounty < 1_000_000:
            bounty_ranges["100k-1M"] += 1
        else:
            bounty_ranges["1M+"] += 1

        # Contracts & repos
        total_contracts += len(p.contracts)
        total_repos += len(p.repos)

    return ok(
        StatsResponse(
            total_programs=len(programs),
            by_status=by_status,
            by_chain=by_chain,
            bounty_ranges=bounty_ranges,
            total_contracts=total_contracts,
            total_repos=total_repos,
        )
    )
