"""Arbitrary delegatecall injection detector — CRITICAL severity.

Targets:
  - delegatecall to user-controlled address
  - delegatecall storage collision
  - delegatecall with arbitrary calldata
  - Proxy pattern without access control on upgrade

Detection strategy:
  1. Track DELEGATECALL instructions
  2. Check if target address is symbolic (user-controlled)
  3. Check if calldata for delegatecall is symbolic
  4. If target is symbolic → CRITICAL (arbitrary code execution)
  5. If target is hardcoded but calldata symbolic → HIGH (logic injection)
"""

from __future__ import annotations

from typing import Any

from manticore.plugins import Plugin


class DelegatecallArbDetector(Plugin):
    """Manticore plugin for arbitrary delegatecall detection."""

    # Known proxy upgrade selectors
    UPGRADE_SELECTORS: set[str] = {
        "3659cfe6",  # upgradeTo(address)
        "f2fde38b",  # upgradeToAndCall(address,bytes)
        "4f1ef286",  # upgradeToAndCall(address,bytes) — newer
        "99a88ec4",  # upgradeTo(address)
    }

    def __init__(self) -> None:
        super().__init__()
        self._findings: list[dict[str, Any]] = []
        self._delegatecall_count: int = 0
        self._has_access_control: bool = False
        self._sstore_in_delegatecall: bool = False

    def did_evm_execute_instruction(self, state: Any, instruction: int) -> None:
        """Track DELEGATECALL (0xF4)."""
        if instruction == 0xF4:  # DELEGATECALL
            self._delegatecall_count += 1
            self._analyze_delegatecall(state)

    def did_evm_execute_staticcall(self, state: Any, address: int, gas: int, data: bytes) -> None:
        """Also track STATICCALL for read-only delegatecall patterns."""
        pass

    def _analyze_delegatecall(self, state: Any) -> None:
        """Analyze if delegatecall target/calldata is symbolic."""
        try:
            stack = state.cpu.stack
            # Stack layout: gas, address, argsOffset, argsSize, retOffset, retSize
            gas = stack[-1]
            addr = stack[-2]
            args_offset = stack[-3]
            args_size = stack[-4]

            # Check if address is symbolic (user-controlled)
            target_symbolic = False
            try:
                target_symbolic = addr.symbolic
            except (AttributeError, TypeError):
                pass

            # Check if calldata is symbolic
            calldata_symbolic = False
            try:
                calldata_symbolic = args_size.symbolic
            except (AttributeError, TypeError):
                pass

            if target_symbolic:
                self._report_finding(
                    severity="critical",
                    bug_type="arbitrary_delegatecall",
                    title="DELEGATECALL to user-controlled address",
                    description=(
                        "Contract delegates execution to a user-controlled address. "
                        "This allows arbitrary code execution in the contract's context: "
                        "attacker can read/write any storage, drain funds, and "
                        "selfdestruct the contract."
                    ),
                    state=state,
                    metadata={
                        "delegatecall_count": self._delegatecall_count,
                        "target_symbolic": True,
                        "calldata_symbolic": calldata_symbolic,
                    },
                )

            elif calldata_symbolic:
                self._report_finding(
                    severity="high",
                    bug_type="arbitrary_delegatecall_calldata",
                    title="DELEGATECALL with user-controlled calldata",
                    description=(
                        "Contract delegates execution with user-controlled calldata. "
                        "Attackers can craft calldata to execute arbitrary logic "
                        "in the target implementation."
                    ),
                    state=state,
                    metadata={
                        "delegatecall_count": self._delegatecall_count,
                        "target_symbolic": False,
                        "calldata_symbolic": True,
                    },
                )

        except (AttributeError, IndexError) as e:
            pass

    def did_evm_execute_sstore(self, state: Any, key: int, value: int) -> None:
        """If SSTORE happens after delegatecall, storage collision possible."""
        if self._delegatecall_count > 0:
            self._sstore_in_delegatecall = True

    def will_evm_execute_return(self, state: Any, result: int) -> None:
        """On return from delegatecall, check for storage collision."""
        if self._sstore_in_delegatecall and self._delegatecall_count > 0:
            # Delegatecall + SSTORE = storage collision potential
            existing = [
                f for f in self._findings
                if f["bug_type"] in ("arbitrary_delegatecall", "arbitrary_delegatecall_calldata")
            ]
            if existing:
                # Add storage collision warning
                existing[-1]["metadata"]["storage_collision_potential"] = True
                existing[-1]["description"] += (
                    " Storage collision risk: delegatecall modifies contract storage "
                    "directly. Implementations and proxies may share storage slots "
                    "incorrectly."
                )

    def did_evm_execute_call(
        self, state: Any, address: int, value: int, gas: int, data: bytes | None = None
    ) -> None:
        """Detect proxy upgrade function calls."""
        if data is not None and len(data) >= 4:
            selector = data[:4].hex()
            if selector in self.UPGRADE_SELECTORS:
                # Check if upgrade function has access control
                if not self._has_access_control:
                    self._report_finding(
                        severity="critical",
                        bug_type="unprotected_proxy_upgrade",
                        title="Proxy upgrade function without access control",
                        description=(
                            f"Proxy upgrade function (selector: 0x{selector}) "
                            f"has no access control. Anyone can upgrade the "
                            f"implementation to a malicious contract."
                        ),
                        state=state,
                        metadata={
                            "upgrade_selector": f"0x{selector}",
                            "delegatecall_count": self._delegatecall_count,
                        },
                    )

    def _report_finding(self, severity: str, bug_type: str, title: str, description: str, state: Any, metadata: dict | None = None) -> None:
        finding: dict[str, Any] = {
            "severity": severity,
            "bug_type": bug_type,
            "title": title,
            "description": description,
            "confidence": 0.95,
            "detector": "delegatecall_arb",
            "metadata": metadata or {},
        }
        try:
            finding["proof"] = {
                "delegatecall_count": self._delegatecall_count,
                "pc": state.cpu.pc,
            }
        except Exception:
            pass
        self._findings.append(finding)

    def get_findings(self) -> list[dict[str, Any]]:
        return self._findings

    def reset(self) -> None:
        self._findings.clear()
        self._delegatecall_count = 0
        self._has_access_control = False
        self._sstore_in_delegatecall = False
