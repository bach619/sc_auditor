"""Pydantic v2 models shared across all Vyper services.

All request/response models follow the Vyper standard envelope:
  {"data": ..., "meta": {"status": "ok", "timestamp": "..."}}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Finding ─────────────────────────────────────────────────


class Finding(BaseModel):
    """A single finding from a security analysis tool.

    Attributes:
        tool: The tool that produced this finding (slither, mythril, echidna).
        severity: Severity level (critical, high, medium, low, informational).
        title: Short title of the finding.
        description: Detailed description of the vulnerability.
        contract: Contract file path where the finding was detected.
        line: Starting line number in the source file.
        line_end: Ending line number (if multi-line).
        recommendation: Suggested fix or mitigation.
        swc_id: Smart Contract Weakness Classification identifier.
        function: Function name (Mythril/Echidna).
        test_function: Echidna test function that triggered the finding.
        failing_input: Echidna fuzzing input that caused the failure.
        confidence: Confidence score 0.0–1.0 (Slither).
    """

    tool: str
    severity: str = "informational"
    title: str
    description: str = ""
    contract: str | None = None
    line: int | None = None
    line_end: int | None = None
    recommendation: str | None = None
    swc_id: str | None = None
    function: str | None = None
    test_function: str | None = None
    failing_input: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Scanners ─────────────────────────────────────────────────


class ToolResult(BaseModel):
    """Output from running a single tool.

    Attributes:
        tool: Tool name.
        success: Whether the tool ran without errors.
        findings: List of findings detected.
        raw_output: Full stdout from the tool.
        error: Error message if the tool failed.
        duration_seconds: Wall-clock duration of the run.
    """

    tool: str
    success: bool = True
    findings: list[Finding] = Field(default_factory=list)
    raw_output: str = ""
    error: str | None = None
    duration_seconds: float = 0.0
    coverage: dict[str, Any] | None = None


class ForgeResult(BaseModel):
    """Result from the Foundry Forge build step.

    Attributes:
        success: Whether compilation succeeded.
        errors: List of compiler error messages.
        warnings: List of compiler warnings.
        compiler_version: Solidity compiler version used.
    """

    success: bool = True
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    compiler_version: str | None = None


# ── Requests ─────────────────────────────────────────────────


class ScanRequest(BaseModel):
    """Request body for POST /scan (used by Slither, Echidna, Mythril).

    Attributes:
        chain: Blockchain name (e.g. "ethereum", "polygon").
        address: Contract address being scanned.
        sources: Dict mapping file path → source code.
        compiler: Solidity compiler version (e.g. "0.8.20").
        config_tier: Slither config preset ("strict", "default", "noisy").
        timeout: Tool-specific timeout in seconds.
        contract_name: Primary contract name for Echidna.
    """

    chain: str
    address: str
    sources: dict[str, str]
    compiler: str = "0.8.20"
    config_tier: str = "default"
    timeout: int = 600
    contract_name: str | None = None


class BuildRequest(BaseModel):
    """Request body for POST /build (Forge-specific).

    Attributes:
        chain: Blockchain name.
        address: Contract address.
        sources: Dict mapping file path → source code.
        compiler: Solidity compiler version.
        timeout: Build timeout in seconds.
    """

    chain: str
    address: str
    sources: dict[str, str]
    compiler: str = "0.8.20"
    timeout: int = 300


# ── Responses ────────────────────────────────────────────────


class ScanResponse(BaseModel):
    """Response from a completed scan.

    Attributes:
        audit_id: Unique identifier for this scan session.
        contract_address: Address of the scanned contract.
        chain: Blockchain name.
        compiler: Solidity compiler version used.
        forge: Forge compilation result (only for forge service).
        tools: List of tool results.
        all_findings: Flat list of all findings across tools.
        total_findings: Total number of findings.
        critical_count: Count of critical-severity findings.
        high_count: Count of high-severity findings.
        duration_seconds: Total scan duration.
    """

    audit_id: str = ""
    contract_address: str
    chain: str
    compiler: str
    forge: ForgeResult | None = None
    tools: list[ToolResult] = Field(default_factory=list)
    all_findings: list[Finding] = Field(default_factory=list)
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    duration_seconds: float = 0.0
    contract_type: str = "Unknown"


class ToolInfo(BaseModel):
    """Information about an available analysis tool.

    Attributes:
        name: Tool name.
        version: Installed version string.
        available: Whether the tool is installed and executable.
        type: Tool type (static, symbolic, fuzzer, compiler).
    """

    name: str
    version: str | None = None
    available: bool = False
    type: str = "static"


class InstallResult(BaseModel):
    """Result of a tool install/update operation.

    Attributes:
        tool: Tool name.
        success: Whether installation succeeded.
        version: Installed version.
        error: Error message if installation failed.
    """

    tool: str
    success: bool = True
    version: str | None = None
    error: str | None = None


# ── API Envelope ─────────────────────────────────────────────


class Meta(BaseModel):
    """Standard response metadata.

    Attributes:
        status: Response status indicator ("ok" or "error").
        timestamp: ISO-8601 timestamp of the response.
    """

    status: Literal["ok", "error"] = "ok"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ApiResponse(BaseModel):
    """Standard Vyper API response envelope.

    Attributes:
        data: The response payload.
        meta: Response metadata including status and timestamp.
    """

    data: Any = None
    meta: Meta = Field(default_factory=Meta)


# ── Health ───────────────────────────────────────────────────


class HealthData(BaseModel):
    """Health check response data."""

    status: str = "ok"
    service: str = ""
    version: str = "0.1.0"
    tools_available: int = 0
    tools_installed: list[str] = Field(default_factory=list)
    solc_versions: list[str] = Field(default_factory=list)


# ── Legacy vyper_lib models ──────────────────────────────────


class HealthResponse(BaseModel):
    """Simple health response (backward compat)."""

    status: str = "ok"
    service: str = ""
    version: str = "0.1.0"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: str | None = None
    code: str = "internal_error"
