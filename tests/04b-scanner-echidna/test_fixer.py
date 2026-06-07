"""Tests for EchidnaFixer."""
import sys
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parents[2] / "services" / "04b-scanner-echidna"


@pytest.fixture(autouse=True)
def _echidna_env():
    """Isolate echidna imports to prevent namespace pollution with other services' src/."""
    sys.path.insert(0, str(SERVICE_DIR))
    for k in [k for k in sys.modules if k == "src" or k.startswith("src.")]:
        del sys.modules[k]
    yield
    # Cleanup after test
    if str(SERVICE_DIR) in sys.path:
        sys.path.remove(str(SERVICE_DIR))
    for k in list(sys.modules):
        if k == "src" or k.startswith("src."):
            del sys.modules[k]


class TestEchidnaFixer:
    def setup_method(self):
        from src.intelligence.fixer import create_fixer
        self.fixer = create_fixer()

    def test_generate_fix_reentrancy(self):
        fix = self.fixer.generate_fix("reentrancy", "Reentrancy in withdraw", "critical")
        assert fix.category == "reentrancy"
        assert "Checks-Effects-Interactions" in fix.solidity_example
        assert fix.before
        assert fix.after
        assert fix.solidity_example
        assert fix.confidence > 0.9

    def test_generate_fix_access_control(self):
        fix = self.fixer.generate_fix("access_control", "Missing auth", "critical")
        assert "onlyOwner" in fix.after or "Ownable" in fix.solidity_example

    def test_generate_fix_arithmetic(self):
        fix = self.fixer.generate_fix("arithmetic", "Overflow risk", "high")
        assert fix.confidence >= 0.9

    def test_generate_fix_unknown_category(self):
        fix = self.fixer.generate_fix("nonexistent", "Weird bug", "medium")
        assert fix.confidence == 0.4

    def test_generate_fixes_batch(self):
        findings = [
            {"failure_category": "reentrancy", "title": "Reentrancy A", "severity": "critical"},
            {"failure_category": "arithmetic", "title": "Overflow B", "severity": "high"},
            {"failure_category": "reentrancy", "title": "Reentrancy C", "severity": "critical"},
        ]
        fixes = self.fixer.generate_fixes(findings)
        assert "reentrancy" in fixes
        assert "arithmetic" in fixes
        assert len(fixes["reentrancy"]) == 2
        assert len(fixes["arithmetic"]) == 1

    def test_get_available_categories(self):
        cats = self.fixer.get_available_categories()
        assert "reentrancy" in cats
        assert "access_control" in cats
        assert "arithmetic" in cats
