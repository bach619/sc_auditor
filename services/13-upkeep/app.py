"""Vyper Upkeep Service — FastAPI microservice for platform utility.

Handles self-update, backup/restore of all service data, and
aggregated metrics collection across the entire Vyper platform.

Port: 8012
"""

from __future__ import annotations

import asyncio
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

import structlog
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from src.backup import BackupManager, create_backup_manager
from src.metrics import MetricsAggregator, create_metrics_aggregator
from src.resource_governor import ResourceGovernor, SystemLoad
from src.models import (
    AggregatedMetrics,
    ApiResponse,
    BackupInfo,
    BackupResult,
    HealthData,
    Meta,
    MetricsSummary,
    RestoreResult,
    UpdateCheckResult,
    UpdateResult,
)
from shared.observability import setup_observability
from src.update import UpdateManager, create_update_manager

# ── Constants ──────────────────────────────────────────────

SERVICE_NAME = "upkeep"
SERVICE_VERSION = "0.1.0"
DATA_DIR = Path("/data/upkeep")
BACKUP_DIR = DATA_DIR / "backups"
UPDATE_DIR = DATA_DIR / "update"
METRICS_DIR = DATA_DIR / "metrics"

# How often metrics auto-refresh (seconds)
METRICS_REFRESH_INTERVAL = 300  # 5 minutes

# ── Global State ───────────────────────────────────────────


class AppState:
    """Shared application state injected via ``request.app.state.vyper``."""

    def __init__(self) -> None:
        self.update_mgr: UpdateManager = create_update_manager()
        self.backup_mgr: BackupManager = create_backup_manager()
        self.metrics_mgr: MetricsAggregator = create_metrics_aggregator()
        self._start_time: float = time.monotonic()
        self._shutdown_requested: bool = False

    @property
    def uptime_seconds(self) -> float:
        return time.monotonic() - self._start_time

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def request_shutdown(self) -> None:
        self._shutdown_requested = True


def _get_state(request: Request) -> AppState:
    """Get the application state from the request."""
    return request.app.state.vyper  # type: ignore[no-any-return]


# ── Lifespan ───────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: create data dirs. Shutdown: clean log."""
    state = AppState()
    app.state.vyper = state

    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        UPDATE_DIR.mkdir(parents=True, exist_ok=True)
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        log.warning("data_dir.permission_denied", path=str(DATA_DIR))

    log.info(
        "upkeep.startup",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        backup_dir=str(BACKUP_DIR),
    )

    # Warm metrics cache on startup (non-blocking)
    asyncio.create_task(_warm_metrics(state))

    # Start resource governor
    global _governor
    _governor = create_resource_governor()
    asyncio.create_task(_governor.start_monitoring(interval=5.0))
    log.info("resource_governor.started")

    yield

    log.info("upkeep.shutdown", service=SERVICE_NAME)


async def _warm_metrics(state: AppState) -> None:
    """Pre-populate the metrics cache on startup."""
    try:
        await state.metrics_mgr.aggregate_all()
        log.info("upkeep.metrics_warmed")
    except Exception as exc:
        log.warning("upkeep.metrics_warm_failed", error=str(exc))


# ── App Factory ────────────────────────────────────────────

app = FastAPI(
    title="Vyper Upkeep Service",
    description=(
        "Utility microservice: self-update, backup/restore, and "
        "aggregated metrics collection for the Vyper platform."
    ),
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

# CORS — permissive for local development / Docker compose
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

log = setup_observability(app, "13-upkeep", "0.1.0")


# ── Helper ─────────────────────────────────────────────────


def ok(data: object = None) -> ApiResponse:
    """Build a standard Vyper success response."""
    return ApiResponse(data=data, meta=Meta(status="ok"))


def err(detail: str, status_code: int = 400) -> HTTPException:
    """Build a standard Vyper error response."""
    return HTTPException(
        status_code=status_code,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


# ── Health ─────────────────────────────────────────────────


@app.get("/health")
async def health(request: Request) -> ApiResponse:
    """Health check endpoint.

    Returns service status, version, current version, and uptime.
    """
    state = _get_state(request)

    return ok(
        HealthData(
            status="ok",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
            current_version=state.update_mgr.get_current_version(),
            uptime_seconds=round(state.uptime_seconds, 2),
        )
    )


# ── Update ─────────────────────────────────────────────────


@app.post("/upkeep/check-update")
async def check_update(request: Request) -> ApiResponse:
    """Check for available updates on GitHub.

    Queries the GitHub releases API for the Vyper repository and
    compares the latest published version against the locally
    installed version. Results are cached in ``/data/upkeep/update/``.
    """
    state = _get_state(request)

    try:
        result = await state.update_mgr.check_github_version()
        return ok(result)
    except Exception as exc:
        log.exception("upkeep.check_update_failed", error=str(exc))
        raise err(f"Update check failed: {exc}", status_code=500)


@app.post("/upkeep/update")
async def perform_update(request: Request) -> ApiResponse:
    """Execute a self-update.

    Performs ``git pull``, ``docker compose pull``, and
    ``docker compose up -d`` to bring the entire Vyper platform
    up to the latest version. This is a long-running operation.
    """
    state = _get_state(request)

    result = await state.update_mgr.perform_update()
    if not result.success:
        log.error("upkeep.update_failed", error=result.error)
        return ok(result)  # Still return 200 with error details

    log.info(
        "upkeep.update_complete",
        previous=result.previous_version,
        current=result.current_version,
    )
    return ok(result)


# ── Backup ─────────────────────────────────────────────────


@app.post("/upkeep/backup")
async def create_backup(request: Request) -> ApiResponse:
    """Create a compressed backup of all Vyper service data.

    Creates a ``tar.gz`` archive of the entire ``/data/`` directory
    and stores it in ``/data/upkeep/backups/``. Returns the backup
    name, path, and size on completion.
    """
    state = _get_state(request)

    result = await state.backup_mgr.create_backup()
    if not result.success:
        raise err(f"Backup failed: {result.error}", status_code=500)

    log.info("upkeep.backup_created", name=result.name, size=result.size_bytes)
    return ok(result)


@app.get("/upkeep/backups")
async def list_backups(request: Request) -> ApiResponse:
    """List all available backup archives.

    Returns each backup's name, size (bytes), creation timestamp,
    age in days, and full path. Sorted newest-first.
    """
    state = _get_state(request)

    backups = await state.backup_mgr.list_backups()
    return ok(backups)


@app.post("/upkeep/restore/{backup_name:path}")
async def restore_backup(backup_name: str, request: Request) -> ApiResponse:
    """Restore Vyper data from a backup archive.

    Before restoring, automatically creates a pre-restore backup
    so the operation can be rolled back if needed. The backup name
    can be provided with or without the ``.tar.gz`` extension.

    **This is a destructive operation** — it overwrites current
    data in ``/data/`` with the contents of the backup.
    """
    state = _get_state(request)

    # Sanitise backup name to prevent path traversal
    if ".." in backup_name or "/" in backup_name:
        raise err("Invalid backup name", status_code=400)

    result = await state.backup_mgr.restore_backup(backup_name)
    if not result.success:
        raise err(f"Restore failed: {result.error}", status_code=500)

    log.info(
        "upkeep.restore_complete",
        backup=backup_name,
        pre_restore=result.pre_restore_backup,
    )
    return ok(result)


# ── Metrics ────────────────────────────────────────────────


@app.get("/upkeep/metrics")
async def get_metrics(request: Request) -> ApiResponse:
    """Get aggregated metrics from all Vyper services.

    Queries every registered service's ``/health`` endpoint
    concurrently and aggregates the results. Returns per-service
    snapshots plus a computed summary (precision, recall, F1,
    audit counts, etc.).
    """
    state = _get_state(request)

    try:
        aggregated = await state.metrics_mgr.aggregate_all()
        return ok(aggregated)
    except Exception as exc:
        log.exception("upkeep.metrics_failed", error=str(exc))
        raise err(f"Metrics aggregation failed: {exc}", status_code=500)


@app.get("/upkeep/metrics/summary")
async def get_metrics_summary(request: Request) -> ApiResponse:
    """Get a concise, dashboard-friendly metrics summary.

    Returns a lightweight summary of key platform metrics without
    per-service details. Uses cached data if available to avoid
    querying all services on every request.
    """
    state = _get_state(request)

    try:
        summary = await state.metrics_mgr.get_summary()
        return ok(summary)
    except Exception as exc:
        log.exception("upkeep.metrics_summary_failed", error=str(exc))
        raise err(f"Metrics summary failed: {exc}", status_code=500)


# ── Resource Governor ─────────────────────────────────────

from src.resource_governor import create_resource_governor

# Initialize governor on module level
_governor: ResourceGovernor | None = None


@app.get("/upkeep/governor/status")
async def governor_status(request: Request) -> ApiResponse:
    """Get current resource governor status."""
    global _governor
    if _governor is None:
        _governor = create_resource_governor()
    return ok({
        "load": _governor.current_load.value,
        "state": {
            "cpu_percent": _governor.state.cpu_percent,
            "memory_percent": _governor.state.memory_percent,
            "battery_percent": _governor.state.battery_percent,
            "is_on_battery": _governor.state.is_on_battery,
        },
    })


@app.get("/upkeep/governor/stats")
async def governor_stats(request: Request) -> ApiResponse:
    """Get resource usage statistics."""
    global _governor
    if _governor is None:
        _governor = create_resource_governor()
    state = _governor.state
    return ok({
        "cpu_percent": state.cpu_percent,
        "memory_percent": state.memory_percent,
        "load": state.load.value,
        "battery": {
            "percent": state.battery_percent,
            "on_battery": state.is_on_battery,
        },
    })


# ── Entry Point ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8012,
        log_level="info",
        reload=False,
    )
