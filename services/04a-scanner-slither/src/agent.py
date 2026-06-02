"""SlitherAgent — Backend Agent for Slither static analysis with quality pipeline.

Receives delegations from Antonio, runs Slither static analysis
on Solidity/Vyper source code, and returns findings enriched through
the full quality pipeline:

  FP Pattern Match → Noise Filter → AI Verify → Score → Rank → Enrich

Pipeline integrates:
  - L5: AI Verification (06-AI) for context-aware TP/FP classification
  - L6: FP Pattern Matching (known false-positive signatures)
  - L7: Quality Pipeline (end-to-end post-processing)
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
from shared.skills.skill_registry import SkillRegistry

from src.slither import SlitherRunner
from src.intelligence.classifier import ContractClassifier, ContractType
from src.intelligence.pipeline import QualityPipeline, PipelineStage, create_pipeline
from src.intelligence.fp_db import FalsePositiveDB
from src.intelligence.scorer import CompositeScorer
from .skills import create_registry


class SlitherAgent(BaseAgent):
    """Backend Agent for Slither static analysis with quality pipeline."""

    def __init__(
        self,
        runner: SlitherRunner,
        pipeline: QualityPipeline | None = None,
        classifier: ContractClassifier | None = None,
    ) -> None:
        self._runner = runner
        self._classifier = classifier or ContractClassifier()
        self._pipeline = pipeline
        self.skill_registry = create_registry(
            runner=runner,
            pipeline=pipeline,
            classifier=self._classifier,
        )
        super().__init__(
            service_name="04a-scanner-slither",
            agent_role="slither_analyzer",
            version="0.3.0",
            skill_registry=self.skill_registry,
        )
        self._max_concurrent = 3

        self.register_capability(CapabilityDefinition(
            name=AgentCapability.RUN_STATIC_ANALYSIS,
            description="Run Slither static analysis with quality pipeline on Solidity/Vyper source code",
            input_schema={
                "type": "object",
                "properties": {
                    "sources": {"type": "object", "description": "Source files keyed by path"},
                    "contract_address": {"type": "string"},
                    "chain": {"type": "string"},
                    "compiler": {"type": "string"},
                    "config_tier": {"type": "string"},
                    "timeout": {"type": "integer"},
                    "enable_pipeline": {
                        "type": "boolean",
                        "description": "Enable quality post-processing pipeline",
                        "default": True,
                    },
                    "enable_ai_verify": {
                        "type": "boolean",
                        "description": "Enable AI verification (calls 06-AI)",
                        "default": True,
                    },
                    "min_quality_score": {
                        "type": "number",
                        "description": "Minimum quality score to keep finding",
                        "default": 10.0,
                    },
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "findings": {"type": "array"},
                    "total_findings": {"type": "integer"},
                    "total_raw": {"type": "integer"},
                    "total_dropped": {"type": "integer"},
                    "contract_type": {"type": "string"},
                    "quality_report": {"type": "object"},
                    "duration_seconds": {"type": "number"},
                },
            },
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        capability = request.capability
        data = request.input_data

        if capability == AgentCapability.RUN_STATIC_ANALYSIS:
            sources = data.get("sources", {})
            if not sources:
                raise ValueError("At least one source file is required")

            enable_pipeline = data.get("enable_pipeline", True)
            enable_ai_verify = data.get("enable_ai_verify", True)
            min_quality_score = data.get("min_quality_score", 10.0)
            contract_address = data.get("contract_address", "")
            contract_name = data.get("contract_name", "")
            compiler = data.get("compiler", "")

            audit_id = uuid.uuid4().hex[:12]
            audit_dir = Path(f"/tmp/slither_agent_{audit_id}")
            audit_dir.mkdir(parents=True, exist_ok=True)

            try:
                for file_path, source_code in sources.items():
                    target = audit_dir / file_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(source_code, encoding="utf-8")

                start = time.monotonic()

                # 1. Classify contract type
                contract_type = ContractType.UNKNOWN
                try:
                    contract_type, _ = await self._classifier.classify(
                        sources, address=contract_address or None,
                    )
                except Exception as exc:
                    self.log.warning("agent.classify_failed", error=str(exc))

                # 2. Run Slither
                result = await asyncio.to_thread(
                    self._runner.run,
                    audit_dir,
                    config={"detectors": data.get("detectors", None)},
                    timeout=data.get("timeout", 600),
                )

                findings = result.findings or []
                finding_dicts = [
                    {
                        "title": f.title,
                        "severity": f.severity,
                        "description": f.description or "",
                        "contract": f.contract or "",
                        "line": f.line,
                        "recommendation": f.recommendation or "",
                    }
                    for f in findings
                ]

                # 3. Run quality pipeline (if enabled)
                quality_report = None
                if enable_pipeline and self._pipeline and finding_dicts:
                    enabled = {
                        PipelineStage.FP_PATTERN,
                        PipelineStage.NOISE_FILTER,
                        PipelineStage.SCORE,
                        PipelineStage.RANK,
                        PipelineStage.ENRICH,
                    }
                    if enable_ai_verify:
                        enabled.add(PipelineStage.AI_VERIFY)

                    self._pipeline._enable_stages = enabled
                    self._pipeline._min_quality_score = min_quality_score

                    try:
                        quality_report = await self._pipeline.run(
                            findings=finding_dicts,
                            source_code=sources,
                            contract_type=contract_type,
                            contract_address=contract_address,
                            contract_name=contract_name,
                            compiler=compiler,
                            audit_id=audit_id,
                        )
                    except Exception as exc:
                        self.log.error("agent.pipeline_failed", error=str(exc))

                elapsed = time.monotonic() - start

                # Build response
                if quality_report:
                    relevant_findings = [f.to_output() for f in quality_report.relevant_findings]
                    response = {
                        "findings": relevant_findings,
                        "total_findings": len(relevant_findings),
                        "total_raw": quality_report.total_raw_findings,
                        "total_dropped": quality_report.total_dropped,
                        "drop_rate_pct": quality_report.drop_rate,
                        "success": result.success,
                        "contract_type": contract_type.value,
                        "contract_address": contract_address,
                        "quality_report": quality_report.to_dict(),
                        "duration_seconds": round(elapsed, 2),
                    }
                else:
                    response = {
                        "findings": finding_dicts,
                        "total_findings": len(finding_dicts),
                        "total_raw": len(finding_dicts),
                        "total_dropped": 0,
                        "success": result.success,
                        "contract_type": contract_type.value,
                        "duration_seconds": round(elapsed, 2),
                    }

                self.log.info(
                    "agent.scan.complete",
                    audit_id=audit_id,
                    total=response["total_findings"],
                    raw=response["total_raw"],
                    dropped=response["total_dropped"],
                    contract_type=contract_type.value,
                    duration=round(elapsed, 2),
                )

                return response

            finally:
                shutil.rmtree(audit_dir, ignore_errors=True)
        else:
            raise ValueError(f"Unknown capability: {capability}")
