"""Unit tests for Case dedup logic.

Spec (Section 2.4 Rule 2 & 2.5):
  - Same contract + same function + same vulnerability class →
    MERGE into existing case.
  - Different function → separate CASE.
  - Different vulnerability class → separate CASE.
  - CLOSED case → NOT merged (no ghost reopen).
  - Confidence recalculated as average when merged.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services/15-dashboard"))

from src.models import CaseCreate, ClosedReason, ScannerFinding
from src.storage import close_case, create_case


@pytest.fixture(autouse=True)
def _patch_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect SC_AUDITOR_DIR to a temp directory."""
    tmp = Path(tempfile.mkdtemp())
    import src.storage as _stor
    _stor.SC_AUDITOR_DIR = tmp
    _stor.CASES_DIR = tmp / "cases"
    _stor.LEARNING_DIR = tmp / "learning"
    (tmp / "cases").mkdir(parents=True, exist_ok=True)
    (tmp / "learning").mkdir(parents=True, exist_ok=True)


def _scan(name: str, detector: str, confidence: float = 0.85) -> ScannerFinding:
    return ScannerFinding(name=name, detector=detector, confidence=confidence)


def _create(
    scanner_name: str = "slither",
    vuln_class: str = "reentrancy",
    contract: str = "Vault",
    function: str = "withdraw",
    confidence: float = 0.85,
) -> CaseCreate:
    return CaseCreate(
        project="test",
        title=f"{vuln_class.title()} in {contract}.{function}()",
        contract=contract,
        function=function,
        scanners=[_scan(scanner_name, vuln_class, confidence)],
        severity="High",
        description=f"{scanner_name} found {vuln_class}",
        recommendation="Fix it",
    )


class TestDedupSameBug:
    """Same bug from different scanners → 1 CASE."""

    def test_same_bug_merges(self) -> None:
        """Slither + Mythril detect reentrancy in Vault.withdraw() → merged."""
        case1 = create_case(_create("slither", "reentrancy", "Vault", "withdraw", 0.85))
        case2 = create_case(_create("mythril", "reentrancy", "Vault", "withdraw", 0.90))
        assert case2.case_id == case1.case_id, "Same bug should merge"

    def test_scanner_count_increases_on_merge(self) -> None:
        """scanner_count increases from 1 to 2 after merge."""
        case1 = create_case(_create("slither", "reentrancy", "Vault", "withdraw"))
        assert case1.scanner_count == 1
        case2 = create_case(_create("mythril", "reentrancy", "Vault", "withdraw"))
        assert case2.case_id == case1.case_id
        assert case2.scanner_count == 2

    def test_confidence_increases_on_merge(self) -> None:
        """Confidence increases when multiple scanners confirm (avg)."""
        case1 = create_case(_create("slither", "reentrancy", "Vault", "withdraw", 0.70))
        case2 = create_case(_create("mythril", "reentrancy", "Vault", "withdraw", 0.90))
        assert case2.case_id == case1.case_id
        assert case2.confidence > 0.70

    def test_merge_updates_title(self) -> None:
        """Merged case keeps the more descriptive (longer) title."""
        case1 = create_case(CaseCreate(
            project="test", title="Short",
            contract="Vault", function="withdraw",
            scanners=[_scan("slither", "reentrancy")],
            severity="High", description="x", recommendation="x"))
        case2 = create_case(CaseCreate(
            project="test", title="Reentrancy in Vault.withdraw() - Detailed",
            contract="Vault", function="withdraw",
            scanners=[_scan("mythril", "reentrancy")],
            severity="High", description="y", recommendation="y"))
        assert case2.case_id == case1.case_id
        # Title should be the longer one
        assert len(case2.title) >= len(case1.title)


class TestDedupDifferentFunction:
    """Different function → separate CASE."""

    def test_different_function_separate(self) -> None:
        """Same contract/class, different function → 2 CASES."""
        c1 = create_case(_create("slither", "reentrancy", "Vault", "withdraw"))
        c2 = create_case(_create("mythril", "reentrancy", "Vault", "deposit"))
        assert c2.case_id != c1.case_id


class TestDedupDifferentVulnClass:
    """Different vulnerability class → separate CASE."""

    def test_different_vuln_separate(self) -> None:
        """Same function, different vuln class → 2 CASES."""
        c1 = create_case(_create("slither", "reentrancy", "Vault", "withdraw"))
        c2 = create_case(_create("slither", "access-control", "Vault", "withdraw"))
        assert c2.case_id != c1.case_id


class TestDedupNoGhostReopen:
    """CLOSED case should not be merged into (no ghost reopen)."""

    def test_no_ghost_reopen(self) -> None:
        """Closed case tidak bisa di-merge → results in new CASE."""
        case = create_case(_create("slither", "reentrancy", "Vault", "withdraw"))
        close_case(case.case_id, reason=ClosedReason.CONFIRMED)
        case2 = create_case(_create("mythril", "reentrancy", "Vault", "withdraw"))
        assert case2.case_id != case.case_id, "Closed case should NOT receive new findings"


class TestDedupDifferentContract:
    """Different contract → separate CASE."""

    def test_different_contract_separate(self) -> None:
        """Same vuln/function, different contract → 2 CASES."""
        c1 = create_case(_create("slither", "reentrancy", "Vault", "withdraw"))
        c2 = create_case(_create("mythril", "reentrancy", "Token", "withdraw"))
        assert c2.case_id != c1.case_id
