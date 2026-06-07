"""Natural Language Query — L4 Intelligence.

Provides a simple NLP endpoint for users to ask questions about
scan results in plain English.

Since this is an offline/on-prem system without cloud LLM dependency,
this module uses rule-based intent classification and template-based
response generation.

Architecture:
  1. Intent classification via keyword matching + regex
  2. Entity extraction (detector names, severity levels, etc.)
  3. Response template selection based on intent + entities
  4. Optional: local LLM integration via plugin (future)

Supported intents:
  - "what are the critical findings?" → filter by severity
  - "show me reentrancy issues" → filter by detector
  - "how do I fix this?" → link to fixer
  - "summary" → overall risk summary
  - "is this contract safe?" → qualitative assessment
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from src.intelligence.classifier import ContractClassifier
from src.intelligence.fixer import FixGenerator
from src.intelligence.scorer import CompositeScorer

log = structlog.get_logger()


# ── Intent Patterns ─────────────────────────────────────────
# Each intent has: keywords, response template, and required context

INTENT_PATTERNS: list[dict[str, Any]] = [
    {
        "intent": "summary",
        "keywords": ["summary", "overview", "overall", "report", "result"],
        "description": "Get a summary of all findings",
    },
    {
        "intent": "critical_findings",
        "keywords": ["critical", "dangerous", "worst", "severe", "emergency"],
        "description": "List critical/high severity findings",
    },
    {
        "intent": "filter_by_severity",
        "keywords": ["high", "medium", "low", "info", "informational"],
        "description": "Filter findings by specific severity",
    },
    {
        "intent": "filter_by_detector",
        "keywords": [
            "reentrancy", "delegatecall", "overflow", "underflow",
            "timestamp", "tx.origin", "unchecked", "phishing",
            "access", "control", "flash", "loan", "price",
        ],
        "description": "Filter findings by detector type",
    },
    {
        "intent": "how_to_fix",
        "keywords": ["fix", "repair", "solve", "remediate", "patch", "how to"],
        "description": "Get fix suggestions",
    },
    {
        "intent": "safety",
        "keywords": ["safe", "secure", "production", "deploy", "ready", "risk"],
        "description": "Assess overall contract safety",
    },
    {
        "intent": "exploit_path",
        "keywords": ["exploit", "attack", "hack", "chain", "path", "scenario"],
        "description": "Show exploit paths",
    },
    {
        "intent": "classify",
        "keywords": ["what is this", "type", "category", "kind", "classify"],
        "description": "Classify the contract type",
    },
]


SEVERITY_MAP: dict[str, str] = {
    "dangerous": "critical",
    "critical": "critical",
    "severe": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "info": "informational",
    "informational": "informational",
}


class NaturalLanguageQuery:
    """Process natural language queries about scan results."""

    def __init__(
        self,
        classifier: ContractClassifier | None = None,
        scorer: CompositeScorer | None = None,
        fixer: FixGenerator | None = None,
    ) -> None:
        self._classifier = classifier
        self._scorer = scorer
        self._fixer = fixer or FixGenerator()

    def ask(
        self,
        query: str,
        findings: list[dict[str, Any]],
        contract_type_label: str = "Unknown",
        aggregate_risk: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process a natural language query.

        Args:
            query: User's question in plain English.
            findings: List of finding dicts from scan.
            contract_type_label: Optional contract type label.
            aggregate_risk: Optional aggregate risk data.

        Returns:
            Dict with 'answer', 'intent', 'context', and 'findings'.
        """
        query_lower = query.lower().strip()
        context = self._build_context(findings, contract_type_label, aggregate_risk)

        # 1. Determine intent
        intent = self._classify_intent(query_lower)

        # 2. Extract entities
        severity_filter = self._extract_severity(query_lower)
        detector_filter = self._extract_detector(query_lower)

        # 3. Generate response
        if intent == "summary":
            answer, filtered = self._answer_summary(context)
        elif intent == "critical_findings":
            answer, filtered = self._answer_critical(context)
        elif intent == "filter_by_severity":
            if severity_filter:
                answer, filtered = self._answer_by_severity(context, severity_filter)
            else:
                answer, filtered = self._answer_critical(context)
        elif intent == "filter_by_detector":
            answer, filtered = self._answer_by_detector(context, detector_filter or query)
        elif intent == "how_to_fix":
            answer, filtered = self._answer_how_to_fix(context, detector_filter)
        elif intent == "safety":
            answer, filtered = self._answer_safety(context)
        elif intent == "exploit_path":
            answer, filtered = self._answer_exploit_path(context)
        elif intent == "classify":
            answer, filtered = self._answer_classify(context)
        else:
            answer, filtered = self._answer_fallback(context, query)

        return {
            "query": query,
            "intent": intent,
            "answer": answer,
            "context": {
                "total_findings": context["total_findings"],
                "contract_type": contract_type_label,
                "severity_filter": severity_filter,
                "detector_filter": detector_filter,
            },
            "findings": filtered,
            "follow_up_questions": self._generate_follow_ups(intent, context),
        }

    # ── Intent Classification ───────────────────────────────

    def _classify_intent(self, query: str) -> str:
        """Classify the user's intent from their query."""
        scores: dict[str, int] = {}
        for pattern in INTENT_PATTERNS:
            score = sum(1 for kw in pattern["keywords"] if kw in query)
            if score > 0:
                scores[pattern["intent"]] = score

        if not scores:
            return "unknown"

        # Return intent with highest keyword match count
        return max(scores, key=scores.get)  # type: ignore[arg-type]

    # ── Entity Extraction ───────────────────────────────────

    def _extract_severity(self, query: str) -> str | None:
        """Extract severity level from query."""
        for word, sev in SEVERITY_MAP.items():
            if word in query:
                return sev
        return None

    def _extract_detector(self, query: str) -> str | None:
        """Extract detector name from query."""
        detector_patterns = [
            (r"\breentran(cy|t)\b", "reentrancy"),
            (r"\bdelegatecall\b", "controlled-delegatecall"),
            (r"\btx\.?origin\b", "tx-origin"),
            (r"\btimestamp\b", "timestamp"),
            (r"\bunchecked\b", "unchecked-lowlevel"),
            (r"\boverflow\b", "overflow"),
            (r"\bunderflow\b", "underflow"),
            (r"\baccess.?control\b", "access-control"),
            (r"\bphishing\b", "tx-origin"),
            (r"\bflash.?loan\b", "flash-loan"),
            (r"\bprice\b", "price-manipulation"),
        ]
        for pattern, detector in detector_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return detector
        return None

    # ── Answer Generators ────────────────────────────────────

    @staticmethod
    def _answer_summary(context: dict) -> tuple[str, list]:
        c = context
        return (
            f"I found **{c['total_findings']} findings** in this {c['contract_type_label']} contract. "
            f"Breakdown: **{c['critical_count']} critical**, **{c['high_count']} high**, "
            f"**{c['medium_count']} medium**, **{c['low_count']} low**, "
            f"**{c['info_count']} informational**. "
            f"Overall risk: **{c.get('overall_risk_label', c['risk_label']).upper()}**.",
            c["all_findings"],
        )

    @staticmethod
    def _answer_critical(context: dict) -> tuple[str, list]:
        critical = [
            f for f in context["all_findings"]
            if f.get("severity", "").lower() in ("critical", "high")
        ]
        if not critical:
            return "✅ No critical or high-severity findings. The code looks clean.", []

        lines = [f"🔴 Found **{len(critical)} critical/high issues**:"]
        for i, f in enumerate(critical[:10], 1):
            lines.append(f"  {i}. **{f.get('title', 'Unknown')}** ({f.get('severity', '?')})")
        if len(critical) > 10:
            lines.append(f"  ... and {len(critical) - 10} more.")
        return "\n".join(lines), critical

    @staticmethod
    def _answer_by_severity(context: dict, severity: str) -> tuple[str, list]:
        filtered = [
            f for f in context["all_findings"]
            if f.get("severity", "").lower() == severity.lower()
        ]
        if not filtered:
            return f"No {severity} findings found.", []
        lines = [f"Found **{len(filtered)} {severity}** findings:"]
        for i, f in enumerate(filtered[:15], 1):
            lines.append(f"  {i}. {f.get('title', 'Unknown')}")
        return "\n".join(lines), filtered

    @staticmethod
    def _answer_by_detector(context: dict, detector_hint: str) -> tuple[str, list]:
        hint_lower = detector_hint.lower()
        filtered = [
            f for f in context["all_findings"]
            if hint_lower in f.get("title", "").lower()
        ]
        if not filtered:
            return f"No findings matching '{detector_hint}' found.", []
        lines = [f"Found **{len(filtered)}** findings matching '{detector_hint}':"]
        for i, f in enumerate(filtered[:15], 1):
            lines.append(
                f"  {i}. {f.get('title', 'Unknown')} ({f.get('severity', '?')})"
            )
        return "\n".join(lines), filtered

    def _answer_how_to_fix(
        self, context: dict, detector_filter: str | None
    ) -> tuple[str, list]:
        """Answer with fix suggestions."""
        if detector_filter:
            findings = [
                f for f in context["all_findings"]
                if detector_filter in f.get("title", "").lower()
            ]
        else:
            findings = context["all_findings"][:3]

        if not findings:
            return "No issues found. Nothing to fix!", []

        fixes = self._fixer.generate_fixes(findings, context.get("contract_name", ""))

        lines = ["Here are fix suggestions for the detected issues:\n"]
        for detector, fix_list in fixes.items():
            for fix in fix_list:
                lines.append(f"### {detector}")
                lines.append(fix.get("description", ""))
                if fix.get("solidity_example"):
                    lines.append(f"\nExample fix:\n```solidity\n{fix['solidity_example']}\n```")
                lines.append("")

        return "\n".join(lines), findings

    @staticmethod
    def _answer_safety(context: dict) -> tuple[str, list]:
        """Answer whether the contract is safe to deploy."""
        total = context["total_findings"]
        critical = context["critical_count"]
        high = context["high_count"]
        label = context.get("overall_risk_label", context["risk_label"])

        if label == "critical" or critical > 0:
            verdict = "🚨 **NOT SAFE FOR PRODUCTION**"
            explanation = (
                f"Found {critical} critical and {high} high-severity issues. "
                "These vulnerabilities can lead to fund loss or contract compromise. "
                "Do not deploy until all critical and high issues are resolved."
            )
        elif label == "high" or high > 2:
            verdict = "⚠️ **CAUTION — Review Required**"
            explanation = (
                f"Found {high} high-severity issues. While not immediately critical, "
                "these may be chained for significant impact. Review before deployment."
            )
        elif total > 10:
            verdict = "⚠️ **MODERATE RISK**"
            explanation = (
                f"Found {total} findings. High volume suggests code quality issues. "
                "Review medium+ findings before deploying."
            )
        else:
            verdict = "✅ **LOW RISK — Looks Good**"
            explanation = (
                f"Only {total} findings, none critical. "
                "The contract appears reasonably safe for deployment. "
                "Standard audits recommended for high-value contracts."
            )

        return f"### {verdict}\n\n{explanation}", context["all_findings"]

    @staticmethod
    def _answer_exploit_path(context: dict) -> tuple[str, list]:
        """Answer with exploit path analysis."""
        paths = context.get("exploit_paths", [])
        if not paths:
            return (
                "No specific exploit chains identified. "
                "Individual findings should still be reviewed.",
                context["all_findings"],
            )

        lines = [f"Identified **{len(paths)}** potential exploit scenarios:\n"]
        for i, path in enumerate(paths[:5], 1):
            lines.append(f"### {i}. {path.get('name', 'Unknown')}")
            lines.append(f"Severity: **{path.get('severity', '?')}**")
            lines.append(f"Confidence: **{path.get('confidence', 0) * 100:.0f}%**")
            lines.append(f"Impact: {path.get('impact', '')}")
            lines.append("Steps:")
            for j, step in enumerate(path.get("steps", []), 1):
                lines.append(f"  {j}. {step}")
            lines.append("")

        return "\n".join(lines), context["all_findings"]

    @staticmethod
    def _answer_classify(context: dict) -> tuple[str, list]:
        """Answer with contract type classification."""
        ctype = context.get("contract_type_label", "Unknown")
        return (
            f"This contract is classified as **{ctype}** type.\n\n"
            "This classification is based on function signatures and import analysis.",
            context["all_findings"],
        )

    @staticmethod
    def _answer_fallback(context: dict, query: str) -> tuple[str, list]:
        """Fallback when no intent matches."""
        return (
            f"I understand you asked: \"{query}\"\n\n"
            "I can help with the following queries:\n"
            "- \"summary\" — Overview of all findings\n"
            "- \"critical issues\" — Show critical/high findings\n"
            "- \"how do I fix reentrancy?\" — Fix suggestions\n"
            "- \"is this contract safe?\" — Safety assessment\n"
            "- \"what type is this?\" — Contract classification\n"
            "- \"exploit paths\" — Attack chain analysis",
            context["all_findings"],
        )

    # ── Context Building ─────────────────────────────────────

    @staticmethod
    def _build_context(
        findings: list[dict[str, Any]],
        contract_type_label: str,
        aggregate_risk: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build context dict from findings and risk data."""
        if aggregate_risk is None:
            aggregate_risk = {}

        return {
            "total_findings": len(findings),
            "all_findings": findings,
            "critical_count": aggregate_risk.get("critical_count", 0),
            "high_count": aggregate_risk.get("high_count", 0),
            "medium_count": aggregate_risk.get("risk_distribution", {}).get("medium", 0) or 0,
            "low_count": aggregate_risk.get("risk_distribution", {}).get("low", 0) or 0,
            "info_count": aggregate_risk.get("risk_distribution", {}).get("info", 0) or 0,
            "risk_label": aggregate_risk.get("overall_risk_label", "unknown"),
            "overall_risk_label": aggregate_risk.get("overall_risk_label", "unknown"),
            "exploit_paths": aggregate_risk.get("exploit_paths", []),
            "contract_type_label": contract_type_label,
            "contract_name": "",
        }

    @staticmethod
    def _generate_follow_ups(intent: str, context: dict) -> list[str]:
        """Generate context-aware follow-up questions."""
        follow_ups = {
            "summary": [
                "Show me critical issues",
                "How do I fix the issues?",
                "Is this contract safe?",
            ],
            "critical_findings": [
                "How do I fix these?",
                "Show me exploit paths",
                "Is there a reentrancy issue?",
            ],
            "filter_by_severity": [
                "Show me the critical ones",
                "How do I fix these?",
            ],
            "filter_by_detector": [
                "How do I fix this?",
                "Show me the exploit scenario",
            ],
            "how_to_fix": [
                "Show me critical issues",
                "Is the contract safe now?",
            ],
            "safety": [
                "Show me what needs fixing",
                "Classify the contract type",
            ],
            "exploit_path": [
                "How do I prevent these attacks?",
                "Show me fix suggestions",
            ],
            "classify": [
                "Show me the findings",
                "Is this contract type risky?",
            ],
        }

        return follow_ups.get(intent, [
            "Show me the summary",
            "Is this contract safe?",
            "How do I fix issues?",
        ])


def create_nlp(
    classifier: ContractClassifier | None = None,
    scorer: CompositeScorer | None = None,
    fixer: FixGenerator | None = None,
) -> NaturalLanguageQuery:
    return NaturalLanguageQuery(classifier=classifier, scorer=scorer, fixer=fixer)
