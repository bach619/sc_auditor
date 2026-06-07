"""Pydantic models for Vyper Webhook Service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Meta(BaseModel):
    """Standard Vyper response metadata."""

    status: Literal["ok", "error"] = "ok"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class ApiResponse(BaseModel):
    """Standard Vyper API response envelope."""

    data: Any = None
    meta: Meta = Field(default_factory=Meta)


class HealthData(BaseModel):
    """Health check response payload."""

    status: str = "ok"
    service: str = "webhook"
    version: str = "0.1.0"
    uptime_seconds: float = 0.0
    delivery_count: int = 0
    failed_count: int = 0
    configured_endpoints: int = 0


class WebhookTrigger(BaseModel):
    """Request body for POST /webhook/trigger."""

    event: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Event name, e.g. audit_complete, critical_finding, daemon_status",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary JSON payload to deliver",
    )
    urls: list[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of target webhook URLs",
    )
    secret: str = Field(
        ...,
        min_length=1,
        description="HMAC-SHA256 secret shared with the receiving endpoint",
    )


class WebhookResult(BaseModel):
    """Result of delivering a webhook to a single URL."""

    url: str
    success: bool
    status_code: int | None = None
    duration_ms: float = 0.0
    error: str | None = None


class BatchDeliveryResult(BaseModel):
    """Aggregated result of delivering to all URLs."""

    event: str
    total_urls: int
    succeeded: int = 0
    failed: int = 0
    results: list[WebhookResult] = Field(default_factory=list)


class DeliveryLogEntry(BaseModel):
    """A single delivery event persisted to disk."""

    timestamp: str
    url: str
    event: str
    success: bool
    status_code: int | None = None
    duration_ms: float = 0.0
    error: str | None = None


class EndpointInfo(BaseModel):
    """Information about a configured webhook endpoint (derived from config)."""

    url: str
    label: str | None = None
    events: list[str] | None = None
    last_delivery_ts: str | None = None
    last_delivery_ok: bool | None = None


class DeliveryLogQuery(BaseModel):
    """Query parameters for GET /webhook/delivery-log."""

    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    event: str | None = Field(default=None, description="Filter by event type")
    success: bool | None = Field(default=None, description="Filter by success/failure")
