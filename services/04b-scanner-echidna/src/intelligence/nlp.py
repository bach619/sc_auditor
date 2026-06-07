"""Echidna Natural Language Query — L4 Intelligence.

Rule-based NLP untuk menjawab pertanyaan tentang hasil fuzzing.

Supported intents:
  - "summary" → overview of fuzzing results
  - "failures" → list all property violations
  - "show reentrancy" → filter by category
  - "how to fix?" → fix suggestions
  - "call sequence" → sequence analysis
"""

from __future__ import annotations

from typing import Any

from src.intelligence.classifier import EchidnaClassifier
from src.intelligence.fixer import EchidnaFixer

INTENTS: list[dict[str, Any]] = [
    {"intent": "summary", "keywords": ["summary", "overview", "overall", "result"]},
    {"intent": "failures", "keywords": ["failure", "fail", "violation", "broken", "property"]},
    {"intent": "critical", "keywords": ["critical", "worst", "severe", "dangerous"]},
    {"intent": "filter_category", "keywords": [
        "reentrancy", "access", "arithmetic", "overflow",
        "oracle", "flash", "fund", "loss",
    ]},
    {"intent": "how_to_fix", "keywords": ["fix", "repair", "solve", "how to", "remediate"]},
    {"intent": "sequence", "keywords": ["sequence", "call", "trace", "steps", "path"]},
]


CATEGORY_ALIASES: dict[str, str] = {
    "reentrancy": "reentrancy",
    "access": "access_control",
    "access control": "access_control",
    "overflow": "arithmetic",
    "arithmetic": "arithmetic",
    "oracle": "oracle_manipulation",
    "flash": "flash_loan",
    "fund": "fund_loss",
    "invariant": "invariant_break",
}


class EchidnaNLP:
    """"""

    def __init__(
        self,
        classifier: EchidnaClassifier | None = None,
        fixer: EchidnaFixer | None = None,
    ) -> None:
        self._classifier = classifier
        self._fixer = fixer or EchidnaFixer()

    def ask(
        self,
        query: str,
        findings: list[dict[str, Any]],
        aggregate: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        q = query.lower().strip()

        # Determine intent
        intent = self._classify_intent(q)
        category = self._extract_category(q)

        # Generate answer
        if intent == "summary":
            answer, filtered = self._answer_summary(findings, aggregate)
        elif intent == "failures":
            answer, filtered = self._answer_failures(findings, category)
        elif intent == "critical":
            answer, filtered = self._answer_critical(findings)
        elif intent == "filter_category" and category:
            answer, filtered = self._answer_by_category(findings, category)
        elif intent == "how_to_fix":
            answer, filtered = self._answer_fix(findings, category)
        elif intent == "sequence":
            answer, filtered = self._answer_sequence(findings)
        else:
            answer, filtered = self._answer_fallback(q)

        return {
            "query": query,
            "intent": intent,
            "answer": answer,
            "context": {
                "total_findings": len(findings),
                "category_filter": category,
            },
            "findings": filtered,
            "follow_up_questions": self._follow_ups(intent),
        }

    def _classify_intent(self, query: str) -> str:
        scores: dict[str, int] = {}
        for intent_def in INTENTS:
            score = sum(1 for kw in intent_def["keywords"] if kw in query)
            if score > 0:
                scores[intent_def["intent"]] = score
        if not scores:
            return "unknown"
        return max(scores, key=scores.get)

    def _extract_category(self, query: str) -> str | None:
        for alias, category in CATEGORY_ALIASES.items():
            if alias in query:
                return category
        return None

    @staticmethod
    def _answer_summary(
        findings: list[dict[str, Any]],
        aggregate: dict[str, Any] | None,
    ) -> tuple[str, list]:
        agg = aggregate or {}
        total = len(findings)
        critical = agg.get("critical_count", sum(1 for f in findings if f.get("severity") == "critical"))
        high = agg.get("high_count", sum(1 for f in findings if f.get("severity") == "high"))
        health = agg.get("health", "unknown")

        return (
            f"Fuzzing complete: **{total} property violation(s)**. "
            f"{critical} critical, {high} high. "
            f"Health: **{health.upper()}**.",
            findings,
        )

    @staticmethod
    def _answer_failures(
        findings: list[dict[str, Any]],
        category: str | None,
    ) -> tuple[str, list]:
        if category:
            filtered = [
                f for f in findings
                if f.get("failure_category") == category
            ]
            if not filtered:
                return f"No {category} failures found.", []
            lines = [f"Found **{len(filtered)}** {category} failure(s):"]
        else:
            filtered = findings
            lines = [f"Found **{len(filtered)}** fuzzing failure(s):"]

        for i, f in enumerate(filtered[:10], 1):
            fn = f.get("test_function", f.get("title", "unknown"))
            cat = f.get("failure_label", f.get("failure_category", ""))
            lines.append(f"  {i}. `{fn}` ({cat})")

        if len(filtered) > 10:
            lines.append(f"  ... and {len(filtered) - 10} more.")
        return "\n".join(lines), filtered

    @staticmethod
    def _answer_critical(findings: list[dict[str, Any]]) -> tuple[str, list]:
        critical = [
            f for f in findings
            if f.get("severity") in ("critical", "high")
            or f.get("failure_severity") in ("critical", "high")
        ]
        if not critical:
            return "✅ No critical failures!", []
        lines = [f"🔴 Found **{len(critical)}** critical/high failure(s):"]
        for i, f in enumerate(critical[:10], 1):
            fn = f.get("test_function", f.get("title", "unknown"))
            sev = f.get("failure_severity", f.get("severity", "?"))
            lines.append(f"  {i}. `{fn}` (severity: {sev})")
        return "\n".join(lines), critical

    @staticmethod
    def _answer_by_category(
        findings: list[dict[str, Any]],
        category: str,
    ) -> tuple[str, list]:
        filtered = [f for f in findings if f.get("failure_category") == category]
        if not filtered:
            return f"No findings in category '{category}'.", []
        lines = [f"Found **{len(filtered)}** finding(s) in {category}:"]
        for i, f in enumerate(filtered[:10], 1):
            lines.append(f"  {i}. {f.get('title', '?')}")
        return "\n".join(lines), filtered

    def _answer_fix(
        self,
        findings: list[dict[str, Any]],
        category: str | None,
    ) -> tuple[str, list]:
        if category:
            target = [f for f in findings if f.get("failure_category") == category]
        else:
            target = findings[:3]

        if not target:
            return "No issues to fix.", []

        fixes = self._fixer.generate_fixes(target)
        lines = ["Fix suggestions:\n"]
        for cat, fix_list in fixes.items():
            for fix in fix_list:
                if fix.get("solidity_example"):
                    lines.append(f"### {cat}")
                    lines.append(fix["description"])
                    lines.append(f"\n```solidity\n{fix['solidity_example']}\n```")
                    lines.append("")
        return "\n".join(lines), target

    @staticmethod
    def _answer_sequence(findings: list[dict[str, Any]]) -> tuple[str, list]:
        with_seq = [
            f for f in findings
            if f.get("failing_input") or f.get("sequence_analysis", {}).get("has_sequence")
        ]
        if not with_seq:
            return "No call sequences available.", []
        lines = [f"Found {len(with_seq)} finding(s) with call sequences.\n"]
        for i, f in enumerate(with_seq[:5], 1):
            fn = f.get("test_function", f.get("title", "?"))
            seq = f.get("sequence_analysis", {})
            steps = seq.get("step_count", 0)
            complexity = seq.get("complexity", "unknown")
            narrative = seq.get("narrative", "")
            lines.append(f"### {i}. `{fn}` ({steps} steps, {complexity})")
            if narrative:
                lines.append(f"{narrative}")
            lines.append("")
        return "\n".join(lines), with_seq

    @staticmethod
    def _answer_fallback(query: str) -> tuple[str, list]:
        return (
            f"Maaf, saya belum bisa menjawab \"{query}\". "
            "Coba: 'summary', 'failures', 'how to fix reentrancy', 'call sequence'.",
            [],
        )

    @staticmethod
    def _follow_ups(intent: str) -> list[str]:
        return {
            "summary": ["Show failures", "Show critical", "How to fix?"],
            "failures": ["Show critical", "How to fix reentrancy?", "Call sequence"],
            "critical": ["How to fix critical?", "Call sequence"],
            "filter_category": ["How to fix?", "Show call sequence"],
            "how_to_fix": ["Show failures", "Call sequence"],
            "sequence": ["Show critical", "How to fix?"],
        }.get(intent, ["Show summary", "Show failures"])


def create_nlp(
    classifier: EchidnaClassifier | None = None,
    fixer: EchidnaFixer | None = None,
) -> EchidnaNLP:
    return EchidnaNLP(classifier=classifier, fixer=fixer)
