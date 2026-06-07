"""Base memory interface — semua persistent memory types mengikuti interface ini.

All memory types (vector, episodic, graph) implement this ABC
for consistent store/retrieve/delete/clear semantics.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any


class MemoryEntry:
    """A single memory entry with metadata."""

    def __init__(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        entry_id: str | None = None,
        timestamp: str | None = None,
        embedding: list[float] | None = None,
    ) -> None:
        self.entry_id = entry_id or str(uuid.uuid4())[:8]
        self.content = content
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.now(UTC).isoformat()
        self.embedding = embedding

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "embedding": self.embedding,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        return cls(
            entry_id=data.get("entry_id"),
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp"),
            embedding=data.get("embedding"),
        )


class BaseMemory(ABC):
    """Abstract base class for all memory types."""

    @abstractmethod
    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry. Returns entry_id."""
        ...

    @abstractmethod
    async def retrieve(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Retrieve entries matching query."""
        ...

    @abstractmethod
    async def get(self, entry_id: str) -> MemoryEntry | None:
        """Get a specific entry by ID."""
        ...

    @abstractmethod
    async def delete(self, entry_id: str) -> bool:
        """Delete an entry by ID. Returns True if deleted."""
        ...

    @abstractmethod
    async def clear(self) -> None:
        """Clear all entries."""
        ...

    @abstractmethod
    async def count(self) -> int:
        """Return total number of entries."""
        ...
