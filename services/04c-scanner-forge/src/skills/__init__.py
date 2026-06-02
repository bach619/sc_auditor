"""04c-Scanner-Forge Skills — Forge build verification."""
from shared.skills.op_skills import (
    AlgorithmAnalyzerSkill,
    MathVerifierSkill,
    ComplexityAnalyzerSkill,
    DataStructureOptimizerSkill,
)
from .run_forge import RunForgeSkill
from .analyze_build_errors import AnalyzeBuildErrorsSkill

def create_registry():
    from shared.skills.skill_registry import SkillRegistry
    registry = SkillRegistry()
    registry.register(RunForgeSkill())
    registry.register(AnalyzeBuildErrorsSkill())
    registry.register(AlgorithmAnalyzerSkill())
    registry.register(MathVerifierSkill())
    registry.register(ComplexityAnalyzerSkill())
    registry.register(DataStructureOptimizerSkill())
    return registry

__all__ = ["RunForgeSkill", "AnalyzeBuildErrorsSkill", "create_registry"]
