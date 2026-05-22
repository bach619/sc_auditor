"""Vyper Config Service — FastAPI microservice for managing service configuration.

All configuration is stored as a single JSON file at ``/data/config/config.json``.
This service exposes a REST API that other Vyper services use to retrieve and
update shared configuration at runtime.
"""

from __future__ import annotations

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from typing import Any

from shared.observability import setup_observability
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.manager import ConfigManager
from src.models import BulkConfig, ConfigResponse, ConfigValue, ErrorResponse, HealthResponse

# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------
manager: ConfigManager | None = None


class AppState:
    """Shared application state injected via ``request.app.state``."""

    def __init__(self) -> None:
        self.manager: ConfigManager = ConfigManager()
        self._shutdown_requested: bool = False

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def request_shutdown(self) -> None:
        self._shutdown_requested = True


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Handle startup and shutdown lifecycle."""
    global manager

    # ---- startup ----
    state = AppState()
    app.state.vyper = state
    manager = state.manager

    # Load config (creates defaults if missing)
    try:
        cfg = state.manager.load()
        log.info("config_service_started", keys=len(cfg), version="0.1.0")
    except PermissionError:
        log.warning("config_service_permission_denied", data_dir="/data/config")
        log.info("config_service_started_with_defaults", version="0.1.0")

    # Register signal handlers for graceful shutdown within Docker/K8s.
    loop = None
    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):

            def _handler(sig: int, frame: Any = None) -> None:
                log.info("received_signal", signal=sig)
                state.request_shutdown()

            loop.add_signal_handler(sig, _handler, sig)
    except NotImplementedError:
        # Windows does not support add_signal_handler on the event loop.
        log.info("signal_handlers_not_available_on_windows")

    yield  # ---- application runs here ----

    # ---- shutdown ----
    log.info("config_service_shutting_down")
    # Flush any pending state (config is already persisted on every write).
    log.info("config_service_stopped")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Vyper Config Service",
    description="Centralized configuration store for the Vyper microservice ecosystem.",
    version="0.1.0",
    lifespan=lifespan,
)

# -- Middleware --------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)



log = setup_observability(app, "01-config", "0.1.0")

# -- Exception handlers -----------------------------------------------------
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions — return a Vyper error envelope."""
    log.exception("unhandled_exception", path=str(request.url))
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            meta=Meta(status="error")
        ).model_dump(),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint.

    Returns a simple status payload indicating the service is alive.
    """
    return HealthResponse()


# -- Config CRUD ------------------------------------------------------------


# -- Config CRUD ------------------------------------------------------------
# IMPORTANT: Specific static routes (bulk, reset) MUST be registered BEFORE
# the parameterized {key:path} routes, otherwise the greedy :path converter
# will capture "bulk" and "reset" as path parameters.


@app.get("/config/", response_model=ConfigResponse)
async def list_config_keys(request: Request) -> ConfigResponse:
    """Retrieve all configuration keys and their values."""
    mgr: ConfigManager = request.app.state.vyper.manager
    return ConfigResponse(data=mgr.get_all())


@app.put("/config/bulk", response_model=ConfigResponse)
async def bulk_upsert_config(
    request: Request, body: BulkConfig
) -> ConfigResponse:
    """Atomically upsert multiple configuration keys at once."""
    mgr: ConfigManager = request.app.state.vyper.manager
    for k, v in body.config.items():
        mgr.set(k, v)
    log.info("config_bulk_upserted", keys=len(body.config))
    return ConfigResponse(data={"updated": len(body.config)})


@app.post("/config/reset", response_model=ConfigResponse)
async def reset_config(request: Request) -> ConfigResponse:
    """Restore all configuration values to their factory defaults."""
    mgr: ConfigManager = request.app.state.vyper.manager
    defaults = mgr.reset()
    log.info("config_reset")
    return ConfigResponse(data=defaults)


@app.get("/config/{key:path}", response_model=ConfigResponse)
async def get_config_value(request: Request, key: str) -> ConfigResponse:
    """Retrieve a single configuration value by key.

    Returns ``404`` if the key does not exist.
    """
    mgr: ConfigManager = request.app.state.vyper.manager
    value = mgr.get(key)
    if value is None and key not in mgr.get_all():
        raise HTTPException(status_code=404, detail=f"Config key '{key}' not found")
    return ConfigResponse(data={key: value})


@app.put("/config/{key:path}", response_model=ConfigResponse)
async def upsert_config_value(
    request: Request, key: str, body: ConfigValue
) -> ConfigResponse:
    """Create or update a single configuration key.

    If the key already exists, its value is overwritten.
    """
    mgr: ConfigManager = request.app.state.vyper.manager
    mgr.set(key, body.value)
    log.info("config_key_upserted", key=key)
    return ConfigResponse(data={key: body.value})


@app.delete("/config/{key:path}", response_model=ConfigResponse)
async def delete_config_value(request: Request, key: str) -> ConfigResponse:
    """Delete a configuration key.

    Returns ``404`` if the key does not exist.
    """
    mgr: ConfigManager = request.app.state.vyper.manager
    deleted = mgr.delete(key)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Config key '{key}' not found")
    log.info("config_key_deleted", key=key)
    return ConfigResponse(data={"deleted": key})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8011,
        log_level="info",
        reload=False,
    )
