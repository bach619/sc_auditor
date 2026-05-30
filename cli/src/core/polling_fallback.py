"""
VYPER TUI v2 — PollingFallback

BACKUP polling untuk service yang BELUM mengimplementasikan EventPublisher / SSE.
Hanya aktif jika EventBus PERNAH terkoneksi — kalau backend mati total, jangan polling.

Smart backoff:
  - 3x gagal beruntun → polling interval naik 2x (per-service)
  - Semua service gagal → global sleep naik (maks 60s)
  - Service berhasil 1x → reset backoff service itu
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from cli.src.core.event_bus import EventBus
from cli.src.models.events import VyperEvent

logger = logging.getLogger("vyper_tui.polling_fallback")


class PollingFallback:
    """
    Polling-based fallback untuk service tanpa SSE.

    Smart behavior:
    - TIDAK polling sebelum EventBus pernah connect (backend mungkin mati)
    - Per-service backoff: 3x gagal → poll 2x jarang, 10x gagal → poll 4x jarang
    - Global backoff: semua gagal → sleep naik sampai 60s
    - Reset segera saat satu service berhasil di-poll
    """

    FALLBACK_INTERVAL = 5.0
    GRACE_PERIOD = 5.0
    MAX_GLOBAL_BACKOFF = 60.0
    BACKOFF_THRESHOLD = 3       # berapa kali gagal sebelum backoff naik
    BACKOFF_FACTOR = 2.0         # pengali interval per backoff level

    DEFAULT_SERVICES: list[tuple[str, int]] = [
        ("01-config",      8011),
        ("02-immunefi",    8001),
        ("03-source",      8002),
        ("04-scanner",     8003),
        ("04a-slither",    8014),
        ("04b-echidna",    8015),
        ("04c-forge",      8016),
        ("04d-halmos",     8017),
        ("05-mythril",     8013),
        ("06-ai",          8004),
        ("07-classifier",  8005),
        ("08-exploit",     8006),
        ("09-reporter",    8007),
        ("10-notifier",    8008),
        ("11-orchestrator", 8009),
        ("12-webhook",     8010),
        ("13-upkeep",      8012),
        ("14-agent",       8021),
        ("16-submission",  8018),
    ]

    def __init__(
        self,
        event_bus: EventBus,
        services: list[tuple[str, int]] | None = None,
        interval: float | None = None,
        grace_period: float | None = None,
    ):
        self.event_bus = event_bus
        self.services = services or self.DEFAULT_SERVICES
        self.interval = interval or self.FALLBACK_INTERVAL
        self.grace_period = grace_period or self.GRACE_PERIOD
        self._last_event_time: dict[str, float] = {}
        self._consecutive_failures: dict[str, int] = {}
        self._total_consecutive_failures = 0
        self._running = False
        self._http_client: httpx.AsyncClient | None = None

    def mark_event_received(self, service_name: str) -> None:
        """Tandai bahwa service telah mengirim event via SSE — stop polling untuk service itu."""
        self._last_event_time[service_name] = asyncio.get_event_loop().time()
        self._consecutive_failures.pop(service_name, None)

    async def start(self) -> None:
        """Mulai polling loop. Hanya polling jika EventBus pernah connect."""
        self._running = True
        self._http_client = httpx.AsyncClient(timeout=5.0)

        # ── Tunggu EventBus pertama kali connect ──
        logger.info(
            "PollingFallback: menunggu EventBus connect (grace=%ss)...",
            self.grace_period,
        )
        await asyncio.sleep(self.grace_period)

        if not self.event_bus.is_connected:
            logger.info(
                "PollingFallback: EventBus belum connect — "
                "backend mungkin mati. Polling tidak dimulai."
            )

        global_backoff = self.interval

        while self._running:
            # ── Skip semua polling kalau EventBus belum pernah connect ──
            if not self.event_bus.is_connected:
                await asyncio.sleep(self.interval * 2)
                continue

            now = asyncio.get_event_loop().time()
            tasks: list[asyncio.Task] = []
            any_attempt = False

            for svc_name, port in self.services:
                # Skip jika sudah dapat event via SSE
                last = self._last_event_time.get(svc_name, 0.0)
                if now - last < self.interval * 2:
                    continue

                # Per-service backoff: makin sering gagal, makin jarang di-poll
                fail_count = self._consecutive_failures.get(svc_name, 0)
                backoff_mult = 1.0
                if fail_count >= self.BACKOFF_THRESHOLD:
                    levels = fail_count // self.BACKOFF_THRESHOLD
                    backoff_mult = self.BACKOFF_FACTOR ** min(levels, 4)  # max 16x
                    if backoff_mult > 1.0:
                        logger.debug(
                            "Backoff %s: %dx (gagal %dx)",
                            svc_name, backoff_mult, fail_count,
                        )

                # Cek apakah service ini waktunya di-poll berdasarkan backoff
                last_poll_attempt = self._last_event_time.get(
                    f"{svc_name}_last_poll", 0.0
                )
                if now - last_poll_attempt < self.interval * backoff_mult:
                    continue

                self._last_event_time[f"{svc_name}_last_poll"] = now
                any_attempt = True
                tasks.append(
                    asyncio.create_task(self._poll_service(svc_name, port))
                )

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                successes = 0
                failures = 0
                for r in results:
                    if isinstance(r, Exception):
                        failures += 1
                    else:
                        successes += 1

                # Global backoff: jika SEMUA gagal, tidur lebih lama
                if successes == 0 and failures > 0:
                    self._total_consecutive_failures += 1
                    if self._total_consecutive_failures >= self.BACKOFF_THRESHOLD:
                        global_backoff = min(
                            global_backoff * 1.5,
                            self.MAX_GLOBAL_BACKOFF,
                        )
                        logger.debug(
                            "Global backoff: %d consecutive all-fail → sleep %.1fs",
                            self._total_consecutive_failures,
                            global_backoff,
                        )
                else:
                    # Ada yang sukses → reset global backoff
                    if self._total_consecutive_failures > 0:
                        logger.info(
                            "PollingFallback: service mulai online (global backoff reset)"
                        )
                    self._total_consecutive_failures = 0
                    global_backoff = self.interval

                await asyncio.sleep(global_backoff)
            else:
                # Tidak ada service yang perlu di-poll
                await asyncio.sleep(self.interval * 2)

    async def stop(self) -> None:
        """Hentikan polling loop."""
        self._running = False
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        logger.info("PollingFallback stopped")

    async def _poll_service(self, service_name: str, port: int) -> None:
        """Poll satu service via GET /activity."""
        if not self._http_client:
            return

        url = f"http://localhost:{port}/activity"
        try:
            response = await self._http_client.get(url)
            response.raise_for_status()
            data = response.json()

            event = VyperEvent(
                event_type="service.activity",
                service=service_name,
                payload=data,
                source="polling_fallback",
            )
            await self.event_bus.emit(event)

            # Sukses → reset semua counter
            now = asyncio.get_event_loop().time()
            self._last_event_time[service_name] = now
            self._consecutive_failures.pop(service_name, None)

            logger.info(
                "PollingFallback: %s online ✓ (status=%s)",
                service_name,
                data.get("status", "?"),
            )

        except httpx.HTTPError:
            # Gagal → increment consecutive failure
            fails = self._consecutive_failures.get(service_name, 0) + 1
            self._consecutive_failures[service_name] = fails

            if fails == 1:
                logger.debug(
                    "PollingFallback: %s offline (404). Akan coba lagi.",
                    service_name,
                )
            elif fails == self.BACKOFF_THRESHOLD:
                logger.debug(
                    "PollingFallback: %s offline %dx — backoff aktif.",
                    service_name,
                    fails,
                )

        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Unexpected polling error for %s", service_name)
