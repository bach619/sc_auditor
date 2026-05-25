"""SkillSpec — metadata definition for a skill.

Setiap backend agent publish SkillSpec via manifest,
sehingga Antonio tahu parameter apa yang dibutuhkan,
berapa biaya, durasi, dan akurasi yang diharapkan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillSpec:
    """Spesifikasi sebuah skill — metadata untuk discovery & routing.

    Attributes:
        name: Nama unik skill (e.g. "classify_single")
        description: Deskripsi untuk LLM prompt
        parameters: JSON Schema-style parameter definition
        examples: Contoh penggunaan untuk LLM few-shot
        estimated_duration_ms: Perkiraan durasi eksekusi
        estimated_cost_usd: Perkiraan biaya per eksekusi
        confidence: Akurasi yang diharapkan (0.0 - 1.0)
        category: Kategori skill (e.g. "analysis", "scanning", "reporting")
    """

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)
    estimated_duration_ms: int = 0
    estimated_cost_usd: float = 0.0
    confidence: float = 0.0
    category: str = "general"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "examples": self.examples,
            "estimated_duration_ms": self.estimated_duration_ms,
            "estimated_cost_usd": self.estimated_cost_usd,
            "confidence": self.confidence,
            "category": self.category,
        }
