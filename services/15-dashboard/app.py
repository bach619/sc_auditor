"""Vyper Dashboard Service — FastAPI entry point.

API Gateway + Web UI for the Vyper smart contract bug hunting platform.
Serves a React SPA via static files, SSE real-time updates,
and REST API proxy/aggregation to internal backend services.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from shared.observability import setup_observability
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from src.models import (
    ApiResponse,
    Case,
    CaseClose,
    CaseCreate,
    CaseStats,
    HealthData,
    Meta,
)
from src.health_monitor import HealthMonitor
from src.proxy import proxy, ServiceProxy
from src.sse import sse_manager
from src.storage import (
    close_case as storage_close_case,
    create_case as storage_create_case,
    get_case as storage_get_case,
    get_case_stats as storage_get_case_stats,
    get_report_md as storage_get_report_md,
    get_report_pdf as storage_get_report_pdf,
    list_cases as storage_list_cases,
    list_cases_with_total as storage_list_cases_with_total,
)

# ── Paths ───────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent

# ── Security Headers Middleware ─────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


# ── Application ─────────────────────────────────────────────────

app = FastAPI(
    title="Vyper Dashboard Service",
    description="API Gateway + Web UI for Vyper Smart Contract Bug Hunter",
    version="1.0.0",
)

ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)

logger = setup_observability(app, "15-dashboard", "1.0.0")

app.add_middleware(SecurityHeadersMiddleware)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)

STATIC_DIR = BASE_DIR / "static"

# ── Startup / Shutdown ──────────────────────────────────────────

_start_time: float = 0.0
health_monitor: HealthMonitor = HealthMonitor(check_interval=30.0)


@app.on_event("startup")
async def startup() -> None:
    global _start_time
    _start_time = time.time()
    logger.info("Starting Dashboard Service")
    await proxy.start()
    await health_monitor.start()
    logger.info("Dashboard ready — http://localhost:8000")


@app.on_event("shutdown")
async def shutdown() -> None:
    logger.info("Shutting down Dashboard Service")
    await health_monitor.stop()
    await proxy.close()


# ── Helpers ─────────────────────────────────────────────────────

def _ok(data: Any = None, **meta: Any) -> JSONResponse:
    return JSONResponse(
        content=ApiResponse(
            data=data,
            meta=Meta(
                status="ok",
                timestamp=datetime.now(timezone.utc).isoformat(),
            ),
        ).model_dump(mode="json"),
    )


def _err(message: str, status_code: int = 400, **meta: Any) -> JSONResponse:
    return JSONResponse(
        content={
            "data": None,
            "meta": {
                "status": "error",
                "error": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **meta,
            },
        },
        status_code=status_code,
    )


def _uptime() -> float:
    return time.time() - _start_time if _start_time else 0.0


# ═══════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════

@app.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint."""
    return _ok(
        data=HealthData(
            service="dashboard",
            version="1.0.0",
            uptime_seconds=_uptime(),
        ).model_dump(mode="json"),
    )


@app.get("/api/health/graph")
async def health_graph() -> JSONResponse:
    """Dependency graph + status for all services."""
    try:
        graph = health_monitor.get_graph()
        return _ok(data=graph)
    except Exception as e:
        logger.error("Health graph failed", error=str(e))
        return _err(f"Health graph failed: {e}", status_code=502)


@app.get("/api/health/metrics")
async def health_metrics() -> JSONResponse:
    """Aggregated metrics across all services."""
    try:
        metrics = health_monitor.get_metrics()
        return _ok(data=metrics)
    except Exception as e:
        logger.error("Health metrics failed", error=str(e))
        return _err(f"Health metrics failed: {e}", status_code=502)


# ═══════════════════════════════════════════════════════════════
# SSE — Server-Sent Events
# ═══════════════════════════════════════════════════════════════

@app.get("/events")
@limiter.limit("100/minute")
async def sse_events(request: Request) -> StreamingResponse:
    """SSE stream for real-time dashboard updates."""
    queue = await sse_manager.connect()
    logger.info("SSE client connected")
    return StreamingResponse(
        sse_manager.event_stream(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )





# ═══════════════════════════════════════════════════════════════
# REST API Proxies
# ═══════════════════════════════════════════════════════════════

# ── Daemon ──────────────────────────────────────────────────────

@app.post("/api/daemon/start")
@limiter.limit("10/minute")
async def api_daemon_start(request: Request) -> JSONResponse:
    """Start daemon (proxies to Orchestrator)."""
    try:
        result = await proxy.start_daemon()
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Daemon start failed", error=str(e))
        return _err(f"Daemon start failed: {e}", status_code=502)


@app.post("/api/daemon/stop")
@limiter.limit("10/minute")
async def api_daemon_stop(request: Request) -> JSONResponse:
    """Stop daemon (proxies to Orchestrator)."""
    try:
        result = await proxy.stop_daemon()
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Daemon stop failed", error=str(e))
        return _err(f"Daemon stop failed: {e}", status_code=502)


@app.get("/api/daemon/status")
async def api_daemon_status() -> JSONResponse:
    """Get daemon status (proxies to Orchestrator)."""
    try:
        result = await proxy.get_daemon_status()
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Daemon status failed", error=str(e))
        return _err(f"Daemon status failed: {e}", status_code=502)


# ── Audits ──────────────────────────────────────────────────────

@app.get("/api/audits")
async def api_list_audits(
    state: Optional[str] = Query(None),
    program: Optional[str] = Query(None),
    chain: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> JSONResponse:
    """List audits (proxies to Orchestrator)."""
    try:
        result = await proxy.get_audits(
            state=state, program=program, chain=chain,
            limit=limit, offset=offset,
        )
        return _ok(
            data=result.get("data", []),
            total=result.get("meta", {}).get("total", 0),
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error("List audits failed", error=str(e))
        return _err(f"Failed to fetch audits: {e}", status_code=502)


@app.get("/api/audits/{audit_id}")
async def api_get_audit(audit_id: str) -> JSONResponse:
    """Get single audit (proxies to Orchestrator)."""
    try:
        result = await proxy.get_audit(audit_id)
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Get audit failed", audit_id=audit_id, error=str(e))
        return _err(f"Audit not found: {audit_id}", status_code=404)


@app.post("/api/audit")
async def api_start_audit(body: dict) -> JSONResponse:
    """Start a new audit (proxies to Orchestrator)."""
    try:
        result = await proxy.start_audit(
            chain=body.get("chain", ""),
            address=body.get("address", ""),
            program=body.get("program", ""),
            priority=body.get("priority", 5),
            metadata=body.get("metadata"),
        )
        # Broadcast via SSE
        audit_id = result.get("data", {}).get("audit_id", "")
        if audit_id:
            await sse_manager.broadcast_audit_progress(
                audit_id=audit_id,
                state="PENDING",
                progress=0.0,
                message="Audit queued",
            )
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Start audit failed", error=str(e))
        return _err(f"Failed to start audit: {e}", status_code=502)


@app.post("/api/audits/{audit_id}/retry")
async def api_retry_audit(audit_id: str) -> JSONResponse:
    """Retry a failed audit (proxies to Orchestrator)."""
    try:
        result = await proxy.retry_audit(audit_id)
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Retry audit failed", audit_id=audit_id, error=str(e))
        return _err(f"Failed to retry audit: {e}", status_code=502)


# ── Queue ───────────────────────────────────────────────────────

@app.get("/api/queue")
async def api_get_queue() -> JSONResponse:
    """Get priority queue (proxies to Orchestrator)."""
    try:
        result = await proxy.get_queue()
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Get queue failed", error=str(e))
        return _err(f"Failed to fetch queue: {e}", status_code=502)


@app.post("/api/queue")
async def api_add_to_queue(body: dict) -> JSONResponse:
    """Add to priority queue (proxies to Orchestrator)."""
    try:
        result = await proxy.add_to_queue(
            contract_id=body.get("contract_id", ""),
            chain=body.get("chain", ""),
            address=body.get("address", ""),
            program=body.get("program", ""),
            priority_score=body.get("priority_score", 0.0),
        )
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Add to queue failed", error=str(e))
        return _err(f"Failed to add to queue: {e}", status_code=502)


# ── Config ──────────────────────────────────────────────────────

@app.get("/api/config")
async def api_get_config() -> JSONResponse:
    """Get all config (proxies to Config Service)."""
    try:
        result = await proxy.get_all_config()
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Get config failed", error=str(e))
        return _err(f"Failed to fetch config: {e}", status_code=502)


@app.get("/api/config/{key}")
async def api_get_config_key(key: str) -> JSONResponse:
    """Get a single config key (proxies to Config Service)."""
    try:
        result = await proxy.get_config(key)
        return _ok(data=result.get("data"))
    except Exception as e:
        return _err(f"Config key not found: {key}", status_code=404)


@app.put("/api/config/{key}")
async def api_set_config(key: str, body: dict) -> JSONResponse:
    """Set a config value (proxies to Config Service)."""
    try:
        result = await proxy.set_config(key, body.get("value"))
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Set config failed", key=key, error=str(e))
        return _err(f"Failed to set config: {e}", status_code=502)


@app.put("/api/config/bulk")
async def api_set_bulk_config(body: dict) -> JSONResponse:
    """Set multiple config values at once (proxies to Config Service)."""
    try:
        result = await proxy.set_bulk_config(body.get("config", {}))
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Bulk config failed", error=str(e))
        return _err(f"Failed to set config: {e}", status_code=502)


# ── Metrics ─────────────────────────────────────────────────────

@app.get("/api/metrics")
async def api_get_metrics() -> JSONResponse:
    """Get classification metrics (proxies to Classifier)."""
    try:
        result = await proxy.get_metrics()
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Get metrics failed", error=str(e))
        return _err(f"Failed to fetch metrics: {e}", status_code=502)


@app.get("/api/stats")
async def api_get_stats() -> JSONResponse:
    """Get pipeline stats (proxies to Orchestrator)."""
    try:
        result = await proxy.get_orchestrator_stats()
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Get stats failed", error=str(e))
        return _err(f"Failed to fetch stats: {e}", status_code=502)


# ── Feedback ────────────────────────────────────────────────────

@app.get("/api/feedback")
async def api_list_feedback() -> JSONResponse:
    """List all feedback items (proxies to Classifier)."""
    try:
        result = await proxy.get_feedback_list()
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("List feedback failed", error=str(e))
        return _err(f"Failed to fetch feedback: {e}", status_code=502)


@app.post("/api/feedback")
async def api_submit_feedback(body: dict) -> JSONResponse:
    """Submit feedback for a finding (proxies to Classifier)."""
    try:
        result = await proxy.submit_feedback(
            finding_id=body.get("finding_id", ""),
            feedback=body.get("feedback", ""),
            status=body.get("status", "pending_review"),
        )
        # Broadcast via SSE
        await sse_manager.broadcast_feedback_received(
            finding_id=body.get("finding_id", ""),
            status=body.get("status", ""),
        )
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Submit feedback failed", error=str(e))
        return _err(f"Failed to submit feedback: {e}", status_code=502)


# ── Programs (Immunefi) ─────────────────────────────────────────

@app.get("/api/programs")
async def api_list_programs(
    search: Optional[str] = Query(None),
    chain: Optional[str] = Query(None),
) -> JSONResponse:
    """List Immunefi programs (proxies to Immunefi Service).

    Immunefi returns:   {"data": {"data": [...], "total": N, ...}, "meta": {...}}
    We need to extract the inner "data" list for the frontend.
    """
    try:
        result = await proxy.get_programs(search=search, chain=chain)
        inner = result.get("data", {})
        if isinstance(inner, dict):
            programs_list = inner.get("data", [])
            total = inner.get("total", 0)
        else:
            programs_list = inner if isinstance(inner, list) else []
            total = len(programs_list)
        return _ok(data=programs_list, total=total)
    except Exception as e:
        logger.error("List programs failed", error=str(e))
        return _err(f"Failed to fetch programs: {e}", status_code=502)


@app.get("/api/programs/{slug}")
async def api_get_program(slug: str) -> JSONResponse:
    """Get single Immunefi program (proxies to Immunefi Service)."""
    try:
        result = await proxy.get_program(slug)
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Get program failed", slug=slug, error=str(e))
        return _err(f"Program not found: {slug}", status_code=404)


# ── Notifications ───────────────────────────────────────────────

@app.post("/api/notifications/test")
async def api_test_notification(body: dict) -> JSONResponse:
    """Send a test notification (proxies to Notifier)."""
    try:
        result = await proxy.send_test_notification(
            channel=body.get("channel", "discord")
        )
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Test notification failed", error=str(e))
        return _err(f"Failed to send test notification: {e}", status_code=502)


# ── Reports ─────────────────────────────────────────────────────

@app.post("/api/reports/generate")
async def api_generate_report(body: dict) -> JSONResponse:
    """Generate a report (proxies to Reporter)."""
    try:
        result = await proxy.generate_report(
            audit_id=body.get("audit_id", ""),
            format=body.get("format", "immunefi"),
        )
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Generate report failed", error=str(e))
        return _err(f"Failed to generate report: {e}", status_code=502)


# ── Agent ────────────────────────────────────────────────────────

@app.get("/api/agent/health")
async def api_agent_health() -> JSONResponse:
    """Agent service health check."""
    try:
        result = await proxy.get_agent_health()
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Agent health failed", error=str(e))
        return _err("Agent unreachable", status_code=502)


@app.post("/api/agent/team/run")
async def api_agent_team_run(body: dict) -> JSONResponse:
    """Run a team-based audit."""
    try:
        result = await proxy.run_team_audit(
            task_type=body.get("task_type", "full_audit"),
            input_data=body.get("input_data", {}),
            goal=body.get("goal", ""),
            max_delegations=body.get("max_delegations", 15),
        )
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Agent team run failed", error=str(e))
        return _err(f"Agent run failed: {e}", status_code=502)


@app.get("/api/agent/team/sessions")
async def api_agent_team_sessions(
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
) -> JSONResponse:
    """List team audit sessions."""
    try:
        result = await proxy.get_team_sessions(limit=limit, status=status)
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("List team sessions failed", error=str(e))
        return _err(f"Failed: {e}", status_code=502)


@app.get("/api/agent/team/{session_id}")
async def api_agent_team_session(session_id: str) -> JSONResponse:
    """Get team session detail."""
    try:
        result = await proxy.get_team_session(session_id)
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Get team session failed", session_id=session_id, error=str(e))
        return _err(f"Failed: {e}", status_code=502)


@app.get("/api/agent/team/structure")
async def api_agent_team_structure() -> JSONResponse:
    """Get team organizational structure."""
    try:
        result = await proxy.get_team_structure()
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Get team structure failed", error=str(e))
        return _err(f"Failed: {e}", status_code=502)


@app.get("/api/agent/skills")
async def api_agent_skills() -> JSONResponse:
    """List all agent skills."""
    try:
        result = await proxy.get_agent_skills()
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Get agent skills failed", error=str(e))
        return _err(f"Failed: {e}", status_code=502)


# ── Daemon (from Dashboard API, additional) ─────────────────────

@app.post("/api/daemon/sync")
async def api_daemon_sync() -> JSONResponse:
    """Trigger an immediate sync/scan cycle (proxies to Orchestrator via daemon restart)."""
    try:
        # Stop then start to trigger re-scan
        await proxy.stop_daemon()
        result = await proxy.start_daemon()
        return _ok(data=result.get("data"), message="Sync triggered")
    except Exception as e:
        logger.error("Daemon sync failed", error=str(e))
        return _err(f"Daemon sync failed: {e}", status_code=502)


# ═══════════════════════════════════════════════════════════════
# New API Endpoints (React SPA)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/health/all")
async def api_health_all() -> JSONResponse:
    """Health check for all 18 backend services."""
    try:
        result = await proxy.check_all_services()
        return _ok(data=result)
    except Exception as e:
        logger.error("Health all failed", error=str(e))
        return _err(f"Health check failed: {e}", status_code=502)


@app.get("/api/pipeline")
async def api_pipeline_status() -> JSONResponse:
    """Get full pipeline status (proxies to Orchestrator)."""
    try:
        result = await proxy.get_pipeline_status()
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Pipeline status failed", error=str(e))
        return _err(f"Pipeline status failed: {e}", status_code=502)


@app.get("/api/pipeline/steps")
async def api_pipeline_steps() -> JSONResponse:
    """Get pipeline step definitions (proxies to Orchestrator)."""
    try:
        result = await proxy.get_pipeline_steps()
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Pipeline steps failed", error=str(e))
        return _err(f"Pipeline steps failed: {e}", status_code=502)


@app.get("/api/scanner/tools")
async def api_scanner_tools() -> JSONResponse:
    """Get all scanner tool statuses (Slither, Mythril, Echidna, Forge, Halmos)."""
    try:
        result = await proxy.get_scanner_tools_status()
        return _ok(data=result)
    except Exception as e:
        logger.error("Scanner tools failed", error=str(e))
        return _err(f"Scanner tools failed: {e}", status_code=502)


@app.get("/api/scanner/{audit_id}/results")
async def api_scanner_results(audit_id: str) -> JSONResponse:
    """Get per-tool scanner results for an audit."""
    try:
        result = await proxy.get_scanner_results(audit_id)
        return _ok(data=result.get("data"))
    except Exception as e:
        return _err(f"Scanner results failed: {e}", status_code=502)


@app.get("/api/exploit/{finding_id}")
async def api_exploit_detail(finding_id: str) -> JSONResponse:
    """Get exploit/PoC detail for a finding."""
    try:
        result = await proxy.get_exploit_detail(finding_id)
        return _ok(data=result.get("data"))
    except Exception as e:
        return _err(f"Exploit detail failed: {e}", status_code=502)


@app.get("/api/notifier/channels")
async def api_notifier_channels() -> JSONResponse:
    """Get notifier channel statuses (proxies to Notifier)."""
    try:
        result = await proxy.get_notifier_channels()
        return _ok(data=result.get("data"))
    except Exception as e:
        return _err(f"Notifier channels failed: {e}", status_code=502)


@app.get("/api/notifier/logs")
async def api_notifier_logs(limit: int = Query(50, ge=1, le=500)) -> JSONResponse:
    """Get notifier delivery logs (proxies to Notifier)."""
    try:
        result = await proxy.get_notifier_logs(limit=limit)
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Notifier logs failed", error=str(e))
        return _err(f"Notifier logs failed: {e}", status_code=502)


@app.get("/api/webhook/logs")
async def api_webhook_logs(limit: int = Query(50, ge=1, le=500)) -> JSONResponse:
    """Get webhook event logs (proxies to Webhook Service)."""
    try:
        result = await proxy.get_webhook_logs(limit=limit)
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Webhook logs failed", error=str(e))
        return _err(f"Webhook logs failed: {e}", status_code=502)


@app.get("/api/source/{audit_id}")
async def api_source_code(audit_id: str) -> JSONResponse:
    """Get source code for an audit (proxies to Source Service)."""
    try:
        result = await proxy.get_source_code(audit_id)
        return _ok(data=result.get("data"))
    except Exception as e:
        return _err(f"Source code failed: {e}", status_code=502)


@app.get("/api/reports")
async def api_list_reports(limit: int = Query(50, ge=1, le=500)) -> JSONResponse:
    """List generated reports (proxies to Reporter)."""
    try:
        result = await proxy.list_reports(limit=limit)
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("List reports failed", error=str(e))
        return _err(f"List reports failed: {e}", status_code=502)


@app.get("/api/upkeep/status")
async def api_upkeep_status() -> JSONResponse:
    """Get scheduler/upkeep status (proxies to Upkeep Service)."""
    try:
        result = await proxy.get_upkeep_status()
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Upkeep status failed", error=str(e))
        return _err(f"Upkeep status failed: {e}", status_code=502)


@app.get("/api/upkeep/logs")
async def api_upkeep_logs(limit: int = Query(50, ge=1, le=500)) -> JSONResponse:
    """Get upkeep execution logs (proxies to Upkeep Service)."""
    try:
        result = await proxy.get_upkeep_logs(limit=limit)
        return _ok(data=result.get("data"))
    except Exception as e:
        logger.error("Upkeep logs failed", error=str(e))
        return _err(f"Upkeep logs failed: {e}", status_code=502)


# ═══════════════════════════════════════════════════════════════
# Case Management — Agenda 05: Each Bug Is Cases
# ═══════════════════════════════════════════════════════════════

@app.get("/api/cases")
async def api_list_cases(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    confidence: Optional[str] = Query(None, description="Filter by confidence label (Low/Medium/High/Critical)"),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> JSONResponse:
    """List all OPEN cases with filter, search, sort, pagination."""
    try:
        cases, total = storage_list_cases_with_total(
            status=status or "OPEN",
            search=search,
            severity=severity,
            confidence=confidence,
            sort=sort,
            order=order,
            limit=limit,
            offset=offset,
        )
        return _ok(
            data=[c.model_dump(mode="json") for c in cases],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error("List cases failed", error=str(e))
        return _err(f"Failed to list cases: {e}", status_code=500)


@app.get("/api/cases/archive")
async def api_list_archive(
    search: Optional[str] = Query(None),
    sort: str = Query("closed_at"),
    order: str = Query("desc"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> JSONResponse:
    """List all CLOSED cases with filter, search, sort, pagination."""
    try:
        cases, total = storage_list_cases_with_total(
            status="CLOSED",
            search=search,
            sort=sort,
            order=order,
            limit=limit,
            offset=offset,
        )
        return _ok(
            data=[c.model_dump(mode="json") for c in cases],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error("List archive failed", error=str(e))
        return _err(f"Failed to list archive: {e}", status_code=500)


@app.get("/api/cases/stats")
async def api_case_stats() -> JSONResponse:
    """Get case statistics for dashboard."""
    try:
        stats = storage_get_case_stats()
        return _ok(data=stats.model_dump(mode="json"))
    except Exception as e:
        logger.error("Case stats failed", error=str(e))
        return _err(f"Failed to get case stats: {e}", status_code=500)


@app.get("/api/cases/{case_id}")
async def api_get_case(case_id: str) -> JSONResponse:
    """Get a single case by ID."""
    try:
        case = storage_get_case(case_id)
        if case is None:
            return _err(f"Case not found: {case_id}", status_code=404)
        return _ok(data=case.model_dump(mode="json"))
    except Exception as e:
        logger.error("Get case failed", case_id=case_id, error=str(e))
        return _err(f"Failed to get case: {e}", status_code=500)


@app.post("/api/cases")
@limiter.limit("30/minute")
async def api_create_case(request: Request, body: CaseCreate) -> JSONResponse:
    """Create a new case (from Agent scanner output)."""
    try:
        case = storage_create_case(body)
        # Broadcast via SSE
        await sse_manager.broadcast_audit_progress(
            audit_id=case.case_id,
            state="OPEN",
            progress=1.0,
            message=f"New case: {case.title}",
        )
        return _ok(data=case.model_dump(mode="json"))
    except Exception as e:
        logger.error("Create case failed", error=str(e))
        return _err(f"Failed to create case: {e}", status_code=500)


@app.put("/api/cases/{case_id}/close")
async def api_close_case(case_id: str, body: CaseClose) -> JSONResponse:
    """Close a case (by User after bounty received or FP)."""
    try:
        case = storage_close_case(
            case_id=case_id,
            reason=body.closed_reason,
            bounty=body.bounty_amount,
            notes=body.notes,
        )
        if case is None:
            existing = storage_get_case(case_id)
            if existing is None:
                return _err(f"Case not found: {case_id}", status_code=404)
            return _err(f"Case {case_id} is already closed", status_code=400)
        # Broadcast via SSE
        await sse_manager.broadcast_audit_progress(
            audit_id=case_id,
            state="CLOSED",
            progress=1.0,
            message=f"Case closed: {body.closed_reason.value}",
        )
        return _ok(data=case.model_dump(mode="json"))
    except Exception as e:
        logger.error("Close case failed", case_id=case_id, error=str(e))
        return _err(f"Failed to close case: {e}", status_code=500)


@app.get("/api/cases/{case_id}/report.md")
async def api_case_report_md(case_id: str) -> JSONResponse:
    """Download case report as Markdown."""
    try:
        md = storage_get_report_md(case_id)
        if md is None:
            return _err(f"Case not found: {case_id}", status_code=404)
        from fastapi.responses import Response
        return Response(
            content=md,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="{case_id}_report.md"',
            },
        )
    except Exception as e:
        logger.error("Report MD failed", case_id=case_id, error=str(e))
        return _err(f"Failed to generate report: {e}", status_code=500)


@app.get("/api/cases/{case_id}/report.pdf")
async def api_case_report_pdf(case_id: str) -> JSONResponse:
    """Download case report as PDF."""
    try:
        pdf = storage_get_report_pdf(case_id)
        if pdf is None:
            return _err(f"Case not found: {case_id}", status_code=404)
        from fastapi.responses import Response
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{case_id}_report.pdf"',
            },
        )
    except Exception as e:
        logger.error("Report PDF failed", case_id=case_id, error=str(e))
        return _err(f"Failed to generate PDF: {e}", status_code=500)


# ═══════════════════════════════════════════════════════════════
# SPA Catch-All (must be LAST route)
# ═══════════════════════════════════════════════════════════════

@app.get("/{path:path}")
async def spa_fallback(request: Request, path: str) -> HTMLResponse:
    """Catch-all route: serve static assets or React SPA for non-API paths."""
    if path.startswith("api/") or path.startswith("events") or path == "health":
        raise HTTPException(status_code=404)
    
    # Serve static files (JS, CSS, images) if they exist
    file_path = STATIC_DIR / path
    if file_path.exists() and file_path.is_file():
        content = file_path.read_bytes()
        from fastapi.responses import Response
        media_type = {
            ".js": "application/javascript",
            ".css": "text/css",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".ico": "image/x-icon",
            ".json": "application/json",
            ".woff2": "font/woff2",
        }.get(file_path.suffix, "application/octet-stream")
        return Response(content=content, media_type=media_type)
    
    # SPA fallback: serve index.html
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        content = index_path.read_text()
        return HTMLResponse(content=content)
    return HTMLResponse(
        content="<html><body><h1>React build not found. Run: cd frontend && npm run build</h1></body></html>"
    )


# ═══════════════════════════════════════════════════════════════
# Run (dev)
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("DASHBOARD_HOST", "0.0.0.0")
    port = int(os.environ.get("DASHBOARD_PORT", "8000"))
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        log_level="info",
        reload=True,
    )
