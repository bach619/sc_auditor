"""Metrics Aggregator for Vyper Upkeep Service.

Fetches health / metrics data from all Vyper microservices and
aggregates them into a unified view. Stores the aggregated result
on disk for dashboard and reporting consumption.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import structlog

from src.models import AggregatedMetrics, MetricsSummary, ServiceMetrics

log = structlog.get_logger()

# ── Constants ───────────────────────────────────────────────

METRICS_DIR = Path("/data/upkeep/metrics")
AGGREGATED_FILE = METRICS_DIR / "aggregated.json"

# Default service registry: name → health endpoint
# Ports match docker-compose.yml internal mapping (all :8000 internally)
SERVICE_REGISTRY: dict[str, str] = {
    "scanner": "http://04-scanner:8000/health",
    "ai": "http://06-ai:8000/health",
    "classifier": "http://07-classifier:8000/health",
    "exploit": "http://08-exploit:8006/health",
    "reporter": "http://09-reporter:8007/health",
    "notifier": "http://10-notifier:8000/health",
    "orchestrator": "http://11-orchestrator:8000/health",
    "source": "http://03-source:8000/health",
    "immunefi": "http://02-immunefi:8000/health",
    "webhook": "http://12-webhook:8000/health",
    "config": "http://01-config:8000/health",
}

# Endpoints that provide richer metrics beyond /health
METRICS_ENDPOINTS: dict[str, str] = {
    "scanner": "http://04-scanner:8000/health",
    "classifier": "http://07-classifier:8000/health",
    "exploit": "http://08-exploit:8000/health",
}


# ── MetricsAggregator ────────────────────────────────────────


class MetricsAggregator:
    """Aggregates metrics from all Vyper services.

    Responsibilities:
        - Query each service's ``/health`` endpoint concurrently.
        - Extract service-specific metrics where available.
        - Compute summary statistics (success rate, F1, etc.).
        - Persist aggregated metrics to disk as JSON.
        - Provide a cached summary for quick dashboard consumption.
    """

    def __init__(
        self,
        service_registry: dict[str, str] | None = None,
        request_timeout: float = 10.0,
    ) -> None:
        self.service_registry = service_registry or SERVICE_REGISTRY
        self.request_timeout = request_timeout

        METRICS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Main Aggregation ─────────────────────────────────────

    async def aggregate_all(self) -> AggregatedMetrics:
        """Fetch metrics from every registered service concurrently.

        Returns:
            AggregatedMetrics with per-service snapshots + summary.
        """
        services: list[ServiceMetrics] = []
        total = len(self.service_registry)
        available = 0

        async def fetch_service(name: str, url: str) -> ServiceMetrics:
            """Fetch a single service's health/metrics."""
            try:
                async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()

                # Parse Vyper standard response envelope
                health_data = data.get("data", data) if isinstance(data, dict) else {}
                if isinstance(health_data, dict):
                    status = health_data.get("status", "unknown")
                    version = health_data.get("version", "")
                else:
                    status = "ok" if resp.is_success else "error"
                    version = ""

                # Fetch richer metrics if available
                metrics = await self._fetch_metrics(name)

                return ServiceMetrics(
                    service=name,
                    available=True,
                    status=status,
                    version=version,
                    metrics=metrics,
                )

            except httpx.HTTPError as exc:
                log.warning(
                    "metrics.service_unreachable",
                    service=name,
                    error=str(exc),
                )
                return ServiceMetrics(
                    service=name,
                    available=False,
                    status="unreachable",
                    error=str(exc),
                )
            except (json.JSONDecodeError, OSError) as exc:
                log.warning(
                    "metrics.service_bad_response",
                    service=name,
                    error=str(exc),
                )
                return ServiceMetrics(
                    service=name,
                    available=False,
                    status="error",
                    error=str(exc),
                )

        # Fan-out: query all services concurrently
        tasks = [
            fetch_service(name, url)
            for name, url in self.service_registry.items()
        ]

        import asyncio

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, ServiceMetrics):
                services.append(result)
                if result.available:
                    available += 1
            elif isinstance(result, Exception):
                log.error("metrics.fetch_crashed", error=str(result))

        # Compute summary
        summary = self._compute_summary(services)

        aggregated = AggregatedMetrics(
            services=services,
            total_services=total,
            available_services=available,
            summary=summary,
        )

        # Persist to disk
        await self._save_aggregated(aggregated)

        log.info(
            "metrics.aggregated",
            total=total,
            available=available,
        )

        return aggregated

    async def _fetch_metrics(self, service: str) -> dict[str, Any]:
        """Fetch service-specific metrics beyond the basic health check."""
        endpoint = METRICS_ENDPOINTS.get(service)
        if not endpoint:
            return {}

        # Services expose extra detail in /health
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(endpoint)
                resp.raise_for_status()
                data = resp.json()

            health_data = data.get("data", data) if isinstance(data, dict) else {}

            # Extract meaningful metrics per service
            metrics: dict[str, Any] = {}

            if service == "scanner":
                metrics["tools_available"] = health_data.get("tools_available", 0)
                tools = health_data.get("tools_installed", [])
                if isinstance(tools, list):
                    metrics["tools_installed"] = tools
                    metrics["tool_count"] = len(tools)

            elif service == "classifier":
                metrics["tp"] = health_data.get("tp", 0)
                metrics["fp"] = health_data.get("fp", 0)
                metrics["tn"] = health_data.get("tn", 0)
                metrics["fn"] = health_data.get("fn", 0)
                metrics["total_classified"] = (
                    metrics["tp"] + metrics["fp"] + metrics["tn"] + metrics["fn"]
                )

            elif service == "exploit":
                metrics["exploits_attempted"] = health_data.get(
                    "exploits_attempted", 0
                )
                metrics["exploits_successful"] = health_data.get(
                    "exploits_successful", 0
                )

            # Flatten any extra fields into metrics dict
            for key in health_data:
                if isinstance(health_data[key], (str, int, float, bool, list)):
                    if key not in metrics and not key.startswith("_"):
                        metrics[key] = health_data[key]

            return metrics

        except (httpx.HTTPError, json.JSONDecodeError, OSError):
            return {}

    # ── Summary Computation ──────────────────────────────────

    def _compute_summary(
        self, services: list[ServiceMetrics]
    ) -> dict[str, Any]:
        """Compute aggregated summary fields from service metrics."""
        summary: dict[str, Any] = {}

        # ── Scanner ──────────────────────────────────────
        scanner = self._find_service(services, "scanner")
        if scanner and scanner.metrics:
            summary["scanner_tools_used"] = scanner.metrics.get(
                "tools_installed", []
            )

        # ── Classifier ───────────────────────────────────
        classifier = self._find_service(services, "classifier")
        tp = fp = tn = fn = 0
        if classifier and classifier.metrics:
            tp = classifier.metrics.get("tp", 0) or 0
            fp = classifier.metrics.get("fp", 0) or 0
            tn = classifier.metrics.get("tn", 0) or 0
            fn = classifier.metrics.get("fn", 0) or 0

        summary["classifier_tp"] = tp
        summary["classifier_fp"] = fp
        summary["classifier_tn"] = tn
        summary["classifier_fn"] = fn

        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = (
            _safe_div(2 * precision * recall, precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        summary["precision"] = round(precision, 4)
        summary["recall"] = round(recall, 4)
        summary["f1_score"] = round(f1, 4)

        # ── AI ───────────────────────────────────────────
        ai = self._find_service(services, "ai")
        if ai and ai.metrics:
            cache_hits = ai.metrics.get("cache_hits", 0) or 0
            cache_misses = ai.metrics.get("cache_misses", 0) or 0
            total_requests = cache_hits + cache_misses
            hit_rate = _safe_div(cache_hits, total_requests) if total_requests > 0 else 0.0
            summary["ai_cache_hit_rate"] = round(hit_rate, 4)
            summary["ai_analyses"] = ai.metrics.get("analyses_performed", 0) or 0
        else:
            summary["ai_cache_hit_rate"] = 0.0

        # ── Exploit ──────────────────────────────────────
        exploit = self._find_service(services, "exploit")
        if exploit and exploit.metrics:
            attempted = exploit.metrics.get("exploits_attempted", 0) or 0
            successful = exploit.metrics.get("exploits_successful", 0) or 0
            summary["exploits_attempted"] = attempted
            summary["exploits_successful"] = successful
            summary["exploit_success_rate"] = round(
                _safe_div(successful, attempted), 4
            )

        # ── Reporter ─────────────────────────────────────
        reporter = self._find_service(services, "reporter")
        if reporter and reporter.metrics:
            summary["reports_generated"] = reporter.metrics.get(
                "reports_generated", 0
            ) or 0

        # ── Notifier ─────────────────────────────────────
        notifier = self._find_service(services, "notifier")
        if notifier and notifier.metrics:
            summary["notifications_sent"] = notifier.metrics.get(
                "notifications_sent", 0
            ) or 0

        # ── Orchestrator ─────────────────────────────────
        orch = self._find_service(services, "orchestrator")
        if orch and orch.metrics:
            summary["audits_completed"] = orch.metrics.get(
                "audits_completed", 0
            ) or 0
            summary["audits_success_rate"] = orch.metrics.get(
                "success_rate", 0.0
            ) or 0.0
            summary["orchestrator_uptime"] = orch.metrics.get(
                "uptime_seconds", 0
            ) or 0

        # ── Totals ───────────────────────────────────────
        total_audits = (
            summary.get("audits_completed", 0) or 0
        )
        total_findings = summary.get("classifier_tp", 0) + summary.get(
            "classifier_fp", 0
        )
        total_exploits = summary.get("exploits_attempted", 0) or 0
        total_reports = summary.get("reports_generated", 0) or 0
        total_notifications = summary.get("notifications_sent", 0) or 0

        summary["total_audits"] = total_audits
        summary["total_findings"] = total_findings
        summary["total_exploits"] = total_exploits
        summary["total_reports"] = total_reports
        summary["total_notifications"] = total_notifications

        return summary

    # ── Quick Summary ────────────────────────────────────────

    async def get_summary(self) -> MetricsSummary:
        """Return a concise, dashboard-friendly metrics summary.

        Loads the latest aggregated data from disk if available,
        otherwise runs a fresh aggregation.
        """
        # Try loading cached aggregation first
        if AGGREGATED_FILE.exists():
            try:
                data = json.loads(AGGREGATED_FILE.read_text(encoding="utf-8"))
                aggregated = AggregatedMetrics(**data)
            except (json.JSONDecodeError, OSError, TypeError):
                aggregated = await self.aggregate_all()
        else:
            aggregated = await self.aggregate_all()

        summary = aggregated.summary

        return MetricsSummary(
            total_audits=summary.get("total_audits", 0),
            total_findings=summary.get("total_findings", 0),
            total_exploits=summary.get("total_exploits", 0),
            total_reports=summary.get("total_reports", 0),
            total_notifications=summary.get("total_notifications", 0),
            success_rate=summary.get("audits_success_rate", 0.0),
            precision=summary.get("precision", 0.0),
            recall=summary.get("recall", 0.0),
            f1_score=summary.get("f1_score", 0.0),
            ai_cache_hit_rate=summary.get("ai_cache_hit_rate", 0.0),
            scanner_tools_used=summary.get("scanner_tools_used", []),
            uptime_hours=round(
                summary.get("orchestrator_uptime", 0) / 3600, 2
            ),
        )

    # ── Persistence ──────────────────────────────────────────

    async def _save_aggregated(
        self, aggregated: AggregatedMetrics
    ) -> None:
        """Persist aggregated metrics to disk as JSON."""
        try:
            data = aggregated.model_dump(mode="json")
            AGGREGATED_FILE.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            log.error("metrics.save_failed", error=str(exc))

    # ── Helpers ──────────────────────────────────────────────

    @staticmethod
    def _find_service(
        services: list[ServiceMetrics],
        name: str,
    ) -> ServiceMetrics | None:
        """Find a service by name in the list."""
        for svc in services:
            if svc.service == name and svc.available:
                return svc
        return None


# ── Factory ──────────────────────────────────────────────────


def create_metrics_aggregator() -> MetricsAggregator:
    """Create a MetricsAggregator instance."""
    return MetricsAggregator()


# ── Internal Helpers ─────────────────────────────────────────


def _safe_div(a: float | int, b: float | int) -> float:
    """Safely divide a by b, returning 0.0 if b is zero."""
    try:
        return float(a) / float(b) if float(b) != 0 else 0.0
    except (ValueError, TypeError):
        return 0.0
