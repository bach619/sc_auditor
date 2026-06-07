"""SubmissionAgent — Backend Agent for Immunefi submission assistant.

Receives delegations from Antonio, creates submissions, generates
draft responses, and manages the submission lifecycle.
"""

from __future__ import annotations

from typing import Any

from shared.agent_protocol.base_agent import BaseAgent
from shared.agent_protocol.models import (
    AgentCapability,
    CapabilityDefinition,
    DelegationRequest,
)

from .draft_generator import generate_draft
from .evidence_collector import EvidenceCollector
from .intent_classifier import classify_intent
from .skills import create_registry
from .storage import SubmissionStorage


class SubmissionAgent(BaseAgent):
    """Backend Agent for Immunefi submission assistant."""

    def __init__(
        self,
        storage: SubmissionStorage,
        evidence: EvidenceCollector,
        ai_url: str,
    ) -> None:
        self._storage = storage
        self._evidence = evidence
        self._ai_url = ai_url
        self.skill_registry = create_registry()
        super().__init__(
            service_name="16-submission",
            agent_role="submission_assistant",
            version="0.1.0",
            skill_registry=self.skill_registry,
        )
        self._max_concurrent = 3

        self.register_capability(CapabilityDefinition(
            name=AgentCapability.SUBMIT_FINDING,
            description="Create Immunefi submissions, generate draft responses, collect evidence",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "Action: create, draft, evidence, list"},
                    "finding_id": {"type": "string"},
                    "program_slug": {"type": "string"},
                    "bug_category": {"type": "string"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "result": {"type": "object"},
                },
            },
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        capability = request.capability
        data = request.input_data

        if capability == AgentCapability.SUBMIT_FINDING:
            action = data.get("action", "list")

            if action == "list":
                submissions = self._storage.list_all_submissions()
                return {
                    "total": len(submissions),
                    "submissions": [s.model_dump(mode="json") for s in submissions],
                }

            elif action == "get":
                finding_id = data.get("finding_id", "")
                sub = self._storage.load_submission(finding_id)
                if not sub:
                    return {"error": f"Submission {finding_id} not found"}
                return sub.model_dump(mode="json")

            elif action == "evidence":
                finding_id = data.get("finding_id", "")
                bug_category = data.get("bug_category", "other")
                sub = self._storage.load_submission(finding_id)
                if not sub:
                    return {"error": f"Submission {finding_id} not found"}
                evidence = await self._evidence.collect_all_evidence(
                    finding_id=finding_id,
                    bug_category=bug_category,
                )
                return {"evidence": evidence}

            elif action == "draft":
                finding_id = data.get("finding_id", "")
                message = data.get("immunefi_message", "")
                sub = self._storage.load_submission(finding_id)
                if not sub:
                    return {"error": f"Submission {finding_id} not found"}
                intent = await classify_intent(
                    message_text=message,
                    ai_url=self._ai_url,
                    bug_category=data.get("bug_category"),
                )
                evidence = await self._evidence.collect_all_evidence(
                    finding_id=finding_id,
                    bug_category=sub.bug_category.value if hasattr(sub.bug_category, "value") else str(sub.bug_category),
                )
                draft = await generate_draft(
                    submission=sub,
                    immunefi_message=message,
                    intent=intent.intent,
                    evidence=evidence,
                    ai_url=self._ai_url,
                    tone=data.get("tone"),
                )
                return {
                    "draft": draft,
                    "intent": intent.intent,
                    "confidence": intent.confidence,
                    "bug_category": intent.bug_category or sub.bug_category,
                }

            else:
                raise ValueError(f"Unknown action: {action}")
        else:
            raise ValueError(f"Unknown capability: {capability}")
