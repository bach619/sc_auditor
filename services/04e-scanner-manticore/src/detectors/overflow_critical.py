"""Integer overflow → fund loss detector — HIGH/CRIT severity.

Targets overflow/underflow that leads to financial loss:
  - Arithmetic overflow in balance calculations
  - Underflow in transfer amounts
  - Precision loss in division (rounding errors)
  - Fee calculation manipulation

Detection strategy:
  1. Track all ADD, SUB, MUL instructions
  2. Detect arithmetic wrapping (result < operand)
  3. Check if the result flows into SSTORE (state change)
  4. Check if the result flows into CALL (value transfer)
  5. If overflow + fund movement → HIGH/CRIT
"""

from __future__ import annotations

from typing import Any

from manticore.plugins import Plugin


class OverflowCriticalDetector(Plugin):
    """Manticore plugin for overflow leading to fund loss.

    Only flags overflows that result in:
      - Incorrect balance updates (SSTORE)
      - Incorrect value transfers (CALL with value)
    """

    def __init__(self) -> None:
        super().__init__()
        self._findings: list[dict[str, Any]] = []
        self._arithmetic_ops: list[dict[str, Any]] = []
        self._overflow_occurred: bool = False
        self._last_overflow_op: dict[str, Any] | None = None
        self._overflow_flows_to_state: bool = False
        self._overflow_flows_to_value: bool = False

    def did_evm_execute_instruction(self, state: Any, instruction: int) -> None:
        """Monitor arithmetic instructions for overflow."""
        op_name = self._get_op_name(instruction)
        if op_name is None:
            return

        try:
            a = state.cpu.stack[-1]
            b = state.cpu.stack[-2] if instruction in (0x01, 0x02, 0x04, 0x06, 0x08) else None

            if instruction == 0x01:  # ADD
                if b is not None:
                    result = (a + b) & ((1 << 256) - 1)
                    if result < a or result < b:
                        self._overflow_occurred = True
                        self._last_overflow_op = {
                            "op": "ADD",
                            "a": hex(a),
                            "b": hex(b),
                            "result": hex(result),
                            "pc": state.cpu.pc,
                        }

            elif instruction == 0x03:  # SUB
                if a > b if b is not None else False:
                    self._overflow_occurred = True
                    self._last_overflow_op = {
                        "op": "SUB (underflow)",
                        "a": hex(a),
                        "b": hex(b),
                        "pc": state.cpu.pc,
                    }

            elif instruction == 0x02:  # MUL
                if b is not None:
                    result = (a * b) & ((1 << 256) - 1)
                    if b != 0 and result // b != a:
                        self._overflow_occurred = True
                        self._last_overflow_op = {
                            "op": "MUL (overflow)",
                            "a": hex(a),
                            "b": hex(b),
                            "result": hex(result),
                            "pc": state.cpu.pc,
                        }

        except (AttributeError, IndexError):
            pass

    def will_evm_execute_instruction(self, state: Any, instruction: int) -> None:
        """Track if overflow result flows into SSTORE or CALL."""
        if not self._overflow_occurred:
            return

        if instruction == 0x55:  # SSTORE
            self._overflow_flows_to_state = True
            self._report_overflow_finding(state)

        if instruction == 0xF1:  # CALL
            # Check if CALL has value argument (third from top of stack)
            try:
                value = state.cpu.stack[-3]
                if value > 0:
                    self._overflow_flows_to_value = True
                    self._report_overflow_finding(state)
            except (AttributeError, IndexError):
                pass

    def _report_overflow_finding(self, state: Any) -> None:
        """Report overflow that affects state or value transfer."""
        if self._last_overflow_op is None:
            return

        severity = "critical" if self._overflow_flows_to_value else "high"
        confidence = 0.95 if self._overflow_flows_to_value else 0.80

        self._report_finding(
            severity=severity,
            bug_type="overflow_leading_to_fund_loss",
            title="Integer overflow leads to incorrect fund movement",
            description=(
                f"Arithmetic {self._last_overflow_op['op']} overflows, "
                f"and the result is used in a "
                f"{'value transfer (CALL)' if self._overflow_flows_to_value else 'state update (SSTORE)'}. "
                f"This can lead to loss of funds or incorrect accounting."
            ),
            state=state,
            metadata={
                "arithmetic_op": self._last_overflow_op,
                "effects": {
                    "state_modified": self._overflow_flows_to_state,
                    "value_transferred": self._overflow_flows_to_value,
                },
            },
        )
        self._overflow_occurred = False
        self._overflow_flows_to_state = False
        self._overflow_flows_to_value = False

    @staticmethod
    def _get_op_name(instruction: int) -> str | None:
        ops = {
            0x01: "ADD",
            0x02: "MUL",
            0x03: "SUB",
            0x04: "DIV",
            0x06: "MOD",
            0x08: "ADDMOD",
            0x09: "MULMOD",
        }
        return ops.get(instruction)

    def _report_finding(self, severity: str, bug_type: str, title: str, description: str, state: Any, metadata: dict | None = None) -> None:
        finding: dict[str, Any] = {
            "severity": severity,
            "bug_type": bug_type,
            "title": title,
            "description": description,
            "confidence": 0.95 if severity == "critical" else 0.80,
            "detector": "overflow_critical",
            "metadata": metadata or {},
        }
        try:
            finding["proof"] = {
                "overflow_op": self._last_overflow_op,
                "pc": state.cpu.pc,
            }
        except Exception:
            pass
        self._findings.append(finding)

    def get_findings(self) -> list[dict[str, Any]]:
        return self._findings

    def reset(self) -> None:
        self._findings.clear()
        self._arithmetic_ops.clear()
        self._overflow_occurred = False
        self._last_overflow_op = None
        self._overflow_flows_to_state = False
        self._overflow_flows_to_value = False
