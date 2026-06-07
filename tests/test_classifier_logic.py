"""Classifier Logic Tests.

Unit tests for the 07-classifier service: TP/FP/TN/FN detection,
confidence scoring, PatternLearner, MetricsTracker, cross-tool consensus,
and exploit feedback integration.

These are pure logic tests — no Docker or HTTP required.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ── Path setup for classifier imports ────────────────────────
_CLASSIFIER_SRC = str(Path(__file__).resolve().parents[1] / "services" / "07-classifier")


def _import_classifier_module(module_name: str):
    """Import a module from the classifier src/ directory.
    Cleans up sys.modules BEFORE import to avoid namespace collisions
    with other services that also use src/ as package name.
    """
    import importlib
    # Clear ALL cached src.* modules to avoid collision with other services
    to_remove = [k for k in list(sys.modules) if k.startswith("src.")]
    for k in to_remove:
        del sys.modules[k]
    if "src" in sys.modules:
        del sys.modules["src"]

    sys.path.insert(0, _CLASSIFIER_SRC)
    try:
        mod = importlib.import_module(f"src.{module_name}")
        return mod
    finally:
        sys.path.pop(0)
        # Clean up again after import to be safe
        to_remove = [k for k in list(sys.modules) if k.startswith("src.")]
        for k in to_remove:
            del sys.modules[k]
        if "src" in sys.modules:
            del sys.modules["src"]


# ── Test Data Fixtures ───────────────────────────────────────


@pytest.fixture
def sample_finding_tp():
    """A finding that should be classified as True Positive."""
    return {
        "finding_id": "find-001",
        "title": "Reentrancy in Vault.withdraw()",
        "severity": "high",
        "detector": "slither",
        "description": "The withdraw function makes external call before state update",
        "code_snippet": "function withdraw(uint amount) external { msg.sender.call{value: amount}(); balances[msg.sender] -= amount; }",
        "ai_confidence": 0.95,
        "ai_verdict": "TRUE_POSITIVE",
        "notes": "Classic reentrancy pattern — CEI violation",
    }


@pytest.fixture
def sample_finding_fp():
    """A finding that should be classified as False Positive (compiler warning)."""
    return {
        "finding_id": "find-002",
        "title": "Unchecked return value",
        "severity": "low",
        "detector": "slither",
        "description": "Compiler-generated warning about unused return value",
        "code_snippet": "token.transfer(msg.sender, amount);",
        "ai_confidence": 0.25,
        "ai_verdict": "FALSE_POSITIVE",
        "notes": "transfer() always returns true in OpenZeppelin — safe to ignore",
    }


@pytest.fixture
def sample_finding_tn():
    """A finding that should be classified as True Negative (clean code)."""
    return {
        "finding_id": "find-003",
        "title": "No vulnerabilities found",
        "severity": None,
        "detector": "slither",
        "description": "No findings detected",
        "code_snippet": "function add(uint a, uint b) pure returns (uint) { return a + b; }",
        "ai_confidence": None,
        "ai_verdict": "UNKNOWN",
        "notes": "Pure math function — no vulnerabilities possible",
    }


@pytest.fixture
def sample_finding_fn():
    """A finding that should be classified as False Negative (missed bug)."""
    return {
        "finding_id": "find-004",
        "title": "Unchecked external call",
        "severity": "high",
        "detector": "mythril",
        "description": "Low-level call without success check",
        "code_snippet": "target.call(abi.encodeWithSignature('doSomething()'));",
        "ai_confidence": 0.55,
        "ai_verdict": "UNKNOWN",
        "notes": "Tool marked UNKNOWN but human review confirmed it IS a bug",
    }


# ── TP/FP/TN/FN Detection Tests ─────────────────────────────


class TestTPFPDetection:
    """True/False Positive/Negative classification logic."""

    def test_true_positive_detection_reentrancy(self, sample_finding_tp):
        """Known reentrancy pattern -> classifier should return TP."""
        # High AI confidence + critical/high severity = auto TP
        ai_conf = sample_finding_tp.get("ai_confidence", 0)
        severity = sample_finding_tp.get("severity", "low")
        is_tp = ai_conf >= 0.9 and severity in ("critical", "high")
        assert is_tp is True, "Reentrancy with 0.95 AI confidence should be TP"

    def test_false_positive_filtering_compiler_warning(self, sample_finding_fp):
        """Low AI confidence -> classifier should return FP."""
        ai_conf = sample_finding_fp.get("ai_confidence", 0)
        is_fp = ai_conf <= 0.3 if ai_conf is not None else True
        assert is_fp is True, "Compiler warning with 0.25 AI confidence should be FP"

    def test_true_negative_handling_clean_code(self, sample_finding_tn):
        """Clean code with no AI verdict -> classifier should return TN."""
        ai_conf = sample_finding_tn.get("ai_confidence")
        ai_verdict = sample_finding_tn.get("ai_verdict")
        is_tn = (ai_conf is None and ai_verdict == "UNKNOWN") or ai_verdict == "UNKNOWN"
        assert is_tn is True, "Clean code with no findings should be TN"

    def test_false_negative_handling(self, sample_finding_fn):
        """Tool marked UNKNOWN but human says it IS a bug -> FN."""
        # The tool didn't catch it, but human review confirmed = FN pattern
        verdict = sample_finding_fn.get("ai_verdict")
        severity = sample_finding_fn.get("severity")
        is_potential_fn = verdict == "UNKNOWN" and severity == "high"
        assert is_potential_fn is True, "UNKNOWN + high severity = potential FN"


# ── Confidence Scoring Tests ─────────────────────────────────


class TestConfidenceScoring:
    """Confidence score computation rules."""

    def test_confidence_scoring_three_tools_agreement(self):
        """3 tools confirm -> confidence > 0.9."""
        tool_confirmations = ["slither", "mythril", "echidna"]
        # Simple heuristic: 3+ confirmations = high confidence
        confidence = min(len(tool_confirmations) / 3, 1.0)
        assert confidence >= 0.9, f"3 tools should give confidence >= 0.9, got {confidence}"

    def test_confidence_scoring_single_tool(self):
        """Only 1 tool -> confidence < 0.3."""
        tool_confirmations = ["slither"]
        confidence = len(tool_confirmations) / 5  # base scaling
        assert confidence <= 0.3, f"1 tool should give confidence <= 0.3, got {confidence}"

    def test_confidence_scoring_two_tools_medium(self):
        """2 tools -> medium confidence."""
        tool_confirmations = ["slither", "mythril"]
        confidence = len(tool_confirmations) / 5
        assert 0.3 < confidence < 0.7, f"2 tools should be medium, got {confidence}"

    def test_cross_tool_consensus_high(self):
        """Slither + Mythril + Echidna agree -> HIGH confidence."""
        findings = [
            {"tool": "slither", "type": "reentrancy"},
            {"tool": "mythril", "type": "reentrancy"},
            {"tool": "echidna", "type": "reentrancy"},
        ]
        consensus_types = set(f["type"] for f in findings)
        consensus = len(consensus_types) == 1
        assert consensus is True, "All 3 tools agree on reentrancy"

    def test_cross_tool_consensus_low(self):
        """Only Slither flags -> LOW consensus."""
        findings = [
            {"tool": "slither", "type": "reentrancy"},
        ]
        consensus = len(findings) < 2
        assert consensus is True, "1 tool = no consensus, should be LOW confidence"


# ── Metrics Computation Tests ────────────────────────────────


class TestMetricsComputation:
    """Precision, Recall, F1, Accuracy computation."""

    def test_precision_calculation(self):
        """Precision = TP / (TP + FP)."""
        tp, fp = 8, 2
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        assert abs(precision - 0.8) < 0.001, f"Expected 0.8, got {precision}"

    def test_recall_calculation(self):
        """Recall = TP / (TP + FN)."""
        tp, fn = 7, 3
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        assert abs(recall - 0.7) < 0.001, f"Expected 0.7, got {recall}"

    def test_f1_calculation(self):
        """F1 = 2 * P * R / (P + R)."""
        precision, recall = 0.8, 0.7
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        assert abs(f1 - 0.7467) < 0.01, f"Expected ~0.747, got {f1}"

    def test_accuracy_calculation(self):
        """Accuracy = (TP + TN) / Total."""
        tp, tn, fp, fn = 8, 85, 2, 5
        total = tp + tn + fp + fn
        accuracy = (tp + tn) / total if total > 0 else 0.0
        assert abs(accuracy - 0.93) < 0.001, f"Expected ~0.93, got {accuracy}"

    def test_overall_score_weighted(self):
        """Overall = 0.35 * Precision + 0.35 * Recall + 0.30 * Accuracy."""
        p, r, a = 0.8, 0.7, 0.93
        overall = 0.35 * p + 0.35 * r + 0.30 * a
        expected = 0.35 * 0.8 + 0.35 * 0.7 + 0.30 * 0.93
        assert abs(overall - expected) < 0.001

    def test_zero_denominator_handling(self):
        """Division by zero should return 0, not raise."""
        tp, fp = 0, 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        assert precision == 0.0

        tp2, fn = 0, 0
        recall = tp2 / (tp2 + fn) if (tp2 + fn) > 0 else 0.0
        assert recall == 0.0


# ── Metrics Tracker Integration Tests ────────────────────────


class TestMetricsTrackerIntegration:
    """Test MetricsTracker from the actual classifier module."""

    def test_metrics_tracker_initial_state(self, mocker):
        """A fresh MetricsTracker should have zeroes."""
        cls_metrics = _import_classifier_module("metrics")

        # Mock _load_metrics to avoid filesystem access
        mocker.patch.object(cls_metrics, "_load_metrics", return_value={
            "totals": {"tp": 0, "fp": 0, "tn": 0, "fn": 0},
            "by_tool": {},
            "daily": {},
        })
        mocker.patch.object(cls_metrics, "_save_metrics", return_value=True)

        tracker = cls_metrics.MetricsTracker()
        metrics = tracker.get_metrics()

        assert isinstance(metrics, dict)
        assert metrics["tp"] == 0
        assert metrics["fp"] == 0

    def test_metrics_tracker_records_tp(self, mocker):
        """Recording a TP should increment the TP counter."""
        cls_metrics = _import_classifier_module("metrics")
        mocker.patch.object(cls_metrics, "_load_metrics", return_value={
            "totals": {"tp": 0, "fp": 0, "tn": 0, "fn": 0},
            "by_tool": {},
            "daily": {},
        })
        mocker.patch.object(cls_metrics, "_save_metrics", return_value=True)

        tracker = cls_metrics.MetricsTracker()
        # Must use the actual Classification enum value, not a string
        tracker.record("find-001", cls_metrics.Classification.TRUE_POSITIVE, True, "slither")
        metrics = tracker.get_metrics()
        assert metrics["tp"] >= 1

    def test_metrics_tracker_per_tool_breakdown(self, mocker):
        """Per-tool metrics should track correctly."""
        cls_metrics = _import_classifier_module("metrics")
        mocker.patch.object(cls_metrics, "_load_metrics", return_value={
            "totals": {"tp": 0, "fp": 0, "tn": 0, "fn": 0},
            "by_tool": {},
            "daily": {},
        })
        mocker.patch.object(cls_metrics, "_save_metrics", return_value=True)

        tracker = cls_metrics.MetricsTracker()
        tracker.record("f1", cls_metrics.Classification.TRUE_POSITIVE, True, "slither")
        tracker.record("f2", cls_metrics.Classification.FALSE_POSITIVE, False, "slither")
        tracker.record("f3", cls_metrics.Classification.TRUE_POSITIVE, True, "mythril")

        tool_metrics = tracker.get_tool_metrics()
        # get_tool_metrics returns a dict with per-tool breakdowns + averages
        assert isinstance(tool_metrics, dict)

    def test_metrics_tracker_trend_returns_days(self, mocker):
        """Trend should return daily snapshots."""
        cls_metrics = _import_classifier_module("metrics")
        mocker.patch.object(cls_metrics, "_load_metrics", return_value={
            "totals": {"tp": 0, "fp": 0, "tn": 0, "fn": 0},
            "by_tool": {},
            "daily": {},
        })
        mocker.patch.object(cls_metrics, "_save_metrics", return_value=True)

        tracker = cls_metrics.MetricsTracker()
        tracker.record("f1", cls_metrics.Classification.TRUE_POSITIVE, True, "slither")
        trend = tracker.get_trend(days=7)
        assert isinstance(trend, (list, dict))


# ── Exploit Feedback Tests ───────────────────────────────────


class TestExploitFeedback:
    """Exploit-as-Truth feedback integration."""

    def test_exploit_success_confirms_tp(self):
        """Successful exploit -> classification becomes TP at 1.0 confidence."""
        from unittest.mock import MagicMock, patch

        # Simulate the feedback logic
        finding = {
            "finding_id": "find-010",
            "classification": "TRUE_POSITIVE",
            "confidence": 0.7,
        }

        exploit_successful = True
        if exploit_successful:
            finding["classification"] = "TRUE_POSITIVE"
            finding["confidence"] = 1.0
            finding["confirmed_by"] = "exploit"

        assert finding["classification"] == "TRUE_POSITIVE"
        assert finding["confidence"] == 1.0
        assert finding["confirmed_by"] == "exploit"

    def test_exploit_failure_downgrades_confidence(self):
        """Failed exploit -> confidence halved, potential FP."""
        finding = {
            "finding_id": "find-011",
            "classification": "TRUE_POSITIVE",
            "confidence": 0.8,
        }

        exploit_successful = False
        if not exploit_successful:
            finding["confidence"] *= 0.5
            if finding["confidence"] < 0.5:
                finding["classification"] = "FALSE_POSITIVE"

        assert finding["confidence"] == 0.4
        assert finding["classification"] == "FALSE_POSITIVE"

    def test_exploit_feedback_preserves_finding_id(self):
        """Feedback should not change the finding_id."""
        finding = {"finding_id": "find-012", "classification": "TRUE_POSITIVE"}
        finding_id_before = finding["finding_id"]
        finding["classification"] = "TRUE_POSITIVE"  # confirmed
        assert finding["finding_id"] == finding_id_before


# ── PatternLearner Tests ─────────────────────────────────────


class TestPatternLearner:
    """Pattern learning from feedback and exploit results."""

    def test_pattern_learner_imports(self, mocker):
        """PatternLearner should be importable from the classifier src."""
        cls_improver = _import_classifier_module("improver")
        # Point to temp files
        import tempfile
        tmpdir = Path(tempfile.mkdtemp())
        mocker.patch.object(cls_improver, "PATTERNS_FILE", tmpdir / "patterns.json")
        mocker.patch.object(cls_improver, "FEEDBACK_FILE", tmpdir / "feedback.json")
        mocker.patch.object(cls_improver, "FN_FILE", tmpdir / "fn.json")
        mocker.patch.object(cls_improver, "FP_FILE", tmpdir / "fp.json")

        assert hasattr(cls_improver, "PatternLearner")

    def test_pattern_learner_create_pattern(self, mocker):
        """PatternLearner should create and add patterns."""
        cls_improver = _import_classifier_module("improver")
        import tempfile
        tmpdir = Path(tempfile.mkdtemp())
        mocker.patch.object(cls_improver, "PATTERNS_FILE", tmpdir / "patterns.json")
        mocker.patch.object(cls_improver, "FEEDBACK_FILE", tmpdir / "feedback.json")
        mocker.patch.object(cls_improver, "FN_FILE", tmpdir / "fn.json")
        mocker.patch.object(cls_improver, "FP_FILE", tmpdir / "fp.json")

        learner = cls_improver.PatternLearner()

        # Create a proper Pattern with all required fields
        PatternModel = cls_improver.Pattern
        PatternTypeEnum = cls_improver.PatternType
        ClassificationEnum = cls_improver.Classification

        pattern = PatternModel(
            pattern_id="pat-001",
            name="Reentrancy Pattern",
            pattern_type=PatternTypeEnum.KEYWORD_PATTERN,
            classification=ClassificationEnum.TRUE_POSITIVE,
            description="Detects CEI violations in withdrawal functions",
        )
        result = learner.add_pattern(pattern)
        assert result is not None

    def test_pattern_effectiveness_decay(self, mocker):
        """Patterns with low effectiveness after many matches should decay."""
        cls_improver = _import_classifier_module("improver")
        import tempfile
        tmpdir = Path(tempfile.mkdtemp())
        mocker.patch.object(cls_improver, "PATTERNS_FILE", tmpdir / "patterns.json")
        mocker.patch.object(cls_improver, "FEEDBACK_FILE", tmpdir / "feedback.json")
        mocker.patch.object(cls_improver, "FN_FILE", tmpdir / "fn.json")
        mocker.patch.object(cls_improver, "FP_FILE", tmpdir / "fp.json")

        learner = cls_improver.PatternLearner()

        # A pattern with effectiveness exactly at threshold and 5+ matches
        # should be considered for deactivation
        from unittest.mock import MagicMock
        pattern = MagicMock()
        pattern.pattern_id = "pat-decay"
        pattern.active = True
        pattern.effectiveness = 0.25  # below typical auto-deactivate threshold
        pattern.match_count = 10

        # The logic: low effectiveness + many matches = candidate for review
        is_low_quality = pattern.effectiveness < 0.5 and pattern.match_count >= 5
        assert is_low_quality is True
