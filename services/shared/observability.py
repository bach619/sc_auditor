"""Observability setup utility untuk Vyper services.

Usage di setiap service app.py:
    from shared.observability import setup_observability

    setup_observability(app, service_name="01-config", service_version="1.0.0")
    
Ini akan:
    1. Register /metrics endpoint (Prometheus)
    2. Add trace_id middleware (X-Trace-ID)
    3. Ensure structlog JSON format
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from typing import Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Gauge, Histogram, generate_latest, REGISTRY
from prometheus_client.exposition import CONTENT_TYPE_LATEST
import structlog


def _setup_structlog(service_name: str) -> None:
    """Configure structlog for JSON output (production) or console (dev)."""
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    if sys.stdout.isatty() and not os.environ.get("FORCE_JSON_LOGS"):
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _make_trace_id_middleware(svc_name: str):
    async def trace_id_middleware(request: Request, call_next: Callable) -> Response:
        trace_id = request.headers.get("X-Trace-ID", uuid.uuid4().hex[:12])
        structlog.contextvars.bind_contextvars(trace_id=trace_id, service=svc_name)
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        structlog.contextvars.unbind_contextvars("trace_id", "service")
        return response
    return trace_id_middleware


def setup_observability(
    app: FastAPI,
    service_name: str = "unknown",
    service_version: str = "1.0.0",
) -> structlog.BoundLogger:
    """Register all observability features on a FastAPI app.

    1. Configures structlog with JSON format
    2. Adds trace_id middleware
    3. Registers /metrics Prometheus endpoint

    Returns:
        Configured structlog logger
    """
    # 1. Structured logging
    _setup_structlog(service_name)
    logger = structlog.get_logger(service=service_name)

    # 2. Trace ID middleware
    app.middleware("http")(_make_trace_id_middleware(service_name))

    # 3. Metrics
    _request_count = Counter(
        "vyper_request_count", "Total requests",
        ["service", "method", "endpoint", "status"],
    )
    _request_duration = Histogram(
        "vyper_request_duration_seconds", "Request latency",
        ["service", "method", "endpoint"],
        buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
    )
    _error_count = Counter(
        "vyper_error_count", "Total errors",
        ["service", "method", "endpoint", "error_type"],
    )
    _service_info = Gauge(
        "vyper_service_info", "Service metadata",
        ["service", "version"],
    )
    _service_info.labels(service_name, service_version).set(1)

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next: Callable) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)
        method = request.method
        path = request.url.path
        start = time.monotonic()
        try:
            response = await call_next(request)
            status = str(response.status_code)
            _request_count.labels(service_name, method, path, status).inc()
            _request_duration.labels(service_name, method, path).observe(
                time.monotonic() - start
            )
            if response.status_code >= 500:
                _error_count.labels(service_name, method, path, "server_error").inc()
            return response
        except Exception as e:
            _request_count.labels(service_name, method, path, "500").inc()
            _error_count.labels(service_name, method, path, type(e).__name__).inc()
            raise

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint() -> Response:
        return Response(
            content=generate_latest(REGISTRY),
            media_type=CONTENT_TYPE_LATEST,
        )

    logger.info("observability.setup_complete",
                service=service_name, version=service_version)
    return logger
