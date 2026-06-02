"""AnalyzeLogsSkill — delivery log analysis."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class AnalyzeLogsSkill(BaseSkill):
    """Analyze webhook delivery logs for success rates, failures, and trends."""

    @property
    def name(self) -> str:
        return "analyze_logs"

    @property
    def description(self) -> str:
        return (
            "Analyze webhook delivery history to compute success rates, "
            "identify failing endpoints, detect error trends, and "
            "provide recommendations for improving delivery reliability."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "log_count": {
                    "type": "integer",
                    "description": "Number of recent log entries to analyze (default 100)",
                },
                "filter_endpoint": {
                    "type": "string",
                    "description": "Filter logs for a specific endpoint URL",
                },
                "filter_event": {
                    "type": "string",
                    "description": "Filter logs for a specific event type",
                },
            },
        }

    @property
    def category(self) -> str:
        return "notifications"

    async def run(
        self,
        log_count: int = 100,
        filter_endpoint: str | None = None,
        filter_event: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        from ..dispatcher import WebhookDispatcher

        dispatcher = WebhookDispatcher()
        logs = dispatcher.read_delivery_log() if hasattr(dispatcher, "read_delivery_log") else []

        recent = logs[-log_count:] if logs else logs
        if filter_endpoint:
            recent = [l for l in recent if filter_endpoint in str(l.get("url", l.get("endpoint", "")))]
        if filter_event:
            recent = [l for l in recent if filter_event in str(l.get("event_type", l.get("event", "")))]

        total = len(recent)
        if total == 0:
            return {
                "skill": "analyze_logs",
                "total_logs_analyzed": 0,
                "message": "No matching logs found",
            }

        successful = sum(1 for l in recent if l.get("success", l.get("status", 500)) in (True, 200, 201, 202, 204))
        failed = total - successful
        success_rate = successful / total if total > 0 else 0

        from collections import Counter
        error_counter: Counter[str] = Counter()
        endpoint_counter: Counter[str] = Counter()
        event_counter: Counter[str] = Counter()

        for log in recent:
            err = log.get("error", log.get("error_message", ""))
            if err:
                error_counter[str(err)[:100]] += 1
            url = log.get("url", log.get("endpoint", "unknown"))
            endpoint_counter[str(url)] += 1
            evt = log.get("event_type", log.get("event", "unknown"))
            event_counter[str(evt)] += 1

        return {
            "skill": "analyze_logs",
            "total_logs_analyzed": total,
            "successful_deliveries": successful,
            "failed_deliveries": failed,
            "success_rate": round(success_rate, 4),
            "top_errors": [{"error": err, "count": cnt} for err, cnt in error_counter.most_common(5)],
            "top_endpoints": [{"url": url, "count": cnt} for url, cnt in endpoint_counter.most_common(10)],
            "top_events": [{"event": evt, "count": cnt} for evt, cnt in event_counter.most_common(10)],
            "health_status": "healthy" if success_rate >= 0.95 else "degraded" if success_rate >= 0.8 else "unhealthy",
        }
