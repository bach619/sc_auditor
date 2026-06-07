"""Detects upgrade-related vulnerabilities in Cairo contracts."""

from __future__ import annotations

from typing import Any

from src.detectors.base import BaseCairoDetector


class UpgradeSafetyDetector(BaseCairoDetector):
    name = "upgrade_safety"
    description = "Detects proxy patterns without proper initialization guards in Cairo"
    severity_focus = "high"
    category = "upgrade"

    def analyze(self, ir_contract: dict[str, Any]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_parse = ir_contract.get("_raw_parse", {})
        source = raw_parse.get("source", "")
        functions = ir_contract.get("functions", {})

        proxy_indicators = [
            "proxy", "upgrade", "implementation",
            "fallback", "delegate",
        ]
        is_proxy = any(
            ind in source.lower() for ind in proxy_indicators
        )

        if not is_proxy:
            return findings

        any(
            func.get("is_constructor") for func in functions.values()
        )
        has_initializer = any(
            "init" in name.lower() or "initialize" in name.lower()
            for name in functions
        )

        if is_proxy and not has_initializer:
            findings.append({
                "tool": "cairo-detector",
                "title": "Proxy pattern without explicit initializer",
                "description": (
                    "The contract appears to use a proxy/upgrade pattern but lacks "
                    "an explicit initialization function with protection against "
                    "multiple initializations."
                ),
                "severity": "high",
                "contract": ir_contract.get("name", ""),
                "recommendation": (
                    "Add an initializer function with a guard (e.g., storage flag) "
                    "to prevent re-initialization attacks on the proxy implementation."
                ),
            })

        has_storage_gap = any(
            "gap" in name.lower() or "reserved" in name.lower()
            for name in ir_contract.get("state_variables", {})
        )
        if is_proxy and not has_storage_gap:
            findings.append({
                "tool": "cairo-detector",
                "title": "Upgradeable contract missing storage gap",
                "description": (
                    "The upgradeable contract does not appear to have reserved storage "
                    "slots (storage gap). Future upgrades may cause storage collisions."
                ),
                "severity": "medium",
                "contract": ir_contract.get("name", ""),
                "recommendation": (
                    "Add reserved storage variables to prevent storage layout "
                    "collisions between implementation versions."
                ),
            })

        return findings
