"""Tests for EchidnaNLP."""
import pytest
from src.intelligence.nlp import EchidnaNLP, create_nlp
from src.intelligence.classifier import create_classifier
from src.intelligence.fixer import create_fixer


class TestEchidnaNLP:
    def setup_method(self):
        classifier = create_classifier()
        fixer = create_fixer()
        self.nlp = create_nlp(classifier=classifier, fixer=fixer)

    SAMPLE_FINDINGS = [
        {"test_function": "echidna_no_reentrancy", "title": "Reentrancy", "severity": "critical", "failure_category": "reentrancy", "failure_severity": "critical", "failing_input": "withdraw(100)"},
        {"test_function": "echidna_test_supply", "title": "Supply", "severity": "high", "failure_category": "supply_cap", "failure_severity": "high", "failing_input": ""},
    ]

    def test_ask_summary(self):
        result = self.nlp.ask("summary", self.SAMPLE_FINDINGS)
        assert "property violation" in result["answer"]
        assert result["intent"] == "summary"

    def test_ask_failures(self):
        result = self.nlp.ask("show failures", self.SAMPLE_FINDINGS)
        assert result["intent"] == "failures"

    def test_ask_critical(self):
        result = self.nlp.ask("critical issues", self.SAMPLE_FINDINGS)
        assert result["intent"] == "critical"

    def test_ask_filter_category(self):
        result = self.nlp.ask("show reentrancy", self.SAMPLE_FINDINGS)
        assert result["intent"] == "filter_category"
        assert result["context"]["category_filter"] == "reentrancy"

    def test_ask_how_to_fix(self):
        result = self.nlp.ask("how to fix reentrancy", self.SAMPLE_FINDINGS)
        assert result["intent"] == "how_to_fix"

    def test_ask_sequence(self):
        result = self.nlp.ask("call sequence", self.SAMPLE_FINDINGS)
        assert result["intent"] == "sequence"

    def test_ask_unknown(self):
        result = self.nlp.ask("what is the meaning of life", self.SAMPLE_FINDINGS)
        assert result["intent"] == "unknown"

    def test_follow_up_questions(self):
        result = self.nlp.ask("summary", self.SAMPLE_FINDINGS)
        assert len(result["follow_up_questions"]) > 0
