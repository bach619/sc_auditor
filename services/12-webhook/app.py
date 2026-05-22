"""Vyper Webhook Service — FastAPI entry point.

Delivers signed webhook notifications (HMAC-SHA256) to configured endpoints
(Slack, PagerDuty, custom URLs) when audit events occur.
"""

from __future__ import annotations

import os
import sys
import time as time_module
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from src.dispatcher import WebhookDispatcher, create_dispatcher
from src.models import (
    ApiResponse,
    BatchDeliveryResult,
    DeliveryLogQuery,
    EndpointInfo,
    HealthData,
    Meta,
    WebhookResult,
    WebhookTrigger,
)
from shared.observability import setup_observability

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SERVICE_NAME = "webhook"
SERVICE_VERSION = "0.1.0"

DATA_DIR = Path(os.environ.get("WEBHOOK_DATA_DIR", "/data/webhook"))

# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

_START_TIME: float = time_module.monotonic()


class AppState:
    """Shared application state injected via ``request.app.state.vyper``."""

    def __init__(self) -> None:
        self.dispatcher: WebhookDispatcher = create_dispatcher()

    async def close(self) -> None:
        """Release HTTP client held by the dispatcher."""
        await self.dispatcher.close()


def _get_state(request: Request) -> AppState:
    return request.app.state.vyper  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def ok(data: object = None) -> ApiResponse:
    """Standard Vyper success response."""
    return ApiResponse(data=data, meta=Meta(status="ok"))


def err(detail: str, status_code: int = 400) -> HTTPException:
    """Standard Vyper error response (raised as exception)."""
    return HTTPException(status_code=status_code, detail=detail)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    # ---- startup ----
    state = AppState()
    app.state.vyper = state

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    log.info(
        "webhook.startup",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        data_dir=str(DATA_DIR),
    )

    yield

    # ---- shutdown ----
    await state.close()
    log.info("webhook.shutdown", service=SERVICE_NAME)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Vyper Webhook Service",
    description="Signed webhook delivery for audit events",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

log = setup_observability(app, "12-webhook", "0.1.0")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health(request: Request) -> ApiResponse:
    """Health check — returns service status and basic counters."""
    state = _get_state(request)
    uptime = time_module.monotonic() - _START_TIME

    return ok(
        HealthData(
            status="ok",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
            uptime_seconds=round(uptime, 2),
            delivery_count=state.dispatcher.delivery_count,
            failed_count=state.dispatcher.failed_count,
            configured_endpoints=0,
        )
    )


@app.post("/webhook/trigger")
async def trigger_webhook(
    body: WebhookTrigger,
    request: Request,
) -> ApiResponse:
    """Deliver a signed webhook to one or more target URLs.

    The payload is serialised to JSON, signed with HMAC-SHA256 using the
    provided *secret*, and sent as an HTTP POST to every URL in *urls*.

    Headers attached to each request:

    - ``X-Vyper-Signature: sha256=<hex-digest>``
    - ``X-Vyper-Event: <event>``
    - ``Content-Type: application/json``
    """
    state = _get_state(request)

    log.info(
        "webhook.trigger",
        event=body.event,
        url_count=len(body.urls),
    )

    results = await state.dispatcher.dispatch_batch(
        urls=body.urls,
        payload=body.payload,
        secret=body.secret,
        event=body.event,
    )

    batch = BatchDeliveryResult(
        event=body.event,
        total_urls=len(body.urls),
        succeeded=sum(1 for r in results if r.success),
        failed=sum(1 for r in results if not r.success),
        results=results,
    )

    return ok(batch)


@app.get("/webhook/delivery-log")
async def get_delivery_log(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    event: str | None = None,
    success: bool | None = None,
) -> ApiResponse:
    """Return paginated delivery history from the persisted log file.

    Supports optional filtering by *event* type and *success* status.
    Results are ordered newest-first (reverse-chronological).
    """
    state = _get_state(request)

    raw = state.dispatcher.read_delivery_log(
        limit=limit,
        offset=offset,
        event=event,
        success=success,
    )

    # Reverse so newest entries appear first
    raw.reverse()

    return ok(
        {
            "entries": raw,
            "total": len(state.dispatcher.read_delivery_log()),
            "limit": limit,
            "offset": offset,
        }
    )


@app.get("/webhook/endpoints")
async def list_endpoints(request: Request) -> ApiResponse:
    """List known webhook endpoints (currently derived from delivery log).

    In a production deployment this would be backed by the config service;
    for now we extract unique URLs from the delivery log.
    """
    state = _get_state(request)
    raw = state.dispatcher.read_delivery_log()

    # Deduplicate by URL, keeping the latest entry per URL
    seen: dict[str, dict[str, Any]] = {}
    for entry in raw:
        url: str = entry.get("url", "")
        if not url:
            continue
        ts = entry.get("timestamp", "")
        if url not in seen or ts > seen[url].get("last_delivery_ts", ""):
            seen[url] = {
                "url": url,
                "label": None,
                "events": [entry.get("event")] if entry.get("event") else [],
                "last_delivery_ts": ts,
                "last_delivery_ok": entry.get("success"),
            }

    # Merge events for URLs seen multiple times
    for entry in raw:
        url = entry.get("url", "")
        if url in seen and entry.get("event") and entry["event"] not in seen[url]["events"]:
            seen[url]["events"].append(entry["event"])

    endpoints = [EndpointInfo(**v) for v in seen.values()]

    return ok(
        {
            "endpoints": endpoints,
            "total": len(endpoints),
        }
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False,
    )
