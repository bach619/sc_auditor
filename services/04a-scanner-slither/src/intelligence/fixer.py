"""Fix Generator — L4 Intelligence.

Produces actionable Solidity fix suggestions for each detector finding.
Uses rule-based templates per detector, with optional interpolation
of contract-specific variable names extracted from the analysis.

Architecture:
  - Each detector maps to one or more "fix templates"
  - A FixTemplate contains: description, diff (before/after), and
    optional preconditions
  - For complex detectors, multiple alternative fixes may be provided
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

log = structlog.get_logger()


@dataclass
class FixSuggestion:
    """A single fix suggestion for a finding."""

    detector: str
    title: str
    description: str
    severity: str
    before: str = ""
    after: str = ""
    diff: str = ""
    solidity_example: str = ""
    references: list[str] = field(default_factory=list)
    confidence: float = 0.8  # 0.0 (guess) to 1.0 (certain)


@dataclass
class DetectorInfo:
    """Information extracted about a detector result."""

    name: str
    severity: str
    description: str
    contract_name: str = ""
    function_name: str = ""
    line_number: int = 0
    variables: dict[str, str] = field(default_factory=dict)


# ── Fix Templates ───────────────────────────────────────────
# Keyed by detector name, each entry is a dict with fix details.

FIX_TEMPLATES: dict[str, dict[str, Any]] = {
    "reentrancy-eth": {
        "description": (
            "Reentrancy vulnerability via ETH transfer. An attacker can "
            "re-enter the contract before state updates complete."
        ),
        "before": (
            "function withdraw(uint256 amount) external {\n"
            "    require(balances[msg.sender] >= amount);\n"
            "    (bool success, ) = msg.sender.call{{value: amount}}(\"\");\n"
            "    require(success);\n"
            "    balances[msg.sender] -= amount;\n"
            "}"
        ),
        "after": (
            "function withdraw(uint256 amount) external {\n"
            "    require(balances[msg.sender] >= amount);\n"
            "    balances[msg.sender] -= amount;  // ← Checks-Effects-Interactions\n"
            "    (bool success, ) = msg.sender.call{{value: amount}}(\"\");\n"
            "    require(success);\n"
            "}"
        ),
        "solidity_example": (
            "// 🔒 Fix: Apply Checks-Effects-Interactions pattern\n"
            "// 1. Update state BEFORE external call\n"
            "// 2. Consider using OpenZeppelin ReentrancyGuard\n"
            "// 3. Limit gas for external calls (2300 for transfer/send)\n\n"
            "import \"@openzeppelin/contracts/security/ReentrancyGuard.sol\";\n\n"
            "contract SecureWithdraw is ReentrancyGuard {\n"
            "    function withdraw(uint256 amount) external nonReentrant {\n"
            "        require(balances[msg.sender] >= amount);\n"
            "        balances[msg.sender] -= amount;\n"
            "        (bool success, ) = msg.sender.call{{value: amount}}(\"\");\n"
            "        require(success);\n"
            "    }\n"
            "}"
        ),
        "references": [
            "SWC-107: https://swcregistry.io/docs/SWC-107",
            "OpenZeppelin ReentrancyGuard",
            "Checks-Effects-Interactions Pattern",
        ],
        "confidence": 0.95,
    },
    "reentrancy-no-eth": {
        "description": (
            "Reentrancy vulnerability via token/ERC20 transfer. The target "
            "contract may re-enter via a callback in the token's transfer function."
        ),
        "before": ("token.transfer(msg.sender, amount);\n" "balances[msg.sender] -= amount;"),
        "after": ("balances[msg.sender] -= amount;\n" "token.transfer(msg.sender, amount);"),
        "solidity_example": (
            "// 🔒 Fix: Apply Checks-Effects-Interactions\n"
            "// Update balances before external token transfer\n\n"
            "function withdrawToken(address token, uint256 amount) external {\n"
            "    require(balances[msg.sender][token] >= amount);\n"
            "    balances[msg.sender][token] -= amount;\n"
            "    IERC20(token).transfer(msg.sender, amount);\n"
            "}"
        ),
        "references": ["SWC-107", "Checks-Effects-Interactions Pattern"],
        "confidence": 0.90,
    },
    "unchecked-lowlevel": {
        "description": (
            "Unchecked low-level call. The return value of a low-level call "
            "(call, delegatecall, staticcall) is not checked, which may silently "
            "swallow failures."
        ),
        "before": ("(bool success, ) = target.call(data);"),
        "after": ("(bool success, ) = target.call(data);\n" "require(success, \"call failed\");"),
        "solidity_example": (
            "// 🔒 Fix: Always check the return value\n\n"
            "(bool success, bytes memory ret) = target.call(data);\n"
            "require(success, \"LowLevelCall: failed\");\n"
            "// Optionally decode and verify return data\n"
            "if (ret.length > 0) {\n"
            "    abi.decode(ret, (ExpectedType));\n"
            "}"
        ),
        "references": ["SWC-104: https://swcregistry.io/docs/SWC-104"],
        "confidence": 0.85,
    },
    "controlled-delegatecall": {
        "description": (
            "Controlled delegatecall to user-supplied address. An attacker can "
            "execute arbitrary code in the context of the calling contract."
        ),
        "before": (
            "function execute(address impl, bytes calldata data) external {\n"
            "    (bool s, ) = impl.delegatecall(data);\n"
            "    require(s);\n"
            "}"
        ),
        "after": (
            "function execute(address impl, bytes calldata data) external {\n"
            "    require(whitelisted[impl], \"not allowed\");\n"
            "    (bool s, ) = impl.delegatecall(data);\n"
            "    require(s);\n"
            "}"
        ),
        "solidity_example": (
            "// 🔒 Fix: Whitelist allowed implementations\n\n"
            "mapping(address => bool) public whitelisted;\n\n"
            "function execute(address impl, bytes calldata data) external {\n"
            "    require(whitelisted[impl], \"Unauthorized implementation\");\n"
            "    (bool s, ) = impl.delegatecall(data);\n"
            "    require(s, \"Delegatecall failed\");\n"
            "}"
        ),
        "references": ["SWC-112: https://swcregistry.io/docs/SWC-112"],
        "confidence": 0.95,
    },
    "tx-origin": {
        "description": (
            "Use of tx.origin for authentication. tx.origin returns the original "
            "sender of the transaction and can be manipulated via phishing attacks."
        ),
        "before": ("require(tx.origin == owner);"),
        "after": ("require(msg.sender == owner);"),
        "solidity_example": (
            "// 🔒 Fix: Use msg.sender instead of tx.origin\n\n"
            "modifier onlyOwner() {\n"
            "    require(msg.sender == owner, \"Not owner\");\n"
            "    _;\n"
            "}"
        ),
        "references": ["SWC-115: https://swcregistry.io/docs/SWC-115"],
        "confidence": 0.95,
    },
    "incorrect-equality": {
        "description": (
            "Incorrect equality comparison (hardcoded address). Using == to "
            "compare against a constant address may be exploited by miners."
        ),
        "before": ("require(msg.sender == 0x0000000000000000000000000000000000000000);"),
        "after": (
            "require(\n"
            "    msg.sender == address(0),\n"
            "    \"Not burn address\"\n"
            ");"
        ),
        "solidity_example": (
            "// 🔒 Fix: Use an explicit variable for clarity\n"
            "address constant BURN_ADDRESS = address(0);\n"
            "require(msg.sender == BURN_ADDRESS, \"Not burn address\");"
        ),
        "references": ["SWC-120: https://swcregistry.io/docs/SWC-120"],
        "confidence": 0.70,
    },
    "timestamp": {
        "description": (
            "Dependence on block.timestamp. Miners can manipulate timestamps "
            "within a ~30-second window."
        ),
        "solidity_example": (
            "// 🔒 Fix: Use block.number instead of block.timestamp for timing\n"
            "// or accept a ~30s manipulation window\n\n"
            "uint256 public deadline = block.timestamp + 7 days;\n"
            "// Allow ±30s deviation\n"
            "require(block.timestamp <= deadline + 30, \"Expired\");"
        ),
        "references": ["SWC-116: https://swcregistry.io/docs/SWC-116"],
        "confidence": 0.60,
    },
    "arbitrary-send": {
        "description": (
            "Arbitrary send to user-supplied address without restrictions. "
            "An attacker can drain the contract by manipulating the recipient."
        ),
        "before": ("function withdrawAll() external {\n" "    payable(msg.sender).transfer(address(this).balance);\n" "}"),
        "after": (
            "function withdrawAll() external {\n"
            "    uint256 amount = balances[msg.sender];\n"
            "    require(amount > 0);\n"
            "    balances[msg.sender] = 0;\n"
            "    payable(msg.sender).transfer(amount);\n"
            "}"
        ),
        "solidity_example": (
            "// 🔒 Fix: Limit amounts to user's balance\n\n"
            "function withdraw(uint256 amount) external {\n"
            "    require(amount <= balances[msg.sender]);\n"
            "    balances[msg.sender] -= amount;\n"
            "    payable(msg.sender).transfer(amount);\n"
            "}"
        ),
        "references": [],
        "confidence": 0.80,
    },
    "uninitialized-state": {
        "description": (
            "Uninitialized state variable. State variables default to zero, "
            "which may cause logic errors."
        ),
        "before": "address public owner;",
        "after": "address public owner = msg.sender;",
        "solidity_example": (
            "// 🔒 Fix: Initialize in constructor or declaration\n\n"
            "address public owner;\n\n"
            "constructor() {\n"
            "    owner = msg.sender;  // Initialize at deployment\n"
            "}"
        ),
        "references": ["SWC-109: https://swcregistry.io/docs/SWC-109"],
        "confidence": 0.90,
    },
    "uninitialized-storage": {
        "description": (
            "Uninitialized storage pointer. Storage pointers default to slot 0, "
            "which corrupts other state variables."
        ),
        "before": (
            "function foo() external {\n"
            "    Data storage d;\n"
            "    d.value = 42;  // Overwrites slot 0!\n"
            "}"
        ),
        "after": (
            "function foo() external {\n"
            "    Data storage d = dataMap[key];  // Must assign\n"
            "    d.value = 42;\n"
            "}"
        ),
        "solidity_example": (
            "// 🔒 Fix: Always assign a storage pointer\n\n"
            "function foo(uint256 key) external {\n"
            "    Data storage d = data[key];\n"
            "    d.value = 42;\n"
            "}"
        ),
        "references": ["SWC-109"],
        "confidence": 0.85,
    },
    "missing-zero-check": {
        "description": (
            "Missing zero-address check. Functions accepting address parameters "
            "do not validate that the address is not zero."
        ),
        "before": ("function setOwner(address newOwner) public {\n" "    owner = newOwner;\n" "}"),
        "after": (
            "function setOwner(address newOwner) public {\n"
            "    require(newOwner != address(0), \"Zero address\");\n"
            "    owner = newOwner;\n"
            "}"
        ),
        "solidity_example": (
            "// 🔒 Fix: Validate address parameters\n\n"
            "modifier notZeroAddress(address addr) {\n"
            "    require(addr != address(0), \"Zero address\");\n"
            "    _;\n"
            "}\n\n"
            "function setOwner(address newOwner) external notZeroAddress(newOwner) {\n"
            "    owner = newOwner;\n"
            "}"
        ),
        "references": [],
        "confidence": 0.75,
    },
    "suicidal": {
        "description": (
            "Contract contains a suicide/selfdestruct function. This allows "
            "the contract to be destroyed, locking all funds."
        ),
        "solidity_example": (
            "// 🔒 Fix: Remove or protect selfdestruct\n\n"
            "// ❌ Dangerous:\n"
            "// function kill() external { selfdestruct(payable(owner)); }\n\n"
            "// ✅ Better: Add timelock and multi-sig\n"
            "function kill() external onlyOwner {\n"
            "    require(block.timestamp >= destructionTime, \"Too early\");\n"
            "    selfdestruct(payable(owner));\n"
            "}"
        ),
        "references": ["SWC-106: https://swcregistry.io/docs/SWC-106"],
        "confidence": 0.85,
    },
}


class FixGenerator:
    """Generate fix suggestions for Slither findings."""

    def __init__(self) -> None:
        self._templates = FIX_TEMPLATES

    def generate_fix(
        self,
        detector: str,
        title: str,
        severity: str,
        description: str = "",
        contract_name: str = "",
    ) -> FixSuggestion:
        """Generate a single fix suggestion for a finding.

        Args:
            detector: Slither detector name (e.g., 'reentrancy-eth').
            title: Finding title/name.
            severity: Finding severity.
            description: Optional finding description.
            contract_name: Name of the affected contract.

        Returns:
            FixSuggestion with before/after code and explanation.
        """
        template = self._templates.get(detector)
        if template is None:
            # Generic fallback
            return FixSuggestion(
                detector=detector,
                title=title,
                description=description or f"Review and fix the {detector} issue.",
                severity=severity,
                confidence=0.4,
                references=[],
            )

        # Personalize with contract name if available
        solidity_example = template.get("solidity_example", "")
        if contract_name and "{contract}" in solidity_example:
            solidity_example = solidity_example.replace("{contract}", contract_name)

        return FixSuggestion(
            detector=detector,
            title=title,
            description=template.get("description", ""),
            severity=severity,
            before=template.get("before", ""),
            after=template.get("after", ""),
            solidity_example=solidity_example,
            references=template.get("references", []),
            confidence=template.get("confidence", 0.7),
        )

    def generate_fixes(
        self,
        findings: list[dict[str, Any]],
        contract_name: str = "",
    ) -> dict[str, list[dict[str, Any]]]:
        """Generate fixes for multiple findings.

        Args:
            findings: List of finding dicts with 'title' and 'severity'.
            contract_name: Contract name for personalization.

        Returns:
            Dict mapping detector names to list of fix dicts.
        """
        result: dict[str, list[dict[str, Any]]] = {}
        for finding in findings:
            detector = finding.get("title", "unknown")
            fix = self.generate_fix(
                detector=detector,
                title=str(finding.get("title", "")),
                severity=str(finding.get("severity", "medium")),
                description=str(finding.get("description", "")),
                contract_name=contract_name,
            )
            result.setdefault(detector, []).append({
                "title": fix.title,
                "description": fix.description,
                "before": fix.before,
                "after": fix.after,
                "solidity_example": fix.solidity_example,
                "references": fix.references,
                "confidence": fix.confidence,
            })
        return result

    def get_available_detectors(self) -> list[str]:
        """List all detectors with known fix templates."""
        return sorted(self._templates.keys())

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about fix template coverage."""
        return {
            "total_templates": len(self._templates),
            "detectors": sorted(self._templates.keys()),
            "high_confidence_count": sum(
                1 for t in self._templates.values() if t.get("confidence", 0) >= 0.9
            ),
        }


def create_fixer() -> FixGenerator:
    return FixGenerator()
