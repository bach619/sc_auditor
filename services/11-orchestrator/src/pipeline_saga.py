"""Saga compensation functions for the pipeline.

Each compensator undoes the effects of one pipeline step when a later
step fails — implementing the Saga rollback pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from src.models import AuditRecord
    from src.pipeline import Pipeline

logger = structlog.get_logger("vyper.orchestrator.pipeline.saga")


async def compensate(pipeline: Pipeline, record: AuditRecord, failed_step_idx: int) -> None:
    """Rollback completed steps in reverse order (Saga pattern)."""
    logger.info("Starting Saga compensation for audit %s", record.audit_id)
    for idx in range(failed_step_idx - 1, -1, -1):
        state, _, _ = pipeline.WORKFLOW[idx]
        compensators = pipeline.COMPENSATIONS.get(state, [])
        for comp_name in compensators:
            comp_fn = COMPENSATION_REGISTRY.get(comp_name)
            if comp_fn:
                try:
                    await comp_fn(record)
                    logger.info("Compensation %s succeeded for step %s", comp_name, state.value)
                except Exception as exc:
                    logger.warning(
                        "Compensation %s failed for step %s: %s",
                        comp_name, state.value, exc,
                    )


async def _compensate_fetch(record: AuditRecord) -> None:
    """Remove cached source data."""
    record.metadata.pop("source_data", None)
    record.metadata.pop("program_data", None)


async def _compensate_scan(record: AuditRecord) -> None:
    """Remove scan results."""
    record.metadata.pop("scan_results", None)


async def _compensate_ai(record: AuditRecord) -> None:
    """Remove AI analysis results."""
    record.metadata.pop("ai_results", None)


async def _compensate_classify(record: AuditRecord) -> None:
    """Remove classified findings."""
    record.metadata.pop("classified_findings", None)
    record.findings = None


async def _compensate_exploit(record: AuditRecord) -> None:
    """Remove exploit data."""
    record.metadata.pop("exploit_data", None)


async def _compensate_reclassify(record: AuditRecord) -> None:
    """Remove reclassification data (rollback to Stage 1)."""
    record.metadata.pop("reclassification_data", None)


async def _compensate_report(record: AuditRecord) -> None:
    """Remove report path."""
    record.report_path = None
    record.metadata.pop("report_data", None)


async def _compensate_notify(record: AuditRecord) -> None:
    """No compensation needed for notifications."""
    pass


COMPENSATION_REGISTRY: dict[str, object] = {
    "_compensate_fetch": _compensate_fetch,
    "_compensate_scan": _compensate_scan,
    "_compensate_ai": _compensate_ai,
    "_compensate_classify": _compensate_classify,
    "_compensate_exploit": _compensate_exploit,
    "_compensate_reclassify": _compensate_reclassify,
    "_compensate_report": _compensate_report,
    "_compensate_notify": _compensate_notify,
}

__all__ = ["compensate", "COMPENSATION_REGISTRY"]
