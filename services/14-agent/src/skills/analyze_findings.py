"""Skill: AI-powered vulnerability analysis of scanner findings."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.skills.base import BaseSkill

log = structlog.get_logger()

AI_URL = "http://06-ai:8000"


class AnalyzeFindingsSkill(BaseSkill):
    """Menggunakan AI (LLM) untuk menganalisis temuan scanner — TP/FP, severity, fix."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client

    @property
    def name(self) -> str:
        return "analyze_findings"

    @property
    def description(self) -> str:
        return (
            "Menganalisis temuan scanner menggunakan AI/LLM. "
            "Untuk setiap finding, AI akan menentukan True Positive atau False Positive, "
            "menilai severity yang tepat, memberikan reasoning, dan suggest fix code. "
            "Hasilnya adalah enriched findings dengan AI verdict."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "audit_id": {
                "type": "string",
                "description": "Unique audit session ID",
                "required": True,
            },
            "source": {
                "type": "object",
                "description": "Dictionary: filename → source code",
                "required": True,
            },
            "findings": {
                "type": "array",
                "description": "List of findings from scan_contract skill. Each has id, tool, title, description, severity, location",
                "required": True,
            },
            "compiler": {
                "type": "string",
                "description": "Solidity compiler version",
                "required": False,
            },
            "contract_name": {
                "type": "string",
                "description": "Nama kontrak",
                "required": False,
            },
        }

    async def run(self, **kwargs: Any) -> Any:
        findings = kwargs.get("findings", [])
        source = kwargs.get("source", {})

        if not findings:
            return {"error": "findings list required", "findings": []}
        if not source:
            return {"error": "source code required", "findings": []}

        body = {
            "audit_id": kwargs.get("audit_id", f"agent-{hash(str(findings))}"),
            "source": source,
            "findings": findings,
            "compiler": kwargs.get("compiler", ""),
            "contract_name": kwargs.get("contract_name", ""),
        }

        resp = await self._client.post(f"{AI_URL}/analyze", json=body)
        resp.raise_for_status()
        data = resp.json()

        result = data.get("data", {})
        enriched = result.get("findings", [])
        summary = result.get("summary", {})

        tp_count = sum(1 for f in enriched if f.get("ai_verdict") == "true_positive")
        fp_count = sum(1 for f in enriched if f.get("ai_verdict") == "false_positive")

        # Ambil findings critical/high yang confirmed
        critical_findings = [
            f for f in enriched
            if f.get("ai_verdict") == "true_positive"
            and f.get("ai_severity") in ("critical", "high")
        ]

        return {
            "findings": enriched,
            "summary": {
                "total": len(enriched),
                "true_positives": tp_count,
                "false_positives": fp_count,
                "critical_high_confirmed": len(critical_findings),
            },
            "critical_findings": critical_findings,
        }
