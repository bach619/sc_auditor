from __future__ import annotations

from datetime import UTC
from typing import Any
from uuid import uuid4

import structlog
from fastapi import HTTPException

from src.draft_generator import generate_draft
from src.evidence_collector import EvidenceCollector
from src.intent_classifier import classify_intent
from src.models import BugCategory, Message, MessageRole
from src.storage import SubmissionStorage

log = structlog.get_logger()


async def handle_immunefi_webhook(
    payload: dict[str, Any],
    storage: SubmissionStorage,
    evidence_collector: EvidenceCollector,
    ai_url: str,
) -> dict[str, Any]:
    """Process an incoming webhook from Immunefi.

    Steps:
    1. Parse the incoming message
    2. Find the related submission
    3. Classify intent
    4. Collect evidence
    5. Generate draft
    6. Save message
    7. Return draft and analysis
    """
    submission_id = payload.get("submission_id") or payload.get("finding_id")
    if not submission_id:
        raise HTTPException(status_code=400, detail="submission_id or finding_id required")

    message_content = payload.get("message", payload.get("content", ""))
    if not message_content:
        raise HTTPException(status_code=400, detail="message content required")

    attachments = payload.get("attachments", [])

    submission = storage.load_submission(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found")

    bug_category = None
    if payload.get("bug_category"):
        try:
            bug_category = BugCategory(payload["bug_category"])
        except ValueError:
            pass

    intent_result = await classify_intent(
        message_text=message_content,
        ai_url=ai_url,
        bug_category=bug_category or submission.bug_category,
    )

    evidence = await evidence_collector.collect_all_evidence(
        finding_id=submission.finding_id,
        bug_category=submission.bug_category.value if hasattr(submission.bug_category, "value") else str(submission.bug_category),
    )

    draft = await generate_draft(
        submission=submission,
        immunefi_message=message_content,
        intent=intent_result.intent,
        evidence=evidence,
        ai_url=ai_url,
    )

    msg = Message(
        id=str(uuid4()),
        submission_id=submission.id,
        role=MessageRole.immunefi,
        content=message_content,
        attachments=attachments,
        intent=intent_result.intent,
        intent_context={
            "confidence": intent_result.confidence,
            "bug_category": intent_result.bug_category.value if intent_result.bug_category else None,
            "suggested_evidence": intent_result.suggested_evidence,
        },
        suggested_reply=draft,
    )
    storage.save_message(msg)

    if intent_result.intent in ("accepted", "rejected") and submission.status not in ("accepted", "rejected", "paid"):
        from src.models import SubmissionStatus
        new_status = SubmissionStatus.accepted if intent_result.intent == "accepted" else SubmissionStatus.rejected
        submission.status = new_status
        from datetime import datetime
        submission.updated_at = datetime.now(UTC)
        storage.save_submission(submission)

    log.info(
        "webhook.processed",
        submission_id=submission.id,
        intent=intent_result.intent,
        confidence=intent_result.confidence,
    )

    return {
        "submission_id": submission.id,
        "finding_id": submission.finding_id,
        "intent": {
            "intent": intent_result.intent,
            "confidence": intent_result.confidence,
            "bug_category": intent_result.bug_category.value if intent_result.bug_category else None,
            "suggested_evidence": intent_result.suggested_evidence,
        },
        "draft": draft,
        "message_id": msg.id,
    }


async def handle_classify_intent_request(
    message_text: str,
    ai_url: str,
    bug_category: BugCategory | None = None,
) -> dict[str, Any]:
    """Classify the intent of a message."""
    result = await classify_intent(
        message_text=message_text,
        ai_url=ai_url,
        bug_category=bug_category,
    )
    return {
        "intent": result.intent,
        "confidence": result.confidence,
        "bug_category": result.bug_category.value if result.bug_category else None,
        "suggested_evidence": result.suggested_evidence,
        "required_evidence": result.required_evidence,
        "suggested_action": result.suggested_action,
    }
