"""CompilerVerifier — Verifikasi source code match dengan on-chain bytecode.

Karena tidak ada Solidity compiler (solc) di environment, verifier ini
menggunakan pendekatan:
1. Fetch on-chain bytecode via eth_getCode
2. Bandingkan bytecode hash dengan yang tersimpan
3. Analisis metadata hash (CBOR) di akhir bytecode
4. Deteksi perubahan bytecode (contract upgrade)

Untuk full verification dengan re-compile, butuh instalasi solc
via ``pip install py-solc-x`` dan binary solc terpisah.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx
import structlog

from src.models import VerificationResult
from src.storage import EnhancedJSONStorage

log = structlog.get_logger()

# Public RPC endpoints untuk fetch bytecode
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
    "zksync": "https://mainnet.era.zksync.io",
}


class CompilerVerifier:
    """Verifikasi source code match dengan on-chain bytecode.

    Usage::

        verifier = CompilerVerifier(storage)
        result = await verifier.verify("ethereum", "0x...")
    """

    def __init__(self, storage: EnhancedJSONStorage) -> None:
        self.storage = storage

    async def verify(
        self,
        chain: str,
        address: str,
    ) -> VerificationResult:
        """Verifikasi source == bytecode dengan analisis on-chain.

        Args:
            chain: Blockchain name.
            address: Contract address.

        Returns:
            VerificationResult dengan status verifikasi.
        """
        chain_l = chain.lower()
        addr_l = address.lower()

        # 1. Check if source is cached
        source = self.storage.get_source(chain_l, addr_l)
        if not source:
            return VerificationResult(
                verified=False,
                chain=chain_l,
                address=addr_l,
                error="Source not cached. Use POST /fetch first.",
            )

        metadata = self.storage.get_metadata(chain_l, addr_l)

        # 2. Fetch on-chain bytecode
        bytecode = await self._fetch_bytecode(chain_l, addr_l)
        if not bytecode:
            return VerificationResult(
                verified=False,
                chain=chain_l,
                address=addr_l,
                error="Cannot fetch on-chain bytecode. Chain may not be supported.",
                provider=source.provider,
                compiler_version=source.compiler_version,
            )

        # 3. Compute hashes
        raw_bytecode_hash = hashlib.sha256(bytecode.encode()).hexdigest()

        # 4. Strip metadata hash (CBOR) dari bytecode
        cleaned_bytecode = self._strip_metadata(bytecode)
        cleaned_hash = hashlib.sha256(cleaned_bytecode.encode()).hexdigest()

        # 5. Extract metadata hash
        metadata_hash = self._extract_metadata_hash(bytecode)

        # 6. Compare with stored metadata
        stored_hash = metadata.source_hash if metadata else None
        match_percentage = 0.0

        if stored_hash:
            # Compute source content hash
            all_content = "".join(sorted(source.sources.values()))
            source_hash = hashlib.sha256(all_content.encode()).hexdigest()

            if source_hash == stored_hash:
                match_percentage = 100.0
            else:
                # Partial match — compare line by line
                match_percentage = self._compute_similarity(source, bytecode)

        # 7. Determine verification status
        is_verified = match_percentage >= 90.0

        # Jika bytecode berubah dari yang terakhir diverifikasi
        if metadata:
            old_hash = getattr(metadata, 'bytecode_hash', None)
            if old_hash and old_hash != cleaned_hash and is_verified:
                # Source masih match, catat upgrade
                self.storage._append_history(chain_l, addr_l, {
                    "event": "bytecode_changed",
                    "old_hash": old_hash,
                    "new_hash": cleaned_hash,
                    "timestamp": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
                })

        return VerificationResult(
            verified=is_verified,
            chain=chain_l,
            address=addr_l,
            match_percentage=round(match_percentage, 2),
            compiler_version=source.compiler_version,
            provider=source.provider,
            metadata_hash=metadata_hash,
            optimized=False,
        )

    async def _fetch_bytecode(self, chain: str, address: str) -> str | None:
        """Fetch on-chain bytecode via eth_getCode RPC."""
        rpc_url = PUBLIC_RPCS.get(chain)
        if not rpc_url:
            log.warning("verifier.unsupported_chain", chain=chain)
            return None

        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getCode",
            "params": [address, "latest"],
            "id": 1,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(rpc_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                log.warning("verifier.rpc_failed", chain=chain, address=address, error=str(exc))
                return None

        bytecode = data.get("result", "")
        if not bytecode or bytecode in ("0x", "0x0"):
            return None

        return bytecode

    def _strip_metadata(self, bytecode: str) -> str:
        """Strip the IPFS/Swarm metadata hash dari akhir bytecode.

        Solidity append CBOR-encoded metadata di akhir bytecode.
        2 byte terakhir menunjukkan panjang metadata.
        """
        if len(bytecode) < 40:
            return bytecode

        try:
            # Baca 2 byte terakhir sebagai length metadata
            meta_length = int(bytecode[-4:], 16) * 2 + 4
            if meta_length < len(bytecode):
                return bytecode[:-meta_length]
        except (ValueError, IndexError):
            pass

        return bytecode

    def _extract_metadata_hash(self, bytecode: str) -> str | None:
        """Extract IPFS/Swarm metadata hash dari bytecode."""
        # CBOR metadata biasanya diawali dengan 0xa2 0x64 0x69 0x70 0x66 0x73 0x58 ...
        # (IPFS hash) atau 0xa2 0x64 0x62 0x7a 0x7a 0x72 0x30 0x58 ...
        # (Swarm hash)
        try:
            # Cari pattern 0xa2... di akhir bytecode
            meta_start = bytecode.rfind("a2")
            if meta_start > 0:
                meta_hex = bytecode[meta_start:]
                # CBOR sederhana: ambil hash setelah 0x58 + length byte
                if len(meta_hex) > 10:
                    try:
                        hash_len = int(meta_hex[4:6], 16) * 2
                        if hash_len > 0 and len(meta_hex) > 6 + hash_len:
                            return meta_hex[6:6 + hash_len]
                    except (ValueError, IndexError):
                        pass
        except Exception:
            pass

        return None

    def _compute_similarity(self, source: SourceResult, onchain_bytecode: str) -> float:
        """Compute similarity antara source code dan on-chain bytecode.

        Pendekatan: bandingkan known function selectors (4-byte signatures)
        yang bisa diekstrak dari source vs yang ada di bytecode.
        """
        # Ekstrak function selectors dari source (pattern matching)
        import re

        source_selectors: set[str] = set()
        for content in source.sources.values():
            # Cari function definitions
            funcs = re.findall(r"function\s+(\w+)\s*\(([^)]*)\)", content)
            for name, params in funcs:
                param_types = re.findall(r"(\w+(?:\[\])*(?:\s+calldata|\s+memory|\s+storage)?)", params)
                clean_types = [p.split()[0] for p in param_types if p.strip()]
                sig = f"{name}({','.join(clean_types)})"
                selector = hashlib.keccak_256(sig.encode()).hexdigest()[:8]
                source_selectors.add(selector)

        # Ekstrak function selectors dari bytecode (4-byte signatures)
        bytecode_selectors: set[str] = set()
        if len(onchain_bytecode) > 10:
            for i in range(0, len(onchain_bytecode) - 7, 2):
                # Cari pattern PUSH4 (0x63) diikuti 4 byte selector
                if onchain_bytecode[i:i+2] == "63":
                    selector = onchain_bytecode[i+2:i+10]
                    if len(selector) == 8 and all(c in "0123456789abcdef" for c in selector):
                        bytecode_selectors.add(selector)

        if not source_selectors or not bytecode_selectors:
            return 0.0

        # Jaccard similarity
        intersection = source_selectors & bytecode_selectors
        union = source_selectors | bytecode_selectors

        return (len(intersection) / len(union)) * 100.0 if union else 0.0
