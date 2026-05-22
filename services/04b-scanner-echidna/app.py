"""Vyper Scanner Echidna Service — Standalone Echidna fuzzing microservice.

Runs Echidna property-based fuzzing on Solidity contracts.
Augmented with L2-L4 intelligence for fuzzing-specific analysis.

Port: 8015
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.echidna import EchidnaRunner, create_echidna_runner
from src.intelligence import (
    EchidnaClassifier,
    EchidnaFixer,
    EchidnaNLP,
    EchidnaScorer,
    FailureCategory,
    FailureScore,
    SequenceAnalyzer,
    create_classifier,
    create_fixer,
    create_nlp,
    create_path_predictor,
    create_scorer,
)
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
from shared.observability import setup_observability
from vyper_lib.solc_manager import SolcManager, create_solc_manager
from vyper_lib.deps import DependencyResolver, create_dependency_resolver

# ── Constants ──────────────────────────────────────────────

SERVICE_NAME = "scanner-echidna"
SERVICE_VERSION = "0.2.0"
DATA_DIR = Path("/data/scanner-echidna")
SOURCES_DIR = DATA_DIR / "sources"

# ── Pydantic Schemas ───────────────────────────────────────


class ClassifyRequest(BaseModel):
    findings: list[dict[str, Any]]


class ClassifyResponse(BaseModel):
    total: int
    categories: dict[str, int]
    severity_counts: dict[str, int]


class ScoreRequest(BaseModel):
    findings: list[dict[str, Any]]


class ScoreResponse(BaseModel):
    scores: list[dict[str, Any]]
    aggregate: dict[str, Any]


class FixRequest(BaseModel):
    findings: list[dict[str, Any]]


class FixResponse(BaseModel):
    fixes: dict[str, list[dict[str, Any]]]
    template_stats: dict[str, Any]


class AskRequest(BaseModel):
    query: str
    findings: list[dict[str, Any]]
    aggregate: dict[str, Any] | None = None


class AskResponse(BaseModel):
    answer: str
    intent: str
    context: dict[str, Any]
    findings: list[dict[str, Any]]
    follow_up_questions: list[str]


class SequenceRequest(BaseModel):
    findings: list[dict[str, Any]]


class SequenceResponse(BaseModel):
    analyses: list[dict[str, Any]]
    total: int


# ── App State ──────────────────────────────────────────────


class AppState:
    def __init__(self) -> None:
        # Core
        self.solc_mgr: SolcManager = create_solc_manager()
        self.echidna_runner: EchidnaRunner = create_echidna_runner()
        self.dep_resolver: DependencyResolver = create_dependency_resolver()
        # Intelligence
        self.classifier: EchidnaClassifier = create_classifier()
        self.scorer: EchidnaScorer = create_scorer()
        self.fixer: EchidnaFixer = create_fixer()
        self.sequence: SequenceAnalyzer = create_path_predictor()
        self.nlp: EchidnaNLP = create_nlp(
            classifier=self.classifier,
            fixer=self.fixer,
        )


def _get_state(request: Request) -> AppState:
    return request.app.state.vyper


# ── Lifespan ───────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    state = AppState()
    app.state.vyper = state

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    solc_versions = state.solc_mgr.list_versions()
    log.info(
        "echidna.startup",
        service=SERVICE_NAME, version=SERVICE_VERSION,
        solc_versions=len(solc_versions),
        intel_categories=len(state.classifier.get_available_categories()),
    )
    yield
    log.info("echidna.shutdown", service=SERVICE_NAME)


# ── App Factory ────────────────────────────────────────────

app = FastAPI(
    title="Vyper Scanner Echidna Service",
    description="Runs Echidna fuzzing on Solidity contracts.",
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

log = setup_observability(app, "04b-scanner-echidna", "0.1.0")


def ok(data: object = None) -> ApiResponse:
    return ApiResponse(data=data, meta=Meta(status="ok"))


def err(detail: str, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


# ── Core Endpoints ─────────────────────────────────────────


@app.get("/health")
async def health(request: Request) -> ApiResponse:
    state = _get_state(request)
    solc_versions = await asyncio.to_thread(state.solc_mgr.list_versions)

    echidna_available = False
    echidna_version = None
    try:
        result = await asyncio.to_thread(
            subprocess.run, ["echidna", "--version"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            echidna_available = True
            echidna_version = (result.stdout.strip() or result.stderr.strip())[:100]
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    return ok(HealthData(
        status="ok", service=SERVICE_NAME, version=SERVICE_VERSION,
        tools_available=1 if echidna_available else 0,
        tools_installed=["echidna"] if echidna_available else [],
        solc_versions=solc_versions,
    ))


@app.post("/scan")
async def run_scan(body: ScanRequest, request: Request) -> ApiResponse:
    """Run Echidna fuzzing on Solidity source code.

    Results are enriched with failure classification and scoring.
    """
    start = time.monotonic()
    state = _get_state(request)

    if not body.sources:
        raise err("At least one source file is required")

    audit_id = str(uuid.uuid4())
    audit_dir = SOURCES_DIR / audit_id
    audit_dir.mkdir(parents=True, exist_ok=True)

    try:
        for file_path, source_code in body.sources.items():
            target = audit_dir / file_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source_code, encoding="utf-8")

        log.info(
            "echidna.scan.start",
            audit_id=audit_id, contract=body.address,
            chain=body.chain, files=len(body.sources),
        )

        try:
            await asyncio.to_thread(state.solc_mgr.ensure_version, body.compiler)
        except RuntimeError as exc:
            log.warning("echidna.solc_unavailable", error=str(exc))

        try:
            deps = await asyncio.to_thread(state.dep_resolver.resolve, audit_dir)
            if deps:
                log.info("echidna.deps_resolved", count=len(deps))
        except Exception as exc:
            log.warning("echidna.deps_failed", error=str(exc))

        result = await asyncio.to_thread(
            state.echidna_runner.run,
            audit_dir,
            contract_name=body.contract_name,
            timeout=body.timeout,
        )

        elapsed = time.monotonic() - start

        # ── Intelligence enrichment ────────────────────────
        if result.success and result.findings:
            try:
                finding_dicts = [f.model_dump() for f in result.findings]
                enriched = state.classifier.classify_batch(finding_dicts)
                scores = state.scorer.score_findings(enriched)

                # Merge back
                for i, f in enumerate(result.findings):
                    if i < len(enriched):
                        f.metadata["failure_category"] = enriched[i].get("failure_category")
                        f.metadata["failure_label"] = enriched[i].get("failure_label")
                        f.metadata["failure_severity"] = enriched[i].get("failure_severity")
                        f.metadata["failure_confidence"] = enriched[i].get("failure_confidence")
                    if i < len(scores):
                        f.metadata["risk_score"] = scores[i].normalized_score
                        f.metadata["risk_label"] = scores[i].risk_label
                        f.metadata["priority"] = scores[i].priority
            except Exception as exc:
                log.warning("echidna.intel_failed", error=str(exc))

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
        )

        log.info(
            "echidna.scan.complete",
            audit_id=audit_id, findings=len(result.findings),
            critical=critical, high=high, duration=round(elapsed, 2),
        )

        return ok(scan_response)

    except Exception as exc:
        log.exception("echidna.scan.failed", audit_id=audit_id, error=str(exc))
        raise err(f"Scan failed: {exc}", status_code=500)

    finally:
        try:
            shutil.rmtree(audit_dir, ignore_errors=True)
        except OSError:
            pass


@app.post("/install")
async def install_echidna() -> ApiResponse:
    """Install or update Echidna binary."""
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["curl", "-fsSL", "https://api.github.com/repos/crytic/echidna/releases/latest"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return ok(InstallResult(tool="echidna", success=False, error="GitHub API failed"))

        import json as _json
        release = _json.loads(result.stdout)
        tag = release.get("tag_name", "v2.3.2")
        version_str = tag.lstrip("v")
        url = f"https://github.com/crytic/echidna/releases/download/{tag}/echidna-{version_str}-x86_64-linux.tar.gz"

        dl = await asyncio.to_thread(
            subprocess.run,
            ["curl", "-fsSL", url, "-o", "/tmp/echidna.tar.gz"],
            capture_output=True, text=True, timeout=120,
        )
        if dl.returncode != 0:
            return ok(InstallResult(tool="echidna", success=False, error="Download failed"))

        await asyncio.to_thread(
            subprocess.run,
            ["tar", "-xzf", "/tmp/echidna.tar.gz", "-C", "/tmp/"],
            capture_output=True, text=True, timeout=30,
        )
        await asyncio.to_thread(
            subprocess.run,
            ["install", "-m", "755", "/tmp/echidna", "/usr/local/bin/echidna"],
            capture_output=True, text=True, timeout=30,
        )

        return ok(InstallResult(tool="echidna", success=True, version=version_str))

    except Exception as exc:
        return ok(InstallResult(tool="echidna", success=False, error=str(exc)[:200]))


# ── Intelligence Endpoints ─────────────────────────────────


@app.post("/classify")
async def classify_findings(body: ClassifyRequest, request: Request) -> ApiResponse:
    """Classify Echidna findings by failure category."""
    state = _get_state(request)
    if not body.findings:
        raise err("At least one finding is required")

    enriched = state.classifier.classify_batch(body.findings)
    categories: dict[str, int] = {}
    severities: dict[str, int] = {}
    for f in enriched:
        cat = f.get("failure_category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1
        sev = f.get("failure_severity", "unknown")
        severities[sev] = severities.get(sev, 0) + 1

    return ok({
        "enriched_findings": enriched,
        "categories": categories,
        "severity_counts": severities,
        "total": len(enriched),
    })


@app.post("/score")
async def score_findings(body: ScoreRequest, request: Request) -> ApiResponse:
    """Score fuzzing findings."""
    state = _get_state(request)
    if not body.findings:
        raise err("At least one finding is required")

    scores = state.scorer.score_findings(body.findings)
    aggregate = state.scorer.compute_aggregate(scores)

    return ok({
        "scores": [_s_to_dict(s) for s in scores],
        "aggregate": aggregate,
    })


@app.post("/fix")
async def generate_fix(body: FixRequest, request: Request) -> ApiResponse:
    """Generate fix suggestions."""
    state = _get_state(request)
    if not body.findings:
        raise err("At least one finding is required")

    fixes = state.fixer.generate_fixes(body.findings)
    return ok({
        "fixes": fixes,
        "template_stats": state.fixer.get_stats(),
    })


@app.post("/sequence")
async def analyze_sequences(body: SequenceRequest, request: Request) -> ApiResponse:
    """Analyze Echidna call sequences."""
    state = _get_state(request)
    if not body.findings:
        raise err("At least one finding is required")

    analyses = state.sequence.analyze_findings(body.findings)
    return ok({
        "analyses": analyses,
        "total": len(analyses),
    })


@app.post("/ask")
async def ask_question(body: AskRequest, request: Request) -> ApiResponse:
    """Ask about fuzzing results."""
    state = _get_state(request)

    result = state.nlp.ask(
        query=body.query,
        findings=body.findings,
        aggregate=body.aggregate,
    )
    return ok(result)


@app.get("/intel/stats")
async def intel_stats(request: Request) -> ApiResponse:
    """Get intelligence engine stats."""
    state = _get_state(request)
    return ok({
        "classifier": {
            "categories": state.classifier.get_available_categories(),
        },
        "scorer": {
            "factors": ["reproducibility", "sequence_complexity", "fund_movement", "category_weight"],
        },
        "fixer": state.fixer.get_stats(),
        "sequence": {
            "features": ["call_parsing", "eth_detection", "delegatecall_detection"],
        },
    })


# ── Helper ─────────────────────────────────────────────────


def _s_to_dict(s: FailureScore) -> dict[str, Any]:
    return {
        "finding_title": s.finding_title,
        "test_function": s.test_function,
        "category": s.category,
        "severity": s.severity,
        "reproducibility": s.reproducibility,
        "sequence_complexity": s.sequence_complexity,
        "fund_movement": s.fund_movement,
        "category_weight": s.category_weight,
        "raw_score": s.raw_score,
        "normalized_score": s.normalized_score,
        "risk_label": s.risk_label,
        "priority": s.priority,
    }


# ── Entry Point ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8015,
        log_level="info",
        reload=False,
    )
