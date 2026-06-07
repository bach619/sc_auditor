"""Detects oracle dependency with insufficient validation in Cairo."""

from __future__ import annotations

import re
from typing import Any

from src.detectors.base import BaseCairoDetector


class OracleManipulationDetector(BaseCairoDetector):
    name = "oracle_manipulation"
    description = "Detects oracle/price data used in critical calculations without validation"
    severity_focus = "high"
    category = "oracle"

    def analyze(self, ir_contract: dict[str, Any]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_parse = ir_contract.get("_raw_parse", {})
        source = raw_parse.get("source", "")

        oracle_indicators = [
            "price", "oracle", "rate", "feed",
            "get_price", "get_rate", "latest_round",
        ]
        critical_operations = [
            "transfer", "mint", "burn", "liquidate",
            "borrow", "repay", "swap", "withdraw",
        ]

        for func_name, func in ir_contract.get("functions", {}).items():
            func_source = ""
            func_pattern = re.compile(
                rf'func\s+{re.escape(func_name)}\s*\((.*?)\)(?:\s*->\s*\(?(.*?)\)?)?\s*\{{',
                re.DOTALL
            )
            match = func_pattern.search(source)
            if match:
                body_start = match.end()
                depth = 0
                body_end = body_start
                for i in range(body_start, len(source)):
                    if source[i] == "{":
                        depth += 1
                    elif source[i] == "}":
                        if depth == 0:
                            body_end = i
                            break
                        depth -= 1
                func_source = source[body_start:body_end]

            has_oracle = any(ind in func_source.lower() for ind in oracle_indicators)
            has_critical = any(op in func_source.lower() for op in critical_operations)

            if has_oracle and has_critical:
                has_validation = any(
                    kw in func_source.lower()
                    for kw in ["assert", "check", "require", "valid_", "bound", "stale"]
                )
                if not has_validation:
                    findings.append({
                        "tool": "cairo-detector",
                        "title": f"Oracle data used without validation in '{func_name}'",
                        "description": (
                            f"Function '{func_name}' uses oracle/price data in critical "
                            "operations without bounds checking or staleness validation. "
                            "This is susceptible to oracle manipulation attacks."
                        ),
                        "severity": "high",
                        "contract": ir_contract.get("name", ""),
                        "recommendation": (
                            "Validate oracle data with freshness checks (timestamp), "
                            "price bounds (min/max), and consider using a TWAP or "
                            "median of multiple oracle sources."
                        ),
                    })

        return findings
