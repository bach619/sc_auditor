"""CompetitionIntelligence — Analisis kompetisi antar bug hunter.

Menggunakan data submission history (dari Immunefi API atau lokal)
untuk menilai seberapa kompetitif suatu program bounty.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.models import Program
from src.storage import EnhancedJSONStorage


class CompetitionIntelligence:
    """Analisis kompetisi untuk program bounty."""

    def __init__(self, storage: EnhancedJSONStorage) -> None:
        self.storage = storage

    async def analyze_program(
        self,
        program: Program,
    ) -> dict[str, Any]:
        """Analisis tingkat kompetisi suatu program.

        Menggabungkan data on-chain (jumlah kontrak, bounty)
        dengan historical submission data.
        """
        slug = program.slug

        # Metrics
        bounty_score = self._bounty_attractiveness(program)
        contract_complexity = self._contract_complexity(program)
        chain_popularity = self._chain_popularity(program)
        repo_activity = self._repo_activity(program)

        # Composite competition level
        competition_score = (
            bounty_score * 0.35
            + contract_complexity * 0.25
            + chain_popularity * 0.20
            + repo_activity * 0.20
        )

        # Competition level
        if competition_score >= 80:
            competition = "very_high"
            strategy = "focus_on_deep_dive — bugs yang orang lain lewatkan"
        elif competition_score >= 60:
            competition = "high"
            strategy = "speed_first — submit cepat sebelum orang lain"
        elif competition_score >= 40:
            competition = "medium"
            strategy = "quality_over_speed — prioritaskan finding solid"
        elif competition_score >= 20:
            competition = "low"
            strategy = "first_mover — little competition, claim quickly"
        else:
            competition = "unknown"
            strategy = "explore — new program, assess manually"

        return {
            "slug": slug,
            "program_name": program.name,
            "competition_level": competition,
            "competition_score": round(competition_score, 1),
            "components": {
                "bounty_attractiveness": round(bounty_score, 1),
                "contract_complexity": round(contract_complexity, 1),
                "chain_popularity": round(chain_popularity, 1),
                "repo_activity": round(repo_activity, 1),
            },
            "max_bounty": program.max_bounty,
            "total_contracts": len(program.contracts),
            "total_repos": len(program.repos),
            "chains": program.chains,
            "recommended_strategy": strategy,
            "analyzed_at": datetime.now(UTC).isoformat(),
        }

    def _bounty_attractiveness(self, program: Program) -> float:
        """Higher bounty = more attractive = more competition."""
        bounty = program.max_bounty or 0
        if bounty >= 1_000_000:
            return 95.0
        elif bounty >= 100_000:
            return 75.0
        elif bounty >= 10_000:
            return 50.0
        elif bounty > 0:
            return 25.0
        return 10.0

    def _contract_complexity(self, program: Program) -> float:
        """More contracts = more complex = fewer competitors."""
        count = len(program.contracts)
        if count == 0:
            return 50.0  # unknown
        elif count >= 10:
            return 80.0  # very complex, fewer hunters
        elif count >= 5:
            return 65.0
        elif count >= 3:
            return 50.0
        return 30.0  # simple, many hunters

    def _chain_popularity(self, program: Program) -> float:
        """More popular chains = more hunters."""
        chains = [c.lower() for c in program.chains]
        ethereum_based = any("eth" in c or c == "ethereum" for c in chains)
        solana = any("sol" in c for c in chains)

        if ethereum_based:
            return 80.0  # most hunters are here
        elif solana:
            return 60.0
        elif len(chains) >= 3:
            return 70.0  # multi-chain = more exposure
        elif len(chains) == 0:
            return 50.0
        return 40.0  # niche chain = less competition

    def _repo_activity(self, program: Program) -> float:
        """Active repos = more attention = more competition."""
        count = len(program.repos)
        if count >= 3:
            return 70.0  # well-known project
        elif count >= 1:
            return 50.0
        return 20.0  # no public repo = less known
