"""KnowledgeRepository — unified read/write layer for shared knowledge.

Both Classifier and Exploit services use this repository to persist
and query confirmed findings, attack patterns, and feedback data.

File layout on ``/data/knowledge/``:
    confirmed_tp.json   — List of ConfirmedFinding (exploit + human confirmed)
    feedback.json        — List of human feedback records
    stats.json           — Pre-computed KnowledgeStats
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .models import ConfirmedFinding, KnowledgeStats

log = logging.getLogger("vyper.knowledge_base")

KNOWLEDGE_DIR = Path("/data/knowledge")
CONFIRMED_FILE = KNOWLEDGE_DIR / "confirmed_tp.json"
FEEDBACK_FILE = KNOWLEDGE_DIR / "feedback.json"
STATS_FILE = KNOWLEDGE_DIR / "stats.json"


class KnowledgeRepository:
    """Persistence layer for the unified knowledge base.

    Usage::

        kb = KnowledgeRepository()
        kb.save_confirmed(finding)
        all_confirmed = kb.get_all_confirmed()
        matches = kb.find_matching_contracts(contract_hash)
    """

    def __init__(self, data_dir: str | Path = KNOWLEDGE_DIR) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _confirmed_file(self) -> Path:
        return self.data_dir / "confirmed_tp.json"

    @property
    def _feedback_file(self) -> Path:
        return self.data_dir / "feedback.json"

    @property
    def _stats_file(self) -> Path:
        return self.data_dir / "stats.json"

    # ── Confirmed Findings ───────────────────────────────────

    def save_confirmed(self, finding: ConfirmedFinding) -> None:
        """Persist a confirmed finding to the shared knowledge base.

        Thread-safe: uses atomic write (tmp + replace).
        """
        records = self._load_json(self._confirmed_file, [])
        # Deduplicate by finding_id
        records = [r for r in records if r.get("finding_id") != finding.finding_id]
        records.append(self._to_dict(finding))
        self._save_json(self._confirmed_file, records)
        log.info(
            "kb.confirmed_saved",
            finding_id=finding.finding_id,
            confirmed_by=finding.confirmed_by,
        )

    def get_all_confirmed(self) -> list[ConfirmedFinding]:
        """Return all confirmed findings."""
        records = self._load_json(self._confirmed_file, [])
        return [ConfirmedFinding(**r) for r in records]

    def find_matching_contracts(
        self, contract_hash: str
    ) -> list[ConfirmedFinding]:
        """Find confirmed findings matching a contract hash.

        Args:
            contract_hash: SHA-256 hash of contract source.

        Returns:
            List of confirmed findings for this contract.
        """
        records = self._load_json(self._confirmed_file, [])
        return [
            ConfirmedFinding(**r)
            for r in records
            if r.get("contract_hash") == contract_hash
        ]

    def find_matching_pattern(
        self,
        contract_hash: str | None = None,
        attack_type: str | None = None,
        severity: str | None = None,
    ) -> list[ConfirmedFinding]:
        """Find confirmed findings matching a pattern.

        Args:
            contract_hash: Optional contract hash filter.
            attack_type: Optional attack type filter.
            severity: Optional severity filter.

        Returns:
            Matching confirmed findings.
        """
        records = self._load_json(self._confirmed_file, [])
        results = []
        for r in records:
            if contract_hash and r.get("contract_hash") != contract_hash:
                continue
            if attack_type and r.get("attack_type") != attack_type:
                continue
            if severity and r.get("severity") != severity:
                continue
            results.append(ConfirmedFinding(**r))
        return results

    def count_confirmed(self) -> int:
        """Return total number of confirmed findings."""
        return len(self._load_json(self._confirmed_file, []))

    # ── Feedback ─────────────────────────────────────────────

    def save_feedback(self, record: dict[str, Any]) -> None:
        """Persist human feedback to the shared knowledge base.

        Args:
            record: Feedback dict with finding_id, classification,
                    is_correction, notes, etc.
        """
        records = self._load_json(self._feedback_file, [])
        records.append(record)
        self._save_json(self._feedback_file, records)
        log.info(
            "kb.feedback_saved",
            finding_id=record.get("finding_id"),
            is_correction=record.get("is_correction"),
        )

    def get_all_feedback(self) -> list[dict[str, Any]]:
        """Return all human feedback records."""
        return self._load_json(self._feedback_file, [])

    # ── Stats ────────────────────────────────────────────────

    def get_stats(self) -> KnowledgeStats:
        """Compute and cache aggregated statistics.

        Returns:
            KnowledgeStats with current aggregated data.
        """
        confirmed = self.get_all_confirmed()

        attack_type_counts: dict[str, int] = {}
        exploit_count = 0
        human_count = 0
        contract_hashes: set[str] = set()

        for f in confirmed:
            if f.confirmed_by == "exploit":
                exploit_count += 1
            elif f.confirmed_by == "human":
                human_count += 1
            contract_hashes.add(f.contract_hash)
            attack_type_counts[f.attack_type] = (
                attack_type_counts.get(f.attack_type, 0) + 1
            )

        top_attack_types = sorted(
            attack_type_counts.items(), key=lambda x: -x[1]
        )[:10]

        stats = KnowledgeStats(
            total_confirmed=len(confirmed),
            confirmed_by_exploit=exploit_count,
            confirmed_by_human=human_count,
            unique_contracts=len(contract_hashes),
            unique_attack_types=list(attack_type_counts.keys()),
            top_attack_types=top_attack_types,
        )
        self._save_json(self._stats_file, self._to_dict(stats))
        return stats

    # ── Internal Helpers ─────────────────────────────────────

    @staticmethod
    def _load_json(path: Path, default: Any = None) -> Any:
        """Load JSON from file, returning default if missing/corrupt."""
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("kb.load_error", path=str(path), error=str(exc))
        return default if default is not None else {}

    @staticmethod
    def _save_json(path: Path, data: Any) -> bool:
        """Save JSON atomically (tmp + replace)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        try:
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2, default=str)
            tmp.replace(path)
            return True
        except OSError as exc:
            log.error("kb.save_error", path=str(path), error=str(exc))
            if tmp.exists():
                tmp.unlink()
            return False

    @staticmethod
    def _to_dict(obj: Any) -> dict[str, Any]:
        """Convert a dataclass (or any object with __dict__) to dict."""
        if hasattr(obj, "__dataclass_fields__"):
            result = {}
            for field_name in obj.__dataclass_fields__:
                value = getattr(obj, field_name)
                if hasattr(value, "__dataclass_fields__"):
                    result[field_name] = KnowledgeRepository._to_dict(value)
                elif isinstance(value, list):
                    result[field_name] = [
                        KnowledgeRepository._to_dict(v)
                        if hasattr(v, "__dataclass_fields__")
                        else v
                        for v in value
                    ]
                else:
                    result[field_name] = value
            return result
        return obj
