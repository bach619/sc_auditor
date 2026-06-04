"""Vyper Scanner Manticore Service — Standalone Manticore symbolic execution.

Focused on HIGH/CRITICAL severity bug confirmation via:
  - Cross-contract reentrancy detection
  - Critical access control bypass
  - Flash loan + oracle manipulation
  - Integer overflow → fund loss
  - Arbitrary delegatecall injection

Uses Slither guidance to focus symbolic execution on high-value targets.

Port: 8018
"""

from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from shared.observability import setup_observability
from shared.agent_protocol.models import DelegationRequest, NegotiationRequest

from src.agent import ManticoreAgent
from src.guided_analyzer import GuidedAnalyzer
from src.resource_guard import ResourceBudget
from src.severity_scorer import SeverityScorer

# ── Constants ──────────────────────────────────────────────

SERVICE_NAME = "scanner-manticore"
SERVICE_VERSION = "0.1.0"
DATA_DIR = Path("/data/scanner-manticore")

# ── Pydantic Schemas ───────────────────────────────────────


class Meta(BaseModel):
    status: str = "ok"
    service: str = SERVICE_NAME
    version: str = SERVICE_VERSION
    timestamp: str = ""


class ApiResponse(BaseModel):
    meta: Meta = Field(default_factory=Meta)
    data: Any = None
    error: str | None = None


class AnalyzeRequest(BaseModel):
    sources: dict[str, str]
    contract_name: str | None = None
    functions: list[str] | None = None
    timeout: int = 300
    use_slither_guide: bool = True


class ConfirmRequest(BaseModel):
    sources: dict[str, str]
    finding: dict[str, Any]
    timeout: int = 120


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    manticore_available: bool
    uptime_seconds: float
    findings_count: int


# ── App State ──────────────────────────────────────────────


class AppState:
    def __init__(self) -> None:
        self.analyzer = GuidedAnalyzer(
            slither_url=os.environ.get(
                "SLITHER_URL", "http://04a-scanner-slither:8014"
            ),
            default_budget=ResourceBudget(
                max_duration_seconds=300,
                max_path_instructions=5000,
                max_states=10000,
            ),
        )
        self.agent = ManticoreAgent(analyzer=self.analyzer)
        self._start_time = time.monotonic()
        self._findings_count = 0

    @property
    def uptime(self) -> float:
        return time.monotonic() - self._start_time


def _ok(data: Any = None) -> ApiResponse:
    return ApiResponse(data=data)


def _error(msg: str, status: int = 400) -> ApiResponse:
    return ApiResponse(error=msg, meta=Meta(status="error"))


# ── Lifespan ───────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: create data dir on startup."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    from shared.storage import init_sqlite_store; init_sqlite_store("/data/scanner-manticore")
    yield


# ── FastAPI App ────────────────────────────────────────────

app = FastAPI(
    title="Vyper Scanner Manticore",
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

setup_observability(app, service_name=SERVICE_NAME)


# ── Helper ─────────────────────────────────────────────────


def _get_state(request: Request) -> AppState:
    if not hasattr(request.app.state, "vyper"):
        request.app.state.vyper = AppState()
    return request.app.state.vyper


# ═══════════════════════════════════════════════════════════
# REST Endpoints
# ═══════════════════════════════════════════════════════════


@app.get("/health")
async def health(request: Request) -> HealthResponse:
    """Health check endpoint."""
    state = _get_state(request)

    manticore_available = False
    try:
        import manticore  # noqa: F401
        manticore_available = True
    except ImportError:
        pass

    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        manticore_available=manticore_available,
        uptime_seconds=round(state.uptime, 2),
        findings_count=state._findings_count,
    )


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "description": (
            "Manticore symbolic execution — HIGH/CRITICAL bug confirmation. "
            "Endpoints: /analyze, /confirm, /health, /agent/manifest, "
            "/agent/delegate, /agent/negotiate"
        ),
    }


@app.post("/analyze", response_model=ApiResponse)
async def analyze_contract(request: Request, body: AnalyzeRequest) -> ApiResponse:
    """Run guided Manticore analysis on a contract.

    Input: source files keyed by path, optional contract name and functions.
    Output: HIGH/CRITICAL findings with symbolic proof paths.
    """
    state = _get_state(request)

    if not body.sources:
        return _error("At least one source file is required")

    start = time.monotonic()
    result = await state.analyzer.analyze(
        source_files=body.sources,
        contract_name=body.contract_name,
        functions_to_test=body.functions,
        timeout=body.timeout,
        use_slither_guide=body.use_slither_guide,
    )
    elapsed = time.monotonic() - start

    state._findings_count += len(result.get("findings", []))

    return _ok({
        "audit_id": result.get("audit_id"),
        "contract_name": result.get("contract_name"),
        "duration_seconds": result.get("duration_seconds", round(elapsed, 2)),
        "findings": result.get("findings", []),
        "summary": result.get("summary"),
        "resource_usage": result.get("resource_usage"),
        "slither_cross_reference": result.get("slither_cross_reference"),
    })


@app.post("/confirm", response_model=ApiResponse)
async def confirm_finding(request: Request, body: ConfirmRequest) -> ApiResponse:
    """Deep-confirm a specific finding with focused symbolic execution."""
    state = _get_state(request)

    if not body.sources:
        return _error("At least one source file is required")

    result = await state.analyzer.confirm_finding(
        source_files=body.sources,
        finding=body.finding,
        timeout=body.timeout,
    )

    if result.get("confirmed"):
        state._findings_count += 1

    return _ok(result)


@app.get("/findings/{audit_id}")
async def get_findings(request: Request, audit_id: str) -> ApiResponse:
    """Retrieve findings for a previous analysis (stub — future: persistent storage)."""
    return _ok({
        "audit_id": audit_id,
        "note": "Persistent storage not yet implemented. "
                "Findings are returned in /analyze response.",
    })


# ═══════════════════════════════════════════════════════════
# Agent Endpoints (Antonio integration)
# ═══════════════════════════════════════════════════════════


@app.get("/agent/manifest")
async def manticore_agent_manifest(request: Request) -> ApiResponse:
    state = _get_state(request)
    return _ok(state.agent.get_manifest())


@app.post("/agent/delegate")
async def manticore_agent_delegate(request: Request, body: dict) -> ApiResponse:
    state = _get_state(request)
    req = DelegationRequest(
        task_id=body.get("task_id", uuid.uuid4().hex[:12]),
        goal=body.get("goal", ""),
        capability=body.get("capability", ""),
        input_data=body.get("input_data", {}),
        constraints=body.get("constraints", {}),
        parent_session_id=body.get("parent_session_id", ""),
        priority=body.get("priority", "normal"),
    )
    response = await state.agent.handle_delegation(req)
    return _ok(response)


@app.post("/agent/negotiate")
async def manticore_agent_negotiate(request: Request, body: dict) -> ApiResponse:
    state = _get_state(request)
    req = NegotiationRequest(
        task_description=body.get("task_description", ""),
        required_capability=body.get("required_capability", ""),
        estimated_complexity=body.get("estimated_complexity", "medium"),
        budget_usd=body.get("budget_usd", 0.0),
        deadline_seconds=body.get("deadline_seconds", 0),
    )
    response = await state.agent.handle_negotiation(req)
    return _ok(response)


# ── Entry Point ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8018,
        log_level="info",
        reload=False,
    )
