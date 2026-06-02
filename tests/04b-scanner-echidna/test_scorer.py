"""Tests for EchidnaScorer."""
import pytest
from src.intelligence.scorer import EchidnaScorer, FailureScore, create_scorer


class TestEchidnaScorer:
    def setup_method(self):
        self.scorer = create_scorer()

    def test_score_critical_finding(self):
        finding = {
            "title": "Reentrancy detected",
            "test_function": "echidna_no_reentrancy",
            "failure_category": "reentrancy",
            "failure_severity": "critical",
            "severity": "critical",
            "failing_input": "transfer(0x1234)\nwithdraw(100)\ncall(0xdead)\ndeposit(50)\ncheckBalance()\n",
        }
        score = self.scorer.score_finding(finding)
        assert score.normalized_score >= 80
        assert score.risk_label == "critical"
        assert score.priority == 1

    def test_score_low_risk_finding(self):
        finding = {
            "title": "Minor issue",
            "test_function": "echidna_test_something",
            "failure_category": "unknown",
            "failure_severity": "low",
            "severity": "low",
            "failing_input": "",
        }
        score = self.scorer.score_finding(finding)
        assert score.normalized_score < 35
        assert score.priority >= 4

    def test_score_with_call_sequence(self):
        finding = {
            "title": "Fund loss",
            "test_function": "echidna_no_loss",
            "failure_category": "fund_loss",
            "failure_severity": "critical",
            "failing_input": "deposit(100)\nwithdraw(200)\ntransfer(0xdead, 50)\n",
        }
        score = self.scorer.score_finding(finding)
        assert score.reproducibility > 0.5
        assert score.fund_movement > 0

    def test_score_no_call_sequence(self):
        finding = {
            "title": "Simple assertion",
            "test_function": "echidna_test",
            "failure_category": "invariant_break",
            "failure_severity": "medium",
            "failing_input": "",
        }
        score = self.scorer.score_finding(finding)
        assert score.reproducibility == 0.3
        assert score.sequence_complexity == 0.3

    def test_score_findings_sorting(self):
        findings = [
            {"title": "A", "test_function": "t1", "failure_category": "a", "severity": "low", "failing_input": ""},
            {"title": "B", "test_function": "t2", "failure_category": "b", "severity": "critical", "failing_input": "step1\nstep2\nstep3\n"},
        ]
        scores = self.scorer.score_findings(findings)
        assert len(scores) == 2
        # Should be sorted descending by score
        assert scores[0].normalized_score >= scores[1].normalized_score

    def test_compute_aggregate_empty(self):
        agg = self.scorer.compute_aggregate([])
        assert agg["overall_score"] == 0
        assert agg["health"] == "unknown"

    def test_compute_aggregate_with_scores(self):
        findings = [
            {"title": "Critical", "test_function": "t1", "failure_category": "c", "severity": "critical", "failing_input": "x\ny\nz\n"},
            {"title": "High", "test_function": "t2", "failure_category": "h", "severity": "high", "failing_input": "a\nb\n"},
        ]
        scores = self.scorer.score_findings(findings)
        agg = self.scorer.compute_aggregate(scores)
        assert agg["total_failures"] == 2
        assert "overall_score" in agg
        assert "health" in agg
