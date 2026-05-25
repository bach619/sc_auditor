"""SearchProgramsSkill — Search and filter bounty programs."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class SearchProgramsSkill(BaseSkill):
    """Search and filter bounty programs by multiple criteria."""

    name = "search_programs"
    description = "Search and filter bounty programs by chain, bounty amount, status, and other criteria"
    category = "intelligence"

    parameters = {
        "chain": {"type": "string", "required": False, "description": "Filter by blockchain (ethereum, solana, etc.)"},
        "min_bounty": {"type": "number", "required": False, "description": "Minimum bounty amount in USD"},
        "status": {"type": "string", "required": False, "description": "Program status (active, paused, closed)"},
        "search": {"type": "string", "required": False, "description": "Text search in program name/description"},
        "limit": {"type": "integer", "required": False, "description": "Max results to return"},
    }

    def __init__(self, storage_service: Any) -> None:
        super().__init__()
        self._storage = storage_service

    async def run(
        self,
        chain: str | None = None,
        min_bounty: float | None = None,
        status: str | None = None,
        search: str | None = None,
        limit: int = 20,
        **kwargs: Any,
    ) -> dict[str, Any]:
        filters = {}
        if chain:
            filters["chain"] = chain
        if min_bounty is not None:
            filters["min_bounty_usd"] = min_bounty
        if status:
            filters["status"] = status
        if search:
            filters["search"] = search

        programs = await self._storage.query_programs(filters=filters, limit=limit)
        return {
            "total": len(programs),
            "programs": programs[:limit] if isinstance(programs, list) else [],
            "filters_applied": filters,
        }
