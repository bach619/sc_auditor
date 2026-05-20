"""Unit tests for EnhancedJSONStorage.

Run: pytest tests/test_immunefi_storage.py -v
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest

from src.models import Program, Contract, Repo
from src.storage import EnhancedJSONStorage


# ── Fixtures ────────────────────────────────────────────────

@pytest.fixture
def storage():
    """Create a temporary EnhancedJSONStorage for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield EnhancedJSONStorage(Path(tmpdir))


@pytest.fixture
def sample_program() -> Program:
    return Program(
        slug="test-protocol",
        name="Test Protocol",
        chains=["ethereum", "arbitrum"],
        max_bounty=500_000.0,
        min_bounty=1_000.0,
        currency="USD",
        status="active",
        repos=[Repo(url="https://github.com/owner/repo", owner="owner", repo="repo", source="project_url")],
        contracts=[Contract(address="0xabc", chain="ethereum", name="Token")],
        project_url="https://test.protocol",
        description="A test protocol",
        tags=["defi", "lending"],
        updated_at="2025-01-01T00:00:00Z",
    )


@pytest.fixture
def legacy_programs_json(tmp_path) -> Path:
    """Create a legacy programs.json file for migration testing."""
    data = {
        "last_synced": "2025-01-01T00:00:00Z",
        "commit_hash": "abc123",
        "programs": {
            "legacy-protocol": {
                "slug": "legacy-protocol",
                "name": "Legacy Protocol",
                "chains": ["ethereum"],
                "max_bounty": 100000.0,
                "status": "active",
                "repos": [],
                "contracts": [],
                "project_url": "",
                "logo": "",
                "description": "",
                "tags": [],
                "updated_at": "",
            },
            "another-protocol": {
                "slug": "another-protocol",
                "name": "Another Protocol",
                "chains": ["polygon"],
                "max_bounty": 50000.0,
                "status": "active",
                "repos": [],
                "contracts": [],
                "project_url": "",
                "logo": "",
                "description": "",
                "tags": [],
                "updated_at": "",
            },
        },
    }
    path = tmp_path / "programs.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


# ── Tests: Initialization ───────────────────────────────────

class TestInit:
    def test_create_directories(self):
        """Should create programs/, history/, indexes/ directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = EnhancedJSONStorage(Path(tmpdir))
            assert (Path(tmpdir) / "programs").exists()
            assert (Path(tmpdir) / "history").exists()
            assert (Path(tmpdir) / "indexes").exists()

    def test_existing_directories_not_recreated(self):
        """Should not fail if directories already exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "programs").mkdir()
            (Path(tmpdir) / "history").mkdir()
            (Path(tmpdir) / "indexes").mkdir()
            storage = EnhancedJSONStorage(Path(tmpdir))  # should not raise


# ── Tests: Atomic Write ─────────────────────────────────────

class TestAtomicWrite:
    def test_write_and_read(self, storage):
        """Should write JSON and read it back."""
        data = {"key": "value", "number": 42}
        path = storage.data_dir / "test.json"
        assert storage.write_atomic(path, data)
        assert storage.read_json(path) == data

    def test_write_creates_tmp_then_renames(self, storage):
        """Should write to .tmp then rename to target."""
        path = storage.data_dir / "test.json"
        storage.write_atomic(path, {"hello": "world"})
        # .tmp file should NOT exist after successful write
        assert not (storage.data_dir / "test.json.tmp").exists()
        # Target should exist and be valid JSON
        assert path.exists()
        assert json.loads(path.read_text(encoding="utf-8")) == {"hello": "world"}

    def test_read_nonexistent_returns_default(self, storage):
        """Should return default for missing file."""
        assert storage.read_json(storage.data_dir / "nonexistent.json") is None
        assert storage.read_json(storage.data_dir / "nonexistent.json", {}) == {}


# ── Tests: Per-Program Operations ───────────────────────────

class TestProgramOperations:
    def test_save_and_load(self, storage, sample_program):
        """Should save a program and load it back identically."""
        storage.save_program(sample_program)
        loaded = storage.load_program(sample_program.slug)
        assert loaded is not None
        assert loaded.slug == sample_program.slug
        assert loaded.name == sample_program.name
        assert loaded.max_bounty == sample_program.max_bounty
        assert loaded.chains == sample_program.chains

    def test_save_creates_file(self, storage, sample_program):
        """Should create programs/{slug}.json on disk."""
        storage.save_program(sample_program)
        path = storage.data_dir / "programs" / f"{sample_program.slug}.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["slug"] == sample_program.slug

    def test_load_nonexistent(self, storage):
        """Should return None for non-existent program."""
        assert storage.load_program("nonexistent") is None

    def test_save_all(self, storage, sample_program):
        """Should save multiple programs."""
        p2 = Program(slug="protocol-2", name="Protocol 2")
        programs = {"p1": sample_program, "p2": p2}
        assert storage.save_all(programs)
        assert storage.load_program("test-protocol") is not None
        assert storage.load_program("protocol-2") is not None

    def test_load_all_programs(self, storage, sample_program):
        """load_all_programs should return all saved programs."""
        storage.save_program(sample_program)
        p2 = Program(slug="protocol-2", name="Protocol 2")
        storage.save_program(p2)

        all_progs = storage.load_all_programs()
        assert len(all_progs) == 2
        assert "test-protocol" in all_progs
        assert "protocol-2" in all_progs

    def test_load_all_empty(self, storage):
        """load_all_programs should return empty dict when none saved."""
        assert storage.load_all_programs() == {}


# ── Tests: History ──────────────────────────────────────────

class TestHistory:
    def test_history_created_on_save(self, storage, sample_program):
        """Save should automatically create a history entry."""
        storage.save_program(sample_program)
        hist = storage.get_history(sample_program.slug)
        assert len(hist) == 1
        assert hist[0]["snapshot"]["slug"] == sample_program.slug

    def test_history_multiple_entries(self, storage, sample_program):
        """Multiple saves should create multiple history entries."""
        for i in range(3):
            sample_program.max_bounty = 100_000 + i
            storage.save_program(sample_program)

        hist = storage.get_history(sample_program.slug)
        assert len(hist) == 3  # 3 saves

    def test_history_limit(self, storage, sample_program):
        """get_history should respect the limit parameter."""
        for i in range(10):
            sample_program.max_bounty = 100_000 + i
            storage.save_program(sample_program)

        hist = storage.get_history(sample_program.slug, limit=3)
        assert len(hist) <= 3

    def test_history_empty(self, storage):
        """get_history for non-existent program should return []."""
        assert storage.get_history("nonexistent") == []

    def test_history_newest_first(self, storage, sample_program):
        """History should be returned newest first."""
        for i in range(3):
            sample_program.max_bounty = float(i)
            storage.save_program(sample_program)

        hist = storage.get_history(sample_program.slug, limit=3)
        bounties = [h["snapshot"]["max_bounty"] for h in hist]
        assert bounties == sorted(bounties, reverse=True)

    def test_append_history_manual(self, storage):
        """append_history should work for custom events."""
        assert storage.append_history("test-slug", {"custom": "data"})
        hist = storage.get_history("test-slug")
        assert len(hist) == 1
        assert hist[0]["snapshot"]["custom"] == "data"


# ── Tests: Indexes ──────────────────────────────────────────

class TestIndexes:
    def test_rebuild_indexes_creates_files(self, storage, sample_program):
        """rebuild_indexes should create 4 index files."""
        storage.rebuild_indexes({"test-protocol": sample_program})
        index_dir = storage.data_dir / "indexes"
        assert (index_dir / "by_chain.json").exists()
        assert (index_dir / "by_status.json").exists()
        assert (index_dir / "by_bounty.json").exists()
        assert (index_dir / "by_last_updated.json").exists()

    def test_index_by_chain(self, storage):
        """by_chain should map chain names to program slugs."""
        p1 = Program(slug="p1", chains=["ethereum"])
        p2 = Program(slug="p2", chains=["ethereum", "polygon"])
        p3 = Program(slug="p3", chains=["arbitrum"])
        storage.rebuild_indexes({"p1": p1, "p2": p2, "p3": p3})

        idx = storage.get_index("by_chain")
        assert "ethereum" in idx
        assert "polygon" in idx
        assert "arbitrum" in idx
        assert "p1" in idx["ethereum"]
        assert "p2" in idx["polygon"]

    def test_index_by_bounty_ranges(self, storage):
        """by_bounty should categorize programs into bounty ranges."""
        programs = {
            "low": Program(slug="low", max_bounty=500.0),
            "mid": Program(slug="mid", max_bounty=50_000.0),
            "high": Program(slug="high", max_bounty=500_000.0),
            "mega": Program(slug="mega", max_bounty=5_000_000.0),
            "none": Program(slug="none", max_bounty=None),
        }
        storage.rebuild_indexes(programs)
        idx = storage.get_index("by_bounty")
        assert "low" in idx["0-1k"]
        assert "mid" in idx["10k-100k"]
        assert "high" in idx["100k-1M"]
        assert "mega" in idx["1M+"]
        assert "none" in idx["unknown"]

    def test_index_by_status(self, storage):
        """by_status should group programs by status."""
        progs = {
            "active1": Program(slug="active1", status="active"),
            "active2": Program(slug="active2", status="active"),
            "paused": Program(slug="paused", status="paused"),
        }
        storage.rebuild_indexes(progs)
        idx = storage.get_index("by_status")
        assert len(idx["active"]) == 2
        assert len(idx["paused"]) == 1

    def test_get_nonexistent_index(self, storage):
        """get_index should return None for non-existent index."""
        assert storage.get_index("nonexistent") is None


# ── Tests: Metadata ─────────────────────────────────────────

class TestMeta:
    def test_read_meta_defaults(self, storage):
        """read_meta should return defaults if no meta file."""
        meta = storage.read_meta()
        assert meta["schema_version"] == "2.0"
        assert meta["last_synced"] is None
        assert meta["commit_hash"] is None

    def test_write_and_read_meta(self, storage):
        """Should write and read metadata."""
        assert storage.write_meta(last_synced="2025-06-01", commit_hash="def789")
        meta = storage.read_meta()
        assert meta["last_synced"] == "2025-06-01"
        assert meta["commit_hash"] == "def789"

    def test_write_meta_preserves_existing(self, storage):
        """write_meta should update fields without losing existing ones."""
        storage.write_meta(last_synced="2025-01-01")
        storage.write_meta(commit_hash="xyz789")
        meta = storage.read_meta()
        assert meta["last_synced"] == "2025-01-01"
        assert meta["commit_hash"] == "xyz789"


# ── Tests: Sync Log ─────────────────────────────────────────

class TestSyncLog:
    def test_append_and_read(self, storage):
        """Should append to sync log and read back."""
        storage.append_sync_log({"sync_id": "s1", "status": "completed"})
        storage.append_sync_log({"sync_id": "s2", "status": "failed"})

        log = storage.get_sync_log()
        assert len(log) == 2
        assert log[0]["sync_id"] == "s2"  # newest first

    def test_sync_log_limit(self, storage):
        """get_sync_log should respect the limit."""
        for i in range(10):
            storage.append_sync_log({"sync_id": f"s{i}"})
        assert len(storage.get_sync_log(limit=3)) == 3

    def test_empty_sync_log(self, storage):
        """get_sync_log should return [] when no entries."""
        assert storage.get_sync_log() == []


# ── Tests: Legacy Migration ─────────────────────────────────

class TestLegacyMigration:
    def test_migrate_from_legacy(self, storage, legacy_programs_json):
        """_migrate_from_legacy should convert programs.json to new format."""
        programs = storage._migrate_from_legacy(legacy_programs_json)
        assert len(programs) == 2
        assert "legacy-protocol" in programs
        assert "another-protocol" in programs

        # Check new files exist
        assert (storage.data_dir / "programs" / "legacy-protocol.json").exists()
        assert (storage.data_dir / "programs" / "another-protocol.json").exists()

        # Check indexes were rebuilt
        assert (storage.data_dir / "indexes" / "by_chain.json").exists()

        # Check meta was preserved
        meta = storage.read_meta()
        assert meta["last_synced"] == "2025-01-01T00:00:00Z"
        assert meta["commit_hash"] == "abc123"

        # Check legacy was renamed to .bak
        assert not legacy_programs_json.exists()  # renamed
        assert legacy_programs_json.with_suffix(".json.bak").exists()

    def test_migrate_idempotent(self, storage, legacy_programs_json):
        """After migration, _meta.json should exist so re-migration doesn't happen."""
        storage._migrate_from_legacy(legacy_programs_json)
        assert (storage.data_dir / "_meta.json").exists()

        # load_all_programs should NOT trigger migration again
        # (programs.json is now .bak, so _meta.json check prevents re-migration)
        programs = storage.load_all_programs()
        assert len(programs) == 2

    def test_migrate_preserves_data_fidelity(self, storage, legacy_programs_json):
        """Migrated programs should have the same data as original."""
        programs = storage._migrate_from_legacy(legacy_programs_json)
        p = programs["legacy-protocol"]
        assert p.name == "Legacy Protocol"
        assert p.max_bounty == 100000.0
        assert p.status == "active"

    def test_auto_migration_on_load(self, storage, legacy_programs_json):
        """load_all_programs should auto-migrate if legacy exists and _meta doesn't."""
        # Move legacy file to storage dir (not tmp_path)
        legacy_in_storage = storage.data_dir / "programs.json"
        legacy_in_storage.write_text(legacy_programs_json.read_text(), encoding="utf-8")

        programs = storage.load_all_programs()
        assert len(programs) == 2
        # Old file should now be .bak
        assert (storage.data_dir / "programs.json.bak").exists()


# ── Tests: Edge Cases ───────────────────────────────────────

class TestEdgeCases:
    def test_program_with_all_empty_fields(self, storage):
        """Should handle programs with minimal fields."""
        p = Program(slug="minimal")
        storage.save_program(p)
        loaded = storage.load_program("minimal")
        assert loaded is not None
        assert loaded.slug == "minimal"
        assert loaded.chains == []
        assert loaded.max_bounty is None

    def test_program_with_special_chars_in_slug(self, storage):
        """Should handle slugs with special characters."""
        p = Program(slug="special_chars-123.def", name="Special")
        storage.save_program(p)
        loaded = storage.load_program("special_chars-123.def")
        assert loaded is not None

    def test_large_number_of_programs(self, storage):
        """Should handle saving many programs without performance issues."""
        n = 50
        for i in range(n):
            p = Program(slug=f"prog-{i}", name=f"Program {i}", max_bounty=float(i * 1000))
            storage.save_program(p)
        all_progs = storage.load_all_programs()
        assert len(all_progs) == n

    def test_rebuild_indexes_empty(self, storage):
        """rebuild_indexes should not fail with empty programs dict."""
        assert storage.rebuild_indexes({})
        idx = storage.get_index("by_chain")
        assert idx == {}

    def test_corrupted_json_file(self, storage, sample_program):
        """load_program should return None for corrupted file."""
        storage.save_program(sample_program)
        path = storage.data_dir / "programs" / f"{sample_program.slug}.json"
        # Corrupt the file
        path.write_text("{invalid json", encoding="utf-8")
        loaded = storage.load_program(sample_program.slug)
        assert loaded is None
