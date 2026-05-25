"""AnalyzeCompetitionSkill — Competitive analysis for a program."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class AnalyzeCompetitionSkill(BaseSkill):
    """Analyze competitive landscape for a bounty program."""

    name = "analyze_competition"
    description = "Analyze competitive landscape: similar programs, audit history, and market positioning"
    category = "analysis"

    parameters = {
        "slug": {"type": "string", "required": True, "description": "Program slug"},
    }

    def __init__(self, competition_service: Any) -> None:
        super().__init__()
        self._competition = competition_service

    async def run(self, slug: str, **kwargs: Any) -> dict[str, Any]:
        analysis = await self._competition.analyze(slug)
        return analysis if isinstance(analysis, dict) else {"result": str(analysis)}
