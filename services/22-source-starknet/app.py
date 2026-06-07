"""Vyper StarkNet Source Service — FastAPI microservice for Cairo source intelligence.

Fetches Cairo smart contract source code from StarkNet explorers.
Port: 8025 | Version: 0.1.0
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from shared.observability import setup_observability
from shared.api_errors import register_error_handlers
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from src.fetcher import StarkNetSourceFetcher
from src.storage import StarkNetSourceStorage
from src.models import ApiResponse, FetchRequest, HealthData, Meta

SERVICE_NAME = "22-source-starknet"
SERVICE_VERSION = "0.1.0"

fetcher = StarkNetSourceFetcher()
storage = StarkNetSourceStorage()
_results: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    log.info("starknet_source.startup", service=SERVICE_NAME, version=SERVICE_VERSION)
    from shared.storage import init_sqlite_store; init_sqlite_store("/data/source-starknet")
    yield
    await fetcher.close()
    log.info("starknet_source.shutdown", service=SERVICE_NAME)


app = FastAPI(
    title="Vyper StarkNet Source Service",
    description="Fetches Cairo smart contract source code from StarkNet explorers.",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

log = setup_observability(app, "22-source-starknet", "0.1.0")


def ok(data: object = None) -> ApiResponse:
    return ApiResponse(data=data, meta=Meta(status="ok"))


def err(detail: str, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


@app.get("/health")
async def health() -> ApiResponse:
    return ok(
        HealthData(
            status="ok",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
            sources_cached=0,
        )
    )


@app.post("/fetch")
async def fetch_source(body: FetchRequest) -> ApiResponse:
    if not body.chain:
        raise err("chain is required")
    if not body.address or not body.address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    log.info("starknet.fetch_requested", chain=body.chain, address=body.address)

    result = await fetcher.fetch(body.address, body.contract_name)

    if not result.success:
        raise err(
            f"Source for {body.address} not found on any provider. Errors: {result.errors}",
            status_code=404,
        )

    request_id = uuid.uuid4().hex[:12]
    storage.save_source(body.address, result)
    _results[request_id] = {
        "address": body.address,
        "result": result,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    return ok({
        "request_id": request_id,
        "address": body.address,
        "contract_name": result.contract_name,
        "compiler_version": result.compiler_version,
        "file_count": len(result.source_files),
        "has_abi": result.abi is not None,
    })


@app.get("/fetch/{request_id}")
async def get_fetch_result(request_id: str) -> ApiResponse:
    entry = _results.get(request_id)
    if not entry:
        raise err(f"Fetch result {request_id} not found", status_code=404)
    return ok(entry["result"])


@app.get("/source/{address}")
async def get_cached_source(address: str) -> ApiResponse:
    if not address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    result = storage.load_source(address)
    if not result:
        raise err(f"Source for {address} not found in cache", status_code=404)

    return ok(result)
