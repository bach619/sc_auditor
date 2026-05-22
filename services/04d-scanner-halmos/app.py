"""Vyper Scanner Halmos Service — Standalone Halmos symbolic testing microservice.

Runs ``halmos`` (a16z symbolic execution) on Foundry test files.
Provides L2-L4 intelligence for counter-example interpretation.

Port: 8017
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from src.halmos import HalmosRunner, create_halmos_runner
from src.intelligence import (
    HalmosClassifier,
    HalmosFixer,
    HalmosNLP,
    HalmosPathPredictor,
    HalmosScorer,
    create_classifier,
    create_fixer,
    create_nlp,
    create_path_predictor,
    create_scorer,
)
from shared.observability import setup_observability

# ── Constants ──────────────────────────────────────────────

SERVICE_NAME = "scanner-halmos"
SERVICE_VERSION = "0.1.0"
DATA_DIR = Path("/data/scanner-halmos")

# ── Pydantic Schemas ───────────────────────────────────────


from pydantic import BaseModel, Field


class Meta(BaseModel):
    service: str = SERVICE_NAME
    version: str = SERVICE_VERSION


class ApiResponse(BaseModel):
    ok: bool
    data: Any | None = None
    error: str | None = None
    meta: Meta = Field(default_factory=Meta)


class ScanRequest(BaseModel):
    sources: dict[str, str]
    timeout: int = 300
    function: str | None = None


class HealthInfo(BaseModel):
    service: str = SERVICE_NAME
    version: str = SERVICE_VERSION
    halmos_available: bool = False
    halmos_version: str | None = None
    forge_available: bool = False
    forge_version: str | None = None


# ── Intel Schemas ──────────────────────────────────────────


class IntelClassifyRequest(BaseModel):
    findings: list[dict[str, Any]]


class IntelScoreRequest(BaseModel):
    findings: list[dict[str, Any]]


class IntelFixRequest(BaseModel):
    findings: list[dict[str, Any]]


class IntelChainRequest(BaseModel):
    findings: list[dict[str, Any]]


class IntelAskRequest(BaseModel):
    query: str
    findings: list[dict[str, Any]]


# ── App State ──────────────────────────────────────────────


class AppState:
    def __init__(self) -> None:
        self.runner: HalmosRunner = create_halmos_runner()
        # Intelligence
        self.classifier: HalmosClassifier = create_classifier()
        self.scorer: HalmosScorer = create_scorer()
        self.fixer: HalmosFixer = create_fixer()
        self.chain_predictor: HalmosPathPredictor = create_path_predictor()
        self.nlp: HalmosNLP = create_nlp()


def _get_state(request: Request) -> AppState:
    return request.app.state.vyper  # type: ignore[attr-defined]


# ── Lifespan ───────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    state = AppState()
    app.state.vyper = state

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    halmos_avail, halmos_ver = state.runner.check_available()
    forge_avail, forge_ver = state.runner.check_forge()

    log.info(
        "halmos.startup",
        service=SERVICE_NAME, version=SERVICE_VERSION,
        halmos_available=halmos_avail, halmos_version=halmos_ver,
        forge_available=forge_avail, forge_version=forge_ver,
        intel_categories=len(state.classifier.get_categories()),
    )
    yield
    log.info("halmos.shutdown", service=SERVICE_NAME)


# ── App Factory ────────────────────────────────────────────

app = FastAPI(
    title="Vyper Scanner Halmos Service",
    description="Runs Halmos symbolic execution on Foundry tests.",
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

log = setup_observability(app, "04d-scanner-halmos", "0.1.0")


def ok(data: object = None) -> ApiResponse:
    return ApiResponse(ok=True, data=data)


def err(detail: str, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


# ── Core Endpoints ─────────────────────────────────────────


@app.get("/health")
async def health(request: Request) -> ApiResponse:
    state = _get_state(request)
    halmos_avail, halmos_ver = state.runner.check_available()
    forge_avail, forge_ver = state.runner.check_forge()
    return ok(HealthInfo(
        halmos_available=halmos_avail,
        halmos_version=halmos_ver,
        forge_available=forge_avail,
        forge_version=forge_ver,
    ))


@app.post("/scan")
async def run_scan(body: ScanRequest, request: Request) -> ApiResponse:
    """Run Halmos symbolic execution on Foundry test files."""
    start = time.monotonic()
    state = _get_state(request)

    if not body.sources:
        raise err("At least one source file is required")

    result = await asyncio.to_thread(
        state.runner.run,
        sources=body.sources,
        timeout=body.timeout,
        function=body.function,
    )

    elapsed = time.monotonic() - start


    # ── Intelligence enrichment ────────────────────────────
    if result.findings:
        try:
            finding_dicts = [f.to_dict() for f in result.findings]
            enriched = state.classifier.classify_batch(finding_dicts)
            scores = state.scorer.score_findings(enriched)

            # Enrich findings in-place
            for i, f in enumerate(result.findings):
                if i < len(enriched):
                    f.category = enriched[i].get("category", f.category)
                    f.confidence = enriched[i].get("confidence", f.confidence)
        except Exception as exc:
            log.warning("halmos.intel_failed", error=str(exc))

    log.info(
        "halmos.scan.complete",
        findings=len(result.findings),
        passed=result.passed,
        failed=result.failed,
        duration=round(elapsed, 2),
    )

    return ok(result.to_dict())


# ── Intelligence Endpoints ─────────────────────────────────


@app.post("/intel/classify")
async def intel_classify(body: IntelClassifyRequest, request: Request) -> ApiResponse:
    """Classify Halmos symbolic execution findings."""
    state = _get_state(request)
    if not body.findings:
        raise err("At least one finding is required")

    enriched = state.classifier.classify_batch(body.findings)
    categories: dict[str, int] = {}
    for f in enriched:
        cat = f.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    return ok({
        "enriched_findings": enriched,
        "categories": categories,
        "total": len(enriched),
    })


@app.post("/intel/score")
async def intel_score(body: IntelScoreRequest, request: Request) -> ApiResponse:
    """Score Halmos findings."""
    state = _get_state(request)
    if not body.findings:
        raise err("At least one finding is required")

    scores = state.scorer.score_findings(body.findings)
    aggregate = state.scorer.compute_aggregate(scores)
    return ok({"scores": scores, "aggregate": aggregate})


@app.post("/intel/fix")
async def intel_fix(body: IntelFixRequest, request: Request) -> ApiResponse:
    """Generate fix suggestions for Halmos findings."""
    state = _get_state(request)
    if not body.findings:
        raise err("At least one finding is required")

    fixes = state.fixer.generate_fixes(body.findings)
    return ok({
        "fixes": fixes,
        "template_stats": state.fixer.get_stats(),
    })


@app.post("/intel/paths")
async def intel_paths(body: IntelChainRequest, request: Request) -> ApiResponse:
    """Predict exploit chains from Halmos findings."""
    state = _get_state(request)
    if not body.findings:
        raise err("At least one finding is required")

    chains = state.chain_predictor.predict_chains(body.findings)
    summary = state.chain_predictor.summarize(chains)
    return ok({"chains": chains, "summary": summary})


@app.post("/intel/ask")
async def intel_ask(body: IntelAskRequest, request: Request) -> ApiResponse:
    """Ask questions about Halmos symbolic execution results."""
    state = _get_state(request)
    chains = state.chain_predictor.predict_chains(body.findings)

    result = state.nlp.ask(
        query=body.query,
        findings=body.findings,
        chains=chains,
    )
    return ok(result)


@app.get("/intel/stats")
async def intel_stats(request: Request) -> ApiResponse:
    """Get intelligence engine statistics."""
    state = _get_state(request)
    return ok({
        "classifier": {
            "categories": state.classifier.get_categories(),
        },
        "scorer": {
            "factors": ["severity_base", "category_weight", "calldata_complexity"],
        },
        "fixer": state.fixer.get_stats(),
        "chain_predictor": {
            "chains_defined": 3,
            "chain_names": ["unauthorized_drain", "price_oracle_attack", "reentrancy_exploit"],
        },
    })


# ── Entry Point ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8017,
        log_level="info",
        reload=False,
    )
