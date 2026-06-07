"""Mock Case data for Case Management tests (Agenda 05).

These fixtures create realistic Case models for unit-testing
the dedup logic, confidence calculation, and report generation.

Imports are lazy (inside functions) to avoid namespace collision
with 04b-scanner-echidna's ``src/`` package during pytest collection.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DASHBOARD_SRC = Path(__file__).resolve().parents[2] / "services" / "15-dashboard"


def _ensure_dashboard_path() -> None:
    """Add dashboard source to sys.path, clearing any cached src modules."""
    sys.path.insert(0, str(DASHBOARD_SRC))
    for k in [k for k in sys.modules if k == "src" or k.startswith("src.")]:
        del sys.modules[k]


def _get_models():
    """Lazy import Case models."""
    _ensure_dashboard_path()
    from src.models import Case, CaseCreate, CaseStatus, ScannerFinding, Severity  # noqa: F401

    return Case, CaseCreate, CaseStatus, ScannerFinding, Severity


def make_scanner_finding(
    detector: str = "slither",
    vuln_class: str = "reentrancy",
    contract: str = "Vault",
    function: str = "withdraw",
    severity: str = "High",
    confidence: float = 0.85,
) -> Any:
    """Create a ScannerFinding with minimal required fields."""
    _, _, _, ScannerFinding, _ = _get_models()
    return ScannerFinding(
        detector=detector,
        vulnerability_class=vuln_class,
        contract=contract,
        function=function,
        severity=severity,
        confidence=confidence,
        description=f"{detector} detected {vuln_class} in {contract}.{function}()",
        recommendation="Fix the vulnerability.",
    )


def make_case_create(
    detector: str = "slither",
    vuln_class: str = "reentrancy",
    contract: str = "Vault",
    function: str = "withdraw",
    severity: str = "High",
    confidence: float = 0.85,
    title: str | None = None,
) -> Any:
    """Create a CaseCreate payload (as received from scanner)."""
    _, CaseCreate, _, ScannerFinding, _ = _get_models()
    finding = make_scanner_finding(detector, vuln_class, contract, function, severity, confidence)
    return CaseCreate(
        title=title or f"{vuln_class.title()} in {contract}.{function}()",
        description=finding.description,
        severity=severity,
        contract=contract,
        function=function,
        detector=detector,
        scanner_findings=[finding],
        recommendation=finding.recommendation,
    )


def make_open_case(
    case_id: str = "CASE-001",
    detector: str = "slither",
    vuln_class: str = "reentrancy",
    contract: str = "Vault",
    function: str = "withdraw",
    severity: str = "High",
    confidence: float = 0.85,
    scanner_count: int = 1,
) -> Any:
    """Create an open Case as stored in YAML (with all fields)."""
    Case, _, CaseStatus, ScannerFinding, Severity = _get_models()
    finding = make_scanner_finding(detector, vuln_class, contract, function, severity, confidence)
    now = datetime.now(UTC).isoformat()
    return Case(
        case_id=case_id,
        title=f"{vuln_class.title()} in {contract}.{function}()",
        description=finding.description,
        severity=Severity(severity),
        contract=contract,
        function=function,
        confidence=confidence,
        status=CaseStatus.OPEN,
        created_at=now,
        updated_at=now,
        scanner_findings=[finding],
        scanner_count=scanner_count,
        detector=detector,
    )


def make_closed_case(
    case_id: str = "CASE-002",
    severity: str = "Critical",
    detector: str = "mythril",
) -> Any:
    """Create a closed Case (used for no-ghost-reopen tests)."""
    Case, _, CaseStatus, _, Severity = _get_models()
    finding = make_scanner_finding(detector=detector, severity=severity)
    now = datetime.now(UTC).isoformat()
    return Case(
        case_id=case_id,
        title=f"Closed {severity.lower()} case",
        description=finding.description,
        severity=Severity(severity),
        contract=finding.contract,
        function=finding.function,
        confidence=0.90,
        status=CaseStatus.CLOSED,
        closed_at=now,
        closed_reason="confirmed",
        bounty_amount=5000.0,
        created_at=now,
        updated_at=now,
        scanner_findings=[finding],
        scanner_count=1,
        detector=detector,
    )


# ── Module-level fixtures (safe — conftest no longer pollutes sys.path) ──

REENTRANCY_VAULT_OPEN = make_open_case(
    case_id="CASE-001",
    detector="slither",
    vuln_class="reentrancy",
    contract="Vault",
    function="withdraw",
    confidence=0.85,
)

REENTRANCY_VAULT_CLOSED = make_closed_case(
    case_id="CASE-002",
    severity="Critical",
    detector="mythril",
)

ACCESS_CONTROL_VAULT = make_open_case(
    case_id="CASE-003",
    detector="halmos",
    vuln_class="access-control",
    contract="Vault",
    function="emergencyWithdraw",
    confidence=0.95,
)

INTEGER_OVERFLOW_TOKEN = make_open_case(
    case_id="CASE-004",
    detector="echidna",
    vuln_class="integer-overflow",
    contract="Token",
    function="transfer",
    severity="Medium",
    confidence=0.60,
)
