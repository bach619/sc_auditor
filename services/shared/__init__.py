"""Vyper shared utilities — metrics, observability, trace_id.

Usage:
    from shared.metrics import register_metrics_endpoint, MetricsMiddleware
    from shared.observability import setup_observability
"""

from __future__ import annotations

from .metrics import MetricsMiddleware, register_metrics_endpoint
from .observability import setup_observability

__all__ = [
    "MetricsMiddleware",
    "register_metrics_endpoint",
    "setup_observability",
]
