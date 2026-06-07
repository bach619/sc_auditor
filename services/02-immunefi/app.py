"""Immunefi Service — FastAPI application.

Fetches bug bounty programs from the Immunefi GitHub mirror,
detects associated GitHub repositories, and serves the data via REST API.

Port: 8001
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from shared.observability import setup_observability
from shared.api_errors import register_error_handlers

from src.agent_loop import ImmunefiAgent
from src.models import ApiResponse, StatsResponse
import src.state as _state
from src.state import (
    CONFIG_URL,
    DATA_DIR,
    ORCHESTRATOR_URL,
    SERVICE_NAME,
    SERVICE_VERSION,
    SOURCE_URL,
    STORAGE_ENGINE,
    init_sqlite,
    log,
    ok,
    sync_manager,
)

from src.routes.routes_agent import router as agent_router
from src.routes.routes_contracts import router as contracts_router
from src.routes.routes_dashboard import router as dashboard_router
from src.routes.routes_forks import router as forks_router
from src.routes.routes_health import router as health_router
from src.routes.routes_intel import router as intel_router
from src.routes.routes_programs import router as programs_router
from src.routes.routes_submissions import router as submissions_router
from src.routes.routes_sync import router as sync_router


# ── Lifespan ───────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Load programs on startup, clean up client on shutdown."""
    log.info("app.startup", service=SERVICE_NAME)

    # ── Startup Validation ──────────────────────────────────
    errors: list[str] = []

    # Validate data directory
    if not DATA_DIR.exists():
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            log.info("app.data_dir_created", path=str(DATA_DIR))
        except OSError as e:
            errors.append(f"Cannot create DATA_DIR {DATA_DIR}: {e}")
    elif not os.access(str(DATA_DIR), os.W_OK):
        errors.append(f"DATA_DIR {DATA_DIR} is not writable")

    # Validate required subdirectories
    for sub in ("programs", "history", "indexes"):
        sub_path = DATA_DIR / sub
        if not sub_path.exists():
            try:
                sub_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                errors.append(f"Cannot create {sub_path}: {e}")

    # Validate env config has sensible defaults
    if not ORCHESTRATOR_URL.startswith("http"):
        errors.append(f"ORCHESTRATOR_URL does not look like a URL: {ORCHESTRATOR_URL}")
    if not SOURCE_URL.startswith("http"):
        errors.append(f"SOURCE_URL does not look like a URL: {SOURCE_URL}")

    if errors:
        for err in errors:
            log.error("app.validation_error", error=err)
        log.warning("app.startup_with_errors", error_count=len(errors))
    else:
        log.info("app.validation_passed")

    # ── Initialize SQLite store (if STORAGE_ENGINE=sqlite|dual) ─
    sqlite_store = init_sqlite()
    if sqlite_store:
        log.info("app.sqlite_ready", engine=STORAGE_ENGINE, tables=3)
    else:
        log.info("app.sqlite_skipped", engine=STORAGE_ENGINE, reason="using JSON files")

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

    # Init Immunefi Agent
    _state._immunefi_agent = ImmunefiAgent(
        sync_service=sync_manager,
        storage=sync_manager,
        scorer=sync_manager,
        competition=sync_manager,
        predictor=sync_manager,
        onchain=sync_manager,
    )
    log.info("app.agent_initialized")

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

register_error_handlers(app)

# CORS — permissive for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Observability ──────────────────────────────────────────

_state.log = setup_observability(app, "02-immunefi", "0.1.0")


# ── Route Inclusion ────────────────────────────────────────

app.include_router(health_router, prefix="")
app.include_router(programs_router, prefix="")
app.include_router(sync_router, prefix="")
app.include_router(contracts_router, prefix="")
app.include_router(intel_router, prefix="")
app.include_router(submissions_router, prefix="")
app.include_router(dashboard_router, prefix="")
app.include_router(forks_router, prefix="")
app.include_router(agent_router, prefix="")


# ── Remaining Endpoints ────────────────────────────────────

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
