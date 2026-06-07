"""Pydantic models for the Vyper AI Service.

All request/response models follow the Vyper standard format:
  {"data": ..., "meta": {"status": "ok", "timestamp": "..."}}
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ── Enums / Literals ──────────────────────────────────────

Severity = Literal["critical", "high", "medium", "low", "informational"]
Verdict = Literal["true_positive", "false_positive"]
Provider = Literal["openai", "anthropic", "openrouter", "huggingface"]


# ── Findings ──────────────────────────────────────────────


class Finding(BaseModel):
    """A single scanner finding to be analyzed.

    Attributes:
        id: Unique identifier for this finding (e.g. "REENT-001").
        tool: The scanner that produced this finding (e.g. "slither").
        title: Short description of the finding.
        description: Detailed explanation of the issue.
        severity: Severity assigned by the scanner (may differ from AI).
        location: Source location (file, line number, code snippet).
    """

    id: str
    tool: str
    title: str
    description: str
    severity: str | None = None
    location: dict[str, Any] | None = None


class AnalyzedFinding(BaseModel):
    """A finding enriched by AI analysis.

    Attributes:
        id: Original finding identifier.
        tool: Original scanner tool.
        title: Original finding title.
        description: Original finding description.
        ai_verdict: AI's True Positive / False Positive classification.
        ai_confidence: Confidence score 0.0–1.0.
        ai_severity: AI-assessed severity (may differ from scanner).
        ai_reasoning: Detailed reasoning from the AI.
        suggested_fix: Fix recommendation code / explanation (if TP).
        scanner_severity: Severity originally assigned by the scanner.
        location: Source location information.
    """

    id: str
    tool: str
    title: str
    description: str
    ai_verdict: Verdict
    ai_confidence: float = Field(ge=0.0, le=1.0)
    ai_severity: Severity
    ai_reasoning: str
    suggested_fix: str | None = None
    scanner_severity: str | None = None
    location: dict[str, Any] | None = None


class FixSuggestion(BaseModel):
    """Fix suggestion from the AI.

    Attributes:
        finding_id: Original finding identifier.
        fix_code: The suggested code fix (diff or full replacement).
        explanation: Why this fix addresses the vulnerability.
        gas_impact: Estimated gas impact (e.g. "+500 gas").
        breaking_changes: Whether this fix changes the contract interface.
    """

    finding_id: str
    fix_code: str
    explanation: str
    gas_impact: str | None = None
    breaking_changes: bool = False


# ── AI LLM Response ───────────────────────────────────────


class LlmAnalysis(BaseModel):
    """Structured output parsed from the LLM response.

    The LLM is instructed to return a JSON object matching this shape.

    Attributes:
        verdict: True Positive or False Positive.
        confidence: Confidence in the verdict (0.0–1.0).
        severity: Assessed severity level.
        reasoning: Step-by-step reasoning for the verdict.
        suggested_fix: Code or explanation for fixing the issue (if TP).
    """

    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    severity: Severity
    reasoning: str
    suggested_fix: str | None = None


# ── API Request Bodies ────────────────────────────────────


class AnalyzeRequest(BaseModel):
    """Request body for POST /analyze.

    Attributes:
        audit_id: Unique identifier for the audit session.
        source: Dictionary mapping file names to source code.
        findings: List of scanner findings to analyze.
        compiler: Solidity compiler version (e.g. "0.8.20").
        contract_name: Name of the contract being analyzed.
    """

    audit_id: str
    source: dict[str, str]
    findings: list[Finding]
    compiler: str | None = None
    contract_name: str | None = None


class FixSuggestionRequest(BaseModel):
    """Request body for POST /fix-suggestion.

    Attributes:
        source: Dictionary mapping file names to source code.
        finding: The finding to generate a fix for.
        compiler: Solidity compiler version.
    """

    source: dict[str, str]
    finding: Finding
    compiler: str | None = None


# ── API Response Envelope ─────────────────────────────────


class Meta(BaseModel):
    """Standard response metadata.

    Attributes:
        status: Response status indicator ("ok" or "error").
        timestamp: ISO-8601 timestamp of the response.
        error: Optional error detail when status is "error".
    """

    status: Literal["ok", "error"] = "ok"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    error: str | None = None


class ApiResponse(BaseModel):
    """Standard Vyper API response envelope.

    Attributes:
        data: The response payload.
        meta: Response metadata including status and timestamp.
    """

    data: Any = None
    meta: Meta = Field(default_factory=Meta)


class ErrorResponse(BaseModel):
    """Error response envelope.

    Attributes:
        data: Null in error responses.
        meta: Response metadata with status set to "error".
    """

    data: None = None
    meta: Meta


# ── Health ─────────────────────────────────────────────────


class HealthData(BaseModel):
    """Health check response data.

    Attributes:
        status: Service health status.
        service: Service name.
        version: Service version.
        provider: Active AI provider (openai, anthropic, openrouter, or huggingface).
        model: Active model name.
        cache_entries: Number of cached analysis results.
    """

    status: str = "ok"
    service: str = "ai"
    version: str = "0.1.0"
    provider: str | None = None
    model: str | None = None
    cache_entries: int = 0
