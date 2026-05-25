"""Memory system for Antonio.

Three types of memory:
- **Episodic**: Urutan kejadian dalam session (apa yang sudah dilakukan)
- **Semantic**: Pengetahuan umum (pola kerentanan, preferensi)
- **Working**: Konteks aktif session saat ini
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any

import structlog

from src.models import MemoryEntry

log = structlog.get_logger()

MAX_WORKING_ENTRIES = 50
MAX_EPISODIC_ENTRIES = 200
MAX_SEMANTIC_ENTRIES = 500


class AgentMemory:
    """Memory system untuk agent — menyimpan konteks & pembelajaran.

    Attributes:
        working: Konteks aktif session (findings, source code, dll)
        episodic: Riwayat langkah-langkah yang sudah diambil
        semantic: Pengetahuan yang terakumulasi antar session
    """

    def __init__(self) -> None:
        self.working: dict[str, Any] = {}
        self.episodic: list[MemoryEntry] = []
        self.semantic: dict[str, Any] = {}
        log.info("agent_memory_initialized")

    # ── Working Memory ─────────────────────────────────────

    def set_working(self, key: str, value: Any) -> None:
        """Simpan data ke working memory (konteks session aktif)."""
        self.working[key] = value
        if len(self.working) > MAX_WORKING_ENTRIES:
            # Hapus item paling lama
            oldest = next(iter(self.working))
            del self.working[oldest]

    def get_working(self, key: str, default: Any = None) -> Any:
        """Ambil data dari working memory."""
        return self.working.get(key, default)

    def has_working(self, key: str) -> bool:
        return key in self.working

    def clear_working(self) -> None:
        """Bersihkan working memory (saat session selesai)."""
        self.working.clear()

    # ── Episodic Memory ────────────────────────────────────

    def add_episode(self, key: str, content: Any, metadata: dict | None = None) -> None:
        """Catat satu kejadian dalam session."""
        entry = MemoryEntry(
            key=key,
            content=content,
            type="episodic",
            metadata=metadata or {},
        )
        self.episodic.append(entry)
        if len(self.episodic) > MAX_EPISODIC_ENTRIES:
            self.episodic.pop(0)

    def get_episodes(self, key: str | None = None) -> list[MemoryEntry]:
        """Ambil semua episode, filter by key jika diberikan."""
        if key is None:
            return list(self.episodic)
        return [e for e in self.episodic if e.key == key]

    def last_episodes(self, n: int = 5) -> list[MemoryEntry]:
        """Ambil N episode terakhir."""
        return self.episodic[-n:]

    # ── Semantic Memory ────────────────────────────────────

    def set_semantic(self, key: str, value: Any) -> None:
        """Simpan pengetahuan permanen."""
        self.semantic[key] = value
        if len(self.semantic) > MAX_SEMANTIC_ENTRIES:
            oldest = next(iter(self.semantic))
            del self.semantic[oldest]

    def get_semantic(self, key: str, default: Any = None) -> Any:
        """Ambil pengetahuan permanen."""
        return self.semantic.get(key, default)

    # ── Context Builder ────────────────────────────────────

    def build_context(self) -> str:
        """Bangun context string untuk LLM prompt.

        Menggabungkan working memory + episode terakhir menjadi
        deskripsi text yang bisa dipahami LLM.
        """
        parts: list[str] = ["=== WORKING MEMORY ==="]

        for key, value in self.working.items():
            val_str = str(value)
            if len(val_str) > 500:
                val_str = val_str[:500] + "..."
            parts.append(f"  {key}: {val_str}")

        parts.append("\n=== RECENT HISTORY ===")
        for ep in self.last_episodes(8):
            val_str = str(ep.content)
            if len(val_str) > 300:
                val_str = val_str[:300] + "..."
            parts.append(f"  [{ep.key}] {val_str}")

        return "\n".join(parts)

    # ── Stats ──────────────────────────────────────────────

    @property
    def total_entries(self) -> int:
        return len(self.working) + len(self.episodic) + len(self.semantic)
