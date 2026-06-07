"""Skill Registry — mendaftarkan, menemukan, dan melacak skill.

Extends shared SkillRegistry with:
- format_for_prompt() for LLM system prompt generation
- Override execute() to return Pydantic SkillResult
"""

from __future__ import annotations

from typing import Any

import structlog
from shared.skills.skill_registry import SkillCallMetrics
from shared.skills.skill_registry import SkillRegistry as SharedSkillRegistry

from src.models import SkillDefinition, SkillResult
from src.skills.base import BaseSkill

log = structlog.get_logger()


class SkillRegistry(SharedSkillRegistry):
    """Registry untuk semua skill yang tersedia (extends SharedSkillRegistry).

    Agent menggunakan registry ini untuk:
    1. Menemukan skill berdasarkan nama
    2. Mendapatkan daftar skill untuk LLM prompt
    3. Memanggil skill dengan parameter
    4. Melacak metrics penggunaan skill
    """

    def __init__(self) -> None:
        super().__init__()
        log.info("skill_registry_initialized")

    def register(self, skill: BaseSkill) -> None:
        """Daftarkan satu skill (mengizinkan overwrite dengan warning).

        Args:
            skill: Instance skill yang akan didaftarkan
        """
        if skill.name in self._skills:
            log.warning("skill_overwrite", name=skill.name)
        else:
            super().register(skill)
            log.info("skill_registered", name=skill.name)
            return

        # Overwrite path: manually replace skill + reset metrics
        self._skills[skill.name] = skill
        self._metrics[skill.name] = SkillCallMetrics(skill.name)
        log.info("skill_registered", name=skill.name)

    def list_skills(self) -> list[SkillDefinition]:
        """Dapatkan daftar semua skill untuk LLM prompt."""
        return [s.get_definition() for s in self._skills.values()]

    def format_for_prompt(self) -> str:
        """Format skill descriptions untuk system prompt LLM."""
        parts: list[str] = []
        for skill in self._skills.values():
            params_desc = []
            for param_name, param_info in skill.parameters.items():
                required = "(required)" if param_info.get("required") else "(optional)"
                ptype = param_info.get("type", "string")
                desc = param_info.get("description", "")
                params_desc.append(f"    - {param_name} ({ptype}) {required}: {desc}")

            params_str = "\n".join(params_desc) if params_desc else "    (no parameters)"

            # Tambah metrics ke prompt
            metrics = self.get_metrics(skill.name)
            metrics_str = ""
            if metrics and metrics.get("call_count", 0) > 0:
                metrics_str = (
                    f" [called {metrics['call_count']}x, "
                    f"{metrics['success_rate']*100:.0f}% success, "
                    f"avg {metrics['avg_duration_ms']:.0f}ms]"
                )

            parts.append(
                f"- {skill.name}{metrics_str}: {skill.description}\n{params_str}"
            )

        return "\n\n".join(parts)

    async def execute(self, name: str, **kwargs: Any) -> SkillResult:
        """Execute skill by name dengan metrics tracking.

        Args:
            name: Skill name
            **kwargs: Arguments to pass

        Returns:
            SkillResult (Pydantic)
        """
        skill = self.get(name)
        if skill is None:
            return SkillResult(success=False, error=f"Skill '{name}' not found")

        import time
        t0 = time.monotonic()
        result = await skill.execute(**kwargs)
        duration = (time.monotonic() - t0) * 1000

        # Record metrics via shared metrics
        metrics = self._metrics.get(name)
        if metrics:
            metrics.record_call(
                duration_ms=duration,
                success=result.success,
                error=result.error,
            )

        return result
