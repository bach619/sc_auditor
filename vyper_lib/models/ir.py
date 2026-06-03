"""Chain-agnostic Intermediate Representation (IR) models for multi-chain smart contract analysis.

The IR layer decouples chain-specific parsing from chain-agnostic analysis.
Each chain adapter (EVM, Cairo, Move, Rust) converts its native representation
into this unified IR, allowing all analysis engines to work on a single model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


# ── IR Operation Types ──────────────────────────────────────────


class IROpType(str, Enum):
    """Chain-agnostic IR operation types covering all VM semantics."""

    # Storage operations
    LOAD_STORAGE = "load_storage"
    STORE_STORAGE = "store_storage"

    # Memory operations
    LOAD_MEMORY = "load_memory"
    STORE_MEMORY = "store_memory"

    # Arithmetic
    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"
    MOD = "mod"
    EXP = "exp"

    # Bitwise
    AND = "and"
    OR = "or"
    XOR = "xor"
    NOT = "not"
    SHL = "shl"
    SHR = "shr"

    # Comparison
    LT = "lt"
    GT = "gt"
    EQ = "eq"
    IS_ZERO = "is_zero"

    # Control flow
    JUMP = "jump"
    JUMP_IF = "jump_if"
    CALL = "call"
    STATIC_CALL = "static_call"
    DELEGATE_CALL = "delegate_call"
    RETURN = "return"
    REVERT = "revert"
    STOP = "stop"

    # Stack operations
    PUSH = "push"
    POP = "pop"
    DUP = "dup"
    SWAP = "swap"

    # Logging
    LOG = "log"

    # External queries
    BALANCE = "balance"
    EXTCODE_SIZE = "extcode_size"
    EXTCODE_HASH = "extcode_hash"

    # ── Semantic (protocol-level) operations ──
    TRANSFER = "transfer"
    MINT = "mint"
    BURN = "burn"
    APPROVE = "approve"
    SWAP = "swap"
    ADD_LIQUIDITY = "add_liquidity"
    REMOVE_LIQUIDITY = "remove_liquidity"
    DEPOSIT = "deposit"
    BORROW = "borrow"
    REPAY = "repay"
    LIQUIDATE = "liquidate"
    STAKE = "stake"
    UNSTAKE = "unstake"
    CLAIM_REWARDS = "claim_rewards"
    PROPOSE = "propose"
    VOTE = "vote"
    EXECUTE = "execute"


# ── Protocol Classification ─────────────────────────────────────


class ProtocolType(str, Enum):
    """High-level protocol classification for context-aware analysis."""

    AMM = "amm"
    LENDING = "lending"
    BRIDGE = "bridge"
    STAKING = "staking"
    GOVERNANCE = "governance"
    NFT = "nft"
    NFT_FI = "nft_fi"
    PERPETUAL = "perpetual"
    OPTIONS = "options"
    STABLECOIN = "stablecoin"
    YIELD = "yield"
    INSURANCE = "insurance"
    ORACLE = "oracle"
    LIQUID_STAKING = "liquid_staking"
    ACCOUNT_ABSTRACTION = "account_abstraction"
    TOKEN = "token"
    UNKNOWN = "unknown"


# ── IR Data Structures ──────────────────────────────────────────


@dataclass
class IRValue:
    """A value in the IR — constant, variable reference, or computed expression.

    Examples:
        IRValue(type="constant", value=42)
        IRValue(type="variable", value="user_balance")
        IRValue(type="expression", value="user_balance + amount")
    """

    type: str  # "constant" | "variable" | "expression"
    value: Any
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IROperation:
    """A single IR instruction within a basic block."""

    id: str
    op_type: IROpType
    operands: List[IRValue] = field(default_factory=list)
    result: Optional[IRValue] = None
    source_location: Optional[Dict[str, Any]] = None  # {file, line, col}
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IRBasicBlock:
    """A basic block in the control flow graph."""

    id: str
    label: Optional[str] = None
    operations: List[IROperation] = field(default_factory=list)
    predecessors: Set[str] = field(default_factory=set)
    successors: Set[str] = field(default_factory=set)
    is_entry: bool = False
    is_exit: bool = False
    is_revert: bool = False


@dataclass
class IRFunction:
    """A function in the IR."""

    name: str
    signature: str
    visibility: str = "public"  # public | external | internal | private
    modifiers: List[str] = field(default_factory=list)
    parameters: List[Dict[str, str]] = field(default_factory=list)
    returns: List[Dict[str, str]] = field(default_factory=list)
    basic_blocks: List[IRBasicBlock] = field(default_factory=list)
    natspec: Dict[str, str] = field(default_factory=dict)
    is_payable: bool = False
    is_view: bool = False


@dataclass
class IRContract:
    """Full contract IR — the primary unit of analysis."""

    name: str
    chain: str
    language: str
    address: Optional[str] = None
    source_hash: Optional[str] = None
    compiler_version: Optional[str] = None

    functions: Dict[str, IRFunction] = field(default_factory=dict)
    storage_layout: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    state_variables: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    events: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    modifiers: Dict[str, List[IROperation]] = field(default_factory=dict)

    constructor: Optional[IRFunction] = None
    fallback: Optional[IRFunction] = None
    receive: Optional[IRFunction] = None

    inherited_contracts: List[str] = field(default_factory=list)
    external_calls: Dict[str, List[str]] = field(default_factory=dict)
    semantic_model: Dict[str, Any] = field(default_factory=dict)

    protocol_type: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IRProtocol:
    """Multi-contract protocol IR for cross-contract analysis."""

    name: str
    contracts: Dict[str, IRContract] = field(default_factory=dict)
    cross_contract_calls: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)
    shared_storage: Dict[str, List[str]] = field(default_factory=dict)
    protocol_type: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── IR Analysis Results ─────────────────────────────────────────


@dataclass
class IRAnalysisResult:
    """Unified analysis result produced by analyzing IR."""

    findings: List[Dict[str, Any]] = field(default_factory=list)
    ir_contract: Optional[IRContract] = None
    call_graph: Dict[str, Set[str]] = field(default_factory=dict)
    data_flow: Dict[str, List[str]] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
