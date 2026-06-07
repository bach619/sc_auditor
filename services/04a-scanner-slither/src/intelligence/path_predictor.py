"""Exploit Path Predictor — L4 Intelligence.

Analyzes Slither's control-flow graph (CFG) or finding locations to
predict potential exploit paths — sequences of function calls or state
changes that could lead to fund loss.

Since Slither output provides line-level source mappings but not a
full traversable CFG via JSON, this module uses a heuristic approach:

1. Parse finding line numbers to identify affected functions
2. Map known dangerous patterns to exploit scenarios
3. Build chains from entry point → intermediate step → loss

For full CFG analysis, this would integrate with Slither's Python API
directly (future enhancement).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

log = structlog.get_logger()


@dataclass
class ExploitPath:
    """A predicted exploit path from entry to impact."""

    entry_point: str  # Function name where exploit starts
    steps: list[str]  # Sequence of operations
    impact: str  # What the attacker gains
    confidence: float  # 0.0 -1.0
    severity: str  # critical / high / medium
    detector_chain: list[str]  # Detectors involved in the chain


# Known exploit patterns mapped from detector combinations
# Each pattern describes a class of exploits
EXPLOIT_PATTERNS: list[dict[str, Any]] = [
    {
        "name": "reentrancy_with_eth_drain",
        "entry_type": "external_call",
        "required_detectors": {"reentrancy-eth"},
        "booster_detectors": {"unchecked-lowlevel", "missing-zero-check"},
        "steps": [
            "Attacker calls vulnerable function with ETH",
            "Contract sends ETH to attacker before updating state",
            "Attacker's fallback function re-enters the contract",
            "Re-entry drains additional ETH before state is updated",
        ],
        "impact": "Drain contract ETH balance beyond legitimate withdrawal amount",
        "confidence": 0.90,
        "severity": "critical",
    },
    {
        "name": "delegatecall_hijack",
        "entry_type": "delegatecall",
        "required_detectors": {"controlled-delegatecall"},
        "booster_detectors": {"unchecked-lowlevel", "uninitialized-state"},
        "steps": [
            "Attacker supplies malicious implementation address",
            "delegatecall executes attacker code in proxy context",
            "Attacker code modifies storage (owner, balances)",
            "Contract state is fully compromised",
        ],
        "impact": "Complete contract takeover — attacker controls all storage",
        "confidence": 0.95,
        "severity": "critical",
    },
    {
        "name": "tx_origin_phishing",
        "entry_type": "any_call",
        "required_detectors": {"tx-origin"},
        "booster_detectors": {"arbitrary-send"},
        "steps": [
            "Attacker creates a malicious contract that calls vulnerable contract",
            "vulnerable contract uses tx.origin instead of msg.sender",
            "Attacker's contract impersonates the legitimate user",
            "Funds transferred to attacker-controlled address",
        ],
        "impact": "Attacker can drain funds by tricking users into interacting with malicious contracts",
        "confidence": 0.80,
        "severity": "high",
    },
    {
        "name": "flash_loan_price_manipulation",
        "entry_type": "any_call",
        "required_detectors": {"timestamp", "incorrect-equality"},
        "booster_detectors": {"unchecked-lowlevel"},
        "steps": [
            "Attacker takes a flash loan for large capital",
            "Exploits timestamp dependence or incorrect price calculation",
            "Manipulates pool price through sequenced trades",
            "Drains protocol through arbitrage at manipulated price",
        ],
        "impact": "Drain liquidity pools through price oracle manipulation",
        "confidence": 0.60,
        "severity": "high",
    },
    {
        "name": "uninitialized_proxy_attack",
        "entry_type": "delegatecall",
        "required_detectors": {"uninitialized-state"},
        "booster_detectors": {"controlled-delegatecall"},
        "steps": [
            "Proxy contract has uninitialized implementation address",
            "Attacker calls any function (including initialize)",
            "Attacker sets implementation address to malicious contract",
            "All subsequent calls execute attacker code in proxy context",
        ],
        "impact": "Full contract takeover via uninitialized proxy",
        "confidence": 0.85,
        "severity": "critical",
    },
    {
        "name": "signature_replay_cross_chain",
        "entry_type": "external_call",
        "required_detectors": {"incorrect-equality", "timestamp"},
        "booster_detectors": {"controlled-delegatecall"},
        "steps": [
            "Valid signature is captured from one chain",
            "No chain-id or nonce check in signature verification",
            "Same signature replayed on another chain or same chain",
            "Unauthorized actions executed on destination chain",
        ],
        "impact": "Unauthorized state changes via cross-chain signature replay",
        "confidence": 0.55,
        "severity": "high",
    },
]


class ExploitPathPredictor:
    """Predict exploit paths from Slither findings.

    Combines multiple detected issues into exploit chains and
    scores them by plausibility.
    """

    def __init__(self) -> None:
        self._patterns = EXPLOIT_PATTERNS

    def predict_paths(
        self,
        findings: list[dict[str, Any]],
        contract_type: str = "unknown",
    ) -> list[dict[str, Any]]:
        """Predict exploit paths from a set of findings.

        Args:
            findings: List of finding dicts with at least {'title', 'severity'}.
            contract_type: Optional contract type label.

        Returns:
            List of predicted exploit path dicts, sorted by confidence desc.
        """
        detector_names = set(f.get("title", "").lower() for f in findings)
        severities = {f.get("title", "").lower(): f.get("severity", "").lower() for f in findings}

        paths: list[dict[str, Any]] = []
        for pattern in self._patterns:
            required = pattern["required_detectors"]
            # Check if all required detectors are present
            if not required.issubset(detector_names):
                continue

            # Calculate confidence boost from booster detectors
            boosters_present = pattern["booster_detectors"].intersection(detector_names)
            booster_ratio = len(boosters_present) / max(len(pattern["booster_detectors"]), 1)

            # Calculate severity: base severity from pattern, boosted by present detectors
            base_severity = pattern["severity"]
            # Boost severity if critical detectors are present
            has_critical = any(
                severities.get(d, "") == "critical" for d in required
                if d in severities
            )
            if has_critical and base_severity == "high":
                base_severity = "critical"

            confidence = pattern["confidence"] * (0.8 + 0.2 * booster_ratio)
            confidence = min(1.0, max(0.1, confidence))

            paths.append({
                "name": pattern["name"],
                "entry_point": pattern["entry_type"],
                "steps": pattern["steps"],
                "impact": pattern["impact"],
                "confidence": round(confidence, 3),
                "severity": base_severity,
                "detectors_used": list(required),
                "boosters_present": list(boosters_present),
                "contract_type": contract_type,
            })

        # Sort by confidence descending
        paths.sort(key=lambda p: p["confidence"], reverse=True)

        # If no paths found, generate a generic assessment
        if not paths:
            paths.append(self._generic_assessment(findings, contract_type))

        return paths

    def get_critical_paths(
        self,
        findings: list[dict[str, Any]],
        contract_type: str = "unknown",
    ) -> list[dict[str, Any]]:
        """Get only critical/high severity exploit paths."""
        all_paths = self.predict_paths(findings, contract_type)
        return [p for p in all_paths if p["severity"] in ("critical", "high")]

    def summarize_risk(self, paths: list[dict[str, Any]]) -> dict[str, Any]:
        """Summarize exploit path analysis.

        Args:
            paths: Output from predict_paths.

        Returns:
            Summary dict with total paths, worst severity, top concern.
        """
        if not paths:
            return {
                "total_exploit_paths": 0,
                "worst_severity": "none",
                "top_concern": "No exploit paths identified",
            }

        severities = [p["severity"] for p in paths]
        worst = "critical" if "critical" in severities else (
            "high" if "high" in severities else "medium"
        )

        top = max(paths, key=lambda p: p["confidence"])

        return {
            "total_exploit_paths": len(paths),
            "worst_severity": worst,
            "top_concern": {
                "name": top["name"],
                "impact": top["impact"],
                "confidence": top["confidence"],
                "steps": top["steps"],
            },
        }

    # ── Internal ────────────────────────────────────────────

    @staticmethod
    def _generic_assessment(
        findings: list[dict[str, Any]],
        contract_type: str,
    ) -> dict[str, Any]:
        """Generate a generic exploit assessment when no specific patterns match."""
        high_count = sum(1 for f in findings if f.get("severity", "").lower() == "high")
        critical_count = sum(1 for f in findings if f.get("severity", "").lower() == "critical")

        if critical_count > 0:
            severity = "high"
            confidence = 0.5
            impact = (
                "Multiple critical issues detected. While no specific exploit chain "
                "was identified, individually critical vulnerabilities may be "
                "sufficient for fund loss."
            )
        elif high_count > 2:
            severity = "medium"
            confidence = 0.4
            impact = (
                "Several high-severity issues present. Chaining is plausible "
                "though not immediately obvious."
            )
        else:
            severity = "low"
            confidence = 0.2
            impact = (
                "No clear exploit chain identified. Individual issues are "
                "low to medium severity."
            )

        return {
            "name": "generic_assessment",
            "entry_point": "various",
            "steps": [
                "Review all findings for potential chains",
                "Assess whether multiple issues affect the same function",
                "Check if state validation ordering is correct",
            ],
            "impact": impact,
            "confidence": confidence,
            "severity": severity,
            "detectors_used": [f.get("title", "") for f in findings[:3]],
            "boosters_present": [],
            "contract_type": contract_type,
        }


def create_path_predictor() -> ExploitPathPredictor:
    return ExploitPathPredictor()
