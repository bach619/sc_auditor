"""Unit tests for Case confidence calculation.

Spec (Agenda 06):
  - Confidence is label-based (Low/Medium/High/Critical), not raw scanner confidence.
  - Numeric value is a fixed mapping from label: Low=0.30, Medium=0.60, High=0.80, Critical=0.95
  - Label is determined by 4 factors: scanner count, PoC, learning patterns, vuln category.
  - Edge cases: numeric confidence always in [0.30, 0.95].
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services/15-dashboard"))

from src.models import CaseCreate, ScannerFinding
from src.storage import create_case


@pytest.fixture(autouse=True)
def _patch_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect SC_AUDITOR_DIR to a temp directory."""
    tmp = Path(tempfile.mkdtemp())
    monkeypatch.setattr("src.storage.SC_AUDITOR_DIR", tmp)
    monkeypatch.setattr("src.storage.CASES_DIR", tmp / "cases")
    monkeypatch.setattr("src.storage.LEARNING_DIR", tmp / "learning")
    (tmp / "cases").mkdir(parents=True, exist_ok=True)
    (tmp / "learning").mkdir(parents=True, exist_ok=True)


def _scan(name: str, confidence: float, detector: str = "reentrancy") -> ScannerFinding:
    return ScannerFinding(name=name, detector=detector, confidence=confidence)


def _make(project: str = "test", title: str = "Test",
          contract: str = "Vault", function: str = "withdraw",
          scanners: list[ScannerFinding] | None = None,
          severity: str = "High", description: str = "", recommendation: str = "") -> CaseCreate:
    return CaseCreate(
        project=project, title=title, contract=contract, function=function,
        scanners=scanners or [_scan("slither", 0.85)],
        severity=severity, description=description, recommendation=recommendation,
    )


class TestConfidence:
    """Confidence calculation tests."""

    def test_single_scanner(self) -> None:
        """Single scanner → label Medium → confidence 0.60."""
        case = create_case(_make(scanners=[_scan("slither", 0.70)]))
        assert case.confidence_label == "Medium"
        assert case.confidence == 0.60

    def test_average_two_scanners(self) -> None:
        """Two scanners merged → label High → confidence 0.80."""
        case1 = create_case(_make(scanners=[_scan("slither", 0.70)]))
        case2 = create_case(_make(
            scanners=[_scan("mythril", 0.90)],
            contract="Vault", function="withdraw"))  # same contract/function → merge
        assert case2.case_id == case1.case_id
        assert case2.confidence_label == "High"
        assert case2.confidence == 0.80  # label_to_conf["High"]

    def test_average_three_scanners(self) -> None:
        """Three scanners in one case → label Critical → confidence 0.95."""
        case = create_case(_make(
            scanners=[
                _scan("slither", 0.70),
                _scan("mythril", 0.90),
                _scan("echidna", 0.80),
            ]
        ))
        # All three are in one CaseCreate, no merge needed
        assert case.scanner_count == 3
        assert case.confidence_label == "Critical"
        assert case.confidence == 0.95  # label_to_conf["Critical"]

    def test_merge_confidence_average(self) -> None:
        """Merge: 1 + 2 scanners → 3 total → label Critical → 0.95."""
        c1 = create_case(_make(scanners=[_scan("slither", 0.70)]))
        c2 = create_case(_make(
            scanners=[_scan("mythril", 0.86), _scan("echidna", 0.90)],
            contract="Vault", function="withdraw"))
        assert c2.case_id == c1.case_id
        assert c2.confidence_label == "Critical"
        assert c2.confidence == 0.95  # label_to_conf["Critical"]

    def test_confidence_zero(self) -> None:
        """Scanner confidence 0.0 → still label Medium → confidence 0.60."""
        case = create_case(_make(scanners=[_scan("slither", 0.0)]))
        assert case.confidence_label == "Medium"
        assert case.confidence == 0.60  # label_to_conf["Medium"]

    def test_confidence_one(self) -> None:
        """Scanner confidence 1.0 → still label Medium → confidence 0.60."""
        case = create_case(_make(scanners=[_scan("slither", 1.0)]))
        assert case.confidence_label == "Medium"
        assert case.confidence == 0.60  # label_to_conf["Medium"]

    def test_confidence_bounds(self) -> None:
        """Confidence always in [0.30, 0.95] for label-based system."""
        for conf in [0.0, 0.25, 0.5, 0.75, 1.0]:
            case = create_case(_make(scanners=[_scan("slither", conf)]))
            assert case.confidence_label == "Medium"
            assert case.confidence == 0.60
            assert 0.0 <= case.confidence <= 1.0  # always within bounds
