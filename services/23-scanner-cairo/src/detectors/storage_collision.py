"""Detects potential storage variable collisions in Cairo contracts."""

from __future__ import annotations

from typing import Any

from src.detectors.base import BaseCairoDetector


class StorageCollisionDetector(BaseCairoDetector):
    name = "storage_collision"
    description = "Detects multiple functions writing to the same storage slot without coordination"
    severity_focus = "medium"
    category = "storage"

    def analyze(self, ir_contract: dict[str, Any]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        storage_layout = ir_contract.get("storage_layout", {})
        functions = ir_contract.get("functions", {})

        slot_writers: dict[int, list[str]] = {}
        raw_parse = ir_contract.get("_raw_parse", {})
        source = raw_parse.get("source", "")

        for func_name in functions:
            for slot, var_info in storage_layout.items():
                var_name = var_info.get("name", "")
                if var_name and var_name in source:
                    func_start = source.find(f"func {func_name}")
                    var_pos = source.rfind(var_name, func_start, func_start + 2000) if func_start >= 0 else -1
                    if var_pos >= 0:
                        slot_writers.setdefault(slot, []).append(func_name)

        for slot, writers in slot_writers.items():
            if len(writers) > 1:
                var_info = storage_layout.get(slot, {})
                findings.append({
                    "tool": "cairo-detector",
                    "title": f"Storage slot collision risk — slot {slot} written by multiple functions",
                    "description": (
                        f"Storage variable '{var_info.get('name', 'unknown')}' at slot {slot} "
                        f"is modified by functions: {', '.join(writers)}. This may indicate "
                        "unintended state overwrites or upgrade-related collision risks."
                    ),
                    "severity": "medium",
                    "contract": ir_contract.get("name", ""),
                    "recommendation": (
                        "Ensure storage variable writes are coordinated. Consider using "
                        "Cairo's storage namespacing or explicit access functions."
                    ),
                })

        return findings
