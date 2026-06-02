"""Data models for the unified Knowledge Base.

These dataclasses are shared between Classifier (07) and Exploit (08)
services via the ``vyper_kb`` Docker volume at ``/data/knowledge/``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


@dataclass
class ConfirmedFinding:
    """A finding that has been confirmed as True Positive.

    Written by the Exploit service when an exploit succeeds, and/or
    by the Classifier when human feedback confirms a TP.

    Read by:
    - Classifier: to auto-classify similar findings as TP
    - Exploit planner: to prioritize similar attack hypotheses

    Attributes:
        finding_id: Original finding identifier.
        audit_id: Audit session identifier.
        contract_hash: SHA-256 hash of the contract source.
        title: Finding title.
        severity: Severity level (critical/high/medium/low/info).
        attack_type: Type of attack that succeeded.
        confirmed_by: Source of confirmation.
        exploit_successful: Whether an exploit was successfully executed.
        tx_hash: Transaction hash of successful exploit (if any).
        vulnerability_pattern: Key attributes of the vulnerable contract
            (function names, state variables, CEI violations, etc.).
        primitive_sequence: The sequence of exploit primitives that worked
            (for reuse in similar contracts).
        confidence: Confidence level after confirmation (0.0-1.0).
        confirmed_at: ISO-8601 timestamp.
    """

    finding_id: str
    audit_id: str
    contract_hash: str
    title: str
    severity: str
    attack_type: str
    confirmed_by: Literal["exploit", "human", "immunefi"]
    exploit_successful: bool | None = None
    tx_hash: str | None = None
    vulnerability_pattern: dict[str, Any] = field(default_factory=dict)
    primitive_sequence: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    confidence: float = 1.0
    confirmed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class KnowledgeRecord:
    """A record in the knowledge base.

    Supports both confirmed findings and human feedback entries.
    """

    record_id: str
    record_type: Literal["confirmed_tp", "human_feedback", "exploit_attempt"]
    finding_id: str
    audit_id: str
    data: ConfirmedFinding | dict[str, Any]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class KnowledgeStats:
    """Aggregated statistics from the knowledge base."""

    total_confirmed: int = 0
    confirmed_by_exploit: int = 0
    confirmed_by_human: int = 0
    unique_contracts: int = 0
    unique_attack_types: list[str] = field(default_factory=list)
    top_attack_types: list[tuple[str, int]] = field(default_factory=list)
    last_updated: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
