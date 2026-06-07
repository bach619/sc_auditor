"""Vyper API Error Handler — standardized error response format.

Wire into any FastAPI app with::

    from shared.api_errors import register_error_handlers
    app = FastAPI()
    register_error_handlers(app)

Every error response follows the Vyper envelope contract::

    {
        "data": null,
        "meta": {
            "status": "error",
            "error": "<human-readable message>",
            "error_code": "<machine-readable code>",
            "timestamp": "<ISO 8601>"
        }
    }

Supported error types:
    - 400 Bad Request (validation errors)
    - 404 Not Found
    - 405 Method Not Allowed
    - 422 Unprocessable Entity (FastAPI validation)
    - 500 Internal Server Error
    - All unhandled exceptions
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def _error_envelope(
    status_code: int,
    error: str,
    error_code: str = "",
    details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a standard Vyper error envelope."""
    body: dict[str, Any] = {
        "data": None,
        "meta": {
            "status": "error",
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
    if error_code:
        body["meta"]["error_code"] = error_code
    if details:
        body["meta"]["details"] = details
    return body


async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle standard HTTP exceptions (404, 405, etc.)."""
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_envelope(
            status_code=exc.status_code,
            error=str(exc.detail),
            error_code=f"HTTP_{exc.status_code}",
        ),
    )


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle FastAPI validation errors (422)."""
    details = []
    for error in exc.errors():
        details.append({
            "loc": list(error.get("loc", [])),
            "msg": error.get("msg", ""),
            "type": error.get("type", ""),
        })
    return JSONResponse(
        status_code=422,
        content=_error_envelope(
            status_code=422,
            error="Request validation failed",
            error_code="VALIDATION_ERROR",
            details=details,
        ),
    )


async def _generic_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle all unhandled exceptions (500)."""
    return JSONResponse(
        status_code=500,
        content=_error_envelope(
            status_code=500,
            error="Internal server error",
            error_code="INTERNAL_ERROR",
        ),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register standardized error handlers on a FastAPI application.

    Usage::

        from fastapi import FastAPI
        from shared.api_errors import register_error_handlers

        app = FastAPI()
        register_error_handlers(app)
    """
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _generic_exception_handler)
