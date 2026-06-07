"""Email notifier for the Vyper Notifier Service.

Sends HTML-formatted notification emails via SMTP with optional
attachments (audit reports).  Uses ``asyncio`` and ``smtplib`` with
``loop.run_in_executor`` to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import email.utils
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.encoders import encode_base64
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import structlog

from src.models import DeliveryResult

log = structlog.get_logger()


# ── Templates ───────────────────────────────────────────────


def _render_html_body(
    message: str,
    program: str | None = None,
    audit_id: str | None = None,
    findings_count: int = 0,
    critical_count: int = 0,
    high_count: int = 0,
    report_url: str | None = None,
    chain: str | None = None,
    address: str | None = None,
) -> str:
    """Render an HTML email body using inline styles."""
    prog = program or "Smart Contract"
    severity_color = "#e74c3c" if critical_count > 0 else "#e67e22" if high_count > 0 else "#2ecc71"

    rows = ""
    if audit_id:
        rows += _row("Audit ID", f"<code>{audit_id[:12]}…</code>")
    if chain:
        rows += _row("Chain", chain)
    if address:
        short = f"{address[:6]}…{address[-4:]}" if len(address) > 12 else address
        rows += _row("Contract", f"<code>{short}</code>")
    if findings_count > 0:
        rows += _row("Total Findings", str(findings_count))
    if critical_count > 0:
        rows += _row("Critical", str(critical_count), severity_color)
    if high_count > 0:
        rows += _row("High", str(high_count), severity_color)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Vyper Audit — {prog}</title>
</head>
<body style="
  margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont,
  'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f4f5f7;
">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="max-width: 600px; margin: 40px auto;">
    <tr>
      <td style="background: #5865f2; border-radius: 8px 8px 0 0; padding: 24px 32px;">
        <h1 style="margin: 0; font-size: 20px; font-weight: 600; color: #ffffff;">
          ⚡ Vyper Audit Complete — {prog}
        </h1>
      </td>
    </tr>
    <tr>
      <td style="background: #ffffff; border-radius: 0 0 8px 8px; padding: 32px;
                 box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        <p style="margin: 0 0 24px; font-size: 16px; line-height: 1.5; color: #333;">
          {message or "Audit analysis finished."}
        </p>

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="border-collapse: collapse;">
          {rows}
        </table>

        {f'<p style="margin: 24px 0 0;"><a href="{_escape_html(report_url)}" '
           f'style="display: inline-block; background: #5865f2; color: #fff; '
           f'text-decoration: none; padding: 12px 24px; border-radius: 6px; '
           f'font-weight: 500;">View Full Report →</a></p>'
           if report_url else ""}

        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 32px 0 16px;"/>
        <p style="margin: 0; font-size: 12px; color: #888;">
          Sent by <strong>Vyper Security Scanner</strong>
        </p>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return html


def _row(label: str, value: str, color: str | None = None) -> str:
    val_style = f"color: {color}; font-weight: 600;" if color else "color: #333;"
    return f"""<tr>
      <td style="padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 14px;
                 color: #666; white-space: nowrap; width: 40%;">{label}</td>
      <td style="padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 14px;
                 {val_style}">{value}</td>
    </tr>"""


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


# ── Email Config ────────────────────────────────────────────


@dataclass
class SmtpSettings:
    """SMTP server connection settings.

    Populated from environment variables; can be overridden at
    construction time.
    """

    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    from_email: str = ""
    use_tls: bool = True
    timeout: int = 30


def _load_smtp_settings() -> SmtpSettings:
    """Load SMTP settings from environment variables."""
    return SmtpSettings(
        host=os.environ.get("SMTP_HOST", ""),
        port=int(os.environ.get("SMTP_PORT", "587")),
        username=os.environ.get("SMTP_USER", ""),
        password=os.environ.get("SMTP_PASSWORD", ""),
        from_email=os.environ.get("NOTIFICATION_EMAIL", ""),
    )


# ── Notifier ─────────────────────────────────────────────────


class EmailNotifier:
    """Send notifications via SMTP email.

    Supports HTML-formatted messages and file attachments.

    Usage::

        notifier = EmailNotifier()
        result = await notifier.send(
            subject="Vyper Audit: Ethena USDe",
            body="Audit complete with 5 findings.",
            to_email="security@example.com",
        )
    """

    def __init__(self, settings: SmtpSettings | None = None) -> None:
        self._settings = settings or _load_smtp_settings()

    async def send(
        self,
        subject: str,
        body: str,
        to_email: str | None = None,
        *,
        html_body: str | None = None,
        attachments: list[str | Path] | None = None,
        program: str | None = None,
        audit_id: str | None = None,
        findings_count: int = 0,
        critical_count: int = 0,
        high_count: int = 0,
        report_url: str | None = None,
        chain: str | None = None,
        address: str | None = None,
    ) -> DeliveryResult:
        """Send an email notification.

        Args:
            subject: Email subject line.
            body: Plain-text body (used as fallback for HTML).
            to_email: Recipient email address. Falls back to env var.
            html_body: Optional HTML body. If not provided, auto-generated.
            attachments: List of file paths to attach.
            program: Name of the audited program / project.
            audit_id: Unique audit session identifier.
            findings_count: Total number of findings.
            critical_count: Number of critical findings.
            high_count: Number of high findings.
            report_url: Link to the full audit report.
            chain: Blockchain name.
            address: Contract address.

        Returns:
            A DeliveryResult indicating success or failure.
        """
        to = to_email or self._settings.from_email
        if not to:
            return DeliveryResult(
                channel="email",
                success=False,
                error="No recipient email configured (SMTP_USER or NOTIFICATION_EMAIL)",
            )

        settings = self._settings
        if not settings.host:
            return DeliveryResult(
                channel="email",
                success=False,
                error="SMTP not configured (SMTP_HOST missing)",
            )

        # Auto-generate HTML if not provided
        if html_body is None:
            html_body = _render_html_body(
                message=body,
                program=program,
                audit_id=audit_id,
                findings_count=findings_count,
                critical_count=critical_count,
                high_count=high_count,
                report_url=report_url,
                chain=chain,
                address=address,
            )

        try:
            msg = self._build_message(
                from_addr=settings.from_email,
                to_addr=to,
                subject=subject,
                body_text=body,
                body_html=html_body,
                attachments=attachments,
            )

            await asyncio.get_event_loop().run_in_executor(
                None,
                self._send_smtp,
                settings,
                to,
                msg,
            )

            log.info("email.delivered", to=_mask_email(to), subject=subject)
            return DeliveryResult(channel="email", success=True)

        except smtplib.SMTPAuthenticationError as exc:
            log.error("email.auth_failed", error=str(exc))
            return DeliveryResult(
                channel="email",
                success=False,
                error=f"SMTP authentication failed: {exc}",
            )
        except smtplib.SMTPRecipientsRefused as exc:
            log.error("email.recipient_refused", to=_mask_email(to), error=str(exc))
            return DeliveryResult(
                channel="email",
                success=False,
                error=f"Recipient refused: {exc}",
            )
        except (smtplib.SMTPException, OSError) as exc:
            log.error("email.smtp_error", to=_mask_email(to), error=str(exc))
            return DeliveryResult(
                channel="email",
                success=False,
                error=f"SMTP error: {exc}",
            )
        except Exception as exc:
            log.exception("email.unexpected_error", to=_mask_email(to), error=str(exc))
            return DeliveryResult(
                channel="email",
                success=False,
                error=f"Unexpected error: {exc}",
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_message(
        self,
        from_addr: str,
        to_addr: str,
        subject: str,
        body_text: str,
        body_html: str,
        attachments: list[str | Path] | None = None,
    ) -> MIMEMultipart:
        """Build a MIME multipart/alternative message with optional attachments.

        If there are attachments, uses multipart/mixed as the outer
        container with a multipart/alternative inner part for text +
        HTML body.
        """
        has_attachments = attachments and len(attachments) > 0

        if has_attachments:
            outer = MIMEMultipart("mixed")
        else:
            outer = MIMEMultipart("alternative")

        outer["From"] = from_addr
        outer["To"] = to_addr
        outer["Subject"] = subject
        outer["Date"] = email.utils.formatdate(localtime=True)
        outer["Message-ID"] = email.utils.make_msgid(domain="vyper-scanner")

        # Build inner alternative part if we have attachments
        if has_attachments:
            alt = MIMEMultipart("alternative")
            alt.attach(MIMEText(body_text, "plain", "utf-8"))
            alt.attach(MIMEText(body_html, "html", "utf-8"))
            outer.attach(alt)
        else:
            outer.attach(MIMEText(body_text, "plain", "utf-8"))
            outer.attach(MIMEText(body_html, "html", "utf-8"))

        # Attach files
        if attachments:
            for file_path in attachments:
                try:
                    part = _create_attachment(file_path)
                    if part:
                        outer.attach(part)
                except (FileNotFoundError, OSError) as exc:
                    log.warning("email.attachment_skip", file=str(file_path), error=str(exc))

        return outer

    def _send_smtp(self, settings: SmtpSettings, to_addr: str, msg: MIMEMultipart) -> None:
        """Synchronous SMTP send (runs in thread executor)."""
        if settings.use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(settings.host, settings.port, timeout=settings.timeout) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                if settings.username and settings.password:
                    server.login(settings.username, settings.password)
                server.sendmail(settings.from_email, [to_addr], msg.as_string())
        else:
            with smtplib.SMTP(settings.host, settings.port, timeout=settings.timeout) as server:
                server.ehlo()
                if settings.username and settings.password:
                    server.login(settings.username, settings.password)
                server.sendmail(settings.from_email, [to_addr], msg.as_string())


def _create_attachment(file_path: str | Path) -> MIMEBase | None:
    """Create a MIME attachment part from a file on disk."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(str(path))

    with path.open("rb") as f:
        payload = f.read()

    # Determine MIME type from extension
    ext = path.suffix.lower()
    mime_map: dict[str, tuple[str, str]] = {
        ".pdf": ("application", "pdf"),
        ".md": ("text", "markdown"),
        ".txt": ("text", "plain"),
        ".json": ("application", "json"),
        ".html": ("text", "html"),
        ".csv": ("text", "csv"),
        ".zip": ("application", "zip"),
        ".gzip": ("application", "gzip"),
        ".png": ("image", "png"),
        ".jpg": ("image", "jpeg"),
        ".jpeg": ("image", "jpeg"),
    }

    mime_type = mime_map.get(ext, ("application", "octet-stream"))

    part = MIMEBase(*mime_type)
    part.set_payload(payload)
    encode_base64(part)
    part.add_header(
        "Content-Disposition",
        "attachment",
        filename=path.name,
    )
    return part


def _mask_email(email: str) -> str:
    """Mask an email address for logging."""
    at_pos = email.find("@")
    if at_pos > 1:
        return f"{email[0]}{'*' * (at_pos - 2)}{email[at_pos - 1]}@{email[at_pos + 1:]}"
    return "***"


# ── Factory ─────────────────────────────────────────────────


def create_email_notifier() -> EmailNotifier:
    """Create a new EmailNotifier instance.

    Configuration is loaded from environment variables by default.
    """
    return EmailNotifier()
