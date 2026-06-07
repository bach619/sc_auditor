"""Pydantic v2 models for the Vyper Cairo Scanner Service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Finding(BaseModel):
    tool: str
    severity: str = "informational"
    title: str
    description: str = ""
    contract: str | None = None
    line: int | None = None
    line_end: int | None = None
    recommendation: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Meta(BaseModel):
    status: Literal["ok", "error"] = "ok"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class ApiResponse(BaseModel):
    data: Any = None
    meta: Meta = Field(default_factory=Meta)


class HealthData(BaseModel):
    status: str = "ok"
    service: str = "scanner-cairo"
    version: str = "0.1.0"
    detectors_available: int = 0


class CairoScanRequest(BaseModel):
    source_files: dict[str, str]
    contract_name: str = ""
    address: str | None = None
    detectors: list[str] | None = None
    chain: str = "starknet"


class CairoScanResponse(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    detector_results: dict[str, list[Finding]] = Field(default_factory=dict)
    duration_seconds: float = 0.0


class CairoDetector(BaseModel):
    name: str
    description: str
    severity_focus: str
    category: str
