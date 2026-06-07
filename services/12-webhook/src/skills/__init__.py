"""12-webhook — Webhook Notifications Skills."""
from shared.skills.op_skills import (
    AlgorithmAnalyzerSkill,
    ComplexityAnalyzerSkill,
    DataStructureOptimizerSkill,
    MathVerifierSkill,
)

from .analyze_logs import AnalyzeLogsSkill
from .deliver_webhook import DeliverWebhookSkill
from .manage_endpoints import ManageEndpointsSkill


def create_registry():
    from shared.skills.skill_registry import SkillRegistry
    registry = SkillRegistry()
    registry.register(DeliverWebhookSkill())
    registry.register(ManageEndpointsSkill())
    registry.register(AnalyzeLogsSkill())
    # OP skills
    registry.register(AlgorithmAnalyzerSkill())
    registry.register(MathVerifierSkill())
    registry.register(ComplexityAnalyzerSkill())
    registry.register(DataStructureOptimizerSkill())
    return registry

__all__ = ["DeliverWebhookSkill", "ManageEndpointsSkill", "AnalyzeLogsSkill", "create_registry"]
