"""EchidnaAgent — Backend Agent for Echidna fuzzing.

Receives delegations from Antonio, runs Echidna property-based fuzzing
on Solidity contracts, and returns findings with intelligence enrichment.
"""

from __future__ import annotations

import asyncio
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from shared.agent_protocol.base_agent import BaseAgent
from shared.agent_protocol.models import (
    AgentCapability,
    CapabilityDefinition,
    DelegationRequest,
)

from src.echidna import EchidnaRunner

from .skills import create_registry


class EchidnaAgent(BaseAgent):
    """Backend Agent for Echidna fuzzing."""

    def __init__(self, runner: EchidnaRunner) -> None:
        self._runner = runner
        self.skill_registry = create_registry()
        super().__init__(
            service_name="04b-scanner-echidna",
            agent_role="echidna_fuzzer",
            version="0.2.0",
            skill_registry=self.skill_registry,
        )
        self._max_concurrent = 2

        self.register_capability(CapabilityDefinition(
            name=AgentCapability.RUN_FUZZING,
            description="Run Echidna property-based fuzzing on Solidity contracts",
            input_schema={
                "type": "object",
                "properties": {
                    "sources": {"type": "object", "description": "Source files keyed by path"},
                    "contract_address": {"type": "string"},
                    "chain": {"type": "string"},
                    "timeout": {"type": "integer"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "findings": {"type": "array"},
                    "total_findings": {"type": "integer"},
                    "passed": {"type": "boolean"},
                    "failed": {"type": "boolean"},
                    "duration_seconds": {"type": "number"},
                },
            },
        ))

    def estimate_cost(self, input_data: dict) -> dict[str, Any]:
        """Estimate duration and cost for a fuzzing run.

        Factors:
        - Number of source files
        - Total lines of code
        - Timeout requested

        Returns:
            Dict with estimated_duration_seconds, estimated_cost_usd,
            complexity, num_files, total_lines.
        """
        sources = input_data.get("sources", {})
        timeout = input_data.get("timeout", 600)

        num_files = len(sources)
        total_lines = sum(len(s.split("\n")) for s in sources.values())

        if total_lines < 200:
            complexity = "low"
        elif total_lines < 800:
            complexity = "medium"
        else:
            complexity = "high"

        estimated_seconds = min(timeout, max(60, total_lines // 2))

        estimated_cost = round(estimated_seconds * 0.000004, 4)

        return {
            "estimated_duration_seconds": estimated_seconds,
            "estimated_cost_usd": estimated_cost,
            "complexity": complexity,
            "num_files": num_files,
            "total_lines": total_lines,
        }

    async def _execute_task(self, request: DelegationRequest) -> Any:
        capability = request.capability
        data = request.input_data

        if capability == AgentCapability.RUN_FUZZING:
            sources = data.get("sources", {})
            if not sources:
                raise ValueError("At least one source file is required")

            audit_id = uuid.uuid4().hex[:12]
            audit_dir = Path(f"/tmp/echidna_agent_{audit_id}")
            audit_dir.mkdir(parents=True, exist_ok=True)

            try:
                for file_path, source_code in sources.items():
                    target = audit_dir / file_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(source_code, encoding="utf-8")

                start = time.monotonic()
                result = await asyncio.to_thread(
                    self._runner.run,
                    audit_dir,
                    contract_name=data.get("contract_name"),
                    timeout=data.get("timeout", 600),
                )
                elapsed = time.monotonic() - start

                return {
                    "findings": [
                        f.__dict__ if hasattr(f, "__dict__") else f
                        for f in getattr(result, "findings", [])
                    ],
                    "total_findings": len(getattr(result, "findings", [])),
                    "passed": getattr(result, "passed", False),
                    "failed": getattr(result, "failed", False),
                    "duration_seconds": round(elapsed, 2),
                }
            finally:
                shutil.rmtree(audit_dir, ignore_errors=True)
        else:
            raise ValueError(f"Unknown capability: {capability}")
