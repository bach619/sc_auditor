from __future__ import annotations

import app
from app import _err, _ok
from fastapi import APIRouter
from src.models import (
    AgentRequest,
    AgentResponse,
    AgentSession,
    ApiResponse,
    ChatRequest,
    ChatResponse,
    HealthData,
)

router = APIRouter()


@router.get("/health")
async def health() -> ApiResponse:
    """Health check — service status, skills loaded, active sessions."""
    if app.state is None or app.state.agent is None:
        raise _err("Service not initialized", 503)
    return _ok(
        HealthData(
            status="ok",
            service=app.SERVICE_NAME,
            version=app.SERVICE_VERSION,
            active_sessions=app.state.agent.active_sessions,
            skills_loaded=app.state.registry.count if app.state.registry else 0,
            memory_entries=app.state.agent.memory.total_entries,
        )
    )


@router.get("/agent/provider-defaults")
async def agent_provider_defaults() -> ApiResponse:
    """Get the default provider configuration values.

    Returns the PROVIDER_DEFAULTS dict so the frontend can
    reset misconfigured providers to known-good values.
    """
    from src.llm import PROVIDER_DEFAULTS  # noqa: PLC0415

    return _ok({
        "defaults": PROVIDER_DEFAULTS,
        "note": "Set base_url and api_type to these defaults to fix misconfiguration",
    })


@router.post("/agent/reload-providers")
async def agent_reload_providers() -> ApiResponse:
    """Reload AI provider configs from Config Service.

    Called by dashboard after user saves API keys in Settings.
    This is needed because the agent loads providers ONCE at startup
    and doesn't auto-detect changes.
    """
    if app.state is None or app.state.llm is None:
        raise _err("Service not initialized", 503)

    providers = await app._load_providers(app.state.http_client)
    config = await app._load_config(app.state.http_client)
    preferred = config.get("preferred_provider", "openai")

    # Validate before patching
    errors = app._validate_provider_urls(providers)
    if errors:
        app.log.warning("provider_validation", warnings=errors)

    app.state.llm.providers = providers
    app.state.llm.preferred_provider = preferred

    # Count configured providers
    configured = sum(1 for v in providers.values() if v.get("api_key"))
    app.log.info("providers_reloaded", configured=configured, preferred=preferred)

    return _ok({
        "configured": configured,
        "preferred": preferred,
        "validation_warnings": errors,
    })


@router.get("/agent/manifest")
async def agent_manifest() -> ApiResponse:
    """Publish Antonio manifest for discovery by backend agents."""
    if app.state is None or app.state.registry is None:
        raise _err("Service not initialized", 503)

    skills_info = []
    for skill in app.state.registry.list_skills():
        skills_info.append({
            "name": skill.name,
            "description": skill.description,
            "parameters": skill.parameters,
            "input_schema": {"type": "object", "properties": skill.parameters or {}},
            "output_schema": {"type": "object"},
        })

    active = app.state.agent.active_sessions if app.state.agent else 0

    manifest = {
        "service_name": "14-agent",
        "agent_role": "antonio",
        "version": "0.2.0",
        "capabilities": skills_info,
        "constraints": {
            "max_concurrent_tasks": 5,
            "requires_api_key": True,
            "max_context_length": 16000,
        },
        "current_load": {
            "active_tasks": active,
            "queue_depth": 0,
            "status": "idle" if active == 0 else "busy",
        },
    }
    return _ok(manifest)


@router.get("/agent/registry")
async def agent_registry_status() -> ApiResponse:
    """List all discovered backend agents and their capabilities."""
    if app.state is None or app.state.agent_registry is None:
        raise _err("Agent registry not initialized", 503)

    agents = app.state.agent_registry.get_all_agents()
    return _ok({
        "total_agents": len(agents),
        "agents": [
            {
                "service": a.service_name,
                "role": a.agent_role,
                "capabilities": [c.name.value for c in a.capabilities],
                "status": a.current_load.get("status", "unknown"),
                "active_tasks": a.current_load.get("active_tasks", 0),
            }
            for a in agents
        ],
    })


@router.post("/agent/run")
async def run_agent(body: AgentRequest) -> ApiResponse:
    """Start an agent task.

    The agent will run the ReAct loop, calling skills
    as needed until the task is complete.

    **Request body**::

        {
            "task_type": "full_audit",
            "input_data": {
                "contract_address": "0x4c9edd5852cd905f086c759e8383e09bff1e68b3",
                "chain": "ethereum",
                "program_slug": "ethena"
            },
            "goal": "Full audit of USDe contract",
            "max_steps": 25
        }
    """
    if app.state is None or app.state.agent is None:
        raise _err("Service not initialized", 503)

    if not body.input_data:
        raise _err("input_data is required")

    app.log.info(
        "agent.run_requested",
        task_type=body.task_type.value,
        goal=body.goal[:100] if body.goal else "auto",
    )

    try:
        session: AgentSession = await app.state.agent.run(
            task_type=body.task_type,
            input_data=body.input_data,
            goal=body.goal,
            max_steps=body.max_steps,
        )
    except Exception as exc:
        app.log.exception("agent.run_failed")
        raise _err(f"Agent execution failed: {exc}", 500)

    return _ok(
        AgentResponse(
            session_id=session.session_id,
            status=session.status,
            steps=session.steps,
            output=session.output_data,
            error=session.error,
        )
    )


@router.post("/agent/chat")
async def agent_chat(body: ChatRequest) -> ApiResponse:
    """Chat dengan Antonio menggunakan natural language.

    Antonio akan memahami intent user, memanggil skill yang diperlukan
    (audit, search memory, dll), dan merespon dalam bahasa yang sama.

    **Request body**::

        {
            "message": "audit contract 0x4c9edd5852cd905f086c759e8383e09bff1e68b3",
            "session_id": null
        }

    Returns:
        ChatResponse dengan jawaban natural language Antonio.
    """
    if app.state is None or app.state.agent is None:
        raise _err("Service not initialized", 503)

    app.log.info(
        "agent.chat_requested",
        message=body.message[:100],
        has_session=body.session_id is not None,
    )

    try:
        result: ChatResponse = await app.state.agent.chat(
            message=body.message,
            session_id=body.session_id,
        )
    except Exception as exc:
        err_msg = str(exc).strip() or type(exc).__name__
        app.log.exception("agent.chat_failed", error=err_msg)
        raise _err(
            f"Chat failed: {err_msg}. "
            "Check your AI provider configuration in Settings > AI Providers.",
            500,
        )

    return _ok(result.model_dump())


@router.get("/agent/chat/sessions")
async def list_chat_sessions() -> ApiResponse:
    """List all chat sessions with full message history.

    Returns all chat conversations that have been persisted
    to local storage (~/.sc_auditor/learning/chat_sessions.json).
    """
    if app.state is None or app.state.agent is None:
        raise _err("Service not initialized", 503)

    sessions = app.state.agent.list_chat_sessions()
    return _ok({
        "sessions": sessions,
        "total": len(sessions),
    })
