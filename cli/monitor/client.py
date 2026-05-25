"""HTTP client for Vyper Monitor — polls all services for health, stats, and events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from cli.config import get_config


class MonitorClient:
    """Polls all 19 Vyper services for health, stats, and audit events."""

    def __init__(self) -> None:
        self.cfg = get_config()
        self.http = httpx.AsyncClient(timeout=10.0, verify=not self.cfg.get("insecure", False))
        self._prev_audits: dict[str, str] = {}
        self._event_buffer: list[dict] = []

    async def close(self) -> None:
        await self.http.aclose()

    async def check_service_health(self, base_url: str, name: str = "") -> dict:
        """Check a single service's health."""
        try:
            resp = await self.http.get(f"{base_url}/health", timeout=5.0)
            data = resp.json() if resp.status_code == 200 else {}
            return {"name": name or base_url, "status": "healthy" if resp.status_code == 200 else "unhealthy", "data": data}
        except Exception:
            return {"name": name or base_url, "status": "unhealthy", "data": {}}

    async def health_all(self) -> list[dict]:
        """Check health of all 19 Vyper services in parallel.

        Uses config URLs where available, falls back to localhost:port.
        Returns a list of dicts with keys: name, status, data.
        """
        cfg = self.cfg
        all_services: list[tuple[str, str]] = [
            ("orchestrator",      cfg.get("orchestrator_url") or "http://localhost:8009"),
            ("scanner",           cfg.get("scanner_url") or "http://localhost:8003"),
            ("exploit",           cfg.get("exploit_url") or "http://localhost:8006"),
            ("reporter",          cfg.get("reporter_url") or "http://localhost:8007"),
            ("notifier",          cfg.get("notifier_url") or "http://localhost:8008"),
            ("source",            cfg.get("source_url") or "http://localhost:8002"),
            ("immunefi",          cfg.get("immunefi_url") or "http://localhost:8001"),
            ("01-config",         "http://localhost:8011"),
            ("04a-scanner-slither", "http://localhost:8014"),
            ("04b-scanner-echidna", "http://localhost:8015"),
            ("04c-scanner-forge", "http://localhost:8016"),
            ("04d-scanner-halmos", "http://localhost:8017"),
            ("05-scanner-mythril", "http://localhost:8013"),
            ("06-ai",             "http://localhost:8004"),
            ("07-classifier",     "http://localhost:8005"),
            ("12-webhook",        "http://localhost:8010"),
            ("13-upkeep",         "http://localhost:8012"),
            ("14-agent",          "http://localhost:8021"),
            ("16-submission",     "http://localhost:8018"),
        ]
        import asyncio
        tasks = [self.check_service_health(url, name) for name, url in all_services]
        return await asyncio.gather(*tasks)

    async def get_audits(self, limit: int = 20) -> list[dict]:
        """GET orchestrator audits, return list of audit dicts."""
        try:
            url = f"{self.cfg.get('orchestrator_url')}/audits"
            params: dict[str, Any] = {"limit": limit}
            resp = await self.http.get(url, params=params, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    return data.get("data", data.get("audits", []))
                return data if isinstance(data, list) else []
        except Exception:
            pass
        return []

    async def get_events(self) -> list[dict]:
        """Generate events from audit state changes.

        First poll returns current audits as snapshot events.
        Subsequent polls detect state transitions and emit events.
        Returns the last 50 events from rolling buffer (max 200).
        """
        audits = await self.get_audits(limit=20)
        now = datetime.now()  # local time — matches PC clock
        new_events: list[dict] = []
        current_states: dict[str, str] = {}

        for audit in audits:
            aid = audit.get("audit_id", "")
            state = audit.get("state", "UNKNOWN")
            current_states[aid] = state

            if aid not in self._prev_audits:
                level = "INFO"
                icon = "🟢"
                if "FAIL" in state or "TIMEOUT" in state:
                    level = "ERROR"
                    icon = "❌"
                new_events.append({
                    "time": now,
                    "level": level,
                    "icon": icon,
                    "message": f"Pipeline #{aid[:8]} started — {state}",
                    "audit_id": aid,
                })
            elif self._prev_audits.get(aid) != state:
                prev = self._prev_audits[aid]
                if "FAIL" in state or "TIMEOUT" in state:
                    level, icon = "ERROR", "❌"
                elif state in ("COMPLETED", "NOTIFYING"):
                    level, icon = "SUCCESS", "✅"
                else:
                    level, icon = "INFO", "🟢"
                new_events.append({
                    "time": now,
                    "level": level,
                    "icon": icon,
                    "message": f"Pipeline #{aid[:8]} {prev} → {state}",
                    "audit_id": aid,
                })

        self._prev_audits = current_states

        if not new_events:
            for audit in audits[:5]:
                aid = audit.get("audit_id", "")
                state = audit.get("state", "")
                steps = audit.get("steps", [])
                suffix = ""
                if steps:
                    last = steps[-1]
                    suffix = f" — {last.get('name', '')}: {last.get('state', '')}"
                level = "ERROR" if "FAIL" in state or "TIMEOUT" in state else "SUCCESS" if state == "COMPLETED" else "INFO"
                icon = {"SUCCESS": "✅", "INFO": "🟢", "WARNING": "🟡", "ERROR": "❌", "CRITICAL": "⚡"}.get(level, "▪")
                new_events.append({
                    "time": now,
                    "level": level,
                    "icon": icon,
                    "message": f"Pipeline #{aid[:8]} [{state}]{suffix}",
                    "audit_id": aid,
                })

        self._event_buffer.extend(new_events)
        if len(self._event_buffer) > 200:
            self._event_buffer = self._event_buffer[-200:]

        return self._event_buffer[-50:]

    async def get_circuit_breakers(self) -> dict[str, Any] | None:
        """GET Antonio's circuit breaker statuses."""
        try:
            base = self.cfg.get("agent_url") or "http://localhost:8021"
            resp = await self.http.get(f"{base}/circuit-breakers", timeout=5.0)
            if resp.status_code == 200:
                body = resp.json()
                return body.get("data", body) if isinstance(body, dict) else None
        except Exception:
            pass
        return None

    async def get_agent_status(self) -> dict | None:
        """GET Antonio agent health + manifest data."""
        try:
            base = self.cfg.get("agent_url") or "http://localhost:8021"
            health = await self.check_service_health(base, "14-agent")

            sessions_data: list[dict] = []
            try:
                r = await self.http.get(f"{base}/agent/sessions?limit=20", timeout=5.0)
                if r.status_code == 200:
                    sess = r.json()
                    if isinstance(sess, dict):
                        sessions_data = (sess.get("data") or {}).get("sessions", [])
            except Exception:
                pass

            daemon_data: dict = {}
            try:
                r = await self.http.get(f"{base}/daemon/status", timeout=5.0)
                if r.status_code == 200:
                    d_body = r.json()
                    daemon_data = d_body.get("data", d_body) if isinstance(d_body, dict) else {}
            except Exception:
                pass

            memory_data: dict = {}
            try:
                r = await self.http.get(f"{base}/memory/stats", timeout=5.0)
                if r.status_code == 200:
                    m_body = r.json()
                    memory_data = m_body.get("data", m_body) if isinstance(m_body, dict) else {}
            except Exception:
                pass

            return {
                "health": health,
                "sessions": sessions_data,
                "daemon": daemon_data,
                "memory": memory_data,
            }
        except Exception:
            return None

    async def get_queue_size(self) -> int:
        """GET /queue to get queue size."""
        try:
            url = f"{self.cfg.get('orchestrator_url')}/queue"
            resp = await self.http.get(url, params={"limit": 1}, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and "data" in data:
                    items = data["data"]
                    return len(items) if isinstance(items, list) else 0
            return 0
        except Exception:
            return 0
