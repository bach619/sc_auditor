"""Contract Classifier — L2 Intelligence.

Analyzes Solidity source code to determine the contract type (ERC20, DeFi,
NFT, Lending, etc.) and selects optimal Slither detectors accordingly.

This runs BEFORE the scan to tune which detectors are enabled.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import structlog

log = structlog.get_logger()


class ContractType(StrEnum):
    """Known contract types detected by the classifier."""

    UNKNOWN = "unknown"
    ERC20 = "erc20"
    ERC721 = "erc721"
    ERC1155 = "erc1155"
    UNISWAP_V2 = "uniswap-v2"
    UNISWAP_V3 = "uniswap-v3"
    LENDING = "lending"
    STAKING = "staking"
    GOVERNANCE = "governance"
    BRIDGE = "bridge"
    MULTISIG = "multisig"
    PROXY = "proxy"
    DEFI_AGGREGATOR = "defi-aggregator"
    OPTION = "option"
    NFT_MARKETPLACE = "nft-marketplace"
    DEX = "dex"
    VAULT = "vault"
    ORACLE = "oracle"
    CROSS_CHAIN = "cross-chain"


# ── Detection Patterns ──────────────────────────────────────
# Each pattern is: keyword → weight (0-1)

CONTRACT_SIGNATURES: dict[ContractType, dict[str, float]] = {
    ContractType.ERC20: {
        "totalSupply": 0.8,
        "balanceOf": 0.8,
        "transfer": 0.6,
        "transferFrom": 0.7,
        "approve": 0.7,
        "allowance": 0.8,
        "_mint": 0.4,
        "_burn": 0.4,
        "IERC20": 0.9,
        "import '@openzeppelin/contracts/token/ERC20/": 1.0,
    },
    ContractType.ERC721: {
        "ownerOf": 0.9,
        "tokenURI": 0.8,
        "safeTransferFrom": 0.7,
        "_safeMint": 0.5,
        "IERC721": 0.9,
        "import '@openzeppelin/contracts/token/ERC721/": 1.0,
    },
    ContractType.ERC1155: {
        "balanceOfBatch": 0.8,
        "safeBatchTransferFrom": 0.8,
        "_mintBatch": 0.6,
        "IERC1155": 0.9,
        "import '@openzeppelin/contracts/token/ERC1155/": 1.0,
    },
    ContractType.UNISWAP_V2: {
        "getReserves": 0.9,
        "swap": 0.5,
        "_swap": 0.7,
        "mint": 0.3,
        "burn": 0.3,
        "pairFor": 0.8,
        "IUniswapV2Pair": 0.9,
        "IUniswapV2Factory": 0.8,
        "import '@uniswap/v2-core/": 1.0,
    },
    ContractType.UNISWAP_V3: {
        "tickSpacing": 0.7,
        "slot0": 0.8,
        "liquidity": 0.4,
        "observe": 0.6,
        "IUniswapV3Pool": 0.9,
        "INonfungiblePositionManager": 0.8,
        "import '@uniswap/v3-core/": 1.0,
    },
    ContractType.LENDING: {
        "deposit": 0.5,
        "withdraw": 0.4,
        "borrow": 0.8,
        "repay": 0.7,
        "liquidate": 0.8,
        "collateral": 0.7,
        "healthFactor": 0.9,
        "liquidationThreshold": 0.8,
        "interestRate": 0.6,
        "ILendingPool": 0.9,
    },
    ContractType.STAKING: {
        "stake": 0.8,
        "unstake": 0.8,
        "claim": 0.4,
        "_stake": 0.7,
        "_unstake": 0.7,
        "rewardPerToken": 0.8,
        "earned": 0.7,
        "stakeToken": 0.6,
        "rewardRate": 0.7,
    },
    ContractType.GOVERNANCE: {
        "propose": 0.8,
        "vote": 0.7,
        "castVote": 0.8,
        "queue": 0.5,
        "execute": 0.4,
        "quorum": 0.8,
        "proposalThreshold": 0.7,
        "votingPeriod": 0.7,
        "IGovernor": 0.9,
    },
    ContractType.BRIDGE: {
        "sendCrossChain": 0.8,
        "receiveFromChain": 0.8,
        "verifyMessage": 0.7,
        "relay": 0.6,
        "consensus": 0.5,
        "validators": 0.6,
        "IBridge": 0.8,
    },
    ContractType.PROXY: {
        "delegatecall": 0.7,
        "implementation": 0.6,
        "_implementation": 0.7,
        "upgradeTo": 0.8,
        "upgradeAndCall": 0.8,
        "UUPS": 0.8,
        "EIP1967": 0.7,
        "IAccessControl": 0.5,
    },
    ContractType.MULTISIG: {
        "confirm": 0.6,
        "revoke": 0.5,
        "executeTransaction": 0.7,
        "required": 0.6,
        "isConfirmed": 0.7,
        "owners": 0.5,
        "GnosisSafe": 0.9,
    },
    ContractType.DEX: {
        "swap": 0.6,
        "swapExactTokensForTokens": 0.9,
        "swapTokensForExactTokens": 0.8,
        "addLiquidity": 0.8,
        "removeLiquidity": 0.8,
        "getAmountsOut": 0.7,
        "IUniswapV2Router02": 0.8,
    },
    ContractType.VAULT: {
        "deposit": 0.4,
        "withdraw": 0.3,
        "totalAssets": 0.7,
        "totalSupply": 0.3,
        "convertToShares": 0.7,
        "convertToAssets": 0.7,
        "maxWithdraw": 0.6,
        "IVault": 0.8,
    },
    ContractType.ORACLE: {
        "getPrice": 0.7,
        "latestRoundData": 0.8,
        "getRoundData": 0.7,
        "decimals": 0.3,
        "oracle": 0.5,
        "AggregatorV3Interface": 0.9,
        "IOracle": 0.8,
    },
    ContractType.CROSS_CHAIN: {
        "sendMessage": 0.7,
        "receiveMessage": 0.7,
        "sourceChain": 0.6,
        "destinationChain": 0.6,
        "nonce": 0.4,
        "merkleRoot": 0.5,
        "ILayerZero": 0.8,
        "import '@layerzerolabs/": 1.0,
    },
}


# ── Detector Priority Per Contract Type ─────────────────────
# Detectors that are most relevant for each contract type.
# These override the default tier-based selection.

DETECTOR_PRIORITY: dict[ContractType, list[str]] = {
    ContractType.ERC20: [
        "reentrancy-eth",
        "reentrancy-no-eth",
        "unchecked-lowlevel",
        "arbitrary-send",
        "tx-origin",
        "incorrect-equality",
        "shadowing-state",
        "uninitialized-state",
        "missing-zero-check",
        "unused-return",
    ],
    ContractType.ERC721: [
        "reentrancy-eth",
        "reentrancy-no-eth",
        "unchecked-lowlevel",
        "arbitrary-send",
        "shadowing-state",
        "uninitialized-state",
        "missing-zero-check",
    ],
    ContractType.LENDING: [
        "reentrancy-eth",
        "reentrancy-no-eth",
        "controlled-delegatecall",
        "timestamp",
        "unchecked-lowlevel",
        "tx-origin",
        "incorrect-equality",
        "calls-loop",
        "uninitialized-state",
        "missing-zero-check",
    ],
    ContractType.UNISWAP_V2: [
        "reentrancy-eth",
        "reentrancy-no-eth",
        "timestamp",
        "unchecked-lowlevel",
        "controlled-delegatecall",
        "tx-origin",
        "incorrect-equality",
        "calls-loop",
        "missing-zero-check",
        "arbitrary-send",
    ],
    ContractType.UNISWAP_V3: [
        "reentrancy-eth",
        "reentrancy-no-eth",
        "timestamp",
        "unchecked-lowlevel",
        "controlled-delegatecall",
        "tx-origin",
        "incorrect-equality",
        "calls-loop",
        "missing-zero-check",
        "arbitrary-send",
    ],
    ContractType.DEX: [
        "reentrancy-eth",
        "reentrancy-no-eth",
        "timestamp",
        "unchecked-lowlevel",
        "controlled-delegatecall",
        "tx-origin",
        "incorrect-equality",
        "calls-loop",
        "missing-zero-check",
        "arbitrary-send",
    ],
    ContractType.BRIDGE: [
        "controlled-delegatecall",
        "reentrancy-eth",
        "unchecked-lowlevel",
        "tx-origin",
        "incorrect-equality",
        "shadowing-abstract",
        "uninitialized-state",
        "missing-zero-check",
    ],
    ContractType.CROSS_CHAIN: [
        "controlled-delegatecall",
        "reentrancy-eth",
        "unchecked-lowlevel",
        "tx-origin",
        "incorrect-equality",
        "shadowing-abstract",
        "uninitialized-state",
        "missing-zero-check",
    ],
    ContractType.PROXY: [
        "controlled-delegatecall",
        "shadowing-abstract",
        "uninitialized-implementation",
        "uninitialized-state",
        "missing-zero-check",
        "incorrect-equality",
    ],
    ContractType.MULTISIG: [
        "reentrancy-eth",
        "unchecked-lowlevel",
        "tx-origin",
        "incorrect-equality",
        "shadowing-state",
        "missing-zero-check",
    ],
    ContractType.GOVERNANCE: [
        "reentrancy-eth",
        "unchecked-lowlevel",
        "tx-origin",
        "incorrect-equality",
        "calls-loop",
        "missing-zero-check",
        "timestamp",
    ],
    ContractType.STAKING: [
        "reentrancy-eth",
        "reentrancy-no-eth",
        "unchecked-lowlevel",
        "incorrect-equality",
        "timestamp",
        "calls-loop",
        "missing-zero-check",
        "arbitrary-send",
    ],
    ContractType.VAULT: [
        "reentrancy-eth",
        "reentrancy-no-eth",
        "unchecked-lowlevel",
        "incorrect-equality",
        "timestamp",
        "calls-loop",
        "missing-zero-check",
        "arbitrary-send",
    ],
    ContractType.ORACLE: [
        "timestamp",
        "tx-origin",
        "incorrect-equality",
        "unchecked-lowlevel",
        "missing-zero-check",
        "shadowing-state",
    ],
    ContractType.UNKNOWN: [
        "reentrancy-eth",
        "unchecked-lowlevel",
        "tx-origin",
        "incorrect-equality",
        "shadowing-state",
        "uninitialized-state",
        "missing-zero-check",
        "controlled-delegatecall",
        "arbitrary-send",
        "timestamp",
    ],
}


class ContractClassifier:
    """Classify Solidity contracts by type based on source code analysis.

    Uses function signature matching and import analysis to detect
    known contract patterns (ERC20, DeFi, NFT, etc.).
    """

    # Detectors to ALWAYS disable for this type
    TYPE_NOISE_DETECTORS: dict[ContractType, list[str]] = {
        ContractType.ERC20: ["naming-convention", "pragma", "solc-version"],
        ContractType.ERC721: ["naming-convention", "pragma"],
        ContractType.PROXY: ["naming-convention", "pragma", "constable-states"],
        ContractType.UNKNOWN: ["naming-convention", "pragma", "too-many-digits"],
    }

    def __init__(self) -> None:
        self._cache: dict[str, ContractType] = {}

    async def classify(
        self,
        sources: dict[str, str],
        address: str | None = None,
    ) -> tuple[ContractType, dict[str, Any]]:
        """Classify a contract based on its source code.

        Args:
            sources: Dict of file path → source code.
            address: Optional contract address (for caching).

        Returns:
            Tuple of (ContractType, classification_metadata).
        """
        cache_key = address or hash(frozenset(sources.items()))
        if cache_key in self._cache:
            return self._cache[cache_key], {"from_cache": True}

        # Combine all source code
        combined = "\n".join(sources.values())
        combined_lower = combined.lower()

        # Score each contract type
        scores: dict[ContractType, float] = {}
        for ctype, patterns in CONTRACT_SIGNATURES.items():
            score = 0.0
            matches = []
            for pattern, weight in patterns.items():
                if pattern.startswith("import "):
                    # Check raw import lines
                    if pattern.lower() in combined_lower:
                        score += weight * 2.0  # imports are strong signals
                        matches.append(pattern[:50])
                elif pattern in combined or pattern.lower() in combined_lower:
                    # Check for function definitions or interface usage
                    if f"function {pattern}" in combined_lower or f"{pattern}" in combined_lower:
                        score += weight
                        matches.append(pattern[:30])

            if score > 0:
                scores[ctype] = score
                log.debug("classifier.type_score", ctype=ctype.value, score=score, matches=len(matches))

        # Determine best match
        if not scores:
            result = ContractType.UNKNOWN
        else:
            # Normalize by number of patterns to avoid bias toward types with more patterns
            normalized = {
                ctype: score / max(len(CONTRACT_SIGNATURES.get(ctype, {})), 1)
                for ctype, score in scores.items()
            }
            result = max(normalized, key=normalized.get)

            # If best score is too low, downgrade to UNKNOWN
            best_score = normalized[result]
            if best_score < 0.1:
                result = ContractType.UNKNOWN

        # Cache result
        if address:
            self._cache[cache_key] = result

        metadata = {
            "contract_type": result.value,
            "scores": {k.value: round(v, 3) for k, v in scores.items()},
            "top_matches": [
                {"type": k.value, "score": round(v, 3)}
                for k, v in sorted(scores.items(), key=lambda x: -x[1])[:3]
            ],
        }

        log.info(
            "classifier.result",
            contract_type=result.value,
            top_score=round(max(scores.values(), default=0), 3),
        )

        return result, metadata

    def get_priority_detectors(self, contract_type: ContractType) -> list[str]:
        """Get the optimal detector list for a given contract type."""
        return DETECTOR_PRIORITY.get(contract_type, DETECTOR_PRIORITY[ContractType.UNKNOWN])

    def get_noise_detectors(self, contract_type: ContractType) -> list[str]:
        """Get detectors that should be suppressed for this contract type."""
        return self.TYPE_NOISE_DETECTORS.get(contract_type, [])

    def get_scan_strategy(self, contract_type: ContractType, tier: str = "default") -> dict[str, Any]:
        """Build a complete scan strategy: which detectors to enable/disable."""
        priority = self.get_priority_detectors(contract_type)
        noise = self.get_noise_detectors(contract_type)

        strategy = {
            "contract_type": contract_type.value,
            "enable_only": priority,
            "disable": noise,
            "tier": tier,
            "severity_focus": self._get_severity_focus(contract_type),
        }

        return strategy

    @staticmethod
    def _get_severity_focus(contract_type: ContractType) -> str:
        """Determine severity threshold based on contract risk profile."""
        high_risk_types = {
            ContractType.LENDING,
            ContractType.BRIDGE,
            ContractType.CROSS_CHAIN,
            ContractType.PROXY,
            ContractType.DEX,
        }
        if contract_type in high_risk_types:
            return "medium"  # Don't exclude medium findings
        return "high"  # Only high+ for low-risk types


def create_classifier() -> ContractClassifier:
    """Create a configured ContractClassifier instance."""
    return ContractClassifier()
