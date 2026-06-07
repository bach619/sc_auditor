"""False Positive / True Positive Database — L3 Intelligence.

Stores feedback from users and the Classifier service about which findings
are True Positives (real bugs) vs False Positives (noise).

Uses this history to:
1. Auto-suppress detectors that consistently produce FPs for a contract
2. Boost severity for detectors that consistently produce TPs
3. Provide confidence scores for each finding type
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger()

# Default database path
DB_PATH = Path("/data/scanner-slither/fp_db.json")


class FeedbackEntry:
    """A single feedback entry for a finding."""

    def __init__(
        self,
        detector: str,
        contract_address: str,
        chain: str,
        is_tp: bool,
        severity: str = "medium",
        source: str = "user",
        timestamp: float | None = None,
    ) -> None:
        self.detector = detector
        self.contract_address = contract_address.lower()
        self.chain = chain.lower()
        self.is_tp = is_tp
        self.severity = severity
        self.source = source
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> dict:
        return {
            "detector": self.detector,
            "contract_address": self.contract_address,
            "chain": self.chain,
            "is_tp": self.is_tp,
            "severity": self.severity,
            "source": self.source,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> FeedbackEntry:
        return cls(
            detector=data["detector"],
            contract_address=data["contract_address"],
            chain=data.get("chain", ""),
            is_tp=data.get("is_tp", True),
            severity=data.get("severity", "medium"),
            source=data.get("source", "user"),
            timestamp=data.get("timestamp"),
        )


class FalsePositiveDB:
    """Persistent database of FP/TP feedback for Slither findings.

    Stores feedback per (detector, contract_address) and computes
    aggregate metrics for smart filtering.
    """

    def __init__(self, db_path: str | Path = DB_PATH) -> None:
        self._db_path = Path(db_path)
        self._entries: list[dict] = []
        self._load()

    # ── Public API ──────────────────────────────────────────

    def record_feedback(
        self,
        detector: str,
        contract_address: str,
        chain: str,
        is_tp: bool,
        severity: str = "medium",
        source: str = "user",
    ) -> None:
        """Record a single feedback entry."""
        entry = FeedbackEntry(
            detector=detector,
            contract_address=contract_address,
            chain=chain,
            is_tp=is_tp,
            severity=severity,
            source=source,
        )
        self._entries.append(entry.to_dict())
        self._save()
        log.info(
            "fp_db.recorded",
            detector=detector,
            contract=contract_address[:8],
            is_tp=is_tp,
            source=source,
        )

    def get_detector_stats(self, detector: str) -> dict[str, Any]:
        """Get aggregate stats for a detector across all contracts."""
        relevant = [e for e in self._entries if e["detector"] == detector]
        total = len(relevant)
        if total == 0:
            return {
                "detector": detector,
                "total_feedback": 0,
                "tp_count": 0,
                "fp_count": 0,
                "tp_ratio": 0.5,  # Default: unsure
                "confidence": "none",
            }

        tp_count = sum(1 for e in relevant if e["is_tp"])
        fp_count = total - tp_count
        tp_ratio = tp_count / total if total > 0 else 0.5

        return {
            "detector": detector,
            "total_feedback": total,
            "tp_count": tp_count,
            "fp_count": fp_count,
            "tp_ratio": round(tp_ratio, 3),
            "confidence": self._confidence_label(total, tp_ratio),
        }

    def get_contract_stats(self, contract_address: str) -> dict[str, Any]:
        """Get aggregate stats for a specific contract."""
        addr = contract_address.lower()
        relevant = [e for e in self._entries if e["contract_address"] == addr]
        total = len(relevant)

        if total == 0:
            return {"contract": addr[:8], "total_feedback": 0, "detectors": {}}

        detector_stats: dict[str, dict] = {}
        for entry in relevant:
            det = entry["detector"]
            if det not in detector_stats:
                detector_stats[det] = {"tp": 0, "fp": 0, "total": 0}
            if entry["is_tp"]:
                detector_stats[det]["tp"] += 1
            else:
                detector_stats[det]["fp"] += 1
            detector_stats[det]["total"] += 1

        return {
            "contract": addr[:8],
            "total_feedback": total,
            "detectors": detector_stats,
        }

    def should_suppress(
        self,
        detector: str,
        contract_address: str | None = None,
        threshold: float = 0.3,
    ) -> bool:
        """Check if a finding should be suppressed based on history.

        A finding is suppressed if:
        - The detector has a TP ratio < threshold globally
        - OR the detector has a TP ratio < threshold for this specific contract

        Args:
            detector: Detector name.
            contract_address: Optional contract address.
            threshold: Minimum TP ratio to keep (default 0.3 = 30% TP).

        Returns:
            True if the finding should be suppressed.
        """
        # Global check
        global_stats = self.get_detector_stats(detector)
        if global_stats["total_feedback"] >= 5 and global_stats["tp_ratio"] < threshold:
            log.debug(
                "fp_db.suppressing_global",
                detector=detector,
                tp_ratio=global_stats["tp_ratio"],
            )
            return True

        # Contract-specific check
        if contract_address:
            contract_stats = self.get_contract_stats(contract_address)
            det_stats = contract_stats.get("detectors", {}).get(detector, {})
            if det_stats.get("total", 0) >= 3:
                local_ratio = det_stats["tp"] / det_stats["total"]
                if local_ratio < threshold:
                    log.debug(
                        "fp_db.suppressing_local",
                        detector=detector,
                        contract=contract_address[:8],
                        tp_ratio=round(local_ratio, 3),
                    )
                    return True

        return False

    def get_boost_factor(self, detector: str) -> float:
        """Get severity boost factor for a consistently TP detector.

        Returns multiplier 1.0–2.0 based on historical TP ratio.
        """
        stats = self.get_detector_stats(detector)
        if stats["total_feedback"] < 3:
            return 1.0  # Not enough data
        if stats["tp_ratio"] > 0.8:
            return 1.5  # Boost by 50%
        if stats["tp_ratio"] > 0.95:
            return 2.0  # Double severity
        return 1.0

    def get_suppressed_detectors(self, contract_address: str) -> list[str]:
        """Get list of detectors to suppress for this contract."""
        suppressed = []
        contract_stats = self.get_contract_stats(contract_address)
        for detector, stats in contract_stats.get("detectors", {}).items():
            if stats["total"] >= 3 and (stats["tp"] / stats["total"]) < 0.3:
                suppressed.append(detector)
        return suppressed

    # ── Batch API ───────────────────────────────────────────

    def record_batch(self, entries: list[dict]) -> int:
        """Record multiple feedback entries at once.

        Returns number of entries added.
        """
        count = 0
        for entry in entries:
            try:
                fe = FeedbackEntry.from_dict(entry)
                self._entries.append(fe.to_dict())
                count += 1
            except (KeyError, ValueError) as exc:
                log.warning("fp_db.batch_skip", error=str(exc))
        if count > 0:
            self._save()
        return count

    def export_stats(self) -> dict[str, Any]:
        """Export full statistics for dashboard/reporting."""
        detectors = set(e["detector"] for e in self._entries)
        contracts = set(e["contract_address"] for e in self._entries)

        return {
            "total_feedback": len(self._entries),
            "unique_detectors": len(detectors),
            "unique_contracts": len(contracts),
            "detector_stats": {
                det: self.get_detector_stats(det) for det in sorted(detectors)
            },
            "global_tp_ratio": round(
                sum(1 for e in self._entries if e["is_tp"]) / max(len(self._entries), 1),
                3,
            ),
        }

    # ── Internal ─────────────────────────────────────────────

    def _load(self) -> None:
        """Load database from disk."""
        if not self._db_path.exists():
            self._entries = []
            return
        try:
            data = json.loads(self._db_path.read_text(encoding="utf-8"))
            self._entries = data if isinstance(data, list) else []
            log.info("fp_db.loaded", entries=len(self._entries), path=str(self._db_path))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("fp_db.load_failed", error=str(exc))
            self._entries = []

    def _save(self) -> None:
        """Save database to disk."""
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._db_path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self._entries, indent=2, default=str),
                encoding="utf-8",
            )
            tmp.replace(self._db_path)
        except OSError as exc:
            log.error("fp_db.save_failed", error=str(exc))

    @staticmethod
    def _confidence_label(total: int, tp_ratio: float) -> str:
        if total < 3:
            return "insufficient"
        if tp_ratio > 0.9:
            return "high"
        if tp_ratio > 0.7:
            return "medium"
        return "low"


def create_fp_db(db_path: str | Path = DB_PATH) -> FalsePositiveDB:
    """Create a configured FalsePositiveDB instance."""
    return FalsePositiveDB(db_path=db_path)
