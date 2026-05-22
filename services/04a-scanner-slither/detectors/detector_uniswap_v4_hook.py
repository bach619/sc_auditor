"""Uniswap v4 Hook Reentrancy Detector.
Detects external calls before state changes in hook callbacks.
"""
from slither.detectors.abstract_detector import AbstractDetector, DetectorClassification


class UniswapV4HookReentrancy(AbstractDetector):
    NAME = "uniswap-v4-hook-reentrancy"
    DESCRIPTION = "Detect reentrancy in Uniswap v4 hook callbacks — external call before state change"
    IMPACT = DetectorClassification.HIGH

    def detect(self):
        results = []
        for contract in self.slither.contracts:
            if not self._is_hook_contract(contract):
                continue
            for func in contract.functions_entry_points:
                if self._has_external_call_before_state_change(func):
                    info = [
                        "Uniswap v4 hook callback performs external call before state change.",
                        f"Contract: {contract.name}",
                        f"Function: {func.name}",
                    ]
                    res = self.generate_result(info)
                    results.append(res)
        return results

    def _is_hook_contract(self, contract) -> bool:
        interfaces = [i.name for i in contract.interfaces_inherited]
        return "IHooks" in interfaces or "BaseHook" in interfaces

    def _has_external_call_before_state_change(self, func) -> bool:
        """Check if func has external call before any state variable write."""
        if not func.all_internal_calls():
            return False
        has_ext_call = False
        has_state_change = False
        for node in func.slither_nodes_structured:
            if node.is_conditional():
                continue
            if hasattr(node, "calls") and node.calls:
                if any(".call" in str(c) for c in node.calls):
                    has_ext_call = True
            if hasattr(node, "state_variables_written") and node.state_variables_written:
                if has_ext_call:
                    return True
        return False
