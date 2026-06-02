"""16-submission — Submission Assistant Skills."""
from shared.skills.op_skills import (
    AlgorithmAnalyzerSkill,
    MathVerifierSkill,
    ComplexityAnalyzerSkill,
    DataStructureOptimizerSkill,
)
from .create_submission import CreateSubmissionSkill
from .generate_draft import GenerateDraftSkill
from .collect_evidence import CollectEvidenceSkill

def create_registry():
    from shared.skills.skill_registry import SkillRegistry
    registry = SkillRegistry()
    registry.register(CreateSubmissionSkill())
    registry.register(GenerateDraftSkill())
    registry.register(CollectEvidenceSkill())
    # OP skills
    registry.register(AlgorithmAnalyzerSkill())
    registry.register(MathVerifierSkill())
    registry.register(ComplexityAnalyzerSkill())
    registry.register(DataStructureOptimizerSkill())
    return registry

__all__ = ["CreateSubmissionSkill", "GenerateDraftSkill", "CollectEvidenceSkill", "create_registry"]
