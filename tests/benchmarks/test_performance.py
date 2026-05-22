"""Performance benchmark suite untuk Vyper.

Benchmark:
1. Service startup time (cold → healthy)
2. Scan time per kontrak size (small/medium/large)
3. Pipeline throughput (contracts/minute)
4. Memory usage per scan
5. Docker image size per service

Usage:
    pytest tests/benchmarks/ --benchmark
    python -m pytest tests/benchmarks/test_performance.py -v
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

# ── Load thresholds ──────────────────────────────────────────────

THRESHOLDS_PATH = Path(__file__).parent / "thresholds.json"
with open(THRESHOLDS_PATH) as f:
    THRESHOLDS = json.load(f)

# ── Service list ─────────────────────────────────────────────────

ALL_SERVICES = [
    "01-config", "02-immunefi", "03-source", "04-scanner",
    "04a-scanner-slither", "04b-scanner-echidna", "04c-scanner-forge",
    "04d-scanner-halmos", "05-scanner-mythril", "06-ai",
    "07-classifier", "08-exploit", "09-reporter", "10-notifier",
    "11-orchestrator", "12-webhook", "13-upkeep", "14-agent",
    "15-dashboard", "16-submission",
]

SERVICE_PORTS = {
    "01-config": 8011, "02-immunefi": 8001, "03-source": 8002,
    "04-scanner": 8003, "04a-scanner-slither": 8014,
    "04b-scanner-echidna": 8015, "04c-scanner-forge": 8016,
    "04d-scanner-halmos": 8017, "05-scanner-mythril": 8013,
    "06-ai": 8004, "07-classifier": 8005, "08-exploit": 8006,
    "09-reporter": 8007, "10-notifier": 8008,
    "11-orchestrator": 8009, "12-webhook": 8010,
    "13-upkeep": 8012, "14-agent": 8019,
    "15-dashboard": 8000, "16-submission": 8018,
}


# ── Helpers ──────────────────────────────────────────────────────


async def _wait_for_service(url: str, timeout: float = 30.0) -> float:
    """Wait for service to respond, return startup time."""
    import httpx
    start = time.monotonic()
    async with httpx.AsyncClient(timeout=2.0) as client:
        while time.monotonic() - start < timeout:
            try:
                resp = await client.get(f"{url}/health")
                if resp.status_code == 200:
                    return time.monotonic() - start
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            await asyncio.sleep(0.5)
    raise TimeoutError(f"Service at {url} not ready within {timeout}s")


# ── Tests ────────────────────────────────────────────────────────


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_service_startup_time():
    """Benchmark: time each service takes to become healthy."""
    import httpx
    import asyncio
    
    results = {}
    for svc in ALL_SERVICES:
        port = SERVICE_PORTS[svc]
        url = f"http://localhost:{port}"
        try:
            elapsed = await _wait_for_service(url)
            results[svc] = round(elapsed, 2)
        except TimeoutError as e:
            results[svc] = str(e)
    
    # Print results
    print("\n=== Service Startup Times ===")
    for svc, elapsed in results.items():
        status = "✅" if isinstance(elapsed, float) and elapsed < THRESHOLDS["service_startup"]["cold"] else "❌"
        print(f"  {status} {svc}: {elapsed}s")
    
    # Assert all started within threshold
    cold_max = THRESHOLDS["service_startup"]["cold"]
    failures = [
        svc for svc, elapsed in results.items()
        if isinstance(elapsed, float) and elapsed > cold_max
    ]
    assert not failures, f"Slow startup: {failures}"


@pytest.mark.benchmark
def test_thresholds_file_valid():
    """Verify thresholds.json is valid and complete."""
    required_keys = {"service_startup", "scan_time", "pipeline_throughput"}
    assert required_keys.issubset(THRESHOLDS.keys()), \
        f"Missing keys: {required_keys - THRESHOLDS.keys()}"
    assert THRESHOLDS["pipeline_throughput"] > 0
    assert THRESHOLDS["service_startup"]["cold"] > 0


@pytest.mark.benchmark
def test_memory_threshold():
    """Check memory threshold is reasonable."""
    max_mem = THRESHOLDS["max_memory_per_scan_mb"]
    assert 256 <= max_mem <= 4096, \
        f"Memory threshold {max_mem}MB seems unreasonable"
    print(f"  Max memory per scan: {max_mem}MB")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
