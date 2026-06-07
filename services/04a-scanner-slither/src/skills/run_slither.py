"""Run Slither Skill — executes Slither analysis with quality pipeline.

Runs Slither CLI, then passes findings through the full quality pipeline:
FP Pattern Match → Noise Filter → AI Verify → Score → Rank → Enrich.
"""

from pathlib import Path

import structlog
from shared.skills.base_skill import BaseSkill

from src.intelligence.classifier import ContractClassifier, ContractType
from src.intelligence.pipeline import QualityPipeline
from src.slither import SlitherRunner

log = structlog.get_logger()


class RunSlitherSkill(BaseSkill):
    """Execute Slither analysis with quality pipeline post-processing."""

    def __init__(
        self,
        runner: SlitherRunner | None = None,
        pipeline: QualityPipeline | None = None,
        classifier: ContractClassifier | None = None,
    ) -> None:
        self._runner = runner
        self._pipeline = pipeline
        self._classifier = classifier or ContractClassifier()

    @property
    def name(self) -> str:
        return "run_slither"

    @property
    def description(self) -> str:
        return (
            "Run Slither static analysis on Solidity source code with "
            "full quality pipeline: FP filtering, AI verification, "
            "risk scoring, ranking, and enrichment"
        )

    @property
    def category(self) -> str:
        return "static_analysis"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "object",
                    "description": "Source files keyed by path",
                },
                "config_tier": {
                    "type": "string",
                    "description": "Configuration tier (basic, standard, deep)",
                    "enum": ["basic", "standard", "deep"],
                },
                "contract_address": {"type": "string", "description": "Contract address for FP DB"},
                "contract_name": {"type": "string", "description": "Contract name"},
                "compiler": {"type": "string", "description": "Solidity compiler version"},
                "timeout": {"type": "integer", "description": "Analysis timeout in seconds"},
                "enable_ai_verify": {
                    "type": "boolean",
                    "description": "Enable AI verification stage",
                    "default": True,
                },
                "min_quality_score": {
                    "type": "number",
                    "description": "Minimum quality score to keep finding (0-100)",
                    "default": 10.0,
                },
            },
            "required": ["sources"],
        }

    async def run(self, **kwargs) -> dict:
        """Run Slither analysis with quality pipeline.

        Args:
            sources: Dict of file path → source code.
            config_tier: Analysis tier (basic, standard, deep).
            contract_address: Optional contract address.
            contract_name: Optional contract name.
            compiler: Solidity compiler version.
            timeout: Analysis timeout in seconds.
            enable_ai_verify: Whether to call 06-AI for verification.
            min_quality_score: Minimum quality score threshold.

        Returns:
            Dict with findings, quality_report, and metadata.
        """
        sources: dict[str, str] = kwargs.get("sources", {})
        config_tier: str = kwargs.get("config_tier", "standard")
        contract_address: str = kwargs.get("contract_address", "")
        contract_name: str = kwargs.get("contract_name", "")
        compiler: str = kwargs.get("compiler", "")
        timeout: int = kwargs.get("timeout", 600)
        enable_ai_verify: bool = kwargs.get("enable_ai_verify", True)
        min_quality_score: float = kwargs.get("min_quality_score", 10.0)

        if not sources:
            return {
                "skill": self.name,
                "confidence": 1.0,
                "result": {"error": "No source files provided", "findings": []},
            }

        # Classify contract type
        contract_type = ContractType.UNKNOWN
        try:
            contract_type, _ = await self._classifier.classify(sources)
        except Exception as exc:
            log.warning("run_slither.classify_failed", error=str(exc))

        # Run Slither
        if self._runner:
            import asyncio
            import tempfile

            audit_dir = Path(tempfile.mkdtemp(prefix="slither_skill_"))
            try:
                for file_path, source_code in sources.items():
                    target = audit_dir / file_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(source_code, encoding="utf-8")

                result = await asyncio.to_thread(
                    self._runner.run,
                    audit_dir,
                    config={"tier": config_tier},
                    timeout=timeout,
                )
            finally:
                import shutil
                shutil.rmtree(audit_dir, ignore_errors=True)
        else:
            return {
                "skill": self.name,
                "confidence": 0.5,
                "result": {"error": "No runner configured", "findings": []},
            }

        if not result.success:
            return {
                "skill": self.name,
                "confidence": 0.0,
                "result": {
                    "error": result.error or "Analysis failed",
                    "findings": [],
                },
            }

        # Convert findings to dicts
        finding_dicts = [
            {
                "title": f.title,
                "severity": f.severity,
                "description": f.description or "",
                "contract": f.contract or "",
                "line": f.line,
                "recommendation": f.recommendation or "",
            }
            for f in (result.findings or [])
        ]

        # Run quality pipeline
        pipeline = self._pipeline
        quality_report = None
        if pipeline:
            from src.intelligence.pipeline import PipelineStage

            enabled_stages = {PipelineStage.FP_PATTERN, PipelineStage.NOISE_FILTER,
                              PipelineStage.SCORE, PipelineStage.RANK, PipelineStage.ENRICH}
            if enable_ai_verify:
                enabled_stages.add(PipelineStage.AI_VERIFY)

            pipeline._enable_stages = enabled_stages
            pipeline._min_quality_score = min_quality_score

            try:
                quality_report = await pipeline.run(
                    findings=finding_dicts,
                    source_code=sources,
                    contract_type=contract_type,
                    contract_address=contract_address,
                    contract_name=contract_name,
                    compiler=compiler,
                )
            except Exception as exc:
                log.error("run_slither.pipeline_failed", error=str(exc))

        # Build result
        if quality_report:
            relevant = [f.to_output() for f in quality_report.relevant_findings]
            report_dict = quality_report.to_dict()
        else:
            relevant = finding_dicts
            report_dict = {"total_raw_findings": len(finding_dicts), "total_relevant": len(finding_dicts)}

        return {
            "skill": self.name,
            "confidence": 0.95 if quality_report and quality_report.overall_quality > 50 else 0.7,
            "result": {
                "findings": relevant,
                "total_findings": len(relevant),
                "total_raw": len(finding_dicts),
                "quality_report": report_dict,
                "contract_type": contract_type.value,
                "duration_seconds": result.duration_seconds,
            },
        }
