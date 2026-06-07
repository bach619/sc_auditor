from __future__ import annotations

import app
from app import _err, _ok
from fastapi import APIRouter, Query
from src.models import AgentResponse, ApiResponse

router = APIRouter()


@router.get("/agent/sessions")
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
) -> ApiResponse:
    """List all agent sessions."""
    if app.state is None or app.state.agent is None:
        raise _err("Service not initialized", 503)

    sessions = app.state.agent.list_sessions(limit=limit, status=status)
    return _ok({
        "sessions": [
            {
                "session_id": s.session_id,
                "task_type": s.task_type.value,
                "status": s.status.value,
                "goal": s.goal[:100],
                "steps": len(s.steps),
                "created_at": s.created_at,
                "error": s.error,
            }
            for s in sessions
        ],
        "total": len(sessions),
    })


@router.get("/agent/{session_id}")
async def get_session(session_id: str) -> ApiResponse:
    """Get agent session details with all steps."""
    if app.state is None or app.state.agent is None:
        raise _err("Service not initialized", 503)

    session = app.state.agent.get_session(session_id)
    if session is None:
        raise _err(f"Session not found: {session_id}", 404)

    return _ok(
        AgentResponse(
            session_id=session.session_id,
            status=session.status,
            steps=session.steps,
            output=session.output_data,
            error=session.error,
        )
    )
