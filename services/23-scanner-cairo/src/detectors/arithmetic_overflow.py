"""Detects unchecked arithmetic operations in Cairo (felt overflow)."""

from __future__ import annotations

import re
from typing import Any

from src.detectors.base import BaseCairoDetector


class ArithmeticOverflowDetector(BaseCairoDetector):
    name = "arithmetic_overflow"
    description = "Detects arithmetic operations without bounds checking in Cairo"
    severity_focus = "medium"
    category = "arithmetic"

    def analyze(self, ir_contract: dict[str, Any]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_parse = ir_contract.get("_raw_parse", {})
        source = raw_parse.get("source", "")

        arithmetic_ops = re.finditer(r'(\w+)\s*([+\-*/])\s*(\w+)', source)
        for match in arithmetic_ops:
            left = match.group(1)
            op = match.group(2)
            right = match.group(3)
            line = source[:match.start()].count("\n") + 1

            snippet_start = max(0, match.start() - 100)
            snippet_end = min(len(source), match.end() + 100)
            snippet = source[snippet_start:snippet_end]

            has_check = any(
                kw in snippet.lower()
                for kw in ["assert", "check", "require", "valid_", "bound"]
            )

            if not has_check:
                findings.append({
                    "tool": "cairo-detector",
                    "title": f"Unchecked arithmetic operation: {left} {op} {right}",
                    "description": (
                        f"Arithmetic operation '{left} {op} {right}' at line {line} "
                        "lacks bounds checking. In Cairo, felt values can overflow "
                        "the prime field modulus without explicit validation."
                    ),
                    "severity": "medium",
                    "contract": ir_contract.get("name", ""),
                    "line": line,
                    "recommendation": (
                        "Add explicit bounds checking using assert_le, assert_lt, "
                        "or Cairo's SafeUint256 library before this operation."
                    ),
                })

        return findings[:20]
