# Echidna P0/P1 Fix Implementation Plan

> **For Opencode:** Dispatch each task to a subagent with full context.

**Goal:** Fix critical bugs and add test coverage for 04b-scanner-echidna service

**Architecture:** Three self-contained tasks targeting:
1. Bug fix in `agent.py` — wrong parameter passed to `EchidnaRunner.run()`
2. Bug fix in `app.py` — intelligence enrichment runs unreliably
3. New test file for all 5 intelligence modules (classifier, scorer, fixer, path_predictor, NLP)

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, pytest, structlog

---

## Task 1: Fix agent.py — Parameter Mismatch in EchidnaAgent

**Objective:** Fix `EchidnaAgent._execute_task()` passing `sources={...}` dict instead of `source_dir: Path` to `EchidnaRunner.run()`

**Files:**
- Modify: `services/04b-scanner-echidna/src/agent.py:76-86`

**Current broken code (lines 76-86):**
```python
for file_path, source_code in sources.items():
    target = audit_dir / file_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source_code, encoding="utf-8")

start = time.monotonic()
result = await asyncio.to_thread(
    self._runner.run,
    sources={k: (audit_dir / k).read_text() for k in sources},  # ❌ BUG: wrong param
    timeout=data.get("timeout", 600),
    contract_address=data.get("contract_address"),
)
```

**Fix:**
Replace the `self._runner.run()` call with correct parameters matching `EchidnaRunner.run(source_dir, contract_name, config, timeout)`:

```python
result = await asyncio.to_thread(
    self._runner.run,
    audit_dir,                                   # ✅ source_dir: Path
    contract_name=data.get("contract_name"),     # ✅ contract_name
    timeout=data.get("timeout", 600),            # ✅ timeout
)
```

**Verification:**
- `cd /mnt/e/website/project/sc_auditor && python -c "from services.<…> import …"` — no import errors
- Check types match `EchidnaRunner.run(source_dir, contract_name, config, timeout)`

---

## Task 2: Fix app.py — Intelligence Enrichment Reliability

**Objective:** Fix condition `result.success and result.findings` — Echidna may return `success=True` BUT still have findings (property violations don't cause non-zero exit code). Enrichment should run when findings exist, regardless of `success` flag.

**Files:**
- Modify: `services/04b-scanner-echidna/app.py:280-299`

**Current buggy code:**
```python
# ── Intelligence enrichment ────────────────────────
if result.success and result.findings:
```

**Fix:**
Change condition to only check findings exist:
```python
# ── Intelligence enrichment ────────────────────────
if result.findings:
```

**Verification:**
- Review logic: enrichment runs when findings exist, regardless of `success` flag
- Check that `finding_dicts` creation won't crash on empty findings

---

## Task 3: Unit Tests for Intelligence Modules

**Objective:** Create comprehensive unit tests for all 5 intelligence modules

**Files:**
- Create: `tests/04b-scanner-echidna/test_classifier.py`
- Create: `tests/04b-scanner-echidna/test_scorer.py`
- Create: `tests/04b-scanner-echidna/test_fixer.py`
- Create: `tests/04b-scanner-echidna/test_path_predictor.py`
- Create: `tests/04b-scanner-echidna/test_nlp.py`
- Create: `tests/04b-scanner-echidna/__init__.py`

### Task 3a: Test Classifier

**Files:**
- Create: `tests/04b-scanner-echidna/test_classifier.py`

**Test cases to write:**

```python
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
        cat = self.classifier.classify(test_function="echidna_supply_cap")
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
        assert len(cats) >= 9  # at least 9 categories
        names = [c["name"] for c in cats]
        assert "reentrancy" in names
        assert "access_control" in names
        assert "unknown" in names
```

### Task 3b: Test Scorer

**Files:**
- Create: `tests/04b-scanner-echidna/test_scorer.py`

```python
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
            "failing_input": "transfer(0x1234)\nwithdraw(100)\n",
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
        assert scores[0].normalized_score >= scores[1].normalized_score  # sorted desc

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
```

### Task 3c: Test Fixer

**Files:**
- Create: `tests/04b-scanner-echidna/test_fixer.py`

```python
"""Tests for EchidnaFixer."""
import pytest
from src.intelligence.fixer import EchidnaFixer, FixSuggestion, create_fixer

class TestEchidnaFixer:
    def setup_method(self):
        self.fixer = create_fixer()

    def test_generate_fix_reentrancy(self):
        fix = self.fixer.generate_fix("reentrancy", "Reentrancy in withdraw", "critical")
        assert fix.category == "reentrancy"
        assert "Checks-Effects-Interactions" in fix.description
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
        assert fix.confidence == 0.4  # low confidence for unknown

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
```

### Task 3d: Test Path Predictor

**Files:**
- Create: `tests/04b-scanner-echidna/test_path_predictor.py`

```python
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
```

### Task 3e: Test NLP

**Files:**
- Create: `tests/04b-scanner-echidna/test_nlp.py`

```python
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
```

---

## Execution Order

Tasks are independent and can run in parallel:

```
Task 1: Fix agent.py          ─┐
                               ├──▶ All 3 can run in parallel
Task 2: Fix app.py            ─┤
                               │
Task 3a-3e: Test files        ─┘
```

**After all tasks complete:** Run `pytest tests/04b-scanner-echidna/ -v` to verify all tests pass.
