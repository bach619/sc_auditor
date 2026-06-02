"""AIAgent — Delegation Receiver for AI Analysis.

Receives delegations from Antonio and executes them using the Analyzer
or FixSuggester directly. NO autonomous routing — Antonio decides strategy.
NO skill registry — pure execution.

Capabilities:
- CLASSIFY_FINDINGS -> analyzer.analyze_all()
- GENERATE_FIX -> fixer.suggest_fix()
"""

from __future__ import annotations

from typing import Any

from shared.agent_protocol.base_agent import BaseAgent
from shared.agent_protocol.models import (
    AgentCapability,
    CapabilityDefinition,
    DelegationRequest,
)


class AIAgent(BaseAgent):
    """Delegation receiver for AI-powered vulnerability analysis.

    Pure task executor — no skill registry, no autonomous routing,
    no severity-based strategy selection. Antonio decides the strategy;
    06-ai executes exactly what it's told.

    Attributes:
        _analyzer: Analyzer instance for LLM-based finding classification.
        _fixer: FixSuggester instance for LLM-based fix generation.
    """

    def __init__(
        self,
        analyzer: Any,
        fixer: Any,
    ) -> None:
        """Initialize the AIAgent as a pure delegation receiver.

        Args:
            analyzer: The Analyzer instance for TP/FP classification.
            fixer: The FixSuggester instance for fix generation.
        """
        super().__init__(
            service_name="06-ai",
            agent_role="vulnerability_analyst",
            version="0.3.0",
        )
        self._analyzer = analyzer
        self._fixer = fixer

        # ── Capabilities (for discovery by Antonio) ──
        self.register_capability(CapabilityDefinition(
            name=AgentCapability.CLASSIFY_FINDINGS,
            description="Classify scanner findings as True Positive or False Positive using LLM analysis",
            input_schema={},
            output_schema={},
        ))
        self.register_capability(CapabilityDefinition(
            name=AgentCapability.GENERATE_FIX,
            description="Generate code fix recommendations for confirmed vulnerabilities",
            input_schema={},
            output_schema={},
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        """Execute a delegated task — pure execution, no autonomous decisions.

        Antonio controls WHAT to do and HOW. 06-ai only executes.

        Args:
            request: The delegation request from Antonio.

        Returns:
            Task result (dict with findings or fix suggestions).

        Raises:
            ValueError: If the capability is unknown.
        """
        capability = request.capability
        input_data = request.input_data

        if capability == AgentCapability.CLASSIFY_FINDINGS:
            return await self._execute_classify(input_data)
        elif capability == AgentCapability.GENERATE_FIX:
            return await self._execute_fix(input_data)
        else:
            raise ValueError(f"Unknown capability: {capability}")

    async def _execute_classify(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Classify findings using the Analyzer.

        Processes ALL findings as received — Antonio decides grouping/strategy.
        No severity-based routing, no deep vs batch decisions.

        Args:
            input_data: Contains 'source', 'findings', 'compiler', 'contract_name'.

        Returns:
            Dict with 'findings' (list of AnalyzedFinding dicts) and 'summary'.
        """
        from src.models import Finding

        source = input_data.get("source", {})
        findings_data = input_data.get("findings", [])
        compiler = input_data.get("compiler")
        contract_name = input_data.get("contract_name", "unknown")

        if not isinstance(findings_data, list):
            findings_data = []

        finding_objs = [Finding(**f) for f in findings_data]

        results = await self._analyzer.analyze_all(
            source=source,
            findings=finding_objs,
            compiler=compiler,
            contract_name=contract_name,
        )

        result_dicts = [
            r.model_dump() if hasattr(r, 'model_dump') else r
            for r in results
        ]

        tp_count = sum(
            1 for r in result_dicts
            if r.get("ai_verdict") == "true_positive"
        )
        fp_count = len(result_dicts) - tp_count

        return {
            "findings": result_dicts,
            "summary": {
                "total": len(result_dicts),
                "true_positives": tp_count,
                "false_positives": fp_count,
            },
        }

    async def _execute_fix(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Generate a fix for a single finding using the FixSuggester.

        Args:
            input_data: Contains 'source', 'finding', 'compiler'.

        Returns:
            Dict with 'fix' (FixSuggestion dict) and 'finding_id'.
        """
        from src.models import Finding

        source = input_data.get("source", {})
        finding_data = input_data.get("finding", {})
        compiler = input_data.get("compiler")

        # Combine source files into one string
        if isinstance(source, dict):
            full_source = "\n\n".join(
                f"// File: {name}\n{content}"
                for name, content in source.items()
            )
        else:
            full_source = str(source)

        finding_obj = Finding(**finding_data)

        suggestion = await self._fixer.suggest_fix(
            source_code=full_source,
            finding=finding_obj,
            compiler=compiler,
        )

        return {
            "fix": suggestion.model_dump() if hasattr(suggestion, 'model_dump') else suggestion,
            "finding_id": finding_data.get("id"),
        }
