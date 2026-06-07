"""Graph memory — knowledge graph of vulnerabilities.

Nodes:
  - Contract (address, chain, compiler_version)
  - Function (name, signature)
  - Vulnerability (type, severity, pattern)
  - Fix (pattern, recommendation)

Edges:
  - Contract HAS_FUNCTION Function
  - Function HAS_VULN Vulnerability
  - Vulnerability FIXED_BY Fix
  - Vulnerability SIMILAR_TO Vulnerability

Storage: ~/.sc_auditor/learning/graph.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(service="agent_memory", module="graph")


class GraphMemory:
    """Persistent graph memory — knowledge graph of vulnerabilities.

    Note: GraphMemory does NOT extend BaseMemory because its API
    is fundamentally different (nodes + edges vs entries).
    """

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self.storage_path = Path(storage_path or Path.home() / ".sc_auditor" / "learning" / "graph.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []
        self._load()

    # ── Persistence ─────────────────────────────────────────

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                self.nodes = data.get("nodes", {})
                self.edges = data.get("edges", [])
                log.info("graph_memory.loaded", nodes=len(self.nodes), edges=len(self.edges))
            except (json.JSONDecodeError, OSError) as e:
                log.warning("graph_memory.load_failed", error=str(e))

    def _save(self) -> None:
        try:
            self.storage_path.write_text(json.dumps(
                {"nodes": self.nodes, "edges": self.edges}, indent=2
            ))
        except OSError as e:
            log.error("graph_memory.save_failed", error=str(e))

    # ── Node Operations ─────────────────────────────────────

    def add_node(self, node_id: str, node_type: str,
                 properties: dict[str, Any] | None = None) -> None:
        """Add or update a node."""
        self.nodes[node_id] = {
            "type": node_type,
            "properties": properties or {},
        }
        self._save()

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        return self.nodes.get(node_id)

    def find_nodes_by_type(self, node_type: str) -> list[tuple[str, dict[str, Any]]]:
        return [(nid, nd) for nid, nd in self.nodes.items() if nd.get("type") == node_type]

    def find_nodes_by_property(self, key: str, value: Any) -> list[tuple[str, dict[str, Any]]]:
        return [
            (nid, nd) for nid, nd in self.nodes.items()
            if nd.get("properties", {}).get(key) == value
        ]

    def delete_node(self, node_id: str) -> bool:
        if node_id in self.nodes:
            del self.nodes[node_id]
            self.edges = [e for e in self.edges
                         if e["from"] != node_id and e["to"] != node_id]
            self._save()
            return True
        return False

    # ── Edge Operations ─────────────────────────────────────

    def add_edge(self, from_id: str, to_id: str, relation: str,
                 properties: dict[str, Any] | None = None) -> None:
        """Add a directed edge between two nodes."""
        self.edges.append({
            "from": from_id,
            "to": to_id,
            "relation": relation,
            "properties": properties or {},
        })
        self._save()

    def find_edges(self, from_id: str | None = None,
                   to_id: str | None = None,
                   relation: str | None = None) -> list[dict[str, Any]]:
        """Find edges matching given filters."""
        results = self.edges
        if from_id:
            results = [e for e in results if e["from"] == from_id]
        if to_id:
            results = [e for e in results if e["to"] == to_id]
        if relation:
            results = [e for e in results if e["relation"] == relation]
        return results

    # ── Graph Traversal ─────────────────────────────────────

    def find_path(self, from_type: str | None = None,
                  to_type: str | None = None,
                  max_depth: int = 3) -> list[list[str]]:
        """BFS to find connection paths between node types."""
        start_ids = [nid for nid, nd in self.nodes.items()
                     if from_type is None or nd.get("type") == from_type]

        paths: list[list[str]] = []
        for start_id in start_ids:
            visited = {start_id}
            queue: list[tuple[str, list[str]]] = [(start_id, [start_id])]

            while queue:
                current, path = queue.pop(0)
                if len(path) > max_depth:
                    continue
                if to_type and self.nodes.get(current, {}).get("type") == to_type and len(path) > 1:
                    paths.append(path)
                    continue

                for edge in self.edges:
                    if edge["from"] == current and edge["to"] not in visited:
                        visited.add(edge["to"])
                        queue.append((edge["to"], path + [edge["to"]]))
                    elif edge["to"] == current and edge["from"] not in visited:
                        visited.add(edge["from"])
                        queue.append((edge["from"], path + [edge["from"]]))

        return paths[:10]

    # ── Stats ───────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return graph statistics."""
        type_counts: dict[str, int] = {}
        for nd in self.nodes.values():
            t = nd.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        rel_counts: dict[str, int] = {}
        for e in self.edges:
            r = e.get("relation", "unknown")
            rel_counts[r] = rel_counts.get(r, 0) + 1

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": type_counts,
            "relation_types": rel_counts,
        }

    async def count(self) -> int:
        return len(self.nodes)
