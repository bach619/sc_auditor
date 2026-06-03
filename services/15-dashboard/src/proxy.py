"""ServiceProxy — forwards requests to internal Vyper backend services.

Each service (Orchestrator, Config, Classifier, Immunefi, Scanner, etc.)
has its own base URL configured via environment variables. The proxy
uses a shared httpx.AsyncClient with connection pooling for efficiency.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(service="dashboard", module="proxy")


# ── Default service URLs (from env, with fallbacks) ─────────────

def _env_or(key: str, default: str) -> str:
    return os.environ.get(key, default)


@dataclass
class ServiceURLs:
    orchestrator: str = field(
        default_factory=lambda: _env_or("ORCHESTRATOR_URL", "http://localhost:8000")
    )
    config: str = field(
        default_factory=lambda: _env_or("CONFIG_URL", "http://localhost:8011")
    )
    scanner: str = field(
        default_factory=lambda: _env_or("SCANNER_URL", "http://localhost:8003")
    )
    classifier: str = field(
        default_factory=lambda: _env_or("CLASSIFIER_URL", "http://localhost:8005")
    )
    immunefi: str = field(
        default_factory=lambda: _env_or("IMMUNEFI_URL", "http://localhost:8001")
    )
    source: str = field(
        default_factory=lambda: _env_or("SOURCE_URL", "http://localhost:8002")
    )
    reporter: str = field(
        default_factory=lambda: _env_or("REPORTER_URL", "http://localhost:8007")
    )
    notifier: str = field(
        default_factory=lambda: _env_or("NOTIFIER_URL", "http://localhost:8008")
    )
    exploit: str = field(
        default_factory=lambda: _env_or("EXPLOIT_URL", "http://localhost:8006")
    )
    agent: str = field(
        default_factory=lambda: _env_or("AGENT_URL", "http://localhost:8021")  # 8021 (hindari bentrok 04a-scanner-slither di 8014)
    )
    webhook: str = field(
        default_factory=lambda: _env_or("WEBHOOK_URL", "http://localhost:8010")
    )
    upkeep: str = field(
        default_factory=lambda: _env_or("UPKEEP_URL", "http://localhost:8012")
    )
    scanner_slither: str = field(
        default_factory=lambda: _env_or("SCANNER_SLITHER_URL", "http://localhost:8014")
    )
    scanner_echidna: str = field(
        default_factory=lambda: _env_or("SCANNER_ECHIDNA_URL", "http://localhost:8015")
    )
    scanner_forge: str = field(
        default_factory=lambda: _env_or("SCANNER_FORGE_URL", "http://localhost:8016")
    )
    scanner_halmos: str = field(
        default_factory=lambda: _env_or("SCANNER_HALMOS_URL", "http://localhost:8017")
    )
    submission: str = field(
        default_factory=lambda: _env_or("SUBMISSION_URL", "http://localhost:8018")
    )


# ── Retry decorator ─────────────────────────────────────────────

_retry = retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, min=0.3, max=2.0),
    reraise=True,
)


class ServiceProxy:
    """HTTP client proxy for Vyper backend services.

    Usage:
        proxy = ServiceProxy()
        audits = await proxy.get_audits()
        result = await proxy.start_audit(chain="ethereum", address="0x...")
    """

    def __init__(
        self,
        urls: Optional[ServiceURLs] = None,
        timeout: float = 30.0,
    ) -> None:
        self.urls = urls or ServiceURLs()
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        logger.info("ServiceProxy initialised", urls=urls or self.urls)

    # ── Lifecycle ────────────────────────────────────────────────

    async def start(self) -> None:
        """Create the shared HTTP client (call at app startup)."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout),
            follow_redirects=True,
            limits=httpx.Limits(
                max_connections=100,           # default 10 → 100 untuk handle parallel proxy + health poll
                max_keepalive_connections=20,  # keepalive pool untuk reuse koneksi
                keepalive_expiry=30.0,         # keepalive 30 detik
            ),
            headers={
                "User-Agent": "Vyper-Dashboard/1.0",
                "X-API-Key": os.environ.get("DASHBOARD_API_KEY", "dev-mode-no-key"),
                "X-Service-Name": "15-dashboard",
            },
        )
        logger.info("HTTP client created")

    async def close(self) -> None:
        """Close the shared HTTP client (call at app shutdown)."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("HTTP client closed")

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("ServiceProxy not started — call await proxy.start()")
        return self._client

    # ── Helpers ──────────────────────────────────────────────────

    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        resp = await self.client.get(url, params=params)
        if resp.status_code >= 400:
            try:
                body = resp.text[:500]
            except Exception:
                body = "(unreadable)"
            logger.error("upstream_error", method="GET", url=url, status=resp.status_code, body=body)
        resp.raise_for_status()
        return self._safe_json(resp, url)

    async def _post(
        self, url: str, json: Optional[Dict[str, Any]] = None
    ) -> Any:
        resp = await self.client.post(url, json=json)
        if resp.status_code >= 400:
            try:
                body = resp.text[:500]
            except Exception:
                body = "(unreadable)"
            logger.error("upstream_error", method="POST", url=url, status=resp.status_code, body=body)
        resp.raise_for_status()
        return self._safe_json(resp, url)

    def _safe_json(self, resp: httpx.Response, url: str) -> Any:
        """Try to parse JSON, fallback to text on failure."""
        try:
            return resp.json()
        except Exception:
            logger.warning("non_json_response", url=url, status=resp.status_code, text=resp.text[:200])
            return {"data": None, "meta": {"status": "error", "error": f"Non-JSON response ({resp.status_code})"}}

    async def _put(
        self, url: str, json: Optional[Dict[str, Any]] = None
    ) -> Any:
        resp = await self.client.put(url, json=json)
        if resp.status_code >= 400:
            logger.error("upstream_error", method="PUT", url=url, status=resp.status_code, body=resp.text[:500])
        resp.raise_for_status()
        return self._safe_json(resp, url)

    async def _delete(self, url: str) -> Any:
        resp = await self.client.delete(url)
        if resp.status_code >= 400:
            logger.error("upstream_error", method="DELETE", url=url, status=resp.status_code, body=resp.text[:500])
        resp.raise_for_status()
        return self._safe_json(resp, url)

    # ═══════════════════════════════════════════════════════════
    # Orchestrator Service
    # ═══════════════════════════════════════════════════════════

    async def get_health(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.orchestrator}/health")

    async def get_audits(
        self,
        state: Optional[str] = None,
        program: Optional[str] = None,
        chain: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if state:
            params["state"] = state
        if program:
            params["program"] = program
        if chain:
            params["chain"] = chain
        return await self._get(f"{self.urls.orchestrator}/audits", params=params)

    async def get_audit(self, audit_id: str) -> Dict[str, Any]:
        return await self._get(f"{self.urls.orchestrator}/audit/{audit_id}")

    async def start_audit(
        self,
        chain: str,
        address: str,
        program: str = "",
        priority: int = 5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body = {
            "chain": chain,
            "address": address,
            "program": program,
            "priority": priority,
            "metadata": metadata or {},
        }
        # Antonio Supremacy — all audit requests route through Antonio
        return await self._post(f"{self.urls.agent}/audit", json=body)

    async def start_daemon(self) -> Dict[str, Any]:
        # Antonio Supremacy — daemon control through Antonio
        return await self._post(f"{self.urls.agent}/orchestrator/daemon/start")

    async def stop_daemon(self) -> Dict[str, Any]:
        # Antonio Supremacy — daemon control through Antonio
        return await self._post(f"{self.urls.agent}/orchestrator/daemon/stop")

    async def get_daemon_status(self) -> Dict[str, Any]:
        # Antonio Supremacy — daemon status through Antonio
        return await self._get(f"{self.urls.agent}/orchestrator/daemon/status")

    async def get_orchestrator_stats(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.orchestrator}/stats")

    async def retry_audit(self, audit_id: str) -> Dict[str, Any]:
        return await self._post(f"{self.urls.orchestrator}/pipeline/retry/{audit_id}")

    async def add_to_queue(
        self,
        contract_id: str,
        chain: str,
        address: str,
        program: str = "",
        priority_score: float = 0.0,
    ) -> Dict[str, Any]:
        body = {
            "contract_id": contract_id,
            "chain": chain,
            "address": address,
            "program": program,
            "priority_score": priority_score,
        }
        return await self._post(f"{self.urls.orchestrator}/queue", json=body)

    async def get_queue(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.orchestrator}/queue")

    # ═══════════════════════════════════════════════════════════
    # Config Service
    # ═══════════════════════════════════════════════════════════

    async def get_config(self, key: str) -> Dict[str, Any]:
        return await self._get(f"{self.urls.config}/config/{key}")

    async def get_all_config(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.config}/config")

    async def set_config(self, key: str, value: Any) -> Dict[str, Any]:
        return await self._put(
            f"{self.urls.config}/config/{key}", json={"value": value}
        )

    async def set_bulk_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return await self._put(
            f"{self.urls.config}/config/bulk", json={"config": config}
        )

    # ═══════════════════════════════════════════════════════════
    # Classifier Service
    # ═══════════════════════════════════════════════════════════

    async def get_metrics(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.classifier}/metrics")

    async def submit_feedback(
        self,
        finding_id: str,
        feedback: str,
        status: str,
    ) -> Dict[str, Any]:
        body = {
            "finding_id": finding_id,
            "feedback": feedback,
            "status": status,
        }
        return await self._post(f"{self.urls.classifier}/feedback", json=body)

    async def get_feedback_list(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.classifier}/feedback")

    # ═══════════════════════════════════════════════════════════
    # Immunefi Service
    # ═══════════════════════════════════════════════════════════

    async def get_programs(
        self,
        search: Optional[str] = None,
        chain: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if search:
            params["search"] = search
        if chain:
            params["chain"] = chain
        return await self._get(f"{self.urls.immunefi}/programs", params=params)

    async def get_program(self, slug: str) -> Dict[str, Any]:
        return await self._get(f"{self.urls.immunefi}/programs/{slug}")

    async def get_updates(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.immunefi}/updates")

    async def get_scope_contracts(
        self,
        chain: Optional[str] = None,
        min_bounty: float = 0,
        offset: int = 0,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Get in-scope smart contracts ready for audit."""
        params: Dict[str, Any] = {"offset": offset, "limit": limit}
        if chain:
            params["chain"] = chain
        if min_bounty > 0:
            params["min_bounty"] = min_bounty
        return await self._get(f"{self.urls.immunefi}/contracts/scope", params=params)

    # ═══════════════════════════════════════════════════════════
    # Notifier Service
    # ═══════════════════════════════════════════════════════════

    async def send_test_notification(self, channel: str) -> Dict[str, Any]:
        return await self._post(
            f"{self.urls.notifier}/test", json={"channel": channel}
        )

    # ═══════════════════════════════════════════════════════════
    # Reporter Service
    # ═══════════════════════════════════════════════════════════

    async def generate_report(self, audit_id: str, format: str = "immunefi") -> Dict[str, Any]:
        return await self._post(
            f"{self.urls.reporter}/generate",
            json={"audit_id": audit_id, "format": format},
        )


    # ═══════════════════════════════════════════════════════════
    # Agent Service
    # ═══════════════════════════════════════════════════════════

    async def get_team_structure(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.agent}/team/structure")

    async def run_team_audit(
        self,
        task_type: str = "full_audit",
        input_data: Optional[Dict[str, Any]] = None,
        goal: str = "",
        max_delegations: int = 15,
    ) -> Dict[str, Any]:
        body = {
            "task_type": task_type,
            "input_data": input_data or {},
            "goal": goal,
            "max_delegations": max_delegations,
        }
        return await self._post(f"{self.urls.agent}/team/run", json=body)

    async def get_team_sessions(
        self, limit: int = 20, status: Optional[str] = None
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        return await self._get(f"{self.urls.agent}/team/sessions", params=params)

    async def get_team_session(self, session_id: str) -> Dict[str, Any]:
        return await self._get(f"{self.urls.agent}/team/{session_id}")

    async def run_agent(
        self,
        task_type: str = "full_audit",
        input_data: Optional[Dict[str, Any]] = None,
        goal: str = "",
        max_steps: int = 25,
    ) -> Dict[str, Any]:
        body = {
            "task_type": task_type,
            "input_data": input_data or {},
            "goal": goal,
            "max_steps": max_steps,
        }
        return await self._post(f"{self.urls.agent}/agent/run", json=body)

    async def get_agent_sessions(
        self, limit: int = 20, status: Optional[str] = None
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        return await self._get(f"{self.urls.agent}/agent/sessions", params=params)

    async def get_agent_session(self, session_id: str) -> Dict[str, Any]:
        return await self._get(f"{self.urls.agent}/agent/{session_id}")

    async def get_agent_skills(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.agent}/skills")

    async def get_skill_metrics(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.agent}/skills/metrics")

    async def get_agent_memory(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.agent}/memory")

    async def get_memory_stats(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.agent}/memory/stats")

    async def get_learning_stats(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.agent}/learning/stats")

    async def get_agent_health(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.agent}/health")

    async def get_agent_provider_status(self) -> Dict[str, Any]:
        """Get Antonio's LLM provider configuration status.

        Aggregates health, provider defaults, and circuit breaker status.
        """
        try:
            health = await self._get(f"{self.urls.agent}/health")
        except Exception:
            health = {}
        try:
            defaults = await self._get(f"{self.urls.agent}/agent/provider-defaults")
        except Exception:
            defaults = {}
        try:
            breakers = await self._get(f"{self.urls.agent}/circuit-breakers")
        except Exception:
            breakers = {}

        return {
            "health": health.get("data", {}),
            "provider_defaults": defaults.get("data", {}),
            "circuit_breakers": breakers.get("data", {}),
            "note": "Check provider_defaults for expected base URLs. Circuit breakers show skill health."
        }

    async def send_chat_message(
        self, message: str, session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a chat message to Antonio and get response.

        Retries up to 2 times with backoff on connection errors,
        since 14-agent may still be starting up when dashboard is ready.
        Uses a longer timeout (120s) because LLM reasoning with
        large prompts can take 60-90 seconds.
        """
        body: Dict[str, Any] = {"message": message}
        if session_id:
            body["session_id"] = session_id

        url = f"{self.urls.agent}/agent/chat"
        last_error: Optional[Exception] = None

        for attempt in range(3):
            try:
                # Override timeout for chat — LLM may need 60-90s
                resp = await self.client.post(url, json=body, timeout=120.0)
                if resp.status_code >= 400:
                    try:
                        resp_body = resp.text[:500]
                    except Exception:
                        resp_body = "(unreadable)"
                    logger.error("upstream_error", method="POST", url=url, status=resp.status_code, body=resp_body)
                resp.raise_for_status()
                return self._safe_json(resp, url)
            except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError) as exc:
                # Connection-level errors — agent may be starting up, retry with backoff
                last_error = exc
                if attempt < 2:
                    wait = min(2 ** attempt, 4)  # 1s, 2s, capped 4s
                    logger.warning(
                        "chat_proxy_retry",
                        attempt=attempt + 1,
                        error=str(exc),
                        wait_seconds=wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(
                        "chat_proxy_exhausted",
                        attempts=3,
                        error=str(exc),
                    )
            except httpx.HTTPStatusError as exc:
                # Upstream returned an error (4xx/5xx) — don't retry, let caller handle
                logger.error(
                    "chat_proxy_upstream_error",
                    status=exc.response.status_code,
                    url=url,
                )
                raise
            except Exception as exc:
                # Unknown error — don't retry
                logger.error("chat_proxy_unexpected", error=str(exc))
                raise

        # All retries exhausted — raise with user-friendly message
        raise httpx.ConnectError(
            f"Unable to reach Antonio agent at {self.urls.agent} after 3 attempts. "
            f"Last error: {last_error}. "
            f"Is the 14-agent service running?"
        )

    # ═══════════════════════════════════════════════════════════
    # Health Check All Services
    # ═══════════════════════════════════════════════════════════

    async def check_all_services(self) -> Dict[str, Any]:
        """Ping all services in parallel and return health status."""
        services = {
            "01-config": f"{self.urls.config}/health",
            "02-immunefi": f"{self.urls.immunefi}/health",
            "03-source": f"{self.urls.source}/health",
            "04-scanner": f"{self.urls.scanner}/health",
            "04a-slither": f"{self.urls.scanner_slither}/health",
            "04b-echidna": f"{self.urls.scanner_echidna}/health",
            "04c-forge": f"{self.urls.scanner_forge}/health",
            "04d-halmos": f"{self.urls.scanner_halmos}/health",
            "05-mythril": f"{self.urls.orchestrator}/health",  # proxy via orchestrator
            "06-ai": f"{self.urls.agent}/health",  # reuse agent URL for AI
            "07-classifier": f"{self.urls.classifier}/health",
            "08-exploit": f"{self.urls.exploit}/health",
            "09-reporter": f"{self.urls.reporter}/health",
            "10-notifier": f"{self.urls.notifier}/health",
            "11-orchestrator": f"{self.urls.orchestrator}/health",
            "12-webhook": f"{self.urls.webhook}/health",
            "13-upkeep": f"{self.urls.upkeep}/health",
            "14-agent": f"{self.urls.agent}/health",
            "16-submission": f"{self.urls.submission}/health",
        }

        async def _check_one(name: str, url: str) -> tuple[str, dict]:
            try:
                resp = await self.client.get(url, timeout=5.0)
                data = resp.json()
                return name, {
                    "status": "healthy" if resp.status_code == 200 else "unhealthy",
                    "code": resp.status_code,
                    "data": data.get("data") if isinstance(data, dict) else None,
                }
            except Exception as e:
                return name, {"status": "unreachable", "error": str(e)}

        tasks = [_check_one(name, url) for name, url in services.items()]
        results_list = await asyncio.gather(*tasks)
        return dict(results_list)

    # ═══════════════════════════════════════════════════════════
    # Pipeline
    # ═══════════════════════════════════════════════════════════

    async def get_pipeline_status(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.orchestrator}/pipeline")

    async def get_pipeline_steps(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.orchestrator}/pipeline/steps")

    # ═══════════════════════════════════════════════════════════
    # Scanner Tools
    # ═══════════════════════════════════════════════════════════

    async def get_scanner_tools_status(self) -> Dict[str, Any]:
        """Ping all scanner tool services."""
        scanners = {
            "slither": self.urls.scanner_slither,
            "echidna": self.urls.scanner_echidna,
            "forge": self.urls.scanner_forge,
            "halmos": self.urls.scanner_halmos,
        }
        results = {}
        for name, url in scanners.items():
            try:
                resp = await self.client.get(f"{url}/health", timeout=5.0)
                results[name] = {"status": "healthy" if resp.status_code == 200 else "unhealthy"}
            except Exception as e:
                results[name] = {"status": "unreachable", "error": str(e)}
        return results

    async def get_scanner_results(self, audit_id: str) -> Dict[str, Any]:
        return await self._get(f"{self.urls.scanner}/scan/{audit_id}")

    # ═══════════════════════════════════════════════════════════
    # Exploit
    # ═══════════════════════════════════════════════════════════

    async def get_exploit_detail(self, finding_id: str) -> Dict[str, Any]:
        return await self._get(f"{self.urls.exploit}/exploit/{finding_id}")

    # ═══════════════════════════════════════════════════════════
    # Notifier
    # ═══════════════════════════════════════════════════════════

    async def get_notifier_channels(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.notifier}/channels")

    async def get_notifier_logs(self, limit: int = 50) -> Dict[str, Any]:
        return await self._get(f"{self.urls.notifier}/delivery-log", params={"limit": limit})

    # ═══════════════════════════════════════════════════════════
    # Webhook
    # ═══════════════════════════════════════════════════════════

    async def get_webhook_logs(self, limit: int = 50) -> Dict[str, Any]:
        return await self._get(f"{self.urls.webhook}/logs", params={"limit": limit})

    # ═══════════════════════════════════════════════════════════
    # Source
    # ═══════════════════════════════════════════════════════════

    async def get_source_code(self, audit_id: str) -> Dict[str, Any]:
        return await self._get(f"{self.urls.source}/source/{audit_id}")

    # ═══════════════════════════════════════════════════════════
    # Reports
    # ═══════════════════════════════════════════════════════════

    async def list_reports(self, limit: int = 50) -> Dict[str, Any]:
        return await self._get(f"{self.urls.reporter}/reports", params={"limit": limit})

    # ═══════════════════════════════════════════════════════════
    # Upkeep / Scheduler
    # ═══════════════════════════════════════════════════════════

    async def get_upkeep_status(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.upkeep}/status")

    async def get_upkeep_logs(self, limit: int = 50) -> Dict[str, Any]:
        return await self._get(f"{self.urls.upkeep}/logs", params={"limit": limit})


    # ═══════════════════════════════════════════════════════════
    # Submission Service (16)
    # ═══════════════════════════════════════════════════════════

    async def get_submissions(
        self, category: Optional[str] = None, status: Optional[str] = None
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if category:
            params["category"] = category
        if status:
            params["status"] = status
        return await self._get(f"{self.urls.submission}/submissions", params=params)

    async def get_submission(self, finding_id: str) -> Dict[str, Any]:
        return await self._get(f"{self.urls.submission}/submissions/{finding_id}")

    async def create_submission(self, body: Dict[str, Any]) -> Dict[str, Any]:
        return await self._post(f"{self.urls.submission}/submissions", json=body)

    async def generate_submission_draft(
        self, finding_id: str, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await self._post(
            f"{self.urls.submission}/submissions/{finding_id}/draft", json=body
        )

    async def respond_to_immunefi(
        self, finding_id: str, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await self._post(
            f"{self.urls.submission}/submissions/{finding_id}/respond", json=body
        )

    async def get_submission_evidence(self, finding_id: str) -> Dict[str, Any]:
        return await self._get(
            f"{self.urls.submission}/submissions/{finding_id}/evidence"
        )

    async def get_submission_stats(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.submission}/stats")

    async def get_submission_category_stats(self) -> Dict[str, Any]:
        return await self._get(f"{self.urls.submission}/stats/categories")


# Module-level singleton
proxy = ServiceProxy()
