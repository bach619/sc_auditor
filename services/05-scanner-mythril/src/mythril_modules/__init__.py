"""Custom Mythril analysis modules.

These are loaded via `mythril analyze --plugins /path/to/modules`.
Each module extends Mythril's built-in analysis with enhanced detection
for HIGH/CRITICAL severity bugs.

Module interface:
  - Each module must inherit from mythril.analysis.module.BaseAnalysisModule
  - Must implement `execute()` method
  - Must set `self.name` and `self.swc_id`
"""

from .access_control_deep import AccessControlDeepModule
from .delegatecall_arbitrary import DelegatecallArbitraryModule
from .flash_loan_oracle import FlashLoanOracleModule
from .overflow_chain import OverflowChainModule
from .reentrancy_enhanced import ReentrancyEnhancedModule

__all__ = [
    "ReentrancyEnhancedModule",
    "AccessControlDeepModule",
    "FlashLoanOracleModule",
    "DelegatecallArbitraryModule",
    "OverflowChainModule",
]
