"""RunSlitherSkill — Run Slither static analyzer on smart contract source code."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class RunSlitherSkill(BaseSkill):
    name = "run_slither"
    description = "Run Slither static analysis to find common vulnerabilities and code quality issues"
    category = "scanning"

    parameters = {
        "sources": {"type": "object", "required": True, "description": "Source code {filename: content}"},
        "address": {"type": "string", "required": False, "description": "Contract address"},
        "chain": {"type": "string", "required": False, "description": "Blockchain network"},
    }

    def __init__(self, http_client: Any) -> None:
        super().__init__()
        self._http = http_client
        self._url = "http://04a-scanner-slither:8014"

    async def run(
        self, sources: dict[str, str], address: str = "", chain: str = "ethereum", **kwargs: Any
    ) -> dict[str, Any]:
        import httpx
        try:
            resp = await self._http.post(
                f"{self._url}/scan",
                json={"sources": sources, "address": address, "chain": chain},
                timeout=300.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", data)
        except httpx.TimeoutException:
            return {"success": False, "error": "Slither timed out after 300s", "findings": []}
        except Exception as exc:
            return {"success": False, "error": str(exc), "findings": []}
