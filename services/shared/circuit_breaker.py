from __future__ import annotations

import time
import asyncio
from enum import Enum

class CircuitState(str, Enum):
    CLOSED = "closed"             # Normal — requests flow
    OPEN = "open"                 # Tripped — requests rejected instantly
    HALF_OPEN = "half_open"       # Testing — limited requests allowed

class CircuitBreaker:
    """Melindungi service dari cascade failure."""
    
    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_timeout: float = 30.0, half_open_max: int = 3):
        self.name = name
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max
        self.half_open_count = 0
    
    async def call(self, coro):
        """Panggil service dengan circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_count = 0
            else:
                raise CircuitOpenError(f"Circuit {self.name} is OPEN")
        
        try:
            result = await coro
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise exc
    
    def _on_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_count += 1
            if self.half_open_count >= self.half_open_max:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
        else:
            self.failure_count = 0
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

class CircuitOpenError(Exception):
    pass

# Global circuit breakers per service
CIRCUITS = {
    "immunefi": CircuitBreaker("02-immunefi"),
    "source": CircuitBreaker("03-source"),
    "classifier": CircuitBreaker("07-classifier"),
    "exploit": CircuitBreaker("08-exploit"),
    "ai": CircuitBreaker("06-ai", failure_threshold=3),  # AI mahal — lebih sensitif
}
