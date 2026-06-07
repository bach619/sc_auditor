"""Pydantic v2 models for the Vyper Notifier Service.

All request/response models follow the Vyper standard envelope:
  {"data": ..., "meta": {"status": "ok", "timestamp": "..."}}
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ── Notify Request ──────────────────────────────────────────


class NotifyRequest(BaseModel):
    """Request body for POST /notify.

    Attributes:
        type: Notification type (audit_complete, error, test).
        channel: Target delivery channel (discord, telegram, email, desktop, all).
        audit_id: Unique identifier for the audit session.
        findings_count: Total number of findings detected.
        critical_count: Count of critical-severity findings.
        high_count: Count of high-severity findings.
        summary: Human-readable summary of the audit result.
        report_url: URL to the full audit report.
        program: Name of the audited program / project.
        chain: Blockchain name (ethereum, polygon, etc.).
        address: Contract address that was audited.
    """

    type: str = "audit_complete"
    channel: str = "all"
    audit_id: str = ""
    findings_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    summary: str = ""
    report_url: str | None = None
    program: str | None = None
    chain: str | None = None
    address: str | None = None


# ── Test Request ────────────────────────────────────────────


class TestRequest(BaseModel):
    """Request body for POST /test.

    Attributes:
        channels: List of channels to test. Defaults to all configured.
    """

    channels: list[str] | None = None
    message: str = "Vyper Notifier Test — this is a test message."


# ── Delivery Results ────────────────────────────────────────


class DeliveryResult(BaseModel):
    """Result of delivering a notification through a single channel.

    Attributes:
        channel: The delivery channel name.
        success: Whether delivery succeeded.
        timestamp: ISO-8601 timestamp of the delivery attempt.
        error: Error message if delivery failed.
        message_id: Optional provider-specific message identifier.
    """

    channel: str
    success: bool = True
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    error: str | None = None
    message_id: str | None = None


class BatchDeliveryResult(BaseModel):
    """Aggregated result of delivering a notification across multiple channels.

    Attributes:
        audit_id: The associated audit identifier.
        request_type: Type of notification that was sent.
        deliveries: List of per-channel delivery results.
        all_succeeded: Whether every channel delivered successfully.
    """

    audit_id: str = ""
    request_type: str = ""
    deliveries: list[DeliveryResult] = Field(default_factory=list)
    all_succeeded: bool = True


# ── Channel Config ──────────────────────────────────────────


class ChannelConfig(BaseModel):
    """Describes a single notification channel and its state.

    Attributes:
        name: Unique channel identifier (discord, telegram, email, desktop).
        enabled: Whether this channel is configured and active.
        type: Channel type (webhook, bot_api, smtp, native).
        description: Human-readable description of this channel.
    """

    name: str
    enabled: bool = False
    type: str = "webhook"
    description: str = ""


# ── Delivery Log ────────────────────────────────────────────


class DeliveryLogEntry(BaseModel):
    """A single entry in the delivery history log.

    Attributes:
        timestamp: When the delivery was attempted.
        channel: Delivery channel used.
        success: Whether it succeeded.
        request_type: Type of notification sent.
        audit_id: Associated audit identifier.
        error: Error message if delivery failed.
    """

    timestamp: str
    channel: str
    success: bool
    request_type: str = ""
    audit_id: str = ""
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


# ── Health ───────────────────────────────────────────────────


class HealthData(BaseModel):
    """Health check response data."""

    status: str = "ok"
    service: str = "notifier"
    version: str = "0.1.0"
    channels_available: int = 0
    channels_enabled: list[str] = Field(default_factory=list)
