"""Pydantic models for the Vyper Config Service.

All request/response models follow the Vyper standard format:
  {"data": ..., "meta": {"status": "ok", "timestamp": "..."}}
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ConfigValue(BaseModel):
    """Request body for PUT /config/{key}.

    Attributes:
        value: The configuration value (any JSON-serializable type).
    """

    model_config = {"strict": True, "extra": "forbid"}

    value: Any


class BulkConfig(BaseModel):
    """Request body for PUT /config/bulk.

    Attributes:
        config: A dictionary of key-value pairs to upsert.
    """

    model_config = {"strict": True, "extra": "forbid"}

    config: dict[str, Any]


class Meta(BaseModel):
    """Standard response metadata.

    Attributes:
        status: Response status indicator ("ok" or "error").
        timestamp: ISO-8601 timestamp of the response.
    """

    status: Literal["ok", "error"] = "ok"
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class ConfigResponse(BaseModel):
    """Standard Vyper API response envelope.

    Attributes:
        data: The response payload.
        meta: Response metadata including status and timestamp.
    """

    data: Any
    meta: Meta = Field(default_factory=Meta)


class ErrorResponse(BaseModel):
    """Error response envelope.

    Attributes:
        data: Null in error responses.
        meta: Response metadata with status set to "error".
    """

    data: None = None
    meta: Meta


class HealthResponse(BaseModel):
    """Response model for the health check endpoint.

    Attributes:
        status: Service health status ("ok").
        service: Service name ("config").
        version: Service version string.
        timestamp: ISO-8601 timestamp of the health check.
    """

    status: str = "ok"
    service: str = "config"
    version: str = "0.1.0"
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
