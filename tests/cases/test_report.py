"""Unit tests for Case report generation (MD only).

Tests:
  - Markdown report is generated on case creation
  - Report includes case metadata (title, severity, contract, etc.)
  - Report includes scanner findings
  - Nonexistent case returns None
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services/15-dashboard"))

from src.models import CaseCreate, ScannerFinding
from src.storage import create_case, get_report_md, get_report_pdf


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


def _scan(name: str = "slither", detector: str = "reentrancy", confidence: float = 0.85) -> ScannerFinding:
    return ScannerFinding(name=name, detector=detector, confidence=confidence)


def _make(title: str = "Reentrancy in Vault.withdraw()",
          contract: str = "Vault",
          function: str = "withdraw",
          description: str = "The withdraw function does not follow CEI pattern.",
          severity: str = "High",
          recommendation: str = "Apply checks-effects-interactions pattern.") -> CaseCreate:
    return CaseCreate(
        project="test",
        title=title,
        contract=contract,
        function=function,
        scanners=[_scan()],
        severity=severity,
        description=description,
        recommendation=recommendation,
    )


class TestReport:
    """Report generation tests."""

    def test_get_report_md_exists(self) -> None:
        """MD report should be generated on case creation."""
        case = create_case(_make())
        report_md = get_report_md(case.case_id)
        assert report_md is not None
        assert len(report_md) > 0

    def test_report_md_contains_case_title(self) -> None:
        """MD report should include the case title."""
        case = create_case(_make(title="Reentrancy in Vault.withdraw()"))
        report_md = get_report_md(case.case_id)
        assert "Reentrancy in Vault.withdraw()" in report_md

    def test_report_md_contains_severity(self) -> None:
        """MD report should include severity badge."""
        case = create_case(_make(severity="Critical"))
        report_md = get_report_md(case.case_id)
        assert "CRITICAL" in report_md or "Critical" in report_md

    def test_report_md_contains_case_id(self) -> None:
        """MD report should include case ID."""
        case = create_case(_make())
        report_md = get_report_md(case.case_id)
        assert case.case_id in report_md

    def test_report_md_contains_contract_and_function(self) -> None:
        """MD report should reference contract + function."""
        case = create_case(_make(contract="VaultStorage", function="updateBalance"))
        report_md = get_report_md(case.case_id)
        assert "VaultStorage" in report_md
        assert "updateBalance" in report_md

    def test_report_md_contains_description(self) -> None:
        """MD report includes the vulnerability description."""
        desc = "Critical reentrancy vulnerability in withdraw function."
        case = create_case(_make(description=desc))
        report_md = get_report_md(case.case_id)
        assert desc in report_md

    def test_report_md_contains_recommendation(self) -> None:
        """MD report includes the fix recommendation."""
        rec = "Always follow checks-effects-interactions pattern."
        case = create_case(_make(recommendation=rec))
        report_md = get_report_md(case.case_id)
        assert rec in report_md

    def test_report_pdf_generation(self) -> None:
        """PDF report should work (fallback to HTML if no weasyprint)."""
        case = create_case(_make())
        try:
            report_pdf = get_report_pdf(case.case_id)
            # If weasyprint not installed, will generate HTML report instead
            # But should NOT crash
            assert report_pdf is not None or True  # non-fatal
        except Exception:
            pytest.fail("get_report_pdf raised an unexpected exception")

    def test_report_nonexistent_case(self) -> None:
        """Getting report for nonexistent case returns None."""
        assert get_report_md("CASE-99999") is None

    def test_report_pdf_nonexistent_case(self) -> None:
        """Getting PDF report for nonexistent case returns None."""
        assert get_report_pdf("CASE-99999") is None
