"""04d-Scanner-Halmos Skills — Halmos symbolic testing."""
from shared.skills.op_skills import (
    AlgorithmAnalyzerSkill,
    ComplexityAnalyzerSkill,
    DataStructureOptimizerSkill,
    MathVerifierSkill,
)

from .interpret_halmos import InterpretHalmosSkill
from .run_halmos import RunHalmosSkill


def create_registry():
    from shared.skills.skill_registry import SkillRegistry
    registry = SkillRegistry()
    registry.register(RunHalmosSkill())
    registry.register(InterpretHalmosSkill())
    registry.register(AlgorithmAnalyzerSkill())
    registry.register(MathVerifierSkill())
    registry.register(ComplexityAnalyzerSkill())
    registry.register(DataStructureOptimizerSkill())
    return registry

__all__ = ["RunHalmosSkill", "InterpretHalmosSkill", "create_registry"]
