"""ReporterAgent — Backend Agent for report generation with skill registry.

Receives delegations from Antonio, routes to registered skills:
- generate_full_report — comprehensive audit report
- generate_immunefi_report — Immunefi-ready submission
- generate_summary — executive summary
"""

from __future__ import annotations

from typing import Any

from shared.skills.skill_registry import SkillRegistry
from shared.agent_protocol.base_agent import BaseAgent
from shared.agent_protocol.models import (
    AgentCapability,
    CapabilityDefinition,
    DelegationRequest,
)

from .skills import (
    GenerateFullReportSkill,
    GenerateImmunefiReportSkill,
    GenerateSummarySkill,
)


class ReporterAgent(BaseAgent):
    """Backend Agent for audit report generation."""

    def __init__(self) -> None:
        self.skill_registry = SkillRegistry()
        self.skill_registry.register(GenerateFullReportSkill())
        self.skill_registry.register(GenerateImmunefiReportSkill())
        self.skill_registry.register(GenerateSummarySkill())

        super().__init__(
            service_name="09-reporter",
            agent_role="report_generator",
            version="0.2.0",
            skill_registry=self.skill_registry,
        )
        self._max_concurrent = 5

        self.register_capability(CapabilityDefinition(
            name=AgentCapability.GENERATE_REPORT,
            description="Generate comprehensive audit reports in multiple formats",
            input_schema={
                "type": "object",
                "properties": {
                    "audit_data": {
                        "type": "object",
                        "description": "Complete audit data with findings, analysis, and metadata",
                    },
                },
                "required": ["audit_data"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "report_type": {"type": "string"},
                    "format": {"type": "string"},
                    "content": {"type": "string"},
                    "length": {"type": "integer"},
                },
            },
        ))
        self.register_capability(CapabilityDefinition(
            name=AgentCapability.EXPORT_REPORT,
            description="Export audit reports in Immunefi-ready format",
            input_schema={
                "type": "object",
                "properties": {
                    "audit_data": {
                        "type": "object",
                        "description": "Audit data formatted for Immunefi submission",
                    },
                },
                "required": ["audit_data"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "report_type": {"type": "string"},
                    "format": {"type": "string"},
                    "content": {"type": "string"},
                    "length": {"type": "integer"},
                },
            },
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        """Route delegation to the right skill."""
        capability = request.capability
        input_data = request.input_data

        if capability == AgentCapability.GENERATE_REPORT:
            result = await self.skill_registry.execute(
                "generate_full_report",
                audit_data=input_data.get("audit_data", {}),
            )
            return result.output if result.success else {"error": result.error}

        elif capability == AgentCapability.EXPORT_REPORT:
            result = await self.skill_registry.execute(
                "generate_immunefi_report",
                audit_data=input_data.get("audit_data", {}),
            )
            return result.output if result.success else {"error": result.error}

        else:
            raise ValueError(f"Unknown capability: {capability}")
