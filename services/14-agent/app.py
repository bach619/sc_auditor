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
from shared.api_errors import register_error_handlers

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

    # ── Merge with PROVIDER_DEFAULTS for missing base_url / model ──
    from src.llm import PROVIDER_DEFAULTS  # noqa: PLC0415

    for pid, cfg in providers.items():
        defaults = PROVIDER_DEFAULTS.get(pid, {})
        if not cfg["base_url"] and defaults.get("base_url"):
            cfg["base_url"] = defaults["base_url"].rstrip("/")
            log.info(
                "provider_base_url_defaulting",
                provider=pid,
                base_url=cfg["base_url"],
            )
        if not cfg["model"] and defaults.get("model"):
            cfg["model"] = defaults["model"]
        cfg["api_type"] = defaults.get("api_type", "openai_compatible")

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

    # Auto-start the daemon for background skill execution
    if state.daemon and not state.daemon.is_running:
        try:
            state.daemon.start()
            log.info("daemon_auto_started")
        except Exception as exc:
            log.warning("daemon_auto_start_failed", error=str(exc))

    # Warmup: execute a lightweight skill to populate initial metrics
    try:
        result = await state.registry.execute("deduplicate_findings", findings=[])
        log.info("skill_warmup_complete", skill="deduplicate_findings", success=result.success)
    except Exception as exc:
        log.warning("skill_warmup_failed", error=str(exc))

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
register_error_handlers(app)

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


def _truncate(value: Any, max_len: int = 200) -> Any:
    """Truncate long string values for display."""
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + "..."
    if isinstance(value, dict):
        return {k: _truncate(v, max_len) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate(v, max_len) for v in value[:5]]
    return value


# ── Route Modules ──────────────────────────────────────────

from src.routes.routes_core import router as core_router
from src.routes.routes_sessions import router as sessions_router
from src.routes.routes_skills import router as skills_router
from src.routes.routes_memory import router as memory_router
from src.routes.routes_learning import router as learning_router
from src.routes.routes_daemon import router as daemon_router
from src.routes.routes_circuit import router as circuit_router
from src.routes.routes_team import router as team_router
from src.routes.routes_gateway import router as gateway_router

app.include_router(core_router)
app.include_router(sessions_router)
app.include_router(skills_router)
app.include_router(memory_router)
app.include_router(learning_router)
app.include_router(daemon_router)
app.include_router(circuit_router)
app.include_router(team_router)
app.include_router(gateway_router)


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
