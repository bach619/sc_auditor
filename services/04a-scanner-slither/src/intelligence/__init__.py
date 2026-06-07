"""Intelligence Engine for Slither Scanner Service.

Provides context-aware analysis, composite scoring, exploit path prediction,
auto-fix generation, natural language query, AI verification, FP pattern
matching, and end-to-end quality pipeline.

Levels:
  L2 — Contract Classifier + Smart Detector Selection
  L3 — FP/TP Database (self-learning from feedback)
  L4 — Composite Risk Scoring, Exploit Path Prediction, Auto-Fix, NLP
  L5 — AI Verification (06-AI integration)
  L6 — FP Pattern Matching (known false-positive signatures)
  L7 — Quality Pipeline (end-to-end post-processing)
"""

from src.intelligence.ai_verifier import AIVerificationResult, AIVerifier, create_ai_verifier
from src.intelligence.classifier import ContractClassifier, ContractType, create_classifier
from src.intelligence.fixer import FixGenerator, create_fixer
from src.intelligence.fp_db import FalsePositiveDB, create_fp_db
from src.intelligence.fp_patterns import (
    KNOWN_FP_PATTERNS,
    FalsePositivePattern,
    FpMatchResult,
    FpPatternMatcher,
    create_fp_pattern_matcher,
)
from src.intelligence.nlp import NaturalLanguageQuery, create_nlp
from src.intelligence.path_predictor import ExploitPathPredictor, create_path_predictor
from src.intelligence.pipeline import (
    PipelineStage,
    ProcessedFinding,
    QualityPipeline,
    QualityReport,
    create_pipeline,
)
from src.intelligence.scorer import CompositeScorer, RiskScore, create_scorer

__all__ = [
    "AIVerifier",
    "AIVerificationResult",
    "CompositeScorer",
    "ContractClassifier",
    "ContractType",
    "ExploitPathPredictor",
    "FalsePositiveDB",
    "FalsePositivePattern",
    "FixGenerator",
    "FpMatchResult",
    "FpPatternMatcher",
    "KNOWN_FP_PATTERNS",
    "NaturalLanguageQuery",
    "PipelineStage",
    "ProcessedFinding",
    "QualityPipeline",
    "QualityReport",
    "RiskScore",
    "create_ai_verifier",
    "create_classifier",
    "create_fixer",
    "create_fp_db",
    "create_fp_pattern_matcher",
    "create_nlp",
    "create_path_predictor",
    "create_pipeline",
    "create_scorer",
]
