"""ExperienceSyncer — background sync dari local SQLite ke central 17-experience.

Bekerja di background thread:
  - Batch: setiap 50 experiences baru atau 5 menit (mana yang lebih dulu)
  - Never blocks: gagal sync → retry next cycle, tidak pengaruhi local recording
  - At-most-once: kirim batch, 17-experience handle dedup via INSERT OR REPLACE
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import structlog

logger = structlog.get_logger()


class ExperienceSyncer:
    """Background syncer — local → central.

    Args:
        agent_service: Nama service (e.g., "04a-scanner-slither")
        store: Local ExperienceStore instance
        central_url: URL central 17-experience service
        batch_size: Kirim setelah N experiences baru (default: 50)
        interval_seconds: Atau kirim setiap N detik (default: 300 = 5 menit)
    """

    def __init__(
        self,
        agent_service: str,
        store: Any,
        central_url: str | None = None,
        batch_size: int = 50,
        interval_seconds: int = 300,
    ) -> None:
        self._agent_service = agent_service
        self._store = store
        self._central_url = central_url or os.environ.get(
            "EXPERIENCE_CENTRAL_URL",
            "http://17-experience:8019",
        )
        self._batch_size = batch_size
        self._interval = interval_seconds
        self._last_sync_count = 0
        self._last_sync_time = 0.0
        self._task: asyncio.Task | None = None
        self._running = False
        self._synced_count = 0
        self._failed_count = 0

    # ── Public API ─────────────────────────────────────────

    @property
    def is_central_configured(self) -> bool:
        """Cek apakah central URL tersedia (bisa pakai env atau default)."""
        url = self._central_url
        return bool(url) and "localhost" not in url and "127.0.0.1" not in url

    def notify_new_experience(self) -> None:
        """Panggil setiap kali ada experience baru di-record.

        Trigger sync jika sudah mencapai batch_size.
        """
        current = self._store.count()
        new_since_last = current - self._last_sync_count
        if new_since_last >= self._batch_size:
            asyncio.ensure_future(self._try_sync())

    def start_background_sync(self) -> None:
        """Start periodic background sync task."""
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._periodic_sync())
        logger.info(
            "syncer_started",
            agent=self._agent_service,
            central_url=self._central_url,
            batch_size=self._batch_size,
            interval=self._interval,
        )

    async def stop(self) -> None:
        """Stop background sync."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        # Final sync sebelum berhenti
        await self._try_sync()

    async def sync_now(self) -> dict[str, Any]:
        """Force sync sekarang. Return hasilnya."""
        return await self._try_sync()

    # ── Internal ────────────────────────────────────────────

    async def _periodic_sync(self) -> None:
        """Loop background: sync setiap interval detik."""
        while self._running:
            await asyncio.sleep(self._interval)
            try:
                await self._try_sync()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("periodic_sync_error", error=str(exc), agent=self._agent_service)

    async def _try_sync(self) -> dict[str, Any]:
        """Coba sync ke central. Never raises — semua error di-handle."""
        current = self._store.count()
        new_since_last = current - self._last_sync_count

        if new_since_last == 0:
            return {"synced": 0, "reason": "no_new_data"}

        # Ambil experiences yang belum di-sync
        # (last_sync_count adalah jumlah yg sudah di-sync sebelumnya)
        recent = self._store.get_recent(limit=new_since_last)

        # Kirim batch
        try:
            import httpx

            url = f"{self._central_url}/sync"
            payload = {
                "agent_service": self._agent_service,
                "experiences": [e.to_dict() for e in recent],
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()

            self._last_sync_count = current
            self._last_sync_time = time.time()
            self._synced_count += 1
            logger.info(
                "sync_success",
                agent=self._agent_service,
                synced=len(recent),
                total_global=data.get("data", {}).get("total", 0),
            )
            return {"synced": len(recent), "total_global": data.get("data", {}).get("total", 0)}

        except Exception as exc:
            self._failed_count += 1
            logger.warning(
                "sync_failed",
                agent=self._agent_service,
                error=str(exc)[:100],
                failed_count=self._failed_count,
                new_since_last=new_since_last,
            )
            return {"synced": 0, "error": str(exc)[:100]}

    def get_status(self) -> dict[str, Any]:
        """Dapatkan status syncer."""
        return {
            "agent_service": self._agent_service,
            "central_url": self._central_url,
            "running": self._running,
            "synced_count": self._synced_count,
            "failed_count": self._failed_count,
            "last_sync_time": self._last_sync_time,
            "last_sync_count": self._last_sync_count,
            "local_total": self._store.count() if self._store else 0,
            "batch_size": self._batch_size,
            "interval_seconds": self._interval,
        }
