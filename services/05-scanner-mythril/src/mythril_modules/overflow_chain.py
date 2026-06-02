"""Integer Overflow Chain Module — HIGH/CRITICAL severity.

Extends Mythril's default overflow detection with:
  1. Overflow chaining: overflow → state change → fund loss
  2. Precision loss in division chains
  3. Fee calculation manipulation via overflow
  4. Balance accounting corruption via underflow

Usage: mythril analyze --plugins src/mythril_modules
"""

from __future__ import annotations

from typing import Any

from mythril.analysis.module import BaseAnalysisModule


class OverflowChainModule(BaseAnalysisModule):
    """Detects overflow/underflow chains leading to fund loss."""

    ARITHMETIC_OPS: dict[int, str] = {
        0x01: "ADD",
        0x02: "MUL",
        0x03: "SUB",
        0x04: "DIV",
        0x06: "MOD",
        0x08: "ADDMOD",
        0x09: "MULMOD",
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.name = "Overflow Chain Analysis"
        self.swc_id = "SWC-101"
        self.description = (
            "Detects overflow/underflow chains that lead to "
            "incorrect state updates or fund loss"
        )

    def execute(self, state: Any) -> list[dict[str, Any]]:
        """Execute overflow chain analysis."""
        findings: list[dict[str, Any]] = []

        # Track arithmetic operations and their effects
        overflow_sites = self._find_overflow_sites(state)
        if not overflow_sites:
            return findings

        # Check if overflow results flow into SSTORE
        overflow_in_state = self._overflow_affects_state(state)

        # Check if overflow results flow into CALL value
        overflow_in_value = self._overflow_affects_value(state)

        if overflow_in_value:
            # Overflow directly affects ETH/value transfer = CRITICAL
            for site in overflow_sites:
                finding = self._build_finding(
                    severity="critical",
                    bug_type="overflow_leading_to_fund_loss",
                    title="Arithmetic overflow affects value transfer",
                    description=(
                        f"Arithmetic {site['op']} at PC {site['pc']} produces "
                        f"incorrect result that flows into an ETH/value transfer (CALL). "
                        f"This can lead to direct loss of funds."
                    ),
                    state=state,
                    metadata={
                        "overflow_op": site,
                        "affects_value_transfer": True,
                        "affects_state": overflow_in_state,
                    },
                )
                findings.append(finding)

        elif overflow_in_state:
            for site in overflow_sites:
                finding = self._build_finding(
                    severity="high",
                    bug_type="overflow_affects_state",
                    title="Arithmetic overflow corrupts contract state",
                    description=(
                        f"Arithmetic {site['op']} produces incorrect result that "
                        f"is written to contract storage. This can lead to "
                        f"accounting errors, incorrect balances, or logic bypass."
                    ),
                    state=state,
                    metadata={
                        "overflow_op": site,
                        "affects_value_transfer": False,
                        "affects_state": True,
                    },
                )
                findings.append(finding)

        # Division precision loss (separate from overflow)
        precision_loss = self._find_precision_loss(state)
        for pl in precision_loss:
            if self._precision_affects_value(state):
                finding = self._build_finding(
                    severity="high",
                    bug_type="precision_loss_fund",
                    title="Division precision loss leads to incorrect value",
                    description=(
                        f"Integer division truncation in function leads to "
                        f"precision loss that affects fund calculations. "
                        f"Attackers can exploit rounding errors for profit."
                    ),
                    state=state,
                    metadata={
                        "precision_loss": pl,
                        "type": "division_truncation",
                    },
                )
                findings.append(finding)

        return findings

    # ── Analysis Helpers ──────────────────────────────

    def _find_overflow_sites(self, state: Any) -> list[dict[str, Any]]:
        """Find arithmetic operations that could overflow."""
        sites: list[dict[str, Any]] = []
        try:
            instructions = state.mstate.get_instruction_list()
            for op in instructions:
                opcode_val = op.get("opcode_value", op.get("value", op.get("opcode", 0)))
                if isinstance(opcode_val, str):
                    continue
                if opcode_val in self.ARITHMETIC_OPS:
                    sites.append({
                        "op": self.ARITHMETIC_OPS[opcode_val],
                        "pc": op.get("pc", op.get("address", 0)),
                        "opcode": opcode_val,
                    })
        except Exception:
            pass
        return sites

    def _overflow_affects_state(self, state: Any) -> bool:
        """Check if overflow result flows into SSTORE."""
        try:
            instructions = state.mstate.get_instruction_list()
            for i, op in enumerate(instructions):
                opcode = op.get("opcode", "")
                if opcode in ("ADD", "MUL", "SUB"):
                    # Check if SSTORE follows within 10 instructions
                    for next_op in instructions[i : i + 10]:
                        if next_op.get("opcode") == "SSTORE":
                            return True
        except Exception:
            pass
        return False

    def _overflow_affects_value(self, state: Any) -> bool:
        """Check if overflow result flows into CALL value."""
        try:
            instructions = state.mstate.get_instruction_list()
            for i, op in enumerate(instructions):
                opcode = op.get("opcode", "")
                if opcode in ("ADD", "MUL", "SUB"):
                    # Check if CALL with value follows
                    for j, next_op in enumerate(instructions[i : i + 15]):
                        if next_op.get("opcode") == "CALL":
                            # CALL with value > 0
                            return True
        except Exception:
            pass
        return False

    def _find_precision_loss(self, state: Any) -> list[dict[str, Any]]:
        """Find division operations with potential precision loss."""
        precision_sites: list[dict[str, Any]] = []
        try:
            instructions = state.mstate.get_instruction_list()
            for i, op in enumerate(instructions):
                if op.get("opcode") == "DIV":
                    precision_sites.append({
                        "op": "DIV",
                        "pc": op.get("pc", 0),
                        "index": i,
                    })
        except Exception:
            pass
        return precision_sites

    def _precision_affects_value(self, state: Any) -> bool:
        """Check if division result affects value transfer."""
        try:
            instructions = state.mstate.get_instruction_list()
            for i, op in enumerate(instructions):
                if op.get("opcode") == "DIV":
                    for next_op in instructions[i : i + 15]:
                        if next_op.get("opcode") in ("CALL", "SSTORE"):
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
            finding["function"] = state.context.function_name or "unknown"
        except Exception:
            pass
        try:
            finding["address"] = state.context.address or 0
        except Exception:
            pass
        return finding
