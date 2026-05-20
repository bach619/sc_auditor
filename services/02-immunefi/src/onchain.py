"""OnChainMonitor — Real-time on-chain data untuk bounty programs.

TVL dari DeFiLlama + Web3 event listener (optional).

Sources:
  - DeFiLlama: https://api.llama.fi/ (TVL per protocol)
  - Web3: RPC calls via web3.py (on-chain events, optional)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog

from src.models import Program
from src.storage import EnhancedJSONStorage

log = structlog.get_logger()

DEFILLAMA_API = "https://api.llama.fi"
WEB3_RPC_URL = os.getenv("WEB3_RPC_URL", "")

# Immunefi known contract addresses (configurable via env)
IMMUNEFI_CONTRACTS_RAW = os.getenv(
    "IMMUNEFI_CONTRACTS",
    '{"ethereum": "0x0000000000000000000000000000000000000000"}',
)
try:
    IMMUNEFI_CONTRACTS: dict[str, str] = json.loads(IMMUNEFI_CONTRACTS_RAW)
except Exception:
    IMMUNEFI_CONTRACTS = {"ethereum": "0x0000000000000000000000000000000000000000"}

# Event signatures we care about
EVENT_SIGNATURES: dict[str, list[str]] = {
    "BountyCreated(uint256,address,uint256,address,uint256)": [
        "bountyId", "publisher", "bountyAmount", "token", "programId",
    ],
    "BountyClaimed(uint256,address,address,uint256)": [
        "bountyId", "claimant", "payoutToken", "payoutAmount",
    ],
    "BountyCancelled(uint256)": ["bountyId"],
    "ProgramUpdated(bytes32)": ["programId"],
}

_TOPIC0_CACHE: dict[str, tuple[str, list[str]]] | None = None


def _get_topic0_map() -> dict[str, tuple[str, list[str]]]:
    """Lazy-build TOPIC0_MAP — only imports eth_hash when needed."""
    global _TOPIC0_CACHE
    if _TOPIC0_CACHE is not None:
        return _TOPIC0_CACHE

    try:
        from eth_hash.auto import keccak  # noqa: PLC0415
    except ImportError:
        _TOPIC0_CACHE = {}
        return _TOPIC0_CACHE

    result: dict[str, tuple[str, list[str]]] = {}
    for sig, params in EVENT_SIGNATURES.items():
        topic0 = "0x" + keccak(sig.encode()).hex()
        name = sig.split("(")[0]
        result[topic0] = (name, params)
    _TOPIC0_CACHE = result
    return result


class Web3Available:
    """Lazy Web3 check — only import if configured."""

    _available: bool | None = None
    _w3: object = None

    @classmethod
    def is_available(cls) -> bool:
        if cls._available is None:
            if not WEB3_RPC_URL:
                cls._available = False
            else:
                try:
                    from web3 import Web3  # noqa: PLC0415
                    cls._w3 = Web3(Web3.HTTPProvider(WEB3_RPC_URL))
                    cls._available = cls._w3.is_connected()
                except Exception:
                    cls._available = False
        return cls._available

    @classmethod
    def get_w3(cls):
        if cls.is_available():
            return cls._w3
        return None


class OnChainMonitor:
    """Monitor on-chain: TVL (DeFiLlama) + events (Web3).

    Usage:
        monitor = OnChainMonitor(storage)
        tvl = await monitor.fetch_tvl("euler-finance")
        events = await monitor.poll_events()
        slug_events = monitor.get_events_for_program("euler-finance")
    """

    def __init__(
        self,
        storage: EnhancedJSONStorage,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.storage = storage
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    # ── Cache Helpers ───────────────────────────────────────

    def _load_json_index(self, name: str) -> dict[str, Any]:
        path = self.storage.data_dir / "indexes" / name
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
        return {}

    def _save_json_index(self, name: str, data: dict) -> None:
        path = self.storage.data_dir / "indexes" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            log.warning("onchain.index_save_error", index=name, error=str(e)[:100])

    # ── TVL (existing) ──────────────────────────────────────

    def _get_tvl_cache(self) -> dict[str, Any]:
        return self._load_json_index("tvl_cache.json")

    def _save_tvl_cache(self, cache: dict) -> None:
        self._save_json_index("tvl_cache.json", cache)

    async def fetch_tvl(self, protocol_slug: str) -> dict[str, Any]:
        cache = self._get_tvl_cache()
        cached = cache.get(protocol_slug)
        if cached and isinstance(cached, dict):
            try:
                cached_at = datetime.fromisoformat(cached["_cached_at"])
                if cached_at.tzinfo is None:
                    cached_at = cached_at.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - cached_at < timedelta(hours=1):
                    return cached
            except Exception:
                pass

        client = await self._get_client()
        log.info("onchain.fetch_tvl", protocol=protocol_slug)

        try:
            resp = await client.get(
                f"{DEFILLAMA_API}/protocol/{protocol_slug}", timeout=15.0,
            )
            if resp.status_code == 404:
                return {"slug": protocol_slug, "tvl": None, "error": "not_found"}
            resp.raise_for_status()
            data = resp.json()

            tvl_data = {
                "slug": protocol_slug,
                "name": data.get("name", protocol_slug),
                "tvl": data.get("tvl"),
                "current_tvl": data.get("currentChainTvls"),
                "change_1d": data.get("change_1d"),
                "change_7d": data.get("change_7d"),
                "chain": data.get("chain"),
                "chains": data.get("chains", []),
                "symbol": data.get("symbol"),
                "description": (data.get("description") or "")[:300],
                "url": data.get("url", ""),
                "logo": data.get("logo", ""),
                "audit_note": data.get("audit_note", ""),
                "audit_links": data.get("audit_links", []),
                "twitter": data.get("twitter", ""),
                "github": data.get("github", ""),
                "category": data.get("category", ""),
                "_cached_at": datetime.now(timezone.utc).isoformat(),
            }

            cache[protocol_slug] = tvl_data
            self._save_tvl_cache(cache)
            return tvl_data

        except httpx.TimeoutException:
            log.warning("onchain.tvl_timeout", protocol=protocol_slug)
            return cached if cached else {
                "slug": protocol_slug, "tvl": None, "error": "timeout",
            }
        except Exception as e:
            log.warning("onchain.tvl_error", protocol=protocol_slug, error=str(e)[:100])
            return {"slug": protocol_slug, "tvl": None, "error": str(e)[:100]}

    async def fetch_all_tvl(
        self, programs: dict[str, Program], max_programs: int = 20,
    ) -> list[dict[str, Any]]:
        results = []
        count = 0
        for slug, prog in programs.items():
            if count >= max_programs:
                break
            if not prog.project_url:
                continue
            protocol = self._extract_protocol_slug(prog)
            if not protocol:
                continue
            tvl = await self.fetch_tvl(protocol)
            tvl["program_slug"] = slug
            tvl["program_name"] = prog.name
            results.append(tvl)
            count += 1
        return results

    def _extract_protocol_slug(self, program: Program) -> str | None:
        url = program.project_url or ""
        name = program.name or ""
        if "defillama.com" in url:
            parts = url.rstrip("/").split("/")
            if parts:
                return parts[-1]
        if "github.com" in url:
            parts = url.rstrip("/").split("/")
            if len(parts) >= 2:
                return parts[-1].lower()
        return name.lower().replace(" ", "-").replace("_", "-") or None

    def get_tvl_stats(self) -> dict[str, Any]:
        cache = self._get_tvl_cache()
        total = len(cache)
        with_tvl = sum(
            1 for v in cache.values()
            if isinstance(v, dict) and v.get("tvl") is not None
        )
        total_tvl = sum(
            v["tvl"] for v in cache.values()
            if isinstance(v, dict) and v.get("tvl") is not None
        )
        return {
            "total_cached": total,
            "with_tvl": with_tvl,
            "total_tvl_usd": round(total_tvl, 2),
            "average_tvl": round(total_tvl / with_tvl, 2) if with_tvl else 0,
        }

    # ── Web3 Event Listener ─────────────────────────────────

    def is_web3_available(self) -> bool:
        """Cek apakah Web3 RPC tersedia dan terkonfigurasi."""
        return Web3Available.is_available()

    async def poll_events(self) -> list[dict[str, Any]]:
        """Poll on-chain events dari Immunefi contracts.

        Memeriksa block terbaru untuk event yang match dengan
        EVENT_SIGNATURES. Event disimpan di indexes/onchain_events.json.

        Returns list of new events found in this poll cycle.
        """
        if not self.is_web3_available():
            log.info("onchain.web3_not_available")
            return []

        w3 = Web3Available.get_w3()
        events = self._load_json_index("onchain_events.json")
        last_block_key = "_last_block"
        from_block = events.get(last_block_key, 0)
        if not isinstance(from_block, int):
            from_block = 0

        try:
            latest = w3.eth.block_number
        except Exception as e:
            log.warning("onchain.poll_block_error", error=str(e)[:100])
            return []

        if from_block >= latest:
            return []  # No new blocks

        new_events: list[dict] = []
        to_block = min(from_block + 500, latest)

        for chain, contract_addr in IMMUNEFI_CONTRACTS.items():
            if contract_addr == "0x0000000000000000000000000000000000000000":
                continue

            address_checksum = w3.to_checksum_address(contract_addr)

            topic0_map = _get_topic0_map()
            if not topic0_map:
                log.info("onchain.no_topic0_map_no_eth_hash")
                continue

            for topic0, (event_name, param_names) in topic0_map.items():
                try:
                    logs = w3.eth.get_logs({
                        "address": address_checksum,
                        "fromBlock": from_block,
                        "toBlock": to_block,
                        "topics": [topic0],
                    })

                    for log_entry in logs:
                        decoded = self._decode_event(
                            w3, log_entry, event_name, param_names,
                        )
                        decoded["chain"] = chain
                        decoded["contract_address"] = contract_addr
                        decoded["block_number"] = log_entry.get("blockNumber", 0)
                        decoded["transaction_hash"] = log_entry.get(
                            "transactionHash", b""
                        ).hex() if log_entry.get("transactionHash") else ""

                        event_id = (
                            f"{chain}_{decoded['block_number']}_"
                            f"{decoded['transaction_hash'][:16]}"
                        )
                        if event_id not in events or last_block_key in event_id:
                            events[event_id] = decoded
                            new_events.append(decoded)
                            log.info(
                                "onchain.event_detected",
                                chain=chain,
                                event=event_name,
                                tx=decoded["transaction_hash"][:16],
                            )

                except Exception as e:
                    log.warning(
                        "onchain.poll_log_error",
                        chain=chain, event=event_name, error=str(e)[:100],
                    )

        events[last_block_key] = to_block
        self._save_json_index("onchain_events.json", events)

        log.info(
            "onchain.poll_complete",
            from_block=from_block,
            to_block=to_block,
            new_events=len(new_events),
        )
        return new_events

    def _decode_event(
        self,
        w3: Any,
        log_entry: dict,
        event_name: str,
        param_names: list[str],
    ) -> dict[str, Any]:
        """Decode raw event log ke dict yang readable."""
        result: dict[str, Any] = {
            "event": event_name,
            "block_timestamp": None,  # would need eth_getBlockByNumber
        }

        topics = log_entry.get("topics", [])
        data_hex = log_entry.get("data", "0x")

        # topics[0] = event signature hash
        # topics[1+] = indexed parameters
        indexed_count = 0
        for i, name in enumerate(param_names):
            topic_idx = i + 1  # skip topic0
            if topic_idx < len(topics):
                raw = topics[topic_idx]
                if isinstance(raw, bytes):
                    raw = "0x" + raw.hex()
                result[name] = raw
                indexed_count += 1
            else:
                break

        # Non-indexed params from data field
        non_indexed = param_names[indexed_count:]
        if non_indexed and data_hex and data_hex != "0x":
            try:
                decoded_data = w3.codec.decode_abi(
                    ["uint256"] * len(non_indexed),
                    bytes.fromhex(data_hex[2:]),
                )
                for j, name in enumerate(non_indexed):
                    if j < len(decoded_data):
                        val = decoded_data[j]
                        if isinstance(val, int) and val > 10**15:
                            result[name] = str(val)
                        else:
                            result[name] = val
            except Exception:
                result["_raw_data"] = data_hex

        result["_detected_at"] = datetime.now(timezone.utc).isoformat()
        return result

    def get_events(
        self,
        program_slug: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get stored on-chain events, optionally filtered.

        Args:
            program_slug: filter by program slug (if tagged)
            event_type: filter by event name (BountyCreated, dll)
            limit: max events to return

        Returns:
            Dict with total, filtered count, and events list.
        """
        events = self._load_json_index("onchain_events.json")
        last_block = events.pop("_last_block", None)

        all_events = list(events.values())

        if event_type:
            all_events = [e for e in all_events if e.get("event") == event_type]

        if program_slug:
            all_events = [
                e for e in all_events
                if e.get("program_slug") == program_slug
            ]

        all_events.sort(key=lambda x: x.get("_detected_at", ""), reverse=True)

        return {
            "total_stored": len(events),
            "filtered_count": len(all_events),
            "events": all_events[:limit],
            "last_scanned_block": last_block,
            "web3_available": self.is_web3_available(),
        }

    def tag_event_with_program(
        self,
        event_id: str,
        program_slug: str,
    ) -> bool:
        """Link an event to a program (manual tagging)."""
        events = self._load_json_index("onchain_events.json")
        if event_id not in events:
            return False
        if isinstance(events[event_id], dict):
            events[event_id]["program_slug"] = program_slug
            self._save_json_index("onchain_events.json", events)
            return True
        return False

    # ── Background Polling (to be called from SyncManager) ──

    _poll_task: Any = None

    def start_background_polling(self, interval_seconds: int = 300) -> None:
        """Start background task to poll events every N seconds."""
        if not self.is_web3_available():
            log.info("onchain.polling_skipped_no_web3")
            return

        import asyncio  # noqa: PLC0415

        async def _poll_loop() -> None:
            log.info(
                "onchain.polling_started",
                interval=interval_seconds,
            )
            while True:
                try:
                    await self.poll_events()
                except Exception as e:
                    log.warning(
                        "onchain.poll_cycle_error",
                        error=str(e)[:100],
                    )
                await asyncio.sleep(interval_seconds)

        self._poll_task = asyncio.create_task(_poll_loop())

    def stop_background_polling(self) -> None:
        if self._poll_task is not None:
            self._poll_task.cancel()
            self._poll_task = None
            log.info("onchain.polling_stopped")

    async def close(self) -> None:
        self.stop_background_polling()
        if self._client is not None:
            await self._client.aclose()
            self._client = None
