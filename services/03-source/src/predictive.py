"""PredictiveVulnerabilityMapper — Prediksi lokasi vulnerability.

Menganalisis fungsi-fungsi dalam source code dan memberi risk score
berdasarkan pola-pola yang dikenal berbahaya:
- External calls (reentrancy)
- Delegatecall (proxy manipulation)
- Assembly (low-level manipulation)
- Unchecked blocks (overflow)
- Complex functions (logic errors)
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from src.models import SourceResult

log = structlog.get_logger()

_FUNC_DEF_PATTERN = re.compile(
    r"(?:function|modifier)\s+(\w+)\s*\(([^)]*)\)\s*"
    r"(?:\s*(?:public|external|internal|private))?"
    r"(?:\s*(?:pure|view|payable|nonpayable))?"
    r"(?:\s*(?:returns)\s*\([^)]*\))?\s*"
    r"\{"
)

_FUNC_BODY_PATTERN = re.compile(
    r"(?:function|modifier)\s+(\w+)\s*\(([^)]*)\)"
    r".*?\{"  # Match everything up to first brace
)


class PredictiveVulnerabilityMapper:
    """Prediksi fungsi mana yang paling mungkin vulnerable.

    Menggunakan rule-based scoring (bukan ML model) untuk menilai
    risiko setiap fungsi berdasarkan pola yang dikenal.

    Usage::

        mapper = PredictiveVulnerabilityMapper()
        risks = mapper.predict_vulnerable_functions(chain, address, source)
    """

    def __init__(self) -> None:
        # Rule weights
        self.rules = {
            "has_external_call": 0.30,
            "has_delegatecall": 0.50,
            "has_transfer": 0.20,
            "writes_state": 0.20,
            "uses_assembly": 0.30,
            "uses_unchecked": 0.20,
            "uses_arithmetic": 0.15,
            "has_loop": 0.15,
            "is_complex": 0.10,
            "has_many_params": 0.10,
        }

    def predict_vulnerable_functions(
        self,
        chain: str,
        address: str,
        source: SourceResult,
    ) -> list[dict[str, Any]]:
        """Prediksi fungsi mana yang vulnerable.

        Args:
            chain: Blockchain name.
            address: Contract address.
            source: SourceResult dari cache atau fetch.

        Returns:
            List of function risk assessments, sorted by risk descending.
        """
        all_content = "\n".join(source.sources.values())

        # Extract individual function bodies (simplified)
        functions = self._extract_functions(all_content)

        results = []
        for func in functions:
            risk_score = self._rule_based_score(func["body"])
            top_vulns = self._top_vulnerabilities(func["body"])

            results.append({
                "function_name": func["name"],
                "signature": func.get("signature", f"{func['name']}(...)"),
                "risk_score": round(risk_score, 2),
                "risk_level": self._risk_level(risk_score),
                "lines_of_code": func.get("lines", 0),
                "parameters": func.get("param_count", 0),
                "top_vulnerabilities": top_vulns[:3],
                "flags": self._get_flags(func["body"]),
                "estimated_exploitability": self._exploitability(risk_score),
                "recommended_tools": self._recommend_tools(top_vulns),
            })

        # Sort by risk descending
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def _extract_functions(self, content: str) -> list[dict]:
        """Extract individual functions from Solidity source."""
        functions = []
        # Simple extraction — find function definitions
        func_starts = list(_FUNC_DEF_PATTERN.finditer(content))

        for i, match in enumerate(func_starts):
            name = match.group(1)
            params = match.group(2)

            # Get function body (from { to matching })
            start = match.end()
            if start >= len(content):
                continue

            # Find matching closing brace
            depth = 1
            end = start
            while depth > 0 and end < len(content):
                if content[end] == "{":
                    depth += 1
                elif content[end] == "}":
                    depth -= 1
                end += 1

            body = content[start:end - 1] if depth == 0 else content[start:start + 200]

            param_count = len([p for p in params.split(",") if p.strip()])
            lines = body.count("\n") + 1

            functions.append({
                "name": name,
                "body": body,
                "lines": lines,
                "param_count": param_count,
                "signature": f"{name}({params.strip()})",
            })

        return functions

    def _rule_based_score(self, body: str) -> float:
        """Rule-based risk scoring untuk satu fungsi."""
        score = 0.0

        if not body:
            return 0.0

        body_lower = body.lower()

        # External calls
        if ".call{" in body or ".call(" in body:
            score += self.rules["has_external_call"]
        if "delegatecall" in body_lower:
            score += self.rules["has_delegatecall"]
        if ".transfer(" in body_lower or ".send(" in body_lower:
            score += self.rules["has_transfer"]

        # State mutations
        if re.search(r"(?<!//)\s*=\s*(?![\s=])", body):
            score += self.rules["writes_state"]

        # Assembly
        if "assembly" in body_lower:
            score += self.rules["uses_assembly"]

        # Unchecked
        if "unchecked" in body_lower:
            score += self.rules["uses_unchecked"]

        # Arithmetic operations (potential overflow)
        if re.search(r"[+\-*/%]", body):
            score += self.rules["uses_arithmetic"]

        # Loops (gas risks, DoS)
        if "for (" in body_lower or "while (" in body_lower:
            score += self.rules["has_loop"]

        # Complexity
        if len(body) > 500:  # > 500 chars
            score += self.rules["is_complex"]

        # Too many parameters
        if body.count(",") > 10:
            score += self.rules["has_many_params"]

        return min(score, 1.0)

    def _top_vulnerabilities(self, body: str) -> list[str]:
        """Identify top 3 potential vulnerability types."""
        vulns = []

        body_lower = body.lower()

        if ".call{" in body or ".call.value" in body_lower:
            vulns.append("Reentrancy")
        if "delegatecall" in body_lower:
            vulns.append("Delegatecall Injection")
        if "assembly" in body_lower:
            vulns.append("Assembly Manipulation")
        if "unchecked" in body_lower:
            vulns.append("Integer Overflow/Underflow")
        if "tx.origin" in body_lower:
            vulns.append("Tx.Origin Auth")
        if "block.timestamp" in body_lower or "block.number" in body_lower:
            vulns.append("Timestamp/Block Dependency")
        if "selfdestruct" in body_lower or "suicide" in body_lower:
            vulns.append("Selfdestruct")
        if "msg.value" in body_lower and "for" in body_lower:
            vulns.append("Ether Theft via Loop")

        return vulns or ["General Logic Error"]

    def _risk_level(self, score: float) -> str:
        """Convert numeric score to risk level."""
        if score >= 0.8:
            return "CRITICAL"
        if score >= 0.5:
            return "HIGH"
        if score >= 0.3:
            return "MEDIUM"
        if score >= 0.1:
            return "LOW"
        return "INFO"

    def _get_flags(self, body: str) -> list[str]:
        """Get all risk flags for a function."""
        flags = []
        body_lower = body.lower()

        if ".call{" in body:
            flags.append("external_call")
        if "delegatecall" in body_lower:
            flags.append("delegatecall")
        if "assembly" in body_lower:
            flags.append("assembly")
        if "unchecked" in body_lower:
            flags.append("unchecked")
        if len(body) > 500:
            flags.append("complex")
        if body.count(",") > 10:
            flags.append("many_params")

        return flags

    def _exploitability(self, score: float) -> str:
        """Estimate exploitability based on risk score."""
        if score >= 0.7:
            return "high"
        if score >= 0.4:
            return "medium"
        return "low"

    def _recommend_tools(self, vulns: list[str]) -> list[str]:
        """Recommend analysis tools based on vulnerability types."""
        tools = set()
        for v in vulns:
            v_lower = v.lower()
            if "reentrancy" in v_lower:
                tools.add("Slither")
            if "overflow" in v_lower:
                tools.add("Mythril")
            if "assembly" in v_lower or "delegatecall" in v_lower:
                tools.add("Echidna (fuzzing)")
            if "logic" in v_lower:
                tools.add("Manual Review")
        return list(tools)[:3]
