"""Pydantic v2 models for the Vyper Upkeep Service.

All request/response models follow the Vyper standard envelope:
  {"data": ..., "meta": {"status": "ok", "timestamp": "..."}}
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ── API Envelope ─────────────────────────────────────────────


class Meta(BaseModel):
    """Standard response metadata."""

    status: Literal["ok", "error"] = "ok"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class ApiResponse(BaseModel):
    """Standard Vyper API response envelope."""

    data: Any = None
    meta: Meta = Field(default_factory=Meta)


# ── Health ───────────────────────────────────────────────────


class HealthData(BaseModel):
    """Health check response data."""

    status: str = "ok"
    service: str = "upkeep"
    version: str = "0.1.0"
    current_version: str = ""
    uptime_seconds: float = 0.0


# ── Update ───────────────────────────────────────────────────


class UpdateCheckResult(BaseModel):
    """Result of checking for available updates.

    Attributes:
        current_version: Locally installed version.
        latest_version: Latest version available remotely.
        update_available: Whether a newer version exists.
        changelog_summary: Brief summary of changes in latest.
        checked_at: ISO-8601 timestamp of the check.
    """

    current_version: str = "0.0.0"
    latest_version: str = ""
    update_available: bool = False
    changelog_summary: str = ""
    checked_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class UpdateResult(BaseModel):
    """Result of performing a self-update.

    Attributes:
        success: Whether the update completed successfully.
        previous_version: Version before update.
        current_version: Version after update.
        output: Command output / log from update process.
        error: Error message if update failed.
    """

    success: bool = False
    previous_version: str = ""
    current_version: str = ""
    output: str = ""
    error: str | None = None


# ── Backup ───────────────────────────────────────────────────


class BackupInfo(BaseModel):
    """Information about a single backup archive.

    Attributes:
        name: Backup file name (excluding ``.tar.gz`` extension).
        size_bytes: File size in bytes.
        created_at: ISO-8601 timestamp of backup creation.
        age_days: Age of the backup in days.
        path: Full path to the backup file.
    """

    name: str
    size_bytes: int = 0
    created_at: str = ""
    age_days: float = 0.0
    path: str = ""


class BackupResult(BaseModel):
    """Result of creating a backup.

    Attributes:
        success: Whether the backup was created successfully.
        name: Backup file name.
        path: Full path to the backup file.
        size_bytes: Size of the created backup.
        error: Error message if backup failed.
    """

    success: bool = False
    name: str = ""
    path: str = ""
    size_bytes: int = 0
    error: str | None = None


class RestoreResult(BaseModel):
    """Result of restoring from a backup.

    Attributes:
        success: Whether the restore completed successfully.
        backup_name: Name of the backup that was restored.
        backup_path: Path to the backup file used.
        pre_restore_backup: Auto-created pre-restore backup name.
        error: Error message if restore failed.
    """

    success: bool = False
    backup_name: str = ""
    backup_path: str = ""
    pre_restore_backup: str | None = None
    error: str | None = None


# ── Metrics ──────────────────────────────────────────────────


class ServiceMetrics(BaseModel):
    """Metrics snapshot for a single Vyper service.

    Attributes:
        service: Service name (e.g. scanner, ai, classifier).
        available: Whether the service was reachable.
        status: Health status reported by the service.
        version: Service version string.
        metrics: Service-specific metrics key-value map.
        error: Error message if service unreachable.
    """

    service: str
    available: bool = False
    status: str = "unknown"
    version: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class AggregatedMetrics(BaseModel):
    """Aggregated metrics across all Vyper services.

    Attributes:
        services: List of per-service metrics snapshots.
        total_services: Total number of services queried.
        available_services: Number of services that responded.
        collected_at: ISO-8601 timestamp of aggregation.
        summary: Computed summary fields across services.
    """

    services: list[ServiceMetrics] = Field(default_factory=list)
    total_services: int = 0
    available_services: int = 0
    collected_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    summary: dict[str, Any] = Field(default_factory=dict)


class MetricsSummary(BaseModel):
    """High-level summary of Vyper platform metrics.

    Attributes:
        total_audits: Total audits completed across all services.
        total_findings: Total security findings detected.
        total_exploits: Total PoC exploits generated.
        total_reports: Total audit reports generated.
        total_notifications: Total notifications sent.
        success_rate: Overall audit success rate (0.0-1.0).
        precision: Classifier precision (0.0-1.0).
        recall: Classifier recall (0.0-1.0).
        f1_score: Classifier F1 score (0.0-1.0).
        ai_cache_hit_rate: AI service cache hit rate (0.0-1.0).
        scanner_tools_used: Most used scanner tools.
        uptime_hours: Total platform uptime in hours.
    """

    total_audits: int = 0
    total_findings: int = 0
    total_exploits: int = 0
    total_reports: int = 0
    total_notifications: int = 0
    success_rate: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    ai_cache_hit_rate: float = 0.0
    scanner_tools_used: list[str] = Field(default_factory=list)
    uptime_hours: float = 0.0
