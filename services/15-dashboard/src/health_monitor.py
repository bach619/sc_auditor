"""Health monitor — periodically checks all 20 services and aggregates status.

Endpoints consumed by the dashboard router:
  GET /api/health/graph     → Dependency graph + status per service
  GET /api/health/metrics   → Aggregated metrics across all services

Usage:
    from src.health_monitor import HealthMonitor

    monitor = HealthMonitor(check_interval=30.0)
    await monitor.start()   # begins background polling
    graph = monitor.get_graph()
    metrics = monitor.get_metrics()
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("vyper.health_monitor")


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class ServiceInfo:
    """Describes a single backend service to monitor."""

    name: str
    url: str
    depends_on: list[str] = field(default_factory=list)


@dataclass
class HealthResult:
    """Result of a single health check."""

    status: str  # "healthy" | "degraded" | "down" | "unknown"
    code: int = 0
    error: str = ""
    latency_ms: float = 0.0
    timestamp: str = ""


# ── Service registry ─────────────────────────────────────────────────────────

SERVICES: list[ServiceInfo] = [
    ServiceInfo("01-config",        "http://01-config:8000",       []),
    ServiceInfo("02-immunefi",      "http://02-immunefi:8001",     ["01-config"]),
    ServiceInfo("03-source",        "http://03-source:8000",       ["01-config"]),
    ServiceInfo("04-scanner",       "http://04-scanner:8000",      ["01-config"]),
    ServiceInfo("04a-scanner-slither", "http://04a-scanner-slither:8000", ["01-config"]),
    ServiceInfo("04b-scanner-echidna", "http://04b-scanner-echidna:8000", ["01-config"]),
    ServiceInfo("04c-scanner-forge", "http://04c-scanner-forge:8000",   ["01-config"]),
    ServiceInfo("04d-scanner-halmos", "http://04d-scanner-halmos:8000", ["01-config"]),
    ServiceInfo("05-scanner-mythril", "http://05-scanner-mythril:8000", ["01-config"]),
    ServiceInfo("06-ai",            "http://06-ai:8004",           ["01-config"]),
    ServiceInfo("07-classifier",    "http://07-classifier:8005",   ["06-ai", "01-config"]),
    ServiceInfo("08-exploit",       "http://08-exploit:8006",      ["07-classifier", "01-config"]),
    ServiceInfo("09-reporter",      "http://09-reporter:8007",     ["08-exploit", "01-config"]),
    ServiceInfo("10-notifier",      "http://10-notifier:8008",     ["09-reporter", "01-config"]),
    ServiceInfo("11-orchestrator",  "http://11-orchestrator:8000", ["02-immunefi", "03-source", "04-scanner", "06-ai", "07-classifier", "08-exploit", "09-reporter", "10-notifier", "01-config"]),
    ServiceInfo("12-webhook",       "http://12-webhook:8000",      ["01-config"]),
    ServiceInfo("13-upkeep",        "http://13-upkeep:8000",       ["01-config"]),
    ServiceInfo("14-agent",         "http://14-agent:8014",        ["01-config"]),
    ServiceInfo("15-dashboard",     "http://localhost:8000",       ["11-orchestrator", "01-config"]),
    ServiceInfo("16-submission",    "http://16-submission:8000",   ["01-config"]),
]

# Build a lookup for dependency graph
SERVICE_MAP: dict[str, ServiceInfo] = {s.name: s for s in SERVICES}


# ── HealthMonitor ────────────────────────────────────────────────────────────


class HealthMonitor:
    """Periodically checks all backend services and caches results.

    Attributes:
        check_interval: Seconds between background polls (default 30).
        results: Cached {service_name: HealthResult} from last poll.
        graph: Pre-computed dependency graph with status colours.
    """

    def __init__(self, check_interval: float = 30.0) -> None:
        self.check_interval = check_interval
        self.results: dict[str, HealthResult] = {}
        self.graph: dict[str, Any] = {"nodes": {}, "edges": []}
        self._task: asyncio.Task[None] | None = None
        self._client: httpx.AsyncClient | None = None

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start background polling."""
        self._client = httpx.AsyncClient(timeout=5.0)
        # Run an immediate check, then poll on interval
        await self._poll()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop background polling."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _run(self) -> None:
        """Background loop: poll → sleep → repeat."""
        try:
            while True:
                await asyncio.sleep(self.check_interval)
                await self._poll()
        except asyncio.CancelledError:
            pass

    # ── Core health check ────────────────────────────────────────────────

    async def _poll(self) -> None:
        """Check all services in parallel and update cached results + graph."""
        if self._client is None:
            return

        tasks = {s.name: self._check_one(s) for s in SERVICES}
        raw = await asyncio.gather(*tasks.values(), return_exceptions=True)

        self.results = {}
        for name, result in zip(tasks, raw):
            if isinstance(result, HealthResult):
                self.results[name] = result
            else:
                self.results[name] = HealthResult(
                    status="error",
                    error=str(result),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

        self._rebuild_graph()

    async def _check_one(self, svc: ServiceInfo) -> HealthResult:
        """Check a single service's /health endpoint."""
        start = time.monotonic()
        try:
            if self._client is None:
                return HealthResult(status="error", error="no client")
            resp = await self._client.get(f"{svc.url}/health")
            latency = (time.monotonic() - start) * 1000
            ts = datetime.now(timezone.utc).isoformat()

            if resp.status_code == 200:
                return HealthResult(status="healthy", code=200,
                                    latency_ms=round(latency, 2), timestamp=ts)
            if resp.status_code < 500:
                return HealthResult(status="degraded", code=resp.status_code,
                                    latency_ms=round(latency, 2), timestamp=ts)
            return HealthResult(status="down", code=resp.status_code,
                                latency_ms=round(latency, 2), timestamp=ts)
        except httpx.TimeoutException:
            return HealthResult(status="down", error="timeout",
                                timestamp=datetime.now(timezone.utc).isoformat())
        except httpx.ConnectionError:
            return HealthResult(status="down", error="connection refused",
                                timestamp=datetime.now(timezone.utc).isoformat())
        except Exception as exc:
            return HealthResult(status="down", error=str(exc),
                                timestamp=datetime.now(timezone.utc).isoformat())

    # ── Graph builder ────────────────────────────────────────────────────

    def _rebuild_graph(self) -> None:
        """Rebuild the dependency graph from cached health results.

        Node status colours:
          - 🟢 healthy   (CPU < 70%, memory < 80%, latency < 500ms)
          - 🟡 degraded  (service responds but not 200)
          - 🔴 down      (no response / error)
          - ⚪ unknown   (no data yet)
        """
        nodes: dict[str, Any] = {}
        edges: list[dict[str, str]] = []

        for svc in SERVICES:
            result = self.results.get(svc.name)
            if result is None:
                status = "unknown"
                colour = "grey"
            elif result.status == "healthy":
                if result.latency_ms < 500:
                    status = "healthy"
                    colour = "green"
                else:
                    status = "degraded"
                    colour = "yellow"
            elif result.status == "degraded":
                status = "degraded"
                colour = "yellow"
            else:
                status = "down"
                colour = "red"

            nodes[svc.name] = {
                "name": svc.name,
                "status": status,
                "colour": colour,
                "latency_ms": result.latency_ms if result else 0.0,
                "error": result.error if result and result.error else "",
                "timestamp": result.timestamp if result else "",
            }

            for dep in svc.depends_on:
                edges.append({"from": dep, "to": svc.name})

        self.graph = {"nodes": nodes, "edges": edges}

    # ── Public accessors ────────────────────────────────────────────────

    def get_graph(self) -> dict[str, Any]:
        """Return the dependency graph with current status."""
        return self.graph

    def get_metrics(self) -> dict[str, Any]:
        """Return aggregated metrics across all services.

        Returns:
            dict with keys: total_services, healthy, degraded, down,
            unknown, avg_latency_ms, p95_latency_ms, error_rate, timestamp
        """
        total = len(SERVICES)
        healthy = sum(1 for r in self.results.values() if r.status == "healthy")
        degraded = sum(1 for r in self.results.values() if r.status == "degraded")
        down = sum(1 for r in self.results.values() if r.status == "down")
        unknown = total - len(self.results)

        latencies = [r.latency_ms for r in self.results.values() if r.latency_ms > 0]
        avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
        sorted_lat = sorted(latencies)
        p95 = sorted_lat[int(len(sorted_lat) * 0.95)] if sorted_lat else 0.0

        return {
            "total_services": total,
            "healthy": healthy,
            "degraded": degraded,
            "down": down,
            "unknown": unknown,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": round(p95, 2),
            "error_rate": round(down / total * 100, 2) if total > 0 else 0.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
