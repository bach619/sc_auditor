"""ContractSimilarity — AST-based contract comparison and clustering."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from src.config import config

# ── Feature extraction helpers ──────────────────────────────────

_SIG_RE = re.compile(r"function\s+(\w+)\s*\(([^)]*)\)")
_EVENT_RE = re.compile(r"event\s+(\w+)\s*\(([^)]*)\)")
_MODIFIER_RE = re.compile(r"modifier\s+(\w+)\s*\(([^)]*)\)")
_STATE_VAR_RE = re.compile(
    r"(?:public|internal|private)\s+(?:constant\s+)?(\w+(?:\[\])?(?:\s*<[^>]+>)?)\s+(public|internal|private)?\s*(\w+)"
)
_USING_RE = re.compile(r"import|from\s+['\"]|pragma\s+solidity")
_INTERFACE_RE = re.compile(r"interface\s+(\w+)")


def _extract_function_signatures(source: str) -> set[tuple[str, str]]:
    """Return set of (name, param_types_string)."""
    sigs: set[tuple[str, str]] = set()
    for m in _SIG_RE.finditer(source):
        name = m.group(1)
        params = m.group(2).strip()
        sigs.add((name, params))
    return sigs


def _extract_events(source: str) -> set[tuple[str, str]]:
    events: set[tuple[str, str]] = set()
    for m in _EVENT_RE.finditer(source):
        events.add((m.group(1), m.group(2).strip()))
    return events


def _extract_modifiers(source: str) -> set[str]:
    mods: set[str] = set()
    for m in _MODIFIER_RE.finditer(source):
        mods.add(m.group(1))
    return mods


def _extract_state_variables(source: str) -> set[str]:
    vars_: set[str] = set()
    for m in _STATE_VAR_RE.finditer(source):
        vars_.add(m.group(3))  # variable name
    return vars_


def _extract_interfaces(source: str) -> set[str]:
    ifaces: set[str] = set()
    for m in _INTERFACE_RE.finditer(source):
        ifaces.add(m.group(1))
    return ifaces


def _source_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


# ── Contract fingerprint ────────────────────────────────────────

class ContractFingerprint:
    """Lightweight structural fingerprint of a Solidity contract."""

    def __init__(self, source: str) -> None:
        self.source_hash: str = _source_hash(source)
        self.function_sigs: set[tuple[str, str]] = _extract_function_signatures(source)
        self.events: set[tuple[str, str]] = _extract_events(source)
        self.modifiers: set[str] = _extract_modifiers(source)
        self.state_vars: set[str] = _extract_state_variables(source)
        self.interfaces: set[str] = _extract_interfaces(source)
        self.n_functions: int = len(self.function_sigs)
        self.n_state_vars: int = len(self.state_vars)
        self.source_lines: int = source.count("\n") + 1

    def jaccard_similarity(self, other: ContractFingerprint) -> float:
        """Jaccard index over the union of feature sets."""
        sets_self = [
            self.function_sigs,
            self.events,
            self.modifiers,
            self.state_vars,
            self.interfaces,
        ]
        sets_other = [
            other.function_sigs,
            other.events,
            other.modifiers,
            other.state_vars,
            other.interfaces,
        ]
        total_intersection = 0
        total_union = 0
        for s, o in zip(sets_self, sets_other):
            inter = len(s & o)
            union = len(s | o)
            total_intersection += inter
            total_union += union
        if total_union == 0:
            return 0.0
        return total_intersection / total_union

    def structure_similarity(self, other: ContractFingerprint) -> float:
        """Penalize large differences in function count and source size."""
        fn_diff = abs(self.n_functions - other.n_functions)
        max_fn = max(self.n_functions, other.n_functions) or 1
        line_diff = abs(self.source_lines - other.source_lines)
        max_lines = max(self.source_lines, other.source_lines) or 1
        fn_factor = 1.0 - (fn_diff / max_fn)
        line_factor = 1.0 - (line_diff / max_lines)
        return 0.6 * fn_factor + 0.4 * line_factor

    def combined_similarity(self, other: ContractFingerprint) -> float:
        """Weighted combination of Jaccard and structure similarity."""
        j = self.jaccard_similarity(other)
        s = self.structure_similarity(other)
        return 0.7 * j + 0.3 * s


# ── Similarity database ─────────────────────────────────────────

class ContractSimilarity:
    """Manages contract fingerprints, similarity queries, and clustering."""

    def __init__(self, data_path: Path | None = None) -> None:
        self._data_path = data_path or config.similarity_file
        self._fingerprints: dict[str, ContractFingerprint] = {}  # contract_id -> fingerprint
        self._clusters: dict[str, list[str]] = defaultdict(list)  # cluster_id -> contract_ids
        self._load()

    # ── Persistence ────────────────────────────────────────────

    def _load(self) -> None:
        if not self._data_path.exists():
            return
        try:
            raw = json.loads(self._data_path.read_text("utf-8"))
            # Fingerprints aren't serialized directly; we store them as feature dicts
            self._clusters = defaultdict(list, raw.get("clusters", {}))
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self) -> None:
        self._data_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "clusters": dict(self._clusters),
            "contract_ids": list(self._fingerprints.keys()),
        }
        self._data_path.write_text(json.dumps(payload, indent=2), "utf-8")

    # ── Registration ───────────────────────────────────────────

    def register(self, contract_id: str, source: str) -> ContractFingerprint:
        """Register a contract; returns its fingerprint."""
        fp = ContractFingerprint(source)
        self._fingerprints[contract_id] = fp
        self._update_clusters(contract_id, fp)
        self._save()
        return fp

    # ── Similarity queries ─────────────────────────────────────

    def compare(self, contract_a: str, contract_b: str) -> float:
        """AST/feature-based similarity score (0.0–1.0)."""
        fp_a = self._fingerprints.get(contract_a)
        fp_b = self._fingerprints.get(contract_b)
        if fp_a is None or fp_b is None:
            return 0.0
        return fp_a.combined_similarity(fp_b)

    def find_similar(
        self, contract_id: str, threshold: float | None = None
    ) -> list[tuple[str, float]]:
        """Find all known contracts similar above *threshold* (default config)."""
        threshold = threshold if threshold is not None else config.similarity_threshold
        fp = self._fingerprints.get(contract_id)
        if fp is None:
            return []
        results: list[tuple[str, float]] = []
        for cid, other_fp in self._fingerprints.items():
            if cid == contract_id:
                continue
            score = fp.combined_similarity(other_fp)
            if score >= threshold:
                results.append((cid, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def get_fingerprint(self, contract_id: str) -> ContractFingerprint | None:
        return self._fingerprints.get(contract_id)

    # ── Clustering ──────────────────────────────────────────────

    def _update_clusters(self, contract_id: str, fp: ContractFingerprint) -> None:
        """Add contract to the best-matching cluster, or create a new one."""
        best_cluster: str | None = None
        best_score = 0.0
        for cluster_id, member_ids in self._clusters.items():
            if not member_ids:
                continue
            # Compare with first member of cluster
            first = member_ids[0]
            other_fp = self._fingerprints.get(first)
            if other_fp is None:
                continue
            score = fp.combined_similarity(other_fp)
            if score >= config.similarity_threshold and score > best_score:
                best_score = score
                best_cluster = cluster_id
        if best_cluster:
            self._clusters[best_cluster].append(contract_id)
        else:
            new_cluster = f"cluster_{len(self._clusters)}"
            self._clusters[new_cluster].append(contract_id)

    def get_clusters(self) -> dict[str, list[str]]:
        return dict(self._clusters)

    def get_cluster_for(self, contract_id: str) -> str | None:
        for cid, members in self._clusters.items():
            if contract_id in members:
                return cid
        return None

    # ── Stats ──────────────────────────────────────────────────

    @property
    def n_contracts(self) -> int:
        return len(self._fingerprints)

    @property
    def n_clusters(self) -> int:
        return len(self._clusters)


__all__ = ["ContractSimilarity", "ContractFingerprint"]
