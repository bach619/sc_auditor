"""RetryFailedSkill — Retry failed audits."""

from __future__ import annotations

from typing import Any
from shared.skills.base_skill import BaseSkill


class RetryFailedSkill(BaseSkill):
    name = "retry_failed"
    description = "Retry failed audit pipelines"
    category = "orchestration"

    parameters = {
        "audit_id": {"type": "string", "required": False, "description": "Specific audit ID to retry"},
        "retry_all": {"type": "boolean", "required": False, "description": "Retry all failed audits"},
    }

    def __init__(self, pipeline: Any) -> None:
        super().__init__()
        self._pipeline = pipeline

    async def run(
        self, audit_id: str | None = None, retry_all: bool = False, **kwargs: Any
    ) -> dict[str, Any]:
        if audit_id:
            result = await self._pipeline.retry(audit_id=audit_id)
            return {"retried": [audit_id], "results": [str(result)]}
        elif retry_all:
            results = await self._pipeline.retry_all_failed()
            return {"retried": results if isinstance(results, list) else [], "count": len(results) if isinstance(results, list) else 0}
        return {"error": "Provide audit_id or set retry_all=True"}
