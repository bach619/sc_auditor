"""RunPipelineSkill — Execute full audit pipeline."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class RunPipelineSkill(BaseSkill):
    name = "run_pipeline"
    description = "Execute a full audit pipeline for a contract: fetch \u2192 scan \u2192 analyze \u2192 report"
    category = "orchestration"

    parameters = {
        "address": {"type": "string", "required": True, "description": "Contract address"},
        "chain": {"type": "string", "required": True, "description": "Blockchain network"},
        "source": {"type": "object", "required": False, "description": "Pre-fetched source code"},
    }

    def __init__(self, pipeline: Any) -> None:
        super().__init__()
        self._pipeline = pipeline

    async def run(
        self, address: str, chain: str, source: dict[str, str] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        audit_id = await self._pipeline.start_audit(
            address=address,
            chain=chain,
            source=source,
        )
        return {"audit_id": audit_id, "status": "started", "address": address, "chain": chain}
