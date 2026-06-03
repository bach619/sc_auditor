"""Tests for Provider Config Validation in Antonio Agent.

Tests the _validate_provider_urls function that detects
misconfigured LLM provider URLs (e.g., DeepSeek domain for Anthropic).

Run with:
    cd services/14-agent
    python -m pytest tests/test_provider_validation.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path so we can import app.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import _validate_provider_urls  # noqa: E402


def test_detect_cross_provider_url_mix() -> None:
    """Detect when anthropic's base_url uses deepseek domain."""
    providers = {
        "anthropic": {
            "api_key": "sk-test",
            "base_url": "https://api.deepseek.com/anthropic",
            "model": "claude-3-5-sonnet-20241022",
        }
    }
    errors = _validate_provider_urls(providers)
    assert len(errors) >= 1
    combined = " ".join(errors).lower()
    assert "deepseek" in combined


def test_valid_openai_passes() -> None:
    """Valid OpenAI config should pass validation."""
    providers = {
        "openai": {
            "api_key": "sk-test",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
        }
    }
    errors = _validate_provider_urls(providers)
    assert len(errors) == 0


def test_valid_anthropic_passes() -> None:
    """Valid Anthropic config should pass validation."""
    providers = {
        "anthropic": {
            "api_key": "sk-test",
            "base_url": "https://api.anthropic.com/v1",
            "model": "claude-3-5-sonnet-20241022",
        }
    }
    errors = _validate_provider_urls(providers)
    assert len(errors) == 0


def test_skip_unconfigured_providers() -> None:
    """Providers without API key should be skipped (no errors)."""
    providers = {
        "openai": {
            "api_key": "",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
        },
        "anthropic": {
            "api_key": "",
            "base_url": "https://api.deepseek.com/anthropic",
            "model": "claude-3-5-sonnet-20241022",
        },
    }
    errors = _validate_provider_urls(providers)
    assert len(errors) == 0  # Both have no API key, so skipped


def test_valid_deepseek_passes() -> None:
    """Valid DeepSeek config should pass."""
    providers = {
        "deepseek": {
            "api_key": "sk-test",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat",
        }
    }
    errors = _validate_provider_urls(providers)
    assert len(errors) == 0


def test_xai_domain_mismatch() -> None:
    """Detect when openai uses x.ai domain."""
    providers = {
        "openai": {
            "api_key": "sk-test",
            "base_url": "https://api.x.ai/v1",
            "model": "gpt-4o",
        }
    }
    errors = _validate_provider_urls(providers)
    assert len(errors) >= 1
    assert "x.ai" in errors[0]


def test_google_domain_mismatch() -> None:
    """Detect when anthropic uses google domain."""
    providers = {
        "anthropic": {
            "api_key": "sk-test",
            "base_url": "https://generativelanguage.googleapis.com/v1",
            "model": "claude-3-5-sonnet-20241022",
        }
    }
    errors = _validate_provider_urls(providers)
    assert len(errors) >= 1
    assert "google" in errors[0]


def test_multiple_providers_one_bad() -> None:
    """Only the misconfigured provider should generate errors."""
    providers = {
        "openai": {
            "api_key": "sk-valid",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
        },
        "anthropic": {
            "api_key": "sk-bad",
            "base_url": "https://api.deepseek.com/anthropic",
            "model": "claude-3-5-sonnet-20241022",
        },
    }
    errors = _validate_provider_urls(providers)
    assert len(errors) == 1  # Only anthropic should error
    assert "anthropic" in errors[0]
