"""ExperienceManager — otak dari sistem Experience.

Mengatur:
  1. Recording — mencatat setiap task completion sebagai experience
  2. Querying — mencari experiences relevan sebelum/tentang task
  3. Consolidation — mengekstrak pattern dari banyak experiences
  4. Importance scoring — menilai seberapa penting suatu experience
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .models import AuditExperience, ExperienceConsolidation, ExperienceQuery
from .store import ExperienceStore

try:
    from .syncer import ExperienceSyncer
except ImportError:
    ExperienceSyncer = None  # type: ignore


class ExperienceManager:
    """Manager untuk sistem Experience.

    Setiap agent punya instance sendiri.
    Bisa record, query, dan consolidate experiences.

    Args:
        agent_service: Nama service (e.g. "04a-scanner-slither")
        agent_role: Role agent (e.g. "slither_analyzer")
        data_dir: Directory untuk database SQLite
    """

    def __init__(
        self,
        agent_service: str,
        agent_role: str,
        data_dir: str | Path | None = None,
        central_url: str | None = None,
    ) -> None:
        self._agent_service = agent_service
        self._agent_role = agent_role
        self._syncer: ExperienceSyncer | None = None

        if data_dir is None:
            data_dir = Path("/data/experiences") / agent_service
        self._data_dir = Path(data_dir)

        db_path = self._data_dir / "experiences.db"
        self._store = ExperienceStore(db_path)

        # Auto-create syncer ke 17-experience (jika reachable)
        if ExperienceSyncer is not None:
            self._syncer = ExperienceSyncer(
                agent_service=agent_service,
                store=self._store,
                central_url=central_url,
            )

    @property
    def store(self) -> ExperienceStore:
        return self._store

    @property
    def syncer(self) -> Any | None:
        return self._syncer

    def start_sync(self) -> None:
        """Start background sync ke 17-experience."""
        if self._syncer:
            self._syncer.start_background_sync()

    async def stop_sync(self) -> None:
        """Stop background sync."""
        if self._syncer:
            await self._syncer.stop()

    # ── Recording ──────────────────────────────────────────

    def record_experience(
        self,
        capability: str,
        goal: str = "",
        input_summary: str = "",
        contract_name: str = "",
        chain: str = "",
        finding_types: list[str] | None = None,
        output_summary: str = "",
        success: bool = True,
        confidence: float = 0.0,
        severity: str = "info",
        total_findings: int = 0,
        error: str | None = None,
        duration_ms: int = 0,
        cost_usd: float = 0.0,
        tags: list[str] | None = None,
        reflection: str = "",
    ) -> AuditExperience:
        """Record satu experience — method utama untuk logging.

        Args:
            capability: Nama capability yang dijalankan
            goal: Goal task
            input_summary: Ringkasan input
            contract_name: Nama kontrak utama
            chain: Blockchain
            finding_types: List tipe findings
            output_summary: Ringkasan output
            success: Apakah berhasil
            confidence: Confidence level
            severity: Severity ("critical", "high", dll)
            total_findings: Jumlah findings
            error: Error message jika gagal
            duration_ms: Durasi dalam ms
            cost_usd: Biaya dalam USD
            tags: Tags tambahan
            reflection: Agent reflection

        Returns:
            AuditExperience yang sudah di-record
        """
        if finding_types is None:
            finding_types = []
        if tags is None:
            tags = []

        importance = self._compute_importance(
            success=success,
            severity=severity,
            total_findings=total_findings,
            duration_ms=duration_ms,
            has_error=error is not None,
        )

        exp = AuditExperience(
            agent_service=self._agent_service,
            agent_role=self._agent_role,
            capability=capability,
            goal=goal,
            input_summary=input_summary[:500],
            contract_name=contract_name,
            chain=chain,
            finding_types=finding_types,
            output_summary=output_summary[:500],
            success=success,
            confidence=confidence,
            severity=severity,
            total_findings=total_findings,
            error=error[:500] if error else None,
            duration_ms=duration_ms,
            cost_usd=cost_usd,
            tags=tags,
            importance=importance,
            reflection=reflection[:1000] if reflection else "",
        )

        self._store.record(exp)

        # Notify syncer (non-blocking, fire-and-forget)
        if self._syncer:
            self._syncer.notify_new_experience()

        return exp

    # ── Querying ───────────────────────────────────────────

    def find_similar_tasks(
        self,
        capability: str,
        contract_name: str = "",
        chain: str = "",
        limit: int = 5,
    ) -> list[AuditExperience]:
        """Cari task serupa yang pernah dikerjakan.

        Berguna sebelum memulai task baru — lihat pengalaman sebelumnya.
        """
        q = ExperienceQuery(
            capability=capability,
            contract_name=contract_name,
            chain=chain,
            limit=limit,
            min_importance=0.3,
        )
        return self._store.query(q)

    def find_failures(
        self,
        capability: str | None = None,
        limit: int = 10,
    ) -> list[AuditExperience]:
        """Cari task yang gagal — paling penting untuk belajar."""
        return self._store.get_failures(limit)

    def find_successes(
        self,
        capability: str = "",
        limit: int = 5,
    ) -> list[AuditExperience]:
        """Cari task yang berhasil dengan confidence tinggi."""
        return self._store.query(
            ExperienceQuery(
                capability=capability or None,
                success=True,
                limit=limit,
                min_importance=0.5,
            )
        )

    def get_stats(self) -> dict[str, Any]:
        """Dapatkan statistik experiences agent ini."""
        return self._store.get_stats()

    def get_success_rate(self, capability: str | None = None) -> float:
        """Hitung success rate."""
        return self._store.get_success_rate(
            agent_service=self._agent_service,
            capability=capability,
        )

    # ── Consolidation ──────────────────────────────────────

    def consolidate(self) -> list[ExperienceConsolidation]:
        """Jalankan consolidasi — ekstrak pattern dari experiences.

        Dipanggil periodik (setiap 50 task atau manual).

        Returns:
            List of ExperienceConsolidation baru
        """
        new_consolidations: list[ExperienceConsolidation] = []

        # 1. Ekstrak failure patterns
        failures = self._store.get_failures(limit=50)
        if len(failures) >= 3:
            # Kelompokkan failures by finding_type
            failure_by_type: dict[str, list[AuditExperience]] = {}
            for f in failures:
                for ft in f.finding_types:
                    if ft not in failure_by_type:
                        failure_by_type[ft] = []
                    failure_by_type[ft].append(f)

            for ft, exps in failure_by_type.items():
                if len(exps) >= 3:
                    consolidation = ExperienceConsolidation(
                        pattern_type="failure_pattern",
                        title=f"Common failure: {ft} — {len(exps)} occurrences",
                        summary=(
                            f"Found {len(exps)} failed attempts for finding type '{ft}'. "
                            f"Agents: {', '.join(set(e.agent_service for e in exps))}. "
                            f"Review methodology for {ft} detection."
                        ),
                        source_experiences=[e.id for e in exps],
                        source_agents=list(set(e.agent_service for e in exps)),
                        confidence=min(0.9, len(exps) * 0.15),
                        applicability="by_finding_type",
                    )
                    self._store.save_consolidation(consolidation)
                    new_consolidations.append(consolidation)

        # 2. Ekstrak success patterns
        successes = self._store.query(
            ExperienceQuery(success=True, limit=50, min_importance=0.6)
        )
        if len(successes) >= 3:
            high_conf = [s for s in successes if s.confidence >= 0.8]
            if len(high_conf) >= 3:
                consolidation = ExperienceConsolidation(
                    pattern_type="success_pattern",
                    title=f"High confidence success rate: {len(high_conf)} tasks with >= 80% confidence",
                    summary=(
                        f"Agent '{self._agent_service}' achieved {len(high_conf)} tasks "
                        f"with confidence >= 80%. Success rate: "
                        f"{self._store.get_success_rate(agent_service=self._agent_service):.0%}."
                    ),
                    source_experiences=[s.id for s in high_conf],
                    source_agents=[self._agent_service],
                    confidence=0.85,
                    applicability="by_agent",
                )
                self._store.save_consolidation(consolidation)
                new_consolidations.append(consolidation)

        return new_consolidations

    def get_consolidations(
        self,
        pattern_type: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Dapatkan hasil consolidasi."""
        return [
            c.to_dict()
            for c in self._store.get_consolidations(pattern_type, limit)
        ]

    def apply_consolidation(self, consolidation_id: str, success: bool) -> None:
        """Catat bahwa suatu consolidation berhasil/tidak diterapkan."""
        cons = None
        for c in self._store.get_consolidations():
            if c.id == consolidation_id:
                cons = c
                break
        if cons:
            cons.times_applied += 1
            if success:
                cons.success_rate = (
                    cons.success_rate * (cons.times_applied - 1) + 1
                ) / cons.times_applied
            self._store.save_consolidation(cons)

    # ── Importance Scoring ─────────────────────────────────

    def _compute_importance(
        self,
        success: bool,
        severity: str,
        total_findings: int,
        duration_ms: int,
        has_error: bool,
    ) -> float:
        """Hitung importance score (0.0 - 1.0) untuk satu experience.

        Faktor:
          - Failures lebih penting dari successes
          - Higher severity = lebih penting
          - Banyak findings = lebih penting
          - Durasi panjang = lebih penting
        """
        score = 0.3  # Baseline

        # Failures are goldmines for learning
        if not success:
            score += 0.3
        if has_error:
            score += 0.1

        # Severity multiplier
        severity_map = {
            "critical": 0.3,
            "high": 0.2,
            "medium": 0.1,
            "low": 0.0,
            "info": -0.1,
        }
        score += severity_map.get(severity, 0.0)

        # Finding volume
        if total_findings >= 10:
            score += 0.15
        elif total_findings >= 5:
            score += 0.1
        elif total_findings >= 1:
            score += 0.05

        # Duration — task lama menunjukkan kompleksitas tinggi
        if duration_ms > 120_000:  # > 2 menit
            score += 0.1
        elif duration_ms > 30_000:
            score += 0.05

        return max(0.0, min(1.0, score))

    # ── Maintenance ────────────────────────────────────────

    def prune(self, keep_days: int = 365) -> int:
        """Hapus experiences tua yang tidak penting."""
        return self._store.prune_old(keep_days)

    def get_store_path(self) -> str:
        return str(self._store._db_path)
