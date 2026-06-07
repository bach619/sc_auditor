from __future__ import annotations

import app
from app import _err, _ok
from fastapi import APIRouter
from src.models import ApiResponse

router = APIRouter()


@router.get("/skills")
async def list_skills() -> ApiResponse:
    """List all registered skills that the agent can use."""
    if app.state is None or app.state.registry is None:
        raise _err("Service not initialized", 503)

    skills = app.state.registry.list_skills()
    return _ok({
        "total": len(skills),
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "parameters": s.parameters,
            }
            for s in skills
        ],
    })


@router.get("/skills/metrics")
async def skill_metrics() -> ApiResponse:
    """Get usage metrics for all skills."""
    if app.state is None or app.state.registry is None:
        raise _err("Service not initialized", 503)

    return _ok(app.state.registry.get_all_metrics())
