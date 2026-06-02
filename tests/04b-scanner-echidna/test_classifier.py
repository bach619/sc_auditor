"""Tests for EchidnaClassifier."""
import pytest
from src.intelligence.classifier import EchidnaClassifier, FailureCategory, create_classifier


class TestEchidnaClassifier:
    def setup_method(self):
        self.classifier = create_classifier()

    def test_classify_reentrancy(self):
        """Should detect reentrancy from function name."""
        cat = self.classifier.classify(test_function="echidna_no_reentrancy")
        assert cat.name == "reentrancy"
        assert cat.severity == "critical"
        assert cat.priority == 1

    def test_classify_access_control(self):
        cat = self.classifier.classify(test_function="echidna_only_owner")
        assert cat.name == "access_control"

    def test_classify_arithmetic(self):
        cat = self.classifier.classify(test_function="echidna_overflow_safe")
        assert cat.name == "arithmetic"

    def test_classify_fund_loss(self):
        cat = self.classifier.classify(test_function="echidna_no_loss")
        assert cat.name == "fund_loss"

    def test_classify_oracle_manipulation(self):
        cat = self.classifier.classify(test_function="echidna_oracle_price")
        assert cat.name == "oracle_manipulation"

    def test_classify_flash_loan(self):
        cat = self.classifier.classify(test_function="echidna_flash_safe")
        assert cat.name == "flash_loan"

    def test_classify_supply_cap(self):
        cat = self.classifier.classify(test_function="echidna_cap_limit")
        assert cat.name == "supply_cap"

    def test_classify_invariant_break(self):
        cat = self.classifier.classify(test_function="echidna_test_invariant")
        assert cat.name == "invariant_break"

    def test_classify_assertion_failure(self):
        cat = self.classifier.classify(error_message="Assertion failed: balance mismatch")
        assert cat.name == "assertion_failure"

    def test_classify_unknown(self):
        cat = self.classifier.classify(test_function="echidna_my_custom_test")
        assert cat.name == "unknown"
        assert cat.confidence == 0.0

    def test_classify_batch(self):
        findings = [
            {"test_function": "echidna_no_reentrancy", "description": "reentrancy check", "failing_input": ""},
            {"test_function": "echidna_unknown_test", "description": "something else", "failing_input": ""},
        ]
        enriched = self.classifier.classify_batch(findings)
        assert len(enriched) == 2
        assert enriched[0]["failure_category"] == "reentrancy"
        assert enriched[1]["failure_category"] == "unknown"

    def test_get_available_categories(self):
        cats = self.classifier.get_available_categories()
        assert len(cats) >= 9
        names = [c["name"] for c in cats]
        assert "reentrancy" in names
        assert "access_control" in names
        assert "unknown" in names
