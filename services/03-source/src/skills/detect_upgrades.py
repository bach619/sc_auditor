"""DetectUpgradesSkill — Detect proxy/upgrade patterns in smart contracts."""

from __future__ import annotations

import re
from typing import Any

import structlog
from shared.skills.base_skill import BaseSkill

log = structlog.get_logger()

# Proxy/upgrade patterns
INITIALIZER_PATTERN = re.compile(r"(initializ(e|er|ation)|initialize\s*\(|initializer\b)", re.IGNORECASE)
UPGRADE_PATTERN = re.compile(r"(upgradeTo|upgradeToAndCall|_upgradeTo|_authorizeUpgrade|UUPS|uups)", re.IGNORECASE)
BEACON_PATTERN = re.compile(r"(beacon|BeaconProxy|UpgradeableBeacon|getBeacon)", re.IGNORECASE)
TRANSPARENT_PATTERN = re.compile(r"(TransparentUpgradeableProxy|ProxyAdmin|admin\s*\(|getAdmin)", re.IGNORECASE)
DELEGATECALL_PATTERN = re.compile(r"(delegatecall|DELEGATECALL|_delegate)", re.IGNORECASE)
IMPLEMENTATION_PATTERN = re.compile(r"(implementation\s*[=\(]|_implementation\s*\(|getImplementation)", re.IGNORECASE)
STORAGE_GAP_PATTERN = re.compile(r"__gap\b|_gap\b|uint256\[\s*\]\s+private\s+__gap", re.IGNORECASE)
OWNABLE_UPGRADE_PATTERN = re.compile(r"(onlyOwner|OwnableUpgradeable|Ownable\.sol)", re.IGNORECASE)


class DetectUpgradesSkill(BaseSkill):
    """Detects proxy and upgradeable contract patterns in Solidity source code.

    Identifies UUPS, Transparent Proxy, Beacon Proxy, and other upgradeable
    patterns. Checks for delegatecall usage, implementation storage variables,
    initializer functions, OpenZeppelin upgradeable contracts, and storage gaps.
    """

    @property
    def name(self) -> str:
        return "detect_upgrades"

    @property
    def description(self) -> str:
        return (
            "Detect proxy/upgrade patterns in smart contract source code. "
            "Identifies UUPS (ERC-1822), Transparent Proxy, Beacon Proxy, "
            "and custom proxy patterns. Reports delegatecall usage, "
            "implementation pointers, initializer functions, storage gaps, "
            "and OpenZeppelin upgradeable contract inheritance."
        )

    @property
    def category(self) -> str:
        return "source_intel"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "object",
                    "description": "Dictionary mapping file paths to source code strings",
                    "additionalProperties": {"type": "string"},
                },
                "contract_name": {
                    "type": "string",
                    "description": "Primary contract name to analyze",
                },
            },
            "required": ["sources", "contract_name"],
        }

    async def run(
        self,
        sources: dict[str, str],
        contract_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        log.info("detect_upgrades_skill", contract_name=contract_name, file_count=len(sources))

        combined = "\n".join(sources.values())

        patterns: dict[str, dict[str, Any]] = {
            "delegatecall": {
                "detected": bool(DELEGATECALL_PATTERN.search(combined)),
                "pattern": DELEGATECALL_PATTERN.pattern,
                "description": "delegatecall usage — core of proxy pattern",
                "severity": "info",
            },
            "implementation_variable": {
                "detected": bool(IMPLEMENTATION_PATTERN.search(combined)),
                "pattern": IMPLEMENTATION_PATTERN.pattern,
                "description": "Implementation address storage variable",
                "severity": "info",
            },
            "uups": {
                "detected": bool(UPGRADE_PATTERN.search(combined)),
                "pattern": UPGRADE_PATTERN.pattern,
                "description": "UUPS (ERC-1822) proxy pattern",
                "severity": "info",
            },
            "transparent_proxy": {
                "detected": bool(TRANSPARENT_PATTERN.search(combined)),
                "pattern": TRANSPARENT_PATTERN.pattern,
                "description": "Transparent Proxy pattern with ProxyAdmin",
                "severity": "info",
            },
            "beacon_proxy": {
                "detected": bool(BEACON_PATTERN.search(combined)),
                "pattern": BEACON_PATTERN.pattern,
                "description": "Beacon Proxy pattern",
                "severity": "info",
            },
            "initializer": {
                "detected": bool(INITIALIZER_PATTERN.search(combined)),
                "pattern": INITIALIZER_PATTERN.pattern,
                "description": "Initializer function (replaces constructor in proxies)",
                "severity": "info",
            },
            "storage_gap": {
                "detected": bool(STORAGE_GAP_PATTERN.search(combined)),
                "pattern": STORAGE_GAP_PATTERN.pattern,
                "description": "Storage gap for upgradeable contract safety",
                "severity": "info",
            },
            "ownable_upgradeable": {
                "detected": bool(OWNABLE_UPGRADE_PATTERN.search(combined)),
                "pattern": OWNABLE_UPGRADE_PATTERN.pattern,
                "description": "OwnableUpgradeable or onlyOwner pattern",
                "severity": "info",
            },
        }

        # Classify the proxy pattern
        upgrade_type = self._classify_proxy(patterns)

        # Count occurrences
        details: dict[str, int] = {}
        for name, pat_info in patterns.items():
            if pat_info["detected"]:
                details[name] = len(re.findall(pat_info["pattern"], combined, re.IGNORECASE))

        risk = self._assess_risk(patterns, upgrade_type)

        return {
            "contract_name": contract_name,
            "is_upgradeable": upgrade_type is not None,
            "upgrade_type": upgrade_type,
            "patterns": {k: v["detected"] for k, v in patterns.items()},
            "pattern_details": details,
            "risk_assessment": risk,
            "recommendations": self._recommendations(patterns, upgrade_type),
        }

    def _classify_proxy(self, patterns: dict[str, dict[str, Any]]) -> str | None:
        if patterns["uups"]["detected"] and patterns["delegatecall"]["detected"]:
            return "UUPS (ERC-1822)"
        if patterns["transparent_proxy"]["detected"]:
            return "Transparent Proxy"
        if patterns["beacon_proxy"]["detected"]:
            return "Beacon Proxy"
        if patterns["delegatecall"]["detected"] and patterns["implementation_variable"]["detected"]:
            return "Custom Proxy"
        if patterns["delegatecall"]["detected"]:
            return "Unknown Proxy (delegatecall present)"
        return None

    def _assess_risk(self, patterns: dict[str, dict[str, Any]], upgrade_type: str | None) -> dict[str, Any]:
        risks: list[str] = []
        score = 0

        if upgrade_type is not None:
            risks.append("Contract is upgradeable — implementation can change")
            score += 1

        if patterns["delegatecall"]["detected"] and not patterns["uups"]["detected"] and not patterns["transparent_proxy"]["detected"]:
            risks.append("Non-standard delegatecall usage — review authorization")
            score += 2

        if patterns["initializer"]["detected"] and not patterns["storage_gap"]["detected"]:
            risks.append("Initializer present but no storage gap — storage collision risk")
            score += 2

        if patterns["initializer"]["detected"] and not patterns["ownable_upgradeable"]["detected"]:
            risks.append("Initializer without access control — anyone could re-initialize")
            score += 3

        severity = "low" if score <= 1 else ("medium" if score <= 3 else "high")
        return {
            "score": score,
            "severity": severity,
            "risks": risks,
        }

    def _recommendations(self, patterns: dict[str, dict[str, Any]], upgrade_type: str | None) -> list[str]:
        recs: list[str] = []

        if patterns["initializer"]["detected"] and not patterns["ownable_upgradeable"]["detected"]:
            recs.append("Add OwnableUpgradeable or access control to initializer")

        if patterns["initializer"]["detected"] and not patterns["storage_gap"]["detected"]:
            recs.append("Add __gap storage array to all upgradeable contracts")

        if upgrade_type is None and patterns["delegatecall"]["detected"]:
            recs.append("Document the authorization mechanism for delegatecall")

        if upgrade_type == "Custom Proxy" and patterns["delegatecall"]["detected"]:
            recs.append("Consider using a standard proxy pattern (UUPS or Transparent)")

        if not recs:
            recs.append("No critical upgrade-related issues detected")

        return recs
