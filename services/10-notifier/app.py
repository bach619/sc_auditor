"""Vyper Notifier Service — FastAPI microservice for notification delivery.

Receives notification requests from the Vyper Orchestrator and delivers
them to configured channels: Discord, Telegram, Email, and Desktop
(Windows toast).

Port: 8008
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator

from shared.observability import setup_observability
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from src.desktop import DesktopNotifier, create_desktop_notifier
from src.discord import DiscordNotifier, create_discord_notifier
from src.email import EmailNotifier, create_email_notifier
from src.models import (
    ApiResponse,
    BatchDeliveryResult,
    ChannelConfig,
    DeliveryLogEntry,
    DeliveryResult,
    HealthData,
    Meta,
    NotifyRequest,
    TestRequest,
)
from src.telegram import TelegramNotifier, create_telegram_notifier






# ── Constants ──────────────────────────────────────────────

SERVICE_NAME = "notifier"
SERVICE_VERSION = "0.1.0"
DATA_DIR = Path(os.environ.get("NOTIFIER_DATA_DIR", "/data/notifier"))
DELIVERY_LOG = DATA_DIR / "delivery.log"

# ── Global state ───────────────────────────────────────────


class AppState:
    """Shared application state injected via ``request.app.state.vyper``."""

    def __init__(self) -> None:
        self.discord: DiscordNotifier = create_discord_notifier()
        self.telegram: TelegramNotifier | None = None
        self.email: EmailNotifier = create_email_notifier()
        self.desktop: DesktopNotifier = create_desktop_notifier()
        self.channels: list[ChannelConfig] = []
        self._load_channels()

    def _load_channels(self) -> None:
        """Scan environment variables and build the enabled-channels list."""
        channels: list[ChannelConfig] = []

        # Discord
        discord_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
        channels.append(
            ChannelConfig(
                name="discord",
                enabled=bool(discord_url),
                type="webhook",
                description="Discord webhook notifications",
            )
        )

        # Telegram
        tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "")
        if tg_token and tg_chat:
            self.telegram = create_telegram_notifier(bot_token=tg_token)
        channels.append(
            ChannelConfig(
                name="telegram",
                enabled=bool(tg_token and tg_chat),
                type="bot_api",
                description="Telegram Bot API notifications",
            )
        )

        # Email
        smtp_host = os.environ.get("SMTP_HOST", "")
        notif_email = os.environ.get("NOTIFICATION_EMAIL", "")
        channels.append(
            ChannelConfig(
                name="email",
                enabled=bool(smtp_host and notif_email),
                type="smtp",
                description="SMTP email notifications",
            )
        )

        # Desktop (Windows toast)
        channels.append(
            ChannelConfig(
                name="desktop",
                enabled=self.desktop.available,
                type="native",
                description="Windows toast notifications",
            )
        )

        self.channels = channels

    def get_enabled_channels(self) -> list[str]:
        """Return names of channels that are currently enabled."""
        return [c.name for c in self.channels if c.enabled]

    def get_channel(self, name: str) -> ChannelConfig | None:
        """Look up a channel by name."""
        for c in self.channels:
            if c.name == name:
                return c
        return None

    async def close(self) -> None:
        """Release HTTP clients and other resources."""
        await self.discord.close()
        if self.telegram:
            await self.telegram.close()


def _get_state(request: Request) -> AppState:
    """Get the application state from the request."""
    return request.app.state.vyper  # type: ignore[no-any-return]


# ── Lifespan ───────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: create data dirs, load channel config.
    Shutdown: release notifier resources.
    """
    state = AppState()
    app.state.vyper = state

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    enabled = state.get_enabled_channels()
    log.info(
        "notifier.startup",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        channels_total=len(state.channels),
        channels_enabled=enabled,
    )

    yield

    await state.close()
    log.info("notifier.shutdown", service=SERVICE_NAME)


# ── App Factory ────────────────────────────────────────────

app = FastAPI(
    title="Vyper Notifier Service",
    description=(
        "Receives notification requests from the Vyper Orchestrator and "
        "delivers them to configured channels: Discord, Telegram, Email, "
        "and Desktop (Windows toast)."
    ),
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

# CORS — permissive for local development / Docker compose
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


log = setup_observability(app, "10-notifier", "0.1.0")

# ── Helper ─────────────────────────────────────────────────


def ok(data: object = None) -> ApiResponse:
    """Build a standard Vyper success response."""
    return ApiResponse(data=data, meta=Meta(status="ok"))


def err(detail: str, status_code: int = 400) -> HTTPException:
    """Build a standard Vyper error response."""
    return HTTPException(
        status_code=status_code,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health(request: Request) -> ApiResponse:
    """Health check endpoint.

    Returns service status, version, and configured notification channels.
    """
    state = _get_state(request)
    enabled = state.get_enabled_channels()

    return ok(
        HealthData(
            status="ok",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
            channels_available=len(state.channels),
            channels_enabled=enabled,
        )
    )


@app.get("/channels")
async def list_channels(request: Request) -> ApiResponse:
    """List all notification channels and their configuration status."""
    state = _get_state(request)
    return ok(state.channels)


@app.post("/notify")
async def send_notification(body: NotifyRequest, request: Request) -> ApiResponse:
    """Send a notification about an audit result.

    Delivers the notification to the specified channel (or all enabled
    channels if ``channel="all"``).  Returns per-channel delivery results
    and an aggregate success indicator.

    **Request body**::

        {
            "type": "audit_complete",
            "channel": "all",
            "audit_id": "abc-123",
            "findings_count": 5,
            "critical_count": 2,
            "summary": "Audit complete for Ethena USDe",
            "report_url": "https://...",
            "program": "Ethena USDe",
            "chain": "ethereum",
            "address": "0x..."
        }

    ``channel`` can be ``"discord"``, ``"telegram"``, ``"email"``,
    ``"desktop"``, or ``"all"`` (default).
    """
    state = _get_state(request)
    log.info(
        "notify.request",
        audit_id=body.audit_id,
        channel=body.channel,
        type=body.type,
    )

    channels_to_deliver = _resolve_channels(state, body.channel)
    if not channels_to_deliver:
        return ok(
            BatchDeliveryResult(
                audit_id=body.audit_id,
                request_type=body.type,
                deliveries=[],
                all_succeeded=False,
            )
        )

    deliveries: list[DeliveryResult] = []

    for channel_name in channels_to_deliver:
        result = await _deliver_to_channel(state, channel_name, body)
        if result:
            deliveries.append(result)
            _log_delivery(result, body)

    all_ok = all(d.success for d in deliveries) if deliveries else False

    log.info(
        "notify.complete",
        audit_id=body.audit_id,
        delivered=len(deliveries),
        all_succeeded=all_ok,
    )

    return ok(
        BatchDeliveryResult(
            audit_id=body.audit_id,
            request_type=body.type,
            deliveries=deliveries,
            all_succeeded=all_ok,
        )
    )


@app.post("/test")
async def send_test(body: TestRequest | None = None) -> ApiResponse:
    """Send a test message to one or more notification channels.

    Use this to verify that channels are configured correctly without
    triggering an actual audit notification.

    **Request body** (optional)::

        {
            "channels": ["discord", "telegram"],
            "message": "Vyper Notifier Test"
        }

    If ``channels`` is omitted, tests all configured channels.
    """
    state = _get_state(request) if request else _get_state(Request(scope={"type": "http"}))

    payload = body or TestRequest()
    channels = payload.channels or state.get_enabled_channels()
    test_message = payload.message or "Vyper Notifier Test — this is a test message."

    deliveries: list[DeliveryResult] = []

    for channel_name in channels:
        result = await _deliver_test(state, channel_name, test_message)
        if result:
            deliveries.append(result)

    all_ok = all(d.success for d in deliveries) if deliveries else False

    return ok(
        BatchDeliveryResult(
            deliveries=deliveries,
            all_succeeded=all_ok,
        )
    )


@app.get("/delivery-log")
async def get_delivery_log(limit: int = 50) -> ApiResponse:
    """Get the most recent delivery history entries.

    Args:
        limit: Maximum number of log entries to return (default 50, max 500).
    """
    if not DELIVERY_LOG.exists():
        return ok([])

    try:
        entries: list[DeliveryLogEntry] = []
        with open(str(DELIVERY_LOG), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = DeliveryLogEntry(**json.loads(line))
                        entries.append(entry)
                    except (json.JSONDecodeError, Exception):
                        continue

        # Return most recent first
        entries.reverse()
        limit = min(max(limit, 1), 500)
        return ok(entries[:limit])

    except OSError as exc:
        log.error("delivery_log.read_error", error=str(exc))
        raise err("Failed to read delivery log", status_code=500)


# ---------------------------------------------------------------------------
# Internal delivery logic
# ---------------------------------------------------------------------------


def _resolve_channels(state: AppState, channel: str) -> list[str]:
    """Resolve a channel specifier into a list of enabled channel names.

    ``"all"`` returns all enabled channels.  A single channel name
    returns itself if enabled.
    """
    enabled = set(state.get_enabled_channels())

    if channel == "all":
        return list(enabled)

    if channel in enabled:
        return [channel]

    log.warning("notifier.channel_not_available", channel=channel, enabled=list(enabled))
    return []


async def _deliver_to_channel(
    state: AppState,
    channel: str,
    body: NotifyRequest,
) -> DeliveryResult | None:
    """Dispatch a notification to a single channel."""
    try:
        if channel == "discord":
            discord_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
            return await state.discord.send(
                message=body.summary,
                webhook_url=discord_url,
                program=body.program,
                audit_id=body.audit_id,
                findings_count=body.findings_count,
                critical_count=body.critical_count,
                high_count=body.high_count,
                report_url=body.report_url,
                chain=body.chain,
                address=body.address,
            )

        elif channel == "telegram":
            if not state.telegram:
                return DeliveryResult(
                    channel="telegram",
                    success=False,
                    error="Telegram not configured",
                )
            chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
            return await state.telegram.send(
                message=body.summary,
                chat_id=chat_id,
                program=body.program,
                audit_id=body.audit_id,
                findings_count=body.findings_count,
                critical_count=body.critical_count,
                high_count=body.high_count,
                report_url=body.report_url,
                chain=body.chain,
                address=body.address,
            )

        elif channel == "email":
            to_email = os.environ.get("NOTIFICATION_EMAIL", "")
            subject = f"Vyper Audit: {body.program or 'Smart Contract'}"
            return await state.email.send(
                subject=subject,
                body=body.summary or "Audit analysis finished.",
                to_email=to_email,
                program=body.program,
                audit_id=body.audit_id,
                findings_count=body.findings_count,
                critical_count=body.critical_count,
                high_count=body.high_count,
                report_url=body.report_url,
                chain=body.chain,
                address=body.address,
            )

        elif channel == "desktop":
            title = f"Vyper Audit: {body.program or 'Complete'}"
            msg_parts = [body.summary or ""]
            if body.findings_count > 0:
                msg_parts.append(f"{body.findings_count} findings")
            if body.critical_count > 0:
                msg_parts.append(f"{body.critical_count} critical")
            message = " | ".join(msg_parts)
            return await state.desktop.send(title=title, message=message)

        else:
            log.warning("notifier.unknown_channel", channel=channel)
            return DeliveryResult(
                channel=channel,
                success=False,
                error=f"Unknown channel: {channel}",
            )

    except Exception as exc:
        log.exception(
            "notifier.delivery_failed",
            channel=channel,
            audit_id=body.audit_id,
            error=str(exc),
        )
        return DeliveryResult(
            channel=channel,
            success=False,
            error=str(exc),
        )


async def _deliver_test(
    state: AppState,
    channel: str,
    message: str,
) -> DeliveryResult | None:
    """Send a test message to a single channel."""
    try:
        if channel == "discord":
            discord_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
            return await state.discord.send_simple(
                content=f"🧪 **Test Message** — {message}",
                webhook_url=discord_url,
            )

        elif channel == "telegram":
            if not state.telegram:
                return DeliveryResult(
                    channel="telegram",
                    success=False,
                    error="Telegram not configured",
                )
            chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
            return await state.telegram.send_simple(
                text=f"🧪 Test Message — {message}",
                chat_id=chat_id,
            )

        elif channel == "email":
            to_email = os.environ.get("NOTIFICATION_EMAIL", "")
            return await state.email.send(
                subject="Vyper Notifier — Test Message",
                body=message,
                to_email=to_email,
            )

        elif channel == "desktop":
            return await state.desktop.send(
                title="Vyper Test Notification",
                message=message,
            )

        else:
            return DeliveryResult(
                channel=channel,
                success=False,
                error=f"Unknown channel: {channel}",
            )

    except Exception as exc:
        log.exception("notifier.test_failed", channel=channel, error=str(exc))
        return DeliveryResult(
            channel=channel,
            success=False,
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# Delivery logging
# ---------------------------------------------------------------------------


def _log_delivery(result: DeliveryResult, body: NotifyRequest) -> None:
    """Append a delivery result to the persistent delivery log."""
    try:
        DELIVERY_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = DeliveryLogEntry(
            timestamp=result.timestamp,
            channel=result.channel,
            success=result.success,
            request_type=body.type,
            audit_id=body.audit_id,
            error=result.error,
        )
        line = entry.model_dump_json() + "\n"
        with open(str(DELIVERY_LOG), "a", encoding="utf-8") as f:
            f.write(line)
    except OSError as exc:
        log.error("delivery_log.write_failed", error=str(exc))


# ── Entry Point ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8008,
        log_level="info",
        reload=False,
    )
