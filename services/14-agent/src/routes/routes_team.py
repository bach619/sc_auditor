from __future__ import annotations

import asyncio
from typing import Any

import app
from app import _err, _ok
from fastapi import APIRouter, Query
from src.models import AgentRole, ApiResponse, to_serializable
from src.organization import get_all_personas

router = APIRouter()


@router.post("/team/run")
async def run_team_audit(body: dict[str, Any]) -> ApiResponse:
    """Start a team-based audit with Lead Auditor + sub-agents.

    Returns immediately with session_id. The audit runs in the background.
    Poll GET /team/{session_id} to track progress.

    **Request body**::

        {
            "task_type": "full_audit",
            "input_data": {
                "contract_address": "0x...",
                "chain": "ethereum"
            },
            "goal": "Full audit of contract",
            "max_delegations": 15
        }

    **Response**::

        {
            "session_id": "team-abc123",
            "status": "running",
            "goal": "...",
            "created_at": "..."
        }
    """
    if app.state is None or app.state.lead_auditor is None:
        raise _err("Service not initialized", 503)

    task_type = body.get("task_type", "full_audit")
    input_data = body.get("input_data", {})
    goal = body.get("goal", "")
    max_delegations = body.get("max_delegations", 15)

    if input_data is None:
        raise _err("input_data is required")

    app.log.info(
        "team_audit_requested",
        task_type=task_type,
        goal=goal[:100] if goal else "auto",
    )

    # Fire-and-forget: create session, start background task, return immediately
    session_id, session = app.state.lead_auditor.create_session(
        task_type=task_type,
        input_data=input_data,
        goal=goal,
    )

    # Launch the actual audit as a background task
    asyncio.create_task(
        app.state.lead_auditor.run_session(
            session_id=session_id,
            max_delegations=max_delegations,
        )
    )

    return _ok({
        "session_id": session_id,
        "team_session_id": session_id,
        "status": "running",
        "goal": goal[:100] if goal else "auto",
        "created_at": session.created_at,
    })


@router.get("/team/sessions")
async def list_team_sessions(
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
) -> ApiResponse:
    """List all team audit sessions."""
    if app.state is None or app.state.lead_auditor is None:
        raise _err("Service not initialized", 503)

    sessions = app.state.lead_auditor.list_sessions(limit=limit, status=status)
    return _ok({
        "sessions": [
            {
                "session_id": s.team_session_id,  # alias for frontend compatibility
                "team_session_id": s.team_session_id,
                "task_type": s.task_type,
                "status": s.status.value,
                "goal": s.goal[:100],
                "lead_steps": len(s.lead_steps),
                "sub_agents": list(s.sub_agents.keys()),
                "created_at": s.created_at,
                "error": s.error,
            }
            for s in sessions
        ],
        "total": len(sessions),
    })


@router.get("/team/structure")
async def get_team_structure() -> ApiResponse:
    """Get the team organizational structure with all roles."""
    if app.state is None or app.state.lead_auditor is None:
        raise _err("Service not initialized", 503)

    roles = []
    for persona in get_all_personas():
        sub = app.state.lead_auditor.get_sub_agent(persona.role) if persona.role != AgentRole.LEAD_AUDITOR else None
        roles.append({
            "role": persona.role.value,
            "title": persona.title,
            "expertise": persona.expertise,
            "allowed_skills": persona.allowed_skills,
            "registered": sub is not None if persona.role != AgentRole.LEAD_AUDITOR else True,
            "skills_loaded": sub.registry.count if sub else 0,
        })

    return _ok({
        "team_size": len(roles),
        "roles": roles,
    })


@router.get("/team/{session_id}")
async def get_team_session(session_id: str) -> ApiResponse:
    """Get team session details with all delegation steps."""
    if app.state is None or app.state.lead_auditor is None:
        raise _err("Service not initialized", 503)

    session = app.state.lead_auditor.get_session(session_id)
    if session is None:
        raise _err(f"Team session not found: {session_id}", 404)

    return _ok({
        "team_session_id": session.team_session_id,
        "task_type": session.task_type,
        "status": session.status.value,
        "goal": session.goal,
        "input_data": session.input_data,
        "lead_steps": [
            {
                "step": s.step_number,
                "thought": s.thought,
                "action": s.action,
                "action_input": s.action_input,
                "observation": s.observation,
                "action_output": to_serializable(s.action_output),
                "status": s.status.value,
                "duration_ms": s.duration_ms,
            }
            for s in session.lead_steps
        ],
        "sub_agents": {
            role: {
                "role": sa.role.value,
                "status": sa.status.value,
                "task": sa.task,
                "summary": sa.summary,
                "steps": [
                    {
                        "step": s.step_number,
                        "action": s.action,
                        "status": s.status.value,
                        "observation": s.observation[:300],
                        "duration_ms": s.duration_ms,
                    }
                    for s in sa.steps
                ],
                "output": to_serializable(sa.output),
                "error": sa.error,
            }
            for role, sa in session.sub_agents.items()
        },
        "output": to_serializable(session.output_data),
        "error": session.error,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    })
