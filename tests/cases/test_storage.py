"""Unit tests for Case Storage — CRUD operations.

Tests:
  - init: ensure_dirs creates ~/.sc_auditor/cases/
  - create_case: returns Case with correct ID pattern
  - get_case: retrieves by ID
  - list_cases: returns paginated list
  - get_case_stats: returns aggregated statistics
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services/15-dashboard"))

from src.models import CaseCreate, CaseStatus, ClosedReason, ScannerFinding
from src.storage import (
    close_case,
    create_case,
    get_case,
    get_case_stats,
    list_cases,
    list_cases_with_total,
)

_TEST_DIR: Path | None = None


@pytest.fixture(autouse=True)
def _patch_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect SC_AUDITOR_DIR to a temp directory before any import."""
    global _TEST_DIR
    tmp = Path(tempfile.mkdtemp())
    _TEST_DIR = tmp
    import src.storage as _stor
    _stor.SC_AUDITOR_DIR = tmp
    _stor.CASES_DIR = tmp / "cases"
    _stor.LEARNING_DIR = tmp / "learning"
    (tmp / "cases").mkdir(parents=True, exist_ok=True)
    (tmp / "learning").mkdir(parents=True, exist_ok=True)


def _scanner(name: str, detector: str = "reentrancy", confidence: float = 0.85) -> ScannerFinding:
    return ScannerFinding(name=name, detector=detector, confidence=confidence)


def _make_case(
    title: str = "Test Case",
    contract: str = "Vault",
    function: str = "withdraw",
    scanner_name: str = "slither",
    severity: str = "High",
    description: str = "A test vulnerability",
    recommendation: str = "Apply checks-effects-interactions pattern.",
) -> CaseCreate:
    return CaseCreate(
        project="test-project",
        title=title,
        contract=contract,
        function=function,
        scanners=[_scanner(scanner_name)],
        severity=severity,
        description=description,
        recommendation=recommendation,
    )


class TestStorageCRUD:
    """CRUD operations for case storage."""

    def test_create_case_returns_case(self) -> None:
        """create_case returns a valid Case with correct ID."""
        case = create_case(_make_case())
        assert case.case_id.startswith("CASE-")
        assert case.status == CaseStatus.OPEN
        assert case.title == "Test Case"

    def test_create_case_increments_id(self) -> None:
        """Sequential creates get sequential CASE-IDs (different contracts avoid dedup)."""
        c1 = create_case(_make_case(title="Case 1", contract="V1"))
        c2 = create_case(_make_case(title="Case 2", contract="V2"))
        assert c2.case_id != c1.case_id
        # IDs are sequential
        n1 = int(c1.case_id.split("-")[1])
        n2 = int(c2.case_id.split("-")[1])
        assert n2 == n1 + 1

    def test_get_case_exists(self) -> None:
        """get_case returns case after creation."""
        created = create_case(_make_case())
        fetched = get_case(created.case_id)
        assert fetched is not None
        assert fetched.case_id == created.case_id
        assert fetched.title == created.title

    def test_get_case_missing(self) -> None:
        """get_case for non-existent ID returns None."""
        assert get_case("CASE-99999") is None

    def test_get_case_invalid_format(self) -> None:
        """get_case with invalid ID format returns None (not crash)."""
        assert get_case("../../etc/passwd") is None
        assert get_case("INVALID") is None
        assert get_case("CASE-abc") is None

    def test_list_cases_empty(self) -> None:
        """list_cases returns empty list when no cases exist."""
        assert list_cases() == []

    def test_list_cases_with_cases(self) -> None:
        """list_cases returns all created cases."""
        c1 = create_case(_make_case(title="A", contract="C1"))
        c2 = create_case(_make_case(title="B", contract="C2"))
        cases = list_cases()
        assert len(cases) == 2
        ids = {c.case_id for c in cases}
        assert c1.case_id in ids
        assert c2.case_id in ids

    def test_list_cases_status_filter(self) -> None:
        """list_cases filters by status (different contracts avoid dedup)."""
        create_case(_make_case(contract="C1", function="f1"))
        c2 = create_case(_make_case(title="Second", contract="C2", function="f2"))
        close_case(c2.case_id, reason=ClosedReason.CONFIRMED)
        open_cases = list_cases(status="OPEN")
        closed_cases = list_cases(status="CLOSED")
        assert all(c.status == CaseStatus.OPEN for c in open_cases)
        assert all(c.status == CaseStatus.CLOSED for c in closed_cases)

    def test_list_cases_pagination(self) -> None:
        """list_cases respects limit/offset."""
        for i in range(5):
            create_case(_make_case(title=f"Case {i}", contract=f"C{i}"))
        first_3 = list_cases(limit=3, offset=0)
        assert len(first_3) == 3
        next_2 = list_cases(limit=3, offset=3)
        assert len(next_2) == 2
        # No overlap
        first_ids = {c.case_id for c in first_3}
        next_ids = {c.case_id for c in next_2}
        assert first_ids.isdisjoint(next_ids)

    def test_list_cases_with_total(self) -> None:
        """list_cases_with_total returns (cases, total_count)."""
        for i in range(4):
            create_case(_make_case(title=f"Case {i}", contract=f"C{i}"))
        cases, total = list_cases_with_total(limit=2)
        assert len(cases) == 2
        assert total == 4

    def test_close_case(self) -> None:
        """close_case changes status to CLOSED and adds metadata."""
        case = create_case(_make_case())
        closed = close_case(case.case_id, reason=ClosedReason.CONFIRMED, bounty=500.0, notes="Confirmed by manual review")
        assert closed is not None
        assert closed.status == CaseStatus.CLOSED
        assert closed.closed_reason == "confirmed"
        assert closed.bounty_amount == 500.0

    def test_close_case_already_closed(self) -> None:
        """Close an already closed case returns None (no ghost reopen)."""
        case = create_case(_make_case())
        close_case(case.case_id, reason=ClosedReason.CONFIRMED)
        assert close_case(case.case_id, reason=ClosedReason.REJECTED) is None

    def test_get_case_stats(self) -> None:
        """get_case_stats returns aggregated statistics (different contracts avoid dedup)."""
        c1 = create_case(_make_case(severity="High", scanner_name="slither", contract="C1", function="f1"))
        create_case(_make_case(severity="Medium", scanner_name="mythril", title="Medium one", contract="C2", function="f2"))
        close_case(c1.case_id, reason=ClosedReason.CONFIRMED, bounty=1000.0)
        stats = get_case_stats()
        assert stats.total_cases == 2
        assert stats.open_cases == 1
        assert stats.closed_cases == 1
        assert stats.total_bounty == 1000.0
        assert "High" in stats.by_severity
        assert "Medium" in stats.by_severity
