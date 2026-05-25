"""BaseSkill — abstract base for all skills across all services.

Setiap skill adalah class sendiri dengan:
- nama, deskripsi, parameter (metadata)
- run() — implementasi utama (abstract)
- execute() — wrapper dengan timing + error handling

Extend class ini untuk membuat skill baru.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from .skill_result import SkillResult
from .skill_spec import SkillSpec


class BaseSkill(ABC):
    """Abstract base untuk semua skill (Antonio + Backend Agents).

    Subclass WAJIB override:
    - name (property)
    - description (property)
    - parameters (property)
    - run() method
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nama unik skill — digunakan sebagai identifier."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Deskripsi skill — untuk LLM prompt."""
        ...

    @property
    def parameters(self) -> dict[str, Any]:
        """Parameter yang dibutuhkan (JSON Schema format).

        Default: kosong. Override jika butuh parameter.
        """
        return {}

    @property
    def category(self) -> str:
        """Kategori skill — untuk grouping di manifest."""
        return "general"

    def get_spec(self) -> SkillSpec:
        """Build SkillSpec dari property skill."""
        return SkillSpec(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            category=self.category,
        )

    async def execute(self, **kwargs: Any) -> SkillResult:
        """Eksekusi skill dengan timing & error handling otomatis.

        Args:
            **kwargs: Parameter sesuai self.parameters

        Returns:
            SkillResult dengan output atau error
        """
        start = time.monotonic()
        try:
            output = await self.run(**kwargs)
            duration_ms = (time.monotonic() - start) * 1000
            return SkillResult(
                success=True,
                output=output,
                duration_ms=duration_ms,
                skill_name=self.name,
            )
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            return SkillResult(
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
                skill_name=self.name,
            )

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        """Implementasi skill — di-override oleh subclass.

        Args:
            **kwargs: Parameter yang sudah divalidasi

        Returns:
            Output skill (dict, list, string, dll)
        """
        ...
