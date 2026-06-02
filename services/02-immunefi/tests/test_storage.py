"""Tests for EnhancedJSONStorage.

Tests cover:
  - Metadata read/write
  - Program save/load
  - History append/read/pruning
  - Index rebuilding
  - Sync log
  - Atomic writes
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.models import Contract, Program, Repo
from src.storage import EnhancedJSONStorage


# ── Fixtures ────────────────────────────────────────────────


@pytest.fixture
def storage(tmp_data_dir: Path) -> EnhancedJSONStorage:
    """Storage instance backed by a temp directory."""
    return EnhancedJSONStorage(tmp_data_dir)


# ── Meta ────────────────────────────────────────────────────


class TestMeta:
    def test_read_meta_defaults(self, storage: EnhancedJSONStorage) -> None:
        meta = storage.read_meta()
        assert meta["schema_version"] == "2.0"
        assert meta["last_synced"] is None
        assert meta["commit_hash"] is None

    def test_write_and_read_meta(self, storage: EnhancedJSONStorage) -> None:
        assert storage.write_meta(last_synced="2025-06-01T12:00:00Z", commit_hash="abc123")
        meta = storage.read_meta()
        assert meta["last_synced"] == "2025-06-01T12:00:00Z"
        assert meta["commit_hash"] == "abc123"
        assert meta["schema_version"] == "2.0"

    def test_write_meta_preserves_existing(self, storage: EnhancedJSONStorage) -> None:
        storage.write_meta(last_synced="2025-06-01T12:00:00Z")
        storage.write_meta(commit_hash="def456")
        meta = storage.read_meta()
        assert meta["last_synced"] == "2025-06-01T12:00:00Z"
        assert meta["commit_hash"] == "def456"

    def test_meta_file_created(self, storage: EnhancedJSONStorage, tmp_data_dir: Path) -> None:
        storage.write_meta(last_synced="now")
        assert (tmp_data_dir / "_meta.json").exists()


# ── Program Save/Load ───────────────────────────────────────


class TestProgram:
    def test_save_and_load(self, storage: EnhancedJSONStorage, program_data: dict) -> None:
        p = Program(**program_data)
        assert storage.save_program(p)

        loaded = storage.load_program("sushi")
        assert loaded is not None
        assert loaded.slug == "sushi"
        assert loaded.name == "Sushi"
        assert loaded.max_bounty == 2_500_000.0
        assert len(loaded.chains) == 3
        assert "Ethereum" in loaded.chains

    def test_load_nonexistent(self, storage: EnhancedJSONStorage) -> None:
        assert storage.load_program("nonexistent") is None

    def test_save_all(self, storage: EnhancedJSONStorage, program_data: dict) -> None:
        p1 = Program(**program_data)
        p2 = Program(slug="aave", name="Aave", chains=["Ethereum"])

        assert storage.save_all({"sushi": p1, "aave": p2})
        all_progs = storage.load_all_programs()
        assert len(all_progs) == 2
        assert "sushi" in all_progs
        assert "aave" in all_progs

    def test_load_all_empty_dir(self, storage: EnhancedJSONStorage) -> None:
        assert storage.load_all_programs() == {}

    def test_corrupted_file_skipped(self, storage: EnhancedJSONStorage, tmp_data_dir: Path) -> None:
        # Write a corrupt file
        (tmp_data_dir / "programs" / "corrupt.json").write_text("not-json{")
        assert storage.load_all_programs() == {}


# ── History ─────────────────────────────────────────────────


class TestHistory:
    def test_append_and_get_history(self, storage: EnhancedJSONStorage, program_data: dict) -> None:
        p = Program(**program_data)
        storage.save_program(p)  # triggers snapshot

        history = storage.get_history("sushi")
        assert len(history) >= 1
        assert history[0]["snapshot"]["slug"] == "sushi"
        assert history[0]["snapshot"]["max_bounty"] == 2_500_000.0
        assert "timestamp" in history[0]

    def test_get_history_empty(self, storage: EnhancedJSONStorage) -> None:
        assert storage.get_history("nonexistent") == []

    def test_append_history_public_api(self, storage: EnhancedJSONStorage) -> None:
        assert storage.append_history("sushi", {"event": "test", "value": 42})
        history = storage.get_history("sushi")
        assert len(history) >= 1
        assert history[0]["snapshot"]["event"] == "test"

    def test_history_reverse_chronological(self, storage: EnhancedJSONStorage) -> None:
        import time
        for i in range(5):
            storage.append_history("multi", {"index": i})
            time.sleep(0.01)

        history = storage.get_history("multi", limit=5)
        indexes = [h["snapshot"]["index"] for h in history]
        # Should be newest first: 4, 3, 2, 1, 0
        assert indexes == [4, 3, 2, 1, 0]

    def test_history_limit(self, storage: EnhancedJSONStorage) -> None:
        for i in range(20):
            storage.append_history("limited", {"index": i})

        history = storage.get_history("limited", limit=5)
        assert len(history) == 5
        indexes = [h["snapshot"]["index"] for h in history]
        assert indexes == [19, 18, 17, 16, 15]


# ── History Pruning ─────────────────────────────────────────


class TestHistoryPruning:
    def test_prune_triggers_when_exceeds_max(self, storage: EnhancedJSONStorage) -> None:
        """Force prune: write more than MAX_HISTORY_ENTRIES lines and verify."""
        from src.storage import MAX_HISTORY_ENTRIES

        # Write MAX_HISTORY_ENTRIES + 10 entries
        for i in range(MAX_HISTORY_ENTRIES + 10):
            storage.append_history("pruneme", {"index": i})

        path = storage.data_dir / "history" / "pruneme.jsonl"
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) <= MAX_HISTORY_ENTRIES  # pruned

    def test_prune_keeps_newest(self, storage: EnhancedJSONStorage) -> None:
        from src.storage import MAX_HISTORY_ENTRIES

        for i in range(MAX_HISTORY_ENTRIES + 10):
            storage.append_history("keepnewest", {"index": i})

        history = storage.get_history("keepnewest", limit=MAX_HISTORY_ENTRIES)
        indexes = [h["snapshot"]["index"] for h in history]
        # Newest should be preserved
        assert max(indexes) == MAX_HISTORY_ENTRIES + 9
        assert min(indexes) >= 10  # oldest 10 were pruned


# ── Indexes ─────────────────────────────────────────────────


class TestIndexes:
    def test_rebuild_indexes(self, storage: EnhancedJSONStorage) -> None:
        programs = {
            "sushi": Program(
                slug="sushi",
                name="Sushi",
                chains=["Ethereum", "Polygon"],
                max_bounty=2_500_000.0,
                status="active",
            ),
            "aave": Program(
                slug="aave",
                name="Aave",
                chains=["Ethereum"],
                max_bounty=500_000.0,
                status="active",
            ),
            "pancake": Program(
                slug="pancake",
                name="PancakeSwap",
                chains=["BNB Chain"],
                max_bounty=50_000.0,
                status="active",
            ),
        }
        assert storage.rebuild_indexes(programs)

        # by_chain
        by_chain = storage.get_index("by_chain")
        assert by_chain is not None
        assert "Ethereum" in by_chain
        assert "sushi" in by_chain["Ethereum"]
        assert "aave" in by_chain["Ethereum"]

        # by_status
        by_status = storage.get_index("by_status")
        assert by_status is not None
        assert "active" in by_status
        assert len(by_status["active"]) == 3

        # by_bounty
        by_bounty = storage.get_index("by_bounty")
        assert by_bounty is not None
        assert "sushi" in by_bounty["1M+"]
        assert "aave" in by_bounty["100k-1M"]
        assert "pancake" in by_bounty["10k-100k"]

        # by_last_updated
        by_updated = storage.get_index("by_last_updated")
        assert by_updated is not None
        assert isinstance(by_updated, list)

    def test_index_nonexistent(self, storage: EnhancedJSONStorage) -> None:
        assert storage.get_index("nonexistent") is None


# ── Sync Log ────────────────────────────────────────────────


class TestSyncLog:
    def test_append_and_read(self, storage: EnhancedJSONStorage) -> None:
        assert storage.append_sync_log({"event": "sync_start", "count": 50})
        assert storage.append_sync_log({"event": "sync_complete", "count": 50})

        entries = storage.get_sync_log(limit=1)
        assert len(entries) == 1
        assert entries[0]["event"] == "sync_complete"

    def test_read_empty(self, storage: EnhancedJSONStorage) -> None:
        assert storage.get_sync_log() == []


# ── Edge Cases ──────────────────────────────────────────────


class TestEdgeCases:
    def test_program_with_contracts_and_repos(self, storage: EnhancedJSONStorage) -> None:
        p = Program(
            slug="test-prog",
            name="Test",
            chains=["Ethereum"],
            contracts=[Contract(address="0x" + "a" * 40, chain="Ethereum", name="Token")],
            repos=[Repo(url="https://github.com/test/test", owner="test", repo="test", source="project_url")],
        )
        storage.save_program(p)

        loaded = storage.load_program("test-prog")
        assert loaded is not None
        assert len(loaded.contracts) == 1
        assert loaded.contracts[0].address == "0x" + "a" * 40
        assert len(loaded.repos) == 1
        assert loaded.repos[0].owner == "test"

    def test_atomic_write_replaces_content(self, storage: EnhancedJSONStorage, tmp_data_dir: Path) -> None:
        path = tmp_data_dir / "atomic_test.json"
        storage.write_atomic(path, {"version": 1})
        assert json.loads(path.read_text())["version"] == 1

        storage.write_atomic(path, {"version": 2})
        assert json.loads(path.read_text())["version"] == 2
