"""Interpret Slither Skill — analyzes findings with full intelligence engine.

Processes raw findings through:
  1. FP Pattern Matching (known FP signatures)
  2. AI Verification (06-AI integration)
  3. Composite Risk Scoring
  4. Exploit Path Prediction
  5. Fix Generation
  6. Natural Language Summary
"""

from typing import Any

import structlog
from shared.skills.base_skill import BaseSkill

from src.intelligence.classifier import ContractType
from src.intelligence.fixer import FixGenerator
from src.intelligence.fp_patterns import FpPatternMatcher
from src.intelligence.nlp import NaturalLanguageQuery
from src.intelligence.path_predictor import ExploitPathPredictor
from src.intelligence.scorer import CompositeScorer

log = structlog.get_logger()


class InterpretSlitherSkill(BaseSkill):
    """Analyze, score, and enrich Slither findings with intelligence."""

    def __init__(
        self,
        fp_matcher: FpPatternMatcher | None = None,
        scorer: CompositeScorer | None = None,
        fixer: FixGenerator | None = None,
        path_predictor: ExploitPathPredictor | None = None,
        nlp: NaturalLanguageQuery | None = None,
    ) -> None:
        from src.intelligence.fixer import create_fixer
        from src.intelligence.fp_patterns import create_fp_pattern_matcher
        from src.intelligence.path_predictor import create_path_predictor
        from src.intelligence.scorer import create_scorer

        self._fp_matcher = fp_matcher or create_fp_pattern_matcher()
        self._scorer = scorer or create_scorer()
        self._fixer = fixer or create_fixer()
        self._path_predictor = path_predictor or create_path_predictor()
        self._nlp = nlp

    @property
    def name(self) -> str:
        return "interpret_slither"

    @property
    def description(self) -> str:
        return (
            "Analyze Slither findings with FP pattern matching, risk scoring, "
            "exploit path prediction, fix generation, and natural language query"
        )

    @property
    def category(self) -> str:
        return "static_analysis"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "findings": {
                    "type": "array",
                    "description": "Raw findings from Slither analysis",
                },
                "source_code": {
                    "type": "object",
                    "description": "Source files keyed by path (for FP matching)",
                },
                "contract_type": {
                    "type": "string",
                    "description": "Contract type for context-aware scoring",
                    "enum": [ct.value for ct in ContractType],
                },
                "contract_address": {"type": "string"},
                "contract_name": {"type": "string"},
                "query": {"type": "string", "description": "Natural language query about findings"},
            },
            "required": ["findings"],
        }

    async def run(self, **kwargs) -> dict:
        """Interpret findings through intelligence engine.

        Args:
            findings: Raw finding dicts from Slither.
            source_code: Source files for FP pattern matching.
            contract_type: Type of contract analyzed.
            contract_address: Contract address for FP DB lookup.
            contract_name: Contract name for fix personalization.
            query: Optional natural language query.

        Returns:
            Dict with enriched findings, exploit paths, fixes, NLP answer.
        """
        findings: list[dict[str, Any]] = kwargs.get("findings", [])
        source_code: dict[str, str] = kwargs.get("source_code", {})
        contract_type_str: str = kwargs.get("contract_type", "unknown")
        contract_address: str = kwargs.get("contract_address", "")
        contract_name: str = kwargs.get("contract_name", "")
        query: str = kwargs.get("query", "")

        if not findings:
            return {
                "skill": self.name,
                "confidence": 1.0,
                "result": {"message": "No findings to interpret"},
            }

        contract_type = ContractType.UNKNOWN
        try:
            contract_type = ContractType(contract_type_str)
        except ValueError:
            pass

        combined_source = "\n".join(source_code.values()) if source_code else ""
        results: dict[str, Any] = {
            "total_findings": len(findings),
            "enriched_findings": [],
            "exploit_paths": [],
            "fix_suggestions": {},
            "fp_pattern_matches": [],
        }

        # 1. FP Pattern Matching
        fp_matches = []
        for f in findings:
            match = self._fp_matcher.evaluate_finding(f, combined_source)
            if match.is_fp:
                fp_matches.append({
                    "finding": f.get("title", ""),
                    "pattern": match.pattern_name,
                    "description": match.description,
                })
        results["fp_pattern_matches"] = fp_matches

        # 2. Scoring
        scores = self._scorer.score_findings(
            findings,
            contract_type=contract_type,
            contract_address=contract_address or None,
        )
        results["scores"] = [
            {
                "title": s.finding_title,
                "severity": s.finding_severity,
                "normalized_score": s.normalized_score,
                "risk_label": s.risk_label,
                "priority": s.priority,
                "exploitability": s.exploitability,
                "historical_confidence": s.historical_confidence,
            }
            for s in scores
        ]

        # 3. Aggregate risk
        results["aggregate_risk"] = self._scorer.compute_aggregate_risk(scores)

        # 4. Exploit paths
        path_inputs = [
            {"title": s.finding_title, "severity": s.finding_severity}
            for s in scores[:20]
        ]
        exploit_paths = self._path_predictor.predict_paths(
            path_inputs,
            contract_type=contract_type.value,
        )
        results["exploit_paths"] = exploit_paths
        results["exploit_summary"] = self._path_predictor.summarize_risk(exploit_paths)

        # 5. Fix suggestions
        fixes = self._fixer.generate_fixes(findings, contract_name)
        results["fix_suggestions"] = fixes

        # 6. NLP query
        if query and self._nlp:
            nlp_result = self._nlp.ask(
                query=query,
                findings=findings,
                contract_type_label=contract_type.value,
                aggregate_risk=results["aggregate_risk"],
            )
            results["nlp_answer"] = nlp_result

        # 7. Enriched findings (attach scores + FP status)
        enriched = []
        for f in findings:
            title = f.get("title", "")
            enriched_finding = dict(f)
            # Add score
            for s in scores:
                if s.finding_title == title:
                    enriched_finding["risk_score"] = s.normalized_score
                    enriched_finding["risk_label"] = s.risk_label
                    enriched_finding["priority"] = s.priority
                    break
            # Add FP status
            for m in fp_matches:
                if m["finding"] == title:
                    enriched_finding["fp_pattern"] = m
                    enriched_finding["likely_fp"] = True
                    break
            enriched.append(enriched_finding)
        results["enriched_findings"] = enriched

        return {
            "skill": self.name,
            "confidence": 0.92,
            "result": results,
        }
