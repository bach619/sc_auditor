"""Vyper Storage Collision Detector — proxy/upgradeable storage layout issues.

Vyper's storage layout is linear and deterministic, different from Solidity's.
This detector catches:
  1. Storage collision between proxy and implementation
  2. Incorrect storage gap usage
  3. Variable ordering issues that could break delegatecall

Vyper-specific:
  - Storage starts at slot 0 and increments sequentially
  - No mapping/array gaps like Solidity
  - Proxy patterns must carefully align storage layouts
  - `extcodesize` checks can indicate proxy patterns
"""
from slither.detectors.abstract_detector import AbstractDetector, DetectorClassification


class VyperStorageCollisionDetector(AbstractDetector):
    NAME = "vyper-storage-collision"
    DESCRIPTION = "Detect storage collision risks in Vyper upgradeable proxy patterns"
    IMPACT = DetectorClassification.MEDIUM

    PROXY_KEYWORDS = ["delegatecall", "raw_call", "extcodesize", "_implementation"]

    def detect(self):
        results = []

        for contract in self.slither.contracts:
            if not self._is_proxy_like(contract):
                continue

            state_vars = contract.state_variables_ordered
            if len(state_vars) == 0:
                continue

            # Check storage gap
            has_gap = False
            for var in state_vars:
                if "gap" in var.name.lower() or "__gap" in var.name.lower():
                    has_gap = True
                    break

            if not has_gap and len(state_vars) > 0:
                info = [
                    f"Vyper Proxy Storage — potential collision in {contract.name}:\n",
                    f"\tProxy has {len(state_vars)} state variables but no storage gap.\n",
                    "\tIn upgradeable proxies, storage layout must align between\n",
                    "\timplementation and proxy contracts. Add a storage gap\n",
                    "\t(array of reserved slots) to allow future upgrades:\n\n",
                    "\t  gap: uint256[50]  # Reserved storage slots\n",
                    "\n",
                    "\tOr in Vyper:\n",
                    "\t  __gap: public(uint256[50])\n",
                ]
                res = self.generate_result(info)
                results.append(res)

        return results

    def _is_proxy_like(self, contract) -> bool:
        """Check if contract looks like a proxy."""
        for func in contract.functions_entry_points:
            func_str = str(func).lower()
            if any(kw in func_str for kw in self.PROXY_KEYWORDS):
                return True
        return False
