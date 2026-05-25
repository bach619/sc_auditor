# Hybrid Agent Architecture Implementation Plan

> **For Opencode:** Use the task tool to dispatch each task to a subagent for implementation.

**Goal:** Transform VYPER dari satu centralized agent (14-Agent) menjadi arsitektur **Main Agent + Backend Agents**, di mana user hanya berinteraksi dengan satu Main Agent, dan Main Agent mendelegasikan tugas ke Backend Agents di tiap service.

**Architecture:**
```
User ──► MAIN AGENT (14-Agent) ──► Backend Agent 06-AI  (AI Analyst)
          (conversation,           ──► Backend Agent 04-Scanner
           planning,               ──► Backend Agent 02-Immunefi
           delegation,             ──► Backend Agent 08-Exploit
           synthesis)              ──► etc.
```

**Key Principle:** User hanya bicara dengan **satu** AI Agent (Main Agent). Semua interaksi dengan service/agent lain terjadi di belakang layar.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, asyncio, httpx

---

## Phase 0: Shared Protocol Library

Membuat shared library yang digunakan oleh SEMUA agent (Main + Backend) untuk komunikasi.

### Task 0.1: Create shared agent protocol models

**Objective:** Buat Pydantic models untuk Agent Manifest, Delegation, Negotiation, dan Peer-to-Peer communication.

**Files:**
- Create: `services/shared/agent_protocol/models.py`

**Step 1: Write the file**
Buat file `services/shared/agent_protocol/models.py`:

```python
"""Shared protocol models for agent-to-agent communication in VYPER Hybrid Architecture.

All agents (Main + Backend) use these models to:
1. Publish their capabilities (Manifest)
2. Receive tasks from Main Agent (Delegation)
3. Negotiate task feasibility (Negotiation)
4. Collaborate peer-to-peer (Collaboration)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

import structlog

log = structlog.get_logger()


# ── Enums ─────────────────────────────────────────────────


class AgentCapability(str, Enum):
    """Standardized capability names that all agents can use."""

    # Intel capabilities
    FETCH_PROGRAM = "fetch_program"
    FETCH_SOURCE = "fetch_source"

    # Scanner capabilities
    RUN_STATIC_ANALYSIS = "run_static_analysis"
    RUN_FUZZING = "run_fuzzing"
    RUN_SYMBOLIC = "run_symbolic"
    RUN_FORGE = "run_forge"

    # AI Analysis capabilities
    CLASSIFY_FINDINGS = "classify_findings"
    GENERATE_FIX = "generate_fix"
    DEEP_ANALYSIS = "deep_analysis"

    # Exploit capabilities
    TEST_EXPLOIT = "test_exploit"
    GENERATE_POC = "generate_poc"

    # Report capabilities
    GENERATE_REPORT = "generate_report"
    EXPORT_REPORT = "export_report"

    # Notification capabilities
    SEND_NOTIFICATION = "send_notification"


class AgentStatus(str, Enum):
    """Current operational status of an agent."""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"
    STARTING = "starting"


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEFERRED = "deferred"  # Agent suggested alternative


# ── Capability Definition ──────────────────────────────────


@dataclass
class CapabilityDefinition:
    """Definition of one thing an agent can do."""
    name: AgentCapability
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    estimated_duration_ms: float = 1000.0
    estimated_cost_usd: float = 0.01
    confidence: float = 0.85


# ── Agent Manifest ─────────────────────────────────────────


@dataclass
class AgentManifest:
    """What an agent is and what it can do.
    
    Setiap service agent publish manifest ini ke Main Agent
    saat startup, sehingga Main Agent tahu:
    - Siapa mereka
    - Apa yang mereka bisa lakukan
    - Constraints mereka
    """
    service_name: str          # "06-ai", "04-scanner", etc.
    agent_role: str            # "vulnerability_analyst", "scanner_operator"
    version: str               # Semver
    capabilities: list[CapabilityDefinition]
    constraints: dict[str, Any] = field(default_factory=lambda: {
        "max_concurrent_tasks": 3,
        "requires_api_key": False,
        "max_context_length": 8000,
    })
    current_load: dict[str, Any] = field(default_factory=lambda: {
        "active_tasks": 0,
        "queue_depth": 0,
        "status": AgentStatus.IDLE,
    })


# ── Delegation (Main Agent → Backend Agent) ────────────────


@dataclass
class DelegationRequest:
    """Main Agent gives a task to a Backend Agent.
    
    The Main Agent has already planned what needs to be done.
    Now it tells a specific backend agent to do it.
    """
    task_id: str               # Unique ID for tracking
    goal: str                  # "Analyze 15 findings for USDe contract"
    capability: AgentCapability  # Which capability to use
    input_data: dict[str, Any]  # Source code, findings, context
    constraints: dict[str, Any] = field(default_factory=lambda: {
        "max_cost_usd": 0.50,
        "deadline_seconds": 120,
        "min_confidence": 0.8,
    })
    parent_session_id: str = ""   # Main Agent session ID for tracing
    priority: TaskPriority = TaskPriority.NORMAL


@dataclass
class DelegationResponse:
    """Backend Agent's response to a delegation.
    
    Returns the result plus metadata about how it went.
    """
    task_id: str
    status: TaskStatus
    output: Any = None
    error: str | None = None
    confidence: float = 0.0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    steps_taken: int = 0
    reflection: str = ""  # Agent's self-assessment of the result


# ── Negotiation (Two-way feasibility check) ────────────────


@dataclass
class NegotiationRequest:
    """Main Agent asks: 'Can you do this?'
    
    Before delegating, Main Agent might want to know
    if the backend agent can handle a specific task
    given current load and constraints.
    """
    task_description: str
    required_capability: AgentCapability
    estimated_complexity: float = 0.5  # 0.0 (trivial) - 1.0 (very complex)
    budget_usd: float = 1.0
    deadline_seconds: float = 300.0


@dataclass
class NegotiationResponse:
    """Backend Agent answers: 'Yes, but with these caveats.'
    
    The backend agent evaluates its current capacity
    and returns a realistic estimate.
    """
    can_handle: bool
    alternative_suggestion: str | None = None  # "I can do X but not Y"
    estimated_duration_ms: float = 0.0
    estimated_cost_usd: float = 0.0
    estimated_confidence: float = 0.0
    reasoning: str = ""


# ── Peer Collaboration (Backend Agent ↔ Backend Agent) ────


@dataclass
class PeerRequest:
    """Backend Agent asks another Backend Agent for help.
    
    Only for specific cases where one agent needs
    input from another (e.g., Scanner needs AI to
    pre-analyze a suspicious pattern).
    """
    request_id: str
    need: str                          # "pre_analyze_pattern"
    context: dict[str, Any]            # code snippet, finding, etc.
    urgency: Literal["low", "normal", "high", "critical"] = "normal"
    parent_session_id: str = ""


@dataclass
class PeerResponse:
    """Response to a peer collaboration request."""
    request_id: str
    success: bool
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0


# ── Session Tracking ───────────────────────────────────────


@dataclass
class DelegationStep:
    """Record of one delegation in the Main Agent's session."""
    step_number: int
    task_id: str
    target_agent: str       # "06-ai", "04-scanner"
    capability: AgentCapability
    goal: str
    status: TaskStatus
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    cost_usd: float = 0.0
    started_at: str = ""
    completed_at: str = ""


# ── Helpers ─────────────────────────────────────────────────


def now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def generate_task_id() -> str:
    """Generate a unique task ID."""
    import uuid
    return f"task-{uuid.uuid4().hex[:12]}"


def agent_http_client() -> Any:
    """Create an httpx client configured for agent-to-agent communication."""
    import httpx
    return httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=5.0),
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=50),
    )
```

**Step 2: Create `services/shared/agent_protocol/__init__.py`**

```python
"""VYPER Agent Protocol — shared models for agent communication."""

from .models import (
    AgentCapability,
    AgentManifest,
    AgentStatus,
    CapabilityDefinition,
    DelegationRequest,
    DelegationResponse,
    DelegationStep,
    NegotiationRequest,
    NegotiationResponse,
    PeerRequest,
    PeerResponse,
    TaskPriority,
    TaskStatus,
    agent_http_client,
    generate_task_id,
    now_iso,
)

__all__ = [
    "AgentCapability",
    "AgentManifest",
    "AgentStatus",
    "CapabilityDefinition",
    "DelegationRequest",
    "DelegationResponse",
    "DelegationStep",
    "NegotiationRequest",
    "NegotiationResponse",
    "PeerRequest",
    "PeerResponse",
    "TaskPriority",
    "TaskStatus",
    "agent_http_client",
    "generate_task_id",
    "now_iso",
]
```

**Verification:**
```bash
cd services/shared/agent_protocol && python -c "from models import AgentManifest; print('OK')"
```

**Commit:**
```bash
git add services/shared/
git commit -m "feat(agent-protocol): add shared protocol models for agent communication"
```


### Task 0.2: Create BaseAgent class

**Objective:** Buat abstract base class yang bisa dipakai SEMUA agent (Main + Backend).

**Files:**
- Create: `services/shared/agent_protocol/base_agent.py`

**Step 1: Write the file**

```python
"""BaseAgent — abstract base for all VYPER agents.

Setiap agent (Main atau Backend) extends class ini untuk:
1. Register capabilities
2. Handle delegation requests
3. Report status/health
4. Track sessions
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

import structlog

from .models import (
    AgentCapability,
    AgentManifest,
    AgentStatus,
    CapabilityDefinition,
    DelegationRequest,
    DelegationResponse,
    NegotiationRequest,
    NegotiationResponse,
    TaskStatus,
    agent_http_client,
    generate_task_id,
    now_iso,
)

log = structlog.get_logger()


class BaseAgent(ABC):
    """Abstract base for all VYPER agents.
    
    Provides:
    - Manifest management (capabilities, status)
    - Delegation handling (receive tasks, return results)
    - Negotiation handling (feasibility checks)
    - Session tracking
    
    Subclasses must implement:
    - _execute_task(): Actual task execution logic
    - _assess_capability(): Can we do this task?
    """

    def __init__(
        self,
        service_name: str,
        agent_role: str,
        version: str = "0.1.0",
    ) -> None:
        self.service_name = service_name
        self.agent_role = agent_role
        self.version = version
        self._capabilities: dict[AgentCapability, CapabilityDefinition] = {}
        self._active_tasks: dict[str, DelegationRequest] = {}
        self._completed_tasks: list[DelegationResponse] = []
        self._status = AgentStatus.STARTING
        self._started_at = time.time()
        self._max_concurrent = 3
        self._http_client = None

    # ── Capability Registration ────────────────────────────

    def register_capability(self, capability: CapabilityDefinition) -> None:
        """Register a capability this agent provides."""
        self._capabilities[capability.name] = capability
        log.info(
            "capability_registered",
            agent=self.service_name,
            capability=capability.name.value,
        )

    # ── Manifest ───────────────────────────────────────────

    def get_manifest(self) -> AgentManifest:
        """Build current manifest with live load data."""
        active = len(self._active_tasks)
        return AgentManifest(
            service_name=self.service_name,
            agent_role=self.agent_role,
            version=self.version,
            capabilities=list(self._capabilities.values()),
            constraints={
                "max_concurrent_tasks": self._max_concurrent,
                "requires_api_key": False,
                "max_context_length": 8000,
            },
            current_load={
                "active_tasks": active,
                "queue_depth": max(0, active - self._max_concurrent),
                "status": self._status,
            },
        )

    # ── Delegation ─────────────────────────────────────────

    async def handle_delegation(self, request: DelegationRequest) -> DelegationResponse:
        """Receive and execute a delegation from Main Agent.
        
        This is the main entry point for backend agents.
        Main Agent calls POST /agent/delegate -> this method.
        """
        task_id = request.task_id
        started_at = time.monotonic()

        log.info(
            "delegation_received",
            agent=self.service_name,
            task_id=task_id,
            capability=request.capability.value,
        )

        # Check capacity
        if len(self._active_tasks) >= self._max_concurrent:
            return DelegationResponse(
                task_id=task_id,
                status=TaskStatus.DEFERRED,
                error=f"At capacity ({self._max_concurrent} tasks). Try again later.",
            )

        # Check capability
        if request.capability not in self._capabilities:
            return DelegationResponse(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=f"Capability '{request.capability.value}' not available. "
                       f"Available: {[c.value for c in self._capabilities]}",
            )

        # Execute
        self._active_tasks[task_id] = request
        self._status = AgentStatus.BUSY

        try:
            result = await self._execute_task(request)
            duration = (time.monotonic() - started_at) * 1000
            response = DelegationResponse(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                output=result,
                confidence=self._capabilities[request.capability].confidence,
                cost_usd=self._estimate_cost(request.capability, duration),
                duration_ms=round(duration, 1),
                steps_taken=result.get("_steps", 1) if isinstance(result, dict) else 1,
                reflection=await self._generate_reflection(request, result),
            )
        except Exception as exc:
            log.exception("delegation_failed", agent=self.service_name, task_id=task_id)
            duration = (time.monotonic() - started_at) * 1000
            response = DelegationResponse(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=str(exc),
                duration_ms=round(duration, 1),
            )

        # Cleanup
        self._active_tasks.pop(task_id, None)
        self._completed_tasks.append(response)
        if len(self._completed_tasks) > 100:
            self._completed_tasks = self._completed_tasks[-100:]
        if not self._active_tasks:
            self._status = AgentStatus.IDLE

        log.info(
            "delegation_completed",
            agent=self.service_name,
            task_id=task_id,
            status=response.status.value,
            duration_ms=response.duration_ms,
        )

        return response

    async def handle_negotiation(self, request: NegotiationRequest) -> NegotiationResponse:
        """Check if we can handle a proposed task.
        
        Main Agent calls this BEFORE delegating to decide
        which backend agent to use.
        """
        can_handle = request.required_capability in self._capabilities
        has_capacity = len(self._active_tasks) < self._max_concurrent

        if not can_handle:
            return NegotiationResponse(
                can_handle=False,
                reasoning=f"Capability '{request.required_capability.value}' not available.",
            )

        if not has_capacity:
            return NegotiationResponse(
                can_handle=False,
                reasoning=f"At capacity ({len(self._active_tasks)}/{self._max_concurrent}).",
                alternative_suggestion="Try again in a few seconds.",
            )

        cap = self._capabilities[request.required_capability]
        load_factor = len(self._active_tasks) / max(self._max_concurrent, 1)
        estimated_duration = cap.estimated_duration_ms * (1 + load_factor * 0.5)

        return NegotiationResponse(
            can_handle=True,
            estimated_duration_ms=estimated_duration,
            estimated_cost_usd=cap.estimated_cost_usd,
            estimated_confidence=cap.confidence * (1 - load_factor * 0.1),
            reasoning=f"Ready. Current load: {len(self._active_tasks)}/{self._max_concurrent}.",
        )

    # ── Abstract Methods ───────────────────────────────────

    @abstractmethod
    async def _execute_task(self, request: DelegationRequest) -> Any:
        """Execute a delegated task.
        
        This is where the actual work happens.
        Subclasses implement their specific logic here.
        """
        ...

    # ── Optional Overrides ─────────────────────────────────

    async def _generate_reflection(
        self, request: DelegationRequest, result: Any
    ) -> str:
        """Generate a reflection on how the task went.
        
        Override in subclasses for richer self-assessment.
        Default returns empty string.
        """
        return ""

    def _estimate_cost(self, capability: AgentCapability, duration_ms: float) -> float:
        """Estimate the cost of executing this task."""
        cap = self._capabilities.get(capability)
        if cap is None:
            return 0.0
        return cap.estimated_cost_usd

    # ── Health ─────────────────────────────────────────────

    def get_health(self) -> dict[str, Any]:
        """Get agent health status."""
        uptime = time.time() - self._started_at
        return {
            "service": self.service_name,
            "role": self.agent_role,
            "version": self.version,
            "status": self._status.value,
            "uptime_seconds": round(uptime, 1),
            "capabilities": [c.name.value for c in self._capabilities.values()],
            "active_tasks": len(self._active_tasks),
            "max_concurrent": self._max_concurrent,
            "completed_tasks": len(self._completed_tasks),
        }
```

**Verification:**
```bash
cd services/shared/agent_protocol && python -c "from base_agent import BaseAgent; print('OK')"
```

**Commit:**
```bash
git add services/shared/
git commit -m "feat(agent-protocol): add BaseAgent abstract class"
```


### Task 0.3: Create Agent Registry (discovery mechanism)

**Objective:** Buat registry di Main Agent untuk menemukan dan melacak semua Backend Agents.

**Files:**
- Create: `services/shared/agent_protocol/registry.py`

**Step 1: Write the file**

```python
"""AgentRegistry — tracks all available backend agents and their capabilities.

Main Agent menggunakan registry ini untuk:
1. Menemukan agent mana yang bisa melakukan suatu task
2. Menyimpan manifest dari tiap agent
3. Health checking agent secara periodik
4. Load balancing antar agent
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog

from .models import (
    AgentCapability,
    AgentManifest,
    AgentStatus,
    DelegationRequest,
    DelegationResponse,
    NegotiationRequest,
    NegotiationResponse,
)

log = structlog.get_logger()

DEFAULT_REFRESH_INTERVAL = 30  # detik — refresh manifest


class AgentRegistry:
    """Registry of all backend agents known to the Main Agent.
    
    Attributes:
        _agents: Dict of service_name -> AgentManifest
        _http_client: HTTP client for agent communication
        _refresh_task: Background task for periodic refresh
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._agents: dict[str, AgentManifest] = {}
        self._last_seen: dict[str, float] = {}
        self._http_client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=3.0),
        )
        self._refresh_task: asyncio.Task | None = None
        self._known_services: dict[str, str] = {
            "06-ai": "http://06-ai:8000",
            "04-scanner": "http://04-scanner:8003",
            "02-immunefi": "http://02-immunefi:8001",
            "08-exploit": "http://08-exploit:8006",
            "09-reporter": "http://09-reporter:8007",
            "10-notifier": "http://10-notifier:8008",
        }

    # ── Agent Discovery ────────────────────────────────────

    async def discover_all(self) -> list[AgentManifest]:
        """Discover semua backend agents.
        
        Panggil /agent/manifest di setiap service yang dikenal.
        Agents yang tidak merespon dianggap offline.
        """
        manifests: list[AgentManifest] = []

        for service_name, base_url in self._known_services.items():
            try:
                manifest = await self._fetch_manifest(service_name, base_url)
                if manifest:
                    self._agents[service_name] = manifest
                    self._last_seen[service_name] = time.time()
                    manifests.append(manifest)
                    log.info(
                        "agent_discovered",
                        service=service_name,
                        role=manifest.agent_role,
                        capabilities=[c.name.value for c in manifest.capabilities],
                    )
            except Exception as exc:
                log.warning(
                    "agent_discovery_failed",
                    service=service_name,
                    error=str(exc),
                )
                # Mark as offline
                if service_name in self._agents:
                    self._agents[service_name].current_load["status"] = AgentStatus.OFFLINE

        return manifests

    async def _fetch_manifest(self, service_name: str, base_url: str) -> AgentManifest | None:
        """Fetch manifest from a single service."""
        url = f"{base_url}/agent/manifest"
        resp = await self._http_client.get(url, timeout=5.0)
        resp.raise_for_status()
        data = resp.json()
        # Handle standard Vyper envelope: {data: {...}, meta: {...}}
        payload = data.get("data", data)
        return AgentManifest(**payload)

    # ── Query ──────────────────────────────────────────────

    def find_agents_by_capability(
        self, capability: AgentCapability
    ) -> list[tuple[str, AgentManifest]]:
        """Find all agents that have a specific capability."""
        results: list[tuple[str, AgentManifest]] = []
        for name, manifest in self._agents.items():
            caps = [c.name for c in manifest.capabilities]
            if capability in caps:
                status = manifest.current_load.get("status")
                if status != AgentStatus.OFFLINE:
                    results.append((name, manifest))
        return results

    def get_best_agent(
        self, capability: AgentCapability
    ) -> tuple[str, AgentManifest] | None:
        """Get the best available agent for a capability.
        
        Selection criteria:
        1. Has the capability
        2. Is online
        3. Lowest current load
        """
        candidates = self.find_agents_by_capability(capability)
        if not candidates:
            return None

        # Sort by load (lowest first)
        candidates.sort(
            key=lambda x: x[1].current_load.get("active_tasks", 999)
        )
        return candidates[0]

    def get_agent(self, service_name: str) -> AgentManifest | None:
        """Get manifest for a specific agent."""
        return self._agents.get(service_name)

    def get_all_agents(self) -> list[AgentManifest]:
        """Get all known agents."""
        return list(self._agents.values())

    # ── Delegation via Registry ────────────────────────────

    async def delegate_to_best(
        self,
        capability: AgentCapability,
        request: DelegationRequest,
    ) -> DelegationResponse | None:
        """Delegate a task to the best available agent.
        
        Main Agent calls this to automatically route tasks.
        """
        agent_info = self.get_best_agent(capability)
        if agent_info is None:
            log.error(
                "no_agent_available",
                capability=capability.value,
            )
            return None

        service_name, manifest = agent_info
        base_url = self._known_services.get(service_name)
        if base_url is None:
            return None

        return await self._send_delegation(base_url, request)

    async def _send_delegation(
        self, base_url: str, request: DelegationRequest
    ) -> DelegationResponse:
        """Send a delegation request to a specific agent."""
        url = f"{base_url}/agent/delegate"
        resp = await self._http_client.post(url, json=_to_dict(request), timeout=120.0)
        resp.raise_for_status()
        data = resp.json()
        payload = data.get("data", data)
        return DelegationResponse(**payload)

    # ── Background Refresh ─────────────────────────────────

    def start_background_refresh(self, interval: int = DEFAULT_REFRESH_INTERVAL) -> None:
        """Start periodic agent discovery in the background."""
        if self._refresh_task is not None:
            return

        async def _refresh_loop():
            while True:
                await asyncio.sleep(interval)
                try:
                    await self.discover_all()
                except Exception as exc:
                    log.warning("agent_refresh_error", error=str(exc))

        self._refresh_task = asyncio.create_task(_refresh_loop())
        log.info("agent_refresh_started", interval=interval)

    def stop_background_refresh(self) -> None:
        """Stop the background refresh task."""
        if self._refresh_task:
            self._refresh_task.cancel()
            self._refresh_task = None


def _to_dict(obj: Any) -> dict:
    """Convert a dataclass to dict recursively."""
    if hasattr(obj, "__dataclass_fields__"):
        result = {}
        for field_name in obj.__dataclass_fields__:
            value = getattr(obj, field_name)
            result[field_name] = _to_dict(value)
        return result
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj
```

**Verification:**
```bash
cd services/shared/agent_protocol && python -c "from registry import AgentRegistry; print('OK')"
```

**Commit:**
```bash
git add services/shared/
git commit -m "feat(agent-protocol): add AgentRegistry with discovery and delegation routing"
```


## Phase 1: Upgrade Main Agent (14-Agent)

Transform 14-Agent dari executor jadi **Main Agent** yang:
1. User bicara dengannya (conversation interface)
2. Bikin plan sebelum eksekusi (planning phase)
3. Delegasi ke backend agents (delegation)
4. Sintesis hasil dari multiple agents (synthesis)

### Task 1.1: Add Planning Phase to Main Agent

**Objective:** Tambah planning phase BEFORE the ReAct loop. Agent bikin plan dulu, baru eksekusi.

**Files:**
- Modify: `services/14-agent/src/agent.py`
- Create: `services/14-agent/src/planner.py`

**Step 1: Create `services/14-agent/src/planner.py`**

```python
"""Planner — creates execution plans before the ReAct loop.

The Main Agent uses this to:
1. Analyze the user's request
2. Break it into sub-tasks
3. Determine which backend agents to involve
4. Create an ordered execution plan
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from services.shared.agent_protocol.models import AgentCapability, TaskPriority

log = structlog.get_logger()


@dataclass
class PlanStep:
    """Satu langkah dalam execution plan."""
    step_number: int
    goal: str
    required_capability: AgentCapability
    depends_on: list[int] = field(default_factory=list)  # step numbers that must complete first
    priority: TaskPriority = TaskPriority.NORMAL
    context_hint: str = ""  # Hint about what context to pass
    alternative_agent: str | None = None  # Fallback agent if primary unavailable


@dataclass
class ExecutionPlan:
    """Full execution plan for a user request."""
    goal: str
    steps: list[PlanStep]
    total_estimated_duration_ms: float = 0.0
    total_estimated_cost_usd: float = 0.0


class Planner:
    """Creates execution plans from user requests.
    
    Uses the LLM to analyze the request and break it into
    steps that can be delegated to backend agents.
    """

    def __init__(self, llm_client: Any) -> None:
        self.llm = llm_client

    async def create_plan(
        self,
        goal: str,
        input_data: dict[str, Any],
        available_capabilities: list[str],
    ) -> ExecutionPlan:
        """Create an execution plan for a user request.
        
        Args:
            goal: User's natural language goal
            input_data: Input data (contract address, chain, etc.)
            available_capabilities: What backend agents can do
        
        Returns:
            ExecutionPlan with ordered steps
        """
        # Use LLM to create the plan
        prompt = self._build_planning_prompt(goal, input_data, available_capabilities)
        
        # For now, use a rule-based approach
        # In production, this would call the LLM
        plan = self._default_plan(goal, input_data)
        
        log.info(
            "plan_created",
            goal=goal[:100],
            steps=len(plan.steps),
        )
        return plan

    def _default_plan(self, goal: str, input_data: dict[str, Any]) -> ExecutionPlan:
        """Default plan for smart contract audit."""
        steps = [
            PlanStep(
                step_number=1,
                goal="Fetch program information and source code",
                required_capability=AgentCapability.FETCH_SOURCE,
            ),
            PlanStep(
                step_number=2,
                goal="Run static analysis tools on the contract",
                required_capability=AgentCapability.RUN_STATIC_ANALYSIS,
                depends_on=[1],
            ),
            PlanStep(
                step_number=3,
                goal="Analyze scanner findings with AI",
                required_capability=AgentCapability.CLASSIFY_FINDINGS,
                depends_on=[2],
            ),
            PlanStep(
                step_number=4,
                goal="Generate proof-of-concept exploits for critical findings",
                required_capability=AgentCapability.TEST_EXPLOIT,
                depends_on=[3],
            ),
            PlanStep(
                step_number=5,
                goal="Generate audit report",
                required_capability=AgentCapability.GENERATE_REPORT,
                depends_on=[3, 4],
            ),
        ]
        return ExecutionPlan(
            goal=goal,
            steps=steps,
            total_estimated_duration_ms=300_000,  # 5 minutes
            total_estimated_cost_usd=0.50,
        )

    def _build_planning_prompt(
        self, goal: str, input_data: dict[str, Any], capabilities: list[str]
    ) -> str:
        """Build the prompt for LLM-based planning."""
        return f"""You are a planning AI for smart contract audits.
Create an execution plan for: {goal}

Input data: {input_data}

Available capabilities: {', '.join(capabilities)}

Output a JSON plan with steps. Each step has:
- step_number
- goal: what to accomplish
- required_capability: which capability to use
- depends_on: list of step numbers that must complete first

Return ONLY valid JSON.
"""
```

**Step 2: Modify `services/14-agent/src/agent.py`**

Add planning phase before the ReAct loop. Insert after the memory init section and before the `for step_num` loop:

Find the section around line 154 that says `# ReAct loop` and replace with:

```python
        # ── PLANNING PHASE ──
        # Before executing, create a plan
        plan = await self.planner.create_plan(
            goal=goal,
            input_data=input_data,
            available_capabilities=[c.value for c in self.registry.get_all_capabilities()],
        )
        self.memory.set_working("execution_plan", {
            "goal": plan.goal,
            "steps": [
                {"step": s.step_number, "goal": s.goal, "capability": s.required_capability.value}
                for s in plan.steps
            ],
        })
        log.info(
            "plan_created",
            session_id=session_id,
            steps=len(plan.steps),
            estimated_duration_ms=plan.total_estimated_duration_ms,
        )

        # ── ReAct loop ──
        for step_num in range(1, max_steps + 1):
```

**Verification:**
```bash
cd services/14-agent && python -c "from src.planner import Planner; print('OK')"
```

**Commit:**
```bash
git add services/14-agent/src/planner.py services/14-agent/src/agent.py
git commit -m "feat(main-agent): add planning phase before ReAct loop"
```


### Task 1.2: Add Delegation Skills to Main Agent

**Objective:** Tambah skill baru ke Main Agent untuk mendelegasikan task ke Backend Agents via AgentRegistry.

**Files:**
- Create: `services/14-agent/src/skills/delegate_task.py`
- Modify: `services/14-agent/app.py` (register new skill)

**Step 1: Create `services/14-agent/src/skills/delegate_task.py`**

```python
"""DelegateSkill — Main Agent delegates a task to a Backend Agent.

This is how the Main Agent communicates with backend agents.
Instead of calling services directly, it uses the AgentRegistry
to find the right agent and delegate the task.
"""

from __future__ import annotations

from typing import Any

import structlog

from services.shared.agent_protocol.models import (
    AgentCapability,
    DelegationRequest,
    DelegationResponse,
    TaskPriority,
    generate_task_id,
)
from services.shared.agent_protocol.registry import AgentRegistry
from src.skills.base import BaseSkill
from src.models import SkillResult

log = structlog.get_logger()


class DelegateTaskSkill(BaseSkill):
    """Skill untuk mendelegasikan task ke Backend Agent via registry.
    
    Main Agent memanggil skill ini saat ReAct loop memutuskan
    untuk mendelegasikan pekerjaan ke service lain.
    """

    def __init__(self, registry: AgentRegistry) -> None:
        super().__init__()
        self._agent_registry = registry
        self.name = "delegate_task"
        self.description = "Delegate a task to a specialized backend agent"
        self.parameters = {
            "capability": {
                "type": "string",
                "description": "The capability required (e.g., 'run_static_analysis', 'classify_findings')",
                "required": True,
            },
            "goal": {
                "type": "string",
                "description": "What the backend agent should do",
                "required": True,
            },
            "input_data": {
                "type": "object",
                "description": "Context and data for the backend agent",
                "required": True,
            },
        }

    async def execute(self, **kwargs: Any) -> SkillResult:
        """Execute a delegation to a backend agent.
        
        Args:
            capability: AgentCapability string
            goal: Task description
            input_data: Context data
            
        Returns:
            SkillResult with delegation response
        """
        capability_str = kwargs.get("capability", "")
        goal = kwargs.get("goal", "")
        input_data = kwargs.get("input_data", {})

        # Parse capability
        try:
            capability = AgentCapability(capability_str)
        except ValueError:
            return SkillResult(
                success=False,
                error=f"Unknown capability: {capability_str}. "
                       f"Available: {[c.value for c in AgentCapability]}",
            )

        # Find best agent
        agent_info = self._agent_registry.get_best_agent(capability)
        if agent_info is None:
            return SkillResult(
                success=False,
                error=f"No backend agent available for capability: {capability_str}",
            )

        service_name, manifest = agent_info

        # Create delegation request
        request = DelegationRequest(
            task_id=generate_task_id(),
            goal=goal,
            capability=capability,
            input_data=input_data,
            parent_session_id=self._get_current_session_id(),
        )

        log.info(
            "delegating_task",
            to=service_name,
            capability=capability_str,
            task_id=request.task_id,
        )

        # Delegate via registry
        response = await self._agent_registry.delegate_to_best(capability, request)

        if response is None:
            return SkillResult(
                success=False,
                error=f"Delegation failed: no agent responded for {capability_str}",
            )

        if response.status.value in ("failed", "deferred"):
            return SkillResult(
                success=False,
                error=f"Agent {service_name} returned {response.status.value}: {response.error}",
                output={"delegation_response": response},
            )

        return SkillResult(
            success=True,
            output={
                "delegation_response": {
                    "task_id": response.task_id,
                    "agent": service_name,
                    "status": response.status.value,
                    "confidence": response.confidence,
                    "cost_usd": response.cost_usd,
                    "duration_ms": response.duration_ms,
                    "output": response.output,
                    "reflection": response.reflection,
                }
            },
        )

    def _get_current_session_id(self) -> str:
        """Get the current session ID from context."""
        # Injected by the agent loop
        return getattr(self, "_session_id", "")
```

**Step 2: Modify `services/14-agent/app.py` — register DelegateTaskSkill**

Find the skill registration section (around line 152-161) and add after the existing registrations:

```python
    from src.skills.delegate_task import DelegateTaskSkill
    from services.shared.agent_protocol.registry import AgentRegistry

    # Init Agent Registry for backend agent discovery
    agent_registry = AgentRegistry(http_client=state.http_client)
    state.agent_registry = agent_registry
    
    # Register delegation skill (pass the registry)
    registry.register(DelegateTaskSkill(agent_registry))
    
    # Start background agent discovery
    agent_registry.start_background_refresh(interval=30)
```

**Verification:**
```bash
cd services/14-agent && python -c "from src.skills.delegate_task import DelegateTaskSkill; print('OK')"
```

**Commit:**
```bash
git add services/14-agent/src/skills/delegate_task.py services/14-agent/app.py
git commit -m "feat(main-agent): add delegate_task skill for backend agent communication"
```


### Task 1.3: Add Main Agent Endpoint — Agent Manifest & Status

**Objective:** Tambah endpoint ke 14-Agent untuk publish manifest-nya sendiri dan discovery endpoint.

**Files:**
- Modify: `services/14-agent/app.py`

**Step 1: Add manifest endpoint**

Add after the health endpoint (~line 265):

```python
@app.get("/agent/manifest")
async def agent_manifest() -> ApiResponse:
    """Publish Main Agent manifest for discovery by other agents."""
    if state is None or state.agent is None:
        raise _err("Service not initialized", 503)
    
    capabilities = []
    if state.registry:
        for skill in state.registry.list_skills():
            capabilities.append({
                "name": skill.name,
                "description": skill.description,
                "input_schema": skill.parameters,
            })
    
    manifest = {
        "service_name": "14-agent",
        "agent_role": "main_agent",
        "version": "0.2.0",
        "capabilities": capabilities,
        "constraints": {
            "max_concurrent_tasks": 5,
            "requires_api_key": True,
            "max_context_length": 16000,
        },
        "current_load": {
            "active_tasks": state.agent.active_sessions,
            "queue_depth": 0,
            "status": "idle" if state.agent.active_sessions == 0 else "busy",
        },
    }
    return _ok(manifest)


@app.get("/agent/registry")
async def agent_registry_status() -> ApiResponse:
    """List all discovered backend agents and their capabilities."""
    if state is None or state.agent_registry is None:
        raise _err("Agent registry not initialized", 503)
    
    agents = state.agent_registry.get_all_agents()
    return _ok({
        "total_agents": len(agents),
        "agents": [
            {
                "service": a.service_name,
                "role": a.agent_role,
                "capabilities": [c.name.value for c in a.capabilities],
                "status": a.current_load.get("status", "unknown"),
                "active_tasks": a.current_load.get("active_tasks", 0),
            }
            for a in agents
        ],
    })
```

**Verification:**
```bash
# Will be verified via integration test
```

**Commit:**
```bash
git add services/14-agent/app.py
git commit -m "feat(main-agent): add manifest and registry endpoints"
```


## Phase 2: Backend Agent 06-AI

Transform 06-AI dari service pasif jadi **Backend Agent** dengan local ReAct loop.

### Task 2.1: Agentify 06-AI — Add BaseAgent + ReAct Loop

**Objective:** Tambah layer agent ke 06-AI sehingga bisa menerima delegasi dari Main Agent.

**Files:**
- Create: `services/06-ai/src/agent_loop.py`
- Modify: `services/06-ai/app.py`

**Step 1: Create `services/06-ai/src/agent_loop.py`**

```python
"""AIAgent — Backend Agent untuk AI Analysis dengan local ReAct loop.

Menerima delegasi dari Main Agent, lalu menjalankan ReAct loop
sendiri untuk memutuskan STRATEGI terbaik:
- Batch analysis untuk low/medium findings (lebih murah)
- Deep analysis untuk critical findings (lebih akurat)
- Cache-first untuk findings yang sudah pernah dianalisis
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from services.shared.agent_protocol.base_agent import BaseAgent
from services.shared.agent_protocol.models import (
    AgentCapability,
    CapabilityDefinition,
    DelegationRequest,
    DelegationResponse,
    TaskStatus,
)

from src.llm import LLMClient
from src.analyzer import Analyzer

log = structlog.get_logger()


class AIAgent(BaseAgent):
    """Backend Agent untuk AI-powered vulnerability analysis.
    
    Extends BaseAgent with:
    - Local ReAct loop for strategy decisions
    - LLM integration for actual analysis
    - Caching logic
    - Cost optimization
    """

    def __init__(
        self,
        analyzer: Analyzer,
        llm_client: LLMClient,
    ) -> None:
        super().__init__(
            service_name="06-ai",
            agent_role="vulnerability_analyst",
            version="0.2.0",
        )
        self.analyzer = analyzer
        self.llm = llm_client
        self._max_concurrent = 3

        # Register capabilities
        self.register_capability(CapabilityDefinition(
            name=AgentCapability.CLASSIFY_FINDINGS,
            description="Classify scanner findings as True Positive or False Positive using LLM analysis",
            estimated_duration_ms=30_000,  # 30 seconds avg
            estimated_cost_usd=0.05,
            confidence=0.85,
        ))
        self.register_capability(CapabilityDefinition(
            name=AgentCapability.GENERATE_FIX,
            description="Generate code fix recommendations for confirmed vulnerabilities",
            estimated_duration_ms=15_000,
            estimated_cost_usd=0.03,
            confidence=0.75,
        ))
        self.register_capability(CapabilityDefinition(
            name=AgentCapability.DEEP_ANALYSIS,
            description="Deep dive analysis with full source code trace and exploit path verification",
            estimated_duration_ms=60_000,
            estimated_cost_usd=0.15,
            confidence=0.90,
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        """Execute a delegated task with local ReAct loop.
        
        The AI Agent runs its own mini ReAct loop to decide
        the best strategy for analyzing findings.
        """
        capability = request.capability
        input_data = request.input_data

        if capability == AgentCapability.CLASSIFY_FINDINGS:
            return await self._execute_classify(input_data)
        elif capability == AgentCapability.GENERATE_FIX:
            return await self._execute_fix(input_data)
        elif capability == AgentCapability.DEEP_ANALYSIS:
            return await self._execute_deep_analysis(input_data)
        else:
            raise ValueError(f"Unknown capability: {capability}")

    async def _execute_classify(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Classify findings with local ReAct optimization.
        
        Mini ReAct loop:
        1. Check input size
        2. Decide strategy: batch vs single vs deep
        3. Execute
        4. Return results
        """
        source = input_data.get("source", {})
        findings = input_data.get("findings", [])
        compiler = input_data.get("compiler")
        contract_name = input_data.get("contract_name", "unknown")

        steps_taken = 0
        total_cost = 0.0

        # ── THINK: What strategy to use? ──
        total_findings = len(findings)
        critical_count = sum(
            1 for f in findings if f.get("severity") in ("critical", "high")
        )
        low_count = sum(
            1 for f in findings if f.get("severity") in ("low", "informational", "medium")
        )

        log.info(
            "ai_agent_thinking",
            total=total_findings,
            critical=critical_count,
            low=low_count,
        )

        result_findings = []

        # Strategy 1: Deep analysis for critical findings
        if critical_count > 0:
            critical_findings = [f for f in findings if f.get("severity") in ("critical", "high")]
            log.info("ai_agent_strategy", type="deep_analysis", count=len(critical_findings))
            
            for finding in critical_findings:
                analyzed = await self.analyzer.analyze_single(
                    source=source,
                    finding=finding,
                    compiler=compiler,
                )
                result_findings.append(analyzed)
                steps_taken += 1
                total_cost += 0.15  # deep analysis cost

        # Strategy 2: Batch analysis for low/medium findings
        if low_count > 0:
            low_findings = [f for f in findings if f.get("severity") in ("low", "informational", "medium")]
            log.info("ai_agent_strategy", type="batch_analysis", count=len(low_findings))
            
            analyzed = await self.analyzer.analyze_all(
                source=source,
                findings=low_findings,
                compiler=compiler,
                contract_name=contract_name,
            )
            result_findings.extend(analyzed)
            steps_taken += 1
            total_cost += 0.05 * len(low_findings)  # but actually batched = cheaper

        # Count verdicts
        tp_count = sum(1 for r in result_findings if r.ai_verdict == "true_positive")
        fp_count = len(result_findings) - tp_count

        return {
            "findings": [r.model_dump() for r in result_findings],
            "summary": {
                "total": len(result_findings),
                "true_positives": tp_count,
                "false_positives": fp_count,
            },
            "_steps": steps_taken,
            "_cost": round(total_cost, 3),
            "_strategy": "deep+hybrid" if critical_count > 0 else "batch",
        }

    async def _execute_fix(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Generate fix suggestion for a finding."""
        source = input_data.get("source", {})
        finding = input_data.get("finding", {})
        compiler = input_data.get("compiler")

        # Combine source files
        if isinstance(source, dict):
            full_source = "\n\n".join(
                f"// File: {name}\n{content}"
                for name, content in source.items()
            )
        else:
            full_source = str(source)

        # Use the fixer
        from src.fixer import FixSuggester
        fixer = FixSuggester(llm=self.llm)
        
        from src.models import Finding
        finding_obj = Finding(**finding)
        
        suggestion = await fixer.suggest_fix(
            source_code=full_source,
            finding=finding_obj,
            compiler=compiler,
        )

        return {
            "fix": suggestion.model_dump(),
            "finding_id": finding.get("id"),
        }

    async def _execute_deep_analysis(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Deep analysis with full source code trace."""
        source = input_data.get("source", {})
        findings = input_data.get("findings", [])
        compiler = input_data.get("compiler")
        contract_name = input_data.get("contract_name", "unknown")

        # Deep analysis = analyze one by one with full context
        results = []
        for finding in findings:
            result = await self.analyzer.analyze_single(
                source=source,
                finding=finding,
                compiler=compiler,
            )
            results.append(result)

        return {
            "findings": [r.model_dump() for r in results],
            "summary": {
                "total": len(results),
                "true_positives": sum(1 for r in results if r.ai_verdict == "true_positive"),
            },
            "_steps": len(results),
            "_type": "deep",
        }

    async def _generate_reflection(
        self, request: DelegationRequest, result: Any
    ) -> str:
        """Generate reflection on how the analysis went."""
        summary = result.get("summary", {}) if isinstance(result, dict) else {}
        total = summary.get("total", 0)
        tp = summary.get("true_positives", 0)
        strategy = result.get("_strategy", "unknown") if isinstance(result, dict) else "unknown"
        
        return (
            f"Analyzed {total} findings ({tp} TP). "
            f"Strategy: {strategy}. "
            f"Cost: ${result.get('_cost', 0):.3f}" if isinstance(result, dict) else ""
        )
```

**Step 2: Modify `services/06-ai/app.py` — add agent endpoints**

Add after existing imports:

```python
from src.agent_loop import AIAgent
from services.shared.agent_protocol.models import (
    DelegationRequest,
    NegotiationRequest,
    generate_task_id,
)
```

In the lifespan function, after creating the analyzer (~line 188), add:

```python
    # Create AI Agent layer
    state.ai_agent = AIAgent(
        analyzer=state.analyzer,
        llm_client=state.llm,
    )
```

Add after the health endpoint:

```python
@app.get("/agent/manifest")
async def agent_manifest() -> ApiResponse:
    """Publish agent manifest for Main Agent discovery."""
    if state is None or state.ai_agent is None:
        raise err("Service not initialized", 503)
    return ok(state.ai_agent.get_manifest().__dict__)


@app.post("/agent/delegate")
async def agent_delegate(body: dict[str, Any]) -> ApiResponse:
    """Receive a delegation from Main Agent."""
    if state is None or state.ai_agent is None:
        raise err("Service not initialized", 503)
    
    request = DelegationRequest(**body)
    response = await state.ai_agent.handle_delegation(request)
    return ok(response.__dict__)


@app.post("/agent/negotiate")
async def agent_negotiate(body: dict[str, Any]) -> ApiResponse:
    """Handle a negotiation request from Main Agent."""
    if state is None or state.ai_agent is None:
        raise err("Service not initialized", 503)
    
    request = NegotiationRequest(**body)
    response = await state.ai_agent.handle_negotiation(request)
    return ok(response.__dict__)
```

**Verification:**
```bash
cd services/06-ai && python -c "from src.agent_loop import AIAgent; print('OK')"
```

**Commit:**
```bash
git add services/06-ai/src/agent_loop.py services/06-ai/app.py
git commit -m "feat(agent-06-ai): add backend agent layer with ReAct loop"
```


## Phase 3: Backend Agent 04-Scanner

### Task 3.1: Agentify 04-Scanner — Tool Selection Intelligence

**Objective:** Tambah layer agent ke Scanner sehingga bisa memutuskan tool mana yang di-run berdasarkan konteks.

**Files:**
- Create: `services/04-scanner/src/agent_loop.py`
- Modify: `services/04-scanner/app.py`

**Step 1: Create `services/04-scanner/src/agent_loop.py`**

```python
"""ScannerAgent — Backend Agent untuk smart contract scanning dengan tool intelligence.

Menerima delegasi dari Main Agent, lalu menjalankan ReAct loop
untuk memutuskan:
- Tool mana yang di-run (Slither dulu, Mythril kalau perlu)
- Timeout per tool
- Prioritasi findings
- Retry strategy
"""

from __future__ import annotations

from typing import Any

import structlog

from services.shared.agent_protocol.base_agent import BaseAgent
from services.shared.agent_protocol.models import (
    AgentCapability,
    CapabilityDefinition,
    DelegationRequest,
    DelegationResponse,
    TaskStatus,
)

log = structlog.get_logger()


class ScannerAgent(BaseAgent):
    """Backend Agent untuk smart contract scanning.
    
    Memutuskan tool strategy berdasarkan:
    - Contract complexity (LOC, number of functions)
    - Previous scan results (cache)
    - Time constraints
    - User preferences
    """

    def __init__(self, http_client: Any) -> None:
        super().__init__(
            service_name="04-scanner",
            agent_role="scanner_operator",
            version="0.2.0",
        )
        self._http_client = http_client
        self._max_concurrent = 2

        # Register capabilities
        self.register_capability(CapabilityDefinition(
            name=AgentCapability.RUN_STATIC_ANALYSIS,
            description="Run static analysis tools (Slither, Mythril) to find vulnerabilities",
            estimated_duration_ms=120_000,  # 2 minutes
            estimated_cost_usd=0.01,
            confidence=0.80,
        ))
        self.register_capability(CapabilityDefinition(
            name=AgentCapability.RUN_FUZZING,
            description="Run fuzzing with Echidna for property-based testing",
            estimated_duration_ms=600_000,  # 10 minutes
            estimated_cost_usd=0.05,
            confidence=0.70,
        ))
        self.register_capability(CapabilityDefinition(
            name=AgentCapability.RUN_SYMBOLIC,
            description="Run symbolic execution with Halmos for formal verification",
            estimated_duration_ms=300_000,  # 5 minutes
            estimated_cost_usd=0.03,
            confidence=0.75,
        ))

    async def _execute_task(self, request: DelegationRequest) -> Any:
        """Execute a scanning task with tool selection intelligence."""
        input_data = request.input_data
        sources = input_data.get("sources", {})
        address = input_data.get("address", "")
        chain = input_data.get("chain", "ethereum")

        # ── THINK: Which tools to run? ──
        # Default: always run Slither, then decide on others
        tools_to_run = ["slither"]
        reasoning = ["slither: fastest, catches common issues"]

        # If contract is complex, add Mythril
        total_lines = sum(len(s.split("\n")) for s in sources.values())
        if total_lines > 500:
            tools_to_run.append("mythril")
            reasoning.append(f"mythril: contract is large ({total_lines} lines)")

        # Check if previous scan exists (would check via config service in production)
        has_previous_scan = False  # Simplified
        if has_previous_scan:
            tools_to_run.append("echidna")
            reasoning.append("echidna: contract has changed since last fuzz")

        log.info(
            "scanner_agent_plan",
            address=address,
            tools=tools_to_run,
            lines=total_lines,
        )

        # ── ACT: Run selected tools ──
        all_findings = []
        tool_outputs = {}

        for tool in tools_to_run:
            try:
                result = await self._run_tool(tool, sources, address, chain)
                if result.get("success"):
                    all_findings.extend(result.get("findings", []))
                    tool_outputs[tool] = {
                        "status": "completed",
                        "findings_count": len(result.get("findings", [])),
                    }
                else:
                    tool_outputs[tool] = {
                        "status": "failed",
                        "error": result.get("error", "Unknown error"),
                    }
            except Exception as exc:
                tool_outputs[tool] = {
                    "status": "error",
                    "error": str(exc),
                }

        return {
            "findings": all_findings,
            "tool_outputs": tool_outputs,
            "tools_run": tools_to_run,
            "reasoning": reasoning,
            "summary": (
                f"Ran {len(tools_to_run)} tools: {', '.join(tools_to_run)}. "
                f"Found {len(all_findings)} findings total."
            ),
            "_steps": len(tools_to_run),
            "_strategy": {
                "tools": tools_to_run,
                "reasoning": reasoning,
            },
        }

    async def _run_tool(
        self, tool: str, sources: dict[str, str], address: str, chain: str
    ) -> dict[str, Any]:
        """Run a specific scanning tool via internal HTTP call."""
        # Map tool to internal service URL
        tool_urls = {
            "slither": "http://04a-scanner-slither:8014/scan",
            "mythril": "http://05-scanner-mythril:8013/scan",
            "echidna": "http://04b-scanner-echidna:8015/scan",
            "halmos": "http://04d-scanner-halmos:8017/scan",
        }
        
        url = tool_urls.get(tool)
        if url is None:
            return {"success": False, "error": f"Unknown tool: {tool}"}

        resp = await self._http_client.post(
            url,
            json={"sources": sources, "address": address, "chain": chain},
            timeout=300.0,  # 5 minutes max per tool
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", data)
```

**Step 2: Modify `services/04-scanner/app.py` — add agent endpoints**

Add to the FastAPI app:

```python
from src.agent_loop import ScannerAgent
from services.shared.agent_protocol.models import DelegationRequest, NegotiationRequest

# Add to startup
scanner_agent = ScannerAgent(http_client=...)  # init with shared client

@app.get("/agent/manifest")
async def agent_manifest():
    return ok(scanner_agent.get_manifest().__dict__)

@app.post("/agent/delegate")
async def agent_delegate(body: dict):
    request = DelegationRequest(**body)
    response = await scanner_agent.handle_delegation(request)
    return ok(response.__dict__)

@app.post("/agent/negotiate")
async def agent_negotiate(body: dict):
    request = NegotiationRequest(**body)
    response = await scanner_agent.handle_negotiation(request)
    return ok(response.__dict__)
```

**Verification:**
```bash
cd services/04-scanner && python -c "from src.agent_loop import ScannerAgent; print('OK')"
```

**Commit:**
```bash
git add services/04-scanner/src/agent_loop.py services/04-scanner/app.py
git commit -m "feat(agent-04-scanner): add backend agent with tool selection intelligence"
```


## Phase 4: Integration & Testing

### Task 4.1: End-to-End Integration Test

**Objective:** Buat integration test yang mensimulasikan Main Agent → Backend Agent flow.

**Files:**
- Create: `tests/integration/test_hybrid_flow.py`

**Step 1: Create the test**

```python
"""Integration test for Hybrid Agent Architecture.

Tests the full flow:
1. Backend agents register via manifest
2. Main Agent discovers agents
3. Main Agent creates a plan
4. Main Agent delegates to backend agents
5. Backend agents execute and return results
6. Main Agent synthesizes results
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.shared.agent_protocol.models import (
    AgentCapability,
    AgentManifest,
    DelegationRequest,
    DelegationResponse,
    NegotiationRequest,
    NegotiationResponse,
    TaskStatus,
    generate_task_id,
)
from services.shared.agent_protocol.registry import AgentRegistry


@pytest.mark.asyncio
async def test_agent_discovery():
    """Test that Main Agent can discover backend agents."""
    registry = AgentRegistry()
    registry._known_services = {
        "06-ai": "http://mock-06-ai:8000",
    }
    
    # Mock HTTP response
    mock_manifest = {
        "service_name": "06-ai",
        "agent_role": "vulnerability_analyst",
        "version": "0.1.0",
        "capabilities": [
            {
                "name": "classify_findings",
                "description": "Classify findings",
                "input_schema": {},
                "output_schema": {},
                "estimated_duration_ms": 30000,
                "estimated_cost_usd": 0.05,
                "confidence": 0.85,
            }
        ],
        "constraints": {"max_concurrent_tasks": 3},
        "current_load": {"active_tasks": 0, "queue_depth": 0, "status": "idle"},
    }
    
    with patch.object(registry._http_client, 'get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={"data": mock_manifest})
        mock_get.return_value = mock_response
        
        manifests = await registry.discover_all()
        
        assert len(manifests) == 1
        assert manifests[0].service_name == "06-ai"
        assert manifests[0].agent_role == "vulnerability_analyst"


@pytest.mark.asyncio
async def test_agent_capability_lookup():
    """Test finding agents by capability."""
    registry = AgentRegistry()
    
    # Manually add a mock agent
    from services.shared.agent_protocol.models import CapabilityDefinition
    
    registry._agents["06-ai"] = AgentManifest(
        service_name="06-ai",
        agent_role="vulnerability_analyst",
        version="0.1.0",
        capabilities=[
            CapabilityDefinition(
                name=AgentCapability.CLASSIFY_FINDINGS,
                description="Classify findings",
            )
        ],
        current_load={"active_tasks": 0, "queue_depth": 0, "status": "idle"},
    )
    
    # Find by capability
    results = registry.find_agents_by_capability(AgentCapability.CLASSIFY_FINDINGS)
    assert len(results) == 1
    assert results[0][0] == "06-ai"
    
    # Find non-existent capability
    results = registry.find_agents_by_capability(AgentCapability.RUN_FUZZING)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_delegation_flow():
    """Test full delegation flow from Main Agent to Backend Agent."""
    from services.shared.agent_protocol.base_agent import BaseAgent
    
    # Create a simple test agent
    class TestAgent(BaseAgent):
        async def _execute_task(self, request):
            return {"result": f"Processed: {request.goal}", "_steps": 1}
    
    agent = TestAgent(
        service_name="test-agent",
        agent_role="test_role",
    )
    agent._max_concurrent = 5
    
    from services.shared.agent_protocol.models import CapabilityDefinition
    agent.register_capability(CapabilityDefinition(
        name=AgentCapability.CLASSIFY_FINDINGS,
        description="Test capability",
    ))
    
    # Create delegation request
    request = DelegationRequest(
        task_id=generate_task_id(),
        goal="Test task",
        capability=AgentCapability.CLASSIFY_FINDINGS,
        input_data={"key": "value"},
    )
    
    # Handle delegation
    response = await agent.handle_delegation(request)
    
    assert response.status == TaskStatus.COMPLETED
    assert response.output["result"] == "Processed: Test task"
    assert response.duration_ms > 0


@pytest.mark.asyncio
async def test_negotiation_flow():
    """Test negotiation between Main Agent and Backend Agent."""
    from services.shared.agent_protocol.base_agent import BaseAgent
    
    class TestAgent(BaseAgent):
        async def _execute_task(self, request):
            return {"result": "ok"}
    
    agent = TestAgent(service_name="test", agent_role="test")
    
    from services.shared.agent_protocol.models import CapabilityDefinition
    agent.register_capability(CapabilityDefinition(
        name=AgentCapability.CLASSIFY_FINDINGS,
        description="Test",
    ))
    
    # Test: agent can handle the task
    request = NegotiationRequest(
        task_description="Test",
        required_capability=AgentCapability.CLASSIFY_FINDINGS,
    )
    response = await agent.handle_negotiation(request)
    assert response.can_handle is True
    
    # Test: agent cannot handle unknown capability
    request = NegotiationRequest(
        task_description="Test",
        required_capability=AgentCapability.RUN_FUZZING,
    )
    response = await agent.handle_negotiation(request)
    assert response.can_handle is False


@pytest.mark.asyncio
async def test_agent_at_capacity():
    """Test that agent rejects tasks when at capacity."""
    from services.shared.agent_protocol.base_agent import BaseAgent
    
    class TestAgent(BaseAgent):
        async def _execute_task(self, request):
            import asyncio
            await asyncio.sleep(0.1)  # Simulate work
            return {"result": "ok"}
    
    agent = TestAgent(service_name="test", agent_role="test")
    agent._max_concurrent = 1  # Only 1 concurrent task
    
    from services.shared.agent_protocol.models import CapabilityDefinition
    agent.register_capability(CapabilityDefinition(
        name=AgentCapability.CLASSIFY_FINDINGS,
        description="Test",
    ))
    
    # Start first task (don't await it — let it run)
    request1 = DelegationRequest(
        task_id=generate_task_id(),
        goal="Task 1",
        capability=AgentCapability.CLASSIFY_FINDINGS,
        input_data={},
    )
    task1 = asyncio.create_task(agent.handle_delegation(request1))
    await asyncio.sleep(0.01)  # Let it start
    
    # Second task should be deferred
    request2 = DelegationRequest(
        task_id=generate_task_id(),
        goal="Task 2",
        capability=AgentCapability.CLASSIFY_FINDINGS,
        input_data={},
    )
    response2 = await agent.handle_delegation(request2)
    
    assert response2.status == TaskStatus.DEFERRED
    
    # Wait for first task
    await task1
```

**Step 2: Run the test**

```bash
cd /mnt/e/website/project/sc_auditor && python -m pytest tests/integration/test_hybrid_flow.py -v
```

Expected: 5 passed

**Commit:**
```bash
git add tests/integration/test_hybrid_flow.py
git commit -m "test: add integration tests for hybrid agent architecture"
```


## Summary of All Tasks

| Phase | Task | Files | Est. Time |
|-------|------|-------|-----------|
| 0.1 | Shared protocol models | 2 new files | 15 min |
| 0.2 | BaseAgent class | 1 new file | 15 min |
| 0.3 | AgentRegistry | 1 new file | 15 min |
| 1.1 | Planning phase | 1 new, 1 modified | 20 min |
| 1.2 | Delegation skill | 1 new, 1 modified | 20 min |
| 1.3 | Manifest endpoints | 1 modified | 10 min |
| 2.1 | 06-AI agent layer | 1 new, 1 modified | 30 min |
| 3.1 | 04-Scanner agent layer | 1 new, 1 modified | 25 min |
| 4.1 | Integration tests | 1 new file | 20 min |
| **Total** | **9 tasks** | **10 new + 5 modified** | **~170 min** |
