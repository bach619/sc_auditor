"""Pydantic models for the Vyper Source Service.

All request/response models follow the Vyper standard format:
  {"data": ..., "meta": {"status": "ok", "timestamp": "..."}}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Source ─────────────────────────────────────────────────


class SourceFile(BaseModel):
    """A single source file from a verified contract.

    Attributes:
        name: Relative file path (e.g. "contracts/Token.sol").
        content: Full source code of the file.
    """

    name: str
    content: str


class SourceResult(BaseModel):
    """The result of a successful source fetch.

    Attributes:
        sources: Dictionary mapping file names to their source content.
        compiler_version: Solidity compiler version (e.g. "0.8.20").
        license: SPDX license identifier, if detected.
        provider: Name of the provider that returned this result.
        constructor_args: Constructor arguments ABI-encoded hex string, if available.
    """

    sources: dict[str, str]
    compiler_version: str
    license: str | None = None
    provider: str
    constructor_args: str | None = None


# ── Requests ───────────────────────────────────────────────


class FetchRequest(BaseModel):
    """Request body for POST /fetch.

    Attributes:
        chain: Blockchain name (e.g. "ethereum", "polygon").
        address: Contract address (checksummed or lowercase).
        providers: Optional ordered list of providers to try.
                   Defaults to all available providers.
    """

    chain: str
    address: str
    providers: list[str] | None = None


class BatchFetchItem(BaseModel):
    """Single item in a batch fetch request."""

    chain: str
    address: str
    providers: list[str] | None = None


class BatchFetchRequest(BaseModel):
    """Request body for POST /fetch/batch."""

    contracts: list[BatchFetchItem]
    parallel: bool = True


class BatchFetchResult(BaseModel):
    """Single result in a batch fetch response."""

    chain: str
    address: str
    success: bool
    provider: str | None = None
    file_count: int = 0
    error: str | None = None


# ── Verification ────────────────────────────────────────────


class VerificationRequest(BaseModel):
    """Request body for POST /verify."""

    chain: str
    address: str
    providers: list[str] | None = None


class VerificationResult(BaseModel):
    """Result of source verification against on-chain bytecode."""

    verified: bool
    chain: str
    address: str
    match_percentage: float = 0.0
    compiler_version: str = ""
    provider: str = ""
    error: str | None = None
    metadata_hash: str | None = None
    optimized: bool = False


# ── Search ──────────────────────────────────────────────────


class SearchResult(BaseModel):
    """Result item in contract search."""

    chain: str
    address: str
    name: str | None = None
    compiler_version: str = ""
    license: str | None = None
    provider: str = ""
    file_count: int = 0
    fetched_at: str = ""
    cached: bool = True


# ── Metadata ────────────────────────────────────────────────


class ContractMetadata(BaseModel):
    """Full metadata for a contract."""

    chain: str
    address: str
    provider: str
    compiler_version: str
    license: str | None = None
    constructor_args: str | None = None
    file_count: int = 0
    files: list[str] = Field(default_factory=list)
    fetched_at: str = ""
    source_hash: str | None = None
    bytecode_hash: str | None = None
    lines_of_code: int = 0
    has_abi: bool = False
    is_verified: bool | None = None
    upgrade_count: int = 0


# ── Cache Stats ─────────────────────────────────────────────


class CacheStats(BaseModel):
    """Statistics about the source cache."""

    total_contracts: int = 0
    total_files: int = 0
    total_lines: int = 0
    by_chain: dict[str, int] = Field(default_factory=dict)
    by_provider: dict[str, int] = Field(default_factory=dict)
    by_compiler: dict[str, int] = Field(default_factory=dict)
    cache_size_bytes: int = 0
    oldest_entry: str | None = None
    newest_entry: str | None = None


# ── Providers ──────────────────────────────────────────────


class Provider(BaseModel):
    """Descriptor for a source provider.

    Attributes:
        name: Provider identifier (e.g. "etherscan").
        available: Whether the provider responded to connectivity check.
        priority: Default priority order (lower = tried first).
    """

    name: str
    available: bool
    priority: int


# ── Enrichment ──────────────────────────────────────────────


class EnrichedContract(BaseModel):
    """Contract with enriched metadata (Level 2)."""

    chain: str
    address: str
    name: str | None = None
    compiler_version: str = ""
    license: str | None = None
    lines_of_code: int = 0
    function_count: int = 0
    file_count: int = 0

    # Security features
    has_openzeppelin: bool = False
    has_assembly: bool = False
    has_delegatecall: bool = False
    has_unchecked: bool = False
    has_external_call: bool = False

    # Standards
    erc_detected: list[str] = Field(default_factory=list)

    # Framework
    framework: str | None = None

    # Complexity
    cyclomatic_complexity: float = 0.0
    nesting_depth: int = 0

    # Dependencies
    dependency_count: int = 0
    dependencies: list[str] = Field(default_factory=list)

    # Upgradeability
    is_proxy: bool = False
    proxy_type: str | None = None
    upgrade_count: int = 0


# ── Upgrade Detection ───────────────────────────────────────


class UpgradeInfo(BaseModel):
    """Information about a contract upgrade."""

    upgraded: bool = False
    previous_version: int = 0
    current_version: int = 1
    files_changed: list[str] = Field(default_factory=list)
    added_functions: int = 0
    removed_functions: int = 0
    modified_functions: int = 0
    critical: bool = False
    backdoor_detected: bool = False
    severity: str = "medium"
    description: str = ""
    detected_at: str = ""
    diff: dict[str, list[str]] = Field(default_factory=dict)


# ── Block Monitor ───────────────────────────────────────────


class MonitorStatus(BaseModel):
    """Status of the block monitor."""

    running: bool = False
    chains: list[str] = Field(default_factory=list)
    last_blocks: dict[str, int] = Field(default_factory=dict)
    contracts_found: int = 0
    contracts_fetched: int = 0
    uptime_seconds: float = 0.0


# ── Cache Warming ───────────────────────────────────────────


class CacheWarmResult(BaseModel):
    """Result of a cache warming operation."""

    category: str
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0


# ── API Response Envelope ──────────────────────────────────


class Meta(BaseModel):
    """Standard response metadata.

    Attributes:
        status: Response status indicator ("ok" or "error").
        timestamp: ISO-8601 timestamp of the response.
    """

    status: Literal["ok", "error"] = "ok"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ApiResponse(BaseModel):
    """Standard Vyper API response envelope.

    Attributes:
        data: The response payload.
        meta: Response metadata including status and timestamp.
    """

    data: Any = None
    meta: Meta = Field(default_factory=Meta)


# ── Health ─────────────────────────────────────────────────


class HealthData(BaseModel):
    """Health check response data."""

    status: str = "ok"
    service: str = "source"
    version: str = "0.2.0"
    sources_cached: int = 0
    providers_available: int = 0
    cache_size_bytes: int = 0
