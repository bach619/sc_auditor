"""RunEchidnaSkill — Run Echidna fuzzer for property-based testing."""

from __future__ import annotations

from typing import Any
from shared.skills.base_skill import BaseSkill


class RunEchidnaSkill(BaseSkill):
    name = "run_echidna"
    description = "Run Echidna fuzzing to find property violations and edge-case vulnerabilities"
    category = "fuzzing"

    parameters = {
        "sources": {"type": "object", "required": True, "description": "Source code"},
        "address": {"type": "string", "required": False},
        "chain": {"type": "string", "required": False},
    }

    def __init__(self, http_client: Any) -> None:
        super().__init__()
        self._http = http_client
        self._url = "http://04b-scanner-echidna:8015"

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
            return {"success": False, "error": "Echidna timed out after 600s", "findings": []}
        except Exception as exc:
            return {"success": False, "error": str(exc), "findings": []}
