"""HalmosAgent — Backend Agent for Halmos symbolic execution.

Receives delegations from Antonio, runs Halmos symbolic testing
on Foundry test files, and returns findings with intelligence enrichment.
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

from src.halmos import HalmosRunner

from .skills import create_registry


class HalmosAgent(BaseAgent):
    """Backend Agent for Halmos symbolic execution."""

    def __init__(self, runner: HalmosRunner) -> None:
        self._runner = runner
        self.skill_registry = create_registry()
        super().__init__(
            service_name="04d-scanner-halmos",
            agent_role="halmos_symbolic_analyzer",
            version="0.1.0",
            skill_registry=self.skill_registry,
        )
        self._max_concurrent = 2

        self.register_capability(CapabilityDefinition(
            name=AgentCapability.RUN_SYMBOLIC,
            description="Run Halmos symbolic execution on Foundry test files",
            input_schema={
                "type": "object",
                "properties": {
                    "sources": {"type": "object", "description": "Source files keyed by path"},
                    "function": {"type": "string", "description": "Specific function to test"},
                    "timeout": {"type": "integer"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "findings": {"type": "array"},
                    "passed": {"type": "boolean"},
                    "failed": {"type": "boolean"},
                    "duration_seconds": {"type": "number"},
                },
            },
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        capability = request.capability
        data = request.input_data

        if capability == AgentCapability.RUN_SYMBOLIC:
            sources = data.get("sources", {})
            if not sources:
                raise ValueError("At least one source file is required")

            audit_id = uuid.uuid4().hex[:12]
            audit_dir = Path(f"/tmp/halmos_agent_{audit_id}")
            audit_dir.mkdir(parents=True, exist_ok=True)

            try:
                for file_path, source_code in sources.items():
                    target = audit_dir / file_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(source_code, encoding="utf-8")

                start = time.monotonic()
                result = await asyncio.to_thread(
                    self._runner.run,
                    sources=sources,
                    timeout=data.get("timeout", 300),
                    function=data.get("function"),
                )
                elapsed = time.monotonic() - start

                return {
                    "findings": [
                        f.to_dict() if hasattr(f, "to_dict") else f.__dict__
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
