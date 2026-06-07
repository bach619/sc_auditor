"""03-Source Agent Skills — Source code intelligence and analysis."""
from shared.skills.op_skills import (
    AlgorithmAnalyzerSkill,
    ComplexityAnalyzerSkill,
    DataStructureOptimizerSkill,
    MathVerifierSkill,
)

from .analyze_dependencies import AnalyzeDependenciesSkill
from .detect_upgrades import DetectUpgradesSkill
from .fetch_source import FetchSourceSkill


def create_registry():
    from shared.skills.skill_registry import SkillRegistry
    registry = SkillRegistry()
    # Domain skills
    registry.register(FetchSourceSkill())
    registry.register(AnalyzeDependenciesSkill())
    registry.register(DetectUpgradesSkill())
    # Overpower skills
    registry.register(AlgorithmAnalyzerSkill())
    registry.register(MathVerifierSkill())
    registry.register(ComplexityAnalyzerSkill())
    registry.register(DataStructureOptimizerSkill())
    return registry

__all__ = [
    "FetchSourceSkill", "AnalyzeDependenciesSkill", "DetectUpgradesSkill",
    "create_registry",
]
