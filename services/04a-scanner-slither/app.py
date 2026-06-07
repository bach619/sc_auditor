"""Vyper Scanner Slither Service — Standalone Slither static analysis microservice.

Runs Slither static analysis on Solidity source code, augmented with
full intelligence stack:

  L2 — Contract Classifier + Smart Detector Selection
  L3 — FP/TP Database (self-learning from feedback)
  L4 — Composite Risk Scoring, Exploit Path Prediction, Auto-Fix, NLP
  L5 — AI Verification (06-AI integration for TP/FP classification)
  L6 — FP Pattern Matching (known false-positive signatures)
  L7 — Quality Pipeline (end-to-end post-processing)

Port: 8014

Quality Pipeline Endpoints:
  POST /pipeline/run          → Full quality pipeline execution
  POST /pipeline/ai-verify    → AI verification via 06-AI
  POST /pipeline/fp-patterns  → FP pattern matching
  GET  /pipeline/stats        → Pipeline statistics
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.intelligence import (
    AIVerifier,
    CompositeScorer,
    ContractClassifier,
    ContractType,
    ExploitPathPredictor,
    FalsePositiveDB,
    FpPatternMatcher,
    FixGenerator,
    NaturalLanguageQuery,
    ProcessedFinding,
    QualityPipeline,
    QualityReport,
    RiskScore,
    create_ai_verifier,
    create_classifier,
    create_fixer,
    create_fp_db,
    create_fp_pattern_matcher,
    create_nlp,
    create_path_predictor,
    create_pipeline,
    create_scorer,
)
from src.slither import SlitherRunner, create_slither_runner
from vyper_lib.models import (
    ApiResponse,
    Finding,
    HealthData,
    InstallResult,
    Meta,
    ScanRequest,
    ScanResponse,
    ToolInfo,
    ToolResult,
)
from shared.api_errors import register_error_handlers
from shared.observability import setup_observability
from vyper_lib.solc_manager import SolcManager, create_solc_manager
from vyper_lib.deps import DependencyResolver, create_dependency_resolver
from vyper_lib.slither_config import SlitherConfigBuilder, create_slither_config
from src.detector_loader import (
    CustomDetectorRegistry,
    CustomDetectorRunner,
    DetectorLoadError,
    DetectorSandbox,
)
from src.agent import SlitherAgent
from shared.agent_protocol.models import (
    DelegationRequest,
    NegotiationRequest,
)

# ── Constants ──────────────────────────────────────────────

SERVICE_NAME = "scanner-slither"
SERVICE_VERSION = "0.3.0"  # bumped for quality pipeline + AI verification + FP patterns
DATA_DIR = Path("/data/scanner-slither")
RESULTS_DIR = DATA_DIR / "results"
SOURCES_DIR = DATA_DIR / "sources"
FP_DB_PATH = DATA_DIR / "fp_db.json"

# ── Pydantic Schemas (intelligence endpoints) ──────────────


class ClassifyRequest(BaseModel):
    sources: dict[str, str]
    contract_address: str = ""


class ClassifyResponse(BaseModel):
    contract_type: str
    contract_type_label: str
    confidence: float
    matched_patterns: list[str]
    top_detectors: list[str]
    analysis_strategy: str


class ScoreRequest(BaseModel):
    findings: list[dict[str, Any]]
    contract_type: str = "unknown"
    contract_address: str = ""


class ScoreResponse(BaseModel):
    scores: list[dict[str, Any]]
    aggregate: dict[str, Any]


class FixRequest(BaseModel):
    findings: list[dict[str, Any]]
    contract_name: str = ""


class FixResponse(BaseModel):
    fixes: dict[str, list[dict[str, Any]]]
    detector_count: int
    template_coverage: dict[str, Any]


class ExploitPathRequest(BaseModel):
    findings: list[dict[str, Any]]
    contract_type: str = "unknown"


class ExploitPathResponse(BaseModel):
    paths: list[dict[str, Any]]
    total: int
    critical_count: int
    high_count: int
    summary: dict[str, Any]


class AskRequest(BaseModel):
    query: str
    findings: list[dict[str, Any]]
    contract_type: str = "unknown"
    aggregate_risk: dict[str, Any] | None = None


class AskResponse(BaseModel):
    answer: str
    intent: str
    context: dict[str, Any]
    findings: list[dict[str, Any]]
    follow_up_questions: list[str]


class FeedbackRequest(BaseModel):
    detector: str
    contract_address: str
    chain: str = ""
    is_tp: bool = True
    severity: str = "medium"
    source: str = "user"


class FeedbackResponse(BaseModel):
    recorded: bool
    detector: str
    contract: str
    stats: dict[str, Any]


class IntelStatsResponse(BaseModel):
    classifier: dict[str, Any]
    scorer: dict[str, Any]
    fp_db: dict[str, Any]
    fixer: dict[str, Any]
    path_predictor: dict[str, Any]
    nlp: dict[str, Any]


class CustomScanRequest(BaseModel):
    """Request body for POST /scan/custom."""
    chain: str = "ethereum"
    address: str = ""
    sources: dict[str, str]
    compiler: str = "0.8.20"
    config_tier: str = "default"
    timeout: int = 600
    custom_detectors: list[str] = []
    include_built_in: bool = True


# ── App State ──────────────────────────────────────────────


class AppState:
    """Shared application state."""

    def __init__(self) -> None:
        # Core
        self.solc_mgr: SolcManager = create_solc_manager()
        self.slither_runner: SlitherRunner = create_slither_runner()
        self.dep_resolver: DependencyResolver = create_dependency_resolver()
        # Agent
        self.agent: SlitherAgent | None = None

        # Intelligence engine
        self.classifier: ContractClassifier = create_classifier()
        self.fp_db: FalsePositiveDB = create_fp_db(db_path=FP_DB_PATH)
        self.scorer: CompositeScorer = create_scorer(fp_db=self.fp_db)
        self.fixer: FixGenerator = create_fixer()
        self.path_predictor: ExploitPathPredictor = create_path_predictor()
        self.nlp: NaturalLanguageQuery = create_nlp(
            classifier=self.classifier,
            scorer=self.scorer,
            fixer=self.fixer,
        )

        # Custom detectors
        self.detector_registry = CustomDetectorRegistry(
            detectors_dir=str(DATA_DIR / "detectors")
        )
        self.detector_runner = CustomDetectorRunner(self.detector_registry)

        # Quality pipeline (L5-L7)
        self.fp_pattern_matcher: FpPatternMatcher = create_fp_pattern_matcher()
        self.ai_verifier: AIVerifier = create_ai_verifier()
        self.pipeline: QualityPipeline = create_pipeline(
            fp_matcher=self.fp_pattern_matcher,
            ai_verifier=self.ai_verifier,
            scorer=self.scorer,
            fixer=self.fixer,
            path_predictor=self.path_predictor,
            fp_db=self.fp_db,
            classifier=self.classifier,
        )


def _get_state(request: Request) -> AppState:
    return request.app.state.vyper


# ── Lifespan ───────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    state = AppState()
    app.state.vyper = state

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    FP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    from shared.storage import init_sqlite_store; init_sqlite_store("/data/scanner-slither")

    # Load custom detectors on startup
    DETECTORS_DIR = DATA_DIR / "detectors"
    DETECTORS_DIR.mkdir(parents=True, exist_ok=True)
    detector_count = state.detector_registry.load_all()
    if detector_count:
        log.info("custom_detectors.loaded", count=detector_count)

    # Init Agent with pipeline
    state.agent = SlitherAgent(
        runner=state.slither_runner,
        pipeline=state.pipeline,
        classifier=state.classifier,
    )
    log.info("slither.agent_initialized",
        agent_role=state.agent.agent_role,
        pipeline_ready=True,
        fp_patterns=len(state.fp_pattern_matcher._patterns),
    )

    solc_versions = state.solc_mgr.list_versions()
    log.info(
        "slither.startup",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        solc_versions=len(solc_versions),
        classifier_noise_types=len(state.classifier.TYPE_NOISE_DETECTORS),
        fix_templates=len(state.fixer.get_available_detectors()),
    )
    yield
    log.info("slither.shutdown", service=SERVICE_NAME)


# ── App Factory ────────────────────────────────────────────

app = FastAPI(
    title="Vyper Scanner Slither Service",
    description="Runs Slither static analysis on Solidity source code.",
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

log = setup_observability(app, "04a-scanner-slither", "0.1.0")

# ── Helper ─────────────────────────────────────────────────


def ok(data: object = None) -> ApiResponse:
    return ApiResponse(data=data, meta=Meta(status="ok"))


def err(detail: str, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


def _findings_to_dicts(findings: list[Finding]) -> list[dict[str, Any]]:
    """Convert Finding objects to plain dicts for intelligence engines."""
    return [
        {
            "title": f.title,
            "severity": f.severity,
            "description": f.description or "",
            "contract": f.contract or "",
            "line": f.line,
            "recommendation": f.recommendation or "",
        }
        for f in findings
    ]


# ── Core Endpoints ─────────────────────────────────────────


@app.get("/health")
async def health(request: Request) -> ApiResponse:
    state = _get_state(request)
    solc_versions = await asyncio.to_thread(state.solc_mgr.list_versions)

    slither_available = False
    slither_version = None
    try:
        result = await asyncio.to_thread(
            subprocess.run, ["slither", "--version"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            slither_available = True
            slither_version = (result.stdout.strip() or result.stderr.strip())[:100]
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    return ok(HealthData(
        status="ok",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        tools_available=1 if slither_available else 0,
        tools_installed=["slither"] if slither_available else [],
        solc_versions=solc_versions,
    ))


@app.post("/scan")
async def run_scan(body: ScanRequest, request: Request) -> ApiResponse:
    """Run Slither static analysis on Solidity source code.

    Accepts source files, resolves compiler version, optionally installs
    dependencies, then runs Slither analysis. Automatically enriches
    findings with intelligence (classification + scoring) when possible.
    """
    start = time.monotonic()
    state = _get_state(request)

    if not body.sources:
        raise err("At least one source file is required")

    audit_id = str(uuid.uuid4())
    audit_dir = SOURCES_DIR / audit_id
    audit_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Write source files to disk
        for file_path, source_code in body.sources.items():
            target = audit_dir / file_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source_code, encoding="utf-8")

        log.info(
            "slither.scan.start",
            audit_id=audit_id, contract=body.address,
            chain=body.chain, files=len(body.sources),
        )

        # Ensure solc version
        try:
            await asyncio.to_thread(state.solc_mgr.ensure_version, body.compiler)
        except RuntimeError as exc:
            log.warning("slither.solc_unavailable", error=str(exc))

        # Resolve dependencies
        try:
            deps = await asyncio.to_thread(state.dep_resolver.resolve, audit_dir)
            if deps:
                log.info("slither.deps_resolved", count=len(deps))
        except Exception as exc:
            log.warning("slither.deps_failed", error=str(exc))

        # Build config from tier
        config = SlitherConfigBuilder().with_tier(body.config_tier).build()

        # Run Slither
        result = await asyncio.to_thread(
            state.slither_runner.run,
            audit_dir, config=config, timeout=body.timeout,
        )

        elapsed = time.monotonic() - start

        # ── Intelligence enrichment ────────────────────────
        contract_type = ContractType.UNKNOWN
        contract_type_label = "Unknown"

        if body.sources and result.success:
            # Classify contract
            try:
                classification = await state.classifier.classify(body.sources)
                contract_type = classification.contract_type
                contract_type_label = contract_type.value
            except Exception as exc:
                log.warning("intel.classify_failed", error=str(exc))

            # Score findings
            try:
                finding_dicts = _findings_to_dicts(result.findings)
                scores = state.scorer.score_findings(
                    finding_dicts,
                    contract_type=contract_type,
                    contract_address=body.address or None,
                )
                # Attach risk scores to findings
                score_map = {s.finding_title: s for s in scores}
                for f in result.findings:
                    if f.title in score_map:
                        s = score_map[f.title]
                        f.metadata["risk_score"] = s.normalized_score
                        f.metadata["risk_label"] = s.risk_label
                        f.metadata["priority"] = s.priority
            except Exception as exc:
                log.warning("intel.scoring_failed", error=str(exc))

        critical = sum(1 for f in result.findings if f.severity == "critical")
        high = sum(1 for f in result.findings if f.severity == "high")

        scan_response = ScanResponse(
            audit_id=audit_id,
            contract_address=body.address,
            chain=body.chain,
            compiler=body.compiler,
            tools=[result],
            all_findings=result.findings,
            total_findings=len(result.findings),
            critical_count=critical,
            high_count=high,
            duration_seconds=round(elapsed, 2),
            contract_type=contract_type_label,
        )

        log.info(
            "slither.scan.complete",
            audit_id=audit_id,
            findings=len(result.findings),
            critical=critical,
            high=high,
            contract_type=contract_type_label,
            duration=round(elapsed, 2),
        )

        return ok(scan_response)

    except Exception as exc:
        log.exception("slither.scan.failed", audit_id=audit_id, error=str(exc))
        raise err(f"Scan failed: {exc}", status_code=500)

    finally:
        try:
            shutil.rmtree(audit_dir, ignore_errors=True)
        except OSError:
            pass


@app.post("/install")
async def install_slither() -> ApiResponse:
    """Install or update Slither via pip."""
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "pip", "install", "--upgrade", "slither-analyzer", "setuptools"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            return ok(InstallResult(tool="slither", success=True, version="latest"))
        return ok(InstallResult(
            tool="slither", success=False,
            error=result.stderr.strip()[:500],
        ))
    except subprocess.TimeoutExpired:
        return ok(InstallResult(
            tool="slither", success=False,
            error="Installation timed out",
        ))


# ── Intelligence Endpoints ─────────────────────────────────


@app.post("/classify")
async def classify_contract(body: ClassifyRequest, request: Request) -> ApiResponse:
    """Classify a Solidity contract by analyzing its source code.

    Returns the contract type, confidence, matched patterns, and
    recommended detector priority list.
    """
    state = _get_state(request)

    if not body.sources:
        raise err("At least one source file is required")

    try:
        classification = await state.classifier.classify(
            source_code=body.sources,
            contract_address=body.contract_address or None,
        )

        return ok(ClassifyResponse(
            contract_type=classification.contract_type.value,
            contract_type_label=classification.contract_type.value,
            confidence=classification.confidence,
            matched_patterns=list(classification.matched_patterns),
            top_detectors=classification.priority_detectors,
            analysis_strategy=classification.analysis_strategy,
        ))
    except Exception as exc:
        log.exception("classify.failed", error=str(exc))
        raise err(f"Classification failed: {exc}", status_code=500)


@app.post("/classify/detectors")
async def list_detectors(request: Request) -> ApiResponse:
    """List all detector types and their priority per contract type."""
    state = _get_state(request)
    return ok({
        "available_detectors": state.classifier.get_available_detectors(),
        "contract_types": [ct.value for ct in ContractType],
    })


@app.post("/score")
async def score_findings(body: ScoreRequest, request: Request) -> ApiResponse:
    """Score findings with composite multi-dimensional risk scoring.

    Returns normalized risk scores (0-100), risk labels, priorities,
    and aggregate contract risk.
    """
    state = _get_state(request)

    if not body.findings:
        raise err("At least one finding is required")

    try:
        contract_type = ContractType(body.contract_type) if body.contract_type else ContractType.UNKNOWN
    except ValueError:
        contract_type = ContractType.UNKNOWN

    try:
        scores = state.scorer.score_findings(
            body.findings,
            contract_type=contract_type,
            contract_address=body.contract_address or None,
        )
        aggregate = state.scorer.compute_aggregate_risk(scores)

        response_data = ScoreResponse(
            scores=[_score_to_dict(s) for s in scores],
            aggregate=aggregate,
        )
        return ok(response_data)
    except Exception as exc:
        log.exception("score.failed", error=str(exc))
        raise err(f"Scoring failed: {exc}", status_code=500)


@app.post("/fix")
async def generate_fix(body: FixRequest, request: Request) -> ApiResponse:
    """Generate Solidity fix suggestions for detected findings.

    Returns before/after code diffs, solidity examples, and
    references for each detector.
    """
    state = _get_state(request)

    if not body.findings:
        raise err("At least one finding is required")

    try:
        fixes = state.fixer.generate_fixes(body.findings, body.contract_name)
        stats = state.fixer.get_stats()

        response_data = FixResponse(
            fixes=fixes,
            detector_count=len(fixes),
            template_coverage=stats,
        )
        return ok(response_data)
    except Exception as exc:
        log.exception("fix.failed", error=str(exc))
        raise err(f"Fix generation failed: {exc}", status_code=500)


@app.post("/exploit/paths")
async def predict_exploit_paths(body: ExploitPathRequest, request: Request) -> ApiResponse:
    """Predict exploit paths from findings.

    Combines multiple detected issues into attack chains and
    scores them by plausibility.
    """
    state = _get_state(request)

    if not body.findings:
        raise err("At least one finding is required")

    try:
        paths = state.path_predictor.predict_paths(
            body.findings,
            contract_type=body.contract_type,
        )
        critical_paths = [p for p in paths if p["severity"] == "critical"]
        high_paths = [p for p in paths if p["severity"] == "high"]
        summary = state.path_predictor.summarize_risk(paths)

        return ok(ExploitPathResponse(
            paths=paths,
            total=len(paths),
            critical_count=len(critical_paths),
            high_count=len(high_paths),
            summary=summary,
        ))
    except Exception as exc:
        log.exception("exploit.paths.failed", error=str(exc))
        raise err(f"Exploit path prediction failed: {exc}", status_code=500)


@app.post("/ask")
async def ask_question(body: AskRequest, request: Request) -> ApiResponse:
    """Ask a natural language question about scan results.

    Supports: summary, critical findings, filter by severity/detector,
    how to fix, safety assessment, exploit paths, contract classification.
    """
    state = _get_state(request)

    if not body.query.strip():
        raise err("Query is required")

    try:
        result = state.nlp.ask(
            query=body.query,
            findings=body.findings,
            contract_type_label=body.contract_type,
            aggregate_risk=body.aggregate_risk,
        )

        response_data = AskResponse(
            answer=result["answer"],
            intent=result["intent"],
            context=result["context"],
            findings=result["findings"],
            follow_up_questions=result["follow_up_questions"],
        )
        return ok(response_data)
    except Exception as exc:
        log.exception("ask.failed", error=str(exc))
        raise err(f"Query failed: {exc}", status_code=500)


@app.post("/feedback")
async def record_feedback(body: FeedbackRequest, request: Request) -> ApiResponse:
    """Record FP/TP feedback for a finding.

    The FP/TP database uses this feedback to:
    - Auto-suppress detectors that produce false positives
    - Boost severity for consistently accurate detectors
    - Provide confidence scores per detector
    """
    state = _get_state(request)

    try:
        state.fp_db.record_feedback(
            detector=body.detector,
            contract_address=body.contract_address,
            chain=body.chain,
            is_tp=body.is_tp,
            severity=body.severity,
            source=body.source,
        )

        stats = state.fp_db.get_detector_stats(body.detector)

        return ok(FeedbackResponse(
            recorded=True,
            detector=body.detector,
            contract=body.contract_address[:12],
            stats=stats,
        ))
    except Exception as exc:
        log.exception("feedback.failed", error=str(exc))
        raise err(f"Feedback recording failed: {exc}", status_code=500)


@app.get("/intel/stats")
async def intel_stats(request: Request) -> ApiResponse:
    """Get intelligence engine statistics and health."""
    state = _get_state(request)

    try:
        return ok(IntelStatsResponse(
            classifier={
                "available_detectors": state.classifier.get_available_detectors(),
                "contract_types": [ct.value for ct in ContractType],
            },
            scorer={
                "severity_levels": ["critical", "high", "medium", "low", "informational"],
                "detectors_with_exploitability": 35,
            },
            fp_db=state.fp_db.export_stats(),
            fixer=state.fixer.get_stats(),
            path_predictor={
                "patterns": len(state.path_predictor._patterns),
            },
            nlp={
                "intents": ["summary", "critical_findings", "filter_by_severity",
                            "filter_by_detector", "how_to_fix", "safety",
                            "exploit_path", "classify"],
            },
        ))
    except Exception as exc:
        log.exception("intel.stats.failed", error=str(exc))
        raise err(f"Stats failed: {exc}", status_code=500)


# ── Pipeline Endpoints (L5-L7) ─────────────────────────────


class PipelineRequest(BaseModel):
    """Request body for POST /pipeline/run."""
    findings: list[dict[str, Any]]
    source_code: dict[str, str] = {}
    contract_type: str = "unknown"
    contract_address: str = ""
    contract_name: str = ""
    compiler: str = ""
    audit_id: str = "default"
    enable_ai_verify: bool = True
    enable_fp_patterns: bool = True
    enable_scoring: bool = True
    enable_enrich: bool = True
    min_quality_score: float = 10.0


class PipelineResponse(BaseModel):
    report: dict[str, Any]
    relevant_count: int
    dropped_count: int
    drop_rate: float
    duration_ms: float


class AiVerifyRequest(BaseModel):
    findings: list[dict[str, Any]]
    source_code: dict[str, str]
    contract_name: str = ""
    compiler: str = ""
    audit_id: str = "default"


class AiVerifyResponse(BaseModel):
    results: list[dict[str, Any]]
    summary: dict[str, Any]


class FpPatternsRequest(BaseModel):
    findings: list[dict[str, Any]]
    source_code: dict[str, str] = {}
    include_details: bool = True


class FpPatternsResponse(BaseModel):
    results: list[dict[str, Any]]
    total_matched: int
    total_findings: int


@dataclass
class PipelineStats:
    pipeline: dict[str, Any]
    ai_verifier: dict[str, Any]
    fp_patterns: dict[str, Any]


@app.post("/pipeline/run")
async def run_pipeline(body: PipelineRequest, request: Request) -> ApiResponse:
    """Run the full quality pipeline on findings.

    Processes findings through:
      1. FP Pattern Matching (L6)
      2. AI Verification via 06-AI (L5)
      3. Composite Risk Scoring (L4)
      4. Ranking & Enrichment

    Returns a QualityReport with filtered, scored, enriched findings.
    """
    state = _get_state(request)

    if not body.findings:
        raise err("At least one finding is required")

    start = time.monotonic()

    try:
        contract_type = ContractType.UNKNOWN
        try:
            contract_type = ContractType(body.contract_type) if body.contract_type else ContractType.UNKNOWN
        except ValueError:
            pass

        # Configure pipeline stages
        enabled = set()
        if body.enable_fp_patterns:
            enabled.add(PipelineStage.FP_PATTERN)
            enabled.add(PipelineStage.NOISE_FILTER)
        if body.enable_scoring:
            enabled.add(PipelineStage.SCORE)
            enabled.add(PipelineStage.RANK)
        if body.enable_enrich:
            enabled.add(PipelineStage.ENRICH)
        if body.enable_ai_verify:
            enabled.add(PipelineStage.AI_VERIFY)

        state.pipeline._enable_stages = enabled
        state.pipeline._min_quality_score = body.min_quality_score

        report = await state.pipeline.run(
            findings=body.findings,
            source_code=body.source_code,
            contract_type=contract_type,
            contract_address=body.contract_address,
            contract_name=body.contract_name,
            compiler=body.compiler,
            audit_id=body.audit_id,
        )

        elapsed = time.monotonic() - start

        response_data = PipelineResponse(
            report=report.to_dict(),
            relevant_count=report.total_relevant,
            dropped_count=report.total_dropped,
            drop_rate=report.drop_rate,
            duration_ms=round(elapsed * 1000, 1),
        )

        log.info(
            "pipeline.run.complete",
            audit_id=body.audit_id,
            relevant=report.total_relevant,
            dropped=report.total_dropped,
            drop_rate=report.drop_rate,
            duration_ms=round(elapsed * 1000, 1),
        )

        return ok(response_data)

    except Exception as exc:
        log.exception("pipeline.run.failed", error=str(exc))
        raise err(f"Pipeline failed: {exc}", status_code=500)


@app.post("/pipeline/ai-verify")
async def ai_verify_findings(body: AiVerifyRequest, request: Request) -> ApiResponse:
    """Verify findings using 06-AI service.

    Each finding is sent to the LLM for context-aware TP/FP classification.
    Returns verdict, confidence, severity assessment, and reasoning.
    """
    state = _get_state(request)

    if not body.findings:
        raise err("At least one finding is required")

    try:
        results = await state.ai_verifier.verify_findings(
            findings=body.findings,
            source_code=body.source_code,
            audit_id=body.audit_id,
            contract_name=body.contract_name,
            compiler=body.compiler,
        )

        tp_count = sum(1 for r in results if r.is_true_positive)
        fp_count = len(results) - tp_count

        return ok(AiVerifyResponse(
            results=[r.to_dict() for r in results],
            summary={
                "total": len(results),
                "true_positives": tp_count,
                "false_positives": fp_count,
                "avg_confidence": round(
                    sum(r.ai_confidence for r in results) / max(len(results), 1), 3
                ),
            },
        ))
    except Exception as exc:
        log.exception("ai_verify.failed", error=str(exc))
        raise err(f"AI verification failed: {exc}", status_code=500)


@app.post("/pipeline/fp-patterns")
async def check_fp_patterns(body: FpPatternsRequest, request: Request) -> ApiResponse:
    """Match findings against known false-positive patterns.

    Checks each finding against the FP pattern database and returns
    matches with pattern name, confidence penalty, and severity reduction.
    """
    state = _get_state(request)

    if not body.findings:
        raise err("At least one finding is required")

    combined_source = "\n".join(body.source_code.values()) if body.source_code else ""

    results = []
    for f in body.findings:
        match = state.fp_pattern_matcher.evaluate_finding(f, combined_source)
        results.append({
            "finding_title": f.get("title", ""),
            "finding_severity": f.get("severity", ""),
            "match": match.to_dict() if match.is_fp else None,
        })

    total_matched = sum(1 for r in results if r["match"] is not None)

    return ok(FpPatternsResponse(
        results=results,
        total_matched=total_matched,
        total_findings=len(results),
    ))


@app.get("/pipeline/stats")
async def pipeline_stats(request: Request) -> ApiResponse:
    """Get quality pipeline statistics and health."""
    state = _get_state(request)

    return ok(PipelineStats(
        pipeline={
            "stages_available": [s.value for s in PipelineStage],
            "min_quality_score": state.pipeline._min_quality_score,
            "fp_patterns_count": len(state.fp_pattern_matcher._patterns),
        },
        ai_verifier=state.ai_verifier.get_cache_stats(),
        fp_patterns=state.fp_pattern_matcher.get_pattern_stats(),
    ))


# ── Custom Detector Endpoints ─────────────────────────────


@app.get("/detectors")
async def list_custom_detectors(request: Request) -> ApiResponse:
    """List all registered custom detectors."""
    state = _get_state(request)
    return ok({
        "built_in_count": state.detector_registry.get_built_in_count(),
        "custom_detectors": state.detector_registry.metadata,
        "total": len(state.detector_registry.detectors),
    })


@app.post("/detectors")
async def register_detector(name: str, source: str, request: Request) -> ApiResponse:
    """Register a new custom detector."""
    state = _get_state(request)
    try:
        meta = state.detector_registry.register_detector(name, source)
        log.info("detector.registered", name=name)
        return ok(meta)
    except DetectorLoadError as e:
        raise err(str(e))


@app.delete("/detectors/{name}")
async def unregister_detector(name: str, request: Request) -> ApiResponse:
    """Unregister and delete a custom detector."""
    state = _get_state(request)
    if state.detector_registry.unregister_detector(name):
        log.info("detector.unregistered", name=name)
        return ok({"removed": name})
    raise err(f"Detector '{name}' not found", status_code=404)


@app.get("/detectors/{name}/source")
async def get_detector_source(name: str, request: Request) -> ApiResponse:
    """Get the source code of a custom detector."""
    state = _get_state(request)
    source = state.detector_registry.get_source(name)
    if source is not None:
        return ok({"name": name, "source": source})
    raise err(f"Detector '{name}' not found", status_code=404)


@app.post("/scan/custom")
async def scan_with_custom(body: CustomScanRequest, request: Request) -> ApiResponse:
    """Run Slither scan with custom detectors."""
    from src.slither import SlitherRunner
    import uuid, shutil, asyncio

    start = time.monotonic()
    state = _get_state(request)

    if not body.sources:
        raise err("At least one source file is required")

    audit_id = str(uuid.uuid4())
    audit_dir = SOURCES_DIR / audit_id
    audit_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Write source files
        for file_path, source_code in body.sources.items():
            target = audit_dir / file_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source_code, encoding="utf-8")

        log.info("custom_scan.start",
            audit_id=audit_id, contract=body.address,
            custom_detectors=body.custom_detectors,
        )

        # Ensure solc version
        try:
            await asyncio.to_thread(state.solc_mgr.ensure_version, body.compiler)
        except RuntimeError as exc:
            log.warning("solc.unavailable", error=str(exc))

        all_findings: list[Finding] = []

        # Run built-in Slither if requested
        if body.include_built_in:
            config = SlitherConfigBuilder().with_tier(body.config_tier).build()
            slither_result = await asyncio.to_thread(
                state.slither_runner.run,
                audit_dir, config=config, timeout=body.timeout,
            )
            if slither_result.success:
                all_findings.extend(slither_result.findings)

        # Run custom detectors
        if body.custom_detectors:
            custom_findings = await asyncio.to_thread(
                state.detector_runner.run_detectors,
                audit_dir,
                body.custom_detectors,
                timeout=body.timeout,
            )
            all_findings.extend(custom_findings)

        elapsed = time.monotonic() - start

        critical = sum(1 for f in all_findings if f.severity == "critical")
        high = sum(1 for f in all_findings if f.severity == "high")

        result = ToolResult(
            tool="slither+custom",
            success=True,
            findings=all_findings,
            duration_seconds=round(elapsed, 2),
        )

        response = ScanResponse(
            audit_id=audit_id,
            contract_address=body.address,
            chain=body.chain,
            compiler=body.compiler,
            tools=[result],
            all_findings=all_findings,
            total_findings=len(all_findings),
            critical_count=critical,
            high_count=high,
            duration_seconds=round(elapsed, 2),
        )

        log.info("custom_scan.complete",
            findings=len(all_findings),
            custom=len(body.custom_detectors),
            duration=round(elapsed, 2),
        )

        return ok(response)

    except Exception as exc:
        log.exception("custom_scan.failed", audit_id=audit_id, error=str(exc))
        raise err(f"Custom scan failed: {exc}", status_code=500)

    finally:
        try:
            shutil.rmtree(audit_dir, ignore_errors=True)
        except OSError:
            pass


# ── Util ───────────────────────────────────────────────────


def _score_to_dict(score: RiskScore) -> dict[str, Any]:
    """Convert RiskScore dataclass to plain dict."""
    return {
        "finding_title": score.finding_title,
        "finding_severity": score.finding_severity,
        "detector": score.detector,
        "base_score": score.base_score,
        "exploitability": score.exploitability,
        "business_impact": score.business_impact,
        "contract_risk_factor": score.contract_risk_factor,
        "historical_confidence": score.historical_confidence,
        "raw_score": score.raw_score,
        "adjusted_score": score.adjusted_score,
        "normalized_score": score.normalized_score,
        "risk_label": score.risk_label,
        "recommendation": score.recommendation,
        "priority": score.priority,
    }


# ── Agent Protocol Endpoints ────────────────────────────────


@app.get("/agent/manifest")
async def slither_agent_manifest(request: Request) -> ApiResponse:
    """Publish agent manifest for Antonio discovery."""
    state = _get_state(request)
    if state.agent is None:
        raise err("Agent not initialized", 503)
    return ok(state.agent.get_manifest())


@app.post("/agent/delegate")
async def slither_agent_delegate(body: dict, request: Request) -> ApiResponse:
    """Receive a delegation from Antonio."""
    state = _get_state(request)
    if state.agent is None:
        raise err("Agent not initialized", 503)

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
async def slither_agent_negotiate(body: dict, request: Request) -> ApiResponse:
    """Handle a negotiation request from Antonio."""
    state = _get_state(request)
    if state.agent is None:
        raise err("Agent not initialized", 503)

    negotiation_req = NegotiationRequest(
        task_description=body.get("task_description", ""),
        required_capability=body.get("required_capability", ""),
        estimated_complexity=body.get("estimated_complexity", "medium"),
        budget_usd=body.get("budget_usd", 0.0),
        deadline_seconds=body.get("deadline_seconds", 0),
    )
    response = await state.agent.handle_negotiation(negotiation_req)
    return ok(response)


# ── Entry Point ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8014,
        log_level="info",
        reload=False,
    )
