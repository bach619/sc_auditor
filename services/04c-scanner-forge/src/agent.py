"""ForgeAgent — Backend Agent for Foundry build verification.

Receives delegations from Antonio, runs Forge build to verify
Solidity source code compiles correctly.
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

from src.forge import ForgeRunner

from .skills import create_registry


class ForgeAgent(BaseAgent):
    """Backend Agent for Foundry build verification."""

    def __init__(self, runner: ForgeRunner) -> None:
        self._runner = runner
        self.skill_registry = create_registry()
        super().__init__(
            service_name="04c-scanner-forge",
            agent_role="forge_build_verifier",
            version="0.1.0",
            skill_registry=self.skill_registry,
        )
        self._max_concurrent = 2

        self.register_capability(CapabilityDefinition(
            name=AgentCapability.RUN_FORGE,
            description="Verify Solidity source code compiles with Foundry build",
            input_schema={
                "type": "object",
                "properties": {
                    "sources": {"type": "object", "description": "Source files keyed by path"},
                    "contract_address": {"type": "string"},
                    "timeout": {"type": "integer"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "errors": {"type": "array"},
                    "duration_seconds": {"type": "number"},
                },
            },
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        capability = request.capability
        data = request.input_data

        if capability == AgentCapability.RUN_FORGE:
            sources = data.get("sources", {})
            if not sources:
                raise ValueError("At least one source file is required")

            audit_id = uuid.uuid4().hex[:12]
            audit_dir = Path(f"/tmp/forge_agent_{audit_id}")
            audit_dir.mkdir(parents=True, exist_ok=True)

            try:
                for file_path, source_code in sources.items():
                    target = audit_dir / file_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(source_code, encoding="utf-8")

                start = time.monotonic()
                result = await asyncio.to_thread(
                    self._runner.run,
                    project_dir=audit_dir,
                    timeout=data.get("timeout", 300),
                )
                elapsed = time.monotonic() - start

                return {
                    "success": getattr(result, "success", False),
                    "errors": getattr(result, "errors", []),
                    "duration_seconds": round(elapsed, 2),
                }
            finally:
                shutil.rmtree(audit_dir, ignore_errors=True)
        else:
            raise ValueError(f"Unknown capability: {capability}")
