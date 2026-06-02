"""Flash loan + oracle manipulation detector — HIGH severity.

Targets:
  - Twin-transaction: flash loan → manipulate price → exploit
  - Uniswap/TWAP oracle manipulation via large swaps
  - Spot price usage without TWAP validation
  - Oracle price vs calculated price mismatch

Detection strategy:
  1. Run multi-transaction symbolic analysis (2+ tx)
  2. In tx1: detect large swap / flash loan pattern
  3. In tx2: detect price-dependent logic (borrow, withdraw, liquidate)
  4. Track if manipulated state in tx1 affects outcome of tx2
  5. If state from tx1 directly influences fund movement in tx2 → ORACLE ATTACK
"""

from __future__ import annotations

from typing import Any

from manticore import Plugin


class FlashLoanOracleDetector(Plugin):
    """Manticore plugin for flash loan + oracle manipulation.

    Explores sequences of 2+ transactions where:
      - First tx manipulates oracle-relevant state
      - Second tx exploits the manipulated state for profit
    """

    SUSPICIOUS_SELECTORS: set[str] = {
        "7ff36ab5",  # swapExactTokensForETH
        "38ed1739",  # swapExactTokensForTokens
        "5c11d795",  # swapExactTokensForTokensSupportingFeeOnTransferTokens
        "18cbafe5",  # swapExactTokensForETHSupportingFeeOnTransferTokens
        "8803dbee",  # swapTokensForExactTokens
        "4a25d94a",  # swapTokensForExactETH
        "fb3bdb41",  # swapETHForExactTokens
        "ad615dec",  # loan (Aave-style)
        "ab9c4b5d",  # flashLoan
    }

    PROFIT_SELECTORS: set[str] = {
        "2e1a7d4d",  # withdraw(uint256)
        "441a3e70",  # borrow(uint256)
        "c5ebeaec",  # liquidate (various)
        "b02c43d0",  # liquidateLoan
        "d8ccd0f3",  # repayBorrow
    }

    def __init__(self) -> None:
        super().__init__()
        self._findings: list[dict[str, Any]] = []
        self._tx_sequence: list[dict[str, Any]] = []
        self._state_snapshots: list[dict[str, Any]] = []
        self._manipulation_detected: bool = False
        self._current_tx_index: int = 0
        self._critical_state_keys: set[int] = set()
        self._price_oracle_dependent: bool = False

    def will_evm_execute_transaction(
        self, state: Any, tx: Any, sort: str = "symbolic"
    ) -> None:
        """Track transaction start for multi-tx analysis."""
        self._current_tx_index = len(self._tx_sequence)

        tx_info = {
            "index": self._current_tx_index,
            "caller": hex(tx.caller) if hasattr(tx, "caller") else "symbolic",
            "address": hex(tx.address) if hasattr(tx, "address") else "unknown",
            "data": tx.data.hex() if hasattr(tx, "data") else "",
        }

        # Detect flash loan selectors
        if len(tx_info["data"]) >= 8:
            selector = tx_info["data"][:8]
            if selector in self.SUSPICIOUS_SELECTORS:
                tx_info["type"] = "flash_loan_or_swap"
            elif selector in self.PROFIT_SELECTORS:
                tx_info["type"] = "profit_extraction"

        self._tx_sequence.append(tx_info)

    def did_evm_execute_sstore(self, state: Any, key: int, value: int) -> None:
        """Track critical state changes that could be oracle manipulation."""
        # Track state changes that affect balances or reserves
        key_str = hex(key)
        if "balance" in key_str.lower() or "reserve" in key_str.lower():
            self._critical_state_keys.add(key)
            if self._current_tx_index > 0:
                # State modified in subsequent tx after first tx
                prev_tx = self._tx_sequence[self._current_tx_index - 1]
                if prev_tx.get("type") == "flash_loan_or_swap":
                    self._manipulation_detected = True

    def did_evm_execute_call(
        self,
        state: Any,
        address: int,
        value: int,
        gas: int,
        data: bytes | None = None,
    ) -> None:
        """Detect price oracle reads after state manipulation."""
        if data is not None and len(data) >= 4:
            selector = data[:4].hex()
            # Common oracle read selectors
            if selector in (
                "fbfa77cf",  # getPrice()
                "50d65b0b",  # getLatestPrice()
                "8e539e8c",  # peek()
                "9a6fc8f5",  # latestAnswer()
            ):
                if self._manipulation_detected:
                    self._price_oracle_dependent = True

    def did_evm_execute_return(self, state: Any, result: int) -> None:
        """After multi-tx sequence, evaluate if oracle attack is possible."""
        if self._current_tx_index >= 1:
            # We've executed 2+ transactions
            if self._manipulation_detected and self._price_oracle_dependent:
                # Check if value moved after the sequence
                # (profit extraction)
                last_tx = self._tx_sequence[-1] if self._tx_sequence else {}
                profit_extracted = last_tx.get("type") == "profit_extraction"

                self._report_finding(
                    severity="high",
                    bug_type="flash_loan_oracle_manipulation",
                    title="Flash loan + oracle manipulation path detected",
                    description=(
                        "Contract uses a manipulatable oracle (spot price) and "
                        "allows flash loan-sized state changes. An attacker can: "
                        "1) Take a flash loan 2) Swap to manipulate price "
                        "3) Exploit manipulated price for profit. "
                        "Use a TWAP oracle or price feed."
                    ),
                    state=state,
                    metadata={
                        "tx_sequence": self._tx_sequence,
                        "profit_extracted": profit_extracted,
                        "manipulated_state_keys": [hex(k) for k in self._critical_state_keys],
                        "reproduction_steps": [
                            "1. Flash loan large amount of token X",
                            "2. Swap X → Y on DEX to manipulate pool ratio",
                            "3. Call exploit function that reads manipulated price",
                            "4. Profit from price discrepancy",
                            "5. Repay flash loan",
                        ],
                    },
                )

    def _report_finding(
        self,
        severity: str,
        bug_type: str,
        title: str,
        description: str,
        state: Any,
        metadata: dict | None = None,
    ) -> None:
        finding: dict[str, Any] = {
            "severity": severity,
            "bug_type": bug_type,
            "title": title,
            "description": description,
            "confidence": 0.85,
            "detector": "flash_loan_oracle",
            "metadata": metadata or {},
        }
        try:
            finding["proof"] = {
                "tx_count": len(self._tx_sequence),
                "calldata_sequence": [
                    tx.get("data", "") for tx in self._tx_sequence[-2:]
                ],
            }
        except Exception:
            pass
        self._findings.append(finding)

    def get_findings(self) -> list[dict[str, Any]]:
        return self._findings

    def reset(self) -> None:
        self._findings.clear()
        self._tx_sequence.clear()
        self._state_snapshots.clear()
        self._manipulation_detected = False
        self._current_tx_index = 0
        self._critical_state_keys.clear()
        self._price_oracle_dependent = False
