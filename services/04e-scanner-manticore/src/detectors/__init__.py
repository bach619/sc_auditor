"""Custom HIGH/CRIT severity Manticore detectors.

Each detector targets a specific vulnerability class known to
cause loss of funds or total contract compromise.
"""
from .reentrancy_high import ReentrancyHighDetector
from .access_control import AccessControlDetector
from .flash_loan_oracle import FlashLoanOracleDetector
from .overflow_critical import OverflowCriticalDetector
from .delegatecall_arb import DelegatecallArbDetector

__all__ = [
    "ReentrancyHighDetector",
    "AccessControlDetector",
    "FlashLoanOracleDetector",
    "OverflowCriticalDetector",
    "DelegatecallArbDetector",
]
