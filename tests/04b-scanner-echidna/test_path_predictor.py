"""Tests for SequenceAnalyzer."""
import pytest
from src.intelligence.path_predictor import SequenceAnalyzer, create_path_predictor


class TestSequenceAnalyzer:
    def setup_method(self):
        self.analyzer = create_path_predictor()

    def test_analyze_no_sequence(self):
        result = self.analyzer.analyze_sequence(None)
        assert result["has_sequence"] is False
        assert result["step_count"] == 0

    def test_analyze_empty_sequence(self):
        result = self.analyzer.analyze_sequence("")
        assert result["has_sequence"] is False

    def test_analyze_simple_sequence(self):
        seq = "transfer(100)\nwithdraw(50)"
        result = self.analyzer.analyze_sequence(seq)
        assert result["has_sequence"]
        assert result["step_count"] == 2
        assert "transfer" in str(result["functions_called"])
        assert "withdraw" in str(result["functions_called"])

    def test_analyze_with_eth_movement(self):
        seq = "deposit(value: 100)\nwithdraw(50)"
        result = self.analyzer.analyze_sequence(seq)
        assert result["involves_eth"] is True

    def test_analyze_with_delegatecall(self):
        seq = "delegatecall(target)\nupdate(42)"
        result = self.analyzer.analyze_sequence(seq)
        assert result["involves_delegatecall"] is True

    def test_complexity_simple(self):
        result = self.analyzer.analyze_sequence("f(1)")
        assert result["complexity"] == "simple"

    def test_complexity_moderate(self):
        result = self.analyzer.analyze_sequence("a(1)\nb(2)\nc(3)")
        assert result["complexity"] == "moderate"

    def test_complexity_complex(self):
        result = self.analyzer.analyze_sequence("a\nb\nc\nd\ne\nf")
        assert result["complexity"] == "complex"

    def test_analyze_findings_batch(self):
        findings = [
            {"test_function": "t1", "failing_input": "transfer(100)"},
            {"test_function": "t2", "failing_input": None},
        ]
        enriched = self.analyzer.analyze_findings(findings)
        assert len(enriched) == 2
        assert enriched[0]["sequence_analysis"]["has_sequence"]
        assert not enriched[1]["sequence_analysis"]["has_sequence"]
