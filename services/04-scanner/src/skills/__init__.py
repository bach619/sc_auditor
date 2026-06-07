"""04-Scanner Agent Skills — Smart contract scanning tools."""

from shared.skills.op_skills import (
    AlgorithmAnalyzerSkill,
    ComplexityAnalyzerSkill,
    DataStructureOptimizerSkill,
    MathVerifierSkill,
)

from .merge_findings import MergeFindingsSkill
from .run_echidna import RunEchidnaSkill
from .run_halmos import RunHalmosSkill
from .run_mythril import RunMythrilSkill
from .run_slither import RunSlitherSkill
from .select_tools import SelectToolsSkill


def create_registry():
    from shared.skills.skill_registry import SkillRegistry
    registry = SkillRegistry()
    registry.register(RunSlitherSkill())
    registry.register(RunMythrilSkill())
    registry.register(RunEchidnaSkill())
    registry.register(RunHalmosSkill())
    registry.register(SelectToolsSkill())
    registry.register(MergeFindingsSkill())
    registry.register(AlgorithmAnalyzerSkill())
    registry.register(MathVerifierSkill())
    registry.register(ComplexityAnalyzerSkill())
    registry.register(DataStructureOptimizerSkill())
    return registry

__all__ = [
    "RunSlitherSkill",
    "RunMythrilSkill",
    "RunEchidnaSkill",
    "RunHalmosSkill",
    "SelectToolsSkill",
    "MergeFindingsSkill",
    "create_registry",
]
