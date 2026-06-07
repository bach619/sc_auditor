"""Desktop notifier for the Vyper Notifier Service (Windows).

Sends Windows native toast notifications via ``winotify`` if available,
with fallback to a log file.  On non-Windows platforms all deliveries
are silently logged.
"""

from __future__ import annotations

import os
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from src.models import DeliveryResult

log = structlog.get_logger()

# ── Data Directory ──────────────────────────────────────────

DATA_DIR = Path(os.environ.get("NOTIFIER_DATA_DIR", "/data/notifier"))
FALLBACK_LOG = DATA_DIR / "desktop.log"


# ── Notifier ─────────────────────────────────────────────────


class DesktopNotifier:
    """Send Windows toast notifications.

    Uses the ``winotify`` package on Windows.  Falls back to appending
    notifications to a log file when the native API is unavailable.

    Usage::

        notifier = DesktopNotifier()
        result = await notifier.send(
            "Audit Complete",
            "Ethena USDe: 5 findings, 2 critical",
        )
    """

    def __init__(self) -> None:
        self._fallback_path = FALLBACK_LOG
        self._winotify: Any = None
        self._available = self._detect()

    def _detect(self) -> bool:
        """Detect whether native Windows toast notifications are available.

        Returns True if winotify is importable on Windows.
        """
        if platform.system() != "Windows":
            log.info("desktop.platform_not_supported", os=platform.system())
            return False

        try:
            import winotify  # type: ignore[import-untyped]
            self._winotify = winotify
            log.info("desktop.available")
            return True
        except ImportError:
            log.warning(
                "desktop.winotify_missing",
                hint="pip install winotify",
            )
            return False
        except Exception as exc:
            log.warning("desktop.init_error", error=str(exc))
            return False

    @property
    def available(self) -> bool:
        """Whether native notifications can be shown."""
        return self._available

    async def send(
        self,
        title: str,
        message: str,
    ) -> DeliveryResult:
        """Send a desktop (toast) notification.

        Args:
            title: Notification title (e.g. "Vyper Audit Complete").
            message: Notification body text.

        Returns:
            A DeliveryResult indicating success or failure.
        """
        try:
            if self._available:
                return await self._send_native(title, message)
            else:
                return self._send_fallback(title, message)
        except Exception as exc:
            log.exception("desktop.send_failed", title=title, error=str(exc))
            return DeliveryResult(
                channel="desktop",
                success=False,
                error=f"Desktop notification failed: {exc}",
            )

    # ------------------------------------------------------------------
    # Native Windows toast (winotify)
    # ------------------------------------------------------------------

    async def _send_native(self, title: str, message: str) -> DeliveryResult:
        """Send a Windows toast notification via winotify.

        Runs the winotify ``show()`` call in a thread executor to avoid
        blocking the event loop (winotify may perform COM operations).
        """
        import asyncio

        def _show_toast() -> None:
            try:
                toast = self._winotify.Notification(
                    app_id="Vyper Security Scanner",
                    title=title or "Vyper Notification",
                    msg=message or "",
                    duration="short",
                )
                toast.show()
            except Exception as exc:
                log.error("desktop.native_error", error=str(exc))
                raise

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _show_toast)

        log.info("desktop.delivered", title=title)
        return DeliveryResult(channel="desktop", success=True)

    # ------------------------------------------------------------------
    # Fallback: log to file
    # ------------------------------------------------------------------

    def _send_fallback(self, title: str, message: str) -> DeliveryResult:
        """Fallback: append notification to a log file."""
        try:
            self._fallback_path.parent.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(UTC).isoformat()
            line = f"[{timestamp}] {title}: {message}\n"

            with open(str(self._fallback_path), "a", encoding="utf-8") as f:
                f.write(line)

            log.info("desktop.fallback_logged", title=title, path=str(self._fallback_path))
            return DeliveryResult(channel="desktop", success=True)

        except OSError as exc:
            log.error("desktop.fallback_write_error", error=str(exc))
            return DeliveryResult(
                channel="desktop",
                success=False,
                error=f"Fallback log write failed: {exc}",
            )


# ── Factory ─────────────────────────────────────────────────


def create_desktop_notifier() -> DesktopNotifier:
    """Create a new DesktopNotifier instance."""
    return DesktopNotifier()
