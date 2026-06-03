"""Pydantic v2 models for Hats Finance Service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from vyper_lib.models import ApiResponse, HealthData, Meta


class ContractRef(BaseModel):
    """Reference to a smart contract in vault scope."""
    address: str = ""
    chain: str = ""
    name: str = ""


class VaultScope(BaseModel):
    """Scope definition for a Hats Finance vault."""
    vault_id: str
    contracts: list[ContractRef] = Field(default_factory=list)
    repos: list[str] = Field(default_factory=list)


class HatsVault(BaseModel):
    """A single Hats Finance vault (bounty program)."""
    id: str
    title: str = ""
    description: str = ""
    status: str = ""
    chain: str = ""
    max_bounty_usd: float = 0.0
    total_deposited_usd: float = 0.0
    start_date: str | None = None
    end_date: str | None = None
    committee_address: str = ""
    url: str = ""


class VaultListResponse(BaseModel):
    """Paginated list of vaults."""
    data: list[HatsVault]
    total: int
    offset: int
    limit: int


class SyncStatus(BaseModel):
    """Status of a sync operation."""
    sync_id: str
    status: str = "running"
    vaults_fetched: int = 0
    vaults_new: int = 0
    vaults_updated: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    started_at: str | None = None
    completed_at: str | None = None
