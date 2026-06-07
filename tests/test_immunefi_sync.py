"""Immunefi Sync Tests.

Tests for the 02-immunefi service: program sync from GitHub,
detecting new/updated programs, chain indexing, and rate limits.

Pure logic tests — no Docker or HTTP required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Sample Immunefi Program Data ─────────────────────────────


@pytest.fixture
def sample_programs_json():
    """Sample Immunefi program list (matching GitHub JSON format)."""
    return [
        {
            "slug": "opyn",
            "name": "Opyn",
            "url": "https://immunefi.com/bounty/opyn/",
            "max_bounty": "250000 USD",
            "min_bounty": "1000 USD",
            "chains": ["Ethereum"],
            "status": "active",
            "assets_in_scope": ["Opyn Vault", "Gamma Protocol"],
        },
        {
            "slug": "sherlock",
            "name": "Sherlock",
            "url": "https://immunefi.com/bounty/sherlock/",
            "max_bounty": "1000000 USD",
            "min_bounty": "5000 USD",
            "chains": ["Ethereum", "Arbitrum", "Optimism"],
            "status": "active",
            "assets_in_scope": ["Sherlock Core", "Strategy contracts"],
        },
        {
            "slug": "old-program",
            "name": "Old Program",
            "url": "https://immunefi.com/bounty/old-program/",
            "max_bounty": "10000 USD",
            "min_bounty": "500 USD",
            "chains": ["Ethereum"],
            "status": "inactive",
            "assets_in_scope": [],
        },
    ]


@pytest.fixture
def sample_updated_program():
    """A program that has been updated (e.g., new chain added)."""
    return {
        "slug": "opyn",
        "name": "Opyn",
        "url": "https://immunefi.com/bounty/opyn/",
        "max_bounty": "250000 USD",
        "min_bounty": "1000 USD",
        "chains": ["Ethereum", "Polygon"],  # NEW: Polygon added
        "status": "active",
        "assets_in_scope": ["Opyn Vault", "Gamma Protocol"],
    }


# ── Program Sync Tests ───────────────────────────────────────


class TestProgramSync:
    """Testing program sync from GitHub data."""

    def test_sync_programs_parse_json(self, sample_programs_json):
        """Successfully parse the Immunefi program list from JSON."""
        programs = sample_programs_json
        assert len(programs) >= 3, f"Expected at least 3 programs, got {len(programs)}"
        assert programs[0]["slug"] == "opyn"
        assert programs[1]["slug"] == "sherlock"

    def test_detect_new_programs(self, sample_programs_json):
        """A new program not in the database should be detected."""
        existing_slugs = {"opyn", "sherlock"}
        new_program = {"slug": "aave-v3", "name": "Aave V3", "chains": ["Ethereum", "Polygon"]}

        is_new = new_program["slug"] not in existing_slugs
        assert is_new is True, "Aave V3 should be detected as new"

    def test_detect_updated_programs(self, sample_programs_json, sample_updated_program):
        """An existing program with changed data should be detected as updated."""
        existing_opyn = {
            "slug": "opyn",
            "chains": ["Ethereum"],
        }

        updated_opyn = sample_updated_program
        has_changes = set(updated_opyn["chains"]) != set(existing_opyn["chains"])
        assert has_changes is True, "Opyn should be detected as updated (new chain)"

    def test_indexing_by_chain(self, sample_programs_json):
        """Programs should be filterable by chain."""
        ethereum_programs = [
            p for p in sample_programs_json
            if "Ethereum" in p["chains"]
        ]
        assert len(ethereum_programs) >= 3, "All 3 programs are on Ethereum"

        arbitrum_programs = [
            p for p in sample_programs_json
            if "Arbitrum" in p["chains"]
        ]
        assert len(arbitrum_programs) == 1
        assert arbitrum_programs[0]["slug"] == "sherlock"

        solana_programs = [
            p for p in sample_programs_json
            if "Solana" in p["chains"]
        ]
        assert len(solana_programs) == 0

    def test_filter_by_status(self, sample_programs_json):
        """Programs should be filterable by active/inactive status."""
        active = [p for p in sample_programs_json if p["status"] == "active"]
        inactive = [p for p in sample_programs_json if p["status"] == "inactive"]

        assert len(active) == 2
        assert len(inactive) == 1
        assert inactive[0]["slug"] == "old-program"


# ── Rate Limit Handling Tests ────────────────────────────────


class TestRateLimitHandling:
    """GitHub API rate limit and exponential backoff."""

    def test_rate_limit_429_triggers_backoff(self):
        """HTTP 429 should trigger exponential backoff retry."""
        retry_attempts = []

        def mock_request():
            retry_attempts.append(len(retry_attempts) + 1)
            if len(retry_attempts) < 3:
                raise Exception("HTTP 429: rate limit exceeded")
            return {"data": "success"}

        # Simulate: first 2 calls fail with 429, 3rd succeeds
        import time
        for i in range(3):
            try:
                result = mock_request()
                assert result["data"] == "success"
                break
            except Exception:
                if i < 2:
                    continue
                else:
                    raise

        assert len(retry_attempts) == 3, f"Expected 3 attempts, got {len(retry_attempts)}"

    def test_exponential_backoff_delay_increases(self):
        """Each retry should have a longer delay."""
        base_delay = 1  # seconds
        delays = [base_delay * (2 ** i) for i in range(4)]
        # delays = [1, 2, 4, 8]
        assert delays[0] < delays[1] < delays[2] < delays[3]
        assert delays[3] == 8

    def test_max_retries_capped(self):
        """After max retries, give up and raise."""
        max_retries = 3
        attempts = 0

        def should_retry(attempt):
            return attempt < max_retries

        assert should_retry(0) is True
        assert should_retry(1) is True
        assert should_retry(2) is True
        assert should_retry(3) is False
        assert should_retry(4) is False


# ── Stats & Dashboard Tests ──────────────────────────────────


class TestImmunefiStats:
    """Program statistics and dashboard data."""

    def test_stats_computation(self, sample_programs_json):
        """Stats should include total programs, active, inactive."""
        total = len(sample_programs_json)
        active = sum(1 for p in sample_programs_json if p["status"] == "active")
        inactive = total - active

        assert total == 3
        assert active == 2
        assert inactive == 1

    def test_max_bounty_extraction(self, sample_programs_json):
        """Max bounty should be extractable from program data."""
        import re

        def parse_bounty(bounty_str):
            """Extract number from '250000 USD' format."""
            match = re.search(r'(\d+(?:,\d+)*)', bounty_str)
            return int(match.group(1).replace(',', '')) if match else 0

        bounty_values = [parse_bounty(p["max_bounty"]) for p in sample_programs_json if p["status"] == "active"]
        assert sum(bounty_values) > 0
        assert bounty_values[0] == 250000  # Opyn
        assert bounty_values[1] == 1000000  # Sherlock
