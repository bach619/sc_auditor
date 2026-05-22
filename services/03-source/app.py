"""Vyper Source Service v2 — FastAPI microservice for Solidity source intelligence.

Enhanced with:
  - 14 source providers (Level 1)
  - Enhanced JSON Storage + indexing (Level 1)
  - Compiler verification via bytecode comparison (Level 1)
  - ABI extraction + dependency graph (Level 2)
  - Upgrade detection + metadata enrichment (Level 2)
  - Block monitor + cache warming (Level 3)
  - Bytecode repository + cross-chain correlation (Level 4)

Port: 8002 | Version: 0.2.0
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from shared.observability import setup_observability
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from src.detector import SourceDetector
from src.models import (
    ApiResponse,
    BatchFetchItem,
    BatchFetchRequest,
    BatchFetchResult,
    CacheStats,
    CacheWarmResult,
    ContractMetadata,
    EnrichedContract,
    FetchRequest,
    HealthData,
    Meta,
    MonitorStatus,
    SourceResult,
    UpgradeInfo,
    VerificationRequest,
    VerificationResult,
)






SERVICE_NAME = "source"
SERVICE_VERSION = "0.2.0"

detector = SourceDetector()

# ── Global state untuk background tasks ─────────────────────

_monitor_task: asyncio.Task | None = None
_monitor_start: float = 0.0


# ── Lifespan ───────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    log.info("source.startup", service=SERVICE_NAME, version=SERVICE_VERSION)
    cached = detector.count_cached()
    log.info("source.cache_stats", cached_contracts=cached)
    yield
    log.info("source.shutdown", service=SERVICE_NAME)
    global _monitor_task
    if _monitor_task and not _monitor_task.done():
        _monitor_task.cancel()


app = FastAPI(
    title="Vyper Source Service v2",
    description="Smart contract source code intelligence platform.",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



log = setup_observability(app, "03-source", "0.1.0")

# ── Helpers ─────────────────────────────────────────────────


def ok(data: object = None) -> ApiResponse:
    """Build a standard Vyper success response."""
    return ApiResponse(data=data, meta=Meta(status="ok"))


def err(detail: str, status_code: int = 400) -> HTTPException:
    """Build a standard Vyper error response."""
    return HTTPException(status_code=status_code, detail=detail)


# ── Level 1 — Foundation Endpoints ─────────────────────────


@app.get("/health")
async def health() -> ApiResponse:
    """Health check with cache statistics."""
    stats = detector.get_cache_stats()
    return ok(
        HealthData(
            status="ok",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
            sources_cached=stats.get("total_contracts", 0),
            providers_available=len(detector.list_providers()),
            cache_size_bytes=stats.get("cache_size_bytes", 0),
        )
    )


@app.post("/fetch")
async def fetch_source(body: FetchRequest) -> ApiResponse:
    """Fetch verified source code for a contract.

    Tries providers in priority order. Caches result on disk.
    """
    if not body.chain:
        raise err("chain is required")
    if not body.address or not body.address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    log.info("fetch.requested", chain=body.chain, address=body.address)

    result = await detector.fetch(body.chain, body.address, body.providers)

    if result is None:
        raise err(
            f"Contract {body.address} not verified on any provider for chain {body.chain}",
            status_code=404,
        )

    return ok(result)


@app.post("/fetch/batch")
async def fetch_batch(body: BatchFetchRequest) -> ApiResponse:
    """Batch fetch multiple contracts sekaligus.

    Menerima array contracts dan fetch secara parallel (default) atau sequential.
    """
    if not body.contracts:
        raise err("contracts list is required")

    log.info("fetch.batch", count=len(body.contracts), parallel=body.parallel)

    results: list[BatchFetchResult] = []

    async def _fetch_one(item: BatchFetchItem) -> BatchFetchResult:
        try:
            result = await detector.fetch(item.chain, item.address, item.providers)
            if result:
                return BatchFetchResult(
                    chain=item.chain,
                    address=item.address,
                    success=True,
                    provider=result.provider,
                    file_count=len(result.sources),
                )
            return BatchFetchResult(
                chain=item.chain,
                address=item.address,
                success=False,
                error="Not verified on any provider",
            )
        except Exception as e:
            return BatchFetchResult(
                chain=item.chain,
                address=item.address,
                success=False,
                error=str(e),
            )

    if body.parallel:
        tasks = [_fetch_one(item) for item in body.contracts]
        results = await asyncio.gather(*tasks)
    else:
        for item in body.contracts:
            results.append(await _fetch_one(item))

    success_count = sum(1 for r in results if r.success)
    log.info("fetch.batch_complete", total=len(results), success=success_count)

    return ok({
        "total": len(results),
        "success": success_count,
        "failed": len(results) - success_count,
        "results": results,
    })


@app.get("/source/{chain}/{address}")
async def get_cached_source(chain: str, address: str) -> ApiResponse:
    """Get cached source for a contract (full source code)."""
    if not address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    result = detector.get_cached(chain, address)
    if result is None:
        raise err(f"Source for {address} on {chain} not found in cache.", status_code=404)

    return ok(result)


@app.get("/contracts/{chain}/{address}/metadata")
async def get_contract_metadata(chain: str, address: str) -> ApiResponse:
    """Dapatkan metadata kontrak (tanpa source content)."""
    if not address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    metadata = detector.get_metadata(chain, address)
    if not metadata:
        raise err(f"Contract {address} on {chain} not found in cache.", status_code=404)

    return ok(metadata)


@app.delete("/source/{chain}/{address}")
async def clear_source_cache(chain: str, address: str) -> ApiResponse:
    """Remove cached source for a contract."""
    if not address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    removed = detector.clear_cache(chain, address)
    if not removed:
        raise err(f"No cached source for {address} on {chain}", status_code=404)

    return ok({"deleted": True, "chain": chain, "address": address})


@app.get("/providers")
async def list_providers() -> ApiResponse:
    """List all available source providers and their status."""
    providers = detector.list_providers()
    return ok({
        "total": len(providers),
        "providers": providers,
    })


@app.get("/contracts/search")
async def search_contracts(
    query: str | None = Query(None, description="Search query (address, name, or source content)"),
    chain: str | None = Query(None, description="Filter by chain"),
    provider: str | None = Query(None, description="Filter by provider name"),
    compiler: str | None = Query(None, description="Filter by compiler version"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
) -> ApiResponse:
    """Search cached contracts by address, name, or source content."""
    results = detector.search_contracts(
        query=query,
        chain=chain,
        provider=provider,
        compiler=compiler,
        limit=limit,
    )
    return ok({
        "total": len(results),
        "results": results,
    })


@app.get("/contracts")
async def list_contracts(
    chain: str | None = Query(None, description="Filter by chain"),
) -> ApiResponse:
    """List all cached contracts with basic metadata."""
    contracts = detector.list_cached(chain)
    return ok({
        "total": len(contracts),
        "contracts": contracts,
    })


@app.get("/cache/stats")
async def get_cache_stats() -> ApiResponse:
    """Statistik cache: total contracts, per chain, per provider, size."""
    stats = detector.get_cache_stats()
    return ok(stats)


# ── Level 1 — Verification ─────────────────────────────────


@app.post("/verify")
async def verify_contract(body: VerificationRequest) -> ApiResponse:
    """Verify source == on-chain bytecode via eth_getCode.

    Membandingkan source yang di-cache dengan bytecode on-chain.
    """
    from src.verifier import CompilerVerifier

    if not body.chain:
        raise err("chain is required")
    if not body.address or not body.address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    # Auto-fetch if not cached
    if not detector.storage.exists(body.chain, body.address):
        result = await detector.fetch(body.chain, body.address, body.providers)
        if not result:
            raise err(f"Contract {body.address} not found on any provider.", status_code=404)

    verifier = CompilerVerifier(detector.storage)
    result = await verifier.verify(body.chain, body.address)
    return ok(result)


@app.get("/verify/{chain}/{address}")
async def verify_contract_simple(chain: str, address: str) -> ApiResponse:
    """Verify source == on-chain bytecode (shorthand GET version)."""
    from src.verifier import CompilerVerifier

    if not address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    if not detector.storage.exists(chain, address):
        raise err(f"Contract {address} on {chain} not in cache. Use POST /verify first.", status_code=404)

    verifier = CompilerVerifier(detector.storage)
    result = await verifier.verify(chain, address)
    return ok(result)


# ── Level 2 — Intelligence Endpoints ───────────────────────


@app.get("/contracts/{chain}/{address}/abi")
async def get_contract_abi(chain: str, address: str) -> ApiResponse:
    """Dapatkan ABI contract (dari cache atau extract dari source)."""
    if not address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    # Check cache
    abi = detector.storage.get_abi(chain, address)
    if abi:
        return ok({"abi": abi, "source": "cache"})

    # Try to extract from source
    source = detector.get_cached(chain, address)
    if not source:
        raise err(f"Contract {address} on {chain} not found.", status_code=404)

    from src.abi_extractor import AbiExtractor
    extractor = AbiExtractor()
    abi_result = extractor.extract(source)

    # Cache the result
    if abi_result and abi_result.raw_abi:
        detector.storage.save_abi(chain, address, abi_result.raw_abi)

    return ok({
        "abi": abi_result.raw_abi if abi_result else None,
        "functions": abi_result.functions if abi_result else [],
        "events": abi_result.events if abi_result else [],
        "source": "extracted",
    })


@app.get("/contracts/{chain}/{address}/dependencies")
async def get_contract_dependencies(
    chain: str,
    address: str,
    max_depth: int = Query(3, ge=1, le=10),
) -> ApiResponse:
    """Dapatkan dependency graph (import resolution)."""
    if not address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    source = detector.get_cached(chain, address)
    if not source:
        raise err(f"Contract {address} on {chain} not found.", status_code=404)

    from src.dependency_resolver import DependencyResolver
    resolver = DependencyResolver(detector.storage)
    graph = await resolver.resolve(chain, address, max_depth=max_depth)

    return ok(graph)


@app.get("/contracts/{chain}/{address}/upgrades")
async def get_contract_upgrades(chain: str, address: str) -> ApiResponse:
    """History upgrade kontrak (source changes)."""
    if not address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    if not detector.storage.exists(chain, address):
        raise err(f"Contract {address} on {chain} not found.", status_code=404)

    # Get history from storage
    history = detector.storage.get_history(chain, address)
    metadata = detector.get_metadata(chain, address)

    # Check current bytecode
    from src.verifier import CompilerVerifier
    verifier = CompilerVerifier(detector.storage)
    verify_result = await verifier.verify(chain, address)

    return ok({
        "chain": chain,
        "address": address,
        "upgrade_count": metadata.upgrade_count if metadata else 0,
        "verified": verify_result.verified if verify_result else False,
        "match_percentage": verify_result.match_percentage if verify_result else 0,
        "history": history,
    })


@app.get("/contracts/{chain}/{address}/enriched")
async def get_enriched_metadata(chain: str, address: str) -> ApiResponse:
    """Dapatkan metadata lengkap + enrichment (security, complexity, etc)."""
    if not address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    source = detector.get_cached(chain, address)
    if not source:
        raise err(f"Contract {address} on {chain} not found.", status_code=404)

    from src.enricher import MetadataEnricher
    enricher = MetadataEnricher(detector.storage)
    enriched = await enricher.enrich(chain, address)

    return ok(enriched)


@app.post("/contracts/{chain}/{address}/refresh")
async def refresh_contract(chain: str, address: str) -> ApiResponse:
    """Force re-fetch + re-verify + re-enrich."""
    if not address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    # Re-fetch
    result = await detector.fetch(chain, address)
    if not result:
        raise err(f"Contract {address} on {chain} not verified on any provider.", status_code=404)

    # Re-verify
    from src.verifier import CompilerVerifier
    verifier = CompilerVerifier(detector.storage)
    verify_result = await verifier.verify(chain, address)

    return ok({
        "chain": chain,
        "address": address,
        "fetch": {
            "provider": result.provider,
            "files": len(result.sources),
        },
        "verification": verify_result,
    })


# ── Level 3 — Autonomous Endpoints ─────────────────────────


@app.post("/monitor/start")
async def start_block_monitor(
    chains: str | None = Query(None, description="Comma-separated chain list, e.g. 'ethereum,polygon'"),
) -> ApiResponse:
    """Start real-time block monitoring for new contracts."""
    global _monitor_task, _monitor_start

    if _monitor_task and not _monitor_task.done():
        raise err("Block monitor is already running.", status_code=409)

    chain_list = [c.strip() for c in chains.split(",") if c.strip()] if chains else ["ethereum"]

    from src.monitor import BlockMonitor
    monitor = BlockMonitor(detector.storage, detector)

    _monitor_start = datetime.now(timezone.utc).timestamp()
    _monitor_task = asyncio.create_task(monitor.start(chains=chain_list))

    log.info("monitor.started", chains=chain_list)
    return ok({
        "status": "started",
        "chains": chain_list,
    })


@app.post("/monitor/stop")
async def stop_block_monitor() -> ApiResponse:
    """Stop block monitoring."""
    global _monitor_task

    if not _monitor_task or _monitor_task.done():
        raise err("Block monitor is not running.", status_code=404)

    _monitor_task.cancel()
    _monitor_task = None
    log.info("monitor.stopped")
    return ok({"status": "stopped"})


@app.get("/monitor/status")
async def get_monitor_status() -> ApiResponse:
    """Status block monitoring."""
    global _monitor_task, _monitor_start

    running = _monitor_task is not None and not _monitor_task.done()
    uptime = (datetime.now(timezone.utc).timestamp() - _monitor_start) if running else 0.0

    return ok(MonitorStatus(
        running=running,
        uptime_seconds=round(uptime, 1),
    ))


@app.post("/cache/warm")
async def trigger_cache_warm(
    category: str = Query("defi_blue_chips", description="Category to warm: defi_blue_chips, recently_hacked, high_tvl"),
) -> ApiResponse:
    """Trigger cache warming for known contracts."""
    from src.cache_warmer import CacheWarmer
    warmer = CacheWarmer(detector.storage, detector)
    result = await warmer.warm(category=category)
    return ok(result)


# ── Level 4 — God-Tier Endpoints ───────────────────────────


@app.get("/contracts/{chain}/{address}/bytecode/history")
async def get_bytecode_history(chain: str, address: str) -> ApiResponse:
    """History bytecode untuk kontrak."""
    if not address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    if not detector.storage.exists(chain, address):
        raise err(f"Contract {address} on {chain} not found.", status_code=404)

    history = detector.storage.get_history(chain, address)
    metadata = detector.get_metadata(chain, address)

    return ok({
        "chain": chain,
        "address": address,
        "upgrade_count": metadata.upgrade_count if metadata else 0,
        "events": history,
    })


@app.get("/contracts/{chain}/{address}/cross-chain")
async def get_cross_chain_siblings(chain: str, address: str) -> ApiResponse:
    """Cari kontrak yang sama (bytecode match) di chain lain."""
    if not address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    source = detector.get_cached(chain, address)
    if not source:
        raise err(f"Contract {address} on {chain} not found.", status_code=404)

    from src.cross_chain import CrossChainCorrelator
    correlator = CrossChainCorrelator(detector.storage)
    siblings = await correlator.find_siblings(chain, address)

    return ok({
        "chain": chain,
        "address": address,
        "total_siblings": len(siblings),
        "siblings": siblings,
    })


@app.get("/contracts/{chain}/{address}/predict-risks")
async def predict_contract_risks(chain: str, address: str) -> ApiResponse:
    """Prediksi fungsi mana yang vulnerable (rule-based)."""
    if not address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    source = detector.get_cached(chain, address)
    if not source:
        raise err(f"Contract {address} on {chain} not found.", status_code=404)

    from src.predictive import PredictiveVulnerabilityMapper
    mapper = PredictiveVulnerabilityMapper()
    risks = mapper.predict_vulnerable_functions(chain, address, source)

    return ok({
        "chain": chain,
        "address": address,
        "function_count": len(risks),
        "high_risk_count": sum(1 for r in risks if r.get("risk_score", 0) >= 0.7),
        "functions": risks,
    })


@app.get("/contracts/forks/{chain}/{address}")
async def find_contract_forks(chain: str, address: str) -> ApiResponse:
    """Cari fork/salinan kontrak di seluruh cache."""
    if not address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    source = detector.get_cached(chain, address)
    if not source:
        raise err(f"Contract {address} on {chain} not found.", status_code=404)

    from src.cross_chain import CrossChainCorrelator
    correlator = CrossChainCorrelator(detector.storage)

    # Compute source hash
    import hashlib
    content = "".join(sorted(source.sources.values()))
    source_hash = hashlib.sha256(content.encode()).hexdigest()

    forks = await correlator.find_forks(source_hash, exclude=(chain, address))

    return ok({
        "chain": chain,
        "address": address,
        "source_hash": source_hash,
        "fork_count": len(forks),
        "forks": forks,
    })


@app.get("/stats/bytecode")
async def get_bytecode_stats() -> ApiResponse:
    """Statistik bytecode repository."""
    stats = detector.get_cache_stats()
    return ok({
        "total_contracts": stats.get("total_contracts", 0),
        "total_files": stats.get("total_files", 0),
        "total_lines": stats.get("total_lines", 0),
        "by_chain": stats.get("by_chain", {}),
        "by_provider": stats.get("by_provider", {}),
        "by_compiler": stats.get("by_compiler", {}),
        "cache_size_bytes": stats.get("cache_size_bytes", 0),
    })


# ── Entry Point ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8002,
        log_level="info",
        reload=False,
    )
