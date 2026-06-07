from __future__ import annotations

from typing import Any

import app
from app import _err
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from src.models import ApiResponse

router = APIRouter()


@router.post("/audit", status_code=201)
async def gateway_start_audit(body: dict[str, Any], request: Request) -> JSONResponse:
    """Start an audit — gatewayed through Antonio.
    
    Accepts the same payload as Orchestrator's /audit endpoint:
    { chain, address, program, priority, metadata }.
    
    Antonio logs the request, delegates to Orchestrator,
    and returns the result with an Antonio processing header.
    """
    chain = body.get("chain", "ethereum")
    address = body.get("address", "")
    program = body.get("program", "")
    priority = body.get("priority", 5)
    use_ai = body.get("use_ai", True)
    metadata = body.get("metadata", {})

    if not address.startswith("0x"):
        raise _err("Address must be 0x-prefixed")

    app.log.info(
        "antonio.gateway.audit_requested",
        chain=chain,
        address=address,
        program=program,
        priority=priority,
    )

    orchestrator_payload = {
        "chain": chain,
        "address": address,
        "program": program,
        "priority": priority,
        "use_ai": use_ai,
        "metadata": metadata,
    }

    try:
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{app.ORCHESTRATOR_URL}/audit",
                json=orchestrator_payload,
            )
            resp.raise_for_status()
            result = resp.json()
    except httpx.RequestError as exc:
        app.log.error("antonio.gateway.orchestrator_unreachable", error=str(exc))
        raise _err(f"Orchestrator unreachable: {exc}", 502)
    except Exception as exc:
        app.log.error("antonio.gateway.audit_failed", error=str(exc))
        raise _err(f"Audit failed: {exc}", 500)

    # Add Antonio gateway mark
    if isinstance(result, dict) and "meta" in result:
        result["meta"]["gateway"] = "antonio"

    return JSONResponse(
        content=result,
        status_code=201,
        headers={"X-Antonio-Gateway": "true"},
    )


@router.post("/orchestrator/daemon/start")
async def gateway_daemon_start() -> JSONResponse:
    """Start the Orchestrator daemon via Antonio gateway."""
    app.log.info("antonio.gateway.daemon_start")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{app.ORCHESTRATOR_URL}/daemon/start")
            resp.raise_for_status()
            return JSONResponse(content=resp.json())
    except Exception as exc:
        raise _err(f"Daemon start failed: {exc}", 502)


@router.post("/orchestrator/daemon/stop")
async def gateway_daemon_stop() -> JSONResponse:
    """Stop the Orchestrator daemon via Antonio gateway."""
    app.log.info("antonio.gateway.daemon_stop")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{app.ORCHESTRATOR_URL}/daemon/stop")
            resp.raise_for_status()
            return JSONResponse(content=resp.json())
    except Exception as exc:
        raise _err(f"Daemon stop failed: {exc}", 502)


@router.get("/orchestrator/daemon/status")
async def gateway_daemon_status() -> JSONResponse:
    """Get Orchestrator daemon status via Antonio gateway."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{app.ORCHESTRATOR_URL}/daemon/status")
            resp.raise_for_status()
            return JSONResponse(content=resp.json())
    except Exception as exc:
        raise _err(f"Daemon status failed: {exc}", 502)
