"""Dashboard and WebSocket routes."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.models import ApiResponse
from src.state import log, ok, sync_manager

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard() -> ApiResponse:
    """Full dashboard data: overview + chain heatmap + timeline."""
    dash = sync_manager.get_dashboard()
    return ok(dash)


@router.websocket("/ws/dashboard")
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
