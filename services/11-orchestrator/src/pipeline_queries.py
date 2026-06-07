"""Pipeline status query helpers.

Functions for reading, listing, registering, and updating audit records.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models import AuditRecord, PipelineState, PipelineStats
    from src.pipeline import Pipeline


def get_record(pipeline: Pipeline, audit_id: str) -> AuditRecord | None:
    return pipeline._audit_log.get(audit_id)


def get_all_records(
    pipeline: Pipeline,
    state: PipelineState | None = None,
    program: str | None = None,
    chain: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AuditRecord], int]:
    """List audit records with optional filtering and pagination."""
    records = list(pipeline._audit_log.values())

    if state:
        records = [r for r in records if r.state == state]
    if program:
        records = [r for r in records if r.program == program]
    if chain:
        records = [r for r in records if r.chain == chain]

    total = len(records)
    records.sort(key=lambda r: r.created_at, reverse=True)
    return records[offset : offset + limit], total


def get_stats(pipeline: Pipeline) -> PipelineStats:
    """Compute aggregate pipeline statistics."""
    from src.models import PipelineState, PipelineStats

    records = list(pipeline._audit_log.values())
    total = len(records)
    completed = sum(
        1 for r in records
        if r.state in (PipelineState.COMPLETED, PipelineState.COMPLETED_WITH_WARN)
    )
    failed = sum(1 for r in records if r.state.is_failure)
    in_progress = sum(1 for r in records if not r.state.is_terminal)
    timeouts = sum(1 for r in records if r.state == PipelineState.TIMEOUT)

    durations = [r.duration_seconds for r in records if r.duration_seconds is not None]
    avg_dur = sum(durations) / len(durations) if durations else None

    by_state: dict[str, int] = {}
    for r in records:
        by_state[r.state.value] = by_state.get(r.state.value, 0) + 1

    by_program: dict[str, int] = {}
    for r in records:
        prog = r.program or "unknown"
        by_program[prog] = by_program.get(prog, 0) + 1

    return PipelineStats(
        total_audits=total,
        completed=completed,
        failed=failed,
        in_progress=in_progress,
        success_rate=(completed / total * 100) if total > 0 else 0.0,
        avg_duration_seconds=avg_dur,
        by_state=by_state,
        by_program=by_program,
        timeouts=timeouts,
        last_updated=datetime.now(UTC),
    )


def _get_or_create(pipeline: Pipeline, audit_id: str) -> AuditRecord:
    from src.models import AuditRecord

    if audit_id not in pipeline._audit_log:
        record = AuditRecord(audit_id=audit_id, chain="", address="")
        pipeline._audit_log[audit_id] = record
    return pipeline._audit_log[audit_id]


def register_audit(
    pipeline: Pipeline,
    chain: str,
    address: str,
    program: str,
    priority: int,
    use_ai: bool = True,
) -> str:
    """Create a new audit record and return its ID."""
    from src.models import AuditRecord

    audit_id = str(uuid.uuid4())
    record = AuditRecord(
        audit_id=audit_id,
        chain=chain,
        address=address,
        program=program,
        priority=priority,
        use_ai=use_ai,
    )
    pipeline._audit_log[audit_id] = record
    pipeline._save_audit_log()
    return audit_id


def update_record(pipeline: Pipeline, record: AuditRecord) -> None:
    pipeline._audit_log[record.audit_id] = record
    pipeline._save_audit_log()


__all__ = [
    "get_record",
    "get_all_records",
    "get_stats",
    "_get_or_create",
    "register_audit",
    "update_record",
]
