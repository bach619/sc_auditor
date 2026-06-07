"""Fork management routes."""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.models import ApiResponse
from src.state import ok, sync_manager

router = APIRouter()


# ── Fork L4: Fork Management ──────────────────────────────

@router.delete("/forks/{slug}")
async def delete_fork(slug: str) -> ApiResponse:
    """Hapus fork repo untuk program (via GitHub API).

    Body opsional:
      owner (str): GitHub owner of the fork (default: dari env GITHUB_USERNAME)
    """
    result = await sync_manager.fork_engine.delete_fork(slug)
    return ok(result)


@router.post("/forks/{slug}/sync")
async def sync_fork(slug: str) -> ApiResponse:
    """Sync fork dengan upstream (merge latest changes)."""
    result = await sync_manager.fork_engine.sync_fork_upstream(slug)
    return ok(result)


@router.get("/forks/{slug}/prs")
async def list_fork_prs(slug: str) -> ApiResponse:
    """List open pull requests dari forked repo."""
    prs = await sync_manager.fork_engine.list_prs(slug)
    return ok({
        "slug": slug,
        "total": len(prs),
        "prs": prs,
    })


@router.post("/forks/{slug}/pr")
async def create_fork_pr(
    slug: str,
    head_branch: str = Query(..., description="Branch with changes"),
    title: str = Query("Exploit PoC", description="PR title"),
    body: str = Query("", description="PR description"),
) -> ApiResponse:
    """Create a pull request dari forked repo ke upstream."""
    result = await sync_manager.fork_engine.create_pr(
        slug=slug,
        head_branch=head_branch,
        title=title,
        body=body,
    )
    return ok(result)


# ── Fork Endpoints ────────────────────────────────────────

@router.get("/forks")
async def get_fork_info() -> ApiResponse:
    """Get fork status: stats + list of unforked repos."""
    info = sync_manager.get_fork_info()
    return ok(info)


@router.post("/forks/all")
async def fork_all(
    max_forks: int = Query(10, ge=1, le=50, description="Max repos to fork"),
) -> ApiResponse:
    """Fork all unforked repos (up to max_forks)."""
    results = await sync_manager.fork_all_unforked(max_forks=max_forks)
    return ok({
        "total": len(results),
        "results": results,
    })


@router.post("/forks/{slug}")
async def fork_program(slug: str) -> ApiResponse:
    """Fork all unforked repos for a specific program."""
    results = await sync_manager.fork_program(slug)
    return ok({
        "slug": slug,
        "total": len(results),
        "results": results,
    })
