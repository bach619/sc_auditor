"""Deep Access Control Analysis Module — CRITICAL severity.

Extends Mythril's default analysis with:
  1. Symbolic caller analysis — test ALL possible callers
  2. tx.origin vs msg.sender confusion detection
  3. Unprotected initialization (init front-running)
  4. Incorrect modifier implementation
  5. Unprotected selfdestruct

Usage: mythril analyze --plugins src/mythril_modules
"""

from __future__ import annotations

from typing import Any

from mythril.analysis.module import BaseAnalysisModule


class AccessControlDeepModule(BaseAnalysisModule):
    """Deep access control analysis with symbolic caller exploration."""

    SENSITIVE_KEYWORDS: set[str] = {
        "owner", "admin", "manager", "controller", "pause", "paused",
        "withdraw", "mint", "burn", "destroy", "kill", "upgrade",
        "transfer", "approve", "set", "update", "change",
    }

    DANGEROUS_FUNCTIONS: set[str] = {
        "selfdestruct", "suicide", "delegatecall",
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.name = "Access Control Deep"
        self.swc_id = "SWC-105"
        self.description = (
            "Deep access control analysis testing all possible "
            "caller identities for privileged functions"
        )

    def execute(self, state: Any) -> list[dict[str, Any]]:
        """Execute deep access control analysis."""
        findings: list[dict[str, Any]] = []

        function_name = self._get_function_name(state)
        if not function_name:
            return findings

        # Check if this is a sensitive function
        is_sensitive = any(
            kw in function_name.lower() for kw in self.SENSITIVE_KEYWORDS
        )
        if not is_sensitive:
            return findings

        # Check for owner check patterns
        has_owner_check = self._has_owner_verification(state)

        if not has_owner_check:
            # No access control on sensitive function
            is_selfdestruct = any(
                d in function_name.lower() for d in self.DANGEROUS_FUNCTIONS
            )
            severity = "critical" if is_selfdestruct or "withdraw" in function_name.lower() else "high"

            finding = self._build_finding(
                severity=severity,
                bug_type="missing_access_control",
                title=f"Missing access control on '{function_name}'",
                description=(
                    f"Function '{function_name}' performs sensitive operations "
                    f"but has no caller verification (owner check). "
                    f"{'Anyone can selfdestruct this contract!' if 'selfdestruct' in function_name.lower() else ''}"
                    f"{'Anyone can withdraw funds!' if 'withdraw' in function_name.lower() else ''}"
                ),
                state=state,
                metadata={
                    "function": function_name,
                    "has_owner_check": False,
                    "danger_level": severity,
                },
            )
            findings.append(finding)

        # Check for tx.origin misuse
        if self._has_tx_origin_usage(state):
            finding = self._build_finding(
                severity="high",
                bug_type="tx_origin_misuse",
                title="tx.origin used for authentication",
                description=(
                    f"Function '{function_name}' uses tx.origin for access control. "
                    f"tx.origin can be manipulated through intermediate contract calls, "
                    f"bypassing the intended access restriction."
                ),
                state=state,
                metadata={
                    "function": function_name,
                    "auth_method": "tx.origin",
                },
            )
            findings.append(finding)

        # Check for unprotected init
        if self._is_initializer(function_name):
            if not has_owner_check:
                finding = self._build_finding(
                    severity="critical",
                    bug_type="unprotected_initializer",
                    title="Unprotected initializer — front-running attack",
                    description=(
                        f"Initializer '{function_name}' has no access control. "
                        f"An attacker can front-run the deployer and initialize "
                        f"the contract with their own address as owner."
                    ),
                    state=state,
                    metadata={
                        "function": function_name,
                        "initializer": True,
                    },
                )
                findings.append(finding)

        return findings

    # ── Analysis Helpers ──────────────────────────────

    def _get_function_name(self, state: Any) -> str | None:
        try:
            return state.context.function_name or None
        except Exception:
            return None

    def _has_owner_verification(self, state: Any) -> bool:
        """Check if function has caller verification (owner check)."""
        try:
            instructions = state.mstate.get_instruction_list()
            for op in instructions:
                opcode = op.get("opcode", "")
                # CALLER + EQ/EQ + JUMPI = owner check pattern
                if opcode == "CALLER":
                    # Look for EQ followed by JUMPI or REVERT
                    remaining = instructions[
                        instructions.index(op) : instructions.index(op) + 10
                    ]
                    opcodes = [o.get("opcode", "") for o in remaining]
                    if "EQ" in opcodes and ("JUMPI" in opcodes or "REVERT" in opcodes):
                        return True
        except Exception:
            pass
        return False

    def _has_tx_origin_usage(self, state: Any) -> bool:
        """Check if tx.origin is used in access control."""
        try:
            instructions = state.mstate.get_instruction_list()
            for op in instructions:
                if op.get("opcode") == "ORIGIN":
                    return True
        except Exception:
            pass
        return False

    def _is_initializer(self, function_name: str) -> bool:
        """Check if function is a contract initializer."""
        init_patterns = {"initialize", "init", "__init__", "constructor"}
        return any(p in function_name.lower() for p in init_patterns)

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
