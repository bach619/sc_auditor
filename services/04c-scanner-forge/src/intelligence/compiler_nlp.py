"""Compiler NLP — Rule-based natural language query untuk build errors.

Menjawab pertanyaan seperti:
  - "why did the build fail?"
  - "how to fix import errors?"
  - "show me syntax errors"
  - "how many warnings?"
"""

from __future__ import annotations

from typing import Any

INTENT_PATTERNS: list[dict[str, Any]] = [
    {"intent": "summary", "keywords": ["summary", "overview", "overall", "result", "why"]},
    {"intent": "blocking", "keywords": ["blocking", "error", "fail", "failing", "critical"]},
    {"intent": "warning", "keywords": ["warning", "warn", "lint"]},
    {"intent": "fix", "keywords": ["fix", "repair", "solve", "how to", "patch", "solution"]},
    {"intent": "category", "keywords": [
        "syntax", "import", "type", "visibility", "override",
        "pragma", "abstract",
    ]},
]


class CompilerNLP:
    """"""

    def ask(
        self,
        query: str,
        errors: list[dict[str, Any]],
    ) -> dict[str, Any]:
        q = query.lower().strip()
        intent = self._classify_intent(q)
        category_filter = self._extract_category(q)

        if intent == "summary":
            answer, filtered = self._summary(errors)
        elif intent == "blocking":
            answer, filtered = self._blocking(errors)
        elif intent == "warning":
            answer, filtered = self._warnings(errors)
        elif intent == "fix" and category_filter:
            answer, filtered = self._fix(errors, category_filter)
        elif intent == "fix":
            answer, filtered = self._fix_all(errors)
        elif intent == "category" and category_filter:
            answer, filtered = self._by_category(errors, category_filter)
        else:
            answer, filtered = self._fallback(q)

        return {
            "query": query,
            "intent": intent,
            "answer": answer,
            "context": {
                "total_errors": len(errors),
                "category_filter": category_filter,
            },
            "errors": filtered,
            "follow_up_questions": self._follow_ups(intent),
        }

    @staticmethod
    def _classify_intent(query: str) -> str:
        scores: dict[str, int] = {}
        for p in INTENT_PATTERNS:
            score = sum(1 for kw in p["keywords"] if kw in query)
            if score > 0:
                scores[p["intent"]] = score
        return max(scores, key=scores.get) if scores else "unknown"

    @staticmethod
    def _extract_category(query: str) -> str | None:
        mapping = {
            "syntax": "syntax",
            "import": "import",
            "type": "type",
            "visibility": "visibility",
            "override": "override",
            "pragma": "pragma",
            "abstract": "abstract",
        }
        for word, cat in mapping.items():
            if word in query:
                return cat
        return None

    @staticmethod
    def _summary(errors: list) -> tuple[str, list]:
        cats: dict[str, int] = {}
        sevs: dict[str, int] = {}
        for e in errors:
            c = e.get("category", "unknown")
            cats[c] = cats.get(c, 0) + 1
            s = e.get("severity", "unknown")
            sevs[s] = sevs.get(s, 0) + 1

        cat_str = ", ".join(f"{k}={v}" for k, v in sorted(cats.items()))
        sev_str = ", ".join(f"{k}={v}" for k, v in sorted(sevs.items()))

        if not errors:
            return "✅ Build succeeded — no errors or warnings.", []

        return (
            f"Build produced **{len(errors)}** issues. "
            f"Categories: {cat_str}. Severity: {sev_str}.",
            errors,
        )

    @staticmethod
    def _blocking(errors: list) -> tuple[str, list]:
        blocking = [e for e in errors if e.get("severity") == "blocking"]
        if not blocking:
            return "✅ No blocking errors. All warnings only.", []
        lines = [f"Found **{len(blocking)}** blocking error(s):"]
        for i, e in enumerate(blocking[:10], 1):
            label = e.get("label", e.get("category", "error"))
            msg = e.get("error", e.get("message", ""))[:100]
            lines.append(f"  {i}. [{label}] {msg}")
        return "\n".join(lines), blocking

    @staticmethod
    def _warnings(errors: list) -> tuple[str, list]:
        warns = [e for e in errors if e.get("severity") == "warning"]
        if not warns:
            return "✅ No warnings.", []
        lines = [f"Found **{len(warns)}** warning(s):"]
        for i, e in enumerate(warns[:10], 1):
            label = e.get("label", "warning")
            msg = e.get("error", e.get("message", ""))[:100]
            lines.append(f"  {i}. [{label}] {msg}")
        return "\n".join(lines), warns

    @staticmethod
    def _fix(errors: list, category: str) -> tuple[str, list]:
        filtered = [e for e in errors if e.get("category") == category]
        if not filtered:
            return f"No '{category}' errors found.", []
        lines = [f"Fix suggestions for **{category}** errors:\n"]
        for e in filtered[:5]:
            label = e.get("label", "error")
            msg = e.get("error", e.get("message", ""))[:100]
            fix = e.get("fix", e.get("recommendation", "Review the error."))
            lines.append(f"- **{label}**: {msg}")
            lines.append(f"  → {fix}")
        return "\n".join(lines), filtered

    @staticmethod
    def _fix_all(errors: list) -> tuple[str, list]:
        if not errors:
            return "No errors to fix.", []
        lines = [f"Fix suggestions for all **{len(errors)}** issues:\n"]
        for e in errors[:5]:
            label = e.get("label", "error")
            fix = e.get("fix", e.get("recommendation", "Review the error."))
            lines.append(f"- **{label}**: {fix}")
        if len(errors) > 5:
            lines.append(f"\n... and {len(errors) - 5} more issues.")
        return "\n".join(lines), errors

    @staticmethod
    def _by_category(errors: list, category: str) -> tuple[str, list]:
        filtered = [e for e in errors if e.get("category") == category]
        if not filtered:
            return f"No errors in category '{category}'.", []
        lines = [f"**{len(filtered)}** error(s) in '{category}':"]
        for i, e in enumerate(filtered[:10], 1):
            label = e.get("label", "error")
            msg = e.get("error", e.get("message", ""))[:100]
            lines.append(f"  {i}. [{label}] {msg}")
        return "\n".join(lines), filtered

    @staticmethod
    def _fallback(query: str) -> tuple[str, list]:
        return (
            "Coba: 'summary', 'blocking errors', 'warnings', "
            "'how to fix import', 'show syntax errors'.",
            [],
        )

    @staticmethod
    def _follow_ups(intent: str) -> list[str]:
        return {
            "summary": ["Show blocking errors", "Show warnings", "Fix suggestions"],
            "blocking": ["How to fix?", "Show by category"],
            "warning": ["How to fix warnings?", "Show summary"],
            "fix": ["Show blocking errors", "Show type errors"],
            "category": ["Show blocking", "How to fix?"],
        }.get(intent, ["Show summary", "Show blocking errors"])


def create_nlp() -> CompilerNLP:
    return CompilerNLP()
