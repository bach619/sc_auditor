"""SourceAgent — Backend Agent for source code intelligence.

Receives delegations from Antonio, fetches and serves smart contract
source code from multiple blockchain explorers (Etherscan, Sourcify, etc.).
"""

from __future__ import annotations

from typing import Any

from shared.agent_protocol.base_agent import BaseAgent
from shared.agent_protocol.models import (
    AgentCapability,
    CapabilityDefinition,
    DelegationRequest,
)

from .detector import SourceDetector


class SourceAgent(BaseAgent):
    """Backend Agent for source code fetching."""

    def __init__(self, detector: SourceDetector) -> None:
        self._detector = detector
        super().__init__(
            service_name="03-source",
            agent_role="source_intelligence",
            version="0.2.0",
        )
        self._max_concurrent = 5

        self.register_capability(CapabilityDefinition(
            name=AgentCapability.FETCH_SOURCE,
            description="Fetch smart contract source code by chain and address",
            input_schema={
                "type": "object",
                "properties": {
                    "chain": {"type": "string", "description": "Blockchain name (ethereum, bsc, etc.)"},
                    "address": {"type": "string", "description": "Contract address"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "source_code": {"type": "string"},
                    "contract_name": {"type": "string"},
                    "compiler_version": {"type": "string"},
                },
            },
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        capability = request.capability
        data = request.input_data

        if capability == AgentCapability.FETCH_SOURCE:
            chain = data.get("chain", "ethereum")
            address = data.get("address", "")
            result = await self._detector.fetch(chain=chain, address=address)
            return result
        else:
            raise ValueError(f"Unknown capability: {capability}")
