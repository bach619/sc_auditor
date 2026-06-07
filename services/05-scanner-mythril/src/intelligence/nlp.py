"""Mythril Natural Language Query — L4 Intelligence.

Rule-based NLP untuk menjawab pertanyaan tentang Mythril findings.
"""

from __future__ import annotations

from typing import Any

INTENT_PATTERNS: list[dict[str, Any]] = [
    {"intent": "summary", "keywords": ["summary", "overview", "overall", "result"]},
    {"intent": "critical", "keywords": ["critical", "dangerous", "worst", "severe"]},
    {"intent": "swc", "keywords": ["swc", "weakness", "category", "type"]},
    {"intent": "filter_swc", "keywords": [
        "reentrancy", "delegatecall", "overflow", "access", "oracle",
        "arithmetic", "unchecked", "visibility",
    ]},
    {"intent": "how_to_fix", "keywords": ["fix", "repair", "solve", "how to", "patch"]},
    {"intent": "exploit_chain", "keywords": ["chain", "exploit", "attack", "scenario", "combine"]},
    {"intent": "bugs_11", "keywords": [
        "11 bug", "top bug", "critical bug", "high bug", "bounty",
        "access control bypass", "reentrancy", "oracle manipulation",
        "bridge", "proxy", "unchecked call", "overflow", "delegatecall",
        "signature replay", "front running", "precision",
    ]},
]


class MythrilNLP:
    """"""

    def ask(
        self,
        query: str,
        findings: list[dict[str, Any]],
        chain_results: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        q = query.lower().strip()
        intent = self._classify_intent(q)
        swc_filter = self._extract_swc_keyword(q)

        if intent == "summary":
            answer, filtered = self._summary(findings)
        elif intent == "critical":
            answer, filtered = self._critical(findings)
        elif intent == "swc":
            answer, filtered = self._swc_summary(findings)
        elif intent == "filter_swc" and swc_filter:
            answer, filtered = self._filter_swc(findings, swc_filter)
        elif intent == "how_to_fix":
            answer, filtered = self._fix(findings, swc_filter)
        elif intent == "exploit_chain":
            answer, filtered = self._chains(findings, chain_results)
        elif intent == "bugs_11":
            answer, filtered = self._bugs_11(findings, chain_results)
        else:
            answer, filtered = self._fallback(q)

        return {
            "query": query,
            "intent": intent,
            "answer": answer,
            "context": {"total_findings": len(findings)},
            "findings": filtered,
            "follow_up_questions": self._follow_ups(intent),
        }

    @staticmethod
    def _classify_intent(query: str) -> str:
        scores = {}
        for p in INTENT_PATTERNS:
            score = sum(1 for kw in p["keywords"] if kw in query)
            if score > 0:
                scores[p["intent"]] = score
        return max(scores, key=scores.get) if scores else "unknown"

    @staticmethod
    def _extract_swc_keyword(query: str) -> str | None:
        mapping = {
            "reentrancy": "reentrancy",
            "delegatecall": "delegatecall",
            "overflow": "arithmetic",
            "arithmetic": "arithmetic",
            "access": "access_control",
            "oracle": "oracle",
            "unchecked": "low_level",
            "visibility": "function_visibility",
        }
        for word, cat in mapping.items():
            if word in query:
                return cat
        return None

    @staticmethod
    def _summary(findings: list) -> tuple[str, list]:
        cats: dict[str, int] = {}
        for f in findings:
            c = f.get("category", "unknown")
            cats[c] = cats.get(c, 0) + 1
        cat_str = ", ".join(f"{k}={v}" for k, v in sorted(cats.items()))
        return f"Found **{len(findings)}** findings. Categories: {cat_str}.", findings

    @staticmethod
    def _critical(findings: list) -> tuple[str, list]:
        crit = [f for f in findings if f.get("severity", "").lower() in ("critical", "high")]
        if not crit:
            return "✅ No critical/high severity findings.", []
        lines = [f"🔴 Found **{len(crit)}** critical/high issues:"]
        for i, f in enumerate(crit[:10], 1):
            lines.append(f"  {i}. {f.get('title', '?')} ({f.get('severity', '?')})")
        return "\n".join(lines), crit

    @staticmethod
    def _swc_summary(findings: list) -> tuple[str, list]:
        swcs: dict[str, int] = {}
        for f in findings:
            swc = f.get("swc_id", "unknown")
            swcs[swc] = swcs.get(swc, 0) + 1
        lines = [f"SWC distribution across {len(findings)} findings:"]
        for swc, count in sorted(swcs.items()):
            lines.append(f"  {swc}: {count}")
        return "\n".join(lines), findings

    @staticmethod
    def _filter_swc(findings: list, category: str) -> tuple[str, list]:
        filtered = [f for f in findings if f.get("category") == category]
        if not filtered:
            return f"No findings in category '{category}'.", []
        lines = [f"Found **{len(filtered)}** {category} finding(s):"]
        for i, f in enumerate(filtered[:10], 1):
            lines.append(f"  {i}. {f.get('title', '?')} — {f.get('swc_id', '')}")
        return "\n".join(lines), filtered

    @staticmethod
    def _fix(findings: list, swc_filter: str | None) -> tuple[str, list]:
        target = findings[:3]
        if not target:
            return "No findings to fix.", []
        lines = ["Fix suggestions (based on SWC templates):\n"]
        for f in target:
            swc = f.get("swc_id", "unknown")
            lines.append(f"- **{f.get('title', '?')}** ({swc})")
            lines.append(f"  Refer to SWC registry: https://swcregistry.io/docs/{swc}")
        return "\n".join(lines), target

    @staticmethod
    def _chains(findings: list, chains: list | None) -> tuple[str, list]:
        if not chains:
            return "No exploit chains identified from current findings.", findings
        lines = [f"Identified **{len(chains)}** exploit chain(s):\n"]
        for i, c in enumerate(chains[:5], 1):
            lines.append(f"### {i}. {c.get('name', '?')}")
            lines.append(f"Severity: **{c.get('severity', '?')}**")
            lines.append(f"Confidence: **{c.get('confidence', 0) * 100:.0f}%**")
            lines.append(f"Impact: {c.get('impact', '')}")
            lines.append("")
        return "\n".join(lines), findings

    @staticmethod
    def _bugs_11(findings: list, chains: list | None) -> tuple[str, list]:
        """Map findings to 11 critical/high bug categories."""
        # SWC → 11-bug mapping
        swc_to_bug: dict[str, tuple[str, str]] = {
            "SWC-105": ("B01", "Access Control Bypass"),
            "SWC-106": ("B01", "Access Control Bypass"),
            "SWC-108": ("B01", "Access Control Bypass"),
            "SWC-115": ("B01", "Access Control Bypass"),
            "SWC-121": ("B01", "Access Control Bypass"),
            "SWC-122": ("B01", "Access Control Bypass"),
            "SWC-107": ("B02", "Reentrancy"),
            "SWC-116": ("B03", "Oracle Manipulation"),
            "SWC-119": ("B03", "Oracle Manipulation"),
            "SWC-109": ("B05", "Uninitialized Proxy"),
            "SWC-110": ("B05", "Uninitialized Proxy"),
            "SWC-104": ("B06", "Unchecked External Call"),
            "SWC-101": ("B07", "Integer Overflow"),
            "SWC-102": ("B07", "Integer Underflow"),
            "SWC-111": ("B08", "Unsafe Delegatecall"),
            "SWC-112": ("B08", "Unsafe Delegatecall"),
            "SWC-114": ("B10", "Front-running / TOD"),
        }

        found_bugs: dict[str, list[dict]] = {}
        for f in findings:
            swc = (f.get("swc_id") or "").upper().strip()
            if swc in swc_to_bug:
                bug_id, bug_name = swc_to_bug[swc]
                found_bugs.setdefault(bug_id, {"name": bug_name, "severity": "?", "findings": []})
                found_bugs[bug_id]["findings"].append(f.get("title", "?"))
                sev = f.get("severity", "")
                if sev in ("critical", "high"):
                    found_bugs[bug_id]["severity"] = sev

        if not found_bugs:
            return "✅ No findings match any of the 11 high-severity bug categories.", []

        lines = [f"**{len(found_bugs)}** of 11 critical/high bug types detected:\n"]
        for bug_id in sorted(found_bugs):
            info = found_bugs[bug_id]
            lines.append(f"### {bug_id}: {info['name']} ({info['severity']})")
            for t in info["findings"][:3]:
                lines.append(f"  - {t}")
            if len(info["findings"]) > 3:
                lines.append(f"  ... and {len(info['findings']) - 3} more")
            lines.append("")

        if chains:
            lines.append(f"**⛓️ {len(chains)} exploit chain(s)** possible — combine bugs for greater impact.")

        return "\n".join(lines), findings

    @staticmethod
    def _fallback(query: str) -> tuple[str, list]:
        return (
            "Coba: 'summary', 'critical issues', 'SWC distribution', "
            "'how to fix reentrancy', 'exploit chains', '11 bugs'.",
            [],
        )

    @staticmethod
    def _follow_ups(intent: str) -> list[str]:
        return {
            "summary": ["Show critical", "SWC distribution", "Exploit chains"],
            "critical": ["How to fix?", "Exploit chains"],
            "swc": ["Show critical", "Filter by reentrancy"],
            "filter_swc": ["How to fix?", "Exploit chains"],
            "how_to_fix": ["Show critical", "SWC distribution"],
            "exploit_chain": ["Show critical", "How to fix?"],
            "bugs_11": ["Show exploit chains", "How to fix?", "Show critical"],
        }.get(intent, ["Show summary", "Show critical"])


def create_nlp() -> MythrilNLP:
    return MythrilNLP()
