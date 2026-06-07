"""Resource guard for Mythril analysis — prevents runaway execution.

Mythril symbolic execution can be resource-intensive. This module:
  - Enforces time budget per contract
  - Limits function analysis depth
  - Tracks resource consumption
  - Returns partial results if timeout
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any


class AbortReason(Enum):
    TIMEOUT = "timeout"
    PATH_EXPLOSION = "path_explosion"
    MEMORY_LIMIT = "memory_limit"
    MAX_FUNCTIONS = "max_functions"
    USER_CANCELLED = "user_cancelled"


@dataclass
class ResourceBudget:
    max_duration_seconds: int = 300
    max_functions: int = 20
    max_depth: int = 42
    max_states: int = 5000

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_duration_seconds": self.max_duration_seconds,
            "max_functions": self.max_functions,
            "max_depth": self.max_depth,
            "max_states": self.max_states,
        }


@dataclass
class ResourceUsage:
    duration_seconds: float = 0.0
    functions_analyzed: int = 0
    states_visited: int = 0
    aborted: bool = False
    abort_reason: AbortReason | None = None
    partial_results: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "duration_seconds": round(self.duration_seconds, 2),
            "functions_analyzed": self.functions_analyzed,
            "states_visited": self.states_visited,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason.value if self.abort_reason else None,
            "partial_results": self.partial_results,
        }


class ResourceGuard:
    """Monitors and enforces resource budgets during Mythril execution."""

    def __init__(self, budget: ResourceBudget | None = None) -> None:
        self._budget = budget or ResourceBudget()
        self._usage = ResourceUsage()
        self._start_time: float = 0.0
        self._contract_complexity: str = "medium"

    @property
    def usage(self) -> ResourceUsage:
        return self._usage

    @property
    def budget(self) -> ResourceBudget:
        return self._budget

    def start(self, contract_complexity: str = "medium") -> None:
        self._start_time = time.monotonic()
        self._usage = ResourceUsage()
        self._contract_complexity = contract_complexity

        if contract_complexity == "simple":
            self._budget.max_duration_seconds = 60
            self._budget.max_functions = 10
            self._budget.max_depth = 24
        elif contract_complexity == "complex":
            self._budget.max_duration_seconds = 600
            self._budget.max_functions = 30
            self._budget.max_depth = 64
        elif contract_complexity == "extreme":
            self._budget.max_duration_seconds = 1200
            self._budget.max_functions = 50
            self._budget.max_depth = 96

    def check(self) -> bool:
        """Check if analysis should continue. Returns False if budget exceeded."""
        elapsed = time.monotonic() - self._start_time
        self._usage.duration_seconds = elapsed

        if elapsed > self._budget.max_duration_seconds:
            self._usage.aborted = True
            self._usage.abort_reason = AbortReason.TIMEOUT
            self._usage.partial_results = True
            return False

        if self._usage.functions_analyzed > self._budget.max_functions:
            self._usage.aborted = True
            self._usage.abort_reason = AbortReason.MAX_FUNCTIONS
            self._usage.partial_results = True
            return False

        return True

    def record_function(self) -> None:
        self._usage.functions_analyzed += 1

    def record_state(self) -> None:
        self._usage.states_visited += 1

    def get_summary(self) -> dict[str, Any]:
        return {
            "resource_usage": self._usage.to_dict(),
            "budget": self._budget.to_dict(),
            "contract_complexity": self._contract_complexity,
        }
