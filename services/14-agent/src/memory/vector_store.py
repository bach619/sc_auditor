"""Vector memory — semantic search via embedding similarity.

Storage: ~/.sc_auditor/learning/vector_index.json
Embedding: simple TF-IDF fallback (no heavy ML dependencies)

Used for:
  - Mencari kasus mirip berdasarkan deskripsi bug
  - Pattern matching: "bug ini mirip dengan CASE-012 yang bounty $10k"
"""

from __future__ import annotations

import json
import math
import re
import string
from collections import Counter
from pathlib import Path
from typing import Any, List, Optional

import structlog

from .base import BaseMemory, MemoryEntry

log = structlog.get_logger(service="agent_memory", module="vector")


class TFIDFVectorizer:
    """Simple TF-IDF implementation — no heavy ML dependencies."""

    def __init__(self) -> None:
        self.doc_count = 0
        self.df: dict[str, int] = {}  # document frequency per term
        self.idf_cache: dict[str, float] = {}

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize and normalize text."""
        text = text.lower()
        text = text.translate(str.maketrans("", "", string.punctuation))
        return [w for w in re.split(r"\s+", text) if len(w) > 2]

    def fit(self, documents: list[str]) -> None:
        """Fit on a corpus of documents."""
        self.doc_count = len(documents)
        self.df = {}
        for doc in documents:
            terms = set(self._tokenize(doc))
            for term in terms:
                self.df[term] = self.df.get(term, 0) + 1
        self.idf_cache = {}

    def transform(self, text: str) -> dict[str, float]:
        """Transform text to TF-IDF vector (sparse dict)."""
        terms = self._tokenize(text)
        term_count = len(terms)
        if term_count == 0:
            return {}
        tf = Counter(terms)
        vector: dict[str, float] = {}
        for term, count in tf.items():
            tf_val = count / term_count
            idf_val = self._idf(term)
            vector[term] = tf_val * idf_val
        return vector

    def _idf(self, term: str) -> float:
        if term not in self.idf_cache:
            df = self.df.get(term, 1)
            self.idf_cache[term] = math.log((self.doc_count + 1) / (df + 1)) + 1
        return self.idf_cache[term]

    def cosine_similarity(self, vec_a: dict[str, float],
                          vec_b: dict[str, float]) -> float:
        """Cosine similarity between two sparse vectors."""
        dot = 0.0
        for term in vec_a:
            if term in vec_b:
                dot += vec_a[term] * vec_b[term]
        norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
        norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


class VectorMemory(BaseMemory):
    """Persistent vector memory with TF-IDF search.

    Stores entries in a JSON file and uses TF-IDF cosine similarity
    for semantic search — no external ML dependencies required.
    """

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self.storage_path = Path(storage_path or Path.home() / ".sc_auditor" / "learning" / "vector_index.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.entries: list[MemoryEntry] = []
        self.vectorizer = TFIDFVectorizer()
        self._dirty = False
        self._load()

    # ── Persistence ─────────────────────────────────────────

    def _load(self) -> None:
        """Load entries from disk."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                self.entries = [MemoryEntry.from_dict(e) for e in data.get("entries", [])]
                log.info("vector_memory.loaded", count=len(self.entries), path=str(self.storage_path))
            except (json.JSONDecodeError, OSError) as e:
                log.warning("vector_memory.load_failed", error=str(e))
                self.entries = []

    def _save(self) -> None:
        """Save entries to disk."""
        try:
            data = {
                "entries": [e.to_dict() for e in self.entries],
            }
            self.storage_path.write_text(json.dumps(data, indent=2))
            self._dirty = False
        except OSError as e:
            log.error("vector_memory.save_failed", error=str(e))

    # ── BaseMemory Interface ────────────────────────────────

    async def store(self, entry: MemoryEntry) -> str:
        self.entries.append(entry)
        self._dirty = True
        self._save()
        log.debug("vector_memory.stored", entry_id=entry.entry_id)
        return entry.entry_id

    async def search(self, query: str, limit: int = 5, **filters: Any) -> list[MemoryEntry]:
        """Search by semantic similarity. Alias for retrieve()."""
        return await self.retrieve(query, limit=limit)

    async def store_text(self, key: str, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Store text as MemoryEntry (convenience wrapper for callers that pass key+content+metadata)."""
        entry = MemoryEntry(
            content=content,
            metadata={"key": key, **(metadata or {})},
            entry_id=key,
        )
        return await self.store(entry)

    async def retrieve(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        if not self.entries:
            return []

        # Build corpus and fit vectorizer
        corpus = [e.content for e in self.entries]
        self.vectorizer.fit(corpus)
        query_vec = self.vectorizer.transform(query)

        # Score all entries
        scored: list[tuple[float, MemoryEntry]] = []
        for entry in self.entries:
            entry_vec = self.vectorizer.transform(entry.content)
            score = self.vectorizer.cosine_similarity(query_vec, entry_vec)
            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    async def get(self, entry_id: str) -> MemoryEntry | None:
        for e in self.entries:
            if e.entry_id == entry_id:
                return e
        return None

    async def delete(self, entry_id: str) -> bool:
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.entry_id != entry_id]
        if len(self.entries) < before:
            self._save()
            return True
        return False

    async def clear(self) -> None:
        self.entries.clear()
        self._save()

    async def count(self) -> int:
        return len(self.entries)
