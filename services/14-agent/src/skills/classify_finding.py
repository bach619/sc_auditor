"""Skill: Classify findings as TP/FP and update learning metrics."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.skills.base import BaseSkill

log = structlog.get_logger()

CLASSIFIER_URL = "http://07-classifier:8000"


class ClassifyFindingSkill(BaseSkill):
    """Mengklasifikasikan temuan ke TP/FP/TN/FN dan memperbarui metrik pembelajaran."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client

    @property
    def name(self) -> str:
        return "classify_finding"

    @property
    def description(self) -> str:
        return (
            "Mengklasifikasikan temuan ke dalam 4 kategori: "
            "True Positive (bug nyata), False Positive (salah deteksi), "
            "True Negative (aman), False Negative (terlewat). "
            "Juga menyediakan metrik akurasi dan feedback learning."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "action": {
                "type": "string",
                "description": "'classify' untuk klasifikasi, 'metrics' untuk lihat statistik, 'feedback' untuk kirim feedback",
                "required": True,
            },
            "findings": {
                "type": "array",
                "description": "List of findings dengan AI verdict (required untuk action='classify')",
                "required": False,
            },
            "finding_id": {
                "type": "string",
                "description": "ID finding spesifik (required untuk action='feedback')",
                "required": False,
            },
            "feedback": {
                "type": "string",
                "description": "User feedback text (required untuk action='feedback')",
                "required": False,
            },
            "status": {
                "type": "string",
                "description": "Status: confirmed_tp, confirmed_fp, needs_review (required untuk action='feedback')",
                "required": False,
            },
        }

    async def run(self, **kwargs: Any) -> Any:
        action = kwargs.get("action", "classify")

        if action == "metrics":
            resp = await self._client.get(f"{CLASSIFIER_URL}/metrics")
            resp.raise_for_status()
            data = resp.json()
            return {"metrics": data.get("data", {})}

        elif action == "feedback":
            finding_id = kwargs.get("finding_id", "")
            feedback = kwargs.get("feedback", "")
            status = kwargs.get("status", "needs_review")
            if not finding_id:
                return {"error": "finding_id required"}

            body = {"finding_id": finding_id, "feedback": feedback, "status": status}
            resp = await self._client.post(f"{CLASSIFIER_URL}/feedback", json=body)
            resp.raise_for_status()
            data = resp.json()
            return {"result": data.get("data", {})}

        elif action == "classify":
            findings = kwargs.get("findings", [])
            if not findings:
                return {"error": "findings list required"}

            # Hitung distribusi
            tp = sum(1 for f in findings if f.get("ai_verdict") == "true_positive")
            fp = sum(1 for f in findings if f.get("ai_verdict") == "false_positive")
            pending = len(findings) - tp - fp

            return {
                "classification": {
                    "true_positives": tp,
                    "false_positives": fp,
                    "pending_review": pending,
                    "total": len(findings),
                },
                "findings": [
                    {
                        "id": f.get("id"),
                        "title": f.get("title"),
                        "tool": f.get("tool"),
                        "ai_verdict": f.get("ai_verdict"),
                        "ai_severity": f.get("ai_severity"),
                        "ai_confidence": f.get("ai_confidence"),
                    }
                    for f in findings
                ],
            }

        else:
            return {"error": f"Unknown action: {action}"}
