"""MythrilAgent — Backend Agent for Mythril symbolic execution.

Enhanced with deep analysis capability:
  1. RUN_SYMBOLIC (standard) — backward compatible, direct mythril CLI
  2. RUN_MYTHRIL_DEEP (enhanced) — Slither → Mythril → cross-ref → AI
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from shared.agent_protocol.base_agent import BaseAgent
from shared.agent_protocol.models import (
    AgentCapability,
    CapabilityDefinition,
    DelegationRequest,
)

from .guided_analyzer import GuidedAnalyzer
from .skills import create_registry


class MythrilAgent(BaseAgent):
    """Backend Agent for Mythril symbolic analysis.

    Supports both standard and deep analysis modes.
    """

    def __init__(self, guided_analyzer: GuidedAnalyzer | None = None) -> None:
        self._guided_analyzer = guided_analyzer
        self.skill_registry = create_registry()
        super().__init__(
            service_name="05-scanner-mythril",
            agent_role="mythril_symbolic_analyzer",
            version="0.2.0",
            skill_registry=self.skill_registry,
        )
        self._max_concurrent = 1  # Mythril is resource-heavy

        # Standard capability
        self.register_capability(CapabilityDefinition(
            name=AgentCapability.RUN_SYMBOLIC,
            description="Run standard Mythril symbolic execution on Solidity source code",
            input_schema={
                "type": "object",
                "properties": {
                    "sources": {"type": "object", "description": "Source files keyed by path"},
                    "timeout": {"type": "integer", "description": "Max duration per function"},
                    "depth": {"type": "integer", "description": "Mythril analysis depth"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "findings": {"type": "array"},
                    "total_findings": {"type": "integer"},
                    "duration_seconds": {"type": "number"},
                },
            },
        ))

        # Deep analysis capability (new!)
        self.register_capability(CapabilityDefinition(
            name=AgentCapability.RUN_MYTHRIL_DEEP,
            description=(
                "Deep Mythril analysis pipeline: Slither-guided → Mythril custom plugins → "
                "cross-reference with Manticore/Slither/Echidna → AI explanation. "
                "Focused on HIGH/CRITICAL bug confirmation."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "sources": {"type": "object", "description": "Source files keyed by path"},
                    "functions": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Specific functions to analyze (optional)",
                    },
                    "timeout": {"type": "integer", "description": "Max duration in seconds"},
                    "depth": {"type": "integer", "description": "Mythril analysis depth (default 42)"},
                    "use_slither_guide": {"type": "boolean", "description": "Guide with Slither"},
                    "use_custom_plugins": {"type": "boolean", "description": "Use custom Mythril modules"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "findings": {"type": "array", "description": "HIGH/CRITICAL findings"},
                    "summary": {"type": "object", "description": "Aggregated summary"},
                    "cross_reference": {"type": "object", "description": "Cross-ref with other tools"},
                    "resource_usage": {"type": "object", "description": "Resource consumption"},
                },
            },
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        capability = request.capability
        data = request.input_data
        timeout = data.get("timeout", 300)
        sources = data.get("sources", {})

        if not sources:
            raise ValueError("At least one source file is required")

        # ── Deep analysis ──
        if capability == AgentCapability.RUN_MYTHRIL_DEEP:
            if not self._guided_analyzer:
                raise RuntimeError("GuidedAnalyzer not initialized")

            result = await self._guided_analyzer.analyze(
                source_files=sources,
                functions_to_test=data.get("functions"),
                timeout=timeout,
                depth=data.get("depth", 42),
                use_slither_guide=data.get("use_slither_guide", True),
                use_custom_plugins=data.get("use_custom_plugins", True),
            )
            return result

        # ── Standard analysis (backward compatible) ──
        elif capability == AgentCapability.RUN_SYMBOLIC:
            import json
            import subprocess
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                for file_path, source_code in sources.items():
                    target = tmp_path / file_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(source_code, encoding="utf-8")

                start = time.monotonic()
                try:
                    result = await asyncio.to_thread(
                        subprocess.run,
                        ["mythril", "analyze",
                         "--solc-json", str(tmp_path / "combined.json"),
                         "--max-depth", str(data.get("depth", 32))],
                        capture_output=True, text=True,
                        timeout=timeout,
                        cwd=str(tmp_path),
                    )
                    elapsed = time.monotonic() - start
                    success = result.returncode == 0

                    # Try to parse JSON findings
                    findings = []
                    if success and result.stdout:
                        try:
                            parsed = json.loads(result.stdout)
                            findings = parsed.get("issues", parsed if isinstance(parsed, list) else [])
                        except json.JSONDecodeError:
                            pass

                    return {
                        "findings": findings,
                        "total_findings": len(findings),
                        "raw_output": result.stdout[-5000:] if result.stdout else "",
                        "raw_error": result.stderr[-1000:] if result.stderr else "",
                        "success": success,
                        "mythril_available": True,
                        "duration_seconds": round(elapsed, 2),
                    }
                except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
                    elapsed = time.monotonic() - start
                    return {
                        "findings": [],
                        "total_findings": 0,
                        "error": str(exc),
                        "success": False,
                        "mythril_available": isinstance(exc, subprocess.TimeoutExpired),
                        "duration_seconds": round(elapsed, 2),
                    }
        else:
            raise ValueError(f"Unknown capability: {capability}")
