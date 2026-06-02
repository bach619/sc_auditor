"""CollectEvidenceSkill — evidence collection for submissions."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class CollectEvidenceSkill(BaseSkill):
    """Collect all evidence for a finding to support Immunefi submission."""

    @property
    def name(self) -> str:
        return "collect_evidence"

    @property
    def description(self) -> str:
        return (
            "Collect comprehensive evidence for a security finding including "
            "source code snippets, transaction traces, PoC code, "
            "static analysis results, and severity scoring."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "finding_id": {
                    "type": "string",
                    "description": "Finding identifier to collect evidence for",
                },
                "bug_category": {
                    "type": "string",
                    "description": "Bug category to guide evidence collection",
                },
                "include_raw_outputs": {
                    "type": "boolean",
                    "description": "Include raw scanner outputs in evidence (default: false)",
                },
            },
            "required": ["finding_id"],
        }

    @property
    def category(self) -> str:
        return "submission"

    async def run(
        self,
        finding_id: str,
        bug_category: str = "other",
        include_raw_outputs: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        from ..evidence_collector import EvidenceCollector
        from ..storage import SubmissionStorage

        evidence_collector = EvidenceCollector()
        storage = SubmissionStorage()

        sub = storage.load_submission(finding_id)
        collected = await evidence_collector.collect_all_evidence(
            finding_id=finding_id,
            bug_category=bug_category,
        )

        evidence_items = collected if isinstance(collected, list) else collected.get("evidence", collected.get("items", []))
        total_items = len(evidence_items) if isinstance(evidence_items, list) else 1

        return {
            "skill": "collect_evidence",
            "finding_id": finding_id,
            "bug_category": bug_category,
            "evidence_count": total_items,
            "evidence": collected if include_raw_outputs else {
                "summary": f"Collected {total_items} evidence items",
                "types": list({e.get("type", e.get("category", "unknown")) for e in (evidence_items if isinstance(evidence_items, list) else [])}),
                "total_items": total_items,
            },
            "submission_exists": sub is not None,
            "success": True,
        }
