"""Antonio Agent Service — AI Agent with ReAct loop + Skills + Memory.

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
  GET  /knowledge            → Get loaded system knowledge (SYSTEM_KNOWLEDGE.md)
  POST /daemon/start         → Start autonomous daemon (14-agent)
  POST /daemon/stop          → Stop autonomous daemon (14-agent)
  GET  /daemon/status        → Get daemon status (14-agent)
  POST /learning/feedback    → Submit session feedback
  GET  /learning/stats       → Get learning statistics
  GET  /learning/recommendations → Get learning recommendations
  GET  /health               → Health check
  ═══════════════════════════════════════════════════════════
  Antonio Gateway (Supreme Controller — proxied to Orchestrator):
  POST /audit                         → Start audit
  POST /orchestrator/daemon/start     → Start Orchestrator daemon
  POST /orchestrator/daemon/stop      → Stop Orchestrator daemon
  GET  /orchestrator/daemon/status    → Get Orchestrator daemon status
  ═══════════════════════════════════════════════════════════
"""

from __future__ import annotations

import sys
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.agent import AgentLoop
from src.daemon import AgentDaemon
from src.lead_auditor import LeadAuditor
from src.learning.feedback import FeedbackLearner
from src.llm import AgentReasoningClient
from src.memory import AgentMemory
from src.utils.circuit_breaker import all_circuit_breakers
from src.models import (
    AgentRequest,
    AgentResponse,
    AgentRole,
    AgentSession,
    AgentState,
    ApiResponse,
    ChatRequest,
    ChatResponse,
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
from src.skills.delegate_task import DelegateTaskSkill
from src.skills.deduplicate_findings import DeduplicateFindingsSkill
from shared.agent_protocol.registry import AgentRegistry

# ── Constants ──────────────────────────────────────────────

SERVICE_NAME = "antonio"
SERVICE_VERSION = "0.2.0"
CONFIG_URL = "http://01-config:8000"
ORCHESTRATOR_URL = "http://11-orchestrator:8000"

# ── App State ──────────────────────────────────────────────


class AppState:
    def __init__(self) -> None:
        self.registry: SkillRegistry | None = None
        self.llm: AgentReasoningClient | None = None
        self.agent: AgentLoop | None = None
        self.lead_auditor: LeadAuditor | None = None
        self.daemon: AgentDaemon | None = None
        self.learner: FeedbackLearner | None = None
        self.agent_registry: AgentRegistry | None = None
        self.http_client: httpx.AsyncClient | None = None


state: AppState | None = None


# ── All supported provider config keys (matching Settings.tsx) ──

PROVIDER_CONFIG_KEYS: list[dict[str, str]] = [
    # provider_id: {api_key_config, base_url_config, model_config}
    {"id": "openai",     "api_key": "provider_openai_api_key",     "base_url": "provider_openai_base_url",     "model": "provider_openai_model"},
    {"id": "anthropic",  "api_key": "provider_anthropic_api_key",  "base_url": "provider_anthropic_base_url",  "model": "provider_anthropic_model"},
    {"id": "deepseek",   "api_key": "provider_deepseek_api_key",   "base_url": "provider_deepseek_base_url",   "model": "provider_deepseek_model"},
    {"id": "xai",        "api_key": "provider_xai_api_key",        "base_url": "provider_xai_base_url",        "model": "provider_xai_model"},
    {"id": "openrouter", "api_key": "provider_openrouter_api_key", "base_url": "provider_openrouter_base_url", "model": "provider_openrouter_model"},
    {"id": "google",     "api_key": "provider_google_api_key",     "base_url": "provider_google_base_url",     "model": "provider_google_model"},
    {"id": "huggingface","api_key": "provider_huggingface_api_key","base_url": "provider_huggingface_base_url","model": "provider_huggingface_model"},
]


# ── Provider URL Validation ──────────────────────────────────

# Known domain-to-provider mapping for validation
KNOWN_PROVIDER_DOMAINS: dict[str, str] = {
    "api.openai.com": "openai",
    "api.anthropic.com": "anthropic",
    "api.deepseek.com": "deepseek",
    "api.x.ai": "xai",
    "openrouter.ai": "openrouter",
    "generativelanguage.googleapis.com": "google",
    "api-inference.huggingface.co": "huggingface",
}


def _validate_provider_urls(providers: dict[str, dict[str, str]]) -> list[str]:
    """Validate provider configurations for common mistakes.

    Checks:
    1. Provider's base_url domain should match its provider id
       (e.g., anthropic provider using api.deepseek.com is an error)
    2. Only checks providers that have an API key configured
    3. Uses PROVIDER_DEFAULTS from src.llm for expected api_type

    Returns:
        List of validation error messages (empty = all good)
    """
    from src.llm import PROVIDER_DEFAULTS  # noqa: PLC0415

    errors: list[str] = []

    for pid, cfg in providers.items():
        base_url = cfg.get("base_url", "")
        api_key = cfg.get("api_key", "")

        if not api_key:
            continue  # Skip unconfigured providers

        # Get expected defaults for this provider
        defaults = PROVIDER_DEFAULTS.get(pid, {})
        expected_api_type = defaults.get("api_type", "openai_compatible")

        # Check 1: Anthropic api_type mismatch
        if pid == "anthropic" and expected_api_type != "anthropic":
            errors.append(
                f"Provider '{pid}': expected api_type='anthropic' but "
                f"PROVIDER_DEFAULTS has '{expected_api_type}'. "
                f"Check src/llm.py PROVIDER_DEFAULTS."
            )

        # Check 2: Domain-provider mismatch (e.g., deepseek domain for anthropic)
        if base_url:
            for domain, expected_provider in KNOWN_PROVIDER_DOMAINS.items():
                if domain in base_url and pid != expected_provider:
                    errors.append(
                        f"Provider '{pid}': base_url contains '{domain}' "
                        f"which belongs to '{expected_provider}'. "
                        f"Did you mean to use provider '{expected_provider}'?"
                    )

    return errors


async def _load_providers(client: httpx.AsyncClient) -> dict[str, dict[str, str]]:
    """Load all provider configs from Config Service.

    Returns:
        Dict like::
            {
                "deepseek": {"api_key": "sk-...", "base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
                "openai": {"api_key": "", "base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
                ...
            }
    """
    providers: dict[str, dict[str, str]] = {}

    for pdef in PROVIDER_CONFIG_KEYS:
        pid = pdef["id"]
        providers[pid] = {"api_key": "", "base_url": "", "model": ""}

        # Load each config key from Config Service
        for cfg_key in (pdef["api_key"], pdef["base_url"], pdef["model"]):
            try:
                resp = await client.get(f"{CONFIG_URL}/config/{cfg_key}")
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("data") and cfg_key in data["data"]:
                        value = data["data"][cfg_key]
                        if cfg_key == pdef["api_key"]:
                            providers[pid]["api_key"] = value or ""
                        elif cfg_key == pdef["base_url"]:
                            providers[pid]["base_url"] = value or ""
                        elif cfg_key == pdef["model"]:
                            providers[pid]["model"] = value or ""
            except Exception:
                pass  # non-blocking — defaults will be used

        log.info(
            "provider_loaded",
            provider=pid,
            has_key=bool(providers[pid]["api_key"]),
            base_url=providers[pid]["base_url"] or "(default)",
            model=providers[pid]["model"] or "(default)",
        )

    # ── Validate provider configs ──
    validation_errors = _validate_provider_urls(providers)
    if validation_errors:
        log.warning(
            "provider_config_issues",
            errors=validation_errors,
            action="Agent may fail to connect to LLM. Check Settings > AI Providers.",
        )
        for err in validation_errors:
            log.warning("provider_config_error", detail=err)

    return providers


async def _load_config(client: httpx.AsyncClient) -> dict[str, Any]:
    """Load agent config from Config Service."""
    defaults = {
        "preferred_provider": "openai",
        "max_steps": 25,
    }

    try:
        for key in ("preferred_provider", "agent_max_steps"):
            resp = await client.get(f"{CONFIG_URL}/config/{key}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("data") and key in data["data"]:
                    config_key = key.replace("agent_", "")
                    if config_key == "max_steps":
                        defaults["max_steps"] = int(data["data"][key])
                    else:
                        defaults[config_key] = data["data"][key]
    except Exception as exc:
        log.warning("config_service_unreachable", error=str(exc))

    return defaults


# ── System Knowledge Loading ───────────────────────────────


async def _load_system_knowledge(memory: AgentMemory) -> int:
    """Load SYSTEM_KNOWLEDGE.md into vector memory at startup.

    Splits the markdown document by heading sections and stores each
    as a separate vector memory entry for semantic retrieval.
    Returns the number of chunks stored.
    """
    import re
    from pathlib import Path
    from src.memory.base import MemoryEntry

    knowledge_path = Path(__file__).parent / "SYSTEM_KNOWLEDGE.md"
    if not knowledge_path.exists():
        log.warning("system_knowledge_not_found", path=str(knowledge_path))
        return 0

    content = knowledge_path.read_text(encoding="utf-8")
    if not content.strip():
        return 0

    # Split by ## heading sections (skip title/intro)
    sections = re.split(r"\n(?=## )", content)

    chunk_count = 0
    for i, section in enumerate(sections):
        section = section.strip()
        if not section or len(section) < 20:
            continue

        # Extract heading for metadata
        heading_match = re.match(r"^## (.+)", section)
        heading = heading_match.group(1).strip() if heading_match else f"section_{i}"

        entry = MemoryEntry(
            content=section,
            metadata={
                "source": "system_knowledge",
                "type": "documentation",
                "heading": heading,
                "section_index": i,
            },
        )

        try:
            await memory.vector_store.store(entry)
            chunk_count += 1
        except Exception as exc:
            log.warning(
                "knowledge_chunk_store_failed",
                heading=heading,
                error=str(exc),
            )

    log.info(
        "system_knowledge_loaded",
        file=str(knowledge_path),
        chunks=chunk_count,
    )
    return chunk_count


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

    # Load provider configs (API keys, base URLs, models from Config Service)
    providers = await _load_providers(state.http_client)

    # Load general agent config (preferred_provider, max_steps)
    config = await _load_config(state.http_client)

    preferred = config.get("preferred_provider", "openai")

    # Init LLM client — fully provider-agnostic
    state.llm = AgentReasoningClient(
        providers=providers,
        preferred_provider=preferred if preferred else "openai",
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
    registry.register(DeduplicateFindingsSkill())
    state.registry = registry

    # Init Agent Registry for backend agent discovery
    state.agent_registry = AgentRegistry(http_client=state.http_client)

    # Register delegation skill
    registry.register(DelegateTaskSkill(state.agent_registry))

    # Start background discovery of backend agents
    state.agent_registry.start_background_refresh(interval=30)

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

    # Load system knowledge into vector memory
    knowledge_count = await _load_system_knowledge(state.agent.memory)

    # Count configured providers
    configured_providers = state.llm.configured_providers() if state.llm else []

    log.info(
        "agent_service_started",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        skills=registry.count,
        team_members=persona_count,
        preferred_provider=preferred,
        configured_providers=configured_providers,
        knowledge_chunks=knowledge_count,
    )

    yield

    # Shutdown
    log.info("agent_service_shutting_down")
    if state.http_client:
        await state.http_client.aclose()
    log.info("agent_service_stopped")


# ── Application ────────────────────────────────────────────

app = FastAPI(
    title="Antonio Agent Service",
    description="Antonio — AI Agent with ReAct loop, skills, and memory for smart contract auditing",
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


@app.get("/agent/provider-defaults")
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


@app.get("/agent/manifest")
async def agent_manifest() -> ApiResponse:
    """Publish Antonio manifest for discovery by backend agents."""
    if state is None or state.registry is None:
        raise _err("Service not initialized", 503)

    skills_info = []
    for skill in state.registry.list_skills():
        skills_info.append({
            "name": skill.name,
            "description": skill.description,
            "parameters": skill.parameters,
            "input_schema": {"type": "object", "properties": skill.parameters or {}},
            "output_schema": {"type": "object"},
        })

    active = state.agent.active_sessions if state.agent else 0

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


@app.get("/agent/registry")
async def agent_registry_status() -> ApiResponse:
    """List all discovered backend agents and their capabilities."""
    if state is None or state.agent_registry is None:
        raise _err("Agent registry not initialized", 503)

    agents = state.agent_registry.get_all_agents()
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


@app.post("/agent/chat")
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
    if state is None or state.agent is None:
        raise _err("Service not initialized", 503)

    log.info(
        "agent.chat_requested",
        message=body.message[:100],
        has_session=body.session_id is not None,
    )

    try:
        result: ChatResponse = await state.agent.chat(
            message=body.message,
            session_id=body.session_id,
        )
    except Exception as exc:
        err_msg = str(exc).strip() or type(exc).__name__
        log.exception("agent.chat_failed", error=err_msg)
        raise _err(
            f"Chat failed: {err_msg}. "
            "Check your AI provider configuration in Settings > AI Providers.",
            500,
        )

    return _ok(result.model_dump())


@app.get("/agent/chat/sessions")
async def list_chat_sessions() -> ApiResponse:
    """List all chat sessions with full message history.

    Returns all chat conversations that have been persisted
    to local storage (~/.sc_auditor/learning/chat_sessions.json).
    """
    if state is None or state.agent is None:
        raise _err("Service not initialized", 503)

    sessions = state.agent.list_chat_sessions()
    return _ok({
        "sessions": sessions,
        "total": len(sessions),
    })


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


# ── Circuit Breaker Endpoint ───────────────────────────────


@app.get("/circuit-breakers")
async def get_circuit_breakers() -> ApiResponse:
    """Get status of all circuit breakers."""
    return _ok(all_circuit_breakers())


@app.post("/circuit-breakers/reset")
async def reset_circuit_breakers() -> ApiResponse:
    """Reset all circuit breakers."""
    from src.utils.circuit_breaker import reset_all
    reset_all()
    return _ok({"message": "All circuit breakers reset"})


# ── Memory Stats Endpoint (T14) ────────────────────────────


@app.get("/memory/stats")
async def memory_stats() -> ApiResponse:
    """Get detailed memory store statistics."""
    if state is None or state.agent is None:
        raise _err("Service not initialized", 503)

    return _ok(state.agent.memory.get_all_stats())


# ── Knowledge Endpoint ─────────────────────────────────────


@app.get("/knowledge")
async def get_knowledge() -> ApiResponse:
    """Get system knowledge loaded from SYSTEM_KNOWLEDGE.md.

    Returns all knowledge chunks currently in vector memory
    that have metadata.source == 'system_knowledge'.
    """
    if state is None or state.agent is None:
        raise _err("Service not initialized", 503)

    try:
        entries = state.agent.memory.vector_store.get_all()
        knowledge_entries = [
            e.to_dict()
            for e in entries
            if e.metadata.get("source") == "system_knowledge"
        ]

        return _ok({
            "total_chunks": len(knowledge_entries),
            "chunks": sorted(knowledge_entries, key=lambda e: e.get("metadata", {}).get("section_index", 0)),
            "source": "SYSTEM_KNOWLEDGE.md",
            "note": "Antonio uses this knowledge in MODE 1 (direct answers) and for semantic search during audits.",
        })
    except Exception as exc:
        log.warning("knowledge_retrieval_failed", error=str(exc))
        return _ok({
            "total_chunks": 0,
            "chunks": [],
            "error": str(exc),
        })


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

    if input_data is None:
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


# ═══════════════════════════════════════════════════════════
# Antonio Gateway — Supreme Controller Endpoints
# All external requests route through Antonio for awareness,
# context, and audit trail. Orchestrator is backend-only.
# ═══════════════════════════════════════════════════════════


@app.post("/audit", status_code=201)
async def gateway_start_audit(body: dict[str, Any], request: Request) -> JSONResponse:
    """Start an audit — gatewayed through Antonio.
    
    Accepts the same payload as Orchestrator's /audit endpoint:
    { chain, address, program, priority, metadata }.
    
    Antonio logs the request, delegates to Orchestrator,
    and returns the result with an Antonio processing header.
    """
    chain = body.get("chain", "ethereum")
    address = body.get("address", "")
    program = body.get("program", "")
    priority = body.get("priority", 5)
    use_ai = body.get("use_ai", True)
    metadata = body.get("metadata", {})

    if not address.startswith("0x"):
        raise _err("Address must be 0x-prefixed")

    log.info(
        "antonio.gateway.audit_requested",
        chain=chain,
        address=address,
        program=program,
        priority=priority,
    )

    orchestrator_payload = {
        "chain": chain,
        "address": address,
        "program": program,
        "priority": priority,
        "use_ai": use_ai,
        "metadata": metadata,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/audit",
                json=orchestrator_payload,
            )
            resp.raise_for_status()
            result = resp.json()
    except httpx.RequestError as exc:
        log.error("antonio.gateway.orchestrator_unreachable", error=str(exc))
        raise _err(f"Orchestrator unreachable: {exc}", 502)
    except Exception as exc:
        log.error("antonio.gateway.audit_failed", error=str(exc))
        raise _err(f"Audit failed: {exc}", 500)

    # Add Antonio gateway mark
    if isinstance(result, dict) and "meta" in result:
        result["meta"]["gateway"] = "antonio"

    return JSONResponse(
        content=result,
        status_code=201,
        headers={"X-Antonio-Gateway": "true"},
    )


@app.post("/orchestrator/daemon/start")
async def gateway_daemon_start() -> JSONResponse:
    """Start the Orchestrator daemon via Antonio gateway."""
    log.info("antonio.gateway.daemon_start")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{ORCHESTRATOR_URL}/daemon/start")
            resp.raise_for_status()
            return JSONResponse(content=resp.json())
    except Exception as exc:
        raise _err(f"Daemon start failed: {exc}", 502)


@app.post("/orchestrator/daemon/stop")
async def gateway_daemon_stop() -> JSONResponse:
    """Stop the Orchestrator daemon via Antonio gateway."""
    log.info("antonio.gateway.daemon_stop")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{ORCHESTRATOR_URL}/daemon/stop")
            resp.raise_for_status()
            return JSONResponse(content=resp.json())
    except Exception as exc:
        raise _err(f"Daemon stop failed: {exc}", 502)


@app.get("/orchestrator/daemon/status")
async def gateway_daemon_status() -> JSONResponse:
    """Get Orchestrator daemon status via Antonio gateway."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{ORCHESTRATOR_URL}/daemon/status")
            resp.raise_for_status()
            return JSONResponse(content=resp.json())
    except Exception as exc:
        raise _err(f"Daemon status failed: {exc}", 502)


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
