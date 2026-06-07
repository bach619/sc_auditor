"""Pydantic v2 models for Cantina Service."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContractRef(BaseModel):
    """Reference to a smart contract in contest scope."""

    address: str = ""
    chain: str = ""
    name: str = ""


class CantinaContest(BaseModel):
    """A single Cantina audit contest."""

    id: str
    title: str = ""
    description: str = ""
    status: str = ""
    start_date: str = ""
    end_date: str = ""
    total_pool_usd: float = 0.0
    platform_id: str = ""
    url: str = ""


class ContestScope(BaseModel):
    """Scope definition for a Cantina contest."""

    contest_id: str
    contracts: list[ContractRef] = Field(default_factory=list)
    repos: list[str] = Field(default_factory=list)


class ContestListResponse(BaseModel):
    """Paginated list of contests."""

    data: list[CantinaContest]
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
