"""Vyper Integer Safety Detector — overflow/underflow and precision loss.

Vyper has built-in overflow checking (unlike Solidity <0.8), but:
  1. Division before multiplication causes precision loss
  2. Unsafe casts (`convert(x, int256)`) can truncate
  3. `_delegate` and low-level operations may bypass checks
  4. Rounding direction issues in financial calculations

This detector focuses on precision loss and unsafe conversions.
"""
from slither.detectors.abstract_detector import AbstractDetector, DetectorClassification


class VyperIntegerSafetyDetector(AbstractDetector):
    NAME = "vyper-integer-safety"
    DESCRIPTION = "Detect integer precision loss and unsafe conversions in Vyper contracts"
    IMPACT = DetectorClassification.MEDIUM

    def detect(self):
        results = []

        for contract in self.slither.contracts:
            for func in contract.functions_entry_points:
                findings = []

                # Check for division before multiplication
                if self._has_divide_before_multiply(func):
                    findings.append(
                        "Division before multiplication pattern detected\n"
                        "\tThis can cause precision loss:\n"
                        "\t  ❌ amount = value / divisor * multiplier  # truncates first\n"
                        "\t  ✅ amount = value * multiplier / divisor  # full precision"
                    )

                # Check for unsafe convert
                if self._has_unsafe_convert(func):
                    findings.append(
                        "Unsafe type conversion detected\n"
                        "\tConverting between types may truncate values:\n"
                        "\t  ❌ convert(x, int128)  # may overflow int128 range\n"
                        "\t  ✅ Use bounds checking before conversion"
                    )

                # Check for unchecked arithmetic in loops
                if self._has_unchecked_loop_arithmetic(func):
                    findings.append(
                        "Unchecked arithmetic in loop detected\n"
                        "\tRepeated arithmetic in loops may overflow:\n"
                        "\t  ❌ for i in range(N): total += values[i]\n"
                        "\t  ✅ Use uint256 for accumulators"
                    )

                if findings:
                    info = [
                        f"Integer Safety issues in {contract.name}.{func.name}:\n"
                    ] + [f"\t- {f}\n" for f in findings]
                    res = self.generate_result(info)
                    results.append(res)

        return results

    def _has_divide_before_multiply(self, func) -> bool:
        """Check for division before multiplication pattern."""
        func_str = str(func).lower()
        lines = func_str.split("\n")
        for i, line in enumerate(lines):
            if "/" in line and i + 1 < len(lines):
                if "*" in lines[i + 1]:
                    return True
        return False

    def _has_unsafe_convert(self, func) -> bool:
        """Check for convert() calls that may truncate."""
        func_str = str(func)
        return "convert(" in func_str

    def _has_unchecked_loop_arithmetic(self, func) -> bool:
        """Check for loops with arithmetic operations."""
        func_str = str(func).lower()
        has_loop = "for " in func_str or "while " in func_str
        has_accumulator = "+=" in func_str or "total" in func_str or "sum" in func_str
        return has_loop and has_accumulator
