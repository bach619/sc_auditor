"""Vyper Scanner Mythril Service — Isolated Mythril analysis microservice.

Mythril has irreconcilable dependency conflicts with web3 6.x (eth-hash clash).
This service runs in its own container with mythril-compatible deps.

Port: 8013
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from shared.observability import setup_observability
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.intelligence import (
    MythrilChainPredictor,
    MythrilClassifier,
    MythrilFixer,
    MythrilNLP,
    MythrilScorer,
    create_classifier,
    create_fixer,
    create_nlp,
    create_path_predictor,
    create_scorer,
)
from src.agent import MythrilAgent
from src.guided_analyzer import GuidedAnalyzer
from src.cross_reference import CrossReferenceEngine
from src.enhanced_nlp import EnhancedNLP
from src.enhanced_fixer import EnhancedFixer
from src.severity_scorer import SeverityScorer
from src.resource_guard import ResourceBudget, ResourceGuard
from shared.agent_protocol.models import (
    DelegationRequest,
    NegotiationRequest,
)

# ── Constants ──────────────────────────────────────────────

SERVICE_NAME = "scanner-mythril"
SERVICE_VERSION = "0.1.0"
DATA_DIR = Path("/data/scanner-mythril")

# ── Models ─────────────────────────────────────────────────


class Meta(BaseModel):
    service: str = SERVICE_NAME
    version: str = SERVICE_VERSION


class ApiResponse(BaseModel):
    ok: bool
    data: Any | None = None
    error: str | None = None
    meta: Meta = Field(default_factory=Meta)


class AnalyzerFinding(BaseModel):
    """A single finding returned by Mythril."""

    title: str
    description: str
    severity: str  # Low / Medium / High / Critical
    swc_id: str | None = None
    swc_title: str | None = None
    function: str | None = None
    address: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict, description="Enriched intelligence data")


class AnalyzeRequest(BaseModel):
    """Request to analyze Solidity source code."""

    sources: dict[str, str]  # {filename: source_code}
    compiler_version: str | None = None
    timeout: int = 120  # seconds


class AnalyzeResponse(BaseModel):
    """Result of a Mythril analysis run."""

    findings: list[AnalyzerFinding]
    tool: str = "mythril"
    tool_version: str | None = None
    errors: list[str] = []


class HealthInfo(BaseModel):
    service: str = SERVICE_NAME
    version: str = SERVICE_VERSION
    mythril_available: bool = False
    mythril_version: str | None = None


# ── Intelligence Schemas ────────────────────────────────────


class IntelClassifyRequest(BaseModel):
    findings: list[dict[str, Any]]


class IntelScoreRequest(BaseModel):
    findings: list[dict[str, Any]]


class IntelFixRequest(BaseModel):
    findings: list[dict[str, Any]]


class IntelPathRequest(BaseModel):
    findings: list[dict[str, Any]]


class IntelAskRequest(BaseModel):
    query: str
    findings: list[dict[str, Any]]


# ── Runner ─────────────────────────────────────────────────


def check_mythril() -> tuple[bool, str | None]:
    """Check if mythril CLI is available and return its version."""
    try:
        result = subprocess.run(
            ["myth", "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        version = result.stdout.strip() or result.stderr.strip()
        return True, version or "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, None


def run_mythril_analyze(
    sources: dict[str, str],
    compiler_version: str | None = None,
    timeout: int = 120,
) -> tuple[list[AnalyzerFinding], list[str]]:
    """Run ``mythril analyze`` on the given Solidity sources.

    Writes sources to a temp directory and runs mythril CLI.

    Returns:
        Tuple of (findings, errors).
    """
    findings: list[AnalyzerFinding] = []
    errors: list[str] = []

    with tempfile.TemporaryDirectory(prefix="mythril_") as tmpdir:
        # Write all sources
        for path, content in sources.items():
            filepath = Path(tmpdir) / path
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding="utf-8")

        # Find the main contract file
        main_file = None
        for path in sources:
            if path.endswith(".sol"):
                main_file = Path(tmpdir) / path
                break

        if not main_file:
            errors.append("No .sol file found in sources")
            return findings, errors

        # Build CLI args
        cmd = [
            "myth", "analyze",
            str(main_file),
            "--solc-json", str(Path(tmpdir) / "solc.json"),
            "--out", "json",
            "--max-depth", "32",
        ]

        # Add compiler version if provided
        if compiler_version:
            cmd.extend(["--solc-version", compiler_version])

        # Create minimal solc.json
        solc_config = {
            "language": "Solidity",
            "sources": {},
            "settings": {
                "optimizer": {"enabled": False},
                "outputSelection": {"*": {"*": ["abi", "evm.bytecode"]}},
            },
        }
        for path in sources:
            solc_config["sources"][path] = {"content": sources[path]}
        (Path(tmpdir) / "solc.json").write_text(
            json.dumps(solc_config), encoding="utf-8"
        )

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
            )

            stdout = result.stdout
            stderr = result.stderr

            # Mythril outputs JSON to stdout
            parsed = _parse_mythril_output(stdout)
            findings.extend(parsed)

            if stderr:
                errors.append(stderr[:2000])  # truncate

        except subprocess.TimeoutExpired:
            errors.append(f"Mythril analysis timed out after {timeout}s")
        except FileNotFoundError:
            errors.append("Myth CLI not found")
        except Exception as exc:
            errors.append(f"Mythril execution error: {str(exc)[:500]}")

    return findings, errors


def _parse_mythril_output(output: str) -> list[AnalyzerFinding]:
    """Parse Mythril JSON output into AnalyzerFinding list."""
    findings: list[AnalyzerFinding] = []

    # Mythril outputs JSON lines or JSON array
    lines = output.strip().splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Mythril can output different formats
        # Format 1: {"issues": [...]}
        # Format 2: direct issue objects
        issues = data if isinstance(data, list) else data.get("issues", [data])

        for issue in issues if isinstance(issues, list) else [issues]:
            if not isinstance(issue, dict):
                continue
            findings.append(
                AnalyzerFinding(
                    title=issue.get("title", issue.get("swc-title", "Unknown")),
                    description=issue.get("description", ""),
                    severity=issue.get("severity", "Medium"),
                    swc_id=issue.get("swc-id", issue.get("swcID")),
                    swc_title=issue.get(
                        "swc-title",
                        issue.get("swcTitle"),
                    ),
                    function=issue.get("function", issue.get("functionName")),
                    address=issue.get("address"),
                )
            )

    return findings


# ── App State ──────────────────────────────────────────────


class AppState:
    """Shared application state."""

    def __init__(self) -> None:
        self.mythril_available: bool = False
        self.mythril_version: str | None = None
        self._shutdown_requested: bool = False
        # Agent
        self.agent: MythrilAgent | None = None

        # Intelligence engine (existing)
        self.classifier: MythrilClassifier = create_classifier()
        self.scorer: MythrilScorer = create_scorer()
        self.fixer: MythrilFixer = create_fixer()
        self.chain_predictor: MythrilChainPredictor = create_path_predictor()
        self.nlp: MythrilNLP = create_nlp()

        # Enhanced modules
        self.guided_analyzer: GuidedAnalyzer = GuidedAnalyzer(
            slither_url=os.environ.get(
                "SLITHER_URL", "http://04a-scanner-slither:8014"
            ),
            ai_url=os.environ.get(
                "AI_URL", "http://06-ai:8004"
            ),
            manticore_url=os.environ.get(
                "MANTICORE_URL", "http://04e-scanner-manticore:8018"
            ),
        )
        self.cross_reference: CrossReferenceEngine = CrossReferenceEngine()
        self.enhanced_nlp: EnhancedNLP = EnhancedNLP(
            ai_url=os.environ.get("AI_URL", "http://06-ai:8004"),
        )
        self.enhanced_fixer: EnhancedFixer = EnhancedFixer()
        self.resource_guard: ResourceGuard = ResourceGuard()
        self._mythril_findings_count: int = 0

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def request_shutdown(self) -> None:
        self._shutdown_requested = True


# ── Lifespan ───────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: check mythril availability. Shutdown: clean exit."""
    state = AppState()
    app.state.vyper = state

    # Init Agent
    state.agent = MythrilAgent(guided_analyzer=state.guided_analyzer)
    log.info("mythril.agent_initialized", agent_role=state.agent.agent_role)

    available, version = check_mythril()
    state.mythril_available = available
    state.mythril_version = version

    log.info(
        "mythril_service.startup",
        mythril_available=available,
        mythril_version=version,
        swc_count=len(state.classifier.get_swc_registry()),
    )

    yield

    log.info("mythril_service.shutdown")


# ── App Factory ────────────────────────────────────────────

app = FastAPI(
    title="Vyper Scanner Mythril Service",
    description=(
        "Isolated Mythril analysis microservice. Runs mythril analyze "
        "on Solidity source code with its own compatible dependency tree."
    ),
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


log = setup_observability(app, "05-scanner-mythril", "0.1.0")

# ── Exception Handlers ─────────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_exception", error=str(exc), path=str(request.url))
    return JSONResponse(
        status_code=500,
        content=ApiResponse(ok=False, error=f"Internal server error: {str(exc)[:200]}").model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse(ok=False, error=exc.detail).model_dump(),
    )


# ── Helper ─────────────────────────────────────────────────


def ok(data: Any = None) -> ApiResponse:
    return ApiResponse(ok=True, data=data)


# ── Routes ─────────────────────────────────────────────────


@app.get("/health")
async def health(request: Request) -> ApiResponse:
    """Health check with mythril availability status."""
    state: AppState = request.app.state.vyper  # type: ignore[attr-defined]
    return ok(
        HealthInfo(
            mythril_available=state.mythril_available,
            mythril_version=state.mythril_version,
        )
    )


@app.post("/analyze")
async def analyze(body: AnalyzeRequest, request: Request) -> ApiResponse:
    """Run Mythril analysis on the provided Solidity sources.

    **Request body**::

        {
            "sources": {
                "Contract.sol": "// SPDX... pragma solidity ^0.8.0; ..."
            },
            "compiler_version": "0.8.20",
            "timeout": 120
        }

    Returns findings in Vyper standard format.
    """
    state: AppState = request.app.state.vyper  # type: ignore[attr-defined]

    if not state.mythril_available:
        return ApiResponse(ok=False, error="Mythril CLI is not available")

    findings, errors = await asyncio.to_thread(
        run_mythril_analyze,
        body.sources,
        body.compiler_version,
        body.timeout,
    )

    # ── Intelligence enrichment ────────────────────────────
    if findings:
        try:
            finding_dicts = [f.model_dump() for f in findings]
            enriched = state.classifier.classify_findings(finding_dicts)
            scores = state.scorer.score_findings(enriched)

            # Merge classification and scores back into findings
            for i, f in enumerate(findings):
                if i < len(enriched):
                    f.swc_id = enriched[i].get("swc_id", f.swc_id)
                if i < len(scores):
                    s = scores[i]
                    # We extend the model by adding attributes dynamically
                    f.metadata = {  # type: ignore[attr-defined]
                        "category": enriched[i].get("category", "unknown") if i < len(enriched) else "unknown",
                        "risk_score": s.get("adjusted_score", 0),
                        "risk_label": s.get("risk_label", "medium"),
                        "priority": s.get("priority", 3),
                    }
        except Exception as exc:
            log.warning("mythril.intel_enrichment_failed", error=str(exc))

    return ok(
        AnalyzeResponse(
            findings=findings,
            tool="mythril",
            tool_version=state.mythril_version,
            errors=errors,
        )
    )


@app.post("/analyze/raw")
async def analyze_raw(request: Request) -> JSONResponse:
    """Accept raw Solidity source files as multipart upload.

    Alternative to the JSON /analyze endpoint for direct file uploads.
    """
    # This is a placeholder — the JSON endpoint is the primary API
    return JSONResponse(
        content=ApiResponse(
            ok=False, error="Use POST /analyze with JSON body instead"
        ).model_dump(),
        status_code=400,
    )


# ── Helper ─────────────────────────────────────────────────


def _get_state(request: Request) -> AppState:
    return request.app.state.vyper  # type: ignore[attr-defined]


# ── Intelligence Endpoints ─────────────────────────────────


@app.post("/intel/classify")
async def intel_classify(body: IntelClassifyRequest, request: Request) -> ApiResponse:
    """Classify Mythril findings by SWC category."""
    state = _get_state(request)
    if not body.findings:
        return ApiResponse(ok=False, error="At least one finding is required")

    enriched = state.classifier.classify_findings(body.findings)
    categories: dict[str, int] = {}
    severities: dict[str, int] = {}
    for f in enriched:
        cat = f.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1
        sev = f.get("severity", "unknown")
        severities[sev] = severities.get(sev, 0) + 1

    return ok({
        "enriched_findings": enriched,
        "categories": categories,
        "severity_counts": severities,
        "total": len(enriched),
    })


@app.get("/intel/classify/swc")
async def intel_swc_registry(request: Request) -> ApiResponse:
    """List all known SWC IDs with categories."""
    state = _get_state(request)
    return ok(state.classifier.get_swc_registry())


@app.post("/intel/score")
async def intel_score(body: IntelScoreRequest, request: Request) -> ApiResponse:
    """Score Mythril findings."""
    state = _get_state(request)
    if not body.findings:
        return ApiResponse(ok=False, error="At least one finding is required")

    scores = state.scorer.score_findings(body.findings)
    aggregate = state.scorer.compute_aggregate(scores)
    return ok({"scores": scores, "aggregate": aggregate})


@app.post("/intel/fix")
async def intel_fix(body: IntelFixRequest, request: Request) -> ApiResponse:
    """Generate fix suggestions for Mythril findings."""
    state = _get_state(request)
    if not body.findings:
        return ApiResponse(ok=False, error="At least one finding is required")

    fixes = state.fixer.generate_fixes(body.findings)
    return ok({
        "fixes": fixes,
        "template_stats": state.fixer.get_stats(),
    })


@app.post("/intel/paths")
async def intel_paths(body: IntelPathRequest, request: Request) -> ApiResponse:
    """Predict exploit chains from findings."""
    state = _get_state(request)
    if not body.findings:
        return ApiResponse(ok=False, error="At least one finding is required")

    chains = state.chain_predictor.predict_chains(body.findings)
    summary = state.chain_predictor.summarize(chains)
    return ok({"chains": chains, "summary": summary})


@app.post("/intel/ask")
async def intel_ask(body: IntelAskRequest, request: Request) -> ApiResponse:
    """Ask questions about Mythril analysis results."""
    state = _get_state(request)

    # Optionally compute chains for context
    chains = state.chain_predictor.predict_chains(body.findings)

    result = state.nlp.ask(
        query=body.query,
        findings=body.findings,
        chain_results=chains,
    )
    return ok(result)


@app.get("/intel/stats")
async def intel_stats(request: Request) -> ApiResponse:
    """Get intelligence engine statistics."""
    state = _get_state(request)
    return ok({
        "classifier": {
            "swc_count": len(state.classifier.get_swc_registry()),
        },
        "scorer": {
            "factors": ["severity_base", "impact_boost", "fn_boost"],
        },
        "fixer": state.fixer.get_stats(),
        "chain_predictor": {
            "chains_defined": 5,
        },
    })


# ═══════════════════════════════════════════════════════════
# Enhanced Endpoints (Power Mode)
# ═══════════════════════════════════════════════════════════


class GuidedAnalyzeRequest(BaseModel):
    sources: dict[str, str]
    functions: list[str] | None = None
    timeout: int = 300
    depth: int = 42
    use_slither_guide: bool = True
    use_custom_plugins: bool = True


class DeepAnalyzeResponse(BaseModel):
    audit_id: str
    duration_seconds: float
    findings: list[dict[str, Any]]
    summary: dict[str, Any]
    cross_reference: dict[str, Any]
    resource_usage: dict[str, Any]
    errors: list[str]


class ExplainRequest(BaseModel):
    finding: dict[str, Any]


class POCRequest(BaseModel):
    finding: dict[str, Any]


class CrossRefRequest(BaseModel):
    mythril_findings: list[dict[str, Any]]
    slither_findings: list[dict[str, Any]] | None = None
    manticore_findings: list[dict[str, Any]] | None = None
    echidna_findings: list[dict[str, Any]] | None = None


@app.post("/analyze/deep", response_model=ApiResponse)
async def analyze_deep(body: GuidedAnalyzeRequest, request: Request) -> ApiResponse:
    """Deep guided analysis: Slither → Mythril → cross-reference → AI explanation.

    Pipeline:
      1. Optional: call Slither for function targeting
      2. Run Mythril with custom plugins and deeper analysis
      3. Cross-reference findings with other tools
      4. Score and filter HIGH/CRITICAL only
      5. Return enriched findings
    """
    state = _get_state(request)
    if not body.sources:
        return ApiResponse(ok=False, error="At least one source file is required")

    result = await state.guided_analyzer.analyze(
        source_files=body.sources,
        functions_to_test=body.functions,
        timeout=body.timeout,
        depth=body.depth,
        use_slither_guide=body.use_slither_guide,
        use_custom_plugins=body.use_custom_plugins,
    )
    state._mythril_findings_count += len(result.get("findings", []))
    return ok(result)


@app.post("/analyze/guided", response_model=ApiResponse)
async def analyze_guided(body: GuidedAnalyzeRequest, request: Request) -> ApiResponse:
    """Quick guided analysis — Slither → Mythril with auto settings."""
    state = _get_state(request)
    if not body.sources:
        return ApiResponse(ok=False, error="At least one source file is required")

    result = await state.guided_analyzer.analyze(
        source_files=body.sources,
        functions_to_test=body.functions,
        timeout=min(body.timeout, 180),  # Shorter timeout
        depth=32,  # Standard depth
        use_slither_guide=body.use_slither_guide,
        use_custom_plugins=True,
    )
    state._mythril_findings_count += len(result.get("findings", []))
    return ok(result)


@app.post("/intel/explain", response_model=ApiResponse)
async def intel_explain(body: ExplainRequest, request: Request) -> ApiResponse:
    """Get AI-powered or rule-based explanation for a finding."""
    state = _get_state(request)
    explanation = await state.enhanced_nlp.explain_finding(body.finding)
    return ok({"explanation": explanation})


@app.post("/intel/poc", response_model=ApiResponse)
async def intel_poc(body: POCRequest, request: Request) -> ApiResponse:
    """Generate PoC description for a finding."""
    state = _get_state(request)
    poc = await state.enhanced_nlp.generate_poc_description(body.finding)
    return ok({"poc": poc})


@app.post("/intel/summarize", response_model=ApiResponse)
async def intel_summarize(body: IntelScoreRequest, request: Request) -> ApiResponse:
    """Generate AI-powered summary of findings."""
    state = _get_state(request)
    summary = await state.enhanced_nlp.summarize_findings(body.findings)
    return ok({"summary": summary})


@app.post("/intel/fix/enhanced", response_model=ApiResponse)
async def intel_fix_enhanced(body: IntelFixRequest, request: Request) -> ApiResponse:
    """Get enhanced fix suggestions covering all 30 SWC entries."""
    state = _get_state(request)
    fixes = state.enhanced_fixer.get_fixes_batch(body.findings)
    return ok({
        "fixes": fixes,
        "total_swc_covered": 30,
    })


@app.post("/intel/crossref", response_model=ApiResponse)
async def intel_crossref(body: CrossrefRequest, request: Request) -> ApiResponse:
    """Cross-reference Mythril findings with Slither, Manticore, Echidna."""
    state = _get_state(request)
    result = state.cross_reference.cross_reference(
        mythril_findings=body.mythril_findings,
        slither_findings=body.slither_findings,
        manticore_findings=body.manticore_findings,
        echidna_findings=body.echidna_findings,
    )
    return ok(result)


@app.post("/intel/ask/enhanced", response_model=ApiResponse)
async def intel_ask_enhanced(body: IntelAskRequest, request: Request) -> ApiResponse:
    """Ask questions with AI-powered responses (falls back to rule-based)."""
    state = _get_state(request)
    context = {
        "findings": body.findings,
        "swc_registry": state.classifier.get_swc_registry(),
    }
    answer = await state.enhanced_nlp.ask_question(body.query, context)
    return ok({"answer": answer, "ai_used": state.enhanced_nlp._ai_url is not None})


@app.get("/analyze/stats")
async def analyze_stats(request: Request) -> ApiResponse:
    """Get Mythril analysis statistics."""
    state = _get_state(request)
    return ok({
        "total_findings_analyzed": state._mythril_findings_count,
        "mythril_available": state.mythril_available,
        "mythril_version": state.mythril_version,
        "enhanced_modules": {
            "guided_analyzer": True,
            "cross_reference": True,
            "enhanced_nlp": state.enhanced_nlp._ai_url is not None,
            "enhanced_fixer": True,
            "custom_plugins": True,
            "resource_guard": True,
        },
        "swc_coverage": len(state.classifier.get_swc_registry()),
    })


# ═══════════════════════════════════════════════════════════
# Agent Endpoints
# ═══════════════════════════════════════════════════════════


@app.get("/agent/manifest")
async def mythril_agent_manifest(request: Request) -> ApiResponse:
    """Publish agent manifest for Antonio discovery."""
    state = _get_state(request)
    if state.agent is None:
        return ApiResponse(ok=False, error="Agent not initialized")
    return ok(state.agent.get_manifest())


@app.post("/agent/delegate")
async def mythril_agent_delegate(body: dict, request: Request) -> ApiResponse:
    """Receive a delegation from Antonio."""
    state = _get_state(request)
    if state.agent is None:
        return ApiResponse(ok=False, error="Agent not initialized")

    delegation_req = DelegationRequest(
        task_id=body.get("task_id", ""),
        goal=body.get("goal", ""),
        capability=body.get("capability", ""),
        input_data=body.get("input_data", {}),
        constraints=body.get("constraints", {}),
        parent_session_id=body.get("parent_session_id", ""),
        priority=body.get("priority", "normal"),
    )
    response = await state.agent.handle_delegation(delegation_req)
    return ok(response)


@app.post("/agent/negotiate")
async def mythril_agent_negotiate(body: dict, request: Request) -> ApiResponse:
    """Handle a negotiation request from Antonio."""
    state = _get_state(request)
    if state.agent is None:
        return ApiResponse(ok=False, error="Agent not initialized")

    negotiation_req = NegotiationRequest(
        task_description=body.get("task_description", ""),
        required_capability=body.get("required_capability", ""),
        estimated_complexity=body.get("estimated_complexity", "medium"),
        budget_usd=body.get("budget_usd", 0.0),
        deadline_seconds=body.get("deadline_seconds", 0),
    )
    response = await state.agent.handle_negotiation(negotiation_req)
    return ok(response)
