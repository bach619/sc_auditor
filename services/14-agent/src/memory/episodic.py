"""Episodic memory — menyimpan pengalaman audit sebelumnya.

Every episode = one audit cycle:
  {contract, scanner_output, findings, actions_taken, outcome}

Used for:
  - Agent mengingat "waktu terakhir audit contract ini, begini hasilnya"
  - Learning dari kegagalan: "waktu itu PoC gagal, coba approach berbeda"

Storage: ~/.sc_auditor/learning/episodic.json
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from .base import BaseMemory, MemoryEntry

log = structlog.get_logger(service="agent_memory", module="episodic")


class EpisodicMemory(BaseMemory):
    """Persistent episodic memory — stores audit experiences as episodes.

    Each episode is a self-contained record of an audit cycle
    with contract info, actions, findings, and outcome.
    """

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self.storage_path = Path(storage_path or Path.home() / ".sc_auditor" / "learning" / "episodic.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.episodes: list[dict[str, Any]] = []
        self._load()

    # ── Persistence ─────────────────────────────────────────

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                self.episodes = json.loads(self.storage_path.read_text())
                log.info("episodic_memory.loaded", count=len(self.episodes))
            except (json.JSONDecodeError, OSError) as e:
                log.warning("episodic_memory.load_failed", error=str(e))
                self.episodes = []

    def _save(self) -> None:
        try:
            self.storage_path.write_text(json.dumps(self.episodes, indent=2))
        except OSError as e:
            log.error("episodic_memory.save_failed", error=str(e))

    # ── Episode-specific API ────────────────────────────────

    async def store_episode(self, episode: dict[str, Any]) -> str:
        """Store a full audit episode with metadata."""
        episode.setdefault("timestamp", datetime.now(UTC).isoformat())
        entry = MemoryEntry(
            content=episode.get("summary", json.dumps(episode, default=str)),
            metadata={
                "contract": episode.get("contract", ""),
                "function": episode.get("function", ""),
                "scanner": episode.get("scanner", ""),
                "findings_count": len(episode.get("findings", [])),
                "outcome": episode.get("outcome", "unknown"),
            },
            entry_id=episode.get("episode_id"),
        )
        episode["episode_id"] = entry.entry_id
        self.episodes.append(episode)
        self._save()
        return entry.entry_id

    async def retrieve_similar(self, contract: str,
                                function: str | None = None) -> list[dict[str, Any]]:
        """Find episodes for the same contract (and optionally function)."""
        results = [e for e in self.episodes if e.get("contract") == contract]
        if function:
            results = [e for e in results if e.get("function") == function]
        results.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return results[:5]

    # ── BaseMemory Interface ────────────────────────────────

    async def store(self, entry: MemoryEntry) -> str:
        """Store a generic memory entry as an episode."""
        episode = {
            "entry_id": entry.entry_id,
            "content": entry.content,
            "metadata": entry.metadata,
            "timestamp": entry.timestamp,
        }
        self.episodes.append(episode)
        self._save()
        return entry.entry_id

    async def store_text(self, key: str, content: Any, metadata: dict[str, Any] | None = None) -> str:
        """Store as MemoryEntry with key+content+metadata (convenience wrapper)."""
        entry = MemoryEntry(
            content=str(content),
            metadata={"key": key, **(metadata or {})},
            entry_id=key,
        )
        return await self.store(entry)

    async def retrieve(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Simple keyword-based retrieval from episodes."""
        query_lower = query.lower()
        results = []
        for ep in self.episodes:
            text = json.dumps(ep, default=str).lower()
            if query_lower in text:
                results.append(MemoryEntry(
                    content=ep.get("content", json.dumps(ep, default=str)),
                    metadata=ep.get("metadata", {}),
                    entry_id=ep.get("entry_id"),
                    timestamp=ep.get("timestamp"),
                ))
        return results[:limit]

    async def get(self, entry_id: str) -> MemoryEntry | None:
        for ep in self.episodes:
            if ep.get("entry_id") == entry_id:
                return MemoryEntry(
                    content=ep.get("content", ""),
                    metadata=ep.get("metadata", {}),
                    entry_id=ep.get("entry_id"),
                    timestamp=ep.get("timestamp"),
                )
        return None

    async def delete(self, entry_id: str) -> bool:
        before = len(self.episodes)
        self.episodes = [e for e in self.episodes if e.get("entry_id") != entry_id]
        if len(self.episodes) < before:
            self._save()
            return True
        return False

    def __len__(self) -> int:
        """Support len() — returns number of stored episodes."""
        return len(self.episodes)

    async def clear(self) -> None:
        self.episodes.clear()
        self._save()

    async def count(self) -> int:
        return len(self.episodes)
