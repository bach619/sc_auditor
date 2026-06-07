"""Shared HTTPX connection pool for inter-service calls.

Reuses TCP connections across requests to reduce handshake overhead.
Each service that needs an HTTP client should use `get_client()` instead
of creating a new `httpx.AsyncClient()` per request.

Usage:
    from shared.http_client import get_client
    client = await get_client()
    resp = await client.get("http://02-immunefi:8000/programs")
"""

from __future__ import annotations
import httpx

_pool: httpx.AsyncClient | None = None

async def get_client() -> httpx.AsyncClient:
    global _pool
    if _pool is None or _pool.is_closed:
        _pool = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=50,
                keepalive_expiry=30.0,
            ),
        )
    return _pool

async def close_client() -> None:
    global _pool
    if _pool and not _pool.is_closed:
        await _pool.aclose()
        _pool = None
