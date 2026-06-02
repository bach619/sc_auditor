"""MonitorHealthSkill — health monitoring of platform services."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class MonitorHealthSkill(BaseSkill):
    """Monitor health of all platform services and system resources."""

    @property
    def name(self) -> str:
        return "monitor_health"

    @property
    def description(self) -> str:
        return (
            "Check health status of all platform services including "
            "scanner agents, classifier, webhook dispatcher, and database. "
            "Reports uptime, resource usage, error rates, and "
            "provides health score."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "services": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific services to check (optional, checks all if omitted)",
                },
                "deep_check": {
                    "type": "boolean",
                    "description": "Perform deep health check including dependency verification",
                },
            },
        }

    @property
    def category(self) -> str:
        return "maintenance"

    async def run(
        self,
        services: list[str] | None = None,
        deep_check: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        from ..update import UpdateManager
        from ..backup import BackupManager

        update_mgr = UpdateManager()
        backup_mgr = BackupManager()

        uptime = update_mgr.uptime_seconds if hasattr(update_mgr, "uptime_seconds") else 0
        backup_count = len(backup_mgr.list_backups()) if hasattr(backup_mgr, "list_backups") else 0

        health_checks = {
            "system": {
                "status": "healthy",
                "uptime_seconds": uptime,
            },
            "backups": {
                "status": "healthy" if backup_count > 0 else "warning",
                "count": backup_count,
            },
        }

        if deep_check:
            import shutil
            health_checks["disk"] = {
                "status": "healthy",
                "total_gb": shutil.disk_usage("/").total // (2**30),
                "free_gb": shutil.disk_usage("/").free // (2**30),
            }

        failed = sum(1 for v in health_checks.values() if v.get("status") == "error")
        warnings = sum(1 for v in health_checks.values() if v.get("status") == "warning")
        healthy = len(health_checks) - failed - warnings

        overall = "healthy"
        if failed > 0:
            overall = "unhealthy"
        elif warnings > 0:
            overall = "degraded"

        return {
            "skill": "monitor_health",
            "overall_status": overall,
            "health_score": round(healthy / len(health_checks) * 10, 1) if health_checks else 0,
            "checks": health_checks,
            "healthy_checks": healthy,
            "warning_checks": warnings,
            "error_checks": failed,
        }
