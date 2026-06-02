"""Integration test: full pipeline flow.

Tests the end-to-end interaction between:
  Classifier (07) ←→ Exploit (08) ←→ Knowledge Base (shared)

This test validates the cross-pollination feedback loop:
  1. Findings diklasifikasikan oleh Classifier
  2. Exploit sukses → result disimpan ke Knowledge Base
  3. Classifier membaca Knowledge Base → auto-classify finding serupa
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Generator

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services"))

from shared.knowledge_base import (
    ConfirmedFinding,
    KnowledgeRepository,
    KnowledgeStats,
)


@pytest.fixture
def kb_dir() -> Generator[Path, None, None]:
    """Create a temporary knowledge base directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestKnowledgeBaseIntegration:
    """Test the cross-service knowledge base integration."""

    def test_save_and_retrieve_confirmed(self, kb_dir: Path):
        """Exploit service saves -> Classifier service retrieves."""
        kb = KnowledgeRepository(data_dir=kb_dir)

        confirmed = ConfirmedFinding(
            finding_id="F-001",
            audit_id="audit-001",
            contract_hash="abc123",
            title="Reentrancy in withdraw()",
            severity="critical",
            attack_type="reentrancy",
            confirmed_by="exploit",
            exploit_successful=True,
            tx_hash="0xdeadbeef",
            vulnerability_pattern={
                "function_count": 5,
                "cei_violations": ["withdraw"],
            },
            primitive_sequence=[
                ("impersonate", {"account": "attacker"}),
                ("call_external", {"target": "vulnerable"}),
            ],
            confidence=1.0,
        )
        kb.save_confirmed(confirmed)

        all_confirmed = kb.get_all_confirmed()
        assert len(all_confirmed) == 1
        assert all_confirmed[0].finding_id == "F-001"
        assert all_confirmed[0].confirmed_by == "exploit"
        assert all_confirmed[0].confidence == 1.0

    def test_deduplicate_by_finding_id(self, kb_dir: Path):
        """Multiple saves of same finding_id should not duplicate."""
        kb = KnowledgeRepository(data_dir=kb_dir)

        data = ConfirmedFinding(
            finding_id="F-001",
            audit_id="audit-001",
            contract_hash="abc123",
            title="Test",
            severity="high",
            attack_type="reentrancy",
            confirmed_by="exploit",
        )
        kb.save_confirmed(data)
        kb.save_confirmed(data)

        assert kb.count_confirmed() == 1

    def test_find_matching_contract(self, kb_dir: Path):
        """Classifier can find matches by contract_hash."""
        kb = KnowledgeRepository(data_dir=kb_dir)

        kb.save_confirmed(ConfirmedFinding(
            finding_id="F-001", audit_id="a1", contract_hash="abc123",
            title="T1", severity="critical", attack_type="reentrancy",
            confirmed_by="exploit",
        ))
        kb.save_confirmed(ConfirmedFinding(
            finding_id="F-002", audit_id="a1", contract_hash="def456",
            title="T2", severity="high", attack_type="access_control",
            confirmed_by="human",
        ))

        matches = kb.find_matching_contracts("abc123")
        assert len(matches) == 1
        assert matches[0].finding_id == "F-001"

    def test_find_matching_pattern(self, kb_dir: Path):
        """Classifier can filter by attack_type + severity."""
        kb = KnowledgeRepository(data_dir=kb_dir)

        kb.save_confirmed(ConfirmedFinding(
            finding_id="F-001", audit_id="a1", contract_hash="abc123",
            title="T1", severity="critical", attack_type="reentrancy",
            confirmed_by="exploit",
        ))
        kb.save_confirmed(ConfirmedFinding(
            finding_id="F-002", audit_id="a1", contract_hash="def456",
            title="T2", severity="low", attack_type="reentrancy",
            confirmed_by="exploit",
        ))

        results = kb.find_matching_pattern(severity="critical")
        assert len(results) == 1

        results = kb.find_matching_pattern(attack_type="reentrancy")
        assert len(results) == 2

    def test_feedback_storage(self, kb_dir: Path):
        """Human feedback is stored in KB."""
        kb = KnowledgeRepository(data_dir=kb_dir)

        feedback = {
            "finding_id": "F-001",
            "audit_id": "audit-001",
            "original_classification": "false_positive",
            "correct_classification": "true_positive",
            "is_correction": True,
            "notes": "This is actually a valid reentrancy bug",
            "source": "human_feedback",
        }
        kb.save_feedback(feedback)

        all_feedback = kb.get_all_feedback()
        assert len(all_feedback) == 1
        assert all_feedback[0]["finding_id"] == "F-001"
        assert all_feedback[0]["is_correction"] is True

    def test_stats_computation(self, kb_dir: Path):
        """Stats are computed correctly."""
        kb = KnowledgeRepository(data_dir=kb_dir)

        kb.save_confirmed(ConfirmedFinding(
            finding_id="F-001", audit_id="a1", contract_hash="abc123",
            title="T1", severity="critical", attack_type="reentrancy",
            confirmed_by="exploit",
        ))
        kb.save_confirmed(ConfirmedFinding(
            finding_id="F-002", audit_id="a1", contract_hash="def456",
            title="T2", severity="high", attack_type="access_control",
            confirmed_by="human",
        ))
        kb.save_confirmed(ConfirmedFinding(
            finding_id="F-003", audit_id="a2", contract_hash="abc123",
            title="T3", severity="critical", attack_type="reentrancy",
            confirmed_by="exploit",
        ))

        stats = kb.get_stats()
        assert stats.total_confirmed == 3
        assert stats.confirmed_by_exploit == 2
        assert stats.confirmed_by_human == 1
        assert stats.unique_contracts == 2
        assert ("reentrancy", 2) in stats.top_attack_types

    def test_empty_kb_returns_empty(self, kb_dir: Path):
        """Empty knowledge base returns empty results gracefully."""
        kb = KnowledgeRepository(data_dir=kb_dir)
        assert kb.count_confirmed() == 0
        assert kb.get_all_confirmed() == []
        assert kb.find_matching_contracts("nonexistent") == []
        assert kb.find_matching_pattern() == []

    def test_cross_service_workflow(self, kb_dir: Path):
        """Simulate full cross-service workflow."""
        kb = KnowledgeRepository(data_dir=kb_dir)

        exploit_result = ConfirmedFinding(
            finding_id="F-001",
            audit_id="audit-001",
            contract_hash="0xdead",
            title="Reentrancy in withdraw()",
            severity="critical",
            attack_type="reentrancy",
            confirmed_by="exploit",
            exploit_successful=True,
            tx_hash="0x1234",
            vulnerability_pattern={
                "function_count": 3,
                "cei_violations": ["withdraw"],
            },
            primitive_sequence=[("reenter", {"target": "vulnerable"})],
            confidence=1.0,
        )
        kb.save_confirmed(exploit_result)
        assert kb.count_confirmed() == 1

        matches = kb.find_matching_pattern(attack_type="reentrancy")
        assert len(matches) == 1
        assert matches[0].confidence == 1.0

        kb.save_feedback({
            "finding_id": "F-002",
            "audit_id": "audit-002",
            "original_classification": "true_positive",
            "correct_classification": "true_positive",
            "is_correction": False,
            "notes": "Confirmed by manual review",
            "source": "human_feedback",
        })
        assert len(kb.get_all_feedback()) == 1

        known_patterns = kb.find_matching_contracts("0xdead")
        assert len(known_patterns) == 1
        assert known_patterns[0].attack_type == "reentrancy"
