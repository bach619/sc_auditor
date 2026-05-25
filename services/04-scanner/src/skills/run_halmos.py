"""RunHalmosSkill — Run Halmos symbolic execution engine."""

from __future__ import annotations

from typing import Any
from shared.skills.base_skill import BaseSkill


class RunHalmosSkill(BaseSkill):
    name = "run_halmos"
    description = "Run Halmos symbolic execution for formal verification of smart contracts"
    category = "symbolic"

    parameters = {
        "sources": {"type": "object", "required": True, "description": "Source code"},
        "address": {"type": "string", "required": False},
        "chain": {"type": "string", "required": False},
    }

    def __init__(self, http_client: Any) -> None:
        super().__init__()
        self._http = http_client
        self._url = "http://04d-scanner-halmos:8017"

    async def run(
        self, sources: dict[str, str], address: str = "", chain: str = "ethereum", **kwargs: Any
    ) -> dict[str, Any]:
        import httpx
        try:
            resp = await self._http.post(
                f"{self._url}/scan",
                json={"sources": sources, "address": address, "chain": chain},
                timeout=600.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", data)
        except httpx.TimeoutException:
            return {"success": False, "error": "Halmos timed out after 600s", "findings": []}
        except Exception as exc:
            return {"success": False, "error": str(exc), "findings": []}
