"""CreateSubmissionSkill — create Immunefi submission."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class CreateSubmissionSkill(BaseSkill):
    """Create a new Immunefi bug submission from a security finding."""

    @property
    def name(self) -> str:
        return "create_submission"

    @property
    def description(self) -> str:
        return (
            "Create a new Immunefi submission from a verified security finding. "
            "Includes finding details, evidence references, and "
            "submission metadata. Stores submission for later retrieval."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "finding_id": {
                    "type": "string",
                    "description": "Unique identifier for the finding",
                },
                "program_slug": {
                    "type": "string",
                    "description": "Immunefi program slug",
                },
                "bug_category": {
                    "type": "string",
                    "description": "Category of the bug (e.g. reentrancy, overflow)",
                },
                "title": {
                    "type": "string",
                    "description": "Submission title",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of the vulnerability",
                },
                "severity": {
                    "type": "string",
                    "description": "Severity level (critical, high, medium, low)",
                },
                "proof_of_concept": {
                    "type": "string",
                    "description": "Proof of concept code or description",
                },
            },
            "required": ["finding_id", "program_slug", "bug_category", "title", "description", "severity"],
        }

    @property
    def category(self) -> str:
        return "submission"

    async def run(
        self,
        finding_id: str,
        program_slug: str,
        bug_category: str,
        title: str,
        description: str,
        severity: str,
        proof_of_concept: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        from ..storage import SubmissionStorage
        from ..models import BugCategory, SeverityLevel, Submission

        storage = SubmissionStorage()

        try:
            category_enum = BugCategory(bug_category)
        except ValueError:
            category_enum = BugCategory.other

        try:
            severity_enum = SeverityLevel(severity)
        except ValueError:
            severity_enum = SeverityLevel.medium

        submission = Submission(
            finding_id=finding_id,
            program_slug=program_slug,
            bug_category=category_enum,
            title=title,
            description=description,
            severity=severity_enum,
            proof_of_concept=proof_of_concept,
        )

        storage.save_submission(submission)

        return {
            "skill": "create_submission",
            "finding_id": finding_id,
            "program_slug": program_slug,
            "bug_category": bug_category,
            "severity": severity,
            "submission_id": submission.id if hasattr(submission, "id") else finding_id,
            "created_at": submission.created_at.isoformat() if hasattr(submission, "created_at") and hasattr(submission.created_at, "isoformat") else __import__("time").time(),
            "status": "created",
        }
