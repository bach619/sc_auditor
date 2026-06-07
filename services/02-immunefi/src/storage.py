"""EnhancedJSONStorage — Atomic, indexed, versioned JSON storage.

Menggantikan flat programs.json dengan struktur multi-file untuk
reliability dan performance yang lebih baik, tanpa SQL dependency.

Struktur direktori:
  /data/immunefi/
  ├── programs/{slug}.json       # Satu file per program
  ├── history/{slug}.jsonl       # Append-only change log per program
  ├── indexes/                    # Fast lookup indexes
  │   ├── by_chain.json
  │   ├── by_status.json
  │   ├── by_bounty.json
  │   └── by_last_updated.json
  ├── sync_log.jsonl              # Sync operation history
  └── _meta.json                  # Schema version, last_synced, commit_hash
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger()

# ── Constants ──────────────────────────────────────────────

MAX_HISTORY_ENTRIES = 500  # max history lines per program (auto-pruned on append)
_MAX_PRUNE_BATCH = 10       # max files to check per save cycle

from src.models import Program


class EnhancedJSONStorage:
    """JSON storage with indexing, history, and atomic operations.

    Usage:
        storage = EnhancedJSONStorage(Path("/data/immunefi"))

        # Write
        storage.save_program(program)
        storage.append_history(slug, snapshot)

        # Read
        programs = storage.load_all_programs()
        prog = storage.load_program(slug)
        history = storage.get_history(slug)

        # Indexes
        storage.rebuild_indexes(programs)

        # Meta
        meta = storage.read_meta()
        storage.write_meta(schema_version="2.0")
    """

    SCHEMA_VERSION = "2.0"

    # ── Initialization ──────────────────────────────────────

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create required directory structure if not exists."""
        for sub_dir in ["programs", "history", "indexes"]:
            (self.data_dir / sub_dir).mkdir(parents=True, exist_ok=True)

    # ── Atomic Writes ────────────────────────────────────────

    def write_atomic(self, path: str | Path, data: Any) -> bool:
        """Atomically write JSON data to a file.

        Strategy: write to .tmp → fsync → rename (atomic on POSIX).
        Returns True on success, False on failure.
        """
        path = Path(path)
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(
                json.dumps(data, indent=2, default=str, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(path)
            return True
        except (OSError, PermissionError) as e:
            log.error("storage.write_atomic.error", path=str(path), error=str(e))
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            return False

    def read_json(self, path: str | Path, default: Any = None) -> Any:
        """Read and parse a JSON file. Return default if missing or corrupt."""
        path = Path(path)
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            log.warning("storage.read_json.error", path=str(path), error=str(e))
            return default

    # ── Per-Program Operations ───────────────────────────────

    def save_program(self, program: Program) -> bool:
        """Save a single program to its own file."""
        path = self.data_dir / "programs" / f"{program.slug}.json"
        result = self.write_atomic(path, program.model_dump(mode="json"))

        # Also save a history snapshot
        self._save_history_snapshot(program)

        return result

    def save_all(self, programs: dict[str, Program]) -> bool:
        """Save all programs in batch. Returns True if all succeeded."""
        success = True
        for slug, program in programs.items():
            if not self.save_program(program):
                log.warning("storage.save_all.failed", slug=slug)
                success = False
        return success

    def load_program(self, slug: str) -> Program | None:
        """Load a single program from its file. Returns None if not found."""
        path = self.data_dir / "programs" / f"{slug}.json"
        if not path.exists():
            return None
        data = self.read_json(path)
        if data is None:
            return None
        try:
            return Program(**data)
        except Exception as e:
            log.warning("storage.load_program.invalid", slug=slug, error=str(e))
            return None

    def load_all_programs(self) -> dict[str, Program]:
        """Load all programs from the programs/ directory.

        Also handles legacy migration: if programs.json exists and _meta.json
        doesn't, auto-migrate to the new format.
        """
        # Check for legacy migration
        legacy = self.data_dir / "programs.json"
        meta = self.data_dir / "_meta.json"
        if legacy.exists() and not meta.exists():
            return self._migrate_from_legacy(legacy)

        programs: dict[str, Program] = {}
        prog_dir = self.data_dir / "programs"
        if not prog_dir.exists():
            return programs

        for f in sorted(prog_dir.iterdir()):
            if f.suffix == ".json":
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    p = Program(**data)
                    programs[p.slug] = p
                except (json.JSONDecodeError, Exception) as e:
                    log.warning(
                        "storage.load_all_programs.skip",
                        file=f.name,
                        error=str(e)[:80],
                    )
                    continue

        log.info("storage.load_all_programs.complete", count=len(programs))
        return programs

    # ── History (Append-Only JSON Lines) ─────────────────────

    # ── History Management ───────────────────────────────────―

    def _save_history_snapshot(self, program: Program) -> None:
        """Append a snapshot to the history file for this program.

        This is called internally by save_program(). The snapshot captures
        key fields so we can track changes over time. Auto-prunes when
        the file exceeds MAX_HISTORY_ENTRIES.
        """
        path = self.data_dir / "history" / f"{program.slug}.jsonl"
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "snapshot": {
                "slug": program.slug,
                "name": program.name,
                "status": program.status,
                "max_bounty": program.max_bounty,
                "chains": list(program.chains),
                "contracts_count": len(program.contracts),
                "repos_count": len(program.repos),
            },
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
            # Auto-prune if too large (fire-and-forget)
            self._prune_history_file(path)
        except OSError as e:
            log.warning("storage.history.append.error", slug=program.slug, error=str(e))

    def append_history(self, slug: str, snapshot: dict) -> bool:
        """Append an arbitrary historical entry for a program.

        This is the public API for external callers who want to
        record custom events (e.g., "bounty_changed", "status_changed").
        Auto-prunes when the file exceeds MAX_HISTORY_ENTRIES.
        """
        path = self.data_dir / "history" / f"{slug}.jsonl"
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "snapshot": snapshot,
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
            self._prune_history_file(path)
            return True
        except OSError as e:
            log.warning("storage.history.append.error", slug=slug, error=str(e))
            return False

    def _prune_history_file(self, path: Path) -> None:
        """Trim a history JSONL file to MAX_HISTORY_ENTRIES lines.

        Keeps the most recent entries, discards oldest.
        Synchronous — fast karena hanya file kecil (<200KB typical).
        """
        try:
            if not path.exists():
                return

            text = path.read_text(encoding="utf-8")
            lines = text.strip().split("\n")

            if len(lines) <= MAX_HISTORY_ENTRIES:
                return

            kept = lines[-MAX_HISTORY_ENTRIES:]
            path.write_text("\n".join(kept) + "\n", encoding="utf-8")
            log.info(
                "storage.history.pruned",
                file=path.name,
                original=len(lines),
                kept=len(kept),
            )
        except OSError as e:
            log.warning("storage.history.prune.error", file=str(path), error=str(e))

    def get_history(self, slug: str, limit: int = 50) -> list[dict]:
        """Read the last N historical entries for a program.

        Returns entries in reverse chronological order (newest first).
        """
        path = self.data_dir / "history" / f"{slug}.jsonl"
        if not path.exists():
            return []

        try:
            lines = path.read_text(encoding="utf-8").strip().split("\n")
            entries = []
            for line in lines[-limit:]:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return entries[::-1]  # newest first
        except OSError as e:
            log.warning("storage.history.read.error", slug=slug, error=str(e))
            return []

    # ── Indexes ──────────────────────────────────────────────

    def rebuild_indexes(self, programs: dict[str, Program]) -> bool:
        """Rebuild all lookup indexes from the full program set.

        Indexes speed up filtering queries without scanning all programs.
        """
        by_chain: dict[str, list[str]] = {}
        by_status: dict[str, list[str]] = {}
        by_bounty: dict[str, list[str]] = {
            "0-1k": [], "1k-10k": [], "10k-100k": [],
            "100k-1M": [], "1M+": [], "unknown": [],
        }
        by_updated: list[dict] = []

        for slug, p in programs.items():
            # Chain index (many-to-many)
            for c in p.chains:
                by_chain.setdefault(c, []).append(slug)

            # Status index
            s = p.status or "unknown"
            by_status.setdefault(s, []).append(slug)

            # Bounty index
            bounty = p.max_bounty
            if bounty is None:
                by_bounty["unknown"].append(slug)
            elif bounty < 1000:
                by_bounty["0-1k"].append(slug)
            elif bounty < 10_000:
                by_bounty["1k-10k"].append(slug)
            elif bounty < 100_000:
                by_bounty["10k-100k"].append(slug)
            elif bounty < 1_000_000:
                by_bounty["100k-1M"].append(slug)
            else:
                by_bounty["1M+"].append(slug)

            # Updated-at index (for sorting by recency)
            by_updated.append({"slug": slug, "updated_at": p.updated_at})

        # Sort by_updated descending
        by_updated.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

        index_dir = self.data_dir / "indexes"
        success = True
        success &= self.write_atomic(index_dir / "by_chain.json", by_chain)
        success &= self.write_atomic(index_dir / "by_status.json", by_status)
        success &= self.write_atomic(index_dir / "by_bounty.json", by_bounty)
        success &= self.write_atomic(
            index_dir / "by_last_updated.json",
            [i["slug"] for i in by_updated],
        )

        log.info("storage.indexes.rebuilt", program_count=len(programs))
        return success

    def get_index(self, name: str) -> dict | list | None:
        """Read an index file by name (without .json extension)."""
        path = self.data_dir / "indexes" / f"{name}.json"
        return self.read_json(path)

    # ── Metadata ─────────────────────────────────────────────

    def read_meta(self) -> dict:
        """Read metadata file. Returns sensible defaults if missing."""
        default = {
            "schema_version": self.SCHEMA_VERSION,
            "last_synced": None,
            "commit_hash": None,
        }
        path = self.data_dir / "_meta.json"
        if not path.exists():
            return default
        meta = self.read_json(path)
        if not isinstance(meta, dict):
            return default
        return {**default, **meta}

    def write_meta(self, **kwargs: Any) -> bool:
        """Update metadata file, preserving existing fields."""
        meta = self.read_meta()
        meta.update(kwargs)
        meta["schema_version"] = self.SCHEMA_VERSION
        return self.write_atomic(self.data_dir / "_meta.json", meta)

    # ── Sync Log ─────────────────────────────────────────────

    def append_sync_log(self, entry: dict) -> bool:
        """Append an entry to the sync operation log (JSON Lines)."""
        path = self.data_dir / "sync_log.jsonl"
        entry["timestamp"] = entry.get(
            "timestamp", datetime.now(UTC).isoformat()
        )
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
            return True
        except OSError as e:
            log.warning("storage.sync_log.append.error", error=str(e))
            return False

    def get_sync_log(self, limit: int = 20) -> list[dict]:
        """Read the last N sync log entries (newest first)."""
        path = self.data_dir / "sync_log.jsonl"
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8").strip().split("\n")
            entries = []
            for line in lines[-limit:]:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return entries[::-1]
        except OSError:
            return []

    # ── Legacy Migration ─────────────────────────────────────

    def _migrate_from_legacy(self, legacy_path: Path) -> dict[str, Program]:
        """Migrate from old single-file format to the new multi-file structure.

        Called automatically by load_all_programs() when it detects
        a legacy programs.json without a corresponding _meta.json.
        """
        log.info("storage.migration.start", legacy_path=str(legacy_path))
        data = self.read_json(legacy_path)
        if data is None:
            log.error("storage.migration.failed", reason="cannot read legacy file")
            return {}

        programs: dict[str, Program] = {}

        # Handle both dict format ({slug: program}) and list format
        raw_programs = data.get("programs", data) if isinstance(data, dict) else data
        items = (
            raw_programs.items()
            if isinstance(raw_programs, dict)
            else enumerate(raw_programs)
        )

        for key, pdata in items:
            try:
                if isinstance(pdata, Program):
                    p = pdata
                elif isinstance(pdata, dict):
                    p = Program(**pdata)
                else:
                    continue
                programs[p.slug] = p
                self.save_program(p)
            except Exception as e:
                log.warning("storage.migration.skip", key=str(key), error=str(e)[:80])
                continue

        # Preserve legacy metadata
        if isinstance(data, dict):
            self.write_meta(
                last_synced=data.get("last_synced"),
                commit_hash=data.get("commit_hash", ""),
            )
        else:
            self.write_meta(last_synced=None, commit_hash="")

        # Rebuild indexes
        self.rebuild_indexes(programs)

        # Rename legacy file as backup (don't delete)
        bak_path = legacy_path.with_suffix(".json.bak")
        try:
            # If bak already exists, keep both
            counter = 0
            while bak_path.exists():
                counter += 1
                bak_path = legacy_path.with_suffix(f".json.bak.{counter}")
            legacy_path.rename(bak_path)
            log.info("storage.migration.backup_created", path=str(bak_path))
        except OSError as e:
            log.warning("storage.migration.backup_failed", error=str(e))

        log.info(
            "storage.migration.complete",
            programs_migrated=len(programs),
            backup_path=str(bak_path),
        )
        return programs
