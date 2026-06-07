"""Health check routes."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Query

from src.models import ApiResponse, HealthData
from src.state import (
    CONFIG_URL,
    ORCHESTRATOR_URL,
    SERVICE_NAME,
    SERVICE_VERSION,
    SOURCE_URL,
    STORAGE_ENGINE,
    get_sqlite_health,
    ok,
    sync_manager,
)

router = APIRouter()


@router.get("/health/dependencies")
async def health_dependencies() -> ApiResponse:
    """Check reachability of dependent services.

    Pings Orchestrator, Source, dan Config untuk memastikan
    seluruh pipeline reachable.
    """
    results: dict[str, Any] = {}

    async def _check(name: str, url: str, path: str = "/health") -> dict:
        """Ping a service and return status."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{url}{path}")
                return {
                    "reachable": resp.status_code < 500,
                    "status_code": resp.status_code,
                    "error": None,
                }
        except httpx.ConnectError:
            return {"reachable": False, "status_code": None, "error": "connection_refused"}
        except httpx.TimeoutException:
            return {"reachable": False, "status_code": None, "error": "timeout"}
        except Exception as e:
            return {"reachable": False, "status_code": None, "error": str(e)[:100]}

    results["orchestrator"] = await _check("orchestrator", ORCHESTRATOR_URL)
    results["source"] = await _check("source", SOURCE_URL)
    results["config"] = await _check("config", CONFIG_URL)

    all_reachable = all(r["reachable"] for r in results.values())
    reachable_count = sum(1 for r in results.values() if r["reachable"])

    return ok({
        "service": SERVICE_NAME,
        "all_reachable": all_reachable,
        "reachable_count": reachable_count,
        "total_dependencies": len(results),
        "dependencies": results,
    })


@router.get("/health")
async def health() -> ApiResponse:
    """Health check endpoint."""
    meta = sync_manager.storage.read_meta()
    return ok(
        HealthData(
            status="ok",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
            programs_cached=len(sync_manager.programs),
            last_synced=sync_manager.last_synced,
            schema_version=meta.get("schema_version"),
            storage_engine=STORAGE_ENGINE,
            sqlite_health=get_sqlite_health(),
        )
    )
