"""Vyper shared utilities — metrics, observability, trace_id.

Usage:
    from shared.metrics import register_metrics_endpoint, MetricsMiddleware
    from shared.observability import setup_observability

Note:
    Sub-modules (metrics, observability) are lazy-loaded via __getattr__
    so that loading ``shared.agent_protocol`` does NOT trigger importing
    heavy dependencies (fastapi, prometheus_client) at import time.
"""

from __future__ import annotations

__all__ = [
    "MetricsMiddleware",
    "atomic_json_read",
    "atomic_json_write",
    "register_metrics_endpoint",
    "setup_observability",
    "generate_service_token",
    "verify_service_token",
    "auth_middleware_factory",
    "CircuitBreaker",
    "CircuitState",
    "CircuitOpenError",
    "CIRCUITS",
    "RequestIDMiddleware",
    "get_client",
    "close_client",
]


def __getattr__(name: str):
    """Lazy-load sub-modules only when explicitly accessed."""
    if name == "setup_observability":
        from .observability import setup_observability as _so

        return _so
    if name in ("MetricsMiddleware", "register_metrics_endpoint"):
        from .metrics import MetricsMiddleware as _mm, register_metrics_endpoint as _rme

        return _mm if name == "MetricsMiddleware" else _rme
    if name in ("atomic_json_read", "atomic_json_write"):
        from .json_utils import atomic_json_read as _ar, atomic_json_write as _aw

        return _ar if name == "atomic_json_read" else _aw
    if name in ("generate_service_token", "verify_service_token", "auth_middleware_factory"):
        from .auth import generate_service_token as _gst, verify_service_token as _vst, auth_middleware_factory as _amf

        if name == "generate_service_token":
            return _gst
        elif name == "verify_service_token":
            return _vst
        return _amf
    if name in ("CircuitBreaker", "CircuitState", "CircuitOpenError", "CIRCUITS"):
        from .circuit_breaker import CircuitBreaker as _cb, CircuitState as _cs, CircuitOpenError as _coe, CIRCUITS as _circuits

        if name == "CircuitBreaker":
            return _cb
        elif name == "CircuitState":
            return _cs
        elif name == "CircuitOpenError":
            return _coe
        return _circuits
    if name == "RequestIDMiddleware":
        from .middleware import RequestIDMiddleware as _rm

        return _rm
    if name in ("get_client", "close_client"):
        from .http_client import get_client as _gc, close_client as _cc

        return _gc if name == "get_client" else _cc
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
