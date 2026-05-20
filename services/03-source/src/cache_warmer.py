"""CacheWarmer — Proaktif fetch source untuk kontrak-kontrak terkenal.

Memanaskan cache dengan melakukan fetch di muka untuk kontrak-kontrak
yang dikenal (DeFi blue chips, recently hacked, high TVL) sehingga
saat dibutuhkan sudah tersedia tanpa delay.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from src.models import CacheWarmResult
from src.storage import EnhancedJSONStorage
from src.detector import SourceDetector

log = structlog.get_logger()

# DefiLlama API untuk fetch kontrak TVL tinggi
DEFILLAMA_API = "https://api.defillama.com"

# Known high-value contracts
KNOWN_CONTRACTS: dict[str, list[dict[str, str]]] = {
    "defi_blue_chips": [
        # Uniswap
        {"chain": "ethereum", "address": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"},
        {"chain": "ethereum", "address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"},
        # Aave
        {"chain": "ethereum", "address": "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9"},
        # Compound
        {"chain": "ethereum", "address": "0xc00e94Cb662C3520282E6f5717214004A7f26888"},
        # MakerDAO
        {"chain": "ethereum", "address": "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2"},
        # Lido
        {"chain": "ethereum", "address": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"},
        # Curve
        {"chain": "ethereum", "address": "0xD533a949740bb3306d119CC777fa900bA034cd52"},
        # Chainlink
        {"chain": "ethereum", "address": "0x514910771AF9Ca656af840dff83E8264EcF986CA"},
    ],
    "recently_hacked": [],  # Auto-populated
    "high_tvl": [],         # Auto-populated from DefiLlama
}

BATCH_SIZE = 10
RATE_LIMIT_DELAY = 1.0  # seconds between batches


class CacheWarmer:
    """Proaktif fetch source untuk kontrak-kontrak terkenal.

    Usage::

        warmer = CacheWarmer(storage, detector)
        result = await warmer.warm("defi_blue_chips")
    """

    def __init__(
        self,
        storage: EnhancedJSONStorage,
        detector: SourceDetector,
    ) -> None:
        self.storage = storage
        self.detector = detector

    async def warm(self, category: str = "defi_blue_chips") -> CacheWarmResult:
        """Warm cache untuk kategori tertentu.

        Args:
            category: Nama kategori (defi_blue_chips, recently_hacked, high_tvl).

        Returns:
            CacheWarmResult dengan statistik.
        """
        start_time = time.monotonic()

        contracts = KNOWN_CONTRACTS.get(category, [])

        # Auto-populate high_tvl from DefiLlama
        if category == "high_tvl":
            tvl_contracts = await self._fetch_high_tvl_contracts()
            contracts.extend(tvl_contracts)

        log.info(
            "cache_warm.starting",
            category=category,
            count=len(contracts),
        )

        attempted = 0
        succeeded = 0
        failed = 0
        errors: list[str] = []

        for i in range(0, len(contracts), BATCH_SIZE):
            batch = contracts[i:i + BATCH_SIZE]
            attempted += len(batch)

            tasks = [
                self._fetch_if_missing(c["chain"], c["address"])
                for c in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if result is True:
                    succeeded += 1
                elif isinstance(result, str):
                    failed += 1
                    errors.append(result)
                elif result is False:
                    failed += 1

            if i + BATCH_SIZE < len(contracts):
                await asyncio.sleep(RATE_LIMIT_DELAY)

            log.info(
                "cache_warm.progress",
                category=category,
                progress=f"{i + len(batch)}/{len(contracts)}",
                succeeded=succeeded,
                failed=failed,
            )

        duration = time.monotonic() - start_time

        log.info(
            "cache_warm.complete",
            category=category,
            attempted=attempted,
            succeeded=succeeded,
            failed=failed,
            duration=round(duration, 1),
        )

        return CacheWarmResult(
            category=category,
            attempted=attempted,
            succeeded=succeeded,
            failed=failed,
            errors=errors[:10],  # Limit error reporting
            duration_seconds=round(duration, 1),
        )

    async def _fetch_if_missing(self, chain: str, address: str) -> bool | str:
        """Fetch source jika belum ada di cache."""
        try:
            if self.storage.exists(chain, address):
                return True  # Already cached

            result = await self.detector.fetch(chain, address)
            if result:
                return True
            return False
        except Exception as exc:
            return str(exc)

    async def _fetch_high_tvl_contracts(self) -> list[dict[str, str]]:
        """Fetch high TVL contracts from DefiLlama."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{DEFILLAMA_API}/protocols",
                    params={"limit": 50},
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                contracts = []
                for protocol in data[:20]:  # Top 20 protocols
                    # Try to get chain + address from protocol data
                    chain = (protocol.get("chains") or ["ethereum"])[0]
                    # Note: actual contract addresses require per-protocol lookup
                    # This is a simplified version
                    pass

        except Exception as exc:
            log.warning("cache_warm.defillama_error", error=str(exc))

        return []
