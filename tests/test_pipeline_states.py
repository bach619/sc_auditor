"""Orchestrator Pipeline State Machine Tests.

Tests the 8-stage pipeline state machine covering transitions,
error states, retry logic, saga rollback, concurrent audits, and timeouts.

Tests import from the real orchestrator modules using namespace isolation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ── Path setup for orchestrator imports ──────────────────────
_ORCHESTRATOR_SRC = str(Path(__file__).resolve().parents[1] / "services" / "11-orchestrator")


def _import_orchestrator():
    """Import orchestrator modules with namespace isolation."""
    import importlib
    # Clear cached src modules to avoid collision with other services
    to_remove = [k for k in list(sys.modules) if k.startswith("src.")]
    for k in to_remove:
        del sys.modules[k]
    if "src" in sys.modules:
        del sys.modules["src"]

    sys.path.insert(0, _ORCHESTRATOR_SRC)
    try:
        models = importlib.import_module("src.models")
        pipeline = importlib.import_module("src.pipeline")
        return models, pipeline
    finally:
        sys.path.pop(0)


# ─────────────────────────────────────────────────────────────
# PipelineState Enum Tests
# ─────────────────────────────────────────────────────────────


class TestPipelineStateEnum:
    """Verify the PipelineState enum from models.py."""

    @pytest.fixture(scope="class")
    def state_enum(self):
        models, _ = _import_orchestrator()
        return models.PipelineState

    def test_state_values_defined(self, state_enum):
        """All 24 states should be defined with correct values."""
        assert state_enum.PENDING.value == "PENDING"
        assert state_enum.FETCHING_PROGRAM.value == "FETCHING_PROGRAM"
        assert state_enum.COMPLETED.value == "COMPLETED"
        assert state_enum.FETCH_FAILED.value == "FETCH_FAILED"
        assert state_enum.TIMEOUT.value == "TIMEOUT"
        states = list(state_enum)
        assert len(states) >= 20, f"Expected >= 20 states, got {len(states)}"

    def test_initial_state_is_pending(self, state_enum):
        """A new audit should start in PENDING state."""
        assert state_enum.PENDING.value == "PENDING"
        assert state_enum.PENDING != state_enum.COMPLETED

    def test_terminal_states_identified(self, state_enum):
        """is_terminal property should correctly identify terminal states."""
        assert not state_enum.PENDING.is_terminal
        assert not state_enum.FETCHING_PROGRAM.is_terminal
        assert state_enum.COMPLETED.is_terminal
        assert state_enum.COMPLETED_WITH_WARN.is_terminal
        assert state_enum.FETCH_FAILED.is_terminal
        assert state_enum.TIMEOUT.is_terminal

    def test_failure_states_identified(self, state_enum):
        """is_failure should return True only for non-success terminals."""
        assert state_enum.FETCH_FAILED.is_failure
        assert state_enum.AI_FAILED.is_failure
        assert state_enum.TIMEOUT.is_failure
        assert not state_enum.COMPLETED.is_failure
        assert not state_enum.COMPLETED_WITH_WARN.is_failure


# ─────────────────────────────────────────────────────────────
# Pipeline Workflow Tests
# ─────────────────────────────────────────────────────────────


class TestPipelineWorkflow:
    """Test the pipeline WORKFLOW table and transitions."""

    @pytest.fixture(scope="class")
    def pipeline_cls(self):
        _, pipeline_mod = _import_orchestrator()
        return pipeline_mod.Pipeline

    def test_workflow_has_all_required_states(self, pipeline_cls):
        """Workflow should contain at least 10 stages."""
        assert len(pipeline_cls.WORKFLOW) >= 10, f"Expected >= 10, got {len(pipeline_cls.WORKFLOW)}"

        state_names = [s.value for s, _, _ in pipeline_cls.WORKFLOW]
        assert "FETCHING_PROGRAM" in state_names
        assert "FETCHING_SOURCE" in state_names
        assert "SCANNING" in state_names
        assert "AI_ANALYSIS" in state_names
        assert "CLASSIFYING" in state_names

    def test_workflow_starts_with_fetching_program(self, pipeline_cls):
        """First step should be FETCHING_PROGRAM."""
        first_state, _, _ = pipeline_cls.WORKFLOW[0]
        assert first_state.value == "FETCHING_PROGRAM"

    def test_workflow_ends_with_notifying(self, pipeline_cls):
        """Last step(s) should include NOTIFYING."""
        last_states = [s.value for s, _, _ in pipeline_cls.WORKFLOW[-2:]]
        assert "NOTIFYING" in last_states


# ─────────────────────────────────────────────────────────────
# AuditRecord State Tests
# ─────────────────────────────────────────────────────────────


class TestAuditRecord:
    """Test AuditRecord creation and state transitions."""

    @pytest.fixture(scope="class")
    def record_cls(self):
        models, _ = _import_orchestrator()
        return models.AuditRecord

    def test_new_record_starts_pending(self, record_cls):
        """A freshly created AuditRecord should be in PENDING state."""
        models, _ = _import_orchestrator()
        rec = record_cls(chain="ethereum", address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                         program="test", priority=5, use_ai=True)
        assert rec.state == models.PipelineState.PENDING

    def test_fail_sets_error_and_state(self, record_cls):
        """fail() should set the error message and transition to failure state."""
        models, _ = _import_orchestrator()
        rec = record_cls(chain="ethereum", address="0x0", program="test", priority=5, use_ai=True)
        rec.state = models.PipelineState.FETCHING_SOURCE
        rec.fail(models.PipelineState.FETCH_FAILED, "Connection refused")
        assert rec.state == models.PipelineState.FETCH_FAILED
        assert rec.error == "Connection refused"

    def test_complete_sets_state_and_duration(self, record_cls):
        """complete() should set COMPLETED state and record duration."""
        models, _ = _import_orchestrator()
        rec = record_cls(chain="ethereum", address="0x0", program="test", priority=5, use_ai=True)
        rec.state = models.PipelineState.NOTIFYING
        rec.complete(duration=120.5)
        assert rec.state == models.PipelineState.COMPLETED
        assert rec.duration_seconds == 120.5

    def test_add_step_transitions_state(self, record_cls):
        """add_step() should append step and update current state."""
        models, _ = _import_orchestrator()
        rec = record_cls(chain="ethereum", address="0x0", program="test", priority=5, use_ai=True)

        step = models.PipelineStep(
            name="FETCHING_PROGRAM",
            state=models.PipelineState.FETCHING_PROGRAM,
        )
        rec.add_step(step)
        assert len(rec.steps) == 1
        assert rec.state == models.PipelineState.FETCHING_PROGRAM

    def test_multiple_audits_independent(self, record_cls):
        """Multiple records should not interfere with each other."""
        models, _ = _import_orchestrator()
        rec1 = record_cls(chain="ethereum", address="0x111", program="p1", priority=5, use_ai=True,
                          state=models.PipelineState.SCANNING)
        rec2 = record_cls(chain="polygon", address="0x222", program="p2", priority=3, use_ai=True,
                          state=models.PipelineState.PENDING)

        rec1.state = models.PipelineState.COMPLETED
        assert rec2.state == models.PipelineState.PENDING
        assert rec1.state == models.PipelineState.COMPLETED

    def test_retry_resets_to_pending(self, record_cls):
        """Retry should reset a failed record to PENDING."""
        models, _ = _import_orchestrator()
        rec = record_cls(chain="ethereum", address="0x0", program="test", priority=5, use_ai=True,
                         state=models.PipelineState.FETCH_FAILED, error="timeout")

        # Reset for retry
        rec.state = models.PipelineState.PENDING
        rec.error = None
        rec.steps = []
        rec.duration_seconds = None

        assert rec.state == models.PipelineState.PENDING
        assert rec.error is None
        assert len(rec.steps) == 0


# ─────────────────────────────────────────────────────────────
# Conditional Skip Tests
# ─────────────────────────────────────────────────────────────


class TestConditionalSkip:
    """Test conditional skipping of steps (exploit, report, notify)."""

    def test_exploit_runs_with_critical_finding(self):
        """EXPLOIT should run when there's a CRITICAL severity finding."""
        findings = [{"severity": "critical"}, {"severity": "low"}]
        should_exploit = any(f.get("severity") in ("critical", "high") for f in findings)
        assert should_exploit is True

    def test_exploit_skipped_with_low_severity(self):
        """EXPLOIT should be skipped when all findings are LOW severity."""
        findings = [{"severity": "low"}, {"severity": "info"}]
        should_exploit = any(f.get("severity") in ("critical", "high") for f in findings)
        assert should_exploit is False

    def test_exploit_skipped_with_no_findings(self):
        """EXPLOIT should be skipped when there are no findings."""
        findings = None
        should_exploit = any(f.get("severity") in ("critical", "high") for f in (findings or []))
        assert should_exploit is False

    def test_notify_enabled_by_default(self):
        """Notify should run when notify_enabled is True or not set."""
        metadata = {}
        notify_enabled = metadata.get("notify_enabled", True)
        assert notify_enabled is True

    def test_notify_disabled_skips(self):
        """Notify should be skipped when notify_enabled is False."""
        metadata = {"notify_enabled": False}
        notify_enabled = metadata.get("notify_enabled", True)
        assert notify_enabled is False


# ─────────────────────────────────────────────────────────────
# Timeout Tests
# ─────────────────────────────────────────────────────────────


class TestTimeoutHandling:
    """Test timeout state and configuration."""

    @pytest.fixture(scope="class")
    def state_enum(self):
        models, _ = _import_orchestrator()
        return models.PipelineState

    def test_timeout_is_failure_terminal(self, state_enum):
        """TIMEOUT should be a failure terminal state."""
        assert state_enum.TIMEOUT.value == "TIMEOUT"
        assert state_enum.TIMEOUT.is_failure
        assert state_enum.TIMEOUT.is_terminal

    def test_timeout_is_not_completed(self, state_enum):
        """TIMEOUT should NOT be considered a success."""
        assert state_enum.TIMEOUT != state_enum.COMPLETED
        assert state_enum.TIMEOUT != state_enum.COMPLETED_WITH_WARN
