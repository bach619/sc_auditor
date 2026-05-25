"""SkillRegistry — register, temukan, eksekusi, dan track metrics skill.

Setiap service (Antonio + backend agents) memiliki SkillRegistry sendiri
yang berisi skill-skill spesifik service tersebut.
"""

from __future__ import annotations

import time
from typing import Any

from .base_skill import BaseSkill
from .skill_result import SkillResult
from .skill_spec import SkillSpec


class SkillCallMetrics:
    """Metrics untuk satu skill — tracking penggunaan & performa."""

    def __init__(self, skill_name: str) -> None:
        self.skill_name = skill_name
        self.call_count: int = 0
        self.success_count: int = 0
        self.error_count: int = 0
        self.total_duration_ms: float = 0.0
        self.last_called: float = 0.0
        self.last_error: str | None = None
        self.recent_calls: list[dict[str, Any]] = []

    def record_call(
        self, duration_ms: float, success: bool, error: str | None = None
    ) -> None:
        self.call_count += 1
        self.total_duration_ms += duration_ms
        self.last_called = time.time()
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
            self.last_error = error
        self.recent_calls.append({
            "timestamp": time.time(),
            "duration_ms": round(duration_ms, 1),
            "success": success,
            "error": error,
        })
        if len(self.recent_calls) > 20:
            self.recent_calls.pop(0)

    @property
    def avg_duration_ms(self) -> float:
        if self.call_count == 0:
            return 0.0
        return round(self.total_duration_ms / self.call_count, 1)

    @property
    def success_rate(self) -> float:
        if self.call_count == 0:
            return 1.0
        return round(self.success_count / self.call_count, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "call_count": self.call_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": self.success_rate,
            "avg_duration_ms": self.avg_duration_ms,
            "last_called": self.last_called,
            "last_error": self.last_error,
        }


class SkillRegistry:
    """Registry untuk semua skill yang tersedia di satu service.

    Setiap service (Antonio, 06-AI, 04-Scanner, dll) punya instance sendiri.

    Methods:
        register(skill) — daftarkan skill
        get(name) — cari skill by name
        list_specs() — semua skill specs (untuk manifest)
        execute(name, **kwargs) — jalankan skill dengan metrics
    """

    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}
        self._metrics: dict[str, SkillCallMetrics] = {}

    def register(self, skill: BaseSkill) -> None:
        """Daftarkan satu skill ke registry.

        Args:
            skill: Instance BaseSkill
        """
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' already registered")
        self._skills[skill.name] = skill
        self._metrics[skill.name] = SkillCallMetrics(skill.name)

    def get(self, name: str) -> BaseSkill | None:
        """Cari skill by name."""
        return self._skills.get(name)

    def has(self, name: str) -> bool:
        """Cek apakah skill terdaftar."""
        return name in self._skills

    @property
    def count(self) -> int:
        """Jumlah skill terdaftar."""
        return len(self._skills)

    def list_specs(self) -> list[SkillSpec]:
        """Dapatkan semua skill specs — untuk manifest / discovery."""
        specs = []
        for skill in self._skills.values():
            spec = skill.get_spec()
            # Inject metrics
            metrics = self._metrics.get(skill.name)
            if metrics and metrics.call_count > 0:
                spec.estimated_duration_ms = int(metrics.avg_duration_ms)
            specs.append(spec)
        return specs

    def list_skills(self) -> list[BaseSkill]:
        """Dapatkan semua skill objects."""
        return list(self._skills.values())

    async def execute(self, name: str, **kwargs: Any) -> SkillResult:
        """Execute skill by name dengan metrics tracking.

        Args:
            name: Nama skill
            **kwargs: Arguments untuk skill

        Returns:
            SkillResult
        """
        skill = self.get(name)
        if skill is None:
            return SkillResult(
                success=False,
                error=f"Skill '{name}' not found in registry",
                skill_name=name,
            )

        t0 = time.monotonic()
        result = await skill.execute(**kwargs)
        duration = (time.monotonic() - t0) * 1000

        # Record metrics
        metrics = self._metrics.get(name)
        if metrics:
            metrics.record_call(
                duration_ms=duration,
                success=result.success,
                error=result.error,
            )

        return result

    # ── Metrics ────────────────────────────────────────────

    def get_metrics(self, name: str) -> dict[str, Any] | None:
        metrics = self._metrics.get(name)
        return metrics.to_dict() if metrics else None

    def get_all_metrics(self) -> list[dict[str, Any]]:
        return [m.to_dict() for m in self._metrics.values()]

    def get_top_skills(self, n: int = 5) -> list[dict[str, Any]]:
        sorted_metrics = sorted(
            self._metrics.values(),
            key=lambda m: m.call_count,
            reverse=True,
        )
        return [m.to_dict() for m in sorted_metrics[:n]]

    def get_failing_skills(self) -> list[dict[str, Any]]:
        return [
            m.to_dict()
            for m in self._metrics.values()
            if m.call_count > 2 and m.success_rate < 0.8
        ]
