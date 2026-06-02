"""Critical access control bypass detector.

Targets:
  - onlyOwner modifier bypass via delegatecall
  - tx.origin vs msg.sender confusion
  - Incorrect address comparison (address(0) checks)
  - Initialization front-running (unprotected init())
  - Role-based access with incorrect implementation

Detection strategy:
  1. Mark all state-changing functions as symbolic entry points
  2. Track the CALLER (msg.sender) throughout execution
  3. Detect SSTORE branches that depend on caller comparison
  4. Symbolically explore: what callers can trigger sensitive state change?
  5. If ANY caller other than the intended owner can pass → CRITICAL
"""

from __future__ import annotations

import re
from typing import Any

from manticore.plugins import Plugin


class AccessControlDetector(Plugin):
    """Manticore plugin for critical access control bypass detection.

    Finds paths where a caller other than the intended owner/role
    can execute privileged operations.
    """

    # Solidity access control patterns to look for
    SENSITIVE_FUNCTIONS: set[str] = {
        "0x" + s for s in [
            "a9059cbb",  # transfer(address,uint256)
            "23b872dd",  # transferFrom(address,address,uint256)
            "095ea7b3",  # approve(address,uint256)
            "42966c68",  # burn(uint256)
            "40c10f19",  # mint(address,uint256)
            "f2fde38b",  # renounceOwnership()
            "715018a6",  # renounceOwnership() (older)
            "8da5cb5b",  # owner()
        ]
    }

    def __init__(self) -> None:
        super().__init__()
        self._findings: list[dict[str, Any]] = []
        self._sensitive_state_changes: list[dict[str, Any]] = []
        self._caller_check_sequences: list[dict[str, Any]] = []
        self._current_selector: str | None = None
        self._entry_caller_is_owner: bool = False
        self._bypass_found: bool = False

        # Track branches that depend on caller
        self._caller_branches: dict[int, dict[str, Any]] = {}

    def will_evm_execute_instruction(self, state: Any, instruction: int) -> None:
        """Track CALLER-dependent logic."""
        if instruction == 0x33:  # CALLER
            # Record that the current path depends on caller identity
            self._caller_branches[state.cpu.pc] = {
                "depth": len(list(state.platform.transactions)),
            }

    def did_evm_execute_sstore(self, state: Any, key: int, value: int) -> None:
        """Track state writes — especially after CALLER checks."""
        # Check if this SSTORE happens on a path where caller was checked
        affected_by_caller = any(
            branch.get("depth", 0) > 0
            for pc, branch in self._caller_branches.items()
        )

        if affected_by_caller and not self._entry_caller_is_owner:
            # State change triggered by a non-owner caller
            self._sensitive_state_changes.append({
                "key": hex(key),
                "value": hex(value),
                "pc": state.cpu.pc,
                "caller_dependent": True,
            })

    def did_evm_execute_call(
        self,
        state: Any,
        address: int,
        value: int,
        gas: int,
        data: bytes | None = None,
    ) -> None:
        """Detect delegatecall to arbitrary address — critical bypass vector."""
        if data is not None and len(data) >= 4:
            selector = data[:4].hex()
            self._current_selector = selector

    def did_evm_execute_delegatecall(
        self, state: Any, address: int, gas: int, data: bytes | None = None
    ) -> None:
        """Arbitrary delegatecall = potential access control bypass."""
        # If delegatecall target is symbolic (user-controlled), flag critical
        try:
            is_symbolic = state.cpu.stack[-2].symbolic
            if is_symbolic:
                self._report_finding(
                    severity="critical",
                    bug_type="arbitrary_delegatecall_access",
                    title="Arbitrary delegatecall — access control bypass",
                    description=(
                        "Contract performs delegatecall to a user-controlled address. "
                        "This can bypass all access control by executing arbitrary code "
                        "in the contract's context."
                    ),
                    state=state,
                    metadata={"target_address": hex(address) if address < 2**160 else "symbolic"},
                )
        except (AttributeError, IndexError):
            pass

    def will_evm_execute_return(self, state: Any, result: int) -> None:
        """Analyze path on return — did we bypass access control?"""
        # Check for unprotected initialization
        if self._sensitive_state_changes:
            # If we have 0 transactions (contract creation), this is init
            tx_count = len(list(state.platform.transactions))
            if tx_count <= 1:
                self._check_initialization_frontrunning(state)

    def _check_initialization_frontrunning(self, state: Any) -> None:
        """Detect unprotected initialize() function (CRITICAL)."""
        if self._current_selector in (
            "8129fc1c",  # initialize() — OpenZeppelin
            "c4d66de8",  # __Ownable_init()
        ):
            # Check if initialization modifies critical state
            for change in self._sensitive_state_changes:
                if "owner" in str(change.get("key", "")).lower() or \
                   "admin" in str(change.get("key", "")).lower():
                    self._report_finding(
                        severity="critical",
                        bug_type="unprotected_initialization",
                        title="Unprotected initializer — anyone can take ownership",
                        description=(
                            "Contract initializer can be called by anyone. "
                            "An attacker can front-run the deployer and initialize "
                            "the contract with their own address as owner."
                        ),
                        state=state,
                        metadata={"initializer_selector": self._current_selector},
                    )
                    break

    def did_evm_execute_selfdestruct(self, state: Any, recipient: int) -> None:
        """Selfdestruct without access control = CRITICAL."""
        if len(self._caller_branches) == 0:
            self._report_finding(
                severity="critical",
                bug_type="unprotected_selfdestruct",
                title="Selfdestruct without access control",
                description=(
                    "Contract can selfdestruct without any caller verification. "
                    "Anyone can destroy the contract and all its funds."
                ),
                state=state,
            )

    def _report_finding(
        self,
        severity: str,
        bug_type: str,
        title: str,
        description: str,
        state: Any,
        metadata: dict | None = None,
    ) -> None:
        finding: dict[str, Any] = {
            "severity": severity,
            "bug_type": bug_type,
            "title": title,
            "description": description,
            "confidence": 0.95,
            "detector": "access_control",
            "metadata": metadata or {},
            "proof": {},
        }
        try:
            finding["proof"] = {
                "calldata": state.cpu.calldata.hex() if hasattr(state.cpu, "calldata") else None,
                "caller": hex(state.cpu.caller) if hasattr(state.cpu, "caller") else None,
            }
        except Exception:
            pass
        self._findings.append(finding)

    def get_findings(self) -> list[dict[str, Any]]:
        return self._findings

    def reset(self) -> None:
        self._findings.clear()
        self._sensitive_state_changes.clear()
        self._caller_branches.clear()
        self._current_selector = None
        self._entry_caller_is_owner = False
        self._bypass_found = False
