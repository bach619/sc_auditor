"""SkillResult — standard return type for all skill executions.

Menggunakan dataclass (bukan BaseModel) agar portable —
tidak perlu dependensi Pydantic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillResult:
    """Hasil dari eksekusi sebuah skill.

    Attributes:
        success: Apakah skill berhasil dieksekusi
        output: Data hasil eksekusi (jika success)
        error: Pesan error (jika failed)
        duration_ms: Waktu eksekusi dalam milidetik
        skill_name: Nama skill yang dieksekusi
    """

    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    skill_name: str = ""
