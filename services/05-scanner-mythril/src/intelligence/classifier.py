"""Mythril SWC Classifier — L2 Intelligence.

Mythril sudah memberikan SWC ID untuk setiap finding. Classifier ini
memetakan SWC ID ke kategori yang lebih tinggi dan severity override.

SWC = Smart Contract Weakness Classification
Ref: https://swcregistry.io/
"""

from __future__ import annotations

from typing import Any

# SWC → Category mapping
SWC_CATEGORIES: dict[str, dict[str, Any]] = {
    "SWC-100": {"category": "function_visibility", "severity": "high", "label": "Function Visibility"},
    "SWC-101": {"category": "arithmetic", "severity": "high", "label": "Integer Overflow"},
    "SWC-102": {"category": "arithmetic", "severity": "high", "label": "Integer Underflow"},
    "SWC-103": {"category": "solidity", "severity": "informational", "label": "Deprecated Solidity Features"},
    "SWC-104": {"category": "low_level", "severity": "high", "label": "Unchecked External Call"},
    "SWC-105": {"category": "access_control", "severity": "critical", "label": "Unprotected Ether Withdrawal"},
    "SWC-106": {"category": "access_control", "severity": "high", "label": "Unprotected SELFDESTRUCT"},
    "SWC-107": {"category": "reentrancy", "severity": "critical", "label": "Reentrancy"},
    "SWC-108": {"category": "access_control", "severity": "critical", "label": "State Variable Default Visibility"},
    "SWC-109": {"category": "initialization", "severity": "high", "label": "Uninitialized Storage Pointer"},
    "SWC-110": {"category": "initialization", "severity": "high", "label": "Uninitialized State Variable"},
    "SWC-111": {"category": "access_control", "severity": "high", "label": "Unsafe Delegatecall"},
    "SWC-112": {"category": "access_control", "severity": "critical", "label": "Controlled Delegatecall"},
    "SWC-113": {"category": "dos", "severity": "medium", "label": "DoS with Failed Call"},
    "SWC-114": {"category": "dos", "severity": "medium", "label": "Transaction Order Dependence"},
    "SWC-115": {"category": "access_control", "severity": "high", "label": "Authorization through tx.origin"},
    "SWC-116": {"category": "consensus", "severity": "low", "label": "Timestamp Dependence"},
    "SWC-117": {"category": "consensus", "severity": "low", "label": "Block Number Dependence"},
    "SWC-118": {"category": "dos", "severity": "medium", "label": "DoS with Block Gas Limit"},
    "SWC-119": {"category": "oracle", "severity": "high", "label": "Oracle Manipulation"},
    "SWC-120": {"category": "arithmetic", "severity": "medium", "label": "Weak Sources of Randomness"},
    "SWC-121": {"category": "access_control", "severity": "high", "label": "Missing Protection against Signature Replay"},
    "SWC-122": {"category": "access_control", "severity": "high", "label": "Improper Access Control"},
    "SWC-123": {"category": "solidity", "severity": "informational", "label": "Requirement Violation"},
    "SWC-124": {"category": "solidity", "severity": "informational", "label": "Write to Arbitrary Storage Location"},
    "SWC-125": {"category": "arithmetic", "severity": "informational", "label": "Incorrect Inheritance Order"},
    "SWC-126": {"category": "solidity", "severity": "informational", "label": "Insufficient Gas Gifting"},
    "SWC-127": {"category": "solidity", "severity": "informational", "label": "Arbitrary Jump with Function Type"},
    "SWC-128": {"category": "dos", "severity": "low", "label": "Unused Return Value"},
}

# Fallback severity ketika SWC tidak dikenal
FALLBACK: dict[str, Any] = {
    "category": "unknown",
    "severity": "medium",
    "label": "Unknown SWC",
}

# Severity override dictionary
SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "informational": 0}


class MythrilClassifier:
    """Mengklasifikasikan Mythril findings berdasarkan SWC ID."""

    def classify(
        self,
        title: str = "",
        description: str = "",
        swc_id: str | None = None,
        severity: str = "Medium",
    ) -> dict[str, Any]:
        """Classify a single Mythril finding.

        Args:
            title: Finding title.
            description: Finding description.
            swc_id: SWC ID (e.g. "SWC-107").
            severity: Original severity from Mythril.

        Returns:
            Dict dengan category, severity_override, label, dll.
        """
        if swc_id:
            swc_id_upper = swc_id.upper().strip()
            info = SWC_CATEGORIES.get(swc_id_upper)
            if info:
                final_severity = info["severity"]
                # Override: jika Mythril bilang "Low" tapi SWC bilang "High",
                # pakai yang lebih tinggi
                orig_rank = SEVERITY_RANK.get(severity.lower(), 1)
                swc_rank = SEVERITY_RANK.get(final_severity, 1)
                if orig_rank > swc_rank:
                    final_severity = severity.lower()

                return {
                    "swc_id": swc_id_upper,
                    "category": info["category"],
                    "category_label": info["label"],
                    "severity": final_severity,
                    "confidence": 0.95,
                }

        # Fallback: coba detect dari title
        title_lower = title.lower()
        for swc_id_key, info in SWC_CATEGORIES.items():
            if info["label"].lower() in title_lower:
                return {
                    "swc_id": swc_id_key,
                    "category": info["category"],
                    "category_label": info["label"],
                    "severity": info["severity"],
                    "confidence": 0.7,
                }

        return {
            "swc_id": swc_id or "unknown",
            "category": FALLBACK["category"],
            "category_label": FALLBACK["label"],
            "severity": severity.lower() if severity else "medium",
            "confidence": 0.3,
        }

    def classify_findings(
        self,
        findings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Classify multiple findings."""
        enriched = []
        for f in findings:
            cls = self.classify(
                title=f.get("title", ""),
                description=f.get("description", ""),
                swc_id=f.get("swc_id"),
                severity=f.get("severity", "Medium"),
            )
            enriched.append({**f, **cls})
        return enriched

    def get_swc_registry(self) -> dict[str, dict[str, Any]]:
        """Return SWC registry dengan category dan severity."""
        return {
            swc: {
                "category": info["category"],
                "severity": info["severity"],
                "label": info["label"],
            }
            for swc, info in SWC_CATEGORIES.items()
        }


def create_classifier() -> MythrilClassifier:
    return MythrilClassifier()
