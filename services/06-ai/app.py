"""Vyper AI Service — FastAPI microservice for LLM-powered vulnerability analysis.

Receives scanner findings + source code, sends to OpenAI/Anthropic LLM for
analysis, and returns enriched findings with TP/FP classification, severity
assessment, and fix recommendations.

Port: 8004

Endpoints:
  - GET  /health            → Health check
  - POST /analyze           → Analyze scanner findings
  - POST /fix-suggestion    → Get fix suggestion for a finding
  - GET  /cache/{hash}      → Get cached AI analysis
  - DELETE /cache/{hash}    → Clear cache entry
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import httpx
from shared.observability import setup_observability
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.analyzer import Analyzer, count_cache_entries
from src.fixer import FixSuggester
from src.llm import LLMClient
from src.models import (
    AnalyzeRequest,
    AnalyzedFinding,
    ApiResponse,
    ErrorResponse,
    FixSuggestion,
    FixSuggestionRequest,
    HealthData,
    Meta,
)






# ── Constants ──────────────────────────────────────────────

SERVICE_NAME = "ai"
SERVICE_VERSION = "0.1.0"
# Config service URL for loading runtime config
CONFIG_URL = "http://01-config:8000"


# ── Application State ──────────────────────────────────────


class AppState:
    """Shared application state injected via request.app.state.

    Attributes:
        llm: The LLM client instance.
        analyzer: The Analyzer orchestrator instance.
        fixer: The FixSuggester instance.
        http_client: Shared HTTP client for Config Service queries.
    """

    def __init__(self) -> None:
        self.llm: LLMClient | None = None
        self.analyzer: Analyzer | None = None
        self.fixer: FixSuggester | None = None
        self.http_client: httpx.AsyncClient | None = None
        self._shutdown_requested: bool = False

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def request_shutdown(self) -> None:
        self._shutdown_requested = True


# ── Config Loader ──────────────────────────────────────────


async def _load_ai_config(client: httpx.AsyncClient) -> dict[str, Any]:
    """Load AI-specific configuration from the Config Service.

    Falls back to default values if the Config Service is unavailable.

    Args:
        client: HTTP client for Config Service requests.

    Returns:
        Dictionary with keys: openai_model, anthropic_model, max_concurrent_ai,
        openai_api_key, anthropic_api_key.
    """
    defaults = {
        "openai_model": "gpt-4o",
        "anthropic_model": "claude-3-5-sonnet-20241022",
        "max_concurrent_ai": 3,
        "preferred_provider": "openai",
        "openai_api_key": "",
        "anthropic_api_key": "",
    }

    try:
        resp = await client.get(f"{CONFIG_URL}/config/openai_model")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data") and "openai_model" in data["data"]:
                defaults["openai_model"] = data["data"]["openai_model"]

        resp = await client.get(f"{CONFIG_URL}/config/anthropic_model")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data") and "anthropic_model" in data["data"]:
                defaults["anthropic_model"] = data["data"]["anthropic_model"]

        resp = await client.get(f"{CONFIG_URL}/config/max_concurrent_ai")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data") and "max_concurrent_ai" in data["data"]:
                defaults["max_concurrent_ai"] = int(data["data"]["max_concurrent_ai"])

        resp = await client.get(f"{CONFIG_URL}/config/preferred_provider")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data") and "preferred_provider" in data["data"]:
                defaults["preferred_provider"] = data["data"]["preferred_provider"]

        # API keys — diset via frontend Settings, disimpan di Config Service
        resp = await client.get(f"{CONFIG_URL}/config/provider_openai_api_key")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data") and "provider_openai_api_key" in data["data"]:
                defaults["openai_api_key"] = data["data"]["provider_openai_api_key"]

        resp = await client.get(f"{CONFIG_URL}/config/provider_anthropic_api_key")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data") and "provider_anthropic_api_key" in data["data"]:
                defaults["anthropic_api_key"] = data["data"]["provider_anthropic_api_key"]

        log.info("config_loaded_from_service", config={
            k: v for k, v in defaults.items()
            if k not in ("openai_api_key", "anthropic_api_key")
        })
    except Exception as exc:
        log.warning("config_service_unreachable_using_defaults", error=str(exc))

    return defaults


# ── Lifespan ───────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: initialize LLM client, load config. Shutdown: clean up clients."""
    global state
    state = AppState()

    # Create shared HTTP client
    state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
    )

    # Load AI config from Config Service
    config = await _load_ai_config(state.http_client)

    # Create the LLM client with keys from Config Service (diset via frontend)
    llm = LLMClient(
        openai_key=config["openai_api_key"],
        anthropic_key=config["anthropic_api_key"],
        openai_model=config["openai_model"],
        anthropic_model=config["anthropic_model"],
        preferred_provider=config["preferred_provider"],
    )
    state.llm = llm

    # Create the Analyzer
    state.analyzer = Analyzer(
        llm=llm,
        max_concurrent=config["max_concurrent_ai"],
    )

    # Create the FixSuggester
    state.fixer = FixSuggester(llm=llm)

    log.info(
        "ai_service_started",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        provider=config["preferred_provider"],
        model_openai=config["openai_model"],
        model_anthropic=config["anthropic_model"],
        max_concurrent=config["max_concurrent_ai"],
        openai_configured=bool(config["openai_api_key"]),
        anthropic_configured=bool(config["anthropic_api_key"]),
    )

    yield  # ── Application runs here ──

    # Shutdown
    log.info("ai_service_shutting_down")
    if state.http_client:
        await state.http_client.aclose()
    log.info("ai_service_stopped")


# ── Application ────────────────────────────────────────────

app = FastAPI(
    title="Vyper AI Service",
    description=(
        "LLM-powered vulnerability analysis for smart contract audits. "
        "Uses OpenAI GPT-4o or Anthropic Claude to classify scanner findings "
        "as True/False Positives, assess severity, and suggest code fixes."
    ),
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

# CORS — permissive for local development / Docker compose
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


log = setup_observability(app, "06-ai", "0.1.0")

# ── Global state (for access in routes) ────────────────────

state: AppState | None = None


# ── Helper ─────────────────────────────────────────────────


def ok(data: object = None) -> ApiResponse:
    """Build a standard Vyper success response."""
    return ApiResponse(data=data, meta=Meta(status="ok"))


def err(detail: str, status_code: int = 400) -> HTTPException:
    """Build a standard Vyper error response."""
    return HTTPException(
        status_code=status_code,
        detail=detail,
    )


# ── Exception Handlers ─────────────────────────────────────


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Catch-all for unhandled exceptions — return a Vyper error envelope."""
    log.exception("unhandled_exception", path=str(request.url))
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            meta=Meta(status="error", error=str(exc))
        ).model_dump(),
    )


# ── Middleware: request logging ────────────────────────────


@app.middleware("http")
async def log_requests(request: Request, call_next: Any) -> Any:
    """Log incoming requests and their duration."""
    import time

    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000

    log.info(
        "request",
        method=request.method,
        path=str(request.url.path),
        status=response.status_code,
        duration_ms=f"{duration_ms:.1f}",
    )
    return response


# ── Endpoints ──────────────────────────────────────────────


@app.get("/health")
async def health() -> ApiResponse:
    """Health check endpoint.

    Returns service status, version, active provider/model,
    and cache statistics.
    """
    if state is None or state.llm is None:
        raise err("Service not fully initialized", status_code=503)

    provider, model = state.llm._select_provider()
    cache_count = count_cache_entries()

    return ok(
        HealthData(
            status="ok",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
            provider=provider,
            model=model,
            cache_entries=cache_count,
        )
    )


@app.post("/analyze")
async def analyze_findings(body: AnalyzeRequest) -> ApiResponse:
    """Analyze scanner findings using the LLM.

    Accepts an audit ID, source code, and list of scanner findings.
    Each finding is sent to the LLM for TP/FP classification, severity
    assessment, and fix suggestion. Results are cached on disk.

    **Request body**::

        {
            "audit_id": "audit-001",
            "source": {"Contract.sol": "// SPDX-License-Identifier: MIT\\n..."},
            "findings": [
                {
                    "id": "REENT-001",
                    "tool": "slither",
                    "title": "Reentrancy in withdraw()",
                    "description": "...",
                    "severity": "high",
                    "location": {"file": "Contract.sol", "line": 42, "snippet": "..."}
                }
            ],
            "compiler": "0.8.20",
            "contract_name": "MyContract"
        }

    Returns:
        A list of enriched findings with AI verdicts.
    """
    if state is None or state.analyzer is None:
        raise err("Service not fully initialized", status_code=503)

    if not body.source:
        raise err("source is required and must not be empty")
    if not body.findings:
        raise err("findings list must not be empty")

    log.info(
        "analyze.requested",
        audit_id=body.audit_id,
        finding_count=len(body.findings),
        contract=body.contract_name,
        files=len(body.source),
    )

    try:
        results: list[AnalyzedFinding] = await state.analyzer.analyze_all(
            source=body.source,
            findings=body.findings,
            compiler=body.compiler,
            contract_name=body.contract_name,
        )
    except Exception as exc:
        log.exception("analyze.failed", audit_id=body.audit_id)
        raise err(f"Analysis failed: {exc}", status_code=500)

    # Count TP vs FP
    tp_count = sum(1 for r in results if r.ai_verdict == "true_positive")
    fp_count = len(results) - tp_count

    log.info(
        "analyze.completed",
        audit_id=body.audit_id,
        total=len(results),
        true_positives=tp_count,
        false_positives=fp_count,
    )

    return ok(
        {
            "audit_id": body.audit_id,
            "findings": [r.model_dump() for r in results],
            "summary": {
                "total": len(results),
                "true_positives": tp_count,
                "false_positives": fp_count,
            },
        }
    )


@app.post("/fix-suggestion")
async def fix_suggestion(body: FixSuggestionRequest) -> ApiResponse:
    """Get a fix suggestion for a single scanner finding.

    Sends the finding and source code to the LLM with a fix-focused
    prompt and returns a structured fix recommendation.

    **Request body**::

        {
            "source": {"Contract.sol": "..."},
            "finding": {
                "id": "REENT-001",
                "tool": "slither",
                "title": "Reentrancy in withdraw()",
                "description": "...",
                "severity": "high",
                "location": {"file": "Contract.sol", "line": 42}
            },
            "compiler": "0.8.20"
        }

    Returns:
        A FixSuggestion with fix code, explanation, gas impact, and
        breaking change assessment.
    """
    if state is None or state.fixer is None:
        raise err("Service not fully initialized", status_code=503)

    if not body.source:
        raise err("source is required and must not be empty")

    # Combine source files
    if len(body.source) == 1:
        full_source = next(iter(body.source.values()))
    else:
        full_source = "\n\n".join(
            f"// File: {name}\n{content}"
            for name, content in body.source.items()
        )

    log.info(
        "fix_suggestion.requested",
        finding_id=body.finding.id,
        tool=body.finding.tool,
    )

    try:
        suggestion: FixSuggestion = await state.fixer.suggest_fix(
            source_code=full_source,
            finding=body.finding,
            compiler=body.compiler,
        )
    except Exception as exc:
        log.exception("fix_suggestion.failed", finding_id=body.finding.id)
        raise err(f"Fix suggestion failed: {exc}", status_code=500)

    return ok(suggestion.model_dump())


@app.get("/cache/{finding_hash:path}")
async def get_cached_analysis(finding_hash: str) -> ApiResponse:
    """Get a cached AI analysis result by hash.

    The hash is a SHA-256 hex string generated from the tool + source
    code + finding title + description. Returns the cached analysis
    or 404 if not found.

    Args:
        finding_hash: SHA-256 hex string cache key.

    Returns:
        The cached LlmAnalysis data.
    """
    if state is None or state.analyzer is None:
        raise err("Service not fully initialized", status_code=503)

    cached = state.analyzer.get_cached(finding_hash)
    if cached is None:
        raise err(f"No cached analysis found for hash: {finding_hash[:16]}...", status_code=404)

    log.info("cache.hit", hash_prefix=finding_hash[:16])
    return ok(cached.model_dump())


@app.delete("/cache/{finding_hash:path}")
async def clear_cached_analysis(finding_hash: str) -> ApiResponse:
    """Remove a cached AI analysis result.

    Args:
        finding_hash: SHA-256 hex string cache key.

    Returns:
        Confirmation of deletion, or 404 if the cache entry did not exist.
    """
    if state is None or state.analyzer is None:
        raise err("Service not fully initialized", status_code=503)

    removed = await state.analyzer.clear_cache(finding_hash)
    if not removed:
        raise err(f"No cached analysis found for hash: {finding_hash[:16]}...", status_code=404)

    log.info("cache.deleted", hash_prefix=finding_hash[:16])
    return ok({"deleted": True, "hash": finding_hash})


# ── Entry Point ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8004,
        log_level="info",
        reload=False,
    )
