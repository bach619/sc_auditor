"""Detects reentrancy patterns in Cairo (cross-contract calls followed by state changes)."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from src.detectors.base import BaseCairoDetector


class ReentrancyDetector(BaseCairoDetector):
    name = "reentrancy"
    description = "Detects external contract calls followed by state changes in Cairo"
    severity_focus = "high"
    category = "reentrancy"

    def analyze(self, ir_contract: Dict[str, Any]) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        raw_parse = ir_contract.get("_raw_parse", {})
        source = raw_parse.get("source", "")
        external_calls = ir_contract.get("external_calls", {})

        call_lines = re.findall(r'call_contract', source)
        if not call_lines:
            return findings

        for func_name, calls in external_calls.items():
            if not calls:
                continue
            func_pattern = re.compile(
                rf'func\s+{re.escape(func_name)}\s*\((.*?)\)(?:\s*->\s*\(?(.*?)\)?)?\s*\{{',
                re.DOTALL
            )
            match = func_pattern.search(source)
            if not match:
                continue
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
            body = source[body_start:body_end]

            storage_writes = re.findall(r'(read|write)\s*\(\s*(\w+)', body)
            has_state_after_call = False
            call_positions = [m.start() for m in re.finditer(r'call_contract', body)]
            for sw_match in re.finditer(r'(read|write)\s*\(\s*(\w+)', body):
                sw_pos = sw_match.start()
                if any(cp < sw_pos for cp in call_positions):
                    has_state_after_call = True
                    break

            if has_state_after_call:
                findings.append({
                    "tool": "cairo-detector",
                    "title": f"Potential reentrancy in function '{func_name}'",
                    "description": (
                        f"Function '{func_name}' performs external contract calls "
                        "(call_contract) followed by state modifications. This pattern "
                        "is susceptible to reentrancy attacks in Cairo."
                    ),
                    "severity": "high",
                    "contract": ir_contract.get("name", ""),
                    "recommendation": (
                        "Move all state modifications before external calls, or implement "
                        "a reentrancy guard using a storage variable flag."
                    ),
                })

        return findings
