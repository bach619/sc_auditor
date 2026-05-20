"""Pydantic models for Immunefi Service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


# ── Contract ──────────────────────────────────────────────

class Contract(BaseModel):
    """On-chain contract associated with a program."""
    address: str = ""
    chain: str = ""
    name: str = ""


# ── Repository ────────────────────────────────────────────

class Repo(BaseModel):
    """Detected GitHub repository."""
    url: str
    owner: str
    repo: str
    source: str  # e.g. "project_url", "social_link", "contract_source"


# ── Program ───────────────────────────────────────────────

class Program(BaseModel):
    """A single Immunefi bug bounty program."""
    slug: str
    name: str = ""
    chains: list[str] = Field(default_factory=list)
    max_bounty: float | None = None
    min_bounty: float | None = None
    currency: str = "USD"
    status: str = "unknown"
    repos: list[Repo] = Field(default_factory=list)
    contracts: list[Contract] = Field(default_factory=list)
    project_url: str = ""
    logo: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    updated_at: str = ""


# ── Sync ──────────────────────────────────────────────────

class SyncStatus(BaseModel):
    """Status of a running sync operation."""
    sync_id: str
    status: str  # running | completed | failed
    programs_synced: int = 0
    total: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None


# ── API Response Wrappers ─────────────────────────────────

class Meta(BaseModel):
    """Standard response metadata."""
    status: str = "ok"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ApiResponse(BaseModel):
    """Standard API response envelope."""
    data: Any = None
    meta: Meta = Field(default_factory=Meta)


class ProgramListResponse(BaseModel):
    """Paginated list of programs."""
    data: list[Program]
    total: int
    offset: int
    limit: int


class StatsResponse(BaseModel):
    """Aggregated statistics."""
    total_programs: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_chain: dict[str, int] = Field(default_factory=dict)
    bounty_ranges: dict[str, int] = Field(default_factory=dict)
    total_contracts: int = 0
    total_repos: int = 0


class HealthData(BaseModel):
    """Health check response data."""
    status: str = "ok"
    service: str = "immunefi"
    version: str = "0.2.0"
    programs_cached: int = 0
    last_synced: str | None = None
    schema_version: str | None = None
