"""04e-Scanner-Manticore Skills — Manticore symbolic execution."""
from shared.skills.op_skills import (
    AlgorithmAnalyzerSkill,
    ComplexityAnalyzerSkill,
    DataStructureOptimizerSkill,
    MathVerifierSkill,
)

from .confirm_finding import ConfirmFindingSkill
from .interpret_manticore import InterpretManticoreSkill
from .run_manticore import RunManticoreSkill


def create_registry():
    from shared.skills.skill_registry import SkillRegistry
    registry = SkillRegistry()
    registry.register(RunManticoreSkill())
    registry.register(ConfirmFindingSkill())
    registry.register(InterpretManticoreSkill())
    registry.register(AlgorithmAnalyzerSkill())
    registry.register(MathVerifierSkill())
    registry.register(ComplexityAnalyzerSkill())
    registry.register(DataStructureOptimizerSkill())
    return registry

__all__ = ["RunManticoreSkill", "ConfirmFindingSkill", "InterpretManticoreSkill", "create_registry"]
