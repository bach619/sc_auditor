"""SQLite-backed stores for 07-classifier service.

Provides drop-in replacements for:
- Classifier.findings  (findings.json  → SQLite)
- PatternLearner       (patterns.json  → SQLite)
- MetricsTracker       (metrics.json   → SQLite)
- Feedback store       (feedback.json  → SQLite)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from shared.storage import SqliteStore, StoreConfig
from . import schema

logger = logging.getLogger("vyper.classifier.store")


class ClassifierSQLiteStore:
    """SQLite-backed storage for classifier findings, patterns, feedback, metrics."""

    def __init__(self, db_path: str = "/data/classifier/classifier.db") -> None:
        self._store = SqliteStore(StoreConfig(
            db_path=db_path,
            journal_mode="WAL",
            cache_size=-10000,
            auto_migrate=False,
        ))
        self._init_schema()

    def _init_schema(self) -> None:
        for stmt in schema.SCHEMA_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                self._store.execute(stmt)
        logger.info("ClassifierSQLiteStore initialized")

    # ── Findings ────────────────────────────────────────────

    def get_findings(self, audit_id: str | None = None, severity: str | None = None) -> list[dict]:
        if audit_id:
            return self._store.query_all(
                "SELECT * FROM findings WHERE audit_id = ? ORDER BY created_at DESC",
                (audit_id,)
            )
        if severity:
            return self._store.query_all(
                "SELECT * FROM findings WHERE severity = ? ORDER BY created_at DESC",
                (severity,)
            )
        return self._store.query_all("SELECT * FROM findings ORDER BY created_at DESC")

    def get_finding(self, finding_id: str) -> dict | None:
        return self._store.query_one("SELECT * FROM findings WHERE finding_id = ?", (finding_id,))

    def save_finding(self, data: dict) -> None:
        data.setdefault("updated_at", None)  # Let SQLite default handle it
        self._store.upsert("findings", {"finding_id": data["finding_id"]}, data)

    def save_findings_batch(self, findings: list[dict]) -> int:
        """Batch upsert — efficient for bulk operations."""
        count = 0
        for f in findings:
            self.save_finding(f)
            count += 1
        return count

    def delete_finding(self, finding_id: str) -> bool:
        return self._store.delete("findings", {"finding_id": finding_id}) > 0

    # ── Classification Layers ───────────────────────────────

    def add_classification_layer(self, finding_id: str, layer: dict) -> int:
        return self._store.insert("classification_layers", {
            "finding_id": finding_id,
            "stage": layer.get("stage", "raw"),
            "classification": layer.get("classification", "unknown"),
            "source": layer.get("source", "classifier"),
            "confidence": layer.get("confidence", 0.0),
            "reasoning": layer.get("reasoning"),
        })

    def get_classification_layers(self, finding_id: str) -> list[dict]:
        return self._store.query_all(
            "SELECT * FROM classification_layers WHERE finding_id = ? ORDER BY id",
            (finding_id,)
        )

    # ── Patterns ────────────────────────────────────────────

    def get_patterns(self, pattern_type: str | None = None) -> list[dict]:
        if pattern_type:
            return self._store.query_all(
                "SELECT * FROM patterns WHERE pattern_type = ?", (pattern_type,)
            )
        return self._store.query_all("SELECT * FROM patterns WHERE is_active = 1")

    def get_pattern(self, pattern_id: str) -> dict | None:
        return self._store.query_one("SELECT * FROM patterns WHERE pattern_id = ?", (pattern_id,))

    def save_pattern(self, pattern: dict) -> None:
        pattern.setdefault("rules_json", json.dumps(pattern.get("rules", {})))
        pattern.pop("rules", None)
        self._store.upsert("patterns", {"pattern_id": pattern["pattern_id"]}, pattern)

    # ── Feedback ────────────────────────────────────────────

    def save_feedback(self, feedback: dict) -> None:
        self._store.upsert("feedback", {"feedback_id": feedback["feedback_id"]}, feedback)

    def get_feedback(self, finding_id: str) -> list[dict]:
        return self._store.query_all(
            "SELECT * FROM feedback WHERE finding_id = ? ORDER BY created_at DESC",
            (finding_id,)
        )

    # ── False Records ───────────────────────────────────────

    def save_false_record(self, record_type: str, finding_id: str, audit_id: str | None = None, reason: str = "") -> None:
        self._store.insert("false_records", {
            "record_type": record_type,
            "finding_id": finding_id,
            "audit_id": audit_id,
            "reason": reason,
        })

    def get_false_records(self, record_type: str | None = None) -> list[dict]:
        if record_type:
            return self._store.query_all(
                "SELECT * FROM false_records WHERE record_type = ?", (record_type,)
            )
        return self._store.query_all("SELECT * FROM false_records")

    # ── Metrics ─────────────────────────────────────────────

    def save_metrics(self, date: str, tool_name: str | None, metrics_data: dict) -> None:
        self._store.upsert("metrics", {"date": date, "tool_name": tool_name or "__aggregate__"}, {
            "tp": metrics_data.get("tp", 0),
            "fp": metrics_data.get("fp", 0),
            "tn": metrics_data.get("tn", 0),
            "fn": metrics_data.get("fn", 0),
            "precision": metrics_data.get("precision", 0.0),
            "recall": metrics_data.get("recall", 0.0),
            "f1_score": metrics_data.get("f1_score", 0.0),
            "accuracy": metrics_data.get("accuracy", 0.0),
            "overall_score": metrics_data.get("overall_score", 0.0),
        })

    def get_metrics(self, tool_name: str | None = None) -> list[dict]:
        if tool_name:
            return self._store.query_all(
                "SELECT * FROM metrics WHERE tool_name = ? ORDER BY date DESC", (tool_name,)
            )
        return self._store.query_all("SELECT * FROM metrics WHERE tool_name = '__aggregate__' ORDER BY date DESC")

    # ── Maintenance ─────────────────────────────────────────

    def health(self) -> dict:
        return self._store.health_check()
