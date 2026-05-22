"""Vyper Scanner Forge Service — Standalone Foundry build verification microservice.

Runs ``forge build`` to verify Solidity source code compiles.
Does NOT include Slither, Echidna, or Mythril.

Port: 8016
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
from pydantic import BaseModel

from src.forge import ForgeRunner, create_forge_runner
from src.intelligence import (
    CompilerClassifier,
    CompilerFixer,
    CompilerNLP,
    CompilerScorer,
    create_classifier,
    create_fixer,
    create_nlp,
    create_scorer,
)
from vyper_lib.models import (
    ApiResponse,
    BuildRequest,
    ForgeResult,
    HealthData,
    InstallResult,
    Meta,
    ScanResponse,
)
from shared.observability import setup_observability
from vyper_lib.solc_manager import SolcManager, create_solc_manager
from vyper_lib.deps import DependencyResolver, create_dependency_resolver

# ── Constants ──────────────────────────────────────────────

SERVICE_NAME = "scanner-forge"
SERVICE_VERSION = "0.1.0"
DATA_DIR = Path("/data/scanner-forge")
SOURCES_DIR = DATA_DIR / "sources"

# ── App State ──────────────────────────────────────────────


# ── Intel Request Schemas ──────────────────────────────────


class IntelClassifyRequest(BaseModel):
    errors: list[str]


class IntelScoreRequest(BaseModel):
    errors: list[dict[str, Any]]


class IntelFixRequest(BaseModel):
    errors: list[dict[str, Any]]


class IntelAskRequest(BaseModel):
    query: str
    errors: list[dict[str, Any]]


# ── App State ──────────────────────────────────────────────


class AppState:
    def __init__(self) -> None:
        self.solc_mgr: SolcManager = create_solc_manager()
        self.forge_runner: ForgeRunner = create_forge_runner()
        self.dep_resolver: DependencyResolver = create_dependency_resolver()
        # Intelligence engine
        self.classifier: CompilerClassifier = create_classifier()
        self.scorer: CompilerScorer = create_scorer()
        self.fixer: CompilerFixer = create_fixer()
        self.nlp: CompilerNLP = create_nlp()


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
        "forge.startup",
        service=SERVICE_NAME, version=SERVICE_VERSION,
        solc_versions=len(solc_versions),
        intel_patterns=len(state.classifier.get_categories()),
    )
    yield
    log.info("forge.shutdown", service=SERVICE_NAME)


# ── App Factory ────────────────────────────────────────────

app = FastAPI(
    title="Vyper Scanner Forge Service",
    description="Runs Foundry Forge build verification on Solidity contracts.",
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

log = setup_observability(app, "04c-scanner-forge", "0.1.0")


def ok(data: object = None) -> ApiResponse:
    return ApiResponse(data=data, meta=Meta(status="ok"))


def err(detail: str, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


# ── Endpoints ──────────────────────────────────────────────


@app.get("/health")
async def health(request: Request) -> ApiResponse:
    state = _get_state(request)
    solc_versions = await asyncio.to_thread(state.solc_mgr.list_versions)

    forge_available = False
    forge_version = None
    try:
        result = await asyncio.to_thread(
            subprocess.run, ["forge", "--version"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            forge_available = True
            forge_version = (result.stdout.strip() or result.stderr.strip())[:100]
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    return ok(HealthData(
        status="ok", service=SERVICE_NAME, version=SERVICE_VERSION,
        tools_available=1 if forge_available else 0,
        tools_installed=["forge"] if forge_available else [],
        solc_versions=solc_versions,
    ))


@app.post("/build")
async def run_build(body: BuildRequest, request: Request) -> ApiResponse:
    """Run Forge build verification on Solidity source code."""
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
            "forge.build.start",
            audit_id=audit_id, contract=body.address,
            chain=body.chain, files=len(body.sources),
        )

        # Ensure solc
        try:
            await asyncio.to_thread(state.solc_mgr.ensure_version, body.compiler)
        except RuntimeError as exc:
            log.warning("forge.solc_unavailable", error=str(exc))

        # Resolve deps
        try:
            deps = await asyncio.to_thread(state.dep_resolver.resolve, audit_dir)
            if deps:
                log.info("forge.deps_resolved", count=len(deps))
        except Exception as exc:
            log.warning("forge.deps_failed", error=str(exc))

        # Run Forge build
        result = await asyncio.to_thread(
            state.forge_runner.run,
            audit_dir,
            compiler_version=body.compiler,
            timeout=body.timeout,
        )

        elapsed = time.monotonic() - start

        scan_response = ScanResponse(
            audit_id=audit_id,
            contract_address=body.address,
            chain=body.chain,
            compiler=body.compiler,
            forge=result,
            tools=[],
            all_findings=[],
            total_findings=0,
            critical_count=0,
            high_count=0,
            duration_seconds=round(elapsed, 2),
        )

        log.info(
            "forge.build.complete",
            audit_id=audit_id,
            success=result.success, errors=len(result.errors),
            duration=round(elapsed, 2),
        )

        return ok(scan_response)

    except Exception as exc:
        log.exception("forge.build.failed", audit_id=audit_id, error=str(exc))
        raise err(f"Build failed: {exc}", status_code=500)

    finally:
        try:
            shutil.rmtree(audit_dir, ignore_errors=True)
        except OSError:
            pass


@app.post("/install")
async def install_forge() -> ApiResponse:
    """Install or update Foundry (forge)."""
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["curl", "-fsSL", "https://foundry.paradigm.xyz", "-o", "/tmp/foundryup.sh"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return ok(InstallResult(tool="forge", success=False, error="Failed to download foundryup"))

        await asyncio.to_thread(
            subprocess.run,
            ["sh", "/tmp/foundryup.sh"],
            capture_output=True, text=True, timeout=60,
        )

        import os as _os
        foundryup_bin = "/root/.foundry/bin/foundryup"
        if _os.path.exists(foundryup_bin):
            result = await asyncio.to_thread(
                subprocess.run,
                [foundryup_bin],
                capture_output=True, text=True, timeout=300,
            )
            # Create symlinks
            for bin_name in ["forge", "cast", "anvil"]:
                src = f"/root/.foundry/bin/{bin_name}"
                dst = f"/usr/local/bin/{bin_name}"
                await asyncio.to_thread(
                    subprocess.run, ["ln", "-sf", src, dst],
                    capture_output=True, text=True,
                )
            return ok(InstallResult(tool="forge", success=True, version="latest"))

        return ok(InstallResult(tool="forge", success=False, error="foundryup binary not found"))
    except Exception as exc:
        return ok(InstallResult(tool="forge", success=False, error=str(exc)[:200]))


# ── Intelligence Endpoints ─────────────────────────────────


@app.post("/intel/classify")
async def intel_classify(body: IntelClassifyRequest, request: Request) -> ApiResponse:
    """Classify compiler errors by category."""
    state = _get_state(request)
    if not body.errors:
        raise err("At least one error message is required")

    classified = state.classifier.classify_batch(body.errors)
    categories: dict[str, int] = {}
    for c in classified:
        cat = c.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    return ok({
        "classified": classified,
        "categories": categories,
        "total": len(classified),
    })


@app.get("/intel/classify/categories")
async def intel_categories(request: Request) -> ApiResponse:
    """List available compiler error categories."""
    state = _get_state(request)
    return ok({
        "categories": state.classifier.get_categories(),
        "pattern_counts": state.classifier.get_pattern_count(),
    })


@app.post("/intel/score")
async def intel_score(body: IntelScoreRequest, request: Request) -> ApiResponse:
    """Score compiler errors."""
    state = _get_state(request)
    if not body.errors:
        raise err("At least one error is required")

    scored = state.scorer.score_errors(body.errors)
    aggregate = state.scorer.compute_aggregate(scored)
    return ok({"scored_errors": scored, "aggregate": aggregate})


@app.post("/intel/fix")
async def intel_fix(body: IntelFixRequest, request: Request) -> ApiResponse:
    """Generate fix suggestions for compiler errors."""
    state = _get_state(request)
    if not body.errors:
        raise err("At least one error is required")

    fixes = state.fixer.generate_fixes(body.errors)
    return ok({
        "fixes": fixes,
        "template_stats": state.fixer.get_stats(),
    })


@app.post("/intel/ask")
async def intel_ask(body: IntelAskRequest, request: Request) -> ApiResponse:
    """Ask questions about compiler errors."""
    state = _get_state(request)

    # First classify for context
    raw_msgs = [e.get("error", e.get("message", "")) for e in body.errors]
    if raw_msgs:
        classified = state.classifier.classify_batch(raw_msgs)
        enriched = []
        for i, e in enumerate(body.errors):
            merged = dict(e)
            if i < len(classified):
                merged.update(classified[i])
            enriched.append(merged)
    else:
        enriched = list(body.errors)

    result = state.nlp.ask(
        query=body.query,
        errors=enriched,
    )
    return ok(result)


# ── Entry Point ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8016,
        log_level="info",
        reload=False,
    )
