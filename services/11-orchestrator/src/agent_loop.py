"""OrchestratorAgent — Backend Agent for pipeline orchestration with skill registry.

Receives delegations from Antonio, routes to registered skills:
- run_pipeline — start audit pipeline
- schedule_audit — recurring audits
- retry_failed — retry failed audits
- manage_queue — priority queue management
- find_similar — contract similarity search
"""

from __future__ import annotations

from typing import Any

from shared.agent_protocol.base_agent import BaseAgent
from shared.agent_protocol.models import (
    AgentCapability,
    CapabilityDefinition,
    DelegationRequest,
)
from shared.skills.skill_registry import SkillRegistry

from .skills import (
    FindSimilarSkill,
    ManageQueueSkill,
    RetryFailedSkill,
    RunPipelineSkill,
    ScheduleAuditSkill,
)


class OrchestratorAgent(BaseAgent):
    """Backend Agent for audit pipeline orchestration."""

    def __init__(
        self,
        pipeline: Any,
        daemon: Any,
        priority_service: Any,
        similarity: Any,
    ) -> None:
        self.skill_registry = SkillRegistry()
        self.skill_registry.register(RunPipelineSkill(pipeline))
        self.skill_registry.register(ScheduleAuditSkill(daemon))
        self.skill_registry.register(RetryFailedSkill(pipeline))
        self.skill_registry.register(ManageQueueSkill(priority_service))
        self.skill_registry.register(FindSimilarSkill(similarity))

        super().__init__(
            service_name="11-orchestrator",
            agent_role="pipeline_orchestrator",
            version="0.2.0",
            skill_registry=self.skill_registry,
        )
        self._max_concurrent = 3

        self.register_capability(CapabilityDefinition(
            name=AgentCapability.FETCH_PROGRAM,
            description="Coordinate full audit pipelines across all services",
            input_schema={},
            output_schema={},
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        input_data = request.input_data
        action = input_data.get("action", "run_pipeline")

        if action == "run_pipeline":
            result = await self.skill_registry.execute(
                "run_pipeline",
                address=input_data.get("address", ""),
                chain=input_data.get("chain", "ethereum"),
                source=input_data.get("source"),
            )
        elif action == "schedule":
            result = await self.skill_registry.execute(
                "schedule_audit",
                address=input_data.get("address", ""),
                chain=input_data.get("chain", "ethereum"),
                interval_hours=input_data.get("interval_hours", 24),
            )
        elif action == "retry":
            result = await self.skill_registry.execute(
                "retry_failed",
                audit_id=input_data.get("audit_id"),
                retry_all=input_data.get("retry_all", False),
            )
        elif action == "queue":
            result = await self.skill_registry.execute(
                "manage_queue",
                action=input_data.get("queue_action", "list"),
                address=input_data.get("address"),
                chain=input_data.get("chain"),
                priority=input_data.get("priority", 5),
            )
        else:
            return {"error": f"Unknown action: {action}"}

        return result.output if result.success else {"error": result.error}
