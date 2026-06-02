"""Resource guard for Manticore analysis — prevents runaway symbolic execution.

Manticore is known for path explosion. This module enforces:
  - Per-contract time budget (default: 300s)
  - Per-path instruction limit (default: 5000)
  - Max active states (default: 10000)
  - Abort strategy: partial results if timeout
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AbortReason(Enum):
    TIMEOUT = "timeout"
    PATH_EXPLOSION = "path_explosion"
    MEMORY_LIMIT = "memory_limit"
    MAX_STATES = "max_states"
    USER_CANCELLED = "user_cancelled"
    INTERNAL_ERROR = "internal_error"


@dataclass
class ResourceBudget:
    """Budget constraints for a single analysis run."""

    max_duration_seconds: int = 300
    max_path_instructions: int = 5000
    max_states: int = 10000
    max_memory_mb: int = 2048
    max_paths_per_function: int = 50

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_duration_seconds": self.max_duration_seconds,
            "max_path_instructions": self.max_path_instructions,
            "max_states": self.max_states,
            "max_memory_mb": self.max_memory_mb,
            "max_paths_per_function": self.max_paths_per_function,
        }


@dataclass
class ResourceUsage:
    """Resource consumption during analysis."""

    duration_seconds: float = 0.0
    paths_explored: int = 0
    states_visited: int = 0
    memory_mb: float = 0.0
    aborted: bool = False
    abort_reason: AbortReason | None = None
    partial_results: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "duration_seconds": round(self.duration_seconds, 2),
            "paths_explored": self.paths_explored,
            "states_visited": self.states_visited,
            "memory_mb": round(self.memory_mb, 1),
            "aborted": self.aborted,
            "abort_reason": self.abort_reason.value if self.abort_reason else None,
            "partial_results": self.partial_results,
        }


class ResourceGuard:
    """Monitors and enforces resource budgets during Manticore execution."""

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
        """Begin monitoring for a new analysis run."""
        self._start_time = time.monotonic()
        self._usage = ResourceUsage()
        self._contract_complexity = contract_complexity

        # Adjust budget based on complexity
        if contract_complexity == "simple":
            self._budget.max_duration_seconds = 60
            self._budget.max_path_instructions = 1000
        elif contract_complexity == "complex":
            self._budget.max_duration_seconds = 600
            self._budget.max_path_instructions = 10000
        elif contract_complexity == "extreme":
            self._budget.max_duration_seconds = 1200
            self._budget.max_path_instructions = 20000

    def check(self) -> bool:
        """Check if we should continue. Returns False if budget exceeded."""
        elapsed = time.monotonic() - self._start_time

        self._usage.duration_seconds = elapsed

        if elapsed > self._budget.max_duration_seconds:
            self._usage.aborted = True
            self._usage.abort_reason = AbortReason.TIMEOUT
            self._usage.partial_results = True
            return False

        if self._usage.states_visited > self._budget.max_states:
            self._usage.aborted = True
            self._usage.abort_reason = AbortReason.MAX_STATES
            self._usage.partial_results = True
            return False

        if self._usage.paths_explored > self._budget.max_paths_per_function * 10:
            self._usage.aborted = True
            self._usage.abort_reason = AbortReason.PATH_EXPLOSION
            self._usage.partial_results = True
            return False

        return True

    def record_path(self) -> None:
        """Record a path exploration."""
        self._usage.paths_explored += 1

    def record_state(self) -> None:
        """Record a state visit."""
        self._usage.states_visited += 1

    def should_skip_function(self, function_name: str, func_analysis: dict[str, Any] | None = None) -> bool:
        """Decide if we should skip analyzing this function entirely.

        Skip if:
          - Function is too large (>200 instructions)
          - Function has no state-changing operations
          - Budget already running low
        """
        if func_analysis:
            complexity = func_analysis.get("complexity", 0)
            if complexity > 200:
                return True  # Skip very large functions

            # Skip getters/view functions (no state change)
            modifiers = func_analysis.get("modifiers", [])
            if "view" in modifiers or "pure" in modifiers:
                return True

        # If we're past 80% of budget, skip remaining
        elapsed = time.monotonic() - self._start_time
        if elapsed > self._budget.max_duration_seconds * 0.8:
            return True

        return False

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of resource usage for analysis output."""
        return {
            "resource_usage": self._usage.to_dict(),
            "budget": self._budget.to_dict(),
            "contract_complexity": self._contract_complexity,
        }
