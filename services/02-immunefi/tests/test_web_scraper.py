"""Tests for ImmunefiWebScraper extraction helpers.

Only tests pure-functions (no HTTP requests). Actual network calls
belong in integration/e2e tests.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.providers.immunefi_web_scraper import ImmunefiWebScraper


# ── _extract_next_data ──────────────────────────────────────


class TestExtractNextData:
    def test_standard_format(self) -> None:
        """Match standard <script id=__NEXT_DATA__ type=application/json>."""
        next_data = {"props": {"pageProps": {}}, "page": "/bug-bounty"}
        html = f"""
        <html>
        <head></head>
        <body>
            <script id="__NEXT_DATA__" type="application/json">
                {json.dumps(next_data)}
            </script>
        </body>
        </html>
        """
        result = ImmunefiWebScraper._extract_next_data(html)
        assert result is not None
        assert result["page"] == "/bug-bounty"

    def test_single_quotes(self) -> None:
        """Match with single-quoted attribute."""
        next_data = {"key": "value"}
        html = f"""
        <script id='__NEXT_DATA__' type='application/json'>
            {json.dumps(next_data)}
        </script>
        """
        result = ImmunefiWebScraper._extract_next_data(html)
        assert result is not None
        assert result["key"] == "value"

    def test_no_type_attribute(self) -> None:
        """Match <script id=__NEXT_DATA__> without type attribute."""
        next_data = {"key": "value"}
        html = f"""
        <script id="__NEXT_DATA__" data-noptimize="1">
            {json.dumps(next_data)}
        </script>
        """
        result = ImmunefiWebScraper._extract_next_data(html)
        assert result is not None
        assert result["key"] == "value"

    def test_no_next_data_tag(self) -> None:
        html = "<html><body>No data here</body></html>"
        result = ImmunefiWebScraper._extract_next_data(html)
        assert result is None

    def test_invalid_json_in_tag(self) -> None:
        html = """
        <script id="__NEXT_DATA__" type="application/json">
            {invalid json here}
        </script>
        """
        result = ImmunefiWebScraper._extract_next_data(html)
        assert result is None

    def test_minified_html(self) -> None:
        """Handle minified HTML without line breaks."""
        next_data = {"a": 1}
        html = f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script></html>'
        result = ImmunefiWebScraper._extract_next_data(html)
        assert result is not None
        assert result["a"] == 1

    def test_nested_script_tags_not_confused(self) -> None:
        """Ensure regex doesn't match other script tags."""
        html = f"""
        <script>var x = 1;</script>
        <script id="__NEXT_DATA__" type="application/json">
            {json.dumps({"data": "real"})}
        </script>
        <script>var y = 2;</script>
        """
        result = ImmunefiWebScraper._extract_next_data(html)
        assert result is not None
        assert result["data"] == "real"


# ── _parse_bounty_string ────────────────────────────────────


class TestParseBountyString:
    @pytest.mark.parametrize(
        ("input_str", "expected"),
        [
            ("250k", 250_000.0),
            ("3M", 3_000_000.0),
            ("1.5M", 1_500_000.0),
            ("500,000", 500_000.0),
            ("1000", 1000.0),
            ("5B", 5_000_000_000.0),
            ("0", 0.0),
            ("", None),
            ("notanumber", None),
            ("abcM", None),
            ("$100k", 100_000.0),  # strips $ sign via comma strip... wait let me check
        ],
    )
    def test_parse_bounty_string(self, input_str: str, expected: float | None) -> None:
        result = ImmunefiWebScraper._parse_bounty_string(input_str)
        assert result == expected

    def test_dollar_sign_handling(self) -> None:
        """$100k should parse to 100000."""
        result = ImmunefiWebScraper._parse_bounty_string("$100k")
        assert result == 100_000.0

    def test_whitespace_handling(self) -> None:
        result = ImmunefiWebScraper._parse_bounty_string("  $2.5M  ")
        assert result == 2_500_000.0


# ── _has_smart_contracts ────────────────────────────────────


class TestHasSmartContracts:
    def test_contracts_list_with_address(self) -> None:
        detail = {
            "contracts": [
                {"address": "0x" + "a" * 40},
            ],
        }
        assert ImmunefiWebScraper._has_smart_contracts(detail) is True

    def test_contracts_list_string_address(self) -> None:
        detail = {
            "contracts": ["0x" + "b" * 40],
        }
        assert ImmunefiWebScraper._has_smart_contracts(detail) is True

    def test_contracts_empty(self) -> None:
        detail = {"contracts": []}
        assert ImmunefiWebScraper._has_smart_contracts(detail) is False

    def test_assets_with_smart_contract_type(self) -> None:
        detail = {
            "assets": [
                {"type": "smart_contract", "url": "https://etherscan.io/address/0x" + "c" * 40},
            ],
        }
        assert ImmunefiWebScraper._has_smart_contracts(detail) is True

    def test_assets_with_etherscan_url(self) -> None:
        detail = {
            "assets": [
                {"type": "website", "url": "https://etherscan.io/address/0x" + "d" * 40},
            ],
        }
        assert ImmunefiWebScraper._has_smart_contracts(detail) is True

    def test_assets_no_contract(self) -> None:
        detail = {
            "assets": [
                {"type": "website", "url": "https://example.com"},
            ],
        }
        assert ImmunefiWebScraper._has_smart_contracts(detail) is False

    def test_empty_detail(self) -> None:
        assert ImmunefiWebScraper._has_smart_contracts({}) is False

    def test_none_values(self) -> None:
        detail = {"contracts": None, "assets": None}
        assert ImmunefiWebScraper._has_smart_contracts(detail) is False


# ── _extract_programs_from_next_data ────────────────────────


class TestExtractProgramsFromNextData:
    def test_extracts_from_common_field(self) -> None:
        """Should find programs in the 'programs' field of pageProps."""
        next_data = {
            "props": {
                "pageProps": {
                    "programs": [
                        {"slug": "sushi", "name": "Sushi"},
                        {"slug": "aave", "name": "Aave"},
                    ],
                },
            },
        }
        scraper = ImmunefiWebScraper()
        result = scraper._extract_programs_from_next_data(next_data)
        assert result is not None
        assert len(result) == 2
        assert result[0]["slug"] == "sushi"

    def test_returns_none_on_empty_list(self) -> None:
        """Empty list should not trigger extraction."""
        next_data = {
            "props": {
                "pageProps": {
                    "programs": [],
                },
            },
        }
        scraper = ImmunefiWebScraper()
        result = scraper._extract_programs_from_next_data(next_data)
        assert result is None

    def test_recursive_search(self) -> None:
        """Should find programs nested deeper in the data structure."""
        next_data = {
            "props": {
                "pageProps": {
                    "someNested": {
                        "results": [
                            {"slug": "compound", "name": "Compound"},
                            {"slug": "maker", "name": "MakerDAO"},
                        ],
                    },
                },
            },
        }
        scraper = ImmunefiWebScraper()
        result = scraper._extract_programs_from_next_data(next_data)
        assert result is not None
        assert len(result) >= 1

    def test_no_programs_found(self) -> None:
        next_data = {"props": {"pageProps": {"title": "Bug Bounties"}}}
        scraper = ImmunefiWebScraper()
        result = scraper._extract_programs_from_next_data(next_data)
        assert result is None
