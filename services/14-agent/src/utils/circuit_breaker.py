"""Circuit Breaker utility — protects backend services from cascading failures.

Usage:
    from src.utils.circuit_breaker import circuit_breaker, CircuitBreaker
    
    cb = circuit_breaker("scan_contract")
    if cb.state == "OPEN":
        # Don't call, return cached/fallback
        return fallback()
    
    try:
        result = await call_service()
        cb.record_success()
        return result
    except Exception:
        cb.record_failure()
        raise
"""

from __future__ import annotations

import threading
import time
from typing import Any


class CircuitBreaker:
    """Circuit breaker untuk satu service/skill.

    States:
        CLOSED:   Normal operation — calls go through
        HALF_OPEN: Testing if service recovered
        OPEN:     Failing — calls are rejected immediately
    """

    STATES = ("CLOSED", "HALF_OPEN", "OPEN")

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state: str = "CLOSED"
        self.failure_count: int = 0
        self.success_count: int = 0
        self.last_failure_time: float = 0.0
        self.last_success_time: float = 0.0
        self.total_calls: int = 0
        self.total_failures: int = 0
        self.total_successes: int = 0
        self._half_open_calls: int = 0
        self._lock = threading.Lock()

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self.total_calls += 1
            self.total_successes += 1
            self.success_count += 1
            self.last_success_time = time.time()

            if self.state == "HALF_OPEN":
                self._half_open_calls += 1
                if self._half_open_calls >= self.half_open_max_calls:
                    self.state = "CLOSED"
                    self.failure_count = 0
                    self._half_open_calls = 0
            elif self.state == "CLOSED":
                # Reset failure count on sustained success
                if self.success_count >= 5:
                    self.failure_count = 0
                    self.success_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self.total_calls += 1
            self.total_failures += 1
            self.failure_count += 1
            self.success_count = 0
            self.last_failure_time = time.time()

            if self.state == "CLOSED":
                if self.failure_count >= self.failure_threshold:
                    self.state = "OPEN"
                    self._half_open_calls = 0
            elif self.state == "HALF_OPEN":
                self.state = "OPEN"

    def can_call(self) -> bool:
        """Check if a call is allowed through the breaker."""
        with self._lock:
            if self.state == "CLOSED":
                return True
            if self.state == "HALF_OPEN":
                return self._half_open_calls < self.half_open_max_calls
            # OPEN — check if recovery timeout elapsed
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                self._half_open_calls = 0
                return True
            return False

    def status(self) -> dict[str, Any]:
        """Get current breaker status for monitoring."""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "recovery_timeout": self.recovery_timeout,
            "is_open": self.state == "OPEN",
        }

    def reset(self) -> None:
        """Manually reset the breaker."""
        with self._lock:
            self.state = "CLOSED"
            self.failure_count = 0
            self.success_count = 0
            self._half_open_calls = 0


# ── Global registry ────────────────────────────────────────

_registry: dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def circuit_breaker(name: str, **kwargs: Any) -> CircuitBreaker:
    """Get or create a circuit breaker by name (singleton per name).

    Usage:
        cb = circuit_breaker("scan_contract")
        cb = circuit_breaker("service:04-scanner", failure_threshold=3)
    """
    with _registry_lock:
        if name not in _registry:
            _registry[name] = CircuitBreaker(name, **kwargs)
        return _registry[name]


def all_circuit_breakers() -> dict[str, dict[str, Any]]:
    """Get status of all registered circuit breakers (for monitoring)."""
    return {name: cb.status() for name, cb in _registry.items()}


def reset_all() -> None:
    """Reset all circuit breakers."""
    for cb in _registry.values():
        cb.reset()
