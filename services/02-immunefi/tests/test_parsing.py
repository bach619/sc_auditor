"""Tests for parsing helpers — ImmunefiScraper.parse_contracts."""

from __future__ import annotations

from typing import Any

import pytest

from src.scraper import ImmunefiScraper


# ── Fixtures ────────────────────────────────────────────────


def detail_with_assets(assets: list[dict]) -> dict[str, Any]:
    """Build a program detail dict with the given assets."""
    return {
        "id": "test",
        "slug": "test",
        "name": "Test Program",
        "assets": assets,
    }


# ── Smart Contract Extraction ───────────────────────────────


class TestParseContracts:
    def test_empty_assets(self) -> None:
        detail = detail_with_assets([])
        assert ImmunefiScraper.parse_contracts(detail) == []

    def test_missing_assets_key(self) -> None:
        assert ImmunefiScraper.parse_contracts({}) == []

    def test_non_dict_assets(self) -> None:
        detail = detail_with_assets(["not-a-dict"])  # type: ignore[list-item]
        assert ImmunefiScraper.parse_contracts(detail) == []

    def test_contract_with_address_field(self) -> None:
        detail = detail_with_assets([
            {
                "type": "smart_contract",
                "address": "0x6B3595068778DD592e39A122f4f5a5cF09C90fE2",
                "url": "https://etherscan.io/address/0x6B3595068778DD592e39A122f4f5a5cF09C90fE2",
                "description": "SushiSwap Router",
            },
        ])
        contracts = ImmunefiScraper.parse_contracts(detail)
        assert len(contracts) == 1
        assert contracts[0]["address"] == "0x6B3595068778DD592e39A122f4f5a5cF09C90fE2"
        assert contracts[0]["chain"] == "ethereum"
        assert contracts[0]["name"] == "SushiSwap Router"

    def test_contract_address_from_url_fallback(self) -> None:
        """When address field is empty, must extract from URL."""
        detail = detail_with_assets([
            {
                "type": "smart_contract",
                "address": "",
                "url": "https://etherscan.io/address/0x6B3595068778DD592e39A122f4f5a5cF09C90fE2",
                "description": "Router",
            },
        ])
        contracts = ImmunefiScraper.parse_contracts(detail)
        assert len(contracts) == 1
        assert contracts[0]["address"] == "0x6B3595068778DD592e39A122f4f5a5cF09C90fE2"

    def test_chain_detection_polygon(self) -> None:
        detail = detail_with_assets([
            {
                "type": "smart_contract",
                "address": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
                "url": "https://polygonscan.com/address/0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
            },
        ])
        contracts = ImmunefiScraper.parse_contracts(detail)
        assert contracts[0]["chain"] == "polygon"

    def test_chain_detection_bsc(self) -> None:
        detail = detail_with_assets([
            {
                "type": "smart_contract",
                "address": "0x0000000000000000000000000000000000000001",
                "url": "https://bscscan.com/address/0x0000000000000000000000000000000000000001",
            },
        ])
        contracts = ImmunefiScraper.parse_contracts(detail)
        assert contracts[0]["chain"] == "bsc"

    def test_chain_detection_arbitrum(self) -> None:
        detail = detail_with_assets([
            {
                "type": "smart_contract",
                "address": "0x0000000000000000000000000000000000000002",
                "url": "https://arbiscan.io/address/0x0000000000000000000000000000000000000002",
            },
        ])
        contracts = ImmunefiScraper.parse_contracts(detail)
        assert contracts[0]["chain"] == "arbitrum"

    def test_chain_detection_avalanche(self) -> None:
        detail = detail_with_assets([
            {
                "type": "smart_contract",
                "address": "0x0000000000000000000000000000000000000003",
                "url": "https://snowtrace.io/address/0x0000000000000000000000000000000000000003",
            },
        ])
        contracts = ImmunefiScraper.parse_contracts(detail)
        assert contracts[0]["chain"] == "avalanche"

    def test_chain_detection_optimism(self) -> None:
        detail = detail_with_assets([
            {
                "type": "smart_contract",
                "address": "0x0000000000000000000000000000000000000004",
                "url": "https://optimistic.etherscan.io/address/0x0000000000000000000000000000000000000004",
            },
        ])
        contracts = ImmunefiScraper.parse_contracts(detail)
        assert contracts[0]["chain"] == "optimism"

    def test_chain_detection_unknown_explorer(self) -> None:
        detail = detail_with_assets([
            {
                "type": "smart_contract",
                "address": "0x0000000000000000000000000000000000000005",
                "url": "https://customscan.xyz/address/0x0000000000000000000000000000000000000005",
            },
        ])
        contracts = ImmunefiScraper.parse_contracts(detail)
        assert contracts[0]["chain"] == "unknown"

    def test_non_smart_contract_types_excluded(self) -> None:
        """Only type='smart_contract' should be included."""
        detail = detail_with_assets([
            {"type": "smart_contract", "address": "0x" + "a" * 40, "url": "https://etherscan.io/address/" + "a" * 40},
            {"type": "website", "url": "https://example.com"},
            {"type": "documentation", "url": "https://docs.example.com"},
            {"type": "social", "url": "https://twitter.com/test"},
        ])
        contracts = ImmunefiScraper.parse_contracts(detail)
        assert len(contracts) == 1

    def test_duplicate_address_deduplicated(self) -> None:
        addr = "0x" + "b" * 40
        detail = detail_with_assets([
            {"type": "smart_contract", "address": addr, "url": f"https://etherscan.io/address/{addr}"},
            {"type": "smart_contract", "address": addr, "url": f"https://etherscan.io/address/{addr}"},
        ])
        contracts = ImmunefiScraper.parse_contracts(detail)
        assert len(contracts) == 1

    def test_short_address_rejected(self) -> None:
        detail = detail_with_assets([
            {"type": "smart_contract", "address": "0xshort", "url": "https://etherscan.io/address/0xshort"},
        ])
        contracts = ImmunefiScraper.parse_contracts(detail)
        assert len(contracts) == 0

    def test_contracts_format_direct_list(self) -> None:
        """Handle format where detail has a 'contracts' list with address/chain/name."""
        detail = {
            "id": "test",
            "slug": "test",
            "name": "Test",
            "contracts": [
                {"address": "0x" + "c" * 40, "chain": "Ethereum", "name": "Main"},
                {"address": "0x" + "d" * 40, "chain": "Polygon", "name": "Side"},
            ],
        }
        contracts = ImmunefiScraper.parse_contracts(detail)
        assert len(contracts) == 2

    def test_type_case_insensitive(self) -> None:
        """'Smart_Contract' and 'SMART_CONTRACT' should both match."""
        detail = detail_with_assets([
            {"type": "Smart_Contract", "address": "0x" + "e" * 40, "url": "https://etherscan.io/address/" + "e" * 40},
        ])
        contracts = ImmunefiScraper.parse_contracts(detail)
        assert len(contracts) == 1
