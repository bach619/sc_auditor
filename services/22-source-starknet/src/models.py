"""Pydantic v2 models for the Vyper StarkNet Source Service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class FetchRequest(BaseModel):
    chain: str
    address: str
    contract_name: str = ""


class FetchResult(BaseModel):
    success: bool = False
    contract_name: str = ""
    source_files: dict[str, str] = Field(default_factory=dict)
    compiler_version: str = ""
    abi: list[dict[str, Any]] | None = None
    errors: list[str] = Field(default_factory=list)


class Meta(BaseModel):
    status: Literal["ok", "error"] = "ok"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ApiResponse(BaseModel):
    data: Any = None
    meta: Meta = Field(default_factory=Meta)


class HealthData(BaseModel):
    status: str = "ok"
    service: str = "starknet-source"
    version: str = "0.1.0"
    sources_cached: int = 0
