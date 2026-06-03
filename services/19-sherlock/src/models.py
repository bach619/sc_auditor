"""Pydantic v2 models for Sherlock Service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from vyper_lib.models import ApiResponse, HealthData, Meta


class ContractRef(BaseModel):
    """Reference to a smart contract in contest scope."""
    address: str = ""
    chain: str = ""
    name: str = ""


class ContestScope(BaseModel):
    """Scope definition for a Sherlock contest."""
    contest_id: str
    contracts: list[ContractRef] = Field(default_factory=list)
    repos: list[str] = Field(default_factory=list)


class SherlockContest(BaseModel):
    """A single Sherlock audit contest."""
    id: str
    title: str = ""
    description: str = ""
    status: str = ""
    starts_at: str | None = None
    ends_at: str | None = None
    total_reward_usd: float = 0.0
    judging_status: str = ""


class ContestListResponse(BaseModel):
    """Paginated list of contests."""
    data: list[SherlockContest]
    total: int
    offset: int
    limit: int


class SyncStatus(BaseModel):
    """Status of a sync operation."""
    sync_id: str
    status: str = "running"
    contests_fetched: int = 0
    contests_new: int = 0
    contests_updated: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    started_at: str | None = None
    completed_at: str | None = None
