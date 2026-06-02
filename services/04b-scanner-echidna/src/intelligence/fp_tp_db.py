"""FP/TP Database — L3 Intelligence.

Tracks flaky Echidna tests and provides confidence adjustment
based on historical false positive rates.

Design:
- Persistent JSON file in data directory
- Each record: {test_function, verdict, audit_id, timestamp, notes}
- Query: FP rate per function, per category
- Auto-prune records older than 90 days
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class FpRecord:
    """A single FP/TP tracking record."""
    test_function: str
    verdict: str  # "true_positive" | "false_positive"
    audit_id: str
    category: str = "unknown"
    timestamp: float = field(default_factory=time.time)
    notes: str = ""


FP_RETENTION_DAYS = 90
MAX_RECORDS = 10_000


class FpTpDatabase:
    """Persistent FP/TP tracking database."""

    def __init__(self, data_dir: str | Path = "/data/scanner-echidna") -> None:
        self._path = Path(data_dir) / "fp_tp_db.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._records: list[FpRecord] = []
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text())
                self._records = [FpRecord(**r) for r in raw[-MAX_RECORDS:]]
            except (json.JSONDecodeError, KeyError, TypeError):
                self._records = []

    def _save(self) -> None:
        raw = [asdict(r) for r in self._records[-MAX_RECORDS:]]
        self._path.write_text(json.dumps(raw, indent=2))

    def record(
        self,
        test_function: str,
        verdict: str,
        audit_id: str,
        category: str = "unknown",
        notes: str = "",
    ) -> None:
        """Record a FP/TP verdict for a test function."""
        self._records.append(FpRecord(
            test_function=test_function,
            verdict=verdict,
            audit_id=audit_id,
            category=category,
            notes=notes,
        ))
        self._prune()
        self._save()

    def get_fp_rate(self, test_function: str) -> float:
        """Get false positive rate for a test function (0.0-1.0)."""
        records = [r for r in self._records if r.test_function == test_function]
        if not records:
            return 0.0
        fps = sum(1 for r in records if r.verdict == "false_positive")
        return round(fps / len(records), 3)

    def get_adjusted_confidence(self, test_function: str, base_confidence: float = 1.0) -> float:
        """Adjust confidence based on historical FP rate."""
        fp_rate = self.get_fp_rate(test_function)
        adjusted = base_confidence * (1.0 - fp_rate * 0.8)
        return round(max(0.1, min(1.0, adjusted)), 3)

    def get_flaky_tests(self, threshold: float = 0.3) -> list[dict[str, Any]]:
        """Return tests with FP rate above threshold."""
        functions = set(r.test_function for r in self._records)
        flaky = []
        for func in functions:
            fp_rate = self.get_fp_rate(func)
            if fp_rate >= threshold:
                flaky.append({
                    "test_function": func,
                    "fp_rate": fp_rate,
                    "total_records": sum(1 for r in self._records if r.test_function == func),
                })
        return sorted(flaky, key=lambda x: x["fp_rate"], reverse=True)

    def get_stats(self) -> dict[str, Any]:
        """Get aggregate stats."""
        if not self._records:
            return {"total_records": 0, "fp_rate": 0.0, "flaky_tests": []}
        total = len(self._records)
        fps = sum(1 for r in self._records if r.verdict == "false_positive")
        return {
            "total_records": total,
            "total_fp": fps,
            "total_tp": total - fps,
            "fp_rate": round(fps / total, 3),
            "flaky_tests": self.get_flaky_tests(),
        }

    def _prune(self) -> None:
        cutoff = time.time() - FP_RETENTION_DAYS * 86400
        self._records = [r for r in self._records if r.timestamp >= cutoff]


def create_fp_tp_db(data_dir: str | Path = "/data/scanner-echidna") -> FpTpDatabase:
    return FpTpDatabase(data_dir=data_dir)
