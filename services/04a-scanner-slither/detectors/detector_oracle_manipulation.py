"""Oracle Manipulation Detector.
Detects TWAP oracle usage without minimum period check — vulnerable to flash loan manipulation.
"""
from slither.detectors.abstract_detector import AbstractDetector, DetectorClassification


class OracleManipulationDetector(AbstractDetector):
    NAME = "oracle-manipulation"
    DESCRIPTION = "Detect TWAP oracle usage without minimum period check — vulnerable to flash loan attacks"
    IMPACT = DetectorClassification.HIGH

    def detect(self):
        results = []
        for contract in self.slither.contracts:
            for func in contract.functions_entry_points:
                if self._uses_twap_oracle(func) and not self._has_twap_period_check(func):
                    info = [
                        "TWAP oracle used without minimum period check.",
                        f"Contract: {contract.name}",
                        f"Function: {func.name}",
                        "Oracle manipulation via flash loans possible if TWAP period is too short or unchecked.",
                    ]
                    res = self.generate_result(info)
                    results.append(res)
        return results

    def _uses_twap_oracle(self, func) -> bool:
        """Check if function references TWAP oracle contracts."""
        for node in func.slither_nodes_structured:
            node_str = str(node).lower()
            if any(kw in node_str for kw in ["twap", "oracle", "spot", "price0", "price1", "observ", "cumulative"]):
                return True
        return False

    def _has_twap_period_check(self, func) -> bool:
        """Check if function has minimum period verification."""
        for node in func.slither_nodes_structured:
            node_str = str(node).lower()
            if any(kw in node_str for kw in ["require", "assert", "revert", "period", "minperiod", "window"]):
                return True
        return False
