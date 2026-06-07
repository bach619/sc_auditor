"""Intelligence routes — scores, trends, anomalies, repos, competition, prediction, TVL, match, similar, vulns."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.models import ApiResponse
from src.state import ok, sync_manager

router = APIRouter()


# ── Intelligence Endpoints ────────────────────────────────

@router.get("/intel/scores")
async def get_program_scores() -> ApiResponse:
    """Get intelligence scores for all programs (ranked)."""
    scores = sync_manager.get_scores()
    return ok(scores)


@router.get("/intel/scores/{slug}")
async def get_program_score(slug: str) -> ApiResponse:
    """Get intelligence score for a single program."""
    score = sync_manager.get_score_for(slug)
    if not score:
        raise HTTPException(status_code=404, detail=f"Program '{slug}' not found")
    return ok(score)


@router.get("/intel/trends")
async def get_trends() -> ApiResponse:
    """Get full trend report."""
    trends = sync_manager.get_trends()
    return ok(trends)


@router.get("/intel/trends/recent")
async def get_recent_changes(
    hours: int = Query(24, ge=1, le=720, description="Lookback hours"),
) -> ApiResponse:
    """Get recent changes summary."""
    changes = sync_manager.get_trends_recent(hours=hours)
    return ok(changes)


@router.get("/intel/anomalies")
async def get_anomalies() -> ApiResponse:
    """Detect anomalies across all programs."""
    anomalies = sync_manager.get_anomalies()
    return ok(anomalies)


@router.get("/intel/repos")
async def get_repo_intel(
    max_programs: int = Query(20, ge=1, le=100),
) -> ApiResponse:
    """Fetch GitHub repo intelligence for programs with repos."""
    intel = await sync_manager.get_repo_intel(max_programs=max_programs)
    return ok({
        "total": len(intel),
        "results": intel,
    })


# ── Level 3: Autonomous Endpoints ─────────────────────────

@router.get("/programs/{slug}/competition")
async def get_program_competition(slug: str) -> ApiResponse:
    """Analisis kompetisi untuk program bounty."""
    result = await sync_manager.analyze_competition(slug)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return ok(result)


@router.get("/programs/{slug}/prediction")
async def predict_bounty(slug: str) -> ApiResponse:
    """Prediksi perubahan bounty untuk program."""
    result = await sync_manager.predict_bounty(slug)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return ok(result)


# ── Level 2 Leftovers ─────────────────────────────────────

@router.get("/programs/recommendations")
async def get_program_recommendations(
    min_bounty: float = Query(10000, ge=0, description="Minimum bounty"),
    chain: str | None = Query(None, description="Filter by chain"),
    limit: int = Query(10, ge=1, le=50),
) -> ApiResponse:
    """Rekomendasi program terbaik berdasarkan preferensi.

    Menggabungkan intelligence score + bounty + chain preference.
    """
    programs = list(sync_manager.programs.values())

    # Filter by min bounty
    if min_bounty > 0:
        programs = [p for p in programs if (p.max_bounty or 0) >= min_bounty]

    # Filter by chain
    if chain:
        chain_lower = chain.lower()
        programs = [
            p for p in programs
            if any(c.lower() == chain_lower for c in p.chains)
        ]

    # Score + sort
    from src.scorer import ProgramScorer  # noqa: PLC0415
    scorer = ProgramScorer()
    scored = []
    for p in programs:
        score = scorer.score(p)
        scored.append({
            "slug": p.slug,
            "name": p.name,
            "score": score,
            "max_bounty": p.max_bounty,
            "chains": p.chains,
            "status": p.status,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)

    return ok({
        "total": len(scored),
        "returned": min(len(scored), limit),
        "recommendations": scored[:limit],
    })


# ── Level 4: God-Tier Endpoints ──────────────────────────

@router.get("/tvl/{protocol_slug}")
async def fetch_protocol_tvl(protocol_slug: str) -> ApiResponse:
    """Fetch TVL data untuk protocol tertentu dari DeFiLlama."""
    result = await sync_manager.fetch_tvl(protocol_slug)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return ok(result)


@router.post("/tvl/refresh")
async def refresh_all_tvl(
    max_programs: int = Query(20, ge=1, le=100),
) -> ApiResponse:
    """Refresh TVL data for all programs that have valid slugs."""
    results = await sync_manager.fetch_all_tvl(max_programs=max_programs)
    return ok({
        "total": len(results),
        "results": results,
    })


@router.get("/tvl/stats")
async def get_tvl_stats() -> ApiResponse:
    """Get TVL cache statistics."""
    stats = sync_manager.get_tvl_stats()
    return ok(stats)


@router.get("/match")
async def match_programs(
    specialization: str = Query(..., description="Your specialization"),
    min_bounty: float = Query(0, ge=0),
    chain: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
) -> ApiResponse:
    """AI-powered program matching — cari program terbaik untuk skillmu."""
    results = await sync_manager.match_programs(
        specialization=specialization,
        min_bounty=min_bounty,
        chain=chain,
        limit=limit,
    )
    return ok({
        "specialization": specialization,
        "total": len(results),
        "matches": results,
    })


@router.get("/programs/{slug}/similar")
async def get_similar_programs(
    slug: str,
    limit: int = Query(5, ge=1, le=20),
) -> ApiResponse:
    """Cari program serupa berdasarkan embedding AI."""
    results = await sync_manager.find_similar_programs(slug, limit=limit)
    if isinstance(results, list) and len(results) > 0 and "error" in results[0]:
        raise HTTPException(404, results[0]["error"])
    return ok({
        "slug": slug,
        "total": len(results),
        "similar": results,
    })


@router.get("/programs/{slug}/predict-vulns")
async def predict_vulnerabilities(slug: str) -> ApiResponse:
    """Predict kemungkinan vulnerability type untuk program."""
    result = await sync_manager.predict_vulnerabilities(slug)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return ok(result)
