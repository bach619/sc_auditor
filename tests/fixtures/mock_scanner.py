"""Mock scanner outputs for testing the aggregation and dedup pipeline.

Each scanner tool returns a list of findings in its own format.
These mocks simulate the raw output from:
  - Slither (static analysis)
  - Mythril (symbolic execution)
  - Echidna (fuzzing)
  - Forge (build/compiler checks)
  - Halmos (formal verification)
"""

from typing import Any


def mock_slither_output(contract: str = "Vault") -> list[dict[str, Any]]:
    """Simulated Slither JSON output."""
    return [
        {
            "detector": "slither",
            "vulnerability_class": "reentrancy",
            "contract": contract,
            "function": "withdraw",
            "severity": "High",
            "confidence": 0.85,
            "description": f"{contract}.withdraw() sends ETH without CEI pattern.",
            "recommendation": "Apply checks-effects-interactions pattern.",
            "source_line": 42,
        },
        {
            "detector": "slither",
            "vulnerability_class": "unused-return",
            "contract": contract,
            "function": "deposit",
            "severity": "Low",
            "confidence": 0.95,
            "description": "Unused return value from transfer.",
            "recommendation": "Check return value or use SafeERC20.",
            "source_line": 18,
        },
    ]


def mock_mythril_output(contract: str = "Vault") -> list[dict[str, Any]]:
    """Simulated Mythril JSON output."""
    return [
        {
            "detector": "mythril",
            "vulnerability_class": "reentrancy",
            "contract": contract,
            "function": "withdraw",
            "severity": "High",
            "confidence": 0.90,
            "description": "External call to arbitrary address in withdraw().",
            "recommendation": "Use OpenZeppelin ReentrancyGuard.",
            "swc_id": "SWC-107",
        },
    ]


def mock_echidna_output(contract: str = "Token") -> list[dict[str, Any]]:
    """Simulated Echidna fuzzing output."""
    return [
        {
            "detector": "echidna",
            "vulnerability_class": "integer-overflow",
            "contract": contract,
            "function": "transfer",
            "severity": "Medium",
            "confidence": 0.60,
            "description": "Fuzzing found overflow in transfer amount.",
            "recommendation": "Use Solidity 0.8+ built-in overflow checks.",
            "property": "transfer_never_overflows",
        },
    ]


def mock_forge_output(contract: str = "Contract") -> list[dict[str, Any]]:
    """Simulated Forge build/compiler output."""
    return [
        {
            "detector": "forge",
            "vulnerability_class": "compiler-warning",
            "contract": contract,
            "function": "constructor",
            "severity": "Info",
            "confidence": 1.0,
            "description": "Unused function parameter.",
            "recommendation": "Remove unused parameter or use it.",
        },
    ]


def mock_halmos_output(contract: str = "Vault") -> list[dict[str, Any]]:
    """Simulated Halmos formal verification output."""
    return [
        {
            "detector": "halmos",
            "vulnerability_class": "access-control",
            "contract": contract,
            "function": "emergencyWithdraw",
            "severity": "Critical",
            "confidence": 0.95,
            "description": "emergencyWithdraw() lacks access control modifier.",
            "recommendation": "Add onlyOwner modifier.",
            "formal_proof": "access_control_violation",
        },
    ]


def mock_all_scanners(contract: str = "Vault") -> dict[str, list[dict[str, Any]]]:
    """Aggregate output from all 5 scanner tools."""
    return {
        "slither": mock_slither_output(contract),
        "mythril": mock_mythril_output(contract),
        "echidna": mock_echidna_output("Token"),
        "forge": mock_forge_output("Contract"),
        "halmos": mock_halmos_output(contract),
    }
