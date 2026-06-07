"""Custom HIGH/CRIT severity Manticore detectors.

Each detector targets a specific vulnerability class known to
cause loss of funds or total contract compromise.
"""
from .access_control import AccessControlDetector
from .delegatecall_arb import DelegatecallArbDetector
from .flash_loan_oracle import FlashLoanOracleDetector
from .overflow_critical import OverflowCriticalDetector
from .reentrancy_high import ReentrancyHighDetector

__all__ = [
    "ReentrancyHighDetector",
    "AccessControlDetector",
    "FlashLoanOracleDetector",
    "OverflowCriticalDetector",
    "DelegatecallArbDetector",
]
