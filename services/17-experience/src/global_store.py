"""GlobalExperienceStore — SQLite terpusat untuk query lintas-agent.

Menerima sync dari semua agent, menyediakan:
  - Global query (semua agent)
  - Cross-agent pattern detection
  - Statistika global
  - Consolidation lintas-agent
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


class GlobalExperienceStore:
    """Thread-safe SQLite store untuk experience dari semua agent."""

    def __init__(self, db_path: str | Path = "/data/experience/global.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._db_path))
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_db(self) -> None:
        self._conn.executescript("""
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
                reflection TEXT DEFAULT '',
                synced_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS consolidations (
                id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                source_agents TEXT DEFAULT '[]',
                source_experiences TEXT DEFAULT '[]',
                confidence REAL DEFAULT 0.0,
                applicability TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                times_applied INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.0
            );

            CREATE INDEX IF NOT EXISTS idx_global_agent ON experiences(agent_service);
            CREATE INDEX IF NOT EXISTS idx_global_capability ON experiences(capability);
            CREATE INDEX IF NOT EXISTS idx_global_contract ON experiences(contract_name);
            CREATE INDEX IF NOT EXISTS idx_global_severity ON experiences(severity);
            CREATE INDEX IF NOT EXISTS idx_global_success ON experiences(success);
            CREATE INDEX IF NOT EXISTS idx_global_ts ON experiences(timestamp);
            CREATE INDEX IF NOT EXISTS idx_global_chain ON experiences(chain);
            CREATE INDEX IF NOT EXISTS idx_global_importance ON experiences(importance);
        """)

    # ── Sync ────────────────────────────────────────────────

    def sync_batch(self, experiences: list[dict]) -> int:
        """Insert or update batch of experiences dari satu agent.

        Returns:
            Jumlah record yang di-insert
        """
        conn = self._conn
        count = 0
        for exp in experiences:
            try:
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
                        exp["id"], exp.get("agent_service", ""),
                        exp.get("agent_role", ""), exp.get("capability", ""),
                        exp.get("goal", ""), exp.get("input_summary", ""),
                        exp.get("contract_name", ""), exp.get("chain", ""),
                        json.dumps(exp.get("finding_types", [])),
                        exp.get("output_summary", ""),
                        1 if exp.get("success", True) else 0,
                        exp.get("confidence", 0.0), exp.get("severity", "info"),
                        exp.get("total_findings", 0), exp.get("error"),
                        exp.get("duration_ms", 0), exp.get("cost_usd", 0.0),
                        exp.get("timestamp", ""), json.dumps(exp.get("tags", [])),
                        exp.get("importance", 0.5), exp.get("reflection", ""),
                    ),
                )
                count += 1
            except Exception:
                pass  # Skip corrupt records
        conn.commit()
        return count

    # ── Query ───────────────────────────────────────────────

    def query(
        self,
        agent_service: str | None = None,
        capability: str | None = None,
        success: bool | None = None,
        severity: str | None = None,
        contract_name: str | None = None,
        chain: str | None = None,
        finding_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
        past_days: int | None = None,
    ) -> list[dict]:
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
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if contract_name:
            conditions.append("contract_name LIKE ?")
            params.append(f"%{contract_name}%")
        if chain:
            conditions.append("chain = ?")
            params.append(chain)
        if finding_type:
            conditions.append("finding_types LIKE ?")
            params.append(f"%{finding_type}%")
        if past_days:
            cutoff = time.time() - (past_days * 86400)
            conditions.append("timestamp >= ?")
            params.append(cutoff)

        where = " AND ".join(conditions) if conditions else "1=1"
        rows = self._conn.execute(
            f"SELECT * FROM experiences WHERE {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        return [dict(r) for r in rows]

    def count(self, agent_service: str | None = None) -> int:
        conditions = []
        params = []
        if agent_service:
            conditions.append("agent_service = ?")
            params.append(agent_service)
        where = " AND ".join(conditions) if conditions else "1=1"
        row = self._conn.execute(
            f"SELECT COUNT(*) as cnt FROM experiences WHERE {where}", params
        ).fetchone()
        return row["cnt"] if row else 0

    # ── Stats ────────────────────────────────────────────────

    def get_global_stats(self) -> dict:
        total = self.count()
        successes = self._conn.execute(
            "SELECT COUNT(*) as c FROM experiences WHERE success = 1"
        ).fetchone()["c"]
        failures = total - successes

        agent_count = self._conn.execute(
            "SELECT COUNT(DISTINCT agent_service) as c FROM experiences"
        ).fetchone()["c"]

        # Per-agent stats
        per_agent = []
        rows = self._conn.execute(
            """
            SELECT agent_service,
                   COUNT(*) as total,
                   SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as successes,
                   ROUND(AVG(confidence), 2) as avg_confidence,
                   ROUND(AVG(importance), 2) as avg_importance
            FROM experiences
            GROUP BY agent_service
            ORDER BY total DESC
            """
        ).fetchall()
        for r in rows:
            t = r["total"]
            s = r["successes"] or 0
            per_agent.append({
                "agent_service": r["agent_service"],
                "total": t,
                "successes": s,
                "failures": t - s,
                "success_rate": round(s / t, 2) if t > 0 else 0,
                "avg_confidence": r["avg_confidence"],
                "avg_importance": r["avg_importance"],
            })

        # Top finding types
        finding_stats = []
        ft_rows = self._conn.execute(
            "SELECT finding_types, success FROM experiences WHERE finding_types != '[]'"
        ).fetchall()
        ft_agg: dict = {}
        for r in ft_rows:
            types = json.loads(r["finding_types"])
            for ft in types:
                if ft not in ft_agg:
                    ft_agg[ft] = {"count": 0, "successes": 0}
                ft_agg[ft]["count"] += 1
                if r["success"]:
                    ft_agg[ft]["successes"] += 1

        for ft, data in sorted(ft_agg.items(), key=lambda x: x[1]["count"], reverse=True)[:20]:
            finding_stats.append({
                "finding_type": ft,
                "count": data["count"],
                "success_rate": round(data["successes"] / data["count"], 2) if data["count"] > 0 else 0,
            })

        return {
            "total_experiences": total,
            "successes": successes,
            "failures": failures,
            "success_rate": round(successes / total, 2) if total > 0 else 0,
            "unique_agents": agent_count,
            "per_agent": per_agent,
            "top_finding_types": finding_stats[:10],
        }

    def get_success_rate(self, agent_service: str | None = None) -> float:
        return self._conn.execute(
            """
            SELECT CASE WHEN COUNT(*) > 0
                THEN ROUND(CAST(SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS REAL) / COUNT(*), 2)
                ELSE 0 END as rate
            FROM experiences
            """ + (" WHERE agent_service = ?" if agent_service else ""),
            ([agent_service] if agent_service else []),
        ).fetchone()["rate"]

    # ── Consolidated Learning ───────────────────────────────

    def detect_cross_agent_patterns(self) -> list[dict]:
        """Deteksi pattern yang muncul di multiple agent.

        Misalnya: "reentrancy sering false positive di Slither tapi
        terkonfirmasi di Manticore" — ini polyma lintas-agent.
        """
        patterns = []

        # Finding types yang muncul di banyak agent
        rows = self._conn.execute(
            """
            SELECT json_each.value as finding_type,
                   COUNT(DISTINCT agent_service) as agent_count,
                   COUNT(*) as total_count,
                   ROUND(AVG(CASE WHEN success=1 THEN 1.0 ELSE 0.0 END), 2) as success_rate
            FROM experiences, json_each(experiences.finding_types)
            GROUP BY finding_type
            HAVING agent_count >= 2
            ORDER BY total_count DESC
            LIMIT 10
            """
        ).fetchall()

        for r in rows:
            patterns.append({
                "pattern_type": "cross_agent_finding",
                "finding_type": r["finding_type"],
                "agents_involved": r["agent_count"],
                "total_occurrences": r["total_count"],
                "success_rate": r["success_rate"],
                "insight": self._generate_insight(r),
            })

        return patterns

    def _generate_insight(self, row: sqlite3.Row) -> str:
        ft = row["finding_type"]
        count = row["total_count"]
        agents = row["agent_count"]
        rate = row["success_rate"]

        if rate < 0.5 and count >= 5:
            return (
                f"⚠️  '{ft}' has low confirmation rate ({rate:.0%}) across {agents} agents "
                f"({count} total). Consider reviewing detection methodology."
            )
        elif rate >= 0.8 and count >= 5:
            return (
                f"✅ '{ft}' is highly reliable ({rate:.0%}) across {agents} agents "
                f"({count} total). High confidence in detection."
            )
        else:
            return (
                f"📊 '{ft}' detected {count} times across {agents} agents "
                f"with {rate:.0%} success rate. More data needed for pattern."
            )

    def get_learnings(self, limit: int = 10) -> list[dict]:
        """Dapatkan insight pembelajaran lintas-agent."""
        results = []

        # 1. Failure patterns (finding types dengan banyak gagal)
        rows = self._conn.execute(
            """
            SELECT json_each.value as finding_type,
                   COUNT(*) as failures,
                   ROUND(AVG(importance), 2) as avg_importance
            FROM experiences, json_each(experiences.finding_types)
            WHERE success = 0
            GROUP BY finding_type
            ORDER BY failures DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        for r in rows:
            results.append({
                "type": "failure_pattern",
                "finding_type": r["finding_type"],
                "failure_count": r["failures"],
                "avg_importance": r["avg_importance"],
                "lesson": f"{r['finding_type']} failed {r['failures']} times — review detection logic",
            })

        # 2. High confidence successes
        rows = self._conn.execute(
            """
            SELECT agent_service, capability, COUNT(*) as count,
                   ROUND(AVG(confidence), 2) as avg_conf
            FROM experiences
            WHERE success = 1 AND confidence >= 0.8
            GROUP BY agent_service, capability
            ORDER BY count DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        for r in rows:
            results.append({
                "type": "high_confidence_success",
                "agent_service": r["agent_service"],
                "capability": r["capability"],
                "count": r["count"],
                "avg_confidence": r["avg_conf"],
                "lesson": f"{r['agent_service']} excels at {r['capability']} ({r['count']} tasks, {r['avg_conf']} avg confidence)",
            })

        return results

    # ── Maintenance ─────────────────────────────────────────

    def prune(self, keep_days: int = 365) -> int:
        cutoff = time.time() - (keep_days * 86400)
        deleted = self._conn.execute(
            "DELETE FROM experiences WHERE timestamp < ? AND importance < 0.7",
            (cutoff,),
        ).rowcount
        self._conn.commit()
        return deleted
