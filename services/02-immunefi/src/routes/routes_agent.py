"""Agent endpoint routes."""

from __future__ import annotations

from fastapi import APIRouter

from shared.agent_protocol.models import DelegationRequest, NegotiationRequest

from src.models import ApiResponse
from src.state import _immunefi_agent, ok

router = APIRouter()


@router.get("/agent/manifest")
async def agent_manifest() -> ApiResponse:
    """Get agent capabilities and skill manifest."""
    agent = _immunefi_agent
    if not agent:
        return ok({"error": "Agent not initialized"})
    manifest = agent.get_manifest()
    return ok(manifest)


@router.post("/agent/delegate")
async def agent_delegate(body: dict) -> ApiResponse:
    """Delegate a task to the Immunefi agent."""
    agent = _immunefi_agent
    if not agent:
        return ok({"error": "Agent not initialized"})

    request = DelegationRequest(
        task_id=body.get("task_id", ""),
        goal=body.get("goal", ""),
        capability=body.get("capability", ""),
        input_data=body.get("input_data", {}),
        constraints=body.get("constraints", {}),
        parent_session_id=body.get("parent_session_id", ""),
        priority=body.get("priority", "normal"),
    )
    response = await agent.handle_delegation(request)
    return ok(response)


@router.post("/agent/negotiate")
async def agent_negotiate(body: dict) -> ApiResponse:
    """Negotiate task feasibility with the agent."""
    agent = _immunefi_agent
    if not agent:
        return ok({"error": "Agent not initialized"})

    request = NegotiationRequest(
        task_description=body.get("task_description", ""),
        required_capability=body.get("required_capability", ""),
        estimated_complexity=body.get("estimated_complexity", "medium"),
        budget_usd=body.get("budget_usd", 0.0),
        deadline_seconds=body.get("deadline_seconds", 0),
    )
    response = await agent.handle_negotiation(request)
    return ok(response)
