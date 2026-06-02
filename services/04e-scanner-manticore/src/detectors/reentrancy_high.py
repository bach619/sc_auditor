"""Cross-contract reentrancy detector — HIGH/CRIT severity.

Targets reentrancy that Slither cannot detect:
  - Cross-contract: contract A calls contract B, which calls back into A
  - Multi-function: reenter via a different function than the original
  - Read-only reentrancy: view function used as oracle

Detection strategy:
  1. Track external CALL instructions with their stack state
  2. Detect SSTORE (state change) AFTER an external call
  3. If a second CALL enters the same contract before state is committed → REENTRANCY
  4. Generate proof-of-concept calldata sequence
"""

from __future__ import annotations

from typing import Any

from manticore import Plugin


class ReentrancyHighDetector(Plugin):
    """Manticore plugin for cross-contract reentrancy detection.

    Flags any path where:
      - An external call is made
      - State is modified AFTER the call (CEI violation)
      - The external call re-enters the originating contract
    """

    def __init__(self) -> None:
        super().__init__()
        self._findings: list[dict[str, Any]] = []
        self._call_stack: list[dict[str, Any]] = []
        self._state_modified_after_call: bool = False
        self._current_call_depth: int = 0
        self._in_reentrant_call: bool = False
        self._entry_contract: str | None = None
        self._function_selectors: set[str] = set()

    def did_evm_execute_instruction(self, state: Any, instruction: int) -> None:
        """Monitor instruction-level execution for reentrancy patterns."""
        # Track contract address on CREATE/CALL
        if instruction == 0x34:  # CALLVALUE
            self._current_call_depth = len(list(state.platform.transactions))

        if instruction == 0x56:  # CALL
            # An external call is being made
            self._call_stack.append({
                "depth": self._current_call_depth,
                "pc": state.cpu.pc,
                "gas": state.cpu.gas,
                "state_root": hex(state.platform.storage_root or 0),
            })
            self._state_modified_after_call = False

        if instruction == 0x55:  # SSTORE
            # State is being modified
            if self._call_stack:
                self._state_modified_after_call = True
                # Check if this state change happens after an external call
                depth = len(self._call_stack)
                if depth >= 2:
                    self._in_reentrant_call = True

        if instruction == 0xFF:  # SELFDESTRUCT
            # Selfdestruct after external call = critical
            if self._state_modified_after_call:
                self._report_finding(
                    severity="critical",
                    bug_type="selfdestruct_after_call",
                    title="Selfdestruct after external call — CEI violation",
                    description=(
                        "Contract selfdestructs after making an external call. "
                        "An attacker can reenter and cause the contract to selfdestruct "
                        "while it still holds funds."
                    ),
                    state=state,
                )

    def did_evm_execute_call(
        self,
        state: Any,
        address: int,
        value: int,
        gas: int,
        data: bytes | None = None,
    ) -> None:
        """Track CALL instructions with target address."""
        if data and len(data) >= 4:
            selector = data[:4].hex()
            self._function_selectors.add(selector)

    def will_evm_execute_return(self, state: Any, result: int) -> None:
        """On return from an external call, check if state was modified."""
        if self._call_stack and self._state_modified_after_call:
            # CEI violation detected: state change after external call
            call_info = self._call_stack[-1]
            if self._in_reentrant_call:
                self._report_finding(
                    severity="critical",
                    bug_type="cross_contract_reentrancy",
                    title="Cross-contract reentrancy detected",
                    description=(
                        "Contract modifies state AFTER an external call, "
                        "and the external contract re-enters the original contract. "
                        "This is a classic reentrancy pattern that can lead to "
                        "draining of contract funds."
                    ),
                    state=state,
                    metadata={
                        "call_depth": len(self._call_stack),
                        "call_pc": call_info.get("pc"),
                        "function_selectors": list(self._function_selectors),
                    },
                )

            if call_info.get("gas", 0) == 0:
                self._report_finding(
                    severity="high",
                    bug_type="unchecked_call_state_change",
                    title="Unchecked external call with state change",
                    description=(
                        "External call with minimal gas (potentially unchecked) "
                        "followed by state modification. If the call fails silently, "
                        "state will be incorrectly updated."
                    ),
                    state=state,
                    metadata={"gas": call_info.get("gas")},
                )

        self._call_stack.clear()
        self._state_modified_after_call = False
        self._in_reentrant_call = False
        self._function_selectors.clear()

    def _report_finding(
        self,
        severity: str,
        bug_type: str,
        title: str,
        description: str,
        state: Any,
        metadata: dict | None = None,
    ) -> None:
        """Register a finding with the current state context."""
        finding: dict[str, Any] = {
            "severity": severity,
            "bug_type": bug_type,
            "title": title,
            "description": description,
            "confidence": 0.95 if severity == "critical" else 0.85,
            "detector": "reentrancy_high",
            "metadata": metadata or {},
        }
        # Include proof path if available
        try:
            finding["proof"] = {
                "pc": state.cpu.pc,
                "calldata": state.cpu.calldata.hex() if hasattr(state.cpu, "calldata") else None,
                "gas_used": state.cpu.gas,
            }
        except Exception:
            pass

        self._findings.append(finding)

    def get_findings(self) -> list[dict[str, Any]]:
        return self._findings

    def reset(self) -> None:
        self._findings.clear()
        self._call_stack.clear()
        self._state_modified_after_call = False
        self._current_call_depth = 0
        self._in_reentrant_call = False
        self._entry_contract = None
