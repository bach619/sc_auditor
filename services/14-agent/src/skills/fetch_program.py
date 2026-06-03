"""Skill: Fetch Immunefi program data."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.skills.base import BaseSkill
from src.models import SkillResult

log = structlog.get_logger()

IMMUNEFI_URL = "http://02-immunefi:8000"


class FetchProgramSkill(BaseSkill):
    """Mengambil data program Immunefi — list program, detail, contract addresses."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client

    @property
    def name(self) -> str:
        return "fetch_program"

    @property
    def description(self) -> str:
        return (
            "Mengambil data program bug bounty dari Immunefi. "
            "Bisa list semua program, cari program, atau ambil detail satu program. "
            "Hasilnya termasuk contract addresses, chain, max bounty, dan status program."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "action": {
                "type": "string",
                "description": "'list' untuk semua program, 'search' untuk cari, 'detail' untuk detail satu program",
                "required": True,
            },
            "query": {
                "type": "string",
                "description": "Keyword pencarian (required jika action='search')",
                "required": False,
            },
            "slug": {
                "type": "string",
                "description": "Slug program (required jika action='detail')",
                "required": False,
            },
            "chain": {
                "type": "string",
                "description": "Filter chain (ethereum, arbitrum, polygon, dll)",
                "required": False,
            },
        }

    async def run(self, **kwargs: Any) -> Any:
        action = kwargs.get("action", "list")

        if action == "list":
            params = {}
            if kwargs.get("chain"):
                params["chain"] = kwargs["chain"]
            resp = await self._client.get(f"{IMMUNEFI_URL}/programs", params=params)
            resp.raise_for_status()
            data = resp.json()
            programs_list = data.get("data", [])
            total = data.get("total", len(programs_list))
            return {
                "programs": programs_list,
                "count": len(programs_list),
                "_total_count": total,
                "_summary": f"Returned {len(programs_list)} of {total} programs. Use search or filter to narrow down."
            }

        elif action == "search":
            query = kwargs.get("query", "")
            if not query:
                return {"error": "query required for search"}
            resp = await self._client.get(f"{IMMUNEFI_URL}/programs", params={"search": query})
            resp.raise_for_status()
            data = resp.json()
            programs_list = data.get("data", [])
            total = data.get("total", len(programs_list))
            return {
                "programs": programs_list,
                "count": len(programs_list),
                "_total_count": total,
                "_summary": f"Found {len(programs_list)} programs matching '{query}' out of {total} total."
            }

        elif action == "detail":
            slug = kwargs.get("slug", "")
            if not slug:
                return {"error": "slug required for detail"}
            resp = await self._client.get(f"{IMMUNEFI_URL}/programs/{slug}")
            resp.raise_for_status()
            data = resp.json()
            return {"program": data.get("data", {})}

        else:
            return {"error": f"Unknown action: {action}"}
