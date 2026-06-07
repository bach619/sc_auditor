"""Health Aggregator for Vyper Upkeep Service.

Queries all 28 Vyper microservices' ``/health`` endpoints concurrently
and returns an aggregated up/down summary.
"""

from __future__ import annotations

import httpx

SERVICES: dict[str, str] = {
    "01-config": "http://01-config:8000",
    "02-immunefi": "http://02-immunefi:8000",
    "03-source": "http://03-source:8000",
    "04-scanner": "http://04-scanner:8000",
    "04a-scanner-slither": "http://04a-scanner-slither:8014",
    "04b-scanner-echidna": "http://04b-scanner-echidna:8015",
    "04c-scanner-forge": "http://04c-scanner-forge:8016",
    "04d-scanner-halmos": "http://04d-scanner-halmos:8017",
    "04e-scanner-manticore": "http://04e-scanner-manticore:8018",
    "05-scanner-mythril": "http://05-scanner-mythril:8013",
    "06-ai": "http://06-ai:8000",
    "07-classifier": "http://07-classifier:8000",
    "08-exploit": "http://08-exploit:8006",
    "09-reporter": "http://09-reporter:8007",
    "10-notifier": "http://10-notifier:8000",
    "11-orchestrator": "http://11-orchestrator:8000",
    "12-webhook": "http://12-webhook:8000",
    "13-upkeep": "http://13-upkeep:8000",
    "14-agent": "http://14-agent:8000",
    "15-dashboard": "http://15-dashboard:8000",
    "16-submission": "http://16-submission:8000",
    "17-experience": "http://17-experience:8019",
    "18-code4rena": "http://18-code4rena:8000",
    "19-sherlock": "http://19-sherlock:8000",
    "20-cantina": "http://20-cantina:8000",
    "21-hats": "http://21-hats:8000",
    "22-source-starknet": "http://22-source-starknet:8000",
    "23-scanner-cairo": "http://23-scanner-cairo:8000",
}


async def aggregate_health() -> dict:
    results: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in SERVICES.items():
            try:
                resp = await client.get(f"{url}/health")
                results[name] = {"status": "up", "data": resp.json()}
            except Exception:
                results[name] = {"status": "down"}

    up_count = sum(1 for r in results.values() if r["status"] == "up")
    return {
        "total": len(SERVICES),
        "up": up_count,
        "down": len(SERVICES) - up_count,
        "services": results,
    }
