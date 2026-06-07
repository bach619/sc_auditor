from __future__ import annotations

from app import _ok
from fastapi import APIRouter
from src.models import ApiResponse
from src.utils.circuit_breaker import all_circuit_breakers

router = APIRouter()


@router.get("/circuit-breakers")
async def get_circuit_breakers() -> ApiResponse:
    """Get status of all circuit breakers."""
    return _ok(all_circuit_breakers())


@router.post("/circuit-breakers/reset")
async def reset_circuit_breakers() -> ApiResponse:
    """Reset all circuit breakers."""
    from src.utils.circuit_breaker import reset_all
    reset_all()
    return _ok({"message": "All circuit breakers reset"})
