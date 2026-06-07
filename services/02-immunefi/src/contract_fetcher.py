"""ContractAutoFetcher — Auto-fetch contract source from Service 03 + trigger scan.

Flow:
  1. Iterasi semua program yang punya contracts
  2. Cek cache: sudah pernah di-fetch? (indexes/fetched_contracts.json)
  3. Kalau belum → POST /fetch ke 03-source service
  4. Kalau sukses → simpan hasil + trigger scan ke 11-orchestrator
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from src.models import Program
from src.storage import EnhancedJSONStorage

log = structlog.get_logger()

SOURCE_SERVICE_URL = os.getenv("SOURCE_URL", "http://03-source:8000")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://11-orchestrator:8000")


class ContractAutoFetcher:
    """Fetch contract source code from Service 03 for all programs.

    Usage:
        fetcher = ContractAutoFetcher(storage)
        results = await fetcher.fetch_all(programs)
        results = await fetcher.fetch_for_program(slug, program)
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

    # ── Cache ──────────────────────────────────────────────

    def _get_cache(self) -> dict[str, Any]:
        """Load fetched contracts cache."""
        data = self.storage.get_index("fetched_contracts")
        return data if isinstance(data, dict) else {}

    def _save_cache(self, cache: dict) -> None:
        """Persist fetched contracts cache."""
        try:
            import json  # noqa: PLC0415
            path = self.storage.data_dir / "indexes" / "fetched_contracts.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(cache, indent=2))
        except Exception as e:
            log.warning("contract_fetcher.cache_save_error", error=str(e)[:100])

    def _cache_key(self, chain: str, address: str) -> str:
        return f"{chain}:{address.lower()}"

    # ── Fetch Single Contract ──────────────────────────────

    async def fetch_contract(
        self,
        chain: str,
        address: str,
        program_slug: str = "",
    ) -> dict[str, Any]:
        """Fetch source code for a single contract from Service 03.

        Returns dict with status + source data (if found).
        """
        cache_key = self._cache_key(chain, address)
        cache = self._get_cache()

        # Check cache
        if cache_key in cache:
            log.debug(
                "contract_fetcher.cache_hit",
                chain=chain,
                address=address[:10],
            )
            entry = cache[cache_key]
            return {
                "status": "cached",
                "chain": chain,
                "address": address,
                "source": entry.get("source"),
                "cached_at": entry.get("fetched_at"),
            }

        client = await self._get_client()
        log.info(
            "contract_fetcher.fetch.start",
            chain=chain,
            address=address[:10],
            program=program_slug or "N/A",
        )

        try:
            resp = await client.post(
                f"{SOURCE_SERVICE_URL}/fetch",
                json={
                    "chain": chain,
                    "address": address,
                },
                timeout=60.0,
            )

            now = datetime.now(UTC).isoformat()

            if resp.status_code == 200:
                data = resp.json().get("data", {})
                source_data = {
                    "sources": data.get("sources", {}),
                    "compiler_version": data.get("compiler_version", ""),
                    "license": data.get("license"),
                    "provider": data.get("provider", "unknown"),
                }

                # Update cache
                cache[cache_key] = {
                    "chain": chain,
                    "address": address,
                    "source": source_data,
                    "fetched_at": now,
                    "program_slug": program_slug,
                }
                self._save_cache(cache)

                log.info(
                    "contract_fetcher.fetch.success",
                    chain=chain,
                    address=address[:10],
                    provider=source_data["provider"],
                )

                return {
                    "status": "success",
                    "chain": chain,
                    "address": address,
                    "source": source_data,
                    "fetched_at": now,
                }

            elif resp.status_code == 404:
                # Contract not verified on any provider
                cache[cache_key] = {
                    "chain": chain,
                    "address": address,
                    "source": None,
                    "fetched_at": now,
                    "program_slug": program_slug,
                    "not_found": True,
                }
                self._save_cache(cache)

                return {
                    "status": "not_found",
                    "chain": chain,
                    "address": address,
                    "error": "Contract not verified on any provider",
                }

            else:
                log.warning(
                    "contract_fetcher.fetch.error",
                    chain=chain,
                    address=address[:10],
                    status=resp.status_code,
                )
                return {
                    "status": "error",
                    "chain": chain,
                    "address": address,
                    "error": f"HTTP {resp.status_code}",
                }

        except httpx.TimeoutException:
            log.warning(
                "contract_fetcher.fetch.timeout",
                chain=chain,
                address=address[:10],
            )
            return {
                "status": "error",
                "chain": chain,
                "address": address,
                "error": "timeout",
            }
        except Exception as e:
            log.warning(
                "contract_fetcher.fetch.exception",
                chain=chain,
                address=address[:10],
                error=str(e)[:100],
            )
            return {
                "status": "error",
                "chain": chain,
                "address": address,
                "error": str(e)[:100],
            }

    # ── Trigger Scan ───────────────────────────────────────

    async def trigger_scan(
        self,
        slug: str,
        chain: str,
        address: str,
    ) -> dict[str, Any]:
        """Trigger orchestrator scan pipeline for a contract.

        POST /audit ke 11-orchestrator.
        """
        client = await self._get_client()
        log.info(
            "contract_fetcher.trigger_scan",
            slug=slug,
            chain=chain,
            address=address[:10],
        )

        try:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/audit",
                json={
                    "chain": chain,
                    "address": address,
                    "program": slug,
                    "priority": 5,
                    "metadata": {
                        "source": "contract_fetcher",
                        "auto_triggered": True,
                    },
                },
                timeout=30.0,
            )

            if resp.status_code == 201:
                data = resp.json().get("data", {})
                audit_id = data.get("audit_id", "")
                log.info(
                    "contract_fetcher.scan_triggered",
                    slug=slug,
                    audit_id=audit_id,
                )
                return {
                    "status": "triggered",
                    "audit_id": audit_id,
                    "slug": slug,
                    "chain": chain,
                    "address": address,
                }
            else:
                log.warning(
                    "contract_fetcher.scan_failed",
                    slug=slug,
                    status=resp.status_code,
                )
                return {
                    "status": "failed",
                    "slug": slug,
                    "chain": chain,
                    "address": address,
                    "error": f"HTTP {resp.status_code}",
                }

        except Exception as e:
            log.warning(
                "contract_fetcher.scan_exception",
                slug=slug,
                error=str(e)[:100],
            )
            return {
                "status": "error",
                "slug": slug,
                "chain": chain,
                "address": address,
                "error": str(e)[:100],
            }

    # ── Batch Operations ──────────────────────────────────

    async def fetch_for_program(
        self,
        slug: str,
        program: Program,
        trigger_scan: bool = True,
    ) -> list[dict[str, Any]]:
        """Fetch all contracts for a single program.

        Args:
            slug: Program slug
            program: Program object with contracts
            trigger_scan: Whether to trigger orchestrator scan after fetch

        Returns:
            List of fetch results
        """
        if not program.contracts:
            return []

        results: list[dict[str, Any]] = []
        for contract in program.contracts:
            if not contract.address or not contract.chain:
                continue

            fetch_result = await self.fetch_contract(
                chain=contract.chain,
                address=contract.address,
                program_slug=slug,
            )
            results.append(fetch_result)

            # Trigger scan if fetch was successful
            if trigger_scan and fetch_result.get("status") == "success":
                scan_result = await self.trigger_scan(
                    slug=slug,
                    chain=contract.chain,
                    address=contract.address,
                )
                fetch_result["scan"] = scan_result

        return results

    async def fetch_all(
        self,
        programs: dict[str, Program],
        trigger_scan: bool = True,
        max_programs: int = 50,
    ) -> dict[str, Any]:
        """Fetch contracts for all programs.

        Args:
            programs: Dict of slug → Program
            trigger_scan: Whether to trigger orchestrator scan
            max_programs: Max programs to process per call

        Returns:
            Summary dict with results per program
        """
        summary: dict[str, Any] = {
            "total_programs": 0,
            "total_contracts": 0,
            "fetched": 0,
            "cached": 0,
            "not_found": 0,
            "errors": 0,
            "scans_triggered": 0,
            "programs": [],
        }

        count = 0
        for slug, prog in programs.items():
            if count >= max_programs:
                break
            if not prog.contracts:
                continue

            results = await self.fetch_for_program(slug, prog, trigger_scan=trigger_scan)
            if results:
                summary["total_programs"] += 1
                summary["total_contracts"] += len(results)
                for r in results:
                    if r.get("status") == "success":
                        summary["fetched"] += 1
                        if r.get("scan", {}).get("status") == "triggered":
                            summary["scans_triggered"] += 1
                    elif r.get("status") == "cached":
                        summary["cached"] += 1
                    elif r.get("status") == "not_found":
                        summary["not_found"] += 1
                    else:
                        summary["errors"] += 1

                summary["programs"].append({
                    "slug": slug,
                    "name": prog.name,
                    "contracts_count": len(prog.contracts),
                    "results": results,
                })
                count += 1

        summary["generated_at"] = datetime.now(UTC).isoformat()
        return summary

    # ── Stats ──────────────────────────────────────────────

    def get_fetch_stats(self) -> dict[str, Any]:
        """Get fetch statistics from cache."""
        cache = self._get_cache()
        total = len(cache)
        found = sum(1 for v in cache.values() if isinstance(v, dict) and v.get("source"))
        not_found = sum(
            1 for v in cache.values()
            if isinstance(v, dict) and v.get("not_found")
        )

        # Group by provider
        providers: dict[str, int] = {}
        for v in cache.values():
            if isinstance(v, dict) and v.get("source"):
                prov = v["source"].get("provider", "unknown")
                providers[prov] = providers.get(prov, 0) + 1

        return {
            "total_cached": total,
            "found": found,
            "not_found": not_found,
            "by_provider": providers,
        }

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
