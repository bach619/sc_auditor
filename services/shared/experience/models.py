"""Experience data models — merekam setiap audit task sebagai pengalaman."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AuditExperience:
    """Satu pengalaman audit — satu task yang dikerjakan oleh satu agent.

    Setiap kali agent menyelesaikan tugas (berhasil/gagal),
    ini dicatat sebagai Experience. Dari sini agent belajar.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    agent_service: str = ""       # "04a-scanner-slither"
    agent_role: str = ""          # "slither_analyzer"
    capability: str = ""          # "run_static_analysis"
    goal: str = ""                # Goal dari delegasi

    # Input summary — apa yang dikerjakan
    input_summary: str = ""       # Ringkasan input (contract name, chain, dll)
    contract_name: str = ""       # Nama kontrak utama
    chain: str = ""               # Blockchain (ethereum, bsc, dll)
    finding_types: list[str] = field(default_factory=list)  # ["reentrancy", "access_control"]

    # Output summary — hasilnya
    output_summary: str = ""      # Ringkasan output
    success: bool = True          # Berhasil atau gagal
    confidence: float = 0.0       # Confidence level
    severity: str = "info"        # "critical", "high", "medium", "low", "info"
    total_findings: int = 0
    error: str | None = None      # Error message jika gagal

    # Metrics
    duration_ms: int = 0
    cost_usd: float = 0.0

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: list[str] = field(default_factory=list)
    importance: float = 0.5       # 0.0 - 1.0 — dihitung otomatis
    embedding: list[float] | None = None  # Untuk semantic search (future)
    reflection: str = ""          # Agent reflection setelah task

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_service": self.agent_service,
            "agent_role": self.agent_role,
            "capability": self.capability,
            "goal": self.goal,
            "input_summary": self.input_summary,
            "contract_name": self.contract_name,
            "chain": self.chain,
            "finding_types": self.finding_types,
            "output_summary": self.output_summary,
            "success": self.success,
            "confidence": self.confidence,
            "severity": self.severity,
            "total_findings": self.total_findings,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "cost_usd": self.cost_usd,
            "timestamp": self.timestamp,
            "tags": self.tags,
            "importance": self.importance,
            "reflection": self.reflection,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditExperience:
        return cls(**data)


@dataclass
class ExperienceQuery:
    """Query untuk mencari experiences."""

    capability: str | None = None         # Filter by capability
    success: bool | None = None           # Filter by success/failure
    severity: str | None = None           # Filter by severity
    contract_name: str | None = None      # Filter by contract name
    finding_type: str | None = None       # Filter by finding type
    chain: str | None = None              # Filter by chain
    agent_service: str | None = None      # Filter by agent
    limit: int = 20                       # Max results
    offset: int = 0
    min_importance: float = 0.0           # Minimum importance
    past_days: int | None = None          # Berapa hari ke belakang

    # Semantic search (future)
    query_text: str | None = None         # Natural language query
    min_similarity: float = 0.0


@dataclass
class ExperienceConsolidation:
    """Hasil consolidasi — pattern yang diekstrak dari banyak experiences."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    pattern_type: str = ""           # "success_pattern", "failure_pattern", "insight"
    title: str = ""
    summary: str = ""
    source_experiences: list[str] = field(default_factory=list)
    source_agents: list[str] = field(default_factory=list)
    confidence: float = 0.0
    applicability: str = ""          # "all", "by_capability", "by_contract_type"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    times_applied: int = 0
    success_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pattern_type": self.pattern_type,
            "title": self.title,
            "summary": self.summary,
            "source_experiences": self.source_experiences,
            "source_agents": self.source_agents,
            "confidence": self.confidence,
            "applicability": self.applicability,
            "created_at": self.created_at,
            "times_applied": self.times_applied,
            "success_rate": self.success_rate,
        }
