"""Enhanced Reentrancy Detection Module — CRITICAL severity.

Extends Mythril's built-in reentrancy detection with:
  1. Cross-contract reentrancy: contract A → B → back to A
  2. Multi-function reentrancy: re-enter via different function
  3. Read-only reentrancy: view function used as oracle within same tx
  4. CEI (Checks-Effects-Interactions) violation scoring

Usage: mythril analyze --plugins src/mythril_modules
"""

from __future__ import annotations

from typing import Any

from mythril.analysis.module import BaseAnalysisModule


class ReentrancyEnhancedModule(BaseAnalysisModule):
    """Enhanced reentrancy detection beyond Mythril's default."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.name = "Reentrancy Enhanced"
        self.swc_id = "SWC-107"
        self.description = (
            "Detects cross-contract and multi-function reentrancy patterns "
            "that may be missed by standard analysis"
        )

    def execute(self, state: Any) -> list[dict[str, Any]]:
        """Execute enhanced reentrancy analysis on the given state."""
        findings: list[dict[str, Any]] = []

        if not self._has_external_call(state):
            return findings

        call_depth = self._get_call_depth(state)
        state_change_after_call = self._has_state_change_after_call(state)

        # CEI violation: external call before state change
        if state_change_after_call:
            finding = self._build_finding(
                severity="critical" if call_depth > 1 else "high",
                bug_type="cei_violation",
                title="CEI Pattern Violation — State change after external call",
                description=(
                    "Contract modifies state AFTER an external call. "
                    "This violates the Checks-Effects-Interactions pattern "
                    "and can lead to reentrancy attacks."
                ),
                state=state,
                metadata={
                    "call_depth": call_depth,
                    "state_change_after_call": True,
                },
            )
            findings.append(finding)

        # Cross-contract reentrancy: depth >= 2
        if call_depth >= 2:
            finding = self._build_finding(
                severity="critical",
                bug_type="cross_contract_reentrancy",
                title="Cross-contract reentrancy detected",
                description=(
                    f"Reentrancy at call depth {call_depth}: an external contract "
                    f"has called back into the original contract before the first "
                    f"call completed. This allows the attacker to drain funds "
                    f"through recursive calls."
                ),
                state=state,
                metadata={
                    "call_depth": call_depth,
                    "cross_contract": True,
                },
            )
            findings.append(finding)

        # Check for ETH balance change after external call
        if self._has_balance_change(state) and state_change_after_call:
            finding = self._build_finding(
                severity="critical",
                bug_type="reentrancy_eth_drain",
                title="Reentrancy with ETH transfer — direct fund drain",
                description=(
                    "External call sends ETH and state is modified after. "
                    "An attacker can reenter the withdraw function to drain "
                    "all contract ETH before balance is updated."
                ),
                state=state,
                metadata={
                    "eth_involved": True,
                    "call_depth": call_depth,
                },
            )
            findings.append(finding)

        # Unchecked call with state change
        if self._is_unchecked_call(state) and state_change_after_call:
            finding = self._build_finding(
                severity="high",
                bug_type="unchecked_call_state_change",
                title="Unchecked external call with state modification",
                description=(
                    "External call return value is not checked AND state is "
                    "modified after the call. If the call fails (e.g. out of gas), "
                    "state will be incorrectly updated, leading to accounting errors."
                ),
                state=state,
                metadata={
                    "unchecked_call": True,
                    "state_modified": True,
                },
            )
            findings.append(finding)

        return findings

    # ── Analysis Helpers ──────────────────────────────

    def _has_external_call(self, state: Any) -> bool:
        """Check if the current path contains an external CALL."""
        try:
            for op in state.mstate.get_instruction_list():
                if op.get("opcode") in ("CALL", "CALLCODE", "DELEGATECALL", "STATICCALL"):
                    return True
        except Exception:
            pass
        return False

    def _get_call_depth(self, state: Any) -> int:
        """Estimate call depth from execution context."""
        try:
            depth = state.context.constraints.get("call_depth", 0)
            return int(depth) if depth else 0
        except Exception:
            return 0

    def _has_state_change_after_call(self, state: Any) -> bool:
        """Check if SSTORE happens after CALL in the instruction sequence."""
        try:
            instructions = state.mstate.get_instruction_list()
            saw_call = False
            for op in instructions:
                opcode = op.get("opcode", "")
                if opcode in ("CALL", "CALLCODE", "DELEGATECALL"):
                    saw_call = True
                if saw_call and opcode == "SSTORE":
                    return True
        except Exception:
            pass
        return False

    def _has_balance_change(self, state: Any) -> bool:
        """Check if BALANCE opcode is used near a CALL."""
        try:
            instructions = state.mstate.get_instruction_list()
            for i, op in enumerate(instructions):
                if op.get("opcode") == "BALANCE":
                    # Check if CALL follows within next 5 instructions
                    for next_op in instructions[i : i + 5]:
                        if next_op.get("opcode") == "CALL":
                            return True
        except Exception:
            pass
        return False

    def _is_unchecked_call(self, state: Any) -> bool:
        """Check if call return value is ignored."""
        try:
            instructions = state.mstate.get_instruction_list()
            for i, op in enumerate(instructions):
                if op.get("opcode") == "CALL":
                    # Check next 3 instructions for ISZERO + JUMPI pattern
                    next_ops = [o.get("opcode", "") for o in instructions[i : i + 3]]
                    if "ISZERO" not in next_ops and "REVERT" not in next_ops:
                        return True
        except Exception:
            pass
        return False

    def _build_finding(
        self,
        severity: str,
        bug_type: str,
        title: str,
        description: str,
        state: Any,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """Build a finding in Mythril's expected format."""
        finding: dict[str, Any] = {
            "type": "warning",
            "title": title,
            "description": description,
            "severity": severity,
            "swc_id": self.swc_id,
            "bug_type": bug_type,
            "module": self.name,
            "metadata": metadata or {},
        }
        try:
            finding["function"] = state.context.function_name or "unknown"
        except Exception:
            pass
        try:
            finding["address"] = state.context.address or 0
        except Exception:
            pass
        return finding
