"""Oracle Deviation Detector — Slither custom detector.

Detects oracle price manipulation vulnerabilities. Standard tools
only check if oracle is USED — they don't check HOW.

This detector:
1. Identifies ALL oracle calls (Chainlink, TWAP, custom)
2. Checks if oracle result is validated (stale check, min/max bounds)
3. Checks if there's a fallback oracle
4. Checks for TWAP manipulation windows (short TWAP period)
5. Flags multi-oracle setups where deviation could be exploited

Vulnerability: Oracle manipulation is the #1 most expensive bug class.
  - Mango Markets: $116M (oracle price manipulation)
  - Cream Finance: $130M (flash loan + price oracle)
  - Inverse Finance: $15M (TWAP manipulation)

Usage:
  slither . --detect oracle-deviation
"""

from __future__ import annotations

import re
from typing import Any

try:
    from slither.detectors.abstract_detector import (
        AbstractDetector, DetectorClassification,
    )
    from slither.slithir.operations import HighLevelCall
    SLITHER_AVAILABLE = True
except ImportError:
    SLITHER_AVAILABLE = False
    class AbstractDetector: pass
    class DetectorClassification: pass


class OracleDeviationDetector(AbstractDetector if SLITHER_AVAILABLE else object):
    """Detect oracle price manipulation vulnerabilities.

    Checks:
    1. Is oracle result validated for staleness?
    2. Is there a min/max price bound?
    3. Is TWAP period sufficiently long?
    4. Is there a deviation check between multiple oracles?
    5. Can a single source manipulate the price feed?
    """

    ARGUMENT = "oracle-deviation"
    HELP = "Detect oracle price manipulation vulnerabilities"
    IMPACT = DetectorClassification.HIGH if SLITHER_AVAILABLE else None
    CONFIDENCE = DetectorClassification.MEDIUM if SLITHER_AVAILABLE else None

    WIKI = "https://github.com/crytic/slither/wiki/Detector-Documentation#oracle-manipulation"
    WIKI_TITLE = "Oracle Price Manipulation"
    WIKI_DESCRIPTION = "Detect vulnerabilities where oracle prices can be manipulated."
    WIKI_EXPLOIT_SCENARIO = """
    Attacker takes flash loan → manipulates Uniswap TWAP price for 1 block
    → Oracle reports manipulated price → Protocol uses this price for
    lending/liquidation → Attacker drains protocol
    """
    WIKI_RECOMMENDATION = "Use Chainlink + TWAP with deviation check. Set reasonable min/max bounds. Use sufficiently long TWAP period (≥30 min)."

    # ── Detection patterns ─────────────────────────────────────

    ORACLE_FUNCTION_SIGNATURES = [
        # Chainlink
        "latestAnswer()", "latestRoundData()", "getRoundData(",
        "decimals()", "getPrice(", "latestPrice(",
        # TWAP
        "consult(", "observe(", "quote(", "estimateAmountOut(",
        # Custom
        "getAssetPrice(", "getTokenPrice(", "getPrice(",
        "assetPrice(", "tokenPrice(", "calcPrice(",
        "fetchPrice(", "queryPrice(",
    ]

    STALENESS_CHECK_PATTERNS = [
        "updatedAt", "lastUpdated", "timestamp",
        "block.timestamp", "blockTimestamp",
        "answeredInRound", "roundId",
        "MAX_DELAY", "STALENESS_THRESHOLD",
        "priceAge", "priceTimestamp",
    ]

    MIN_MAX_BOUND_PATTERNS = [
        "MIN_PRICE", "MAX_PRICE", "minPrice", "maxPrice",
        "require(*price*>=*", "require(*price*<=*",
        "PRICE_UPPER_BOUND", "PRICE_LOWER_BOUND",
        "price >= min", "price <= max",
    ]

    DEVIATION_CHECK_PATTERNS = [
        "deviation", "DEVIATION_THRESHOLD", "MAX_DEVIATION",
        "priceDiff", "priceDelta", "abs(",
        "require(*abs(*", "require(*difference*",
        "withinRange", "withinDeviation",
    ]

    TWAP_PATTERNS = [
        "TWAP", "TimeWeightedAveragePrice", "twap",
        "observe(", "consult(", "UniswapV3OracleLibrary",
        "OracleLibrary.consult", "estimateAmountOut",
    ]

    def _detect(self) -> list:
        if not SLITHER_AVAILABLE:
            return []

        results = []
        oracle_sites: list[dict] = []

        # Step 1: Find ALL oracle call sites
        for contract in self.compilation_unit.contracts:
            for function in contract.functions:
                if not function.is_implemented:
                    continue
                for node in function.nodes:
                    for ir in node.irs:
                        if isinstance(ir, HighLevelCall):
                            self._check_oracle_call(ir, function, node, oracle_sites)

        if not oracle_sites:
            # No oracle found — this is fine, not all contracts use oracles
            pass

        # Step 2: For each oracle site, check safety measures
        for site in oracle_sites:
            issues = []

            # Check 1: Staleness validation
            if not site.get("has_staleness_check"):
                issues.append("No staleness check — could use stale price from hours/days ago")

            # Check 2: Price bounds
            if not site.get("has_price_bounds"):
                issues.append("No min/max price bounds — manipulated price passes through")

            # Check 3: Deviation between sources
            if site.get("has_multiple_oracles") and not site.get("has_deviation_check"):
                issues.append("Multiple oracle sources but no deviation check — single source can be manipulated independently")

            # Check 4: TWAP period too short
            if site.get("uses_twap") and site.get("twap_period_seconds", 0) < 1800:
                issues.append(f"TWAP period is {site['twap_period_seconds']}s (< 30 min) — can be manipulated in a single block")

            # Check 5: Single oracle with no backup
            if not site.get("has_multiple_oracles") and not site.get("has_price_bounds"):
                issues.append("Single oracle source with no safety checks — HIGH risk of manipulation")

            if issues:
                results.append(self._generate_result(site, issues))

        return results

    def _check_oracle_call(self, ir, function, node, oracle_sites: list):
        """Check if an IR operation is an oracle call and analyze its safety."""
        try:
            call_str = str(ir).lower()
        except Exception:
            return

        # Check if this call looks like an oracle query
        is_oracle = any(
            sig.lower() in call_str
            for sig in self.ORACLE_FUNCTION_SIGNATURES
        )
        if not is_oracle:
            return

        # Found an oracle call site — now analyze the function for safety checks
        function_text = self._get_function_text(function)

        site = {
            "function": f"{function.contract.name}.{function.name}()",
            "contract": function.contract.name,
            "has_staleness_check": self._has_pattern(function_text, self.STALENESS_CHECK_PATTERNS),
            "has_price_bounds": self._has_pattern(function_text, self.MIN_MAX_BOUND_PATTERNS),
            "has_deviation_check": self._has_pattern(function_text, self.DEVIATION_CHECK_PATTERNS),
            "uses_twap": self._has_pattern(function_text, self.TWAP_PATTERNS),
            "has_multiple_oracles": False,  # Set by cross-function analysis
            "twap_period_seconds": self._extract_twap_period(function_text),
        }

        # Check if contract uses multiple oracle sources
        all_functions_text = self._get_contract_text(function.contract)
        oracle_count = sum(
            1 for sig in self.ORACLE_FUNCTION_SIGNATURES
            if sig.lower() in all_functions_text.lower()
        )
        site["has_multiple_oracles"] = oracle_count > 1

        oracle_sites.append(site)

    def _has_pattern(self, text: str, patterns: list[str]) -> bool:
        """Check if text contains any pattern (supports * wildcards)."""
        text_lower = text.lower()
        for pattern in patterns:
            # Convert * wildcard to regex .*
            regex = pattern.lower().replace("*", ".*")
            if re.search(regex, text_lower):
                return True
        return False

    def _extract_twap_period(self, text: str) -> int:
        """Extract TWAP period from source code."""
        patterns = [
            r'TWAP_PERIOD\s*=\s*(\d+)',
            r'twap_period\s*=\s*(\d+)',
            r'period\s*=\s*(\d+)',
            r'window\s*=\s*(\d+)',
            r'secondsAgo\s*=\s*(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return 0

    def _get_function_text(self, function) -> str:
        """Get source code of a function."""
        try:
            return function.source_mapping.content or ""
        except Exception:
            return ""

    def _get_contract_text(self, contract) -> str:
        """Get source code of entire contract."""
        try:
            parts = []
            for function in contract.functions:
                if function.is_implemented:
                    parts.append(self._get_function_text(function))
            return "\n".join(parts)
        except Exception:
            return ""

    def _generate_result(self, site: dict, issues: list) -> Any:
        """Generate Slither finding."""
        if not SLITHER_AVAILABLE:
            return {}

        severity = "HIGH"
        if len(issues) >= 3:
            severity = "CRITICAL"

        result_text = [
            f"Oracle manipulation risk in {site['function']}:\n",
        ]
        for i, issue in enumerate(issues, 1):
            result_text.append(f"  [{i}] {issue}\n")

        result_text.append(f"\n  Oracle characteristics:\n")
        result_text.append(f"    - Staleness check: {'YES' if site['has_staleness_check'] else 'NO'}\n")
        result_text.append(f"    - Price bounds: {'YES' if site['has_price_bounds'] else 'NO'}\n")
        result_text.append(f"    - Deviation check: {'YES' if site['has_deviation_check'] else 'NO'}\n")
        result_text.append(f"    - Uses TWAP: {'YES' if site['uses_twap'] else 'NO'}\n")
        result_text.append(f"    - Multiple oracles: {'YES' if site['has_multiple_oracles'] else 'NO'}\n")

        if site["uses_twap"] and site["twap_period_seconds"] > 0:
            result_text.append(f"    - TWAP period: {site['twap_period_seconds']}s\n")

        result_text.append(f"\n  Remediation: Use Chainlink + TWAP with deviation check. Set min/max bounds. TWAP ≥ 30 min.\n")

        return self.generate_result(result_text)


def register():
    """Register this detector with Slither."""
    if SLITHER_AVAILABLE:
        from slither.detectors import all_detectors
        all_detectors.OracleDeviationDetector = OracleDeviationDetector
