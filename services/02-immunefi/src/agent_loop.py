"""ImmunefiAgent — Backend Agent for bounty intelligence with skill registry.

Receives delegations from Antonio, routes to registered skills:
- sync_programs — sync from all providers
- search_programs — search/filter programs
- get_program_details — full program intel
- analyze_competition — competitive analysis
- predict_vulnerabilities — ML-based prediction
- monitor_events — on-chain monitoring
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
    AnalyzeCompetitionSkill,
    GetProgramDetailsSkill,
    MonitorEventsSkill,
    PredictVulnerabilitiesSkill,
    SearchProgramsSkill,
    SyncProgramsSkill,
)


class ImmunefiAgent(BaseAgent):
    """Backend Agent for bounty program intelligence."""

    def __init__(
        self,
        sync_service: Any,
        storage: Any,
        scorer: Any,
        competition: Any,
        predictor: Any,
        onchain: Any,
    ) -> None:
        self.skill_registry = SkillRegistry()
        self.skill_registry.register(SyncProgramsSkill(sync_service))
        self.skill_registry.register(SearchProgramsSkill(storage))
        self.skill_registry.register(GetProgramDetailsSkill(storage, scorer))
        self.skill_registry.register(AnalyzeCompetitionSkill(competition))
        self.skill_registry.register(PredictVulnerabilitiesSkill(predictor))
        self.skill_registry.register(MonitorEventsSkill(onchain))

        super().__init__(
            service_name="02-immunefi",
            agent_role="bounty_intelligence",
            version="0.2.0",
            skill_registry=self.skill_registry,
        )
        self._max_concurrent = 3

        self.register_capability(CapabilityDefinition(
            name=AgentCapability.FETCH_PROGRAM,
            description="Fetch and sync bounty programs from all providers",
            input_schema={
                "type": "object",
                "properties": {
                    "provider": {"type": "string", "description": "Provider name (immunefi, hackerone, etc.)"},
                    "full_sync": {"type": "boolean", "description": "Force full re-sync"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "programs": {"type": "array", "description": "List of synced programs"},
                    "error": {"type": "string", "description": "Error message if failed"},
                },
            },
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        capability = request.capability
        input_data = request.input_data

        if capability == AgentCapability.FETCH_PROGRAM:
            result = await self.skill_registry.execute(
                "sync_programs",
                provider=input_data.get("provider"),
                full_sync=input_data.get("full_sync", False),
            )
            return result.output if result.success else {"error": result.error}

        else:
            raise ValueError(f"Unknown capability: {capability}")
