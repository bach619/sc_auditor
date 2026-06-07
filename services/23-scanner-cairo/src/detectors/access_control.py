"""Detects missing access control on admin/privileged functions in Cairo."""

from __future__ import annotations

from typing import Any

from src.detectors.base import BaseCairoDetector


class AccessControlDetector(BaseCairoDetector):
    name = "access_control"
    description = "Detects @external functions without access control checks"
    severity_focus = "high"
    category = "access-control"

    def analyze(self, ir_contract: dict[str, Any]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        functions = ir_contract.get("functions", {})

        sensitive_keywords = [
            "admin", "owner", "upgrade", "mint", "burn",
            "set_", "update_", "change_", "withdraw",
            "configure", "initialize",
        ]

        for func_name, func in functions.items():
            if func.get("is_constructor"):
                continue
            if not func.get("visibility") == "external":
                continue

            is_sensitive = any(
                kw in func_name.lower() for kw in sensitive_keywords
            )
            has_access = func.get("has_access_control", False)

            if is_sensitive and not has_access:
                findings.append({
                    "tool": "cairo-detector",
                    "title": f"Missing access control on sensitive function '{func_name}'",
                    "description": (
                        f"The function '{func_name}' modifies sensitive state but "
                        "lacks access control checks. Any caller can invoke this function."
                    ),
                    "severity": "high",
                    "contract": ir_contract.get("name", ""),
                    "recommendation": (
                        f"Add access control to '{func_name}' using Cairo's ownable "
                        "pattern or a custom role-based access check."
                    ),
                })

        return findings
