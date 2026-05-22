"""Shared caching layer — Redis atau file-based fallback.

Caching strategy:
1. Contract source: cache 1 jam (Etherscan rate limit)
2. Scan results: cache 24 jam (same contract, same tools)
3. AI analysis: cache 7 hari (same findings)
4. Immunefi programs: cache 30 menit

Storage:
- Primary: Redis (jika tersedia)
- Fallback: JSON file di /data/cache/

TTL Strategy:
    contract:{addr} → 1 hour  (Etherscan rate limit)
    scan:{hash}     → 24 jam  (Same output for same input)
    ai:{hash}       → 7 hari  (Expensive LLM calls)
    immunefi:progs  → 30 mnt  (Need freshness)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("vyper.cache")


# ── TTL Constants (seconds) ──────────────────────────────────────

TTL_CONTRACT = 3600          # 1 hour
TTL_SCAN = 86400             # 24 hours
TTL_AI = 604800              # 7 days
TTL_IMMUNEFI_PROGS = 1800    # 30 minutes


class CacheLayer:
    """Multi-tier cache dengan Redis primary, file fallback."""

    def __init__(self, redis_url: str | None = None, cache_dir: str = "/data/cache") -> None:
        self.redis_url = redis_url
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0
        self._redis = None

        if redis_url:
            try:
                import redis.asyncio as aioredis  # type: ignore
                self._redis = aioredis.from_url(redis_url, decode_responses=True)
                logger.info("Redis connected: %s", redis_url)
            except ImportError:
                logger.info("redis not installed, using file fallback")
            except Exception as exc:
                logger.warning("Redis unavailable: %s, using file fallback", exc)

    # ── Key generation ────────────────────────────────────────────

    @staticmethod
    def _make_key(prefix: str, data: Any) -> str:
        """Generate deterministic cache key."""
        raw = json.dumps(data, sort_keys=True)
        h = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"{prefix}:{h}"

    # ── Get ────────────────────────────────────────────────────────

    async def get(self, prefix: str, data: Any) -> Any | None:
        """Get from cache — try Redis first, fallback to file."""
        key = self._make_key(prefix, data)

        # Try Redis
        if self._redis is not None:
            try:
                val = await self._redis.get(key)
                if val is not None:
                    self.hits += 1
                    return json.loads(val)
            except Exception:
                logger.warning("Redis get failed for key: %s", key, exc_info=True)

        # Try file
        file_path = self.cache_dir / f"{key}.json"
        if file_path.exists():
            try:
                cached: dict = json.loads(file_path.read_text())
                expires_at = cached.get("expires_at", 0)
                if expires_at > time.time():
                    self.hits += 1
                    return cached["value"]
                # Expired — remove stale file
                file_path.unlink(missing_ok=True)
            except (json.JSONDecodeError, OSError, KeyError):
                pass

        self.misses += 1
        return None

    # ── Set ────────────────────────────────────────────────────────

    async def set(
        self,
        prefix: str,
        data: Any,
        value: Any,
        ttl_seconds: int = 3600,
    ) -> None:
        """Store in cache."""
        key = self._make_key(prefix, data)
        payload = json.dumps({
            "value": value,
            "expires_at": time.time() + ttl_seconds,
        })

        if self._redis is not None:
            try:
                await self._redis.setex(key, ttl_seconds, payload)
            except Exception:
                logger.warning("Redis set failed for key: %s", key, exc_info=True)

        # Always write file fallback
        file_path = self.cache_dir / f"{key}.json"
        file_path.write_text(payload)

    # ── Stats ───────────────────────────────────────────────────────

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def stats(self) -> dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hit_rate, 3),
        }

    async def clear(self) -> int:
        """Clear all cached files. Returns count of removed files."""
        removed = 0
        for f in self.cache_dir.glob("*.json"):
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
        if self._redis is not None:
            try:
                await self._redis.flushdb()
            except Exception:
                pass
        self.hits = 0
        self.misses = 0
        return removed


# ── Pre-defined cache prefixes ────────────────────────────────────

CONTRACT_CACHE = "contract"
SCAN_CACHE = "scan"
AI_CACHE = "ai"
IMMUNEFI_PROGS_CACHE = "immunefi:progs"
