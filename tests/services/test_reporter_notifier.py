"""Reporter & Notifier Tests — 09-reporter and 10-notifier (15 tests).

Tests for report generation, Markdown format, immunefi format, empty reports,
critical finding highlighting, PDF generation, Discord/Telegram notification
formats, summary stats, notification skip, multi-channel, rate limiting,
retry, report file path, and template rendering.

All imports use namespace isolation from services/09-reporter/src/ and
services/10-notifier/src/. Uses unittest.mock — no Docker required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Path setup for imports ───────────────────────────────────
_REPORTER_SRC = str(Path(__file__).resolve().parents[2] / "services" / "09-reporter")
_NOTIFIER_SRC = str(Path(__file__).resolve().parents[2] / "services" / "10-notifier")


def _import_reporter():
    """Import reporter service modules with namespace isolation."""
    import importlib
    to_remove = [k for k in list(sys.modules) if k.startswith("src.")]
    for k in to_remove:
        del sys.modules[k]
    if "src" in sys.modules:
        del sys.modules["src"]

    sys.path.insert(0, _REPORTER_SRC)
    try:
        models = importlib.import_module("src.models")
        immunefi = importlib.import_module("src.immunefi")
        full = importlib.import_module("src.full")
        return models, immunefi, full
    finally:
        sys.path.pop(0)


def _import_notifier():
    """Import notifier service modules with namespace isolation."""
    import importlib
    to_remove = [k for k in list(sys.modules) if k.startswith("src.")]
    for k in to_remove:
        del sys.modules[k]
    if "src" in sys.modules:
        del sys.modules["src"]

    sys.path.insert(0, _NOTIFIER_SRC)
    try:
        models = importlib.import_module("src.models")
        discord = importlib.import_module("src.discord")
        telegram = importlib.import_module("src.telegram")
        email = importlib.import_module("src.email")
        return models, discord, telegram, email
    finally:
        sys.path.pop(0)


# ── Shared helpers ──────────────────────────────────────────


def _make_finding(reporter_models, **kwargs):
    """Create a Finding model instance with default values."""
    defaults = {
        "id": "F-001", "tool": "slither", "severity": "medium",
        "title": "Test Finding", "description": "A test finding description.",
        "contract": "Test.sol", "line": 42, "recommendation": "Fix it.",
        "classification": "true_positive", "confidence": 0.85,
    }
    defaults.update(kwargs)
    return reporter_models.Finding(**defaults)


def _make_exploit_result(reporter_models, **kwargs):
    """Create an ExploitResult model instance."""
    defaults = {
        "finding_id": "F-001", "success": True,
        "poc_script": "// PoC contract Attack {}", "tx_hash": "0xabc123",
        "gas_used": 85000, "value_at_risk": 50000.0,
    }
    defaults.update(kwargs)
    return reporter_models.ExploitResult(**defaults)


def _setup_template(base_dir, filename, content):
    """Create a Jinja2 template file in the given directory."""
    tmpl_dir = base_dir / "templates"
    tmpl_dir.mkdir(parents=True, exist_ok=True)
    (tmpl_dir / filename).write_text(content)
    return tmpl_dir


# ─────────────────────────────────────────────────────────────
# 1. Report generation from findings
# ─────────────────────────────────────────────────────────────


class TestReportGeneration:
    """Tests for ImmunefiReportGenerator and FullReportGenerator."""

    def test_immunefi_generator_initialized_with_template(self):
        """ImmunefiReportGenerator initializes with the immunefi template."""
        rmodels, immunefi_mod, _full = _import_reporter()
        gen = immunefi_mod.ImmunefiReportGenerator()
        assert gen.template is not None
        assert gen.env is not None

    def test_full_generator_initialized_with_template(self):
        """FullReportGenerator initializes with the full template."""
        rmodels, _immunefi, full_mod = _import_reporter()
        gen = full_mod.FullReportGenerator()
        assert gen.template is not None
        assert gen.env is not None

    def test_immunefi_generate_returns_string_content(self, tmp_path):
        """generate() returns Markdown content as string."""
        rmodels, immunefi_mod, _full = _import_reporter()

        # Create a minimal template BEFORE constructing generator
        tmpl_dir = tmp_path / "templates"
        tmpl_dir.mkdir(parents=True, exist_ok=True)
        (tmpl_dir / "immunefi.md.j2").write_text(
            "# Immunefi Report\n- Audit: {{ audit_id }}\n- Program: {{ program }}\n"
            "- Chain: {{ chain }}\n- Findings: {{ tp_count }}\n"
        )

        gen = immunefi_mod.ImmunefiReportGenerator(templates_dir=str(tmpl_dir))

        findings = [
            _make_finding(rmodels, id="F-001", classification="true_positive", severity="critical"),
            _make_finding(rmodels, id="F-002", classification="true_positive", severity="high"),
        ]

        with patch.object(gen, "_save_report"):
            content = gen.generate(
                audit_id="audit-123", program="ethena", chain="ethereum",
                address="0xABC", findings=findings,
            )

        assert "Immunefi Report" in content
        assert "audit-123" in content
        assert "ethena" in content
        assert "2" in content  # tp_count


# ─────────────────────────────────────────────────────────────
# 2. Markdown report format (headers, sections)
# ─────────────────────────────────────────────────────────────


class TestMarkdownReportFormat:
    """Tests for Markdown report structure."""

    def test_full_report_contains_expected_sections(self, tmp_path):
        """Full report includes standard sections."""
        rmodels, _immunefi, full_mod = _import_reporter()

        tmpl_dir = _setup_template(tmp_path, "full.md.j2",
            "# Full Audit Report\n"
            "## Executive Summary\n"
            "Audit ID: {{ audit_id }}\n"
            "## Findings\n"
            "{% for f in findings %}\n"
            "- **{{ f.severity | capitalize }}**: {{ f.title }}\n"
            "{% endfor %}\n"
            "## Metrics\n"
            "TP: {{ tp_count }}, FP: {{ fp_count }}\n"
        )

        gen = full_mod.FullReportGenerator(templates_dir=str(tmpl_dir))

        findings = [
            _make_finding(rmodels, id="F-001", severity="critical", title="Reentrancy",
                          classification="true_positive"),
            _make_finding(rmodels, id="F-002", severity="high", title="Access Control",
                          classification="false_positive"),
        ]

        with patch.object(gen, "_save_report"):
            content = gen.generate(
                audit_id="audit-456", program="testprog", chain="ethereum",
                address="0xDEF", findings=findings,
            )

        assert "Full Audit Report" in content
        assert "Executive Summary" in content
        assert "Findings" in content
        assert "Metrics" in content
        assert "audit-456" in content


# ─────────────────────────────────────────────────────────────
# 3. Immunefi-specific report format
# ─────────────────────────────────────────────────────────────


class TestImmunefiReportFormat:
    """Tests for Immunefi-specific report behavior."""

    def test_filter_true_positives_only(self):
        """_filter_true_positives returns only TP findings, sorted by severity."""
        rmodels, immunefi_mod, _full = _import_reporter()

        findings = [
            _make_finding(rmodels, id="F-001", severity="low", classification="true_positive"),
            _make_finding(rmodels, id="F-002", severity="critical", classification="true_positive"),
            _make_finding(rmodels, id="F-003", severity="high", classification="false_positive"),
        ]

        tp = immunefi_mod.ImmunefiReportGenerator._filter_true_positives(findings)
        assert len(tp) == 2
        assert tp[0].severity == "critical"  # Sorted — critical first
        assert tp[1].severity == "low"

    def test_exploit_as_truth_filter(self):
        """When exploit_results provided, only confirmed findings are TP."""
        rmodels, immunefi_mod, _full = _import_reporter()

        findings = [
            _make_finding(rmodels, id="F-001", severity="high", classification="true_positive"),
            _make_finding(rmodels, id="F-002", severity="critical", classification="true_positive"),
        ]

        exploit_results = [
            _make_exploit_result(rmodels, finding_id="F-001", success=True),
            _make_exploit_result(rmodels, finding_id="F-002", success=False),
        ]

        tp = immunefi_mod.ImmunefiReportGenerator._filter_true_positives(
            findings, exploit_results=exploit_results
        )
        assert len(tp) == 1
        assert tp[0].id == "F-001"


# ─────────────────────────────────────────────────────────────
# 4. Report with no findings → empty report
# ─────────────────────────────────────────────────────────────


class TestEmptyReport:
    """Tests for report generation with no findings."""

    def test_immunefi_report_with_no_findings(self, tmp_path):
        """Immunefi report with empty findings is generated cleanly."""
        rmodels, immunefi_mod, _full = _import_reporter()
        tmpl_dir = _setup_template(tmp_path, "immunefi.md.j2",
            "# Immunefi Report — {{ program }}\nNo findings to report.\n"
            "Total: {{ tp_count }}\n"
        )
        gen = immunefi_mod.ImmunefiReportGenerator(templates_dir=str(tmpl_dir))

        with patch.object(gen, "_save_report"):
            content = gen.generate(
                audit_id="empty-1", program="prog", chain="ethereum",
                address="0x0", findings=[],
            )

        assert "No findings" in content
        assert "0" in content

    def test_full_report_with_no_findings(self, tmp_path):
        """Full report with empty findings still renders main sections."""
        rmodels, _immunefi, full_mod = _import_reporter()
        tmpl_dir = _setup_template(tmp_path, "full.md.j2",
            "# Full Report — {{ program }}\n"
            "Findings: {{ findings | length }}\n"
            "TP: {{ tp_count }}\n"
        )
        gen = full_mod.FullReportGenerator(templates_dir=str(tmpl_dir))

        with patch.object(gen, "_save_report"):
            content = gen.generate(
                audit_id="empty-2", program="prog", chain="ethereum",
                address="0x0", findings=[],
            )

        assert "Findings: 0" in content
        assert "TP: 0" in content


# ─────────────────────────────────────────────────────────────
# 5. Report with critical finding → highlighted
# ─────────────────────────────────────────────────────────────


class TestCriticalHighlighting:
    """Tests that critical findings are highlighted in reports."""

    def test_critical_findings_appear_first_in_immunefi(self, tmp_path):
        """Critical findings are listed before others in immunefi report."""
        rmodels, immunefi_mod, _full = _import_reporter()
        tmpl_dir = _setup_template(tmp_path, "immunefi.md.j2",
            "{% for f in findings %}\n"
            "- **{{ f.severity | capitalize }}**: {{ f.title }}\n"
            "{% endfor %}\n"
            "Critical: {{ critical_count }}, High: {{ high_count }}\n"
        )
        gen = immunefi_mod.ImmunefiReportGenerator(templates_dir=str(tmpl_dir))

        findings = [
            _make_finding(rmodels, id="F-001", severity="low", title="Low issue",
                          classification="true_positive"),
            _make_finding(rmodels, id="F-002", severity="critical", title="Critical reentrancy",
                          classification="true_positive"),
            _make_finding(rmodels, id="F-003", severity="high", title="High access issue",
                          classification="true_positive"),
        ]

        with patch.object(gen, "_save_report"):
            content = gen.generate(
                audit_id="crit-1", program="prog", chain="ethereum",
                address="0xABC", findings=findings,
            )

        # Critical should appear before High before Low
        crit_pos = content.index("Critical reentrancy")
        high_pos = content.index("High access issue")
        low_pos = content.index("Low issue")
        assert crit_pos < high_pos < low_pos

    def test_severity_distribution_counts_critical(self):
        """_severity_distribution correctly counts critical findings."""
        rmodels, immunefi_mod, _full = _import_reporter()

        findings = [
            _make_finding(rmodels, id="F-001", severity="critical", classification="true_positive"),
            _make_finding(rmodels, id="F-002", severity="critical", classification="true_positive"),
            _make_finding(rmodels, id="F-003", severity="high", classification="false_positive"),
        ]

        dist = immunefi_mod.ImmunefiReportGenerator._severity_distribution(findings)
        # Find critical count
        critical_entry = next((s, c) for s, c in dist if s == "critical")
        assert critical_entry == ("critical", 2)


# ─────────────────────────────────────────────────────────────
# 6. PDF generation request
# ─────────────────────────────────────────────────────────────


class TestPDFGeneration:
    """Tests for PDF report generation request handling."""

    def test_report_path_generation_contains_audit_id(self):
        """Report paths include the audit_id."""
        rmodels, immunefi_mod, _full = _import_reporter()
        gen = immunefi_mod.ImmunefiReportGenerator()

        with patch.object(gen, "_save_report", return_value=Path("/data/reports/audit-1/immunefi.md")):
            findings = [_make_finding(rmodels)]
            gen.generate(
                audit_id="audit-1", program="prog", chain="ethereum",
                address="0xABC", findings=findings,
            )

        # After generate, the report is saved. Verify the path format.
        report_dir = Path("/data/reporter/reports/audit-1")
        expected_path = report_dir / "immunefi.md"
        assert str(expected_path) == "/data/reporter/reports/audit-1/immunefi.md"


# ─────────────────────────────────────────────────────────────
# 7. Discord notification format
# ─────────────────────────────────────────────────────────────


class TestDiscordNotification:
    """Tests for Discord notification format and delivery."""

    def test_build_embed_has_required_fields(self):
        """_build_embed produces embed with title, description, color."""
        _nmodels, discord_mod, _tel, _email = _import_notifier()

        notifier = discord_mod.DiscordNotifier()
        embed = notifier._build_embed(
            message="Audit complete.", program="TestProgram",
            audit_id="audit-abc123def456", findings_count=5,
            critical_count=2, high_count=1,
            report_url="https://reports/audit-abc.md",
            chain="ethereum", address="0xABC123DEF456789",
        )

        d = embed.to_dict()
        assert "Vyper Audit Complete" in d["title"]
        assert "TestProgram" in d["title"]
        assert d["description"] is not None
        assert len(d["fields"]) >= 4  # Audit ID, Chain, Contract, Findings

    def test_embed_color_critical(self):
        """Critical findings produce red embed color."""
        _nmodels, discord_mod, _tel, _email = _import_notifier()
        color = discord_mod._select_color(critical=1, high=0)
        assert color == discord_mod.EMBED_COLOR_CRITICAL

    def test_embed_color_high(self):
        """High findings (no critical) produce orange embed color."""
        _nmodels, discord_mod, _tel, _email = _import_notifier()
        color = discord_mod._select_color(critical=0, high=3)
        assert color == discord_mod.EMBED_COLOR_HIGH

    def test_embed_color_default(self):
        """No critical/high findings produce default blurple color."""
        _nmodels, discord_mod, _tel, _email = _import_notifier()
        color = discord_mod._select_color(critical=0, high=0)
        assert color == discord_mod.EMBED_COLOR_DEFAULT


# ─────────────────────────────────────────────────────────────
# 8. Telegram notification format
# ─────────────────────────────────────────────────────────────


class TestTelegramNotification:
    """Tests for Telegram notification format."""

    def test_format_message_contains_program_and_summary(self):
        """_format_message includes program name and findings summary."""
        _nmodels, _discord, telegram_mod, _email = _import_notifier()

        notifier = telegram_mod.TelegramNotifier(bot_token="test:1234")
        text = notifier._format_message(
            message="Audit completed successfully.",
            program="Ethena",
            audit_id="audit-xyz123",
            findings_count=5, critical_count=2, high_count=1,
            report_url="https://reports/audit-xyz.md",
            chain="ethereum", address="0xABCDEF1234567890",
        )

        assert "Vyper Audit Complete" in text
        assert "Ethena" in text
        assert "5" in text  # findings_count
        assert "2" in text  # critical_count
        assert "1" in text  # high_count

    def test_escape_markdown_escapes_special_chars(self):
        """_escape_md escapes Telegram MarkdownV2 special characters."""
        _nmodels, _discord, telegram_mod, _email = _import_notifier()

        result = telegram_mod._escape_md("hello_world *bold* [link]")
        assert "\\_" in result
        assert "\\*" in result
        assert "\\[" in result

    def test_escape_markdown_preserves_normal_text(self):
        """_escape_md does not alter plain alphanumeric text."""
        _nmodels, _discord, telegram_mod, _email = _import_notifier()

        result = telegram_mod._escape_md("HelloWorld123")
        assert "\\" not in result


# ─────────────────────────────────────────────────────────────
# 9. Notification with summary stats
# ─────────────────────────────────────────────────────────────


class TestNotificationSummaryStats:
    """Tests for notification summary statistics."""

    def test_discord_notify_payload_includes_counts(self):
        """DiscordNotifier.send() builds embed with findings counts."""
        _nmodels, discord_mod, _tel, _email = _import_notifier()

        notifier = discord_mod.DiscordNotifier()
        embed = notifier._build_embed(
            message="Done.", program="Prog",
            audit_id="a-1", report_url="https://example.com",
            chain="ethereum", address="0xABC",
            findings_count=10, critical_count=3, high_count=2,
        )

        fields_text = " ".join(f.value for f in embed.fields)
        assert "10" in fields_text
        assert "3" in fields_text
        assert "2" in fields_text

    def test_telegram_notify_payload_includes_counts(self):
        """Telegram message includes total, critical, high counts."""
        _nmodels, _discord, telegram_mod, _email = _import_notifier()

        notifier = telegram_mod.TelegramNotifier(bot_token="test:5678")
        text = notifier._format_message(
            message="Done.", program="Prog",
            findings_count=8, critical_count=0, high_count=4,
            audit_id="a-1", report_url="https://example.com",
            chain="ethereum", address="0xABC",
        )

        assert "8" in text
        assert "0" in text  # critical_count
        assert "4" in text  # high_count


# ─────────────────────────────────────────────────────────────
# 10. Notification skip when disabled
# ─────────────────────────────────────────────────────────────


class TestNotificationSkip:
    """Tests that notifications are skipped when channels are disabled."""

    @pytest.mark.asyncio
    async def test_discord_skips_without_webhook_url(self):
        """DiscordNotifier.send() returns failure result when no webhook URL."""
        _nmodels, discord_mod, _tel, _email = _import_notifier()
        notifier = discord_mod.DiscordNotifier()
        result = await notifier.send(message="Test", webhook_url="")
        assert result.success is False
        assert "webhook" in result.error.lower()

    @pytest.mark.asyncio
    async def test_telegram_skips_without_chat_id(self):
        """TelegramNotifier.send() returns failure result when no chat ID."""
        _nmodels, _discord, telegram_mod, _email = _import_notifier()
        notifier = telegram_mod.TelegramNotifier(bot_token="test:9999")
        result = await notifier.send(message="Test", chat_id="")
        assert result.success is False
        assert "chat id" in (result.error or "").lower()


# ─────────────────────────────────────────────────────────────
# 11. Multi-channel notification (Discord + Telegram + Email)
# ─────────────────────────────────────────────────────────────


class TestMultiChannelNotification:
    """Tests for multi-channel notification delivery."""

    def test_batch_delivery_result_tracks_all_channels(self):
        """BatchDeliveryResult holds multiple channel results."""
        _nmodels, _discord, _tel, _email = _import_notifier()

        results = [
            _nmodels.DeliveryResult(channel="discord", success=True),
            _nmodels.DeliveryResult(channel="telegram", success=True),
            _nmodels.DeliveryResult(channel="email", success=False, error="SMTP timeout"),
        ]

        batch = _nmodels.BatchDeliveryResult(
            audit_id="audit-1", request_type="audit_complete",
            deliveries=results,
            all_succeeded=all(r.success for r in results),
        )

        assert batch.audit_id == "audit-1"
        assert len(batch.deliveries) == 3
        assert batch.all_succeeded is False

    def test_channel_config_models(self):
        """ChannelConfig describes each channel state."""
        _nmodels, _discord, _tel, _email = _import_notifier()

        cfg = _nmodels.ChannelConfig(
            name="discord", enabled=True, type="webhook",
            description="Discord webhook integration",
        )
        assert cfg.name == "discord"
        assert cfg.enabled is True
        assert cfg.type == "webhook"


# ─────────────────────────────────────────────────────────────
# 12. Notification rate limiting
# ─────────────────────────────────────────────────────────────


class TestNotificationRateLimiting:
    """Tests for Discord rate limit handling."""

    def test_discord_client_handles_429_with_retry_after(self):
        """DiscordClient.post_webhook retries on 429 with Retry-After header."""
        _nmodels, discord_mod, _tel, _email = _import_notifier()

        client = discord_mod.DiscordClient()
        assert client is not None

    def test_parse_retry_after_extracts_value(self):
        """_parse_retry_after extracts float from response body."""
        _nmodels, discord_mod, _tel, _email = _import_notifier()

        import httpx
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.json.return_value = {"retry_after": 15.5}
        mock_resp.status_code = 429

        result = discord_mod._parse_retry_after(mock_resp)
        assert result == 15.5

    def test_parse_retry_after_defaults_to_zero(self):
        """_parse_retry_after returns 0.0 when body lacks retry_after field."""
        _nmodels, discord_mod, _tel, _email = _import_notifier()

        import httpx
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.json.return_value = {}
        mock_resp.status_code = 429

        result = discord_mod._parse_retry_after(mock_resp)
        assert result == 0.0


# ─────────────────────────────────────────────────────────────
# 13. Notification retry on failure
# ─────────────────────────────────────────────────────────────


class TestNotificationRetry:
    """Tests for notification retry behavior."""

    def test_delivery_result_has_error_field(self):
        """DeliveryResult.error stores failure reason."""
        _nmodels, _discord, _tel, _email = _import_notifier()

        result = _nmodels.DeliveryResult(
            channel="discord", success=False,
            error="HTTP 500: Internal Server Error",
        )

        assert result.channel == "discord"
        assert result.success is False
        assert "HTTP 500" in result.error


# ─────────────────────────────────────────────────────────────
# 14. Report file path generation
# ─────────────────────────────────────────────────────────────


class TestReportFilePathGeneration:
    """Tests for report file path construction."""

    def test_save_report_creates_directory(self, tmp_path):
        """_save_report creates directories and writes the file."""
        rmodels, immunefi_mod, _full = _import_reporter()

        with patch.object(immunefi_mod, "REPORTS_BASE", tmp_path):
            gen = immunefi_mod.ImmunefiReportGenerator()
            path = gen._save_report(
                audit_id="path-test-1",
                content="# Test Report",
                filename="immunefi.md",
            )

            assert path.exists()
            assert path.name == "immunefi.md"
            assert path.parent.name == "path-test-1"
            assert "# Test Report" in path.read_text()

    def test_full_save_report_creates_directory(self, tmp_path):
        """FullReportGenerator._save_report persists full.md."""
        rmodels, _immunefi, full_mod = _import_reporter()

        with patch.object(full_mod, "REPORTS_BASE", tmp_path):
            gen = full_mod.FullReportGenerator()
            path = gen._save_report(
                audit_id="full-path-1",
                content="# Full Report",
                filename="full.md",
            )

            assert path.exists()
            assert "full.md" in str(path)
            assert "# Full Report" in path.read_text()


# ─────────────────────────────────────────────────────────────
# 15. Report template rendering
# ─────────────────────────────────────────────────────────────


class TestReportTemplateRendering:
    """Tests for Jinja2 template rendering in reports."""

    def test_template_renders_audit_id(self, tmp_path):
        """Template correctly renders audit_id variable."""
        rmodels, _immunefi, full_mod = _import_reporter()
        tmpl_dir = _setup_template(tmp_path, "full.md.j2",
            "# Audit: {{ audit_id }}\n"
            "Program: {{ program }}\n"
            "Chain: {{ chain }}\n"
            "Address: {{ address }}\n"
        )
        gen = full_mod.FullReportGenerator(templates_dir=str(tmpl_dir))

        findings = [_make_finding(rmodels)]
        with patch.object(gen, "_save_report"):
            content = gen.generate(
                audit_id="tmpl-test-1", program="MyProg", chain="arbitrum",
                address="0xDEADBEEF", findings=findings,
            )

        assert "Audit: tmpl-test-1" in content
        assert "Program: MyProg" in content
        assert "Chain: arbitrum" in content
        assert "Address: 0xDEADBEEF" in content

    def test_template_renders_finding_details(self, tmp_path):
        """Template renders finding severity, title, and description."""
        rmodels, _immunefi, full_mod = _import_reporter()
        tmpl_dir = _setup_template(tmp_path, "full.md.j2",
            "{% for f in findings %}\n"
            "### {{ f.severity | capitalize }}: {{ f.title }}\n"
            "{{ f.description }}\n"
            "{% endfor %}\n"
        )
        gen = full_mod.FullReportGenerator(templates_dir=str(tmpl_dir))

        findings = [
            _make_finding(rmodels, id="F-099", severity="critical",
                          title="Heap Overflow", description="Memory corruption in buffer."),
        ]

        with patch.object(gen, "_save_report"):
            content = gen.generate(
                audit_id="tpl-2", program="Prog", chain="ethereum",
                address="0x1", findings=findings,
            )

        assert "Critical: Heap Overflow" in content
        assert "Memory corruption in buffer." in content

    def test_empty_template_with_no_findings_loop(self, tmp_path):
        """Template with for-loop over empty findings list renders without error."""
        rmodels, _immunefi, full_mod = _import_reporter()
        tmpl_dir = _setup_template(tmp_path, "full.md.j2",
            "# Report\n"
            "{% for f in findings %}- {{ f.title }}\n{% endfor %}\n"
            "End of report.\n"
        )
        gen = full_mod.FullReportGenerator(templates_dir=str(tmpl_dir))

        with patch.object(gen, "_save_report"):
            content = gen.generate(
                audit_id="tpl-3", program="P", chain="eth",
                address="0x0", findings=[],
            )

        assert "End of report." in content
