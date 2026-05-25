"""SyncProgramsSkill — Sync bounty programs from all providers."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class SyncProgramsSkill(BaseSkill):
    """Sync bounty programs from all configured providers (Immunefi, Cantina, Code4rena, etc.)."""

    name = "sync_programs"
    description = "Sync bounty programs from all providers (Immunefi, Cantina, Code4rena, HackerOne, Sherlock)"
    category = "intelligence"

    parameters = {
        "provider": {
            "type": "string",
            "required": False,
            "description": "Specific provider to sync (immunefi, cantina, code4rena, etc.). Syncs all if omitted.",
        },
        "full_sync": {
            "type": "boolean",
            "required": False,
            "description": "Force full re-sync instead of incremental",
        },
    }

    def __init__(self, sync_service: Any) -> None:
        super().__init__()
        self._sync = sync_service

    async def run(
        self, provider: str | None = None, full_sync: bool = False, **kwargs: Any
    ) -> dict[str, Any]:
        if provider:
            result = await self._sync.sync_provider(provider, full=full_sync)
        else:
            result = await self._sync.sync_all(full=full_sync)
        return {
            "synced": True,
            "provider": provider or "all",
            "result": result if isinstance(result, dict) else {"status": str(result)},
        }
