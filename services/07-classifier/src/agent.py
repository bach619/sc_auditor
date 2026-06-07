"""ClassifierAgent — Backend Agent for bug classification.

Receives delegations from Antonio, classifies findings as TP/FP,
and returns accuracy metrics.
"""

from __future__ import annotations

from typing import Any

from shared.agent_protocol.base_agent import BaseAgent
from shared.agent_protocol.models import (
    AgentCapability,
    CapabilityDefinition,
    DelegationRequest,
)

from .classify import Classifier
from .metrics import MetricsTracker
from .skills import create_registry


class ClassifierAgent(BaseAgent):
    """Backend Agent for bug classification."""

    def __init__(self, classifier: Classifier, metrics: MetricsTracker) -> None:
        self._classifier = classifier
        self._metrics = metrics
        self.skill_registry = create_registry()
        super().__init__(
            service_name="07-classifier",
            agent_role="bug_classifier",
            version="0.1.0",
            skill_registry=self.skill_registry,
        )
        self._max_concurrent = 5

        self.register_capability(CapabilityDefinition(
            name=AgentCapability.CLASSIFY_FINDINGS,
            description="Classify findings as true positive or false positive",
            input_schema={
                "type": "object",
                "properties": {
                    "findings": {"type": "array", "description": "List of findings to classify"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "classifications": {"type": "array"},
                    "metrics": {"type": "object"},
                },
            },
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        capability = request.capability
        data = request.input_data

        if capability == AgentCapability.CLASSIFY_FINDINGS:
            findings = data.get("findings", [])
            results = []
            for f in findings:
                result = await self._classifier.classify(f)
                results.append(result)
            return {
                "classifications": results,
                "metrics": self._metrics.get_summary(),
            }
        else:
            raise ValueError(f"Unknown capability: {capability}")
