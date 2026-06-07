"""Webhook dispatcher with HMAC-SHA256 signing, retry, and delivery logging."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time as time_module
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import structlog
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.models import DeliveryLogEntry, WebhookResult

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATA_DIR = Path(os.environ.get("WEBHOOK_DATA_DIR", "/data/webhook"))
DELIVERY_LOG_PATH = DATA_DIR / "delivery.log"

DEFAULT_TIMEOUT = 10.0  # seconds
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 10.0  # seconds

# Headers
HEADER_SIGNATURE = "X-Vyper-Signature"
HEADER_EVENT = "X-Vyper-Event"
HEADER_CONTENT_TYPE = "Content-Type"
CONTENT_TYPE_JSON = "application/json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_signature(payload: bytes, secret: str) -> str:
    """Return HMAC-SHA256 hex digest for *payload* keyed with *secret*."""
    mac = hmac.new(
        secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    )
    return mac.hexdigest()


def _serialize_payload(payload: dict[str, Any]) -> bytes:
    """Serialize *payload* to JSON bytes with compact encoding."""
    return json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")


def _append_delivery_log(entry: DeliveryLogEntry) -> None:
    """Append a JSON line to the delivery log."""
    try:
        DELIVERY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        line = entry.model_dump_json() + "\n"
        with open(str(DELIVERY_LOG_PATH), "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        log.exception("webhook.delivery_log_write_failed", url=entry.url)


# ---------------------------------------------------------------------------
# Retry policy — retry on network errors and server errors (5xx)
# ---------------------------------------------------------------------------

def _is_retryable(exc: BaseException) -> bool:
    """Return True if the exception should trigger a retry."""
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.NetworkError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500  # retry on server errors only
    return False


webhook_retry = retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=INITIAL_BACKOFF, min=INITIAL_BACKOFF, max=MAX_BACKOFF),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError)),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

class WebhookDispatcher:
    """Delivers signed webhook payloads to configured URLs with retry."""

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: httpx.AsyncClient | None = None
        self._delivery_count: int = 0
        self._failed_count: int = 0

    # ------------------------------------------------------------------
    # Client lifecycle
    # ------------------------------------------------------------------

    async def get_client(self) -> httpx.AsyncClient:
        """Return a lazily-initialised shared HTTPX client."""
        if self._client is None:
            limits = httpx.Limits(max_connections=50, max_keepalive_connections=20)
            timeouts = httpx.Timeout(self._timeout, connect=5.0)
            self._client = httpx.AsyncClient(
                limits=limits,
                timeout=timeouts,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Release the shared HTTPX client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def dispatch(
        self,
        url: str,
        payload: dict[str, Any],
        secret: str,
        event: str,
    ) -> WebhookResult:
        """Deliver a signed webhook to *url*.

        Steps:
        1. Serialise *payload* to compact JSON.
        2. Compute HMAC-SHA256 signature keyed with *secret*.
        3. Send HTTP POST with signature and event headers.
        4. Retry up to *max_retries* times on network/server errors.
        5. Log the delivery outcome to ``delivery.log``.
        """
        body = _serialize_payload(payload)
        signature = _compute_signature(body, secret)

        headers = {
            HEADER_SIGNATURE: f"sha256={signature}",
            HEADER_EVENT: event,
            HEADER_CONTENT_TYPE: CONTENT_TYPE_JSON,
            "User-Agent": "Vyper-Webhook/0.1.0",
        }

        start = time_module.perf_counter()
        result = await self._send_with_retry(url, body, headers)
        duration_ms = (time_module.perf_counter() - start) * 1000.0

        # Track counters
        self._delivery_count += 1
        if not result.success:
            self._failed_count += 1

        # Persist to delivery log
        self._log_delivery(url, event, result, duration_ms)

        return result

    async def dispatch_batch(
        self,
        urls: list[str],
        payload: dict[str, Any],
        secret: str,
        event: str,
    ) -> list[WebhookResult]:
        """Deliver the same payload to every URL in *urls* concurrently."""
        import asyncio

        results = await asyncio.gather(
            *(self.dispatch(url, payload, secret, event) for url in urls),
            return_exceptions=False,  # let individual failures through
        )
        return list(results)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @webhook_retry
    async def _send_with_retry(
        self,
        url: str,
        body: bytes,
        headers: dict[str, str],
    ) -> WebhookResult:
        """Perform the HTTP POST (single attempt — retry decorator handles retries)."""
        client = await self.get_client()
        try:
            response = await client.post(url, content=body, headers=headers)
            response.raise_for_status()
            return WebhookResult(
                url=url,
                success=True,
                status_code=response.status_code,
                duration_ms=0.0,  # updated by caller
            )
        except httpx.TimeoutException:
            raise
        except httpx.NetworkError:
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500:
                raise  # retryable
            # Non-retryable client error (4xx) — return immediately
            return WebhookResult(
                url=url,
                success=False,
                status_code=exc.response.status_code,
                error=f"HTTP {exc.response.status_code}: {exc.response.text[:500]}",
            )
        except Exception as exc:
            # Unexpected error (e.g. SSL cert issue) — do not retry
            return WebhookResult(
                url=url,
                success=False,
                error=f"Unexpected error: {exc}",
            )

    def _log_delivery(
        self,
        url: str,
        event: str,
        result: WebhookResult,
        duration_ms: float,
    ) -> None:
        """Write a delivery log entry."""
        entry = DeliveryLogEntry(
            timestamp=datetime.now(UTC).isoformat(),
            url=url,
            event=event,
            success=result.success,
            status_code=result.status_code,
            duration_ms=round(duration_ms, 1),
            error=result.error,
        )
        _append_delivery_log(entry)

        # Also emit structured log
        log.info(
            "webhook.delivery",
            url=url,
            event=event,
            success=result.success,
            status_code=result.status_code,
            duration_ms=round(duration_ms, 1),
            error=result.error,
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def delivery_count(self) -> int:
        """Total delivery attempts since service start."""
        return self._delivery_count

    @property
    def failed_count(self) -> int:
        """Failed delivery attempts since service start."""
        return self._failed_count

    @staticmethod
    def read_delivery_log(
        limit: int = 100,
        offset: int = 0,
        event: str | None = None,
        success: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Read and filter entries from the persisted delivery log.

        Respects *limit* and *offset* for pagination.  Optionally filters
        by *event* type and/or *success* status.
        """
        entries: list[dict[str, Any]] = []

        if not DELIVERY_LOG_PATH.exists():
            return entries

        try:
            with open(str(DELIVERY_LOG_PATH), encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Apply filters
                    if event is not None and entry.get("event") != event:
                        continue
                    if success is not None and entry.get("success") != success:
                        continue

                    entries.append(entry)
        except OSError:
            log.exception("webhook.delivery_log_read_failed")
            return entries

        # Apply offset / limit in Python (log is append-only, no index)
        return entries[offset: offset + limit]


def create_dispatcher(
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
) -> WebhookDispatcher:
    """Factory function — builds a :class:`WebhookDispatcher`."""
    return WebhookDispatcher(timeout=timeout, max_retries=max_retries)
