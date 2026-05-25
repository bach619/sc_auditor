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
    "register_metrics_endpoint",
    "setup_observability",
]


def __getattr__(name: str):
    """Lazy-load sub-modules only when explicitly accessed."""
    if name == "setup_observability":
        from .observability import setup_observability as _so

        return _so
    if name in ("MetricsMiddleware", "register_metrics_endpoint"):
        from .metrics import MetricsMiddleware as _mm, register_metrics_endpoint as _rme

        return _mm if name == "MetricsMiddleware" else _rme
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
