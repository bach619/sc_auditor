"""07-classifier — Bug Classification Skills."""
from shared.skills.op_skills import (
    AlgorithmAnalyzerSkill,
    MathVerifierSkill,
    ComplexityAnalyzerSkill,
    DataStructureOptimizerSkill,
)
from .classify_finding import ClassifyFindingSkill
from .analyze_patterns import AnalyzePatternsSkill
from .compute_metrics import ComputeMetricsSkill

def create_registry():
    from shared.skills.skill_registry import SkillRegistry
    registry = SkillRegistry()
    registry.register(ClassifyFindingSkill())
    registry.register(AnalyzePatternsSkill())
    registry.register(ComputeMetricsSkill())
    # OP skills
    registry.register(AlgorithmAnalyzerSkill())
    registry.register(MathVerifierSkill())
    registry.register(ComplexityAnalyzerSkill())
    registry.register(DataStructureOptimizerSkill())
    return registry

__all__ = ["ClassifyFindingSkill", "AnalyzePatternsSkill", "ComputeMetricsSkill", "create_registry"]
