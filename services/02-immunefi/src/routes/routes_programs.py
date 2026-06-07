"""Program CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.models import ApiResponse, ProgramListResponse
from src.state import ok, sync_manager

router = APIRouter()


@router.get("/programs")
async def list_programs(
    offset: int = Query(0, ge=0, description="Number of programs to skip"),
    limit: int = Query(50, ge=1, le=500, description="Max programs to return"),
    status: str | None = Query(None, description="Filter by status (active, inactive, etc.)"),
    chain: str | None = Query(None, description="Filter by blockchain"),
    search: str | None = Query(None, description="Search by name or slug"),
    sort: str = Query("name", description="Sort field: name, max_bounty, status"),
    order: str = Query("asc", description="Sort order: asc or desc"),
) -> ApiResponse:
    """List all synced programs with optional filtering."""
    programs = list(sync_manager.programs.values())

    # Filter by status
    if status:
        programs = [p for p in programs if p.status.lower() == status.lower()]

    # Filter by chain
    if chain:
        chain_lower = chain.lower()
        programs = [p for p in programs if any(c.lower() == chain_lower for c in p.chains)]

    # Search by name or slug
    if search:
        q = search.lower()
        programs = [
            p for p in programs
            if q in p.name.lower() or q in p.slug.lower()
        ]

    # Sort
    reverse = order.lower() == "desc"
    if sort == "max_bounty":
        programs.sort(key=lambda p: p.max_bounty or 0, reverse=reverse)
    elif sort == "status":
        programs.sort(key=lambda p: p.status, reverse=reverse)
    else:
        programs.sort(key=lambda p: p.name.lower(), reverse=reverse)

    total = len(programs)
    paginated = programs[offset:offset + limit]

    return ok(
        ProgramListResponse(
            data=paginated,
            total=total,
            offset=offset,
            limit=limit,
        )
    )


@router.get("/programs/{slug:path}/history")
async def get_program_history(
    slug: str,
    limit: int = Query(50, ge=1, le=500),
) -> ApiResponse:
    """Get change history for a specific program."""
    history = sync_manager.storage.get_history(slug, limit=limit)
    return ok({
        "slug": slug,
        "total": len(history),
        "history": history,
    })


@router.get("/programs/{slug:path}/contracts")
async def get_program_contracts(slug: str) -> ApiResponse:
    """Get smart contract addresses for a specific program."""
    program = sync_manager.programs.get(slug)
    if not program:
        raise HTTPException(status_code=404, detail=f"Program '{slug}' not found")
    return ok({
        "slug": slug,
        "total": len(program.contracts),
        "contracts": [c.model_dump() for c in program.contracts],
    })


# ── Alias endpoints (backward compat dengan daily_agenda) ──

@router.get("/programs/chains")
async def list_chains_alias() -> ApiResponse:
    """[Alias] Same as /chains — list unique chains across all programs."""
    from src.routes.routes_contracts import list_chains
    return await list_chains()


@router.get("/programs/trends")
async def get_trends_alias() -> ApiResponse:
    """[Alias] Same as /intel/trends — full trend report."""
    from src.routes.routes_intel import get_trends
    return await get_trends()


@router.get("/programs/alerts")
async def get_alerts_alias() -> ApiResponse:
    """[Alias] Same as /intel/anomalies — anomaly alerts."""
    from src.routes.routes_intel import get_anomalies
    return await get_anomalies()


@router.get("/programs/{slug}/intelligence")
async def get_program_intelligence_alias(slug: str) -> ApiResponse:
    """[Alias] Same as /intel/scores/{slug} — intelligence score."""
    from src.routes.routes_intel import get_program_score
    return await get_program_score(slug)


@router.get("/programs/{slug:path}")
async def get_program(slug: str) -> ApiResponse:
    """Get a single program by slug."""
    program = sync_manager.programs.get(slug)
    if not program:
        raise HTTPException(status_code=404, detail=f"Program '{slug}' not found")
    return ok(program)
