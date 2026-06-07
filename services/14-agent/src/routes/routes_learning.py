from __future__ import annotations

import app
from app import _err, _ok
from fastapi import APIRouter
from pydantic import BaseModel, Field
from src.models import ApiResponse

router = APIRouter()


class FeedbackRequest(BaseModel):
    session_id: str
    rating: int = Field(default=3, ge=1, le=5)
    comment: str = ""
    tags: list[str] = Field(default_factory=list)


@router.post("/learning/feedback")
async def submit_feedback(body: FeedbackRequest) -> ApiResponse:
    """Submit feedback for a completed session."""
    if app.state is None or app.state.agent is None:
        raise _err("Service not initialized", 503)

    session = app.state.agent.get_session(body.session_id)
    if session is None:
        raise _err(f"Session not found: {body.session_id}", 404)

    # Store feedback in vector memory
    memory = app.state.agent.memory
    try:
        await memory.vector.store(
            f"feedback_{body.session_id[:8]}",
            f"Session {body.session_id[:8]}: rating={body.rating}/5, {body.comment}",
            metadata={
                "type": "feedback",
                "session_id": body.session_id,
                "rating": body.rating,
                "tags": body.tags,
                "comment": body.comment[:200],
            },
        )
    except Exception as exc:
        app.log.warning("feedback_store_failed", error=str(exc))

    return _ok({
        "submitted": True,
        "session_id": body.session_id,
        "rating": body.rating,
    })


@router.get("/learning/stats")
async def learning_stats() -> ApiResponse:
    """Get learning statistics."""
    if app.state is None or app.state.learner is None:
        raise _err("Service not initialized", 503)

    return _ok(app.state.learner.get_stats())


@router.get("/learning/recommendations")
async def learning_recommendations(
    task_type: str | None = None,
) -> ApiResponse:
    """Get learning-based recommendations.

    **Query params**::
        task_type: Optional filter by task type
    """
    if app.state is None or app.state.learner is None:
        raise _err("Service not initialized", 503)

    recommendations = await app.state.learner.get_recommendations(
        task_type=task_type
    )
    return _ok(recommendations)
