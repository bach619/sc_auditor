"""
VYPER TUI v2 — EventBus

Komponen inti yang menggantikan polling periodik dengan SSE streaming.
Subscribe ke endpoint /events dari 15-Dashboard dan dispatch
VyperEvent ke handler yang terdaftar.

Arsitektur:
  EventBus.connect()
      │
      ▼  persistent SSE connection
  15-Dashboard /events
      │
      ▼  data: {...}
  EventBus._dispatch(event)
      │
      ├── registered handlers (by event_type)
      └── wildcard handlers ("*")
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine

import httpx

from cli.src.models.events import VyperEvent

logger = logging.getLogger("vyper_tui.event_bus")

Handler = Callable[[VyperEvent], Coroutine[Any, Any, None]]


class EventBus:
    """
    Persistent SSE client dengan auto-reconnect (exponential backoff).

    Usage:
        event_bus = EventBus(app, url="http://localhost:8000/events")

        @event_bus.on("service.activity")
        async def handle(event: VyperEvent):
            print(f"{event.service} → {event.payload.get('status')}")

        asyncio.create_task(event_bus.connect())
    """

    DEFAULT_URL = "http://localhost:8000/events"
    MAX_RECONNECT_DELAY = 30.0
    INITIAL_RECONNECT_DELAY = 1.0

    def __init__(
        self,
        app: Any = None,
        url: str | None = None,
    ):
        """
        Args:
            app: Referensi ke VyperTUI App (Textual) — untuk post_message
            url: SSE endpoint URL. Default: http://localhost:8000/events
        """
        self.app = app
        self.url = url or self.DEFAULT_URL
        self._handlers: dict[str, list[Handler]] = {}
        self._reconnect_delay = self.INITIAL_RECONNECT_DELAY
        self._connected = False
        self._running = False

    # ── Public API ──────────────────────────────────────────────────────

    def on(self, event_type: str) -> Callable[[Handler], Handler]:
        """
        Decorator untuk mendaftarkan handler event.

        Args:
            event_type: Tipe event (e.g. "service.activity", "agent.thought")
                        Gunakan "*" untuk wildcard (semua event).

        Returns:
            Decorator function

        Usage:
            @event_bus.on("service.activity")
            async def handle_activity(event: VyperEvent):
                ...
        """

        def decorator(fn: Handler) -> Handler:
            self._handlers.setdefault(event_type, []).append(fn)
            logger.debug("Handler registered for '%s': %s", event_type, fn.__name__)
            return fn

        return decorator

    def off(self, event_type: str, fn: Handler | None = None) -> None:
        """Hapus handler. Jika fn=None, hapus semua handler untuk event_type."""
        if fn is None:
            self._handlers.pop(event_type, None)
        else:
            handlers = self._handlers.get(event_type, [])
            if fn in handlers:
                handlers.remove(fn)

    async def emit(self, event: VyperEvent) -> None:
        """
        Emit event secara lokal (tanpa HTTP) — untuk testing atau
        inject event dari PollingFallback.
        """
        await self._dispatch(event)

    async def connect(self) -> None:
        """
        Persistent SSE connection dengan auto-reconnect.
        Jalankan sebagai asyncio task terpisah.
        """
        self._running = True
        logger.info("EventBus connecting to %s", self.url)

        while self._running:
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream("GET", self.url) as response:
                        self._connected = True
                        self._reconnect_delay = self.INITIAL_RECONNECT_DELAY
                        logger.info("EventBus connected to %s", self.url)

                        async for line in response.aiter_lines():
                            if not self._running:
                                break
                            if line.startswith("data:"):
                                raw = line[5:].strip()
                                if not raw:
                                    continue
                                try:
                                    event = VyperEvent.from_sse_line(raw)
                                    await self._dispatch(event)
                                except json.JSONDecodeError as exc:
                                    logger.warning(
                                        "Failed to parse SSE data: %s — %s",
                                        exc, raw[:100],
                                    )

            except httpx.ConnectError:
                logger.warning(
                    "EventBus connection failed. Retry in %.1fs...",
                    self._reconnect_delay,
                )
            except httpx.RemoteProtocolError:
                logger.warning(
                    "EventBus connection lost. Retry in %.1fs...",
                    self._reconnect_delay,
                )
            except asyncio.CancelledError:
                logger.info("EventBus task cancelled")
                break
            except Exception:
                logger.exception("EventBus unexpected error")

            if not self._running:
                break

            self._connected = False
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(
                self._reconnect_delay * 2,
                self.MAX_RECONNECT_DELAY,
            )

    def disconnect(self) -> None:
        """Stop koneksi SSE."""
        self._running = False
        self._connected = False
        logger.info("EventBus disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Internal ────────────────────────────────────────────────────────

    async def _dispatch(self, event: VyperEvent) -> None:
        """
        Dispatch event ke semua handler yang terdaftar:
        1. Handler spesifik berdasarkan event_type
        2. Wildcard handler ("*")
        """
        # Handler spesifik
        for handler in self._handlers.get(event.event_type, []):
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    "Handler error for '%s': %s",
                    event.event_type,
                    handler.__name__,
                )

        # Wildcard handler
        for handler in self._handlers.get("*", []):
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    "Wildcard handler error: %s",
                    handler.__name__,
                )
