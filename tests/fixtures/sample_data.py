"""Sample test data for all Vyper services.

These values are used across service tests to ensure consistent,
realistic test inputs.
"""

from typing import Any

# ── Contract Addresses ──────────────────────────────────────────

WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
USDC_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
UNISWAP_V2_ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"

MOCK_CONTRACT_ADDRESSES: list[str] = [
    WETH_ADDRESS,
    USDC_ADDRESS,
    UNISWAP_V2_ROUTER,
]

# ── Audit Payloads ──────────────────────────────────────────────

SAMPLE_AUDIT_PAYLOAD: dict[str, Any] = {
    "chain": "ethereum",
    "address": WETH_ADDRESS,
    "program": "test-program",
    "priority": 5,
    "metadata": {"source": "integration-test"},
}

SAMPLE_AUDIT_PAYLOAD_BSC: dict[str, Any] = {
    "chain": "bsc",
    "address": "0x0000000000000000000000000000000000001004",
    "program": "test-bsc",
    "priority": 3,
}

SAMPLE_AUDIT_PAYLOAD_POLYGON: dict[str, Any] = {
    "chain": "polygon",
    "address": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
    "program": "test-polygon",
    "priority": 1,
}

# ── Scanner Finding Templates ───────────────────────────────────

SLITHER_REENTRANCY_FINDING: dict[str, Any] = {
    "detector": "slither",
    "vulnerability_class": "reentrancy",
    "contract": "Vault",
    "function": "withdraw",
    "severity": "High",
    "confidence": 0.85,
    "description": "The withdraw function does not follow CEI pattern.",
    "recommendation": "Apply checks-effects-interactions pattern.",
}

MYTHRIL_REENTRANCY_FINDING: dict[str, Any] = {
    "detector": "mythril",
    "vulnerability_class": "reentrancy",
    "contract": "Vault",
    "function": "withdraw",
    "severity": "High",
    "confidence": 0.9,
    "description": "External call in withdraw allows reentrancy.",
    "recommendation": "Use reentrancy guard.",
}

ECHIDNA_FUZZ_FINDING: dict[str, Any] = {
    "detector": "echidna",
    "vulnerability_class": "integer-overflow",
    "contract": "Token",
    "function": "transfer",
    "severity": "Medium",
    "confidence": 0.6,
    "description": "Fuzzing detected overflow in transfer amount.",
    "recommendation": "Use SafeMath or Solidity 0.8+ built-in overflow checks.",
}

FORGE_BUILD_FINDING: dict[str, Any] = {
    "detector": "forge",
    "vulnerability_class": "compiler-warning",
    "contract": "Contract",
    "function": "constructor",
    "severity": "Info",
    "confidence": 1.0,
    "description": "Unused return value in constructor.",
    "recommendation": "Remove unused return or use it.",
}

HALMOS_FORMAL_FINDING: dict[str, Any] = {
    "detector": "halmos",
    "vulnerability_class": "access-control",
    "contract": "Vault",
    "function": "emergencyWithdraw",
    "severity": "Critical",
    "confidence": 0.95,
    "description": "Formal verification: emergencyWithdraw lacks access control.",
    "recommendation": "Add onlyOwner modifier to emergencyWithdraw.",
}

SCANNER_FINDINGS: list[dict[str, Any]] = [
    SLITHER_REENTRANCY_FINDING,
    MYTHRIL_REENTRANCY_FINDING,
    ECHIDNA_FUZZ_FINDING,
    FORGE_BUILD_FINDING,
    HALMOS_FORMAL_FINDING,
]

# ── Service Names ───────────────────────────────────────────────

ALL_SERVICES: list[str] = [
    "01-config",
    "02-immunefi",
    "03-source",
    "04-scanner",
    "04a-scanner-slither",
    "04b-scanner-echidna",
    "04c-scanner-forge",
    "04d-scanner-halmos",
    "05-scanner-mythril",
    "06-ai",
    "07-classifier",
    "08-exploit",
    "09-reporter",
    "10-notifier",
    "11-orchestrator",
    "12-webhook",
    "13-upkeep",
    "14-agent",
    "15-dashboard",
    "16-submission",
]
