"""Vyper Reporter Service — FastAPI microservice for audit report generation.

Generates two types of Markdown reports from classified findings and exploit
results:

1. **immunefi.md** — TP-only findings formatted for Immunefi bug bounty
   submission. Includes Proofs of Concept from the Exploit Service.

2. **full.md** — Comprehensive report with all findings, performance metrics,
   ASCII severity charts, tool breakdowns, file statistics, and appendices.

Port: 8007
"""

from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator

from shared.observability import setup_observability
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from src.full import FullReportGenerator
from src.immunefi import ImmunefiReportGenerator
from src.models import (
    ApiResponse,
    ExploitResult,
    Finding,
    HealthData,
    Meta,
    ReportContent,
    ReportRequest,
    ReportResponse,
    SourceInfo,
)






# ── Constants ──────────────────────────────────────────────

SERVICE_NAME = "reporter"
SERVICE_VERSION = "0.1.0"
DATA_DIR = Path("/data/reporter")
REPORTS_DIR = DATA_DIR / "reports"

# ── Global state ───────────────────────────────────────────


class AppState:
    """Shared application state injected via ``request.app.state.vyper``.

    Attributes:
        immunefi_gen: Immunefi report generator instance.
        full_gen: Full report generator instance.
    """

    def __init__(self) -> None:
        self.immunefi_gen: ImmunefiReportGenerator = ImmunefiReportGenerator()
        self.full_gen: FullReportGenerator = FullReportGenerator()
        self._shutdown_requested: bool = False

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def request_shutdown(self) -> None:
        self._shutdown_requested = True


def _get_state(request: Request) -> AppState:
    """Get the application state from the request.

    Args:
        request: The FastAPI incoming request.

    Returns:
        The shared application state instance.
    """
    return request.app.state.vyper  # type: ignore[no-any-return]


# ── Lifespan ───────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: create data directories and initialise generators.
    Shutdown: log clean exit.
    """
    state = AppState()
    app.state.vyper = state

    # Create data directories, but skip if permission denied (volume mount issue)
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        log.warning("data_dir.permission_denied", path=str(DATA_DIR))

    log.info(
        "reporter.startup",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        reports_dir=str(REPORTS_DIR),
    )

    yield

    log.info("reporter.shutdown", service=SERVICE_NAME)


# ── App Factory ────────────────────────────────────────────

app = FastAPI(
    title="Vyper Reporter Service",
    description=(
        "Generates Markdown audit reports from classified findings and "
        "exploit results. Produces both Immunefi-compatible submission "
        "reports (TP-only) and comprehensive full reports."
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


log = setup_observability(app, "09-reporter", "0.1.0")

# ── Helper ─────────────────────────────────────────────────


def ok(data: object = None) -> ApiResponse:
    """Build a standard Vyper success response.

    Args:
        data: Response payload.

    Returns:
        ``ApiResponse`` with status ``"ok"``.
    """
    return ApiResponse(data=data, meta=Meta(status="ok"))


def err(detail: str, status_code: int = 400) -> HTTPException:
    """Build a standard Vyper error response.

    Args:
        detail: Human-readable error description.
        status_code: HTTP status code (default 400).

    Returns:
        ``HTTPException`` with the given status and detail.
    """
    return HTTPException(
        status_code=status_code,
        detail=detail,
    )


def _get_report_dir(audit_id: str) -> Path:
    """Get the report directory for a given audit.

    Args:
        audit_id: Audit session identifier.

    Returns:
        Path to the report directory.
    """
    return REPORTS_DIR / audit_id


def _report_exists(audit_id: str, filename: str) -> bool:
    """Check whether a specific report file exists on disk.

    Args:
        audit_id: Audit session identifier.
        filename: Report filename (e.g. ``"immunefi.md"``).

    Returns:
        ``True`` if the file exists and is non-empty.
    """
    path = _get_report_dir(audit_id) / filename
    return path.exists() and path.stat().st_size > 0


def _read_report(audit_id: str, filename: str) -> str:
    """Read a report file from disk.

    Args:
        audit_id: Audit session identifier.
        filename: Report filename.

    Returns:
        Full text content of the report.

    Raises:
        HTTPException 404: If the report does not exist.
    """
    path = _get_report_dir(audit_id) / filename
    if not path.exists():
        raise err(f"Report not found: {audit_id}/{filename}", status_code=404)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        log.error("report.read_failed", path=str(path), error=str(exc))
        raise err("Failed to read report", status_code=500)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health(request: Request) -> ApiResponse:
    """Health check endpoint.

    Returns service status, version, and statistics about stored reports.
    """
    # Compute report statistics
    reports_count = 0
    reports_size = 0
    if REPORTS_DIR.exists():
        for report_file in REPORTS_DIR.rglob("*.md"):
            reports_count += 1
            reports_size += report_file.stat().st_size

    return ok(
        HealthData(
            status="ok",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
            reports_count=reports_count,
            reports_size=reports_size,
        )
    )


@app.post("/report")
async def generate_report(body: ReportRequest, request: Request) -> ApiResponse:
    """Generate both Immunefi and full audit reports for a completed audit.

    Accepts classified findings, metrics, and exploit results, then
    generates two Markdown reports:

    - ``immunefi.md`` — TP-only findings with PoCs for Immunefi submission.
    - ``full.md`` — All findings with metrics, charts, and appendices.

    **Request body**::

        {
            "audit_id": "aud_abc123",
            "program": "ethena",
            "chain": "ethereum",
            "address": "0x4c9edd...",
            "findings": [...],
            "metrics": {"tp": 2, "fp": 1, ...},
            "exploit_results": [...],
            "source_info": {...}
        }

    Returns paths to both generated reports.
    """
    state = _get_state(request)

    log.info(
        "report.generate.start",
        audit_id=body.audit_id,
        program=body.program,
        findings=len(body.findings),
        exploit_results=len(body.exploit_results),
    )

    try:
        # Generate Immunefi report (TP-only)
        immunefi_content = state.immunefi_gen.generate(
            audit_id=body.audit_id,
            program=body.program,
            chain=body.chain,
            address=body.address,
            findings=body.findings,
            exploit_results=body.exploit_results,
        )

        # Generate full report (all findings)
        full_content = state.full_gen.generate(
            audit_id=body.audit_id,
            program=body.program,
            chain=body.chain,
            address=body.address,
            findings=body.findings,
            metrics=body.metrics,
            exploit_results=body.exploit_results,
            source_info=body.source_info,
        )

        report_dir = _get_report_dir(body.audit_id)
        response = ReportResponse(
            audit_id=body.audit_id,
            immunefi_path=str(report_dir / "immunefi.md"),
            full_path=str(report_dir / "full.md"),
        )

        log.info(
            "report.generate.complete",
            audit_id=body.audit_id,
            immunefi_size=len(immunefi_content),
            full_size=len(full_content),
        )

        return ok(response)

    except Exception as exc:
        log.exception(
            "report.generate.failed",
            audit_id=body.audit_id,
            error=str(exc),
        )
        raise err(f"Report generation failed: {exc}", status_code=500)


@app.get("/report/{audit_id}")
async def get_audit_reports(audit_id: str) -> ApiResponse:
    """Get status and availability of both reports for an audit.

    Args:
        audit_id: Audit session identifier.

    Returns:
        Object indicating which reports are available.
    """
    report_dir = _get_report_dir(audit_id)
    if not report_dir.exists():
        raise err(f"No reports found for audit: {audit_id}", status_code=404)

    immunefi_available = _report_exists(audit_id, "immunefi.md")
    full_available = _report_exists(audit_id, "full.md")

    if not immunefi_available and not full_available:
        raise err(f"No reports found for audit: {audit_id}", status_code=404)

    return ok(
        {
            "audit_id": audit_id,
            "immunefi_available": immunefi_available,
            "full_available": full_available,
            "immunefi_path": str(report_dir / "immunefi.md"),
            "full_path": str(report_dir / "full.md"),
        }
    )


@app.get("/report/{audit_id}/immunefi")
async def get_immunefi_report(audit_id: str) -> ApiResponse:
    """Get the Immunefi submission report content.

    Args:
        audit_id: Audit session identifier.

    Returns:
        Full Markdown content of the Immunefi report.
    """
    content = _read_report(audit_id, "immunefi.md")
    report_dir = _get_report_dir(audit_id)

    return ok(
        ReportContent(
            audit_id=audit_id,
            report_type="immunefi",
            content=content,
            path=str(report_dir / "immunefi.md"),
        )
    )


@app.get("/report/{audit_id}/full")
async def get_full_report(audit_id: str) -> ApiResponse:
    """Get the full comprehensive audit report content.

    Args:
        audit_id: Audit session identifier.

    Returns:
        Full Markdown content of the comprehensive report.
    """
    content = _read_report(audit_id, "full.md")
    report_dir = _get_report_dir(audit_id)

    return ok(
        ReportContent(
            audit_id=audit_id,
            report_type="full",
            content=content,
            path=str(report_dir / "full.md"),
        )
    )


# ── Entry Point ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8007,
        log_level="info",
        reload=False,
    )
