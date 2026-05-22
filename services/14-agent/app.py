"""Vyper Agent Service — AI Agent with ReAct loop + Skills + Memory.

Port: 8014

Endpoints:
  POST /agent/run            → Start agent task (full audit pipeline)
  GET  /agent/{id}           → Get session status & steps
  GET  /agent/sessions       → List all sessions
  POST /agent/stop/{id}      → Stop running session
  GET  /skills               → List all registered skills
  GET  /memory               → Get memory contents
  POST /memory/search        → Search across memory stores
  GET  /memory/stats         → Get memory store statistics
  POST /daemon/start         → Start autonomous daemon
  POST /daemon/stop          → Stop autonomous daemon
  GET  /daemon/status        → Get daemon status
  POST /learning/feedback    → Submit session feedback
  GET  /learning/stats       → Get learning statistics
  GET  /learning/recommendations → Get learning recommendations
  GET  /health               → Health check
"""

from __future__ import annotations

import sys
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.agent import AgentLoop
from src.daemon import AgentDaemon
from src.lead_auditor import LeadAuditor
from src.learning.feedback import FeedbackLearner
from src.llm import AgentReasoningClient
from src.memory import AgentMemory
from src.models import (
    AgentRequest,
    AgentResponse,
    AgentRole,
    AgentSession,
    AgentState,
    ApiResponse,
    ErrorResponse,
    HealthData,
    Meta,
    SkillDefinition,
    TaskType,
    to_serializable,
)
from src.organization import get_all_personas, get_persona
from src.skills.registry import SkillRegistry
from src.skills.fetch_program import FetchProgramSkill
from src.skills.fetch_source import FetchSourceSkill
from src.skills.scan_contract import ScanContractSkill
from src.skills.analyze_findings import AnalyzeFindingsSkill
from src.skills.classify_finding import ClassifyFindingSkill
from src.skills.exploit_test import ExploitTestSkill
from src.skills.generate_report import GenerateReportSkill
from shared.observability import setup_observability
from src.skills.notify import NotifySkill

# ── Constants ──────────────────────────────────────────────

SERVICE_NAME = "agent"
SERVICE_VERSION = "0.1.0"
CONFIG_URL = "http://01-config:8000"

# ── App State ──────────────────────────────────────────────


class AppState:
    def __init__(self) -> None:
        self.registry: SkillRegistry | None = None
        self.llm: AgentReasoningClient | None = None
        self.agent: AgentLoop | None = None
        self.lead_auditor: LeadAuditor | None = None
        self.daemon: AgentDaemon | None = None
        self.learner: FeedbackLearner | None = None
        self.http_client: httpx.AsyncClient | None = None


state: AppState | None = None


async def _load_config(client: httpx.AsyncClient) -> dict[str, Any]:
    """Load agent config from Config Service."""
    defaults = {
        "openai_model": "gpt-4o",
        "anthropic_model": "claude-3-5-sonnet-20241022",
        "preferred_provider": "openai",
        "openai_api_key": "",
        "anthropic_api_key": "",
        "max_steps": 25,
    }

    try:
        for key in (
            "openai_model", "anthropic_model", "preferred_provider",
            "provider_openai_api_key", "provider_anthropic_api_key",
            "agent_max_steps",
        ):
            resp = await client.get(f"{CONFIG_URL}/config/{key}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("data") and key in data["data"]:
                    config_key = key.replace("provider_openai_api_key", "openai_api_key")
                    config_key = config_key.replace("provider_anthropic_api_key", "anthropic_api_key")
                    config_key = config_key.replace("agent_", "")
                    if config_key == "max_steps":
                        defaults["max_steps"] = int(data["data"][key])
                    else:
                        defaults[config_key] = data["data"][key]
    except Exception as exc:
        log.warning("config_service_unreachable", error=str(exc))

    return defaults


# ── Lifespan ───────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: init LLM, registry, agent. Shutdown: cleanup."""
    global state
    state = AppState()

    state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=10.0),
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=30),
    )

    # Load config (API keys dari Config Service, diset via frontend)
    config = await _load_config(state.http_client)

    # Init LLM client
    state.llm = AgentReasoningClient(
        openai_key=config["openai_api_key"],
        anthropic_key=config["anthropic_api_key"],
        openai_model=config["openai_model"],
        anthropic_model=config["anthropic_model"],
        preferred_provider=config["preferred_provider"],
        http_client=state.http_client,
    )

    # Init Skill Registry — daftarkan semua skill
    registry = SkillRegistry()
    registry.register(FetchProgramSkill(state.http_client))
    registry.register(FetchSourceSkill(state.http_client))
    registry.register(ScanContractSkill(state.http_client))
    registry.register(AnalyzeFindingsSkill(state.http_client))
    registry.register(ClassifyFindingSkill(state.http_client))
    registry.register(ExploitTestSkill(state.http_client))
    registry.register(GenerateReportSkill(state.http_client))
    registry.register(NotifySkill(state.http_client))
    state.registry = registry

    # Init Agent Loop
    state.agent = AgentLoop(
        registry=registry,
        llm=state.llm,
        http_client=state.http_client,
    )

    # Init Lead Auditor + Team
    state.lead_auditor = LeadAuditor(
        llm=state.llm,
        http_client=state.http_client,
    )
    state.lead_auditor.set_global_registry(registry)

    # Register all sub-agents (skip Lead Auditor)
    persona_count = 0
    for persona in get_all_personas():
        if persona.role == AgentRole.LEAD_AUDITOR:
            continue
        state.lead_auditor.register_sub_agent(persona.role)
        persona_count += 1

    # Init Daemon (tidak auto-start — via API)
    state.daemon = AgentDaemon(
        agent=state.agent,
        http_client=state.http_client,
        interval=3600,
    )

    # Init Feedback Learner
    state.learner = FeedbackLearner(memory=state.agent.memory)

    log.info(
        "agent_service_started",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        skills=registry.count,
        team_members=persona_count,
        provider=config["preferred_provider"],
        openai_configured=bool(config["openai_api_key"]),
        anthropic_configured=bool(config["anthropic_api_key"]),
    )

    yield

    # Shutdown
    log.info("agent_service_shutting_down")
    if state.http_client:
        await state.http_client.aclose()
    log.info("agent_service_stopped")


# ── Application ────────────────────────────────────────────

app = FastAPI(
    title="Vyper Agent Service",
    description="AI Agent with ReAct loop, skills, and memory for smart contract auditing",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

log = setup_observability(app, "14-agent", "0.1.0")


# ── Helpers ────────────────────────────────────────────────


def _ok(data: Any = None) -> ApiResponse:
    return ApiResponse(data=data, meta=Meta(status="ok"))


def _err(detail: str, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


# ── Endpoints ──────────────────────────────────────────────


@app.get("/health")
async def health() -> ApiResponse:
    """Health check — service status, skills loaded, active sessions."""
    if state is None or state.agent is None:
        raise _err("Service not initialized", 503)
    return _ok(
        HealthData(
            status="ok",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
            active_sessions=state.agent.active_sessions,
            skills_loaded=state.registry.count if state.registry else 0,
            memory_entries=state.agent.memory.total_entries,
        )
    )


@app.post("/agent/run")
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
    if state is None or state.agent is None:
        raise _err("Service not initialized", 503)

    if not body.input_data:
        raise _err("input_data is required")

    log.info(
        "agent.run_requested",
        task_type=body.task_type.value,
        goal=body.goal[:100] if body.goal else "auto",
    )

    try:
        session: AgentSession = await state.agent.run(
            task_type=body.task_type,
            input_data=body.input_data,
            goal=body.goal,
            max_steps=body.max_steps,
        )
    except Exception as exc:
        log.exception("agent.run_failed")
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


@app.get("/agent/sessions")
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
) -> ApiResponse:
    """List all agent sessions."""
    if state is None or state.agent is None:
        raise _err("Service not initialized", 503)

    sessions = state.agent.list_sessions(limit=limit, status=status)
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


@app.get("/agent/{session_id}")
async def get_session(session_id: str) -> ApiResponse:
    """Get agent session details with all steps."""
    if state is None or state.agent is None:
        raise _err("Service not initialized", 503)

    session = state.agent.get_session(session_id)
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


@app.get("/skills")
async def list_skills() -> ApiResponse:
    """List all registered skills that the agent can use."""
    if state is None or state.registry is None:
        raise _err("Service not initialized", 503)

    skills = state.registry.list_skills()
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


@app.get("/skills/metrics")
async def skill_metrics() -> ApiResponse:
    """Get usage metrics for all skills."""
    if state is None or state.registry is None:
        raise _err("Service not initialized", 503)

    return _ok(state.registry.get_all_metrics())


@app.get("/memory")
async def get_memory() -> ApiResponse:
    """Get current agent memory contents."""
    if state is None or state.agent is None:
        raise _err("Service not initialized", 503)

    memory = state.agent.memory
    return _ok({
        "working": {k: _truncate(v) for k, v in memory.working.items()},
        "episodic": [
            {
                "key": e.key,
                "content": _truncate(e.content),
                "timestamp": e.timestamp,
            }
            for e in memory.last_episodes(10)
        ],
        "semantic": {k: _truncate(v) for k, v in list(memory.semantic.items())[:10]},
        "total_entries": memory.total_entries,
    })


# ── Daemon Endpoints (T8+T10) ──────────────────────────────


@app.post("/daemon/start")
async def daemon_start() -> ApiResponse:
    """Start the autonomous daemon background loop."""
    if state is None or state.daemon is None:
        raise _err("Service not initialized", 503)

    started = state.daemon.start()
    return _ok({
        "running": state.daemon.is_running,
        "started": started,
        "message": "Daemon started" if started else "Daemon already running",
    })


@app.post("/daemon/stop")
async def daemon_stop() -> ApiResponse:
    """Stop the daemon background loop."""
    if state is None or state.daemon is None:
        raise _err("Service not initialized", 503)

    stopped = await state.daemon.stop()
    return _ok({
        "running": state.daemon.is_running,
        "stopped": stopped,
        "message": "Daemon stopped" if stopped else "Daemon was not running",
    })


@app.get("/daemon/status")
async def daemon_status() -> ApiResponse:
    """Get daemon status and statistics."""
    if state is None or state.daemon is None:
        raise _err("Service not initialized", 503)

    return _ok(state.daemon.get_status())


# ── Memory Search Endpoint (T11) ───────────────────────────


class MemorySearchRequest(BaseModel):
    query: str
    store: str = "vector"  # vector | episodic | graph
    limit: int = 10
    filters: dict[str, Any] = Field(default_factory=dict)


@app.post("/memory/search")
async def memory_search(body: MemorySearchRequest) -> ApiResponse:
    """Search across memory stores.

    **Request body**::

        {
            "query": "reentrancy vulnerability",
            "store": "vector",
            "limit": 10
        }
    """
    if state is None or state.agent is None:
        raise _err("Service not initialized", 503)

    memory = state.agent.memory

    try:
        if body.store == "vector":
            results = await memory.vector.search(
                body.query, limit=body.limit, **body.filters
            )
        elif body.store == "episodic":
            results = await memory.episodic_store.search(
                body.query, limit=body.limit, **body.filters
            )
        elif body.store == "graph":
            results = await memory.graph.search(
                body.query, limit=body.limit, **body.filters
            )
        else:
            raise _err(f"Unknown store: {body.store}", 400)

        return _ok({
            "store": body.store,
            "query": body.query,
            "results": results,
            "total": len(results),
        })
    except Exception as exc:
        raise _err(f"Memory search failed: {exc}", 500)


# ── Feedback & Learning Endpoints (T9+T12+T14) ────────────


class FeedbackRequest(BaseModel):
    session_id: str
    rating: int = Field(default=3, ge=1, le=5)
    comment: str = ""
    tags: list[str] = Field(default_factory=list)


@app.post("/learning/feedback")
async def submit_feedback(body: FeedbackRequest) -> ApiResponse:
    """Submit feedback for a completed session."""
    if state is None or state.agent is None:
        raise _err("Service not initialized", 503)

    session = state.agent.get_session(body.session_id)
    if session is None:
        raise _err(f"Session not found: {body.session_id}", 404)

    # Store feedback in vector memory
    memory = state.agent.memory
    try:
        await memory.vector.store(
            f"feedback_{body.session_id[:8]}",
            f"Session {body.session_id[:8]}: rating={body.rating}/5, {body.comment}",
            metadata={
                "type": "feedback",
                "session_id": body.session_id,
                "rating": body.rating,
                "tags": body.tags,
                "comment": body.comment[:200],
            },
        )
    except Exception as exc:
        log.warning("feedback_store_failed", error=str(exc))

    return _ok({
        "submitted": True,
        "session_id": body.session_id,
        "rating": body.rating,
    })


@app.get("/learning/stats")
async def learning_stats() -> ApiResponse:
    """Get learning statistics."""
    if state is None or state.learner is None:
        raise _err("Service not initialized", 503)

    return _ok(state.learner.get_stats())


@app.get("/learning/recommendations")
async def learning_recommendations(
    task_type: str | None = None,
) -> ApiResponse:
    """Get learning-based recommendations.

    **Query params**::
        task_type: Optional filter by task type
    """
    if state is None or state.learner is None:
        raise _err("Service not initialized", 503)

    recommendations = await state.learner.get_recommendations(
        task_type=task_type
    )
    return _ok(recommendations)


# ── Memory Stats Endpoint (T14) ────────────────────────────


@app.get("/memory/stats")
async def memory_stats() -> ApiResponse:
    """Get detailed memory store statistics."""
    if state is None or state.agent is None:
        raise _err("Service not initialized", 503)

    return _ok(state.agent.memory.get_all_stats())


# ── Team Endpoints ───────────────────────────────────────────


@app.post("/team/run")
async def run_team_audit(body: dict[str, Any]) -> ApiResponse:
    """Start a team-based audit with Lead Auditor + sub-agents.

    The Lead Auditor will plan the audit, delegate tasks to
    specialized team members, and synthesize results.

    **Request body**::

        {
            "task_type": "full_audit",
            "input_data": {
                "contract_address": "0x...",
                "chain": "ethereum",
                "program_slug": "ethena"
            },
            "goal": "Full audit of USDe contract",
            "max_delegations": 15
        }
    """
    if state is None or state.lead_auditor is None:
        raise _err("Service not initialized", 503)

    task_type = body.get("task_type", "full_audit")
    input_data = body.get("input_data", {})
    goal = body.get("goal", "")
    max_delegations = body.get("max_delegations", 15)

    if not input_data:
        raise _err("input_data is required")

    log.info(
        "team_audit_requested",
        task_type=task_type,
        goal=goal[:100] if goal else "auto",
    )

    try:
        session = await state.lead_auditor.run_team_audit(
            task_type=task_type,
            input_data=input_data,
            goal=goal,
            max_delegations=max_delegations,
        )
    except Exception as exc:
        log.exception("team_audit_failed")
        raise _err(f"Team audit failed: {exc}", 500)

    return _ok({
        "team_session_id": session.team_session_id,
        "status": session.status.value,
        "goal": session.goal,
        "lead_steps": [
            {
                "step": s.step_number,
                "action": s.action,
                "status": s.status.value,
                "observation": s.observation[:200] if s.observation else "",
            }
            for s in session.lead_steps
        ],
        "sub_agents": {
            role: {
                "status": sa.status.value,
                "task": sa.task[:100],
                "steps": len(sa.steps),
                "summary": sa.summary[:200] if sa.summary else "",
            }
            for role, sa in session.sub_agents.items()
        },
        "output": to_serializable(session.output_data),
        "error": session.error,
    })


@app.get("/team/sessions")
async def list_team_sessions(
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
) -> ApiResponse:
    """List all team audit sessions."""
    if state is None or state.lead_auditor is None:
        raise _err("Service not initialized", 503)

    sessions = state.lead_auditor.list_sessions(limit=limit, status=status)
    return _ok({
        "sessions": [
            {
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


@app.get("/team/{session_id}")
async def get_team_session(session_id: str) -> ApiResponse:
    """Get team session details with all delegation steps."""
    if state is None or state.lead_auditor is None:
        raise _err("Service not initialized", 503)

    session = state.lead_auditor.get_session(session_id)
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


@app.get("/team/structure")
async def get_team_structure() -> ApiResponse:
    """Get the team organizational structure with all roles."""
    if state is None or state.lead_auditor is None:
        raise _err("Service not initialized", 503)

    roles = []
    for persona in get_all_personas():
        sub = state.lead_auditor.get_sub_agent(persona.role) if persona.role != AgentRole.LEAD_AUDITOR else None
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


# ── Helpers ──────────────────────────────────────────────────


def _truncate(value: Any, max_len: int = 200) -> Any:
    """Truncate long string values for display."""
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + "..."
    if isinstance(value, dict):
        return {k: _truncate(v, max_len) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate(v, max_len) for v in value[:5]]
    return value


# ── Exception Handler ─────────────────────────────────────


@app.exception_handler(Exception)
async def unhandled_exception(request: Any, exc: Exception) -> JSONResponse:
    log.exception("unhandled_exception")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            meta=Meta(status="error", error=str(exc))
        ).model_dump(),
    )


# ── Entry Point ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8019,
        log_level="info",
        reload=False,
    )
