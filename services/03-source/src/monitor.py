"""BlockMonitor — Monitor blockchain untuk kontrak baru secara real-time.

Menggunakan public RPC untuk memonitor block terbaru dan mendeteksi
contract creation transactions, lalu auto-fetch source jika terverifikasi.
"""

from __future__ import annotations

import asyncio

import httpx
import structlog

from src.detector import SourceDetector
from src.storage import EnhancedJSONStorage

log = structlog.get_logger()

# Public RPC endpoints
PUBLIC_RPCS: dict[str, str] = {
    "ethereum": "https://eth.drpc.org",
    "polygon": "https://polygon.drpc.org",
    "arbitrum": "https://arbitrum.drpc.org",
    "optimism": "https://optimism.drpc.org",
    "bsc": "https://bsc.drpc.org",
    "avalanche": "https://avalanche.drpc.org",
    "base": "https://base.drpc.org",
    "gnosis": "https://gnosis.drpc.org",
    "fantom": "https://fantom.drpc.org",
}

# Starting blocks (recent)
START_BLOCKS: dict[str, int] = {
    "ethereum": 19_500_000,
    "polygon": 50_000_000,
    "arbitrum": 200_000_000,
    "optimism": 110_000_000,
    "bsc": 35_000_000,
    "avalanche": 40_000_000,
    "base": 12_000_000,
}

POLL_INTERVAL = 12  # seconds


class BlockMonitor:
    """Monitor blockchain untuk kontrak baru secara real-time.

    Mendeteksi contract creation transactions (tx.to == None)
    dan auto-fetch source jika kontrak terverifikasi.

    Usage::

        monitor = BlockMonitor(storage, detector)
        await monitor.start(chains=["ethereum", "polygon"])
    """

    def __init__(
        self,
        storage: EnhancedJSONStorage,
        detector: SourceDetector,
    ) -> None:
        self.storage = storage
        self.detector = detector
        self.running = False
        self.last_blocks: dict[str, int] = {}
        self.contracts_found = 0
        self.contracts_fetched = 0

    async def start(self, chains: list[str] | None = None) -> None:
        """Start monitoring untuk chain tertentu.

        Args:
            chains: List chain names. Default semua chain yang didukung.
        """
        if chains is None:
            chains = list(PUBLIC_RPCS.keys())

        self.running = True

        # Initialize last blocks
        for chain in chains:
            self.last_blocks[chain] = START_BLOCKS.get(chain, 0)

        log.info("block_monitor.starting", chains=chains)

        # Create tasks untuk setiap chain
        tasks = [
            self._monitor_chain(chain)
            for chain in chains
            if chain in PUBLIC_RPCS
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self) -> None:
        """Stop monitoring."""
        self.running = False
        log.info("block_monitor.stopped", contracts_found=self.contracts_found)

    async def _monitor_chain(self, chain: str) -> None:
        """Monitor satu chain untuk contract creations."""
        rpc_url = PUBLIC_RPCS.get(chain)
        if not rpc_url:
            return

        last_block = self.last_blocks.get(chain, START_BLOCKS.get(chain, 0))

        async with httpx.AsyncClient(timeout=30.0) as client:
            while self.running:
                try:
                    # Get current block number
                    payload = {
                        "jsonrpc": "2.0",
                        "method": "eth_blockNumber",
                        "params": [],
                        "id": 1,
                    }
                    resp = await client.post(rpc_url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    current_block = int(data.get("result", "0x0"), 16)

                    if current_block > last_block:
                        # Process new blocks (max 10 blocks at a time)
                        end_block = min(current_block, last_block + 10)
                        for block_num in range(last_block + 1, end_block + 1):
                            await self._process_block(client, chain, block_num, rpc_url)

                        self.last_blocks[chain] = end_block

                    await asyncio.sleep(POLL_INTERVAL)

                except Exception as exc:
                    log.warning(
                        "block_monitor.error",
                        chain=chain,
                        error=str(exc),
                    )
                    await asyncio.sleep(60)  # Back off on error

    async def _process_block(
        self,
        client: httpx.AsyncClient,
        chain: str,
        block_num: int,
        rpc_url: str,
    ) -> None:
        """Process a single block for contract creations."""
        try:
            # Get block with full transactions
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_getBlockByNumber",
                "params": [hex(block_num), True],
                "id": 1,
            }
            resp = await client.post(rpc_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            block = data.get("result", {})

            transactions = block.get("transactions", [])

            for tx in transactions:
                # Contract creation: to is None or "0x"
                tx_to = tx.get("to")
                if tx_to is None or tx_to == "0x":
                    tx_hash = tx.get("hash", "")
                    # Get transaction receipt for contract address
                    receipt_payload = {
                        "jsonrpc": "2.0",
                        "method": "eth_getTransactionReceipt",
                        "params": [tx_hash],
                        "id": 1,
                    }
                    receipt_resp = await client.post(rpc_url, json=receipt_payload)
                    receipt_data = receipt_resp.json()
                    receipt = receipt_data.get("result", {})

                    contract_address = receipt.get("contractAddress")
                    if contract_address:
                        self.contracts_found += 1
                        log.info(
                            "block_monitor.new_contract",
                            chain=chain,
                            address=contract_address,
                            block=block_num,
                            tx=tx_hash,
                        )

                        # Auto-fetch source after delay (for verification)
                        # Schedule async fetch
                        asyncio.create_task(
                            self._try_fetch(chain, contract_address)
                        )

        except Exception as exc:
            log.warning(
                "block_monitor.process_error",
                chain=chain,
                block=block_num,
                error=str(exc),
            )

    async def _try_fetch(self, chain: str, address: str) -> None:
        """Coba fetch source untuk kontrak baru setelah delay."""
        # Tunggu beberapa detik agar validator sempat verify
        await asyncio.sleep(30)

        log.info(
            "block_monitor.try_fetch",
            chain=chain,
            address=address,
        )

        result = await self.detector.fetch(chain, address)
        if result:
            self.contracts_fetched += 1
            log.info(
                "block_monitor.fetch_success",
                chain=chain,
                address=address,
                provider=result.provider,
            )
