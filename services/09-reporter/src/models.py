"""Pydantic v2 models for the Vyper Reporter Service.

All request/response models follow the Vyper standard envelope:
  {"data": ..., "meta": {"status": "ok", "timestamp": "..."}}

Reports are generated from classified findings and exploit results.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ── Findings (subset of scanner model) ────────────────────────


class Finding(BaseModel):
    """A single finding for use in report generation.

    Attributes:
        id: Finding identifier (e.g. "F-001").
        tool: Tool that produced the finding.
        severity: Severity level.
        title: Short finding title.
        description: Detailed description.
        contract: Contract file path.
        line: Starting line number.
        recommendation: Fix recommendation.
        swc_id: SWC classification identifier.
        classification: TP / FP / TN / FN.
        confidence: Classification confidence 0.0–1.0.
        ai_reasoning: AI reasoning for the verdict.
        exploit_confirmed: Whether exploit was verified.
        code_context: Source code snippet.
    """

    id: str = ""
    tool: str = ""
    severity: str = "informational"
    title: str = ""
    description: str = ""
    contract: str | None = None
    line: int | None = None
    recommendation: str | None = None
    swc_id: str | None = None
    classification: str = "true_positive"
    confidence: float | None = None
    ai_reasoning: str | None = None
    exploit_confirmed: bool = False
    code_context: str | None = None


# ── Metrics ───────────────────────────────────────────────────


class Metrics(BaseModel):
    """Audit performance metrics.

    Attributes:
        tp: True positive count.
        fp: False positive count.
        tn: True negative count.
        fn: False negative count.
        precision: TP / (TP + FP).
        recall: TP / (TP + FN).
        f1_score: Harmonic mean of precision and recall.
        overall_score: Aggregated quality score (0–10).
    """

    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    overall_score: float = 0.0


class ToolMetrics(BaseModel):
    """Per-tool performance breakdown.

    Attributes:
        tool: Tool name.
        tp: True positives found by this tool.
        fp: False positives from this tool.
        precision: Tool-specific precision.
    """

    tool: str
    tp: int = 0
    fp: int = 0
    precision: float = 0.0


# ── Exploit Results ───────────────────────────────────────────


class ExploitResult(BaseModel):
    """Result from the Exploit Service for a single finding.

    Attributes:
        finding_id: Finding identifier.
        success: Whether the exploit was successfully executed.
        poc_script: PoC Solidity script content.
        tx_hash: Transaction hash of the exploit tx.
        gas_used: Gas consumed by the exploit.
        value_at_risk: Estimated value at risk (USD).
        exploit_contract: Deployed exploit contract address.
        call_sequence: Human-readable call sequence.
    """

    finding_id: str = ""
    success: bool = False
    poc_script: str | None = None
    tx_hash: str | None = None
    gas_used: int | None = None
    value_at_risk: float | None = None
    exploit_contract: str | None = None
    call_sequence: list[str] | None = None


# ── Source Info (for full report) ─────────────────────────────


class SourceInfo(BaseModel):
    """Information about the audited source code.

    Attributes:
        provider: Source provider (github, sourcify, etherscan).
        files: List of source file paths.
        file_count: Total number of files.
        lines_of_code: Total lines of code.
        has_tests: Whether the repo includes tests.
        has_foundry: Whether Foundry is configured.
        is_full_repo: Whether the full repo was fetched.
        compiler_versions: Solidity compiler versions found.
    """

    provider: str = ""
    files: list[str] = Field(default_factory=list)
    file_count: int = 0
    lines_of_code: int = 0
    has_tests: bool = False
    has_foundry: bool = False
    is_full_repo: bool = False
    compiler_versions: list[str] = Field(default_factory=list)


# ── Requests ──────────────────────────────────────────────────


class ReportRequest(BaseModel):
    """Request body for POST /report.

    Attributes:
        audit_id: Audit session identifier.
        program: Immunefi program name (e.g. "ethena").
        chain: Blockchain name (e.g. "ethereum").
        address: Contract address being audited.
        findings: All classified findings.
        metrics: Audit performance metrics.
        exploit_results: Results from Exploit Service (optional).
        source_info: Source code metadata (optional, for full report).
    """

    audit_id: str
    program: str = ""
    chain: str = ""
    address: str = ""
    findings: list[Finding] = Field(default_factory=list)
    metrics: Metrics | None = None
    exploit_results: list[ExploitResult] = Field(default_factory=list)
    source_info: SourceInfo | None = None


# ── Responses ─────────────────────────────────────────────────


class ReportResponse(BaseModel):
    """Response from report generation.

    Attributes:
        audit_id: Audit identifier.
        immunefi_path: Path to the Immunefi submission report.
        full_path: Path to the full comprehensive report.
        generated_at: ISO-8601 timestamp of generation.
    """

    audit_id: str
    immunefi_path: str = ""
    full_path: str = ""
    generated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class ReportContent(BaseModel):
    """Content of a generated report.

    Attributes:
        audit_id: Audit identifier.
        report_type: Type of report ("immunefi" or "full").
        content: Full Markdown content of the report.
        path: File path to the saved report.
    """

    audit_id: str
    report_type: str
    content: str
    path: str


# ── Health ────────────────────────────────────────────────────


class HealthData(BaseModel):
    """Health check response data.

    Attributes:
        status: Service health status.
        service: Service name.
        version: Service version.
        reports_count: Number of stored reports.
        reports_size: Total size of report data in bytes.
    """

    status: str = "ok"
    service: str = "reporter"
    version: str = "0.1.0"
    reports_count: int = 0
    reports_size: int = 0


# ── API Envelope ──────────────────────────────────────────────


class Meta(BaseModel):
    """Standard response metadata.

    Attributes:
        status: Response status indicator ("ok" or "error").
        timestamp: ISO-8601 timestamp of the response.
    """

    status: Literal["ok", "error"] = "ok"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class ApiResponse(BaseModel):
    """Standard Vyper API response envelope.

    Attributes:
        data: The response payload.
        meta: Response metadata including status and timestamp.
    """

    data: Any = None
    meta: Meta = Field(default_factory=Meta)
