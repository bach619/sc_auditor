"""Unified bounty platform models — cross-platform bounty aggregation.

Normalizes bounty data from Immunefi, Code4rena, Sherlock, Cantina, Hats Finance,
and other platforms into a single consistent model for cross-platform comparison.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Platform Enum ───────────────────────────────────────────────


class BountyPlatform(str, Enum):
    """Supported bug bounty and audit contest platforms."""

    IMMUNEFI = "immunefi"
    CODE4RENA = "code4rena"
    SHERLOCK = "sherlock"
    CANTINA = "cantina"
    HACKENPROOF = "hackenproof"
    HATS_FINANCE = "hats_finance"
    HUNTR = "huntr"
    BUGRAP = "bugrap"


class BountyStatus(str, Enum):
    """Status of a bounty program or contest."""

    ACTIVE = "active"
    UPCOMING = "upcoming"
    CLOSED = "closed"
    JUDGING = "judging"
    ESCALATING = "escalating"
    PAID = "paid"


class BountyType(str, Enum):
    """Type of bounty program."""

    BUG_BOUNTY = "bug_bounty"          # Ongoing bug bounty (Immunefi, Hats)
    AUDIT_CONTEST = "audit_contest"     # Time-boxed contest (Code4rena, Sherlock)
    CONTINUOUS = "continuous"           # Continuous audit coverage
    COMPETITIVE = "competitive"         # Competitive audit with rankings


# ── Unified Bounty Models ───────────────────────────────────────


class BountyContract(BaseModel):
    """A smart contract in scope for a bounty program."""

    address: str
    chain: str
    name: str = ""
    source_type: str = ""  # "verified", "github", "manual"
    repo_url: Optional[str] = None
    commit_hash: Optional[str] = None
    lines_of_code: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BountyReward(BaseModel):
    """Reward structure for a bounty program."""

    severity: str  # critical, high, medium, low
    min_reward_usd: float = 0.0
    max_reward_usd: float = 0.0
    reward_token: Optional[str] = None
    reward_percentage: Optional[float] = None  # % of total pool


class UnifiedBounty(BaseModel):
    """Normalized bounty program/contest across all platforms."""

    id: str
    platform: BountyPlatform
    platform_id: str = ""  # Original ID from the platform
    title: str
    description: str = ""
    bounty_type: BountyType = BountyType.BUG_BOUNTY
    status: BountyStatus = BountyStatus.ACTIVE

    # Scope
    scope_contracts: List[BountyContract] = Field(default_factory=list)
    scope_repos: List[str] = Field(default_factory=list)
    chains: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)

    # Rewards
    max_bounty_usd: float = 0.0
    total_pool_usd: float = 0.0
    rewards: List[BountyReward] = Field(default_factory=list)
    rewards_token: Optional[str] = None

    # Timing
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Stats
    participants: int = 0
    submissions: int = 0
    validated_findings: int = 0

    # Links
    url: str = ""
    repo_url: Optional[str] = None
    documentation_url: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Cross-Platform Analytics ────────────────────────────────────


class PlatformStats(BaseModel):
    """Statistics for a single bounty platform."""

    platform: BountyPlatform
    active_bounties: int = 0
    total_bounties: int = 0
    total_value_usd: float = 0.0
    avg_bounty_usd: float = 0.0
    total_submissions: int = 0
    avg_reward_per_submission: float = 0.0
    top_chain: str = ""
    top_language: str = ""


class CrossPlatformAnalytics(BaseModel):
    """Aggregated analytics across all bounty platforms."""

    total_active_bounties: int = 0
    total_bounty_value_usd: float = 0.0
    avg_bounty_by_platform: Dict[str, float] = Field(default_factory=dict)
    most_audited_contracts: List[Dict[str, Any]] = Field(default_factory=list)
    platform_stats: List[PlatformStats] = Field(default_factory=list)
    chains_distribution: Dict[str, int] = Field(default_factory=dict)
    languages_distribution: Dict[str, int] = Field(default_factory=dict)
    generated_at: Optional[datetime] = None


# ── Sync Models ─────────────────────────────────────────────────


class BountySyncRequest(BaseModel):
    """Request to sync bounties from a platform."""

    platform: BountyPlatform
    force_full_sync: bool = False
    limit: int = 100


class BountySyncResult(BaseModel):
    """Result of a bounty sync operation."""

    platform: BountyPlatform
    success: bool
    programs_fetched: int = 0
    programs_new: int = 0
    programs_updated: int = 0
    errors: List[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
