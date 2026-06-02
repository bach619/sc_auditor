"""AggregateMetricsSkill — aggregate platform metrics."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class AggregateMetricsSkill(BaseSkill):
    """Aggregate platform-wide metrics for monitoring and reporting."""

    @property
    def name(self) -> str:
        return "aggregate_metrics"

    @property
    def description(self) -> str:
        return (
            "Aggregate platform metrics across all services. "
            "Collects scan counts, finding stats, classification accuracy, "
            "webhook delivery rates, and system resource usage."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "time_range": {
                    "type": "string",
                    "enum": ["1h", "24h", "7d", "30d", "all"],
                    "description": "Time range for metric aggregation",
                },
                "include_detailed": {
                    "type": "boolean",
                    "description": "Include per-service breakdown (default: false)",
                },
            },
        }

    @property
    def category(self) -> str:
        return "maintenance"

    async def run(
        self,
        time_range: str = "24h",
        include_detailed: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        from ..metrics import MetricsAggregator

        metrics_mgr = MetricsAggregator()
        metrics = await metrics_mgr.aggregate_all(time_range=time_range)

        result: dict[str, Any] = {
            "skill": "aggregate_metrics",
            "time_range": time_range,
            "aggregated_at": __import__("time").time(),
        }

        if isinstance(metrics, dict):
            result["summary"] = metrics.get("summary", metrics)
            if include_detailed:
                result["detailed"] = metrics.get("detailed", metrics.get("per_service", {}))
        else:
            result["summary"] = {"total": metrics}

        return result
