from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from ..skills.skill_registry import SkillRegistry

from .models import (
    AgentCapability,
    AgentManifest,
    AgentStatus,
    CapabilityDefinition,
    DelegationRequest,
    DelegationResponse,
    NegotiationRequest,
    NegotiationResponse,
    TaskStatus,
    now_iso,
)


class BaseAgent(ABC):
    """Abstract base for all VYPER agents.

    Provides:
    - Manifest management (capabilities, status)
    - Delegation handling (receive tasks, return results)
    - Negotiation handling (feasibility checks)
    - Session tracking

    Subclasses must implement:
    - _execute_task(): Actual task execution logic
    """

    def __init__(
        self,
        service_name: str,
        agent_role: str,
        version: str = "0.1.0",
        skill_registry: SkillRegistry | None = None,
    ) -> None:
        self._service_name = service_name
        self._agent_role = agent_role
        self._version = version
        self._start_time = time.monotonic()

        self._capabilities: dict[AgentCapability, CapabilityDefinition] = {}
        self._active_tasks: dict[str, DelegationRequest] = {}
        self._completed_tasks: list[DelegationResponse] = []
        self._status = AgentStatus.STARTING
        self._max_concurrent = 3
        self._skill_registry = skill_registry

        import structlog

        self._logger = structlog.get_logger(
            f"vyper.{service_name}.{agent_role}",
            service_name=service_name,
            agent_role=agent_role,
        )

    def register_capability(self, capability: CapabilityDefinition) -> None:
        cap_enum = AgentCapability(capability.name)
        self._capabilities[cap_enum] = capability
        self._logger.info(
            "capability_registered",
            capability=cap_enum.value,
            description=capability.description,
        )

    def get_manifest(self) -> AgentManifest:
        manifest = AgentManifest(
            service_name=self._service_name,
            agent_role=self._agent_role,
            version=self._version,
            capabilities=list(self._capabilities.values()),
            current_load={
                "active_tasks": len(self._active_tasks),
                "queue_depth": 0,
                "status": self._status.value,
            },
        )
        # Include skill specs if SkillRegistry is available
        if self._skill_registry is not None:
            manifest.skills = [
                s.to_dict() for s in self._skill_registry.list_specs()
            ]
        return manifest

    async def handle_delegation(
        self, request: DelegationRequest
    ) -> DelegationResponse:
        if len(self._active_tasks) >= self._max_concurrent:
            return DelegationResponse(
                task_id=request.task_id,
                status=TaskStatus.DEFERRED,
                error=f"At maximum capacity ({self._max_concurrent})",
            )

        if request.capability not in self._capabilities:
            return DelegationResponse(
                task_id=request.task_id,
                status=TaskStatus.FAILED,
                error=f"Capability '{request.capability.value}' not registered",
            )

        self._status = AgentStatus.BUSY
        self._active_tasks[request.task_id] = request
        start_time = time.monotonic()
        steps_taken: list[dict] = []

        try:
            result = await self._execute_task(request)
            duration_ms = int((time.monotonic() - start_time) * 1000)

            if isinstance(result, dict) and "_steps" in result:
                step_count = result.pop("_steps", 0)
                steps_taken = [
                    {"step": i, "description": f"Step {i}"}
                    for i in range(1, step_count + 1)
                ]

            cost = self._estimate_cost(request.capability, duration_ms)
            reflection = await self._generate_reflection(request, result)

            response = DelegationResponse(
                task_id=request.task_id,
                status=TaskStatus.COMPLETED,
                output=result,
                confidence=self._capabilities[request.capability].confidence,
                cost_usd=cost,
                duration_ms=duration_ms,
                steps_taken=steps_taken,
                reflection=reflection,
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            self._logger.exception(
                "task_execution_failed",
                task_id=request.task_id,
                error=str(exc),
            )
            response = DelegationResponse(
                task_id=request.task_id,
                status=TaskStatus.FAILED,
                error=str(exc),
                duration_ms=duration_ms,
            )

        self._active_tasks.pop(request.task_id, None)
        self._completed_tasks.append(response)
        if len(self._completed_tasks) > 100:
            self._completed_tasks = self._completed_tasks[-100:]

        if not self._active_tasks:
            self._status = AgentStatus.IDLE

        return response

    async def handle_negotiation(
        self, request: NegotiationRequest
    ) -> NegotiationResponse:
        if request.required_capability not in self._capabilities:
            return NegotiationResponse(
                can_handle=False,
                reasoning=(
                    f"Capability '{request.required_capability.value}' not available"
                ),
            )

        cap = self._capabilities[request.required_capability]
        load_factor = (
            len(self._active_tasks) / self._max_concurrent
            if self._max_concurrent > 0
            else 0
        )

        if load_factor >= 1.0:
            return NegotiationResponse(
                can_handle=False,
                reasoning="At maximum capacity",
                estimated_duration_ms=int(
                    cap.estimated_duration_ms * (1 + load_factor * 0.5)
                ),
            )

        estimated_duration = int(
            cap.estimated_duration_ms * (1 + load_factor * 0.5)
        )
        estimated_confidence = cap.confidence * (1 - load_factor * 0.1)
        estimated_cost = self._estimate_cost(
            request.required_capability, estimated_duration
        )

        return NegotiationResponse(
            can_handle=True,
            estimated_duration_ms=estimated_duration,
            estimated_cost_usd=estimated_cost,
            estimated_confidence=estimated_confidence,
            reasoning=f"Load factor: {load_factor:.2f}",
        )

    @abstractmethod
    async def _execute_task(self, request: DelegationRequest) -> Any:
        ...

    async def _generate_reflection(
        self,
        request: DelegationRequest,
        result: Any,
    ) -> str:
        return ""

    def _estimate_cost(
        self, capability: AgentCapability, duration_ms: int
    ) -> float:
        cap = self._capabilities.get(capability)
        if cap is None or cap.estimated_duration_ms <= 0:
            return 0.0
        ratio = duration_ms / cap.estimated_duration_ms
        return cap.estimated_cost_usd * ratio

    def get_health(self) -> dict:
        return {
            "service_name": self._service_name,
            "agent_role": self._agent_role,
            "version": self._version,
            "status": self._status.value,
            "uptime_seconds": time.monotonic() - self._start_time,
            "capabilities": [c.value for c in self._capabilities],
            "active_tasks": len(self._active_tasks),
            "max_concurrent": self._max_concurrent,
            "completed_tasks": len(self._completed_tasks),
        }

    @property
    def status(self) -> AgentStatus:
        return self._status

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def agent_role(self) -> str:
        return self._agent_role
