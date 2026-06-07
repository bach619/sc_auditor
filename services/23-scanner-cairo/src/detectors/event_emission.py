"""Detects state changes without event emission in Cairo."""

from __future__ import annotations

import re
from typing import Any

from src.detectors.base import BaseCairoDetector


class EventEmissionDetector(BaseCairoDetector):
    name = "event_emission"
    description = "Detects state-modifying functions that don't emit events"
    severity_focus = "low"
    category = "events"

    def analyze(self, ir_contract: dict[str, Any]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_parse = ir_contract.get("_raw_parse", {})
        source = raw_parse.get("source", "")
        events = ir_contract.get("events", {})

        for func_name, func in ir_contract.get("functions", {}).items():
            if func.get("is_constructor") or func.get("is_view"):
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

            has_storage_write = bool(re.search(r'write\s*\(', body))
            has_event = any(
                re.search(rf'{re.escape(ev)}\.emit', body)
                for ev in events
            )

            if has_storage_write and not has_event:
                findings.append({
                    "tool": "cairo-detector",
                    "title": f"State change without event emission in '{func_name}'",
                    "description": (
                        f"Function '{func_name}' modifies contract storage but does not "
                        "emit an event. Off-chain services cannot track these state changes."
                    ),
                    "severity": "low",
                    "contract": ir_contract.get("name", ""),
                    "recommendation": (
                        f"Emit an event after state changes in '{func_name}' so that "
                        "indexers and monitoring tools can detect the modification."
                    ),
                })

        return findings
