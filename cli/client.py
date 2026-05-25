"""HTTP client for all Vyper backend services.

Provides typed methods for each service API, with:
  - Connection pooling via httpx
  - Automatic error wrapping
  - Timeout management
  - Response envelope unwrapping
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx
from rich.console import Console

from cli.config import get_config

console = Console(stderr=True)

# ── Custom Exceptions ───────────────────────────────────────────

class VyperClientError(Exception):
    """Base exception for client errors."""

class ServiceUnavailableError(VyperClientError):
    """Service is not reachable."""

class ServiceError(VyperClientError):
    """Service returned an error response."""

class ScanTimeoutError(VyperClientError):
    """Scan exceeded timeout."""


# ── HTTP Client ──────────────────────────────────────────────────

class VyperClient:
    """Typed HTTP client wrapping all Vyper backend services.

    Usage:
        client = VyperClient()
        result = await client.start_audit("0xdead...", chain="ethereum")
    """

    def __init__(self, config: Any = None) -> None:
        self.cfg = config or get_config()
        self._client: httpx.AsyncClient | None = None

    # ── Connection management ──────────────────────────────────

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=5.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> VyperClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ── Core request helpers ───────────────────────────────────

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: Any = None,
        params: dict | None = None,
        timeout: float = 30.0,
        retries: int = 2,
    ) -> Any:
        """Send HTTP request with retry logic."""
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = await self.client.request(
                    method, url, json=json, params=params, timeout=timeout,
                )
                if resp.status_code == 503 and attempt < retries:
                    import asyncio
                    await asyncio.sleep(1.5 ** attempt)
                    continue
                resp.raise_for_status()
                body = resp.json()
                # Unwrap standard envelope: {data: ..., meta: ...}
                if isinstance(body, dict) and "data" in body:
                    return body["data"]
                return body

            except httpx.ConnectError as exc:
                last_error = ServiceUnavailableError(
                    f"Cannot connect to {url} — is the service running?"
                )
                break  # No retry for connection refused
            except httpx.TimeoutException as exc:
                last_error = ScanTimeoutError(
                    f"Request to {url} timed out after {timeout}s"
                )
                break
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 422:
                    detail = exc.response.text[:500]
                    last_error = ServiceError(
                        f"Validation error from {url}: {detail}"
                    )
                    break
                try:
                    err_body = exc.response.json()
                    err_msg = (err_body.get("meta") or {}).get("error", str(exc))
                except Exception:
                    err_msg = str(exc)
                if attempt < retries:
                    import asyncio
                    await asyncio.sleep(1.5 ** attempt)
                    continue
                last_error = ServiceError(f"Service error from {url}: {err_msg}")
            except Exception as exc:
                last_error = VyperClientError(f"Unexpected error: {exc}")
                break

        raise last_error or VyperClientError("Request failed")

    # ── Health check ───────────────────────────────────────────

    async def check_health(self, base_url: str, name: str = "") -> dict:
        """Check service health, return status info."""
        try:
            data = await self._request("GET", f"{base_url}/health", timeout=5.0)
            return {"name": name or base_url, "status": "healthy", "data": data}
        except VyperClientError as exc:
            return {"name": name or base_url, "status": "unhealthy", "error": str(exc)}

    async def health_all(self) -> list[dict]:
        """Check health of all 20 services in parallel.

        Uses config URLs where available, falls back to localhost:port
        for services not registered in config.
        """
        # ── All 20 services with their check URLs ─────────────────
        all_services: list[tuple[str, str]] = [
            # (display_name, health_url)
            ("orchestrator",      self.cfg.get("orchestrator_url") or "http://localhost:8009"),
            ("scanner",           self.cfg.get("scanner_url") or "http://localhost:8003"),
            ("exploit",           self.cfg.get("exploit_url") or "http://localhost:8006"),
            ("reporter",          self.cfg.get("reporter_url") or "http://localhost:8007"),
            ("notifier",          self.cfg.get("notifier_url") or "http://localhost:8008"),
            ("source",            self.cfg.get("source_url") or "http://localhost:8002"),
            ("immunefi",          self.cfg.get("immunefi_url") or "http://localhost:8001"),
            # ── Services without config URL → cek via localhost ────
            ("01-config",         "http://localhost:8011"),
            ("04a-scanner-slither", "http://localhost:8014"),
            ("04b-scanner-echidna", "http://localhost:8015"),
            ("04c-scanner-forge", "http://localhost:8016"),
            ("04d-scanner-halmos", "http://localhost:8017"),
            ("05-scanner-mythril", "http://localhost:8013"),
            ("06-ai",             "http://localhost:8004"),
            ("07-classifier",     "http://localhost:8005"),
            ("12-webhook",        "http://localhost:8010"),
            ("13-upkeep",         "http://localhost:8012"),
            ("14-agent",          self.cfg.get("agent_url") or "http://localhost:8021"),
            ("16-submission",     "http://localhost:8018"),
        ]

        import asyncio
        tasks = [self.check_health(url, name) for name, url in all_services]
        return await asyncio.gather(*tasks)

    # ── Orchestrator API ───────────────────────────────────────

    async def start_audit(
        self,
        address: str,
        chain: str = "ethereum",
        program: str = "",
        priority: int = 5,
        metadata: dict | None = None,
    ) -> dict:
        """POST /audit — start a new audit pipeline."""
        url = f"{self.cfg.get('orchestrator_url')}/audit"
        payload = {
            "address": address,
            "chain": chain,
            "program": program,
            "priority": priority,
            "metadata": metadata or {},
        }
        return await self._request("POST", url, json=payload)

    async def get_audit(self, audit_id: str) -> dict:
        """GET /audit/{audit_id} — get audit status & results."""
        url = f"{self.cfg.get('orchestrator_url')}/audit/{audit_id}"
        return await self._request("GET", url)

    async def list_audits(
        self,
        state: str = "",
        program: str = "",
        chain: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """GET /audits — list all audits with optional filters."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if state:
            params["state"] = state
        if program:
            params["program"] = program
        if chain:
            params["chain"] = chain
        url = f"{self.cfg.get('orchestrator_url')}/audits"
        return await self._request("GET", url, params=params)

    async def retry_audit(self, audit_id: str) -> dict:
        """POST /pipeline/retry/{audit_id} — retry failed audit."""
        url = f"{self.cfg.get('orchestrator_url')}/pipeline/retry/{audit_id}"
        return await self._request("POST", url)

    async def get_queue(self) -> list[dict]:
        """GET /queue — view priority queue."""
        url = f"{self.cfg.get('orchestrator_url')}/queue"
        return await self._request("GET", url)

    async def get_stats(self) -> dict:
        """GET /stats — pipeline statistics."""
        url = f"{self.cfg.get('orchestrator_url')}/stats"
        return await self._request("GET", url)

    async def daemon_start(self) -> dict:
        """POST /daemon/start — start continuous scanning mode."""
        url = f"{self.cfg.get('orchestrator_url')}/daemon/start"
        return await self._request("POST", url)

    async def daemon_stop(self) -> dict:
        """POST /daemon/stop — stop continuous scanning mode."""
        url = f"{self.cfg.get('orchestrator_url')}/daemon/stop"
        return await self._request("POST", url)

    async def daemon_status(self) -> dict:
        """GET /daemon/status — check daemon status."""
        url = f"{self.cfg.get('orchestrator_url')}/daemon/status"
        return await self._request("GET", url)

    # ── Scanner API (direct) ───────────────────────────────────

    async def scan_contract(
        self,
        sources: dict[str, str],
        compiler: str = "0.8.20",
        tools: list[str] | None = None,
        timeout: float = 600.0,
    ) -> dict:
        """POST /scan — run tools on contract source directly."""
        url = f"{self.cfg.get('scanner_url')}/scan"
        payload: dict[str, Any] = {
            "sources": sources,
            "compiler": compiler,
        }
        if tools:
            payload["tools"] = tools
        return await self._request("POST", url, json=payload, timeout=timeout)

    # ── Exploit API ────────────────────────────────────────────

    async def run_exploit(
        self,
        finding_id: str,
        source: dict[str, str],
        attack_type: str = "auto",
        vulnerable_function: str = "unknown",
        compiler: str = "0.8.20",
        chain: str = "ethereum",
        timeout: float = 600.0,
    ) -> dict:
        """POST /exploit — generate PoC for a finding."""
        url = f"{self.cfg.get('exploit_url')}/exploit"
        payload = {
            "audit_id": f"cli-{finding_id}",
            "finding_id": finding_id,
            "source": source,
            "compiler": compiler,
            "vulnerable_function": vulnerable_function,
            "attack_type": attack_type,
            "chain": chain,
            "use_ai": False,
            "max_hypotheses": 3,
        }
        return await self._request("POST", url, json=payload, timeout=timeout)

    # ── Reporter API ───────────────────────────────────────────

    async def generate_report(
        self,
        audit_id: str,
        findings: list[dict],
        source_info: dict | None = None,
        exploit_results: list[dict] | None = None,
    ) -> dict:
        """POST /report — generate audit report."""
        url = f"{self.cfg.get('reporter_url')}/report"
        payload = {
            "audit_id": audit_id or "cli-report",
            "chain": "ethereum",
            "address": "",
            "program": "",
            "findings": findings,
            "metrics": None,
            "exploit_results": exploit_results or [],
            "source_info": source_info or {},
        }
        return await self._request("POST", url, json=payload)
