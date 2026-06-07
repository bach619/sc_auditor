"""Submission routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.models import ApiResponse
from src.state import ok, sync_manager

router = APIRouter()


@router.post("/programs/{slug}/submit")
async def submit_finding(slug: str, body: dict) -> ApiResponse:
    """Auto-submit finding ke Immunefi via API.

    Body:
        title (str): Finding title
        description (str): Detailed description
        severity (str): critical/high/medium/low
        vulnerability_classification (str): reentrancy, access_control, etc.
        proof_of_concept (str): PoC code/text
        contract_address (str): 0x-prefixed address
    """
    prog = sync_manager.programs.get(slug)
    if not prog:
        raise HTTPException(404, f"Program '{slug}' not found")

    required = ["title", "description", "severity", "proof_of_concept", "contract_address"]
    missing = [f for f in required if f not in body]
    if missing:
        raise HTTPException(422, f"Missing fields: {', '.join(missing)}")

    result = await sync_manager.submit_finding(
        program_slug=slug,
        title=body["title"],
        description=body["description"],
        severity=body["severity"],
        vulnerability_classification=body.get("vulnerability_classification", "auto"),
        proof_of_concept=body["proof_of_concept"],
        contract_address=body["contract_address"],
    )
    return ok(result)


@router.get("/submissions")
async def list_submissions(
    status: str | None = Query(None, description="Filter by status"),
) -> ApiResponse:
    """List semua submission yang sudah dilakukan."""
    submissions = sync_manager.list_submissions(status=status)
    return ok({
        "total": len(submissions),
        "submissions": submissions,
    })


@router.get("/submissions/stats")
async def get_submission_stats() -> ApiResponse:
    """Statistik submission."""
    stats = sync_manager.get_submission_stats()
    return ok(stats)


@router.get("/submissions/{submission_id}")
async def get_submission(submission_id: str) -> ApiResponse:
    """Detail satu submission."""
    sub = sync_manager.get_submission(submission_id)
    if not sub:
        raise HTTPException(404, f"Submission '{submission_id}' not found")
    return ok(sub)
