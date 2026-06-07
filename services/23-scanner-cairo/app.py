"""Vyper Cairo Scanner Service — FastAPI microservice for Cairo smart contract analysis.

Analyzes Cairo contracts for vulnerabilities using pattern-based detectors.
Port: 8027 | Version: 0.1.0
"""

from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from shared.observability import setup_observability
from shared.api_errors import register_error_handlers
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from src.adapter import CairoAdapter
from src.models import (
    ApiResponse,
    CairoDetector,
    CairoScanRequest,
    CairoScanResponse,
    Finding,
    HealthData,
    Meta,
)
from src.storage import CairoScanStorage

SERVICE_NAME = "23-scanner-cairo"
SERVICE_VERSION = "0.1.0"

adapter = CairoAdapter()
storage = CairoScanStorage()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    log.info("cairo_scanner.startup", service=SERVICE_NAME, version=SERVICE_VERSION)
    from shared.storage import init_sqlite_store; init_sqlite_store("/data/scanner-cairo")
    detectors = await adapter.get_detectors()
    log.info("cairo_scanner.detectors_loaded", count=len(detectors), detectors=detectors)
    yield
    log.info("cairo_scanner.shutdown", service=SERVICE_NAME)


app = FastAPI(
    title="Vyper Cairo Scanner Service",
    description="Analyzes Cairo smart contracts for security vulnerabilities.",
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

log = setup_observability(app, "23-scanner-cairo", "0.1.0")


def ok(data: object = None) -> ApiResponse:
    return ApiResponse(data=data, meta=Meta(status="ok"))


def err(detail: str, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


@app.get("/health")
async def health() -> ApiResponse:
    detectors = await adapter.get_detectors()
    return ok(
        HealthData(
            status="ok",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
            detectors_available=len(detectors),
        )
    )


@app.post("/scan")
async def scan_contract(body: CairoScanRequest) -> ApiResponse:
    if not body.source_files:
        raise err("source_files is required")

    log.info("cairo.scan_requested", contract=body.contract_name, files=len(body.source_files))

    start_time = time.monotonic()

    from vyper_lib.models.chain_adapter import ContractSource
    source = ContractSource(
        chain="starknet",
        language="cairo",
        address=body.address,
        name=body.contract_name,
        source_files=body.source_files,
    )

    parsed = await adapter.parse(source)
    ir = await adapter.to_ir(parsed, source)
    analysis = await adapter.analyze(ir, body.detectors or [])

    duration = round(time.monotonic() - start_time, 3)

    findings = [Finding(**f) for f in analysis.get("findings", [])]
    detector_results: dict[str, list[Finding]] = {}
    for det_name, det_findings in analysis.get("detector_results", {}).items():
        detector_results[det_name] = [Finding(**f) for f in det_findings]

    critical = sum(1 for f in findings if f.severity == "critical")
    high = sum(1 for f in findings if f.severity == "high")
    medium = sum(1 for f in findings if f.severity == "medium")
    low = sum(1 for f in findings if f.severity == "low")

    log.info(
        "cairo.scan_complete",
        contract=body.contract_name,
        total_findings=len(findings),
        critical=critical,
        high=high,
        medium=medium,
        low=low,
        duration=duration,
    )

    result = CairoScanResponse(
        findings=findings,
        detector_results=detector_results,
        duration_seconds=duration,
    )

    request_id = uuid.uuid4().hex[:12]
    storage.save_scan_result(request_id, result)

    return ok({
        "request_id": request_id,
        "contract_name": body.contract_name,
        "total_findings": len(findings),
        "severity_counts": {
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
        },
        "detectors_run": list(detector_results.keys()),
        "duration_seconds": duration,
        "findings": [f.model_dump() for f in findings],
        "detector_results": {
            k: [f.model_dump() for f in v]
            for k, v in detector_results.items()
        },
    })


@app.get("/detectors")
async def list_detectors() -> ApiResponse:
    from src.detectors import DETECTOR_REGISTRY

    detectors = []
    for name, detector in DETECTOR_REGISTRY.items():
        detectors.append(
            CairoDetector(
                name=name,
                description=detector.description,
                severity_focus=detector.severity_focus,
                category=detector.category,
            )
        )

    return ok({
        "total": len(detectors),
        "detectors": [d.model_dump() for d in detectors],
    })


@app.get("/scan/{request_id}")
async def get_scan_result(request_id: str) -> ApiResponse:
    result = storage.load_scan_result(request_id)
    if not result:
        raise err(f"Scan result {request_id} not found", status_code=404)
    return ok(result)
