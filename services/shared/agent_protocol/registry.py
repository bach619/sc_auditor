from __future__ import annotations

import asyncio
import time
from typing import Any
from enum import Enum

from .models import (
    AgentCapability,
    AgentManifest,
    AgentStatus,
    DelegationRequest,
    DelegationResponse,
)


def _to_dict(obj: Any) -> dict:
    """Convert a dataclass to dict recursively."""
    if hasattr(obj, "__dataclass_fields__"):
        result = {}
        for field_name in obj.__dataclass_fields__:
            value = getattr(obj, field_name)
            result[field_name] = _to_dict(value)
        return result
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj


class AgentRegistry:
    """Registry of all backend agents known to Antonio.
    
    Antonio uses this to:
    1. Find agents by capability
    2. Discover agents via HTTP
    3. Delegate tasks to the best agent
    4. Periodically refresh agent status
    """

    def __init__(self, http_client: Any | None = None):
        import httpx as _httpx
        import structlog as _structlog

        self._agents: dict[str, AgentManifest] = {}
        self._last_seen: dict[str, float] = {}
        self._http_client = http_client or _httpx.AsyncClient(
            timeout=_httpx.Timeout(30.0),
            headers={"Content-Type": "application/json"},
        )
        self._refresh_task: asyncio.Task | None = None
        self._logger = _structlog.get_logger(__name__)
        self._known_services: dict[str, str] = {
            "06-ai": "http://06-ai:8000",
            "04-scanner": "http://04-scanner:8003",
            "02-immunefi": "http://02-immunefi:8001",
            "08-exploit": "http://08-exploit:8006",
            "09-reporter": "http://09-reporter:8007",
            "10-notifier": "http://10-notifier:8008",
        }

    async def discover_all(self) -> list[AgentManifest]:
        discovered: list[AgentManifest] = []
        for service_name, base_url in self._known_services.items():
            try:
                response = await self._http_client.get(
                    f"{base_url}/agent/manifest"
                )
                response.raise_for_status()
                body = response.json()
                data = body.get("data", body)
                if isinstance(data, dict):
                    manifest = AgentManifest(**data)
                else:
                    manifest = data
                self._agents[service_name] = manifest
                self._last_seen[service_name] = time.time()
                discovered.append(manifest)
                self._logger.info(
                    "agent_discovered",
                    service_name=service_name,
                    role=getattr(manifest, "agent_role", None),
                )
            except Exception as exc:
                self._logger.warning(
                    "agent_discovery_failed",
                    service_name=service_name,
                    error=str(exc),
                )
                offline = AgentManifest(
                    service_name=service_name,
                    agent_role="unknown",
                    version="0.0.0",
                    capabilities=[],
                    current_load={"active_tasks": 999},
                )
                self._agents[service_name] = offline
                self._last_seen[service_name] = 0.0
        return discovered

    def find_agents_by_capability(
        self, capability: AgentCapability
    ) -> list[tuple[str, AgentManifest]]:
        results: list[tuple[str, AgentManifest]] = []
        for service_name, manifest in self._agents.items():
            if manifest.agent_role == "unknown" and manifest.version == "0.0.0":
                continue
            has_cap = any(
                cap.name == capability.value or cap.name == capability
                for cap in (manifest.capabilities or [])
            )
            if has_cap:
                results.append((service_name, manifest))
        return results

    def get_best_agent(
        self, capability: AgentCapability
    ) -> tuple[str, AgentManifest] | None:
        candidates = self.find_agents_by_capability(capability)
        if not candidates:
            return None
        candidates.sort(
            key=lambda pair: pair[1].current_load.get("active_tasks", 0)
        )
        return candidates[0]

    def get_agent(self, service_name: str) -> AgentManifest | None:
        return self._agents.get(service_name)

    def get_all_agents(self) -> list[AgentManifest]:
        return list(self._agents.values())

    async def delegate_to_best(
        self,
        capability: AgentCapability,
        request: DelegationRequest,
    ) -> DelegationResponse | None:
        best = self.get_best_agent(capability)
        if best is None:
            self._logger.warning(
                "no_agent_available",
                capability=capability.value,
            )
            return None
        service_name, manifest = best
        base_url = self._known_services.get(service_name)
        if not base_url:
            self._logger.error("unknown_service_url", service_name=service_name)
            return None
        try:
            payload = _to_dict(request)
            response = await self._http_client.post(
                f"{base_url}/agent/delegate",
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
            data = body.get("data", body)
            if isinstance(data, dict):
                return DelegationResponse(**data)
            return data
        except Exception as exc:
            self._logger.error(
                "delegation_failed",
                service_name=service_name,
                capability=capability.value,
                error=str(exc),
            )
            return None

    def start_background_refresh(self, interval: float = 30.0) -> None:
        if self._refresh_task is not None and not self._refresh_task.done():
            self._logger.warning("background_refresh_already_running")
            return
        self._refresh_task = asyncio.create_task(
            self._background_refresh_loop(interval)
        )
        self._logger.info("background_refresh_started", interval=interval)

    def stop_background_refresh(self) -> None:
        if self._refresh_task is None or self._refresh_task.done():
            return
        self._refresh_task.cancel()
        self._refresh_task = None
        self._logger.info("background_refresh_stopped")

    async def _background_refresh_loop(self, interval: float) -> None:
        while True:
            try:
                await self.discover_all()
            except Exception as exc:
                self._logger.error(
                    "background_refresh_error",
                    error=str(exc),
                )
            await asyncio.sleep(interval)
