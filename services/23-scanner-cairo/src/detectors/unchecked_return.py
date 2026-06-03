"""Detects unchecked external call return values in Cairo."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from src.detectors.base import BaseCairoDetector


class UncheckedReturnDetector(BaseCairoDetector):
    name = "unchecked_return"
    description = "Detects call_contract syscalls without return value checking"
    severity_focus = "medium"
    category = "validation"

    def analyze(self, ir_contract: Dict[str, Any]) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        raw_parse = ir_contract.get("_raw_parse", {})
        source = raw_parse.get("source", "")

        call_pattern = re.compile(
            r'(\(\s*(let\s+)?(\w+)\s*=)?\s*call_contract\s*\(',
            re.DOTALL
        )

        for match in call_pattern.finditer(source):
            has_assignment = match.group(1) is not None
            line = source[:match.start()].count("\n") + 1

            if not has_assignment:
                findings.append({
                    "tool": "cairo-detector",
                    "title": "Unchecked external call return value",
                    "description": (
                        f"call_contract at line {line} does not capture the return value. "
                        "Silently ignoring the return value may hide failed external calls."
                    ),
                    "severity": "medium",
                    "contract": ir_contract.get("name", ""),
                    "line": line,
                    "recommendation": (
                        "Always capture and validate the return value of call_contract. "
                        "Check the success flag before proceeding with state changes."
                    ),
                })

        return findings
