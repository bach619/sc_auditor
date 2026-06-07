"""ManticoreAgent — Backend Agent for Manticore symbolic execution.

Receives delegations from Antonio, runs guided Manticore analysis
on Solidity contracts, and returns HIGH/CRITICAL findings.
"""

from __future__ import annotations

from typing import Any

from shared.agent_protocol.base_agent import BaseAgent
from shared.agent_protocol.models import (
    AgentCapability,
    CapabilityDefinition,
    DelegationRequest,
)

from .guided_analyzer import GuidedAnalyzer
from .resource_guard import ResourceBudget
from .skills import create_registry


class ManticoreAgent(BaseAgent):
    """Backend Agent for Manticore symbolic execution.

    Focus: HIGH/CRITICAL severity bug confirmation.
    """

    def __init__(self, analyzer: GuidedAnalyzer) -> None:
        self._analyzer = analyzer
        self.skill_registry = create_registry()
        super().__init__(
            service_name="04e-scanner-manticore",
            agent_role="manticore_symbolic_analyzer",
            version="0.1.0",
            skill_registry=self.skill_registry,
        )
        self._max_concurrent = 1  # Resource-intensive

        self.register_capability(CapabilityDefinition(
            name=AgentCapability.RUN_MANTICORE,
            description=(
                "Run Manticore symbolic execution focused on HIGH/CRITICAL bugs. "
                "Custom detectors: reentrancy, access control, flash loan + oracle, "
                "overflow leading to fund loss, arbitrary delegatecall."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "sources": {
                        "type": "object",
                        "description": "Source files keyed by path (path -> code)",
                    },
                    "contract_name": {
                        "type": "string",
                        "description": "Specific contract name to analyze",
                    },
                    "functions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific functions to test",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Max analysis duration in seconds",
                    },
                    "use_slither_guide": {
                        "type": "boolean",
                        "description": "Use Slither to guide symbolic execution",
                    },
                    "confirm_finding": {
                        "type": "object",
                        "description": "Specific finding to deep-confirm",
                    },
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "findings": {"type": "array"},
                    "summary": {"type": "object"},
                    "resource_usage": {"type": "object"},
                },
            },
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        capability = request.capability
        data = request.input_data
        timeout = data.get("timeout", 300)

        if capability == AgentCapability.RUN_MANTICORE:
            sources = data.get("sources", {})
            if not sources:
                raise ValueError("At least one source file is required")

            # Adjust budget based on complexity
            budget = ResourceBudget(max_duration_seconds=timeout)
            self._analyzer.resource_guard._budget = budget

            # Check if this is a confirmation request
            confirm_target = data.get("confirm_finding")
            if confirm_target:
                return await self._analyzer.confirm_finding(
                    source_files=sources,
                    finding=confirm_target,
                    timeout=timeout,
                )

            # Standard guided analysis
            result = await self._analyzer.analyze(
                source_files=sources,
                contract_name=data.get("contract_name"),
                functions_to_test=data.get("functions"),
                timeout=timeout,
                use_slither_guide=data.get("use_slither_guide", True),
            )
            return result
        else:
            raise ValueError(f"Unknown capability: {capability}")
