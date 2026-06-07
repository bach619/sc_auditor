from __future__ import annotations

import app
from app import _err, _ok
from fastapi import APIRouter
from src.models import ApiResponse

router = APIRouter()


@router.post("/daemon/start")
async def daemon_start() -> ApiResponse:
    """Start the autonomous daemon background loop."""
    if app.state is None or app.state.daemon is None:
        raise _err("Service not initialized", 503)

    started = app.state.daemon.start()
    return _ok({
        "running": app.state.daemon.is_running,
        "started": started,
        "message": "Daemon started" if started else "Daemon already running",
    })


@router.post("/daemon/stop")
async def daemon_stop() -> ApiResponse:
    """Stop the daemon background loop."""
    if app.state is None or app.state.daemon is None:
        raise _err("Service not initialized", 503)

    stopped = await app.state.daemon.stop()
    return _ok({
        "running": app.state.daemon.is_running,
        "stopped": stopped,
        "message": "Daemon stopped" if stopped else "Daemon was not running",
    })


@router.get("/daemon/status")
async def daemon_status() -> ApiResponse:
    """Get daemon status and statistics."""
    if app.state is None or app.state.daemon is None:
        raise _err("Service not initialized", 503)

    return _ok(app.state.daemon.get_status())
