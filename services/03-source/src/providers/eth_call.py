"""EthCallProvider — Fetch source via direct RPC (eth_call + eth_getCode).

Provider terakhir — fallback kalau semua provider explorer gagal.
Menggunakan RPC publik untuk fetch bytecode on-chain dan mencoba
mencocokkan dengan kontrak yang sudah dikenal (OpenZeppelin, dll).

Catatan: Ini adalah BEST-EFFORT provider. Tidak bisa fetch full source
seperti explorer, tapi bisa dapat bytecode, ABI minimal, dan mencoba
identifikasi kontrak terkenal.
"""

from __future__ import annotations

import hashlib

import httpx
import structlog

from src.models import SourceResult

log = structlog.get_logger()

# Public RPC endpoints (free tier)
PUBLIC_RPCS: dict[str, str] = {
    "ethereum": "https://eth.drpc.org",
    "arbitrum": "https://arbitrum.drpc.org",
    "optimism": "https://optimism.drpc.org",
    "polygon": "https://polygon.drpc.org",
    "bsc": "https://bsc.drpc.org",
    "avalanche": "https://avalanche.drpc.org",
    "base": "https://base.drpc.org",
    "gnosis": "https://gnosis.drpc.org",
    "fantom": "https://fantom.drpc.org",
    "celo": "https://celo.drpc.org",
    "linea": "https://linea.drpc.org",
    "scroll": "https://scroll.drpc.org",
    "blast": "https://blast.drpc.org",
}

# Known contract templates (bytecode hash → template info)
# Ini akan di-populate secara bertahap
KNOWN_TEMPLATES: dict[str, dict[str, str]] = {}


class EthCallProvider:
    """Source provider via direct RPC (eth_call / eth_getCode).

    Best-effort: fetch bytecode on-chain, simpan sebagai hex.
    Tidak bisa memberikan full Solidity source, tapi menyediakan
    bytecode untuk verifikasi dan analisis lebih lanjut.

    Priority: rendah (fallback terakhir).
    """

    name = "eth_call"

    async def fetch(self, chain: str, address: str) -> SourceResult | None:
        """Fetch on-chain bytecode via eth_getCode.

        Args:
            chain: Blockchain name (harus ada di PUBLIC_RPCS).
            address: Contract address.

        Returns:
            SourceResult dengan bytecode sebagai source, atau None.
        """
        rpc_url = PUBLIC_RPCS.get(chain.lower())
        if not rpc_url:
            log.warning("eth_call.unsupported_chain", chain=chain)
            return None

        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getCode",
            "params": [address, "latest"],
            "id": 1,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            log.info("eth_call.fetch", chain=chain, address=address)
            try:
                resp = await client.post(rpc_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                log.warning("eth_call.request_failed", chain=chain, address=address, error=str(exc))
                return None

        bytecode = data.get("result", "")
        if not bytecode or bytecode in ("0x", "0x0"):
            log.info("eth_call.no_bytecode", chain=chain, address=address)
            return None

        # Check known templates
        bytecode_hash = hashlib.sha256(bytecode.encode()).hexdigest()
        template = KNOWN_TEMPLATES.get(bytecode_hash)

        sources: dict[str, str] = {
            "bytecode.hex": bytecode,
            "bytecode_hash.txt": bytecode_hash,
        }

        if template:
            sources["README.md"] = (
                f"# Known Contract Template\n\n"
                f"This bytecode matches a known template: {template.get('name', 'Unknown')}\n"
                f"Compiler: {template.get('compiler', 'Unknown')}\n"
            )
            compiler_version = template.get("compiler", "")
        else:
            compiler_version = ""

        return SourceResult(
            sources=sources,
            compiler_version=compiler_version,
            license=None,
            provider=self.name,
            constructor_args=None,
        )
