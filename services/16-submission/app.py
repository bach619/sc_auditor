from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from src.draft_generator import generate_draft
from src.evidence_collector import EvidenceCollector
from src.intent_classifier import classify_intent
from src.models import (
    ApiResponse,
    BugCategory,
    CategoryStats,
    CreateSubmissionRequest,
    DraftRequest,
    DraftResponse,
    HealthData,
    IntentClassification,
    Message,
    MessageRole,
    Meta,
    StatsResponse,
    Submission,
    SubmissionStatus,
)
from src.storage import SubmissionStorage
from shared.observability import setup_observability
from src.webhook_handler import handle_classify_intent_request, handle_immunefi_webhook

SERVICE_NAME = "submission"
SERVICE_VERSION = "0.1.0"
DATA_DIR = Path(os.environ.get("SUBMISSION_DATA_DIR", "/data/submission"))


class AppState:
    def __init__(self) -> None:
        self.storage = SubmissionStorage(DATA_DIR)
        self.evidence = EvidenceCollector(
            immunefi_url=os.environ.get("IMMUNEFI_URL", "http://02-immunefi:8001"),
            source_url=os.environ.get("SOURCE_URL", "http://03-source:8000"),
            ai_url=os.environ.get("AI_URL", "http://06-ai:8004"),
            exploit_url=os.environ.get("EXPLOIT_URL", "http://08-exploit:8006"),
            orchestrator_url=os.environ.get("ORCHESTRATOR_URL", "http://11-orchestrator:8000"),
        )
        self.ai_url = os.environ.get("AI_URL", "http://06-ai:8004")

    async def close(self) -> None:
        pass


def _get_state(request: Request) -> AppState:
    return request.app.state.vyper


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    state = AppState()
    app.state.vyper = state

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    log.info(
        "submission.startup",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        data_dir=str(DATA_DIR),
    )

    yield

    await state.close()
    log.info("submission.shutdown", service=SERVICE_NAME)


app = FastAPI(
    title="Vyper Submission Assistant",
    description="Submission Assistant Service — helps communicate with Immunefi. "
    "Analyses messages, classifies intent, collects evidence, and drafts responses.",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

log = setup_observability(app, "16-submission", "0.1.0")


def ok(data: object = None) -> ApiResponse:
    return ApiResponse(data=data, meta=Meta(status="ok"))


def err(detail: str, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


@app.get("/health")
@app.get("/health/ready")
async def health(request: Request) -> ApiResponse:
    state = _get_state(request)
    submissions = state.storage.list_all_submissions()
    return ok(
        HealthData(
            status="ok",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
            submissions_count=len(submissions),
            data_dir=str(DATA_DIR),
        )
    )


@app.post("/submissions")
async def create_submission(body: CreateSubmissionRequest, request: Request) -> ApiResponse:
    state = _get_state(request)

    existing = state.storage.load_submission(body.finding_id)
    if existing:
        raise err(f"Submission for finding {body.finding_id} already exists", 409)

    sub = Submission(
        id=str(uuid4()),
        finding_id=body.finding_id,
        program_slug=body.program_slug,
        bug_category=body.bug_category,
        title=body.title,
        description=body.description,
        severity=body.severity,
        poc_solidity=body.poc_solidity,
        tx_hash=body.tx_hash,
        exploit_sequence=body.exploit_sequence,
        category_evidence=body.category_evidence,
        status=SubmissionStatus.draft,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    if state.storage.save_submission(sub):
        log.info("submission.created", finding_id=body.finding_id, category=body.bug_category)
        return ok(sub.model_dump(mode="json"))

    raise err("Failed to save submission", 500)


@app.get("/submissions")
async def list_submissions(request: Request, category: str | None = None, status: str | None = None) -> ApiResponse:
    state = _get_state(request)

    if category:
        finding_ids = state.storage.list_by_category(category)
    elif status:
        finding_ids = state.storage.list_by_status(status)
    else:
        finding_ids = None

    if finding_ids is not None:
        submissions = []
        for fid in finding_ids:
            sub = state.storage.load_submission(fid)
            if sub:
                submissions.append(sub)
    else:
        submissions = state.storage.list_all_submissions()

    return ok([s.model_dump(mode="json") for s in submissions])


@app.get("/submissions/{finding_id}")
async def get_submission(finding_id: str, request: Request) -> ApiResponse:
    state = _get_state(request)
    sub = state.storage.load_submission(finding_id)
    if not sub:
        raise err(f"Submission {finding_id} not found", 404)

    result = sub.model_dump(mode="json")
    result["messages"] = [m.model_dump(mode="json") for m in state.storage.load_messages(sub.id)]
    return ok(result)


@app.post("/submissions/{finding_id}/draft")
async def generate_submission_draft(finding_id: str, body: DraftRequest, request: Request) -> ApiResponse:
    state = _get_state(request)
    sub = state.storage.load_submission(finding_id)
    if not sub:
        raise err(f"Submission {finding_id} not found", 404)

    intent_result = await classify_intent(
        message_text=body.immunefi_message,
        ai_url=state.ai_url,
        bug_category=body.bug_category or sub.bug_category,
    )

    evidence = await state.evidence.collect_all_evidence(
        finding_id=sub.finding_id,
        bug_category=sub.bug_category.value if hasattr(sub.bug_category, "value") else str(sub.bug_category),
    )

    draft = await generate_draft(
        submission=sub,
        immunefi_message=body.immunefi_message,
        intent=intent_result.intent,
        evidence=evidence,
        ai_url=state.ai_url,
        tone=body.tone,
    )

    return ok(
        DraftResponse(
            draft=draft,
            intent=intent_result.intent,
            confidence=intent_result.confidence,
            bug_category=intent_result.bug_category or sub.bug_category,
            suggested_evidence=intent_result.suggested_evidence,
        )
    )


@app.post("/submissions/{finding_id}/respond")
async def respond_to_immunefi(finding_id: str, request: Request) -> ApiResponse:
    state = _get_state(request)
    sub = state.storage.load_submission(finding_id)
    if not sub:
        raise err(f"Submission {finding_id} not found", 404)

    body = await request.json()
    message_content = body.get("message", "")
    if not message_content:
        raise err("message is required", 400)

    attachments = body.get("attachments", [])

    msg = Message(
        id=str(uuid4()),
        submission_id=sub.id,
        role=MessageRole.us,
        content=message_content,
        attachments=attachments,
    )
    state.storage.save_message(msg)

    sub.status = SubmissionStatus.submitted
    sub.updated_at = datetime.now(timezone.utc)
    state.storage.save_submission(sub)

    log.info("submission.response_sent", finding_id=finding_id)
    return ok({"message_id": msg.id, "status": "sent"})


@app.get("/submissions/{finding_id}/evidence")
async def get_evidence(finding_id: str, request: Request) -> ApiResponse:
    state = _get_state(request)
    sub = state.storage.load_submission(finding_id)
    if not sub:
        raise err(f"Submission {finding_id} not found", 404)

    evidence = await state.evidence.collect_all_evidence(
        finding_id=sub.finding_id,
        bug_category=sub.bug_category.value if hasattr(sub.bug_category, "value") else str(sub.bug_category),
    )
    return ok(evidence)


@app.post("/webhook/immunefi")
async def immunefi_webhook(request: Request) -> ApiResponse:
    state = _get_state(request)
    payload = await request.json()

    result = await handle_immunefi_webhook(
        payload=payload,
        storage=state.storage,
        evidence_collector=state.evidence,
        ai_url=state.ai_url,
    )
    return ok(result)


@app.post("/ai/classify-intent")
async def classify_message_intent(request: Request) -> ApiResponse:
    state = _get_state(request)
    body = await request.json()

    message_text = body.get("message", "")
    if not message_text:
        raise err("message is required", 400)

    bug_category = None
    if body.get("bug_category"):
        try:
            bug_category = BugCategory(body["bug_category"])
        except ValueError:
            pass

    result = await handle_classify_intent_request(
        message_text=message_text,
        ai_url=state.ai_url,
        bug_category=bug_category,
    )
    return ok(result)


@app.get("/stats")
async def get_stats(request: Request) -> ApiResponse:
    state = _get_state(request)
    submissions = state.storage.list_all_submissions()

    by_category: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_program: dict[str, int] = {}

    for sub in submissions:
        cat = sub.bug_category.value if hasattr(sub.bug_category, "value") else str(sub.bug_category)
        by_category[cat] = by_category.get(cat, 0) + 1

        st = sub.status.value if hasattr(sub.status, "value") else str(sub.status)
        by_status[st] = by_status.get(st, 0) + 1

        by_severity[sub.severity] = by_severity.get(sub.severity, 0) + 1
        by_program[sub.program_slug] = by_program.get(sub.program_slug, 0) + 1

    return ok(
        StatsResponse(
            total_submissions=len(submissions),
            by_category=by_category,
            by_status=by_status,
            by_severity=by_severity,
            by_program=by_program,
        )
    )


@app.get("/stats/categories")
async def get_category_stats(request: Request) -> ApiResponse:
    state = _get_state(request)
    submissions = state.storage.list_all_submissions()

    category_data: dict[str, list[Submission]] = {}
    for sub in submissions:
        cat = sub.bug_category.value if hasattr(sub.bug_category, "value") else str(sub.bug_category)
        category_data.setdefault(cat, []).append(sub)

    stats: list[CategoryStats] = []
    for cat, subs in sorted(category_data.items()):
        accepted = sum(1 for s in subs if s.status in (SubmissionStatus.accepted, SubmissionStatus.paid))
        rejected = sum(1 for s in subs if s.status == SubmissionStatus.rejected)
        total = len(subs)
        rate = (accepted / total * 100) if total > 0 else 0.0
        stats.append(
            CategoryStats(
                category=cat,
                total=total,
                accepted=accepted,
                rejected=rejected,
                acceptance_rate=round(rate, 1),
            )
        )

    return ok(stats)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False,
    )
