"""ScannerAgent — Backend Agent for smart contract scanning with skill registry.

Receives delegations from Antonio, routes to registered skills:
- select_tools — analysis + tool selection
- run_slither, run_mythril, run_echidna, run_halmos — tool execution
- merge_findings — deduplicate and merge results
"""

from __future__ import annotations

from typing import Any

import httpx

from shared.skills.skill_registry import SkillRegistry
from shared.agent_protocol.base_agent import BaseAgent
from shared.agent_protocol.models import (
    AgentCapability,
    CapabilityDefinition,
    DelegationRequest,
)

from .skills import (
    RunSlitherSkill,
    RunMythrilSkill,
    RunEchidnaSkill,
    RunHalmosSkill,
    SelectToolsSkill,
    MergeFindingsSkill,
)


class ScannerAgent(BaseAgent):
    """Backend Agent for smart contract scanning.

    Maintains its own SkillRegistry with 6 registered skills.
    _execute_task() orchestrates: select_tools -> run tools -> merge_findings.
    """

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        # ── Skill Registry ──
        self.skill_registry = SkillRegistry()

        super().__init__(
            service_name="04-scanner",
            agent_role="scanner_operator",
            version="0.2.0",
            skill_registry=self.skill_registry,
        )
        self._http = http_client
        self._max_concurrent = 2
        self.skill_registry.register(SelectToolsSkill())
        self.skill_registry.register(RunSlitherSkill(http_client))
        self.skill_registry.register(RunMythrilSkill(http_client))
        self.skill_registry.register(RunEchidnaSkill(http_client))
        self.skill_registry.register(RunHalmosSkill(http_client))
        self.skill_registry.register(MergeFindingsSkill())

        # -- Capabilities (backward compat) --
        self.register_capability(CapabilityDefinition(
            name=AgentCapability.RUN_STATIC_ANALYSIS,
            description="Run static analysis tools (Slither, Mythril) to find vulnerabilities",
            input_schema={},
            output_schema={},
            estimated_duration_ms=5_000,
            estimated_cost_usd=0.02,
            confidence=0.80,
        ))
        self.register_capability(CapabilityDefinition(
            name=AgentCapability.RUN_FUZZING,
            description="Run fuzzing with Echidna for property-based testing",
            input_schema={},
            output_schema={},
            estimated_duration_ms=10_000,
            estimated_cost_usd=0.05,
            confidence=0.70,
        ))
        self.register_capability(CapabilityDefinition(
            name=AgentCapability.RUN_SYMBOLIC,
            description="Run symbolic execution with Halmos",
            input_schema={},
            output_schema={},
            estimated_duration_ms=300_000,
            estimated_cost_usd=0.03,
            confidence=0.75,
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        """Execute scanning task: select tools -> run tools -> merge findings."""
        input_data = request.input_data
        sources = input_data.get("sources", {})
        address = input_data.get("address", "")
        chain = input_data.get("chain", "ethereum")

        # Step 1: Select tools
        selection = await self.skill_registry.execute("select_tools", sources=sources)
        if not selection.success:
            return {"error": selection.error, "findings": []}
        tools_to_run = selection.output.get("tools", ["slither"])
        reasoning = selection.output.get("reasoning", [])

        # Step 2: Run each tool
        tool_outputs = {}
        for tool in tools_to_run:
            result = await self.skill_registry.execute(
                f"run_{tool}",
                sources=sources,
                address=address,
                chain=chain,
            )
            tool_outputs[tool] = result.output if result.success else {"success": False, "error": result.error, "findings": []}

        # Step 3: Merge findings
        merged = await self.skill_registry.execute(
            "merge_findings",
            tool_outputs=tool_outputs,
            tools_run=tools_to_run,
            reasoning=reasoning,
        )

        return merged.output if merged.success else {
            "findings": [],
            "tool_outputs": tool_outputs,
            "tools_run": tools_to_run,
            "reasoning": reasoning,
            "error": merged.error,
        }
