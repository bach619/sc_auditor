"""DelegateTaskSkill — Antonio delegates tasks to Backend Agents via AgentRegistry."""

from __future__ import annotations

from typing import Any

import structlog

from src.skills.base import BaseSkill
from src.models import SkillResult

log = structlog.get_logger()


class DelegateTaskSkill(BaseSkill):
    """Skill to delegate tasks to backend agents via the AgentRegistry.
    
    Antonio's ReAct loop calls this skill when it decides
    a task should be handled by a specialized backend agent.
    """

    def __init__(self, agent_registry: Any | None = None) -> None:
        super().__init__()
        self._agent_registry = agent_registry
        self.name = "delegate_task"
        self.description = (
            "Delegate a task to a specialized backend agent "
            "(AI analysis, scanner, exploit engine, etc.)"
        )
        self.parameters = {
            "capability": {
                "type": "string",
                "description": "Required capability: classify_findings, run_static_analysis, "
                               "test_exploit, generate_report, fetch_source, etc.",
                "required": True,
            },
            "goal": {
                "type": "string",
                "description": "What the backend agent should do",
                "required": True,
            },
            "input_data": {
                "type": "object",
                "description": "Context data for the backend agent",
                "required": True,
            },
        }

    async def execute(self, **kwargs: Any) -> SkillResult:
        """Delegate task to the best available backend agent."""
        if self._agent_registry is None:
            return SkillResult(
                success=False,
                error="Agent registry not available. Cannot delegate tasks.",
            )

        capability_str = kwargs.get("capability", "")
        goal = kwargs.get("goal", "")
        input_data = kwargs.get("input_data", {})

        if not capability_str:
            return SkillResult(success=False, error="capability is required")
        if not goal:
            return SkillResult(success=False, error="goal is required")

        from shared.agent_protocol.models import AgentCapability
        try:
            capability = AgentCapability(capability_str)
        except ValueError:
            return SkillResult(
                success=False,
                error=f"Unknown capability: {capability_str}",
            )

        agent_info = self._agent_registry.get_best_agent(capability)
        if agent_info is None:
            return SkillResult(
                success=False,
                error=f"No backend agent available for capability: {capability_str}",
            )

        service_name, manifest = agent_info

        from shared.agent_protocol.models import DelegationRequest, generate_task_id
        request = DelegationRequest(
            task_id=generate_task_id(),
            goal=goal,
            capability=capability,
            input_data=input_data,
        )

        log.info(
            "delegating_task",
            to=service_name,
            capability=capability_str,
            task_id=request.task_id,
        )

        response = await self._agent_registry.delegate_to_best(capability, request)

        if response is None:
            return SkillResult(
                success=False,
                error=f"Delegation failed: no agent responded for {capability_str}",
            )

        if response.status.value in ("failed", "deferred", "cancelled"):
            error_msg = response.error or f"Agent returned {response.status.value}"
            return SkillResult(
                success=False,
                error=f"Agent {service_name}: {error_msg}",
                output={"delegation_response": {
                    "task_id": response.task_id,
                    "agent": service_name,
                    "status": response.status.value,
                    "error": response.error,
                }},
            )

        return SkillResult(
            success=True,
            output={
                "delegation_response": {
                    "task_id": response.task_id,
                    "agent": service_name,
                    "capability": capability_str,
                    "status": response.status.value,
                    "confidence": response.confidence,
                    "cost_usd": response.cost_usd,
                    "duration_ms": response.duration_ms,
                    "output": response.output,
                    "reflection": response.reflection,
                }
            },
        )
