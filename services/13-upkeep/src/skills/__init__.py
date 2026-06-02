"""13-upkeep — Platform Maintenance Skills."""
from shared.skills.op_skills import (
    AlgorithmAnalyzerSkill,
    MathVerifierSkill,
    ComplexityAnalyzerSkill,
    DataStructureOptimizerSkill,
)
from .create_backup import CreateBackupSkill
from .aggregate_metrics import AggregateMetricsSkill
from .monitor_health import MonitorHealthSkill

def create_registry():
    from shared.skills.skill_registry import SkillRegistry
    registry = SkillRegistry()
    registry.register(CreateBackupSkill())
    registry.register(AggregateMetricsSkill())
    registry.register(MonitorHealthSkill())
    # OP skills
    registry.register(AlgorithmAnalyzerSkill())
    registry.register(MathVerifierSkill())
    registry.register(ComplexityAnalyzerSkill())
    registry.register(DataStructureOptimizerSkill())
    return registry

__all__ = ["CreateBackupSkill", "AggregateMetricsSkill", "MonitorHealthSkill", "create_registry"]
