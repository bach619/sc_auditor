"""05-scanner-mythril — Mythril Analysis Skills."""
from shared.skills.op_skills import (
    AlgorithmAnalyzerSkill,
    MathVerifierSkill,
    ComplexityAnalyzerSkill,
    DataStructureOptimizerSkill,
)
from .run_mythril_standard import RunMythrilStandardSkill
from .run_mythril_deep import RunMythrilDeepSkill
from .explain_finding import ExplainFindingSkill

def create_registry():
    from shared.skills.skill_registry import SkillRegistry
    registry = SkillRegistry()
    registry.register(RunMythrilStandardSkill())
    registry.register(RunMythrilDeepSkill())
    registry.register(ExplainFindingSkill())
    # OP skills
    registry.register(AlgorithmAnalyzerSkill())
    registry.register(MathVerifierSkill())
    registry.register(ComplexityAnalyzerSkill())
    registry.register(DataStructureOptimizerSkill())
    return registry

__all__ = ["RunMythrilStandardSkill", "RunMythrilDeepSkill", "ExplainFindingSkill", "create_registry"]
