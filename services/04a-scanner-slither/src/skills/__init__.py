"""04a-Scanner-Slither Skills — Slither static analysis with quality pipeline."""
from typing import Any

from shared.skills.op_skills import (
    AlgorithmAnalyzerSkill,
    ComplexityAnalyzerSkill,
    DataStructureOptimizerSkill,
    MathVerifierSkill,
)

from .interpret_slither import InterpretSlitherSkill
from .run_slither import RunSlitherSkill


def create_registry(
    runner: Any = None,
    pipeline: Any = None,
    classifier: Any = None,
) -> Any:
    """Create skill registry with optional runner/pipeline dependencies.

    Args:
        runner: Optional SlitherRunner instance for real execution.
        pipeline: Optional QualityPipeline for post-processing.
        classifier: Optional ContractClassifier for contract type detection.

    Returns:
        Configured SkillRegistry.
    """
    from shared.skills.skill_registry import SkillRegistry
    registry = SkillRegistry()
    registry.register(RunSlitherSkill(runner=runner, pipeline=pipeline, classifier=classifier))
    registry.register(InterpretSlitherSkill())
    registry.register(AlgorithmAnalyzerSkill())
    registry.register(MathVerifierSkill())
    registry.register(ComplexityAnalyzerSkill())
    registry.register(DataStructureOptimizerSkill())
    return registry


__all__ = ["RunSlitherSkill", "InterpretSlitherSkill", "create_registry"]
