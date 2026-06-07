"""Contracts, scope, chains, and fetch routes."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Query

from src.models import ApiResponse
from src.state import ok, sync_manager

router = APIRouter()


@router.get("/contracts")
async def list_all_contracts(
    chain: str | None = Query(None, description="Filter by blockchain"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> ApiResponse:
    """List all smart contracts across all synced programs."""
    all_contracts = []
    for program in sync_manager.programs.values():
        for contract in program.contracts:
            c = contract.model_dump()
            c["program_slug"] = program.slug
            c["program_name"] = program.name
            all_contracts.append(c)

    if chain:
        chain_lower = chain.lower()
        all_contracts = [c for c in all_contracts if c.get("chain", "").lower() == chain_lower]

    total = len(all_contracts)
    paginated = all_contracts[offset:offset + limit]

    return ok({
        "total": total,
        "offset": offset,
        "limit": limit,
        "contracts": paginated,
    })


@router.get("/contracts/scope")
async def list_scope_contracts(
    chain: str | None = Query(None, description="Filter by blockchain"),
    min_bounty: float = Query(0, ge=0, description="Min program bounty in USD"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> ApiResponse:
    """List ONLY in-scope smart contracts ready for audit scanning.

    Filter:
    - Hanya contracts dengan valid 0x address (42 chars)
    - Hanya dari program active
    - Filter chain (opsional)
    - Filter minimum bounty (opsional)
    - Kelompokan per program untuk konteks audit
    """
    scope_contracts = []

    for program in sync_manager.programs.values():
        # Skip program non-active
        if program.status.lower() not in ("active", "live"):
            continue

        # Skip program below min bounty
        if min_bounty > 0 and (program.max_bounty or 0) < min_bounty:
            continue

        for contract in program.contracts:
            # Validasi: hanya address Ethereum valid
            addr = contract.address.strip()
            if not addr.startswith("0x") or len(addr) != 42:
                continue

            # Filter chain (opsional)
            if chain:
                chain_lower = chain.lower()
                contract_chain = (contract.chain or "").lower()
                program_chains = [c.lower() for c in program.chains]
                if contract_chain != chain_lower and chain_lower not in program_chains:
                    continue

            c = contract.model_dump()
            c["program_slug"] = program.slug
            c["program_name"] = program.name
            c["program_max_bounty"] = program.max_bounty
            c["program_status"] = program.status
            scope_contracts.append(c)

    total = len(scope_contracts)
    paginated = scope_contracts[offset:offset + limit]

    # Group by chain untuk statistik
    by_chain: dict[str, int] = {}
    for c in scope_contracts:
        ch = c.get("chain") or "unknown"
        by_chain[ch] = by_chain.get(ch, 0) + 1

    return ok({
        "total": total,
        "offset": offset,
        "limit": limit,
        "contracts": paginated,
        "stats": {
            "total_scope_contracts": total,
            "unique_programs": len(set(c["program_slug"] for c in scope_contracts)),
            "by_chain": by_chain,
        },
    })


@router.get("/chains")
async def list_chains() -> ApiResponse:
    """List all unique blockchains across synced programs."""
    chains: dict[str, int] = {}
    for program in sync_manager.programs.values():
        for chain in program.chains:
            c = chain or "unknown"
            chains[c] = chains.get(c, 0) + 1

    sorted_chains = sorted(chains.items(), key=lambda x: -x[1])
    return ok({
        "total": len(sorted_chains),
        "chains": [
            {"name": name, "program_count": count}
            for name, count in sorted_chains
        ],
    })


# ── Contract Fetch + Scan Endpoints ───────────────────────

@router.get("/contracts/fetch/stats")
async def get_contract_fetch_stats() -> ApiResponse:
    """Get contract fetch cache statistics."""
    stats = sync_manager.get_contract_fetch_stats()
    return ok(stats)


@router.post("/contracts/fetch")
async def fetch_all_contracts(
    max_programs: int = Query(50, ge=1, le=200),
    trigger_scan: bool = Query(True, description="Trigger orchestrator scan after fetch"),
) -> ApiResponse:
    """Fetch contract source code from Service 03 for all programs.

    Optionally triggers orchestrator scan pipeline.
    """
    results = await sync_manager.fetch_contracts(
        max_programs=max_programs,
        trigger_scan=trigger_scan,
    )
    return ok(results)


@router.post("/programs/{slug}/contracts/fetch")
async def fetch_program_contracts(
    slug: str,
    trigger_scan: bool = Query(True),
) -> ApiResponse:
    """Fetch contract source for a specific program + trigger scan."""
    prog = sync_manager.programs.get(slug)
    if not prog:
        raise HTTPException(status_code=404, detail=f"Program '{slug}' not found")

    results = await sync_manager.fetch_program_contracts(
        slug=slug,
        trigger_scan=trigger_scan,
    )
    return ok({
        "slug": slug,
        "name": prog.name,
        "contracts_count": len(prog.contracts),
        "results": results,
    })
