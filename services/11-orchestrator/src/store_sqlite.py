"""SQLite-backed storage for 11-orchestrator service.

Drop-in replacements for:
- Pipeline audit log     (audit_log.json → SQLite)
- Priority queue         (queue.json    → SQLite)
- Daemon state           (daemon_state.json → SQLite)
- Scan metrics / similarity
"""

from __future__ import annotations

import json
import logging
from typing import Any

from services.shared.storage import SqliteStore, StoreConfig
from . import schema

logger = logging.getLogger("vyper.orchestrator.store")


class OrchestratorSQLiteStore:
    """SQLite-backed storage for audit pipeline orchestration."""

    def __init__(self, db_path: str = "/data/orchestrator/orchestrator.db") -> None:
        self._store = SqliteStore(StoreConfig(
            db_path=db_path,
            journal_mode="WAL",
            cache_size=-20000,  # 20 MB — needs more for large audit data
            auto_migrate=False,
        ))
        self._init_schema()

    def _init_schema(self) -> None:
        for stmt in schema.SCHEMA_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                self._store.execute(stmt)
        logger.info("OrchestratorSQLiteStore initialized")

    # ── Audits ─────────────────────────────────────────────

    def save_audit(self, record: dict) -> int:
        """Save or update an audit record."""
        data = dict(record)
        # Serialize JSON fields
        data["metadata_json"] = json.dumps(data.get("metadata", {}))
        data["partial_results"] = json.dumps(data.get("partial_results", {}))
        data.pop("metadata", None)
        data.pop("steps", None)  # Steps saved separately
        return self._store.upsert("audits", {"audit_id": data["audit_id"]}, data)

    def get_audit(self, audit_id: str) -> dict | None:
        row = self._store.query_one("SELECT * FROM audits WHERE audit_id = ?", (audit_id,))
        if row:
            row["metadata"] = json.loads(row.get("metadata_json", "{}"))
            row["partial_results"] = json.loads(row.get("partial_results", "{}"))
            row["steps"] = self.get_pipeline_steps(audit_id)
        return row

    def get_audits(self, status: str | None = None, chain: str | None = None, limit: int = 100) -> list[dict]:
        conditions = []
        params: list[Any] = []
        if status:
            conditions.append("state = ?")
            params.append(status)
        if chain:
            conditions.append("chain = ?")
            params.append(chain)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM audits {where} ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        return self._store.query_all(sql, tuple(params))

    def delete_audit(self, audit_id: str) -> bool:
        self._store.delete("pipeline_steps", {"audit_id": audit_id})
        self._store.delete("audit_data", {"audit_id": audit_id})
        return self._store.delete("audits", {"audit_id": audit_id}) > 0

    # ── Pipeline Steps ─────────────────────────────────────

    def save_pipeline_step(self, audit_id: str, step: dict) -> None:
        data = dict(step)
        data["result_json"] = json.dumps(data.get("result", {})) if data.get("result") else None
        data.pop("result", None)
        data.setdefault("audit_id", audit_id)
        self._store.upsert("pipeline_steps", {"audit_id": audit_id, "step_name": data["step_name"]}, data)

    def get_pipeline_steps(self, audit_id: str) -> list[dict]:
        return self._store.query_all(
            "SELECT * FROM pipeline_steps WHERE audit_id = ? ORDER BY id",
            (audit_id,)
        )

    # ── Audit Data ─────────────────────────────────────────

    def save_audit_data(self, audit_id: str, data: dict) -> None:
        self._store.upsert("audit_data", {"audit_id": audit_id}, data)

    def get_audit_data(self, audit_id: str) -> dict | None:
        return self._store.query_one("SELECT * FROM audit_data WHERE audit_id = ?", (audit_id,))

    # ── Queue ──────────────────────────────────────────────

    def enqueue(self, item: dict) -> None:
        self._store.upsert("queue", {"contract_id": item["contract_id"]}, item)

    def dequeue(self, contract_id: str) -> bool:
        return self._store.delete("queue", {"contract_id": contract_id}) > 0

    def get_queue(self, sort_by_score: bool = True) -> list[dict]:
        order = "ORDER BY priority_score DESC" if sort_by_score else "ORDER BY created_at"
        return self._store.query_all(f"SELECT * FROM queue {order}")

    # ── Daemon State ───────────────────────────────────────

    def save_daemon_state(self, data: dict) -> None:
        data["id"] = 1
        self._store.upsert("daemon_state", {"id": 1}, data)

    def get_daemon_state(self) -> dict | None:
        return self._store.query_one("SELECT * FROM daemon_state WHERE id = 1")

    # ── Scan Metrics ───────────────────────────────────────

    def save_scan_metric(self, audit_id: str, scanner: str, duration_ms: int, findings_count: int, success: bool = True) -> None:
        self._store.insert("scan_metrics", {
            "audit_id": audit_id,
            "scanner": scanner,
            "duration_ms": duration_ms,
            "findings_count": findings_count,
            "success": 1 if success else 0,
        })

    def get_scan_metrics(self, audit_id: str | None = None) -> list[dict]:
        if audit_id:
            return self._store.query_all(
                "SELECT * FROM scan_metrics WHERE audit_id = ?", (audit_id,)
            )
        return self._store.query_all("SELECT * FROM scan_metrics ORDER BY scanned_at DESC LIMIT 100")

    # ── Maintenance ─────────────────────────────────────────

    def health(self) -> dict:
        return self._store.health_check()
