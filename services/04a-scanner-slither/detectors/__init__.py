"""Custom Vyper & Solidity Detectors for the Slither Scanner.

These detectors are loaded dynamically by CustomDetectorRegistry at
startup. Each file should define exactly one class inheriting from
AbstractDetector with NAME and DESCRIPTION attributes.

Available detectors:
  - detector_flash_loan_attack.py       → FlashLoanAttackDetector
  - detector_oracle_manipulation.py     → OracleManipulationDetector
  - detector_uniswap_v4_hook.py         → UniswapV4HookDetector
  - detector_vyper_reentrancy.py        → VyperReentrancyDetector
  - detector_vyper_storage.py           → VyperStorageCollisionDetector
  - detector_vyper_integer.py           → VyperIntegerSafetyDetector
"""
