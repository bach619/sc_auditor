"""Chain Adapter interface — abstract base for all blockchain language adapters.

Each chain/language combination gets its own adapter that:
1. Parses source code into a chain-specific AST
2. Compiles to bytecode (optional, for verification)
3. Converts to the unified Vyper IR (Intermediate Representation)
4. Provides chain-specific detectors

New chains are added by implementing a single ChainAdapter subclass.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Chain & Language Enums ──────────────────────────────────────


class Chain(str, Enum):
    """All supported blockchain networks."""

    # EVM
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    BASE = "base"
    BSC = "bsc"
    AVALANCHE = "avalanche"
    GNOSIS = "gnosis"
    FANTOM = "fantom"
    CELO = "celo"
    LINEA = "linea"
    SCROLL = "scroll"
    BLAST = "blast"
    MANTLE = "mantle"
    CRONOS = "cronos"
    ZKSYNC = "zksync"

    # Non-EVM
    STARKNET = "starknet"
    SOLANA = "solana"
    SUI = "sui"
    APTOS = "aptos"
    NEAR = "near"
    POLKADOT = "polkadot"
    FUEL = "fuel"
    COSMOS = "cosmos"
    TEZOS = "tezos"
    ALGORAND = "algorand"


class Language(str, Enum):
    """Smart contract programming languages."""

    SOLIDITY = "solidity"
    VYPER = "vyper"
    YUL = "yul"
    CAIRO = "cairo"
    MOVE = "move"
    RUST = "rust"
    SWAY = "sway"
    LIGO = "ligo"
    MICHELSON = "michelson"
    TEAL = "teal"
    PYTEAL = "pyteal"


# ── Chain Adapter Data Models ───────────────────────────────────


@dataclass
class ContractSource:
    """Unified contract source representation across all chains."""

    chain: str
    language: str
    address: Optional[str] = None
    name: str = ""
    source_files: Dict[str, str] = field(default_factory=dict)
    compiler_version: Optional[str] = None
    compiler_settings: Dict[str, Any] = field(default_factory=dict)
    dependencies: Dict[str, str] = field(default_factory=dict)
    natspec: Dict[str, Dict[str, str]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompileResult:
    """Result of compiling a smart contract."""

    success: bool
    bytecode: Optional[str] = None
    abi: Optional[List[Dict[str, Any]]] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    compiler_version: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── Abstract Chain Adapter ──────────────────────────────────────


class ChainAdapter(ABC):
    """Abstract base class for all chain adapters.

    To add a new chain/language:
    1. Subclass ChainAdapter
    2. Set `chain` and `language` class attributes
    3. Implement parse(), compile(), to_ir()
    4. Implement get_detectors(), analyze()
    5. Register in the adapter registry

    Example:
        class CairoAdapter(ChainAdapter):
            chain = Chain.STARKNET
            language = Language.CAIRO
            ...
    """

    chain: Chain
    language: Language

    # ── Source processing ───────────────────────────────────

    @abstractmethod
    async def parse(self, source: ContractSource) -> Any:
        """Parse source code into a chain-specific AST.

        Args:
            source: Unified contract source representation.

        Returns:
            Chain-specific AST object.
        """
        ...

    @abstractmethod
    async def compile(self, source: ContractSource) -> CompileResult:
        """Compile source code into bytecode.

        Args:
            source: Unified contract source representation.

        Returns:
            CompileResult with bytecode, ABI, errors, and warnings.
        """
        ...

    # ── IR conversion ───────────────────────────────────────

    @abstractmethod
    async def to_ir(self, parsed_or_compiled: Any, source: ContractSource) -> Dict[str, Any]:
        """Convert chain-specific representation to Vyper IR.

        Args:
            parsed_or_compiled: Output from parse() or compile().
            source: Original contract source for metadata.

        Returns:
            Serialized IRContract dictionary.
        """
        ...

    # ── Detectors ───────────────────────────────────────────

    @abstractmethod
    async def get_detectors(self) -> List[str]:
        """Get available detectors for this chain/language.

        Returns:
            List of detector names.
        """
        ...

    # ── Analysis ────────────────────────────────────────────

    @abstractmethod
    async def analyze(self, ir_contract: Dict[str, Any], detectors: List[str]) -> Dict[str, Any]:
        """Run analysis on an IR contract.

        Args:
            ir_contract: Serialized IRContract.
            detectors: List of detector names to run.

        Returns:
            Analysis result with findings and metrics.
        """
        ...

    # ── Utility ─────────────────────────────────────────────

    def get_supported_attack_types(self) -> List[str]:
        """Get attack types relevant to this chain/language."""
        return []

    def get_chain_info(self) -> Dict[str, Any]:
        """Get metadata about this chain adapter."""
        return {
            "chain": self.chain.value if isinstance(self.chain, Enum) else self.chain,
            "language": self.language.value if isinstance(self.language, Enum) else self.language,
            "detectors": [],
        }


# ── Adapter Registry ────────────────────────────────────────────


class AdapterRegistry:
    """Global registry of chain adapters.

    Usage:
        registry = AdapterRegistry()
        registry.register(CairoAdapter())
        adapter = registry.get(Chain.STARKNET)
    """

    def __init__(self):
        self._adapters: Dict[str, ChainAdapter] = {}

    def register(self, adapter: ChainAdapter) -> None:
        """Register a chain adapter."""
        key = f"{adapter.chain.value}:{adapter.language.value}"
        self._adapters[key] = adapter

    def get(self, chain: Chain, language: Optional[Language] = None) -> Optional[ChainAdapter]:
        """Get adapter for a chain, optionally filtered by language."""
        if language:
            key = f"{chain.value}:{language.value}"
            return self._adapters.get(key)

        # Return first adapter for this chain
        for key, adapter in self._adapters.items():
            if key.startswith(f"{chain.value}:"):
                return adapter
        return None

    def list_chains(self) -> List[str]:
        """List all chains with registered adapters."""
        chains = set()
        for key in self._adapters:
            chain = key.split(":")[0]
            chains.add(chain)
        return sorted(chains)

    def list_all(self) -> List[Dict[str, Any]]:
        """List all registered adapters with metadata."""
        return [a.get_chain_info() for a in self._adapters.values()]

    def __len__(self) -> int:
        return len(self._adapters)


# ── Global registry instance ────────────────────────────────────

adapter_registry = AdapterRegistry()
