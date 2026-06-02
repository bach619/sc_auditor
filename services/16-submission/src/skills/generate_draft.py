"""GenerateDraftSkill — generate draft response for Immunefi."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class GenerateDraftSkill(BaseSkill):
    """Generate a draft response to an Immunefi message based on context."""

    @property
    def name(self) -> str:
        return "generate_draft"

    @property
    def description(self) -> str:
        return (
            "Generate a contextual draft response for an Immunefi conversation. "
            "Analyzes the immunefi message, determines intent, collects "
            "relevant evidence, and produces a professional response draft."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "finding_id": {
                    "type": "string",
                    "description": "Finding identifier",
                },
                "immunefi_message": {
                    "type": "string",
                    "description": "Latest message from Immunefi to respond to",
                },
                "bug_category": {
                    "type": "string",
                    "description": "Bug category for context",
                },
                "tone": {
                    "type": "string",
                    "enum": ["professional", "technical", "concise"],
                    "description": "Desired tone for the draft",
                },
            },
            "required": ["finding_id", "immunefi_message"],
        }

    @property
    def category(self) -> str:
        return "submission"

    async def run(
        self,
        finding_id: str,
        immunefi_message: str,
        bug_category: str = "",
        tone: str = "professional",
        **kwargs: Any,
    ) -> dict[str, Any]:
        from ..storage import SubmissionStorage
        from ..evidence_collector import EvidenceCollector
        from ..draft_generator import generate_draft
        from ..intent_classifier import classify_intent

        storage = SubmissionStorage()
        evidence = EvidenceCollector()

        sub = storage.load_submission(finding_id)
        if not sub:
            return {
                "skill": "generate_draft",
                "error": f"Submission {finding_id} not found",
                "success": False,
            }

        ai_url = kwargs.get("ai_url", "")

        intent = await classify_intent(
            message_text=immunefi_message,
            ai_url=ai_url,
            bug_category=bug_category or sub.bug_category.value if hasattr(sub.bug_category, "value") else str(sub.bug_category),
        )

        collected_evidence = await evidence.collect_all_evidence(
            finding_id=finding_id,
            bug_category=bug_category or sub.bug_category.value if hasattr(sub.bug_category, "value") else str(sub.bug_category),
        )

        draft = await generate_draft(
            submission=sub,
            immunefi_message=immunefi_message,
            intent=intent.intent,
            evidence=collected_evidence,
            ai_url=ai_url,
            tone=tone,
        )

        return {
            "skill": "generate_draft",
            "finding_id": finding_id,
            "draft": draft,
            "intent": intent.intent,
            "intent_confidence": intent.confidence,
            "tone": tone,
            "success": True,
        }
