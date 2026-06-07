"""04b-Scanner-Echidna Skills — Echidna fuzzing."""
from shared.skills.op_skills import (
    AlgorithmAnalyzerSkill,
    ComplexityAnalyzerSkill,
    DataStructureOptimizerSkill,
    MathVerifierSkill,
)

from .interpret_echidna import InterpretEchidnaSkill
from .run_echidna import RunEchidnaSkill


def create_registry():
    from shared.skills.skill_registry import SkillRegistry
    registry = SkillRegistry()
    registry.register(RunEchidnaSkill())
    registry.register(InterpretEchidnaSkill())
    registry.register(AlgorithmAnalyzerSkill())
    registry.register(MathVerifierSkill())
    registry.register(ComplexityAnalyzerSkill())
    registry.register(DataStructureOptimizerSkill())
    return registry

__all__ = ["RunEchidnaSkill", "InterpretEchidnaSkill", "create_registry"]
