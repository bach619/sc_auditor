"""Shared fixtures for 02-immunefi tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def program_data() -> dict[str, Any]:
    """Sample program data resembling GitHub mirror format."""
    return {
        "id": "sushi",
        "slug": "sushi",
        "name": "Sushi",
        "chains": ["Ethereum", "Polygon", "Arbitrum"],
        "max_bounty": 2500000.0,
        "min_bounty": 5000.0,
        "currency": "USD",
        "status": "active",
        "project_url": "https://sushi.com",
        "logo": "/logos/sushi.png",
        "description": "Sushi is a DeFi protocol.",
        "tags": ["defi", "amm"],
        "updated_at": "2025-06-01T12:00:00Z",
        "assets": [
            {
                "type": "smart_contract",
                "url": "https://etherscan.io/address/0x6B3595068778DD592e39A122f4f5a5cF09C90fE2",
                "description": "SushiSwap Router",
            },
            {
                "type": "smart_contract",
                "url": "https://polygonscan.com/address/0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
                "description": "SushiSwap Polygon Router",
            },
        ],
        "project_urls": ["https://github.com/sushiswap"],
    }


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Temporary directory for storage tests."""
    d = tmp_path / "immunefi_data"
    d.mkdir(parents=True, exist_ok=True)
    return d
