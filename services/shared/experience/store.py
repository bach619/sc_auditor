"""ExperienceStore — penyimpanan experiences lokal per-agent.

Menggunakan SQLite untuk persistence + JSON export/import.
Setiap agent punya database sendiri di DATA_DIR/experiences/
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .models import AuditExperience, ExperienceConsolidation, ExperienceQuery


class ExperienceStore:
    """SQLite-based experience store with thread-safe operations.

    Schema:
      experiences — tabel utama untuk AuditExperience
      consolidations — tabel untuk pattern/knowledge yang sudah di-consolidate
      experience_tags — many-to-many tags untuk experiences

    Resilience:
      Jika database tidak bisa ditulis (read-only filesystem, permission denied),
      ExperienceStore otomatis fallback ke in-memory SQLite. Agent tetap bisa
      start tanpa persistence. Log warning ditulis via logger.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._readonly_fallback = False
        self._local = threading.local()

        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
        except (sqlite3.OperationalError, PermissionError) as exc:
            # Fallback ke in-memory jika filesystem read-only atau permission denied
            import structlog
            _log = structlog.get_logger("vyper.experience")
            _log.warning(
                "experience.store.readonly_fallback",
                db_path=str(self._db_path),
                error=str(exc),
                reason=(
                    "Database is on a read-only filesystem or directory has "
                    "wrong ownership. Falling back to in-memory store. "
                    "Experiences will NOT be persisted across restarts."
                ),
            )
            self._readonly_fallback = True
            self._db_path = Path(":memory:")
            self._local = threading.local()
            self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        """Dapatkan koneksi SQLite (thread-local)."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._db_path))
            self._local.conn.row_factory = sqlite3.Row
            # WAL dan synchronous hanya untuk file-based DB, skip untuk :memory:
            if not self._readonly_fallback:
                self._local.conn.execute("PRAGMA journal_mode=WAL")
                self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_db(self) -> None:
        """Initialize schema."""
        conn = self._conn
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS experiences (
                id TEXT PRIMARY KEY,
                agent_service TEXT NOT NULL,
                agent_role TEXT DEFAULT '',
                capability TEXT NOT NULL,
                goal TEXT DEFAULT '',
                input_summary TEXT DEFAULT '',
                contract_name TEXT DEFAULT '',
                chain TEXT DEFAULT '',
                finding_types TEXT DEFAULT '[]',
                output_summary TEXT DEFAULT '',
                success INTEGER NOT NULL DEFAULT 1,
                confidence REAL DEFAULT 0.0,
                severity TEXT DEFAULT 'info',
                total_findings INTEGER DEFAULT 0,
                error TEXT,
                duration_ms INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                timestamp TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                importance REAL DEFAULT 0.5,
                reflection TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS consolidations (
                id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                source_experiences TEXT DEFAULT '[]',
                source_agents TEXT DEFAULT '[]',
                confidence REAL DEFAULT 0.0,
                applicability TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                times_applied INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.0
            );

            CREATE INDEX IF NOT EXISTS idx_exp_agent ON experiences(agent_service);
            CREATE INDEX IF NOT EXISTS idx_exp_capability ON experiences(capability);
            CREATE INDEX IF NOT EXISTS idx_exp_success ON experiences(success);
            CREATE INDEX IF NOT EXISTS idx_exp_severity ON experiences(severity);
            CREATE INDEX IF NOT EXISTS idx_exp_timestamp ON experiences(timestamp);
            CREATE INDEX IF NOT EXISTS idx_exp_contract ON experiences(contract_name);
            CREATE INDEX IF NOT EXISTS idx_exp_chain ON experiences(chain);
            CREATE INDEX IF NOT EXISTS idx_exp_importance ON experiences(importance);
        """)

    def record(self, exp: AuditExperience) -> None:
        """Record satu experience ke database.

        Thread-safe, auto-commit.
        """
        conn = self._conn
        conn.execute(
            """
            INSERT OR REPLACE INTO experiences
                (id, agent_service, agent_role, capability, goal,
                 input_summary, contract_name, chain, finding_types,
                 output_summary, success, confidence, severity,
                 total_findings, error, duration_ms, cost_usd,
                 timestamp, tags, importance, reflection)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exp.id,
                exp.agent_service,
                exp.agent_role,
                exp.capability,
                exp.goal,
                exp.input_summary,
                exp.contract_name,
                exp.chain,
                json.dumps(exp.finding_types),
                exp.output_summary,
                1 if exp.success else 0,
                exp.confidence,
                exp.severity,
                exp.total_findings,
                exp.error,
                exp.duration_ms,
                exp.cost_usd,
                exp.timestamp,
                json.dumps(exp.tags),
                exp.importance,
                exp.reflection,
            ),
        )
        conn.commit()

    def record_batch(self, experiences: list[AuditExperience]) -> None:
        """Batch insert multiple experiences."""
        conn = self._conn
        rows = []
        for exp in experiences:
            rows.append((
                exp.id, exp.agent_service, exp.agent_role, exp.capability,
                exp.goal, exp.input_summary, exp.contract_name, exp.chain,
                json.dumps(exp.finding_types), exp.output_summary,
                1 if exp.success else 0, exp.confidence, exp.severity,
                exp.total_findings, exp.error, exp.duration_ms, exp.cost_usd,
                exp.timestamp, json.dumps(exp.tags), exp.importance, exp.reflection,
            ))
        conn.executemany(
            """
            INSERT OR REPLACE INTO experiences
                (id, agent_service, agent_role, capability, goal,
                 input_summary, contract_name, chain, finding_types,
                 output_summary, success, confidence, severity,
                 total_findings, error, duration_ms, cost_usd,
                 timestamp, tags, importance, reflection)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()

    def query(self, q: ExperienceQuery) -> list[AuditExperience]:
        """Cari experiences berdasarkan query.

        Args:
            q: ExperienceQuery dengan filter

        Returns:
            List of AuditExperience
        """
        conn = self._conn
        conditions: list[str] = []
        params: list[Any] = []

        if q.capability:
            conditions.append("capability = ?")
            params.append(q.capability)

        if q.success is not None:
            conditions.append("success = ?")
            params.append(1 if q.success else 0)

        if q.severity:
            conditions.append("severity = ?")
            params.append(q.severity)

        if q.contract_name:
            conditions.append("contract_name LIKE ?")
            params.append(f"%{q.contract_name}%")

        if q.finding_type:
            conditions.append("finding_types LIKE ?")
            params.append(f"%{q.finding_type}%")

        if q.chain:
            conditions.append("chain = ?")
            params.append(q.chain)

        if q.agent_service:
            conditions.append("agent_service = ?")
            params.append(q.agent_service)

        if q.min_importance > 0:
            conditions.append("importance >= ?")
            params.append(q.min_importance)

        if q.past_days:
            cutoff = time.time() - (q.past_days * 86400)
            conditions.append("timestamp >= ?")
            params.append(cutoff)

        where = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM experiences WHERE {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([q.limit, q.offset])

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_experience(r) for r in rows]

    def get_by_id(self, exp_id: str) -> AuditExperience | None:
        """Cari satu experience by ID."""
        row = self._conn.execute(
            "SELECT * FROM experiences WHERE id = ?", (exp_id,)
        ).fetchone()
        return self._row_to_experience(row) if row else None

    def get_recent(self, limit: int = 20) -> list[AuditExperience]:
        """Dapatkan experiences terbaru."""
        rows = self._conn.execute(
            "SELECT * FROM experiences ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_experience(r) for r in rows]

    def get_failures(self, limit: int = 20) -> list[AuditExperience]:
        """Dapatkan experiences yang gagal — paling penting untuk belajar."""
        rows = self._conn.execute(
            "SELECT * FROM experiences WHERE success = 0 ORDER BY importance DESC, timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_experience(r) for r in rows]

    def get_high_impact(self, limit: int = 20) -> list[AuditExperience]:
        """Dapatkan experiences dengan impact tertinggi."""
        rows = self._conn.execute(
            "SELECT * FROM experiences ORDER BY importance DESC, timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_experience(r) for r in rows]

    def count(
        self,
        agent_service: str | None = None,
        capability: str | None = None,
        success: bool | None = None,
    ) -> int:
        """Hitung jumlah experiences dengan filter opsional."""
        conditions = []
        params = []
        if agent_service:
            conditions.append("agent_service = ?")
            params.append(agent_service)
        if capability:
            conditions.append("capability = ?")
            params.append(capability)
        if success is not None:
            conditions.append("success = ?")
            params.append(1 if success else 0)

        where = " AND ".join(conditions) if conditions else "1=1"
        row = self._conn.execute(
            f"SELECT COUNT(*) as cnt FROM experiences WHERE {where}", params
        ).fetchone()
        return row["cnt"] if row else 0

    def get_success_rate(
        self,
        agent_service: str | None = None,
        capability: str | None = None,
    ) -> float:
        """Hitung success rate untuk agent/capability tertentu.

        Returns:
            Float 0.0 - 1.0
        """
        conditions = []
        params = []
        if agent_service:
            conditions.append("agent_service = ?")
            params.append(agent_service)
        if capability:
            conditions.append("capability = ?")
            params.append(capability)
        where = " AND ".join(conditions) if conditions else "1=1"

        row = self._conn.execute(
            f"SELECT COUNT(*) as total, SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as successes FROM experiences WHERE {where}",
            params,
        ).fetchone()
        if not row or row["total"] == 0:
            return 0.0
        return row["successes"] / row["total"]

    def get_finding_type_stats(self, agent_service: str | None = None) -> list[dict]:
        """Statistik finding types yang pernah ditemukan."""
        conditions = ["finding_types != '[]'"]
        params = []
        if agent_service:
            conditions.append("agent_service = ?")
            params.append(agent_service)

        rows = self._conn.execute(
            f"SELECT finding_types, success, severity FROM experiences WHERE {' AND '.join(conditions)}",
            params,
        ).fetchall()

        stats: dict[str, dict] = {}
        for row in rows:
            types = json.loads(row["finding_types"])
            for ft in types:
                if ft not in stats:
                    stats[ft] = {"count": 0, "success": 0, "severities": {}}
                stats[ft]["count"] += 1
                if row["success"]:
                    stats[ft]["success"] += 1
                sev = row["severity"]
                stats[ft]["severities"][sev] = stats[ft]["severities"].get(sev, 0) + 1

        return [
            {
                "finding_type": ft,
                "count": s["count"],
                "success_rate": round(s["success"] / s["count"], 2) if s["count"] > 0 else 0,
                "severities": s["severities"],
            }
            for ft, s in sorted(stats.items(), key=lambda x: x[1]["count"], reverse=True)
        ]

    # ── Consolidation CRUD ─────────────────────────────────

    def save_consolidation(self, c: ExperienceConsolidation) -> None:
        """Simpan satu hasil consolidasi."""
        self._conn.execute(
            """
            INSERT OR REPLACE INTO consolidations
                (id, pattern_type, title, summary, source_experiences,
                 source_agents, confidence, applicability, created_at,
                 times_applied, success_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                c.id, c.pattern_type, c.title, c.summary,
                json.dumps(c.source_experiences), json.dumps(c.source_agents),
                c.confidence, c.applicability, c.created_at,
                c.times_applied, c.success_rate,
            ),
        )
        self._conn.commit()

    def get_consolidations(
        self,
        pattern_type: str | None = None,
        limit: int = 20,
    ) -> list[ExperienceConsolidation]:
        """Dapatkan consolidations."""
        if pattern_type:
            rows = self._conn.execute(
                "SELECT * FROM consolidations WHERE pattern_type = ? ORDER BY confidence DESC LIMIT ?",
                (pattern_type, limit),
            )
        else:
            rows = self._conn.execute(
                "SELECT * FROM consolidations ORDER BY confidence DESC LIMIT ?", (limit,)
            )
        return [self._row_to_consolidation(r) for r in rows.fetchall()]

    # ── Maintenance ────────────────────────────────────────

    def prune_old(self, keep_days: int = 365) -> int:
        """Hapus experiences yang lebih tua dari keep_days.

        Kecuali yang importance tinggi (>0.7).
        """
        cutoff = time.time() - (keep_days * 86400)
        deleted = self._conn.execute(
            "DELETE FROM experiences WHERE timestamp < ? AND importance < 0.7",
            (cutoff,),
        ).rowcount
        self._conn.commit()
        return deleted

    def get_stats(self) -> dict[str, Any]:
        """Dapatkan statistik store."""
        total = self._conn.execute("SELECT COUNT(*) as c FROM experiences").fetchone()["c"]
        successes = self._conn.execute(
            "SELECT COUNT(*) as c FROM experiences WHERE success = 1"
        ).fetchone()["c"]
        failures = total - successes
        agents = self._conn.execute(
            "SELECT COUNT(DISTINCT agent_service) as c FROM experiences"
        ).fetchone()["c"]
        consolidations = self._conn.execute(
            "SELECT COUNT(*) as c FROM consolidations"
        ).fetchone()["c"]

        return {
            "total_experiences": total,
            "successes": successes,
            "failures": failures,
            "success_rate": round(successes / total, 2) if total > 0 else 0,
            "unique_agents": agents,
            "consolidations": consolidations,
            "db_size_bytes": 0 if self._readonly_fallback else (os.path.getsize(self._db_path) if self._db_path.exists() else 0),
        }

    # ── Helpers ────────────────────────────────────────────

    def _row_to_experience(self, row: sqlite3.Row) -> AuditExperience:
        return AuditExperience(
            id=row["id"],
            agent_service=row["agent_service"],
            agent_role=row["agent_role"],
            capability=row["capability"],
            goal=row["goal"],
            input_summary=row["input_summary"],
            contract_name=row["contract_name"],
            chain=row["chain"],
            finding_types=json.loads(row["finding_types"]),
            output_summary=row["output_summary"],
            success=bool(row["success"]),
            confidence=row["confidence"],
            severity=row["severity"],
            total_findings=row["total_findings"],
            error=row["error"],
            duration_ms=row["duration_ms"],
            cost_usd=row["cost_usd"],
            timestamp=row["timestamp"],
            tags=json.loads(row["tags"]),
            importance=row["importance"],
            reflection=row["reflection"],
        )

    def _row_to_consolidation(self, row: sqlite3.Row) -> ExperienceConsolidation:
        return ExperienceConsolidation(
            id=row["id"],
            pattern_type=row["pattern_type"],
            title=row["title"],
            summary=row["summary"],
            source_experiences=json.loads(row["source_experiences"]),
            source_agents=json.loads(row["source_agents"]),
            confidence=row["confidence"],
            applicability=row["applicability"],
            created_at=row["created_at"],
            times_applied=row["times_applied"],
            success_rate=row["success_rate"],
        )
