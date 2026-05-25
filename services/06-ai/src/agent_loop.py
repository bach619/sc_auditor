"""AIAgent — Backend Agent for AI Analysis with local skill registry.

Receives delegations from Antonio, routes to registered skills:
- classify_single — deep analysis for critical/high findings
- classify_batch — batch analysis for low/medium findings
- generate_fix — code fix recommendations
- deep_analysis — full exploit path verification
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
    ClassifySingleSkill,
    ClassifyBatchSkill,
    GenerateFixSkill,
    DeepAnalysisSkill,
)


class AIAgent(BaseAgent):
    """Backend Agent for AI-powered vulnerability analysis.

    Maintains its own SkillRegistry with 4 registered skills.
    _execute_task() routes delegation to registry.execute().
    """

    def __init__(
        self,
        analyzer: Any,
        llm_client: Any,
    ) -> None:
        # ── Skill Registry ──
        self.skill_registry = SkillRegistry()

        super().__init__(
            service_name="06-ai",
            agent_role="vulnerability_analyst",
            version="0.2.0",
            skill_registry=self.skill_registry,
        )
        self._max_concurrent = 3
        self.skill_registry.register(ClassifySingleSkill(analyzer))
        self.skill_registry.register(ClassifyBatchSkill(analyzer))
        self.skill_registry.register(GenerateFixSkill(llm_client))
        self.skill_registry.register(DeepAnalysisSkill(analyzer))

        # ── Capabilities (untuk backward compat + discovery) ──
        self.register_capability(CapabilityDefinition(
            name=AgentCapability.CLASSIFY_FINDINGS,
            description="Classify scanner findings as True Positive or False Positive using LLM analysis",
        ))
        self.register_capability(CapabilityDefinition(
            name=AgentCapability.GENERATE_FIX,
            description="Generate code fix recommendations for confirmed vulnerabilities",
        ))
        self.register_capability(CapabilityDefinition(
            name=AgentCapability.DEEP_ANALYSIS,
            description="Deep dive analysis with full source code trace and exploit path verification",
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        """Route delegation to the right skill based on capability + context."""
        capability = request.capability
        input_data = request.input_data

        if capability == AgentCapability.CLASSIFY_FINDINGS:
            return await self._execute_classify(input_data)
        elif capability == AgentCapability.GENERATE_FIX:
            # Route to generate_fix skill
            result = await self.skill_registry.execute(
                "generate_fix",
                source=input_data.get("source", {}),
                finding=input_data.get("finding", {}),
                compiler=input_data.get("compiler"),
            )
            return result.output if result.success else {"error": result.error}
        elif capability == AgentCapability.DEEP_ANALYSIS:
            result = await self.skill_registry.execute(
                "deep_analysis",
                findings=input_data.get("findings", []),
                source=input_data.get("source", {}),
                compiler=input_data.get("compiler"),
            )
            return result.output if result.success else {"error": result.error}
        else:
            raise ValueError(f"Unknown capability: {capability}")

    async def _execute_classify(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Classify findings — routes to classify_single or classify_batch."""
        source = input_data.get("source", {})
        findings = input_data.get("findings", [])
        compiler = input_data.get("compiler")
        contract_name = input_data.get("contract_name", "unknown")

        # Separate by severity
        if not isinstance(findings, list):
            findings = []

        critical_high = [
            f for f in findings
            if f.get("severity") in ("critical", "high")
        ]
        low_medium = [
            f for f in findings
            if f.get("severity") in ("low", "informational", "medium")
        ]

        result_findings = []
        steps_taken = 0

        # Deep analysis for critical/high — one by one
        if critical_high:
            for finding in critical_high:
                result = await self.skill_registry.execute(
                    "classify_single",
                    finding=finding,
                    source=source,
                    compiler=compiler,
                )
                if result.success and result.output:
                    result_findings.append(result.output)
                steps_taken += 1

        # Batch analysis for low/medium — all at once
        if low_medium:
            result = await self.skill_registry.execute(
                "classify_batch",
                findings=low_medium,
                source=source,
                compiler=compiler,
                contract_name=contract_name,
            )
            if result.success and result.output:
                result_findings.extend(result.output)
            steps_taken += 1

        tp_count = sum(
            1 for r in result_findings
            if isinstance(r, dict) and r.get("ai_verdict") == "true_positive"
        )
        fp_count = len(result_findings) - tp_count

        return {
            "findings": result_findings,
            "summary": {
                "total": len(result_findings),
                "true_positives": tp_count,
                "false_positives": fp_count,
            },
            "strategy": "hybrid" if critical_high and low_medium
                        else ("deep" if critical_high else "batch"),
            "_steps": steps_taken,
        }

    async def _generate_reflection(
        self, request: DelegationRequest, result: Any
    ) -> str:
        if not isinstance(result, dict):
            return ""
        summary = result.get("summary", {})
        total = summary.get("total", 0) if isinstance(summary, dict) else 0
        tp = summary.get("true_positives", 0) if isinstance(summary, dict) else 0
        strategy = result.get("strategy", "unknown")
        return (
            f"Analyzed {total} findings ({tp} TP). "
            f"Strategy: {strategy}. "
            f"Steps: {result.get('_steps', 0)}"
        )
