from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class BugCategory(StrEnum):
    reentrancy = "reentrancy"
    oracle_manipulation = "oracle_manipulation"
    flash_loan = "flash_loan"
    mev = "mev"
    access_control = "access_control"
    overflow = "overflow"
    precision_loss = "precision_loss"
    bridge = "bridge"
    zero_day = "zero_day"
    governance = "governance"
    signature_replay = "signature_replay"
    storage_collision = "storage_collision"
    donation = "donation"
    other = "other"


class SubmissionStatus(StrEnum):
    draft = "draft"
    submitted = "submitted"
    in_review = "in_review"
    accepted = "accepted"
    rejected = "rejected"
    paid = "paid"


class Submission(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    finding_id: str
    program_slug: str
    bug_category: BugCategory = BugCategory.other
    title: str
    description: str
    severity: str = "medium"
    poc_solidity: str = ""
    tx_hash: str | None = None
    exploit_sequence: list[dict] = Field(default_factory=list)
    category_evidence: dict[str, Any] = Field(default_factory=dict)
    status: SubmissionStatus = SubmissionStatus.draft
    immunefi_submission_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MessageRole(StrEnum):
    us = "us"
    immunefi = "immunefi"


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    submission_id: str
    role: MessageRole
    content: str
    attachments: list[str] = Field(default_factory=list)
    intent: str = ""
    intent_context: dict[str, Any] | None = None
    suggested_reply: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IntentClassification(BaseModel):
    intent: str
    confidence: float
    bug_category: BugCategory | None = None
    suggested_evidence: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    suggested_action: str = ""


class DraftRequest(BaseModel):
    immunefi_message: str
    bug_category: BugCategory | None = None
    tone: str = "professional"


class DraftResponse(BaseModel):
    draft: str
    intent: str
    confidence: float
    bug_category: BugCategory
    suggested_evidence: list[str] = Field(default_factory=list)
    category_specific_tips: list[str] = Field(default_factory=list)
    alternative_drafts: list[str] = Field(default_factory=list)


class CreateSubmissionRequest(BaseModel):
    finding_id: str
    program_slug: str
    bug_category: BugCategory = BugCategory.other
    title: str
    description: str = ""
    severity: str = "medium"
    poc_solidity: str = ""
    tx_hash: str | None = None
    exploit_sequence: list[dict] = Field(default_factory=list)
    category_evidence: dict[str, Any] = Field(default_factory=dict)


class Meta(BaseModel):
    status: str = "ok"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class ApiResponse(BaseModel):
    data: Any = None
    meta: Meta = Field(default_factory=Meta)


class HealthData(BaseModel):
    status: str = "ok"
    service: str = "submission"
    version: str = "0.1.0"
    submissions_count: int = 0
    data_dir: str = ""


class StatsResponse(BaseModel):
    total_submissions: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_program: dict[str, int] = Field(default_factory=dict)


class CategoryStats(BaseModel):
    category: str
    total: int = 0
    accepted: int = 0
    rejected: int = 0
    acceptance_rate: float = 0.0
    average_response_time_hours: float = 0.0
