"""FP Pattern Matcher — known false-positive signature database.

Detects patterns in source code that indicate a Slither finding is likely
a false positive. Uses regex-based pattern matching on source code,
function signatures, and modifier usage.

Each pattern has:
  - name: Human-readable identifier
  - detector: Which Slither detector this applies to
  - patterns: List of regex patterns to match in source code
  - description: Why this is a false positive
  - confidence_penalty: How much to reduce confidence (0.0 = drop entirely)

Pattern sources:
  1. OpenZeppelin's ReentrancyGuard (nonReentrant modifier)
  2. CEI pattern (state update before external call)
  3. Known Solidity/Vyper patterns that trigger FPs
  4. Historical FP data from Experience DB
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger()

# Default path for FP pattern database
FP_PATTERNS_PATH = Path("/data/scanner-slither/fp_patterns.json")


# ── Known FP Patterns ──────────────────────────────────────

KNOWN_FP_PATTERNS: list[dict[str, Any]] = [
    # ── Reentrancy ──────────────────────────────────────────
    {
        "name": "reentrancy_guard_protected",
        "description": "Function uses nonReentrant modifier from OpenZeppelin's ReentrancyGuard",
        "detectors": ["reentrancy-eth", "reentrancy-no-eth", "reentrancy-benign", "reentrancy-events"],
        "patterns": [
            r"(nonReentrant|reentrancyGuard|noReentrancy)",
            r"ReentrancyGuard",
            r"isReentrant",
            r"reentrancy_lock",
        ],
        "source_types": ["solidity", "vyper"],
        "confidence_penalty": 1.0,  # Drop entirely — guard is definitive
        "severity_reduction": "informational",
    },
    {
        "name": "cei_pattern_applied",
        "description": "State update occurs before external call (Checks-Effects-Interactions)",
        "detectors": ["reentrancy-eth", "reentrancy-no-eth", "reentrancy-benign"],
        "patterns": [
            # Pattern: state write (e.g., balances[msg.sender] -= amount)
            # before external call (e.g., msg.sender.call)
            r"(balances\[|_balances\[|userBalance\[|collateral\[).*\b(=|-=|\+=)\b.*\n.*\.(call|transfer|send)\(",
            r"(require.*balance.*>=).*\n.*\1.*(=|-=).*\n.*\.(call|transfer|send)\(",
        ],
        "source_types": ["solidity"],
        "confidence_penalty": 0.8,  # High penalty — likely FP
        "severity_reduction": "low",
    },
    {
        "name": "only_owner_protected",
        "description": "Function is restricted to owner/admin — reentrancy risk is mitigated",
        "detectors": ["reentrancy-eth", "reentrancy-no-eth", "controlled-delegatecall"],
        "patterns": [
            r"(onlyOwner|onlyAdmin|onlyRole|onlyGovernance|auth)",
            r"(require.*msg\.sender\s*==\s*owner|require.*msg\.sender\s*==\s*admin)",
        ],
        "source_types": ["solidity"],
        "confidence_penalty": 0.5,  # Moderate penalty
        "severity_reduction": "low",
    },
    # ── Unchecked Low-Level Calls ───────────────────────────
    {
        "name": "safe_transfer_library",
        "description": "Using SafeERC20 or similar library that wraps low-level calls",
        "detectors": ["unchecked-lowlevel", "low-level-calls", "unused-return"],
        "patterns": [
            r"SafeERC20",
            r"safeTransfer\(",
            r"safeTransferFrom\(",
            r"safeApprove\(",
            r"safeDecreaseAllowance\(",
            r"Address\.sendValue\(",
        ],
        "source_types": ["solidity"],
        "confidence_penalty": 0.9,  # Almost certainly FP
        "severity_reduction": "informational",
    },
    {
        "name": "checked_return_value",
        "description": "Return value of low-level call IS checked (require or if statement)",
        "detectors": ["unchecked-lowlevel", "low-level-calls"],
        "patterns": [
            r"\.call\{.*\}.*\n.*require\(success",
            r"\.call\{.*\}.*\n.*if\s*\(!success\)",
            r"\.call\{.*\}.*\n.*assert\(success",
            r"\.call\(.*\).*\n.*require\(success",
        ],
        "source_types": ["solidity"],
        "confidence_penalty": 0.95,  # Definitely FP
        "severity_reduction": "informational",
    },
    # ── Timestamp Dependence ────────────────────────────────
    {
        "name": "deadline_pattern",
        "description": "Timestamp used as deadline/expiry — acceptable use case",
        "detectors": ["timestamp", "block-timestamp"],
        "patterns": [
            r"deadline",
            r"expir(y|ation|es|ed)",
            r"timeframe",
            r"auction.*end",
            r"vesting.*end",
            r"cliff.*timestamp",
            r"block\.timestamp.*\+\s*\d+\s*(days|hours|minutes)",
            r"block\.timestamp\s*<=\s*\w+\.?deadline",
        ],
        "source_types": ["solidity", "vyper"],
        "confidence_penalty": 0.6,  # Moderate — depends on context
        "severity_reduction": "low",
    },
    # ── Tx.Origin ───────────────────────────────────────────
    {
        "name": "defensive_tx_origin_check",
        "description": "tx.origin is used IN ADDITION to msg.sender (defense-in-depth, not auth)",
        "detectors": ["tx-origin"],
        "patterns": [
            r"tx\.origin\s*==\s*msg\.sender",
            r"tx\.origin\s*!=\s*msg\.sender",
            r"require\(tx\.origin\s*==\s*msg\.sender",
            r"tx\.origin\s*==\s*owner.*&&.*msg\.sender",
            r"msg\.sender.*&&.*tx\.origin",
        ],
        "source_types": ["solidity"],
        "confidence_penalty": 0.7,
        "severity_reduction": "informational",
    },
    # ── Variable Shadowing ──────────────────────────────────
    {
        "name": "intentional_shadowing_inheritance",
        "description": "Variable intentionally shadows parent in diamond/plugin pattern",
        "detectors": ["shadowing-state", "shadowing-abstract", "shadowing-local"],
        "patterns": [
            r"//\s*nosolhint.*shadow",
            r"//\s*shadow.*ok",
            r"//\s*forge-std",
            r"StdAssertions",
            r"Vm\.safe",
        ],
        "source_types": ["solidity"],
        "confidence_penalty": 0.7,
        "severity_reduction": "informational",
    },
    # ── Missing Zero Check ──────────────────────────────────
    {
        "name": "immutable_owner_init",
        "description": "Owner is set in constructor and can only be set once (immutable)",
        "detectors": ["missing-zero-check"],
        "patterns": [
            r"constructor\s*\([^)]*address\s+\w+[^)]*\)\s*\{\s*\n\s*\w+\s*=\s*\w+",
            r"immutable.*address",
            r"address.*immutable",
            r"i_[\w]+\s*=\s*[\w]+;\s*//\s*immutable",
        ],
        "source_types": ["solidity"],
        "confidence_penalty": 0.5,
        "severity_reduction": "low",
    },
    # ── Assembly ────────────────────────────────────────────
    {
        "name": "yul_optimization_only",
        "description": "Assembly is used for gas optimization (Yul), not for control flow hijacking",
        "detectors": ["assembly"],
        "patterns": [
            r"assembly\s*\{",
            r"//\s*yul",
            r"//\s*gas.*optim",
            r"mstore\(",
            r"mload\(",
            r"sstore\(",
            r"sload\(",
        ],
        "source_types": ["solidity"],
        "confidence_penalty": 0.3,
        "severity_reduction": "informational",
    },
    # ── Unused Return ───────────────────────────────────────
    {
        "name": "named_return_used_elsewhere",
        "description": "Named return value is actually used in function body",
        "detectors": ["unused-return"],
        "patterns": [
            r"returns\s*\([^)]+\s+\w+\)\s*\{",
            r"\w+\s*=\s*\w+;\s*\n\s*\}$",
        ],
        "source_types": ["solidity"],
        "confidence_penalty": 0.4,
        "severity_reduction": "low",
    },
]


class FalsePositivePattern:
    """A single FP pattern with matching logic."""

    def __init__(self, pattern_def: dict[str, Any]) -> None:
        self.name: str = pattern_def["name"]
        self.description: str = pattern_def["description"]
        self.detectors: list[str] = pattern_def["detectors"]
        self.patterns: list[str] = pattern_def["patterns"]
        self.source_types: list[str] = pattern_def.get("source_types", ["solidity"])
        self.confidence_penalty: float = pattern_def.get("confidence_penalty", 0.5)
        self.severity_reduction: str = pattern_def.get("severity_reduction", "low")
        self._compiled: list[re.Pattern] = [re.compile(p, re.MULTILINE | re.DOTALL) for p in self.patterns]

    def matches(self, source_code: str, detector: str) -> bool:
        """Check if the source code matches this FP pattern.

        Args:
            source_code: Combined source code of all files.
            detector: Slither detector name.

        Returns:
            True if this pattern matches (likely FP).
        """
        if detector not in self.detectors:
            return False
        for pattern in self._compiled:
            if pattern.search(source_code):
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "detectors": self.detectors,
            "confidence_penalty": self.confidence_penalty,
            "severity_reduction": self.severity_reduction,
        }


class FpPatternMatcher:
    """Match findings against known false-positive patterns.

    Usage:
        matcher = FpPatternMatcher()
        result = matcher.evaluate_finding(finding, combined_source)
        if result.is_fp:
            logger.info("FP detected", pattern=result.pattern_name)
    """

    def __init__(
        self,
        custom_patterns_path: str | Path | None = None,
    ) -> None:
        self._patterns: list[FalsePositivePattern] = [
            FalsePositivePattern(p) for p in KNOWN_FP_PATTERNS
        ]

        # Load custom patterns from file if available
        if custom_patterns_path:
            self._load_custom_patterns(Path(custom_patterns_path))

        log.info("fp_patterns.initialized", pattern_count=len(self._patterns))

    # ── Public API ──────────────────────────────────────────

    def evaluate_finding(
        self,
        finding: dict[str, Any],
        source_code: str,
    ) -> FpMatchResult:
        """Evaluate a single finding against FP patterns.

        Args:
            finding: Finding dict with at least 'title'.
            source_code: Combined source code of all files.

        Returns:
            FpMatchResult with match details.
        """
        detector = finding.get("title", "")
        if not detector:
            return FpMatchResult(is_fp=False)

        source_lower = source_code.lower()

        for pattern in self._patterns:
            if pattern.matches(source_lower, detector):
                log.debug(
                    "fp_patterns.matched",
                    pattern=pattern.name,
                    detector=detector,
                    penalty=pattern.confidence_penalty,
                )
                return FpMatchResult(
                    is_fp=True,
                    pattern_name=pattern.name,
                    description=pattern.description,
                    confidence_penalty=pattern.confidence_penalty,
                    severity_reduction=pattern.severity_reduction,
                )

        return FpMatchResult(is_fp=False)

    def evaluate_findings(
        self,
        findings: list[dict[str, Any]],
        source_code: str,
    ) -> list[FpMatchResult]:
        """Evaluate multiple findings against FP patterns."""
        return [
            self.evaluate_finding(f, source_code) for f in findings
        ]

    def add_custom_pattern(self, pattern_def: dict[str, Any]) -> None:
        """Add a custom FP pattern at runtime."""
        self._patterns.append(FalsePositivePattern(pattern_def))
        log.info("fp_patterns.added", name=pattern_def["name"])

    def get_pattern_stats(self) -> dict[str, Any]:
        """Get statistics about loaded patterns."""
        detector_coverage: dict[str, int] = {}
        for p in self._patterns:
            for d in p.detectors:
                detector_coverage[d] = detector_coverage.get(d, 0) + 1

        return {
            "total_patterns": len(self._patterns),
            "detector_coverage": detector_coverage,
            "patterns": [p.to_dict() for p in self._patterns],
        }

    # ── Internal ────────────────────────────────────────────

    def _load_custom_patterns(self, path: Path) -> None:
        """Load custom patterns from JSON file."""
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            patterns = data if isinstance(data, list) else data.get("patterns", [])
            for p in patterns:
                self._patterns.append(FalsePositivePattern(p))
            log.info("fp_patterns.custom_loaded", count=len(patterns), source=str(path))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("fp_patterns.custom_load_failed", error=str(exc))


class FpMatchResult:
    """Result of evaluating a finding against FP patterns."""

    def __init__(
        self,
        is_fp: bool,
        pattern_name: str = "",
        description: str = "",
        confidence_penalty: float = 0.0,
        severity_reduction: str = "",
    ) -> None:
        self.is_fp = is_fp
        self.pattern_name = pattern_name
        self.description = description
        self.confidence_penalty = confidence_penalty
        self.severity_reduction = severity_reduction

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_fp": self.is_fp,
            "pattern_name": self.pattern_name,
            "description": self.description,
            "confidence_penalty": self.confidence_penalty,
            "severity_reduction": self.severity_reduction,
        }


def create_fp_pattern_matcher(
    custom_patterns_path: str | Path | None = None,
) -> FpPatternMatcher:
    """Create a configured FpPatternMatcher instance."""
    return FpPatternMatcher(custom_patterns_path=custom_patterns_path)


def save_patterns_template(path: str | Path = FP_PATTERNS_PATH) -> None:
    """Save a template patterns file for user customization."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(KNOWN_FP_PATTERNS, indent=2),
        encoding="utf-8",
    )
    log.info("fp_patterns.template_saved", path=str(path))
