"""Agent memory system — persistent + in-memory memory types.

Three persistent memory types:
  - VectorMemory: Semantic search via TF-IDF cosine similarity
  - EpisodicMemory: Audit experience storage and recall
  - GraphMemory: Knowledge graph of vulnerabilities

Plus legacy in-memory AgentMemory for backward compatibility.

Integration with Case Management (Agenda 05):
  - Setiap CASE CLOSED → masuk ke VectorMemory sebagai pattern
  - Setiap audit selesai → masuk ke EpisodicMemory sebagai episode
  - Pattern vulnerability → masuk ke GraphMemory sebagai node/edge
"""

from __future__ import annotations

from typing import Any

from src.inmem_memory import AgentMemory as InMemoryAgentMemory

from .base import BaseMemory, MemoryEntry
from .episodic import EpisodicMemory
from .graph_memory import GraphMemory
from .vector_store import VectorMemory

__all__ = [
    "AgentMemory",
    "BaseMemory",
    "EpisodicMemory",
    "GraphMemory",
    "MemoryEntry",
    "VectorMemory",
]


class AgentMemory(InMemoryAgentMemory):
    """Enhanced AgentMemory — legacy in-memory + persistent memory types.

    Extends the original in-memory AgentMemory with persistent
    vector, episodic, and graph memory backends.
    """

    def __init__(self) -> None:
        super().__init__()
        self.vector = VectorMemory()
        # NOTE: self.episodic (list) is inherited from InMemoryAgentMemory
        # for backward compat with sync add_episode()/last_episodes() calls.
        # Persistent episodic storage uses episodic_store instead.
        self.episodic_store = EpisodicMemory()
        self.graph = GraphMemory()

    async def learn_from_case(self, case_data: dict[str, Any]) -> None:
        """Learn from a closed case — store in all memory types."""
        # Store in vector memory for semantic search
        content = f"{case_data.get('description', '')} {case_data.get('recommendation', '')}"
        await self.vector.store(MemoryEntry(
            content=content,
            metadata={
                "case_id": case_data.get("case_id", ""),
                "severity": case_data.get("severity", "Medium"),
                "contract": case_data.get("contract", ""),
                "function": case_data.get("function", ""),
                "bounty": case_data.get("bounty_amount"),
            },
            entry_id=case_data.get("case_id"),
            timestamp=case_data.get("closed_at"),
        ))

        # Store in episodic memory (persistent)
        await self.episodic_store.store_episode(case_data)

        # Store in graph memory
        self.graph.add_node(
            case_data.get("case_id", "unknown"),
            "vulnerability",
            {"title": case_data.get("title", ""),
             "severity": case_data.get("severity", "Medium")},
        )

    async def find_similar_cases(self, description: str, limit: int = 5) -> list[MemoryEntry]:
        """Find similar cases by semantic similarity."""
        return await self.vector.retrieve(description, limit=limit)

    def get_all_stats(self) -> dict:
        """Return statistics for all memory types including persistent stores."""
        return {
            "working": len(self.working),
            "episodic_inmem": len(self.episodic) if isinstance(self.episodic, list) else 0,
            "semantic": len(self.semantic),
            "vector_persistent": len(self.vector.entries),
            "graph_nodes": len(self.graph.nodes),
            "graph_edges": len(self.graph.edges),
        }

    def memory_stats(self) -> dict[str, Any]:
        """Return statistics for all memory types."""
        return {
            "working": len(self.working),
            "episodic_inmem": len(self.episodic) if isinstance(self.episodic, list) else 0,
            "semantic": len(self.semantic),
            "vector_persistent": 0,  # would need count() which is async
            "graph_nodes": len(self.graph.nodes),
            "graph_edges": len(self.graph.edges),
        }
