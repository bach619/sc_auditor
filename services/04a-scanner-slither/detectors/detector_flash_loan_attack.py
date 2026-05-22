"""Flash Loan Attack Detector.
Detects potential flash loan attack vectors — missing balance verification after callbacks.
"""
from slither.detectors.abstract_detector import AbstractDetector, DetectorClassification


class FlashLoanAttackDetector(AbstractDetector):
    NAME = "flash-loan-attack"
    DESCRIPTION = "Detect potential flash loan attack vectors — missing balance verification after callback"
    IMPACT = DetectorClassification.HIGH

    def detect(self):
        results = []
        for contract in self.slither.contracts:
            for func in contract.functions_entry_points:
                if self._is_flash_loan_callback(func):
                    if not self._has_balance_verification(func):
                        info = [
                            "Flash loan callback without balance verification.",
                            f"Contract: {contract.name}",
                            f"Function: {func.name}",
                            "Missing balance check after flash loan callback — potential price manipulation.",
                        ]
                        res = self.generate_result(info)
                        results.append(res)
        return results

    def _is_flash_loan_callback(self, func) -> bool:
        """Check if function looks like a flash loan callback."""
        name = func.name.lower()
        return any(kw in name for kw in ["flash", "callback", "onflash", "afterflash"])

    def _has_balance_verification(self, func) -> bool:
        """Check if function contains balance or reserve verification."""
        for node in func.slither_nodes_structured:
            if "balance" in str(node).lower() or "reserve" in str(node).lower():
                if "require" in str(node) or "assert" in str(node) or "revert" in str(node):
                    return True
        return False
