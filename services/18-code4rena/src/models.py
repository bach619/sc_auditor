"""Pydantic v2 models for Code4rena Service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from vyper_lib.models import ApiResponse, HealthData, Meta

__all__ = [
    "ApiResponse",
    "Contest",
    "ContestScope",
    "HealthData",
    "Meta",
    "SyncStatus",
]


class Contest(BaseModel):
    """A single Code4rena audit contest."""

    id: str
    title: str = ""
    description: str = ""
    status: str = "upcoming"
    start_date: str = ""
    end_date: str = ""
    total_pool_usd: float = 0.0
    platform_id: str = ""


class ContestScope(BaseModel):
    """Scope details for a contest."""

    contest_id: str
    contracts: list[dict[str, Any]] = Field(default_factory=list)
    repos: list[str] = Field(default_factory=list)


class SyncStatus(BaseModel):
    """Status of a sync operation."""

    sync_id: str
    status: str = "pending"
    started_at: str | None = None
    completed_at: str | None = None
    contests_fetched: int = 0
    contests_new: int = 0
    contests_updated: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
