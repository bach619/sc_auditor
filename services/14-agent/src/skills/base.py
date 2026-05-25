"""Base class for all Agent Skills with caching support.

Extends shared BaseSkill with:
- Response caching
- Circuit breaker integration
- get_definition() returning Pydantic SkillDefinition (for 14-agent internals)
"""

from __future__ import annotations

import hashlib
import json
import time
from abc import abstractmethod
from typing import Any

import structlog

from shared.skills.base_skill import BaseSkill as SharedBaseSkill

from src.models import SkillDefinition, SkillResult
from src.utils.circuit_breaker import CircuitBreaker, circuit_breaker

log = structlog.get_logger()


class BaseSkill(SharedBaseSkill):
    """Abstract base untuk semua skill agent (extends SharedBaseSkill).

    Setiap skill adalah kemampuan yang bisa dipanggil agent
    untuk melakukan satu tugas spesifik.

    Feature:
    - Optional response caching via _cached() helper
    - Auto circuit breaker per skill name
    - get_definition() returns Pydantic SkillDefinition
    """

    # Override di subclass untuk enable caching
    cache_ttl: int = 0  # detik, 0 = no cache
    cache_max_size: int = 100

    def __init__(self) -> None:
        super().__init__()
        self._cache: dict[str, tuple[float, Any]] = {}  # key -> (expiry, value)

    @property
    @abstractmethod
    def name(self) -> str:
        """Nama unik skill (digunakan agent untuk memanggil)."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Deskripsi skill (untuk LLM agent prompt)."""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """Parameter yang dibutuhkan skill (JSON Schema format)."""
        ...

    @property
    def category(self) -> str:
        """Kategori skill — default general."""
        return "general"

    def get_definition(self) -> SkillDefinition:
        return SkillDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )

    # ── Caching helpers ──────────────────────────────────────

    def _cache_key(self, **kwargs: Any) -> str:
        """Generate deterministic cache key from kwargs."""
        raw = json.dumps(kwargs, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def _cache_get(self, key: str) -> Any | None:
        """Get cached value if not expired."""
        if key in self._cache:
            expiry, value = self._cache[key]
            if time.time() < expiry:
                return value
            del self._cache[key]
        return None

    def _cache_set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set cached value with TTL."""
        ttl = ttl or self.cache_ttl
        if ttl <= 0:
            return
        # Evict oldest if full
        if len(self._cache) >= self.cache_max_size:
            oldest = min(self._cache.items(), key=lambda x: x[1][0])
            del self._cache[oldest[0]]
        self._cache[key] = (time.time() + ttl, value)

    def _cache_clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    async def _cached_run(self, **kwargs: Any) -> Any:
        """Run with caching — override run() method instead."""
        if self.cache_ttl <= 0:
            return await self.run(**kwargs)

        key = self._cache_key(**kwargs)
        cached = self._cache_get(key)
        if cached is not None:
            log.info("skill_cache_hit", skill=self.name, cache_key=key[:12])
            return cached

        result = await self.run(**kwargs)
        self._cache_set(key, result)
        return result

    # ── Execute with circuit breaker ─────────────────────────

    async def execute(self, **kwargs: Any) -> SkillResult:
        """Eksekusi skill dengan parameter yang diberikan.

        Includes:
        - Timing
        - Caching (if enabled)
        - Circuit breaker protection
        - Error handling

        Args:
            **kwargs: Parameter sesuai self.parameters

        Returns:
            SkillResult dengan output atau error
        """
        start = time.monotonic()
        try:
            log.info("skill_executing", skill=self.name, params=kwargs)

            # Circuit breaker check
            cb = circuit_breaker(f"skill:{self.name}")
            if cb.state == "OPEN":
                if time.time() - cb.last_failure_time > cb.recovery_timeout:
                    cb.state = "HALF_OPEN"
                else:
                    remaining = int(cb.recovery_timeout - (time.time() - cb.last_failure_time))
                    raise Exception(
                        f"Circuit breaker OPEN for {self.name} "
                        f"(retry in {remaining}s)"
                    )

            # Execute with caching
            output = await self._cached_run(**kwargs)

            # Record success in circuit breaker
            cb.record_success()

            duration = (time.monotonic() - start) * 1000
            log.info("skill_completed", skill=self.name, duration_ms=f"{duration:.0f}")
            return SkillResult(success=True, output=output, duration_ms=duration)

        except Exception as exc:
            duration = (time.monotonic() - start) * 1000

            # Record failure in circuit breaker
            try:
                cb = circuit_breaker(f"skill:{self.name}")
                cb.record_failure()
            except Exception:
                pass

            log.error("skill_failed", skill=self.name, error=str(exc))
            return SkillResult(
                success=False,
                error=str(exc),
                duration_ms=duration,
            )

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        """Implementasi skill — harus di-override oleh subclass.

        Args:
            **kwargs: Parameter yang sudah divalidasi

        Returns:
            Output dari skill (dict, list, string, dll)
        """
        ...


class CachedSkill(BaseSkill):
    """Base class untuk skill yang selalu menggunakan caching.

    Subclass hanya perlu define:
    - cache_ttl (berapa detik cache valid)
    - Implement run() seperti biasa
    """

    cache_ttl: int = 300  # 5 menit default

    async def execute(self, **kwargs: Any) -> SkillResult:
        return await super().execute(**kwargs)
