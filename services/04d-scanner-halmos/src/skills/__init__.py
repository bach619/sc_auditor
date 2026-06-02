"""04d-Scanner-Halmos Skills — Halmos symbolic testing."""
from shared.skills.op_skills import (
    AlgorithmAnalyzerSkill,
    MathVerifierSkill,
    ComplexityAnalyzerSkill,
    DataStructureOptimizerSkill,
)
from .run_halmos import RunHalmosSkill
from .interpret_halmos import InterpretHalmosSkill

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
