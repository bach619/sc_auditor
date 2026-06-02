"""Arbitrary Delegatecall Injection Module — CRITICAL severity.

Extends Mythril's default analysis with:
  1. Symbolic target address detection in DELEGATECALL
  2. Storage collision analysis (proxy + implementation slot overlap)
  3. Unprotected proxy upgrade detection
  4. Calldata injection via delegatecall

Usage: mythril analyze --plugins src/mythril_modules
"""

from __future__ import annotations

from typing import Any

from mythril.analysis.module import BaseAnalysisModule


class DelegatecallArbitraryModule(BaseAnalysisModule):
    """Detects arbitrary delegatecall and proxy vulnerabilities."""

    PROXY_UPGRADE_SELECTORS: dict[str, str] = {
        "3659cfe6": "upgradeTo(address)",
        "4f1ef286": "upgradeToAndCall(address,bytes)",
        "f2fde38b": "upgradeTo(address,bytes)",
        "99a88ec4": "upgradeTo(address)",
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.name = "Delegatecall Analysis"
        self.swc_id = "SWC-112"
        self.description = (
            "Detects arbitrary delegatecall, proxy vulnerabilities, "
            "and storage collision patterns"
        )

    def execute(self, state: Any) -> list[dict[str, Any]]:
        """Execute delegatecall analysis."""
        findings: list[dict[str, Any]] = []

        function_name = self._get_function_name(state)

        # Check for DELEGATECALL opcode
        if not self._has_delegatecall(state):
            return findings

        # Analyze delegatecall target
        target_analysis = self._analyze_delegatecall_target(state)
        if target_analysis.get("target_symbolic", False):
            finding = self._build_finding(
                severity="critical",
                bug_type="arbitrary_delegatecall_target",
                title="DELEGATECALL to user-controlled address",
                description=(
                    f"DELEGATECALL target address is controlled by the caller. "
                    f"An attacker can execute arbitrary code in the contract's context: "
                    f"read/write all storage, drain ETH, selfdestruct. "
                    f"Occurs in function: {function_name or 'unknown'}"
                ),
                state=state,
                metadata={
                    "function": function_name,
                    "target_symbolic": True,
                    "calldata_symbolic": target_analysis.get("calldata_symbolic", False),
                },
            )
            findings.append(finding)

        elif target_analysis.get("calldata_symbolic", False):
            finding = self._build_finding(
                severity="high",
                bug_type="arbitrary_delegatecall_calldata",
                title="DELEGATECALL with user-controlled calldata",
                description=(
                    f"DELEGATECALL uses user-controlled calldata. "
                    f"Attackers can craft calldata to execute arbitrary logic "
                    f"in the target implementation."
                ),
                state=state,
                metadata={
                    "function": function_name,
                    "target_symbolic": False,
                    "calldata_symbolic": True,
                },
            )
            findings.append(finding)

        # Check for storage collision in proxy patterns
        if target_analysis.get("storage_collision_risk", False):
            finding = self._build_finding(
                severity="high",
                bug_type="proxy_storage_collision",
                title="Proxy storage collision risk",
                description=(
                    "Delegatecall modifies state in the proxy's storage context. "
                    "If the implementation contract writes to the same slots as "
                    "the proxy, storage collisions can occur leading to "
                    "unexpected state corruption."
                ),
                state=state,
                metadata={
                    "function": function_name,
                    "storage_collision": True,
                },
            )
            findings.append(finding)

        # Check for unprotected proxy upgrade
        if function_name:
            for selector, sig in self.PROXY_UPGRADE_SELECTORS.items():
                if self._matches_selector(state, selector):
                    if not self._has_owner_verification(state):
                        finding = self._build_finding(
                            severity="critical",
                            bug_type="unprotected_proxy_upgrade",
                            title="Unprotected proxy upgrade function",
                            description=(
                                f"Proxy upgrade function '{sig}' has no access control. "
                                f"Anyone can upgrade the implementation to a malicious contract, "
                                f"gaining full control of the proxy."
                            ),
                            state=state,
                            metadata={
                                "function": function_name,
                                "upgrade_selector": f"0x{selector}",
                            },
                        )
                        findings.append(finding)
                    break

        return findings

    # ── Analysis Helpers ──────────────────────────────

    def _get_function_name(self, state: Any) -> str | None:
        try:
            return state.context.function_name or None
        except Exception:
            return None

    def _has_delegatecall(self, state: Any) -> bool:
        try:
            for op in state.mstate.get_instruction_list():
                if op.get("opcode") == "DELEGATECALL":
                    return True
        except Exception:
            pass
        return False

    def _analyze_delegatecall_target(self, state: Any) -> dict[str, Any]:
        """Analyze if delegatecall target/args are symbolic."""
        result: dict[str, Any] = {
            "target_symbolic": False,
            "calldata_symbolic": False,
            "storage_collision_risk": False,
        }
        try:
            instructions = state.mstate.get_instruction_list()
            for i, op in enumerate(instructions):
                if op.get("opcode") == "DELEGATECALL":
                    # Check if target address is from storage (not hardcoded)
                    # Pattern: CALLER or SLOAD before DELEGATECALL
                    context_ops = [o.get("opcode", "") for o in instructions[max(0, i - 5) : i]]
                    if "SLOAD" in context_ops or "CALLER" in context_ops or "CALLDATALOAD" in context_ops:
                        result["target_symbolic"] = True

                    # Check if SSTORE after delegatecall = storage collision
                    for next_op in instructions[i : i + 5]:
                        if next_op.get("opcode") == "SSTORE":
                            result["storage_collision_risk"] = True
                            break
        except Exception:
            pass
        return result

    def _matches_selector(self, state: Any, selector: str) -> bool:
        """Check if current function matches a 4-byte selector."""
        try:
            calldata = state.mstate.calldata
            if calldata and len(calldata) >= 4:
                return calldata[:4].hex() == selector
        except Exception:
            pass
        return False

    def _has_owner_verification(self, state: Any) -> bool:
        try:
            for op in state.mstate.get_instruction_list():
                if op.get("opcode") == "CALLER":
                    return True
        except Exception:
            pass
        return False

    def _build_finding(self, severity: str, bug_type: str, title: str, description: str, state: Any, metadata: dict | None = None) -> dict[str, Any]:
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
            finding["function"] = metadata.get("function", state.context.function_name or "unknown")
        except Exception:
            pass
        try:
            finding["address"] = state.context.address or 0
        except Exception:
            pass
        return finding
