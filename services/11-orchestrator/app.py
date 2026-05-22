"""Vyper Orchestrator Service — FastAPI entry point.

Central workflow engine that coordinates the entire audit pipeline.
Manages priority queue, daemon mode, contract similarity, and retroactive re-runs.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from src.batch import BatchProcessor
from src.config import config
from src.daemon import Daemon
from src.models import (
    ApiResponse,
    AuditRecord,
    AuditRequest,
    DaemonState,
    DaemonStatus,
    PipelineState,
    PipelineStats,
    QueueItem,
    RerunRequest,
)
from src.pipeline import Pipeline
from src.priority import PriorityScorer
from src.resource_governor import ResourceGovernor, ToolType
from shared.observability import setup_observability
from src.similarity import ContractSimilarity

# ── Application ─────────────────────────────────────────────────
app = FastAPI(
    title="Vyper Orchestrator Service",
    description="Central workflow engine — coordinates the entire audit pipeline across services",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = setup_observability(app, "11-orchestrator", "1.0.0")

# ── Dependencies (injected at startup) ──────────────────────────
governor: ResourceGovernor
pipeline: Pipeline
batch: BatchProcessor
scorer: PriorityScorer
similarity: ContractSimilarity
daemon: Daemon


@app.on_event("startup")
async def startup() -> None:
    """Initialise all components."""
    global governor, pipeline, batch, scorer, similarity, daemon

    logger.info("Starting Orchestrator Service")

    governor = ResourceGovernor(
        max_concurrent_scans=config.max_concurrent_scans,
        max_concurrent_ai=config.max_concurrent_ai,
    )
    pipeline = Pipeline(governor)
    scorer = PriorityScorer()
    similarity = ContractSimilarity()
    batch = BatchProcessor(pipeline)
    daemon = Daemon(pipeline, batch, scorer)

    logger.info(
        "Orchestrator ready — step_timeout=%ds, max_retries=%d",
        config.step_timeout_seconds,
        config.retry_max_attempts,
    )


@app.on_event("shutdown")
async def shutdown() -> None:
    """Graceful shutdown: stop daemon, close connections."""
    logger.info("Shutting down Orchestrator Service")

    if daemon.get_status().status == DaemonStatus.RUNNING:
        await daemon.stop()

    await pipeline.close()
    logger.info("Shutdown complete")


# ── Helper ──────────────────────────────────────────────────────

def _ok(data: Any = None, **meta: Any) -> JSONResponse:
    """Standard success response envelope."""
    response = ApiResponse(
        data=data,
        meta={
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **meta,
        },
    )
    return JSONResponse(content=response.model_dump(mode="json"))


def _err(
    message: str,
    status_code: int = 400,
    **meta: Any,
) -> JSONResponse:
    """Standard error response envelope."""
    return JSONResponse(
        content={
            "data": None,
            "meta": {
                "status": "error",
                "error": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **meta,
            },
        },
        status_code=status_code,
    )


# ── GET /health ─────────────────────────────────────────────────

@app.get("/health")
async def health() -> JSONResponse:
    """Health check with pipeline status summary."""
    stats = pipeline.get_stats()
    daemon_state = daemon.get_status()
    return _ok(
        data={
            "service": "orchestrator",
            "version": "1.0.0",
            "uptime_seconds": None,
            "daemon": daemon_state.status.value,
            "pipeline": {
                "total_audits": stats.total_audits,
                "completed": stats.completed,
                "failed": stats.failed,
                "in_progress": stats.in_progress,
                "active_tasks": len(pipeline._running),
            },
            "resources": {
                "scanner_slots": {
                    "available": governor.available_slots(ToolType.SCANNER),
                    "max": governor.max_slots(ToolType.SCANNER),
                },
                "ai_slots": {
                    "available": governor.available_slots(ToolType.AI),
                    "max": governor.max_slots(ToolType.AI),
                },
            },
            "similarity_db": {
                "contracts": similarity.n_contracts,
                "clusters": similarity.n_clusters,
            },
            "queue_size": batch.queue_size(),
        }
    )


# ── POST /audit ─────────────────────────────────────────────────

@app.post("/audit", status_code=201)
async def start_audit(body: AuditRequest) -> JSONResponse:
    """Start a new audit for a contract.

    Body:
        chain (str): Blockchain name (e.g. "ethereum")
        address (str): Contract address (0x-prefixed)
        program (str, optional): Immunefi program slug
        priority (int, optional): Priority 0–10, default 5
        metadata (dict, optional): Extra context
    """
    # Validate address
    if not body.address.startswith("0x"):
        return _err("Address must be 0x-prefixed")

    # Register the audit
    audit_id = pipeline.register_audit(
        chain=body.chain,
        address=body.address,
        program=body.program,
        priority=body.priority,
    )

    record = pipeline.get_record(audit_id)
    if record:
        record.use_ai = body.use_ai
        record.metadata["use_ai"] = body.use_ai
        record.metadata.update(body.metadata)

    # Launch pipeline in background
    asyncio.create_task(pipeline.run(audit_id))

    logger.info(
        "Audit started",
        audit_id=audit_id,
        chain=body.chain,
        address=body.address,
        program=body.program,
    )

    return _ok(
        data={
            "audit_id": audit_id,
            "chain": body.chain,
            "address": body.address,
            "program": body.program,
            "priority": body.priority,
            "state": PipelineState.PENDING.value,
        },
        audit_id=audit_id,
    )


# ── GET /audit/{audit_id} ──────────────────────────────────────

@app.get("/audit/{audit_id}")
async def get_audit(audit_id: str) -> JSONResponse:
    """Get the status and results of a specific audit."""
    record = pipeline.get_record(audit_id)
    if not record:
        return _err(f"Audit not found: {audit_id}", status_code=404)

    return _ok(
        data=record.model_dump(mode="json"),
        audit_id=audit_id,
        state=record.state.value,
    )


# ── GET /audits ─────────────────────────────────────────────────

@app.get("/audits")
async def list_audits(
    state: Optional[str] = Query(None, description="Filter by pipeline state"),
    program: Optional[str] = Query(None, description="Filter by program slug"),
    chain: Optional[str] = Query(None, description="Filter by chain name"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> JSONResponse:
    """List all audits with optional filtering and pagination."""
    state_enum = None
    if state:
        try:
            state_enum = PipelineState(state.upper())
        except ValueError:
            return _err(f"Invalid state: {state}. Valid: {[s.value for s in PipelineState]}")

    records, total = pipeline.get_all_records(
        state=state_enum,
        program=program,
        chain=chain,
        limit=limit,
        offset=offset,
    )

    return _ok(
        data=[r.model_dump(mode="json") for r in records],
        total=total,
        limit=limit,
        offset=offset,
        returned=len(records),
    )


# ── POST /queue ─────────────────────────────────────────────────

@app.post("/queue", status_code=201)
async def add_to_queue(body: QueueItem) -> JSONResponse:
    """Add a contract to the priority queue."""
    if not body.address.startswith("0x"):
        return _err("Address must be 0x-prefixed")

    batch.add_to_queue(body)

    logger.info(
        "Added to queue",
        contract_id=body.contract_id,
        score=body.priority_score,
    )

    return _ok(
        data=body.model_dump(mode="json"),
        queue_size=batch.queue_size(),
    )


# ── GET /queue ──────────────────────────────────────────────────

@app.get("/queue")
async def view_queue(
    sorted: bool = Query(True, description="Sort by priority descending"),
    limit: int = Query(100, ge=1, le=1000),
) -> JSONResponse:
    """View the priority queue."""
    items = batch.get_queue(sorted_=sorted)
    return _ok(
        data=[item.model_dump(mode="json") for item in items[:limit]],
        total=len(items),
        returned=min(len(items), limit),
    )


# ── POST /daemon/start ──────────────────────────────────────────

@app.post("/daemon/start")
async def daemon_start() -> JSONResponse:
    """Start the daemon mode (continuous scanning loop)."""
    state = await daemon.start()
    return _ok(
        data=state.model_dump(mode="json"),
        message="Daemon started",
    )


# ── POST /daemon/stop ───────────────────────────────────────────

@app.post("/daemon/stop")
async def daemon_stop() -> JSONResponse:
    """Stop the daemon mode."""
    state = await daemon.stop()
    return _ok(
        data=state.model_dump(mode="json"),
        message="Daemon stopped",
    )


# ── GET /daemon/status ─────────────────────────────────────────

@app.get("/daemon/status")
async def daemon_status() -> JSONResponse:
    """Get daemon status."""
    state = daemon.get_status()
    return _ok(data=state.model_dump(mode="json"))


# ── POST /rerun ─────────────────────────────────────────────────

@app.post("/rerun")
async def retroactive_rerun(body: RerunRequest) -> JSONResponse:
    """Trigger retroactive re-runs for false-negative patterns or specific audits.

    If audit_ids are provided, re-runs those specific audits.
    If address + chain provided, re-runs all audits for that contract.
    If pattern_type provided, re-runs audits that had that pattern of FN.
    """
    audit_ids: List[str] = []

    if body.audit_ids:
        audit_ids = body.audit_ids
    elif body.address and body.chain:
        # Find all audits for this contract
        records, _ = pipeline.get_all_records(chain=body.chain)
        audit_ids = [
            r.audit_id for r in records
            if r.address.lower() == body.address.lower()
        ]
    else:
        # Re-run all failed audits by default
        records, _ = pipeline.get_all_records()
        audit_ids = [r.audit_id for r in records if r.state.is_failure]

    if not audit_ids:
        return _err("No matching audits found for re-run", status_code=404)

    # Reset their state to PENDING
    for aid in audit_ids:
        record = pipeline.get_record(aid)
        if record:
            record.state = PipelineState.PENDING
            record.error = None
            record.steps = []
            pipeline.update_record(record)
            # Launch re-run
            asyncio.create_task(pipeline.run(aid))

    logger.info(
        "Retroactive re-run triggered",
        count=len(audit_ids),
        reason=body.reason,
        pattern=body.pattern_type,
    )

    return _ok(
        data={"re_run_audits": audit_ids, "count": len(audit_ids)},
        reason=body.reason,
        pattern=body.pattern_type,
    )


# ── GET /stats ──────────────────────────────────────────────────

@app.get("/stats")
async def get_stats() -> JSONResponse:
    """Get pipeline statistics."""
    stats = pipeline.get_stats()
    return _ok(data=stats.model_dump(mode="json"))


# ── GET /similarity/{contract_id} ──────────────────────────────

@app.get("/similarity/{contract_id}")
async def get_similarity(
    contract_id: str,
    threshold: float = Query(0.7, ge=0.0, le=1.0),
) -> JSONResponse:
    """Find contracts similar to the given contract_id."""
    similar = similarity.find_similar(contract_id, threshold=threshold)
    fp = similarity.get_fingerprint(contract_id)
    return _ok(
        data={
            "contract_id": contract_id,
            "fingerprint": {
                "n_functions": fp.n_functions if fp else None,
                "n_state_vars": fp.n_state_vars if fp else None,
                "source_lines": fp.source_lines if fp else None,
            } if fp else None,
            "similar_contracts": [
                {"contract_id": cid, "score": round(score, 4)}
                for cid, score in similar
            ],
            "cluster": similarity.get_cluster_for(contract_id),
        },
    )


# ── GET /similarity ─────────────────────────────────────────────

@app.get("/similarity")
async def list_similarity_clusters() -> JSONResponse:
    """List all similarity clusters."""
    clusters = similarity.get_clusters()
    return _ok(
        data={
            "n_contracts": similarity.n_contracts,
            "n_clusters": similarity.n_clusters,
            "clusters": clusters,
        }
    )


# ── POST /pipeline/retry/{audit_id} ────────────────────────────

@app.post("/pipeline/retry/{audit_id}")
async def retry_pipeline(audit_id: str) -> JSONResponse:
    """Retry a failed audit from the beginning."""
    record = pipeline.get_record(audit_id)
    if not record:
        return _err(f"Audit not found: {audit_id}", status_code=404)
    if not record.state.is_failure:
        return _err(f"Audit {audit_id} is not in a failed state (current: {record.state.value})")

    record.state = PipelineState.PENDING
    record.error = None
    record.steps = []
    pipeline.update_record(record)
    asyncio.create_task(pipeline.run(audit_id))

    return _ok(data={"audit_id": audit_id, "state": PipelineState.PENDING.value})


# ── GET /resources ──────────────────────────────────────────────

@app.get("/resources")
async def get_resource_status() -> JSONResponse:
    """View current resource usage across tool types."""
    slots = {}
    for tool in ToolType:
        slots[tool.value] = {
            "available": governor.available_slots(tool),
            "max": governor.max_slots(tool),
        }
    return _ok(data=slots)


# ── Run (for dev) ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
        reload=True,
    )
