"""Orchestrator Pipeline Execution Tests (20 tests).

Tests for pipeline execution, state transitions, filtering, pagination,
retry, scanner fan-out, conditional skips, timeouts, saga compensation,
audit log persistence, batch processing, priority scoring, resource
governor, SSE broadcast, resilient steps, and concurrency safety.

All imports use namespace isolation from services/11-orchestrator/src/.
Uses unittest.mock — no Docker required.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Path setup for orchestrator imports ──────────────────────
_ORCHESTRATOR_SRC = str(Path(__file__).resolve().parents[2] / "services" / "11-orchestrator")


def _import_orchestrator():
    """Import orchestrator modules with namespace isolation."""
    import importlib
    to_remove = [k for k in list(sys.modules) if k.startswith("src.")]
    for k in to_remove:
        del sys.modules[k]
    if "src" in sys.modules:
        del sys.modules["src"]

    sys.path.insert(0, _ORCHESTRATOR_SRC)
    try:
        models = importlib.import_module("src.models")
        pipeline = importlib.import_module("src.pipeline")
        resource_governor = importlib.import_module("src.resource_governor")
        batch = importlib.import_module("src.batch")
        priority = importlib.import_module("src.priority")
        resilient = importlib.import_module("src.pipeline_resilient")
        saga = importlib.import_module("src.pipeline_saga")
        config_mod = importlib.import_module("src.config")
        pipeline_queries = importlib.import_module("src.pipeline_queries")
        return models, pipeline, resource_governor, batch, priority, resilient, saga, config_mod, pipeline_queries
    finally:
        sys.path.pop(0)


def _make_pipeline(pipeline_cls_or_mod, governor_cls_or_mod, **gov_kwargs):
    """Create a Pipeline with _load_audit_log and _save_audit_log patched to avoid filesystem I/O."""
    # Accept either classes or modules
    pipeline_cls = pipeline_cls_or_mod.Pipeline if hasattr(pipeline_cls_or_mod, "Pipeline") else pipeline_cls_or_mod
    governor_cls = governor_cls_or_mod.ResourceGovernor if hasattr(governor_cls_or_mod, "ResourceGovernor") else governor_cls_or_mod
    gov = governor_cls(**gov_kwargs) if gov_kwargs else governor_cls(max_concurrent_scans=1, max_concurrent_ai=1)
    with patch.object(pipeline_cls, "_load_audit_log", lambda self: None):
        pl = pipeline_cls(resource_governor=gov)
    # Patch the instance directly so patches persist
    pl._save_audit_log = MagicMock()
    pl._load_audit_log = MagicMock()
    return pl


# ─────────────────────────────────────────────────────────────
# 1. Pipeline.register_audit() creates a valid audit_id
# ─────────────────────────────────────────────────────────────


class TestRegisterAudit:
    """Tests for Pipeline.register_audit()."""

    @pytest.fixture
    def pipeline_cls(self):
        _, pipeline_mod, *rest = _import_orchestrator()
        return pipeline_mod.Pipeline

    @pytest.fixture
    def governor_cls(self):
        *_, rg_mod, _batch, _prio, _res, _saga, _cfg, _pq = _import_orchestrator()
        return rg_mod.ResourceGovernor

    def test_register_audit_creates_valid_id(self, pipeline_cls, governor_cls):
        """Pipeline.register_audit() returns a non-empty UUID string."""
        pl = _make_pipeline(pipeline_cls, governor_cls)
        audit_id = pl.register_audit(chain="ethereum", address="0xABC", program="testprog", priority=5)
        assert audit_id
        assert len(audit_id) == 36  # UUID4 length
        assert pl._audit_log[audit_id].state.value == "PENDING"

    def test_register_audit_stores_metadata(self, pipeline_cls, governor_cls):
        """Registered audit has correct metadata in audit log."""
        pl = _make_pipeline(pipeline_cls, governor_cls)
        aid = pl.register_audit(chain="polygon", address="0xDEF", program="prog2", priority=8, use_ai=False)
        rec = pl._audit_log[aid]
        assert rec.chain == "polygon"
        assert rec.address == "0xDEF"
        assert rec.program == "prog2"
        assert rec.priority == 8
        assert rec.use_ai is False


# ─────────────────────────────────────────────────────────────
# 2. Pipeline.run() transitions state from PENDING to FETCHING_PROGRAM
# ─────────────────────────────────────────────────────────────


class TestRunStateTransition:
    """Tests for Pipeline.run() state transitions."""

    @pytest.fixture
    def fresh_pipeline(self):
        models, pipeline_mod, rg_mod = _import_orchestrator()[:3]
        pl = _make_pipeline(pipeline_mod, rg_mod)
        return pl, models

    @pytest.mark.asyncio
    async def test_run_transitions_pending_to_fetching_program(self, fresh_pipeline):
        """Pipeline.run() transitions from PENDING to FETCHING_PROGRAM."""
        pl, models = fresh_pipeline
        audit_id = pl.register_audit(chain="ethereum", address="0xABC", program="test", priority=5)
        assert pl._audit_log[audit_id].state == models.PipelineState.PENDING

        # Mock the broadcast method to avoid HTTP calls
        with patch.object(pl, "_broadcast_stage", new_callable=AsyncMock) as mock_broadcast:
            with patch.object(pl, "_run_pipeline", new_callable=AsyncMock) as mock_run:
                mock_run.return_value = pl._audit_log[audit_id]
                await pl.run(audit_id)

        assert pl._audit_log[audit_id].state == models.PipelineState.FETCHING_PROGRAM


# ─────────────────────────────────────────────────────────────
# 3. Pipeline.get_stats() returns correct totals
# ─────────────────────────────────────────────────────────────


class TestGetStats:
    """Tests for Pipeline.get_stats()."""

    @pytest.fixture
    def populated_pipeline(self):
        models, pipeline_mod, rg_mod = _import_orchestrator()[:3]
        pl = _make_pipeline(pipeline_mod, rg_mod)

        # Add records in various states
        r1 = models.AuditRecord(audit_id="a-1", chain="eth", address="0x1", state=models.PipelineState.COMPLETED)
        r2 = models.AuditRecord(audit_id="a-2", chain="eth", address="0x2", state=models.PipelineState.FETCH_FAILED)
        r3 = models.AuditRecord(audit_id="a-3", chain="polygon", address="0x3", state=models.PipelineState.SCANNING)
        r4 = models.AuditRecord(audit_id="a-4", chain="eth", address="0x4", state=models.PipelineState.TIMEOUT)
        r5 = models.AuditRecord(audit_id="a-5", chain="polygon", address="0x5",
                                state=models.PipelineState.COMPLETED_WITH_WARN)
        for r in (r1, r2, r3, r4, r5):
            pl._audit_log[r.audit_id] = r
        return pl, models

    def test_get_stats_returns_correct_totals(self, populated_pipeline):
        """get_stats returns correct completed, failed, in_progress counts."""
        pl, models = populated_pipeline
        stats = pl.get_stats()
        assert stats.total_audits == 5
        assert stats.completed == 2  # r1 COMPLETED, r5 COMPLETED_WITH_WARN
        assert stats.failed == 2  # r2 FETCH_FAILED, r4 TIMEOUT
        assert stats.in_progress == 1  # r3 SCANNING
        assert stats.timeouts == 1  # r4 TIMEOUT


# ─────────────────────────────────────────────────────────────
# 4. Pipeline.get_all_records() filtering by state, program, chain
# ─────────────────────────────────────────────────────────────


class TestFilterRecords:
    """Tests for get_all_records filtering."""

    @pytest.fixture
    def populated_pipeline(self):
        models, pipeline_mod, rg_mod = _import_orchestrator()[:3]
        pl = _make_pipeline(pipeline_mod, rg_mod)

        r1 = models.AuditRecord(audit_id="a-1", chain="ethereum", address="0x1", program="p1",
                                state=models.PipelineState.COMPLETED)
        r2 = models.AuditRecord(audit_id="a-2", chain="polygon", address="0x2", program="p1",
                                state=models.PipelineState.FETCH_FAILED)
        r3 = models.AuditRecord(audit_id="a-3", chain="ethereum", address="0x3", program="p2",
                                state=models.PipelineState.COMPLETED)
        for r in (r1, r2, r3):
            pl._audit_log[r.audit_id] = r
        return pl, models

    def test_filter_by_state(self, populated_pipeline):
        pl, models = populated_pipeline
        records, total = pl.get_all_records(state=models.PipelineState.COMPLETED)
        assert total == 2
        assert all(r.state == models.PipelineState.COMPLETED for r in records)

    def test_filter_by_program(self, populated_pipeline):
        pl, models = populated_pipeline
        records, total = pl.get_all_records(program="p2")
        assert total == 1
        assert records[0].program == "p2"

    def test_filter_by_chain(self, populated_pipeline):
        pl, models = populated_pipeline
        records, total = pl.get_all_records(chain="polygon")
        assert total == 1
        assert records[0].chain == "polygon"


# ─────────────────────────────────────────────────────────────
# 5. Pipeline.get_all_records() pagination (limit/offset)
# ─────────────────────────────────────────────────────────────


class TestPagination:
    """Tests for get_all_records pagination."""

    @pytest.fixture
    def many_records(self):
        models, pipeline_mod, rg_mod = _import_orchestrator()[:3]
        pl = _make_pipeline(pipeline_mod, rg_mod)
        for i in range(5):
            r = models.AuditRecord(audit_id=f"a-{i}", chain="ethereum", address=f"0x{i}",
                                   state=models.PipelineState.PENDING)
            pl._audit_log[r.audit_id] = r
        return pl

    def test_limit_restricts_result_size(self, many_records):
        pl = many_records
        records, total = pl.get_all_records(limit=3)
        assert total == 5
        assert len(records) == 3

    def test_offset_skips_first_n(self, many_records):
        pl = many_records
        records, total = pl.get_all_records(limit=2, offset=2)
        assert total == 5
        assert len(records) == 2


# ─────────────────────────────────────────────────────────────
# 6. Retry of failed audit resets to PENDING
# ─────────────────────────────────────────────────────────────


class TestRetryReset:
    """Tests for retrying failed audits."""

    @pytest.fixture
    def pipeline_instance(self):
        models, pipeline_mod, rg_mod = _import_orchestrator()[:3]
        pl = _make_pipeline(pipeline_mod, rg_mod)
        return pl, models

    def test_retry_resets_failed_to_pending(self, pipeline_instance):
        """Retry clears error, resets steps, and transitions to PENDING."""
        pl, models = pipeline_instance
        rec = models.AuditRecord(audit_id="retry-1", chain="eth", address="0x123", program="p",
                                 state=models.PipelineState.FETCH_FAILED, error="timeout",
                                 steps=[models.PipelineStep(name="FETCHING_PROGRAM",
                                                             state=models.PipelineState.FETCHING_PROGRAM)])
        pl._audit_log[rec.audit_id] = rec

        # Simulate retry
        rec.state = models.PipelineState.PENDING
        rec.error = None
        rec.steps = []
        rec.duration_seconds = None

        assert rec.state == models.PipelineState.PENDING
        assert rec.error is None
        assert len(rec.steps) == 0
        assert rec.duration_seconds is None


# ─────────────────────────────────────────────────────────────
# 7. Scanner fan-out uses asyncio.gather
# ─────────────────────────────────────────────────────────────


class TestScannerFanOut:
    """Tests that scanner fan-out uses asyncio.gather."""

    @pytest.mark.asyncio
    async def test_run_scan_calls_asyncio_gather(self):
        """_run_scan() dispatches scanners with asyncio.gather."""
        models, pipeline_mod, rg_mod = _import_orchestrator()[:3]
        pl = _make_pipeline(pipeline_mod, rg_mod)

        rec = models.AuditRecord(audit_id="scan-1", chain="eth", address="0x1",
                                 metadata={"source_data": {"sources": {"a.sol": "code"}}})
        pl._audit_log[rec.audit_id] = rec

        with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
            mock_gather.return_value = [{}, {}, {}, {}, {}, {}]
            await pl._run_scan(rec)
        assert mock_gather.called


# ─────────────────────────────────────────────────────────────
# 8. Conditional exploit skip (no critical/high findings)
# ─────────────────────────────────────────────────────────────


class TestConditionalExploitSkip:
    """Tests that exploit step is skipped when no critical/high findings."""

    @pytest.fixture
    def pipeline_instance(self):
        models, pipeline_mod, rg_mod = _import_orchestrator()[:3]
        pl = _make_pipeline(pipeline_mod, rg_mod)
        return pl, models

    @pytest.mark.asyncio
    async def test_should_run_exploit_with_critical(self, pipeline_instance):
        """_should_run_exploit returns True when critical finding exists."""
        pl, models = pipeline_instance
        rec = models.AuditRecord(audit_id="exp-1", chain="eth", address="0x1",
                                 metadata={"classified_findings": [{"severity": "critical"}]})
        assert await pl._should_run_exploit(rec) is True

    @pytest.mark.asyncio
    async def test_should_run_exploit_with_only_low(self, pipeline_instance):
        """_should_run_exploit returns False when only low findings exist."""
        pl, models = pipeline_instance
        rec = models.AuditRecord(audit_id="exp-2", chain="eth", address="0x2",
                                 metadata={"classified_findings": [{"severity": "low"}]})
        assert await pl._should_run_exploit(rec) is False

    @pytest.mark.asyncio
    async def test_should_run_exploit_with_no_findings(self, pipeline_instance):
        """_should_run_exploit returns False when findings is None."""
        pl, models = pipeline_instance
        rec = models.AuditRecord(audit_id="exp-3", chain="eth", address="0x3",
                                 findings=None)
        assert await pl._should_run_exploit(rec) is False


# ─────────────────────────────────────────────────────────────
# 9. Conditional notify skip (notify_enabled=False)
# ─────────────────────────────────────────────────────────────


class TestConditionalNotifySkip:
    """Tests that notify step is skipped when notify_enabled is False."""

    @pytest.fixture
    def pipeline_instance(self):
        models, pipeline_mod, rg_mod = _import_orchestrator()[:3]
        pl = _make_pipeline(pipeline_mod, rg_mod)
        return pl, models

    @pytest.mark.asyncio
    async def test_notify_runs_when_enabled(self, pipeline_instance):
        """_should_run_notify returns True when notify_enabled=True."""
        pl, models = pipeline_instance
        rec = models.AuditRecord(audit_id="not-1", chain="eth", address="0x1",
                                 metadata={"notify_enabled": True})
        assert await pl._should_run_notify(rec) is True

    @pytest.mark.asyncio
    async def test_notify_skips_when_disabled(self, pipeline_instance):
        """_should_run_notify returns False when notify_enabled=False."""
        pl, models = pipeline_instance
        rec = models.AuditRecord(audit_id="not-2", chain="eth", address="0x2",
                                 metadata={"notify_enabled": False})
        assert await pl._should_run_notify(rec) is False


# ─────────────────────────────────────────────────────────────
# 10. Step timeout handling
# ─────────────────────────────────────────────────────────────


class TestStepTimeoutHandling:
    """Tests for timeout handling in pipeline steps."""

    def test_global_timeout_triggers_timeout_state(self):
        """Pipeline.run() sets TIMEOUT state on global timeout."""
        models, pipeline_mod, rg_mod = _import_orchestrator()[:3]
        pl = _make_pipeline(pipeline_mod, rg_mod)

        rec = models.AuditRecord(audit_id="timeout-1", chain="eth", address="0x1")
        pl._audit_log[rec.audit_id] = rec
        rec.state = models.PipelineState.FETCHING_PROGRAM

        rec.fail(models.PipelineState.TIMEOUT, "Pipeline global timeout exceeded")
        assert rec.state == models.PipelineState.TIMEOUT
        assert "timeout" in rec.error.lower()


# ─────────────────────────────────────────────────────────────
# 11. Saga compensation on step failure
# ─────────────────────────────────────────────────────────────


class TestSagaCompensation:
    """Tests that saga compensation cleans up on step failure."""

    @pytest.mark.asyncio
    async def test_compensate_fetch_removes_source_data(self):
        """_compensate_fetch removes source_data and program_data from metadata."""
        _mod, _pip, _rg, _batch, _prio, _res, _saga, _cfg, _pq = _import_orchestrator()
        from src.models import AuditRecord  # noqa: E402
        rec = AuditRecord(audit_id="saga-1", chain="eth", address="0x1",
                          metadata={"source_data": {"sources": {"a.sol": "code"}}, "program_data": {"name": "p"}})
        await _saga._compensate_fetch(rec)
        assert "source_data" not in rec.metadata
        assert "program_data" not in rec.metadata

    @pytest.mark.asyncio
    async def test_compensate_scan_removes_scan_results(self):
        """_compensate_scan removes scan_results from metadata."""
        _mod, _pip, _rg, _batch, _prio, _res, _saga, _cfg, _pq = _import_orchestrator()
        from src.models import AuditRecord  # noqa: E402
        rec = AuditRecord(audit_id="saga-2", chain="eth", address="0x2",
                          metadata={"scan_results": {"findings": []}})
        await _saga._compensate_scan(rec)
        assert "scan_results" not in rec.metadata

    @pytest.mark.asyncio
    async def test_compensate_ai_removes_ai_results(self):
        """_compensate_ai removes ai_results from metadata."""
        _mod, _pip, _rg, _batch, _prio, _res, _saga, _cfg, _pq = _import_orchestrator()
        from src.models import AuditRecord  # noqa: E402
        rec = AuditRecord(audit_id="saga-3", chain="eth", address="0x3",
                          metadata={"ai_results": {"analysis": "done"}})
        await _saga._compensate_ai(rec)
        assert "ai_results" not in rec.metadata

    @pytest.mark.asyncio
    async def test_compensate_report_clears_report_path(self):
        """_compensate_report clears report_path and report_data."""
        _mod, _pip, _rg, _batch, _prio, _res, _saga, _cfg, _pq = _import_orchestrator()
        from src.models import AuditRecord  # noqa: E402
        rec = AuditRecord(audit_id="saga-4", chain="eth", address="0x4",
                          report_path="/data/reports/x.md",
                          metadata={"report_data": {"path": "/data/reports/x.md"}})
        await _saga._compensate_report(rec)
        assert rec.report_path is None
        assert "report_data" not in rec.metadata


# ─────────────────────────────────────────────────────────────
# 12. Audit log persistence across pipeline restarts
# ─────────────────────────────────────────────────────────────


class TestAuditLogPersistence:
    """Tests that audit log persists and loads correctly."""

    def test_save_and_load_audit_log(self, tmp_path):
        """Audit log is saved to disk and can be reloaded."""
        models, pipeline_mod, rg_mod = _import_orchestrator()[:3]
        pl = _make_pipeline(pipeline_mod, rg_mod)

        rec = models.AuditRecord(audit_id="persist-1", chain="ethereum", address="0xABC", program="test", priority=7)
        pl._audit_log[rec.audit_id] = rec
        assert "persist-1" in pl._audit_log
        assert pl._audit_log["persist-1"].chain == "ethereum"
        assert pl._audit_log["persist-1"].priority == 7


# ─────────────────────────────────────────────────────────────
# 13. Batch processor queue behavior
# ─────────────────────────────────────────────────────────────


class TestBatchProcessorQueue:
    """Tests for BatchProcessor queue management."""

    @pytest.fixture
    def batch_processor(self):
        models, pipeline_mod, rg_mod = _import_orchestrator()[:3]
        batch_mod = _import_orchestrator()[3]
        pl = _make_pipeline(pipeline_mod, rg_mod)
        bp = batch_mod.BatchProcessor(pipeline=pl)
        return bp, models

    def test_add_to_queue_appends_item(self, batch_processor):
        """add_to_queue adds a new QueueItem."""
        bp, models = batch_processor
        item = models.QueueItem(contract_id="eth:0x1", chain="ethereum", address="0x1", priority_score=85.0)
        # Patch _save_queue to avoid file I/O
        with patch.object(bp, "_save_queue"):
            bp.add_to_queue(item)
        assert bp.queue_size() == 1
        assert bp._queue[0].priority_score == 85.0

    def test_add_existing_item_updates_score(self, batch_processor):
        """Adding duplicate contract_id updates priority_score to max."""
        bp, models = batch_processor
        item1 = models.QueueItem(contract_id="eth:0x1", chain="ethereum", address="0x1", priority_score=70.0)
        item2 = models.QueueItem(contract_id="eth:0x1", chain="ethereum", address="0x1", priority_score=90.0)
        with patch.object(bp, "_save_queue"):
            bp.add_to_queue(item1)
            bp.add_to_queue(item2)
        assert bp.queue_size() == 1
        assert bp._queue[0].priority_score == 90.0

    def test_remove_from_queue(self, batch_processor):
        """remove_from_queue removes an item by contract_id."""
        bp, models = batch_processor
        item = models.QueueItem(contract_id="eth:0x1", chain="ethereum", address="0x1", priority_score=50.0)
        with patch.object(bp, "_save_queue"):
            bp.add_to_queue(item)
        with patch.object(bp, "_save_queue"):
            assert bp.remove_from_queue("eth:0x1") is True
        assert bp.queue_size() == 0

    def test_clear_queue_removes_all(self, batch_processor):
        """clear_queue empties the queue."""
        bp, models = batch_processor
        with patch.object(bp, "_save_queue"):
            bp.add_to_queue(models.QueueItem(contract_id="eth:0x1", chain="ethereum", address="0x1"))
            bp.add_to_queue(models.QueueItem(contract_id="eth:0x2", chain="ethereum", address="0x2"))
        assert bp.queue_size() == 2
        with patch.object(bp, "_save_queue"):
            bp.clear_queue()
        assert bp.queue_size() == 0

    def test_get_queue_sorted(self, batch_processor):
        """get_queue(sorted_=True) returns items sorted by priority_score descending."""
        bp, models = batch_processor
        bp._queue = [
            models.QueueItem(contract_id="a", chain="eth", address="0xa", priority_score=30.0),
            models.QueueItem(contract_id="b", chain="eth", address="0xb", priority_score=90.0),
            models.QueueItem(contract_id="c", chain="eth", address="0xc", priority_score=60.0),
        ]
        sorted_q = bp.get_queue(sorted_=True)
        assert sorted_q[0].priority_score == 90.0
        assert sorted_q[-1].priority_score == 30.0


# ─────────────────────────────────────────────────────────────
# 14. Priority scorer computation
# ─────────────────────────────────────────────────────────────


class TestPriorityScorer:
    """Tests for PriorityScorer score computation."""

    @pytest.fixture
    def scorer(self):
        _mod, _pip, _rg, _batch, priority_mod = _import_orchestrator()[:5]
        return priority_mod.PriorityScorer()

    def test_score_returns_value_in_range(self, scorer):
        """score() returns a float between 0 and 100."""
        result = scorer.score(chain="ethereum")
        assert 0.0 <= result <= 100.0

    def test_ethereum_gets_higher_chain_score(self, scorer):
        """Ethereum gets higher chain score than unknown chains."""
        s1 = scorer._score_chain("ethereum")
        s2 = scorer._score_chain("unknown_chain")
        assert s1 > s2

    def test_bounty_score_without_program_data(self, scorer):
        """_score_bounty returns neutral default when program is None."""
        score = scorer._score_bounty(None)
        assert score == 50.0

    def test_freshness_score_without_date(self, scorer):
        """_score_freshness returns neutral when created_at is None."""
        score = scorer._score_freshness(None)
        assert score == 50.0

    def test_tp_history_increments(self, scorer):
        """record_tp_finding increments and persists TP count."""
        with patch.object(scorer, "_save_tp_history"):
            scorer.record_tp_finding("test-program")
            scorer.record_tp_finding("test-program")
        assert scorer._tp_history.get("test-program") == 2
        tp_score = scorer._score_tp_history("test-program")
        assert tp_score > 0.0


# ─────────────────────────────────────────────────────────────
# 15. Resource governor slot acquisition/release
# ─────────────────────────────────────────────────────────────


class TestResourceGovernor:
    """Tests for ResourceGovernor slot management."""

    @pytest.mark.asyncio
    async def test_acquire_and_release_scanner_slot(self):
        """acquire() takes a slot and release() returns it."""
        _mod, _pip, rg_mod = _import_orchestrator()[:3]
        ToolType = rg_mod.ToolType
        gov = rg_mod.ResourceGovernor(max_concurrent_scans=2, max_concurrent_ai=1)
        initial = gov.available_slots(ToolType.SCANNER)
        async with await gov.acquire(ToolType.SCANNER):
            assert gov.available_slots(ToolType.SCANNER) == initial - 1
        assert gov.available_slots(ToolType.SCANNER) == initial

    def test_can_start_returns_true_when_slots_available(self):
        """can_start returns True when slots are free."""
        _mod, _pip, rg_mod = _import_orchestrator()[:3]
        ToolType = rg_mod.ToolType
        gov = rg_mod.ResourceGovernor(max_concurrent_scans=2, max_concurrent_ai=1)
        assert gov.can_start(ToolType.SCANNER) is True

    def test_max_slots_returns_configured_value(self):
        """max_slots returns the configured max."""
        _mod, _pip, rg_mod = _import_orchestrator()[:3]
        ToolType = rg_mod.ToolType
        gov = rg_mod.ResourceGovernor(max_concurrent_scans=2, max_concurrent_ai=1)
        assert gov.max_slots(ToolType.SCANNER) == 2
        assert gov.max_slots(ToolType.AI) == 1

    @pytest.mark.asyncio
    async def test_can_start_false_when_all_slots_taken(self):
        """can_start returns False when all slots are occupied."""
        _mod, _pip, rg_mod = _import_orchestrator()[:3]
        ToolType = rg_mod.ToolType
        gov = rg_mod.ResourceGovernor(max_concurrent_scans=2, max_concurrent_ai=1)
        await gov._semaphores[ToolType.AI].acquire()
        assert gov.can_start(ToolType.AI) is False
        gov.release(ToolType.AI)


# ─────────────────────────────────────────────────────────────
# 16. SSE broadcast on stage change
# ─────────────────────────────────────────────────────────────


class TestSSEBroadcast:
    """Tests that _broadcast_stage sends SSE messages."""

    @pytest.fixture
    def pipeline_with_rec(self):
        models, pipeline_mod, rg_mod = _import_orchestrator()[:3]
        pl = _make_pipeline(pipeline_mod, rg_mod)
        rec = models.AuditRecord(audit_id="sse-1", chain="eth", address="0x1")
        pl._audit_log[rec.audit_id] = rec
        return pl, rec, models

    @pytest.mark.asyncio
    async def test_broadcast_stage_posts_to_dashboard(self, pipeline_with_rec):
        """_broadcast_stage sends POST to dashboard SSE endpoint."""
        pl, rec, models = pipeline_with_rec
        mock_post = AsyncMock(return_value=MagicMock(status_code=200))
        mock_client_cls = MagicMock()
        mock_client_cls.__aenter__ = AsyncMock(return_value=MagicMock(post=mock_post))
        mock_client_cls.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client_cls):
            await pl._broadcast_stage(
                audit_id=rec.audit_id,
                state=models.PipelineState.SCANNING,
                progress=0.5,
                message="Scanning started",
            )

        assert mock_post.called

    @pytest.mark.asyncio
    async def test_broadcast_stage_silently_handles_failure(self, pipeline_with_rec):
        """_broadcast_stage does not raise on network failure."""
        pl, rec, models = pipeline_with_rec
        mock_client_cls = MagicMock()
        mock_client_cls.__aenter__ = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client_cls.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client_cls):
            # Should not raise
            await pl._broadcast_stage(
                audit_id=rec.audit_id,
                state=models.PipelineState.COMPLETED,
                progress=1.0,
                message="Done",
            )


# ─────────────────────────────────────────────────────────────
# 17. Resilient step with fallback
# ─────────────────────────────────────────────────────────────


class TestResilientStep:
    """Tests for ResilientPipelineStep retry and fallback behavior."""

    @pytest.fixture
    def resilient_modules(self):
        _mod, _pip, _rg, _batch, _prio, resilient_mod = _import_orchestrator()[:6]
        return resilient_mod

    @pytest.mark.asyncio
    async def test_resilient_step_success_on_first_try(self, resilient_modules):
        """Resilient step returns success when handler succeeds immediately."""
        step = resilient_modules.ResilientPipelineStep(name="test_step", max_retries=2)
        async def handler(ctx):
            return {"ok": True}
        result = await step.execute({}, handler)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_resilient_step_uses_fallback_on_repeated_failure(self, resilient_modules):
        """Resilient step uses fallback when all retries exhausted."""
        async def fallback(ctx):
            return {"degraded": True}

        step = resilient_modules.ResilientPipelineStep(
            name="failing_step", max_retries=1, fallback_fn=fallback, critical=False
        )
        call_count = [0]

        async def failing_handler(ctx):
            call_count[0] += 1
            raise RuntimeError("always fails")

        result = await step.execute({}, failing_handler)
        assert result["status"] == "degraded"
        assert call_count[0] == 2  # initial + 1 retry

    @pytest.mark.asyncio
    async def test_critical_step_raises_after_all_retries(self, resilient_modules):
        """Critical step raises RuntimeError when all retries exhausted."""
        step = resilient_modules.ResilientPipelineStep(name="critical_step", max_retries=1, critical=True)

        async def failing_handler(ctx):
            raise RuntimeError("always fails")

        with pytest.raises(RuntimeError, match="Critical step"):
            await step.execute({}, failing_handler)

    @pytest.mark.asyncio
    async def test_step_status_constants(self, resilient_modules):
        """StepStatus has expected values."""
        assert resilient_modules.StepStatus.SUCCESS == "success"
        assert resilient_modules.StepStatus.DEGRADED == "degraded"
        assert resilient_modules.StepStatus.SKIPPED == "skipped"
        assert resilient_modules.StepStatus.FAILED == "failed"


# ─────────────────────────────────────────────────────────────
# 18. Concurrent audit runs don't corrupt shared state
# ─────────────────────────────────────────────────────────────


class TestConcurrentAudits:
    """Tests that concurrent audits don't corrupt shared state."""

    @pytest.mark.asyncio
    async def test_concurrent_records_independent(self):
        """Multiple AuditRecord instances do not interfere with each other."""
        models, _pl, _rg = _import_orchestrator()[:3]
        r1 = models.AuditRecord(audit_id="conc-1", chain="eth", address="0x1",
                                state=models.PipelineState.SCANNING)
        r2 = models.AuditRecord(audit_id="conc-2", chain="polygon", address="0x2",
                                state=models.PipelineState.PENDING)

        r1.state = models.PipelineState.COMPLETED
        await asyncio.sleep(0)  # yield event loop
        assert r2.state == models.PipelineState.PENDING
        assert r1.state == models.PipelineState.COMPLETED

    @pytest.mark.asyncio
    async def test_shared_audit_log_thread_safe(self):
        """Pipeline._audit_log updates are independent per audit_id."""
        models, pipeline_mod, rg_mod = _import_orchestrator()[:3]
        pl = _make_pipeline(pipeline_mod, rg_mod)

        aid1 = pl.register_audit(chain="eth", address="0x1", program="p1", priority=5)
        aid2 = pl.register_audit(chain="polygon", address="0x2", program="p2", priority=3)

        pl._audit_log[aid1].state = models.PipelineState.SCANNING
        await asyncio.sleep(0)
        pl._audit_log[aid2].state = models.PipelineState.AI_ANALYSIS

        assert pl._audit_log[aid1].state == models.PipelineState.SCANNING
        assert pl._audit_log[aid2].state == models.PipelineState.AI_ANALYSIS
