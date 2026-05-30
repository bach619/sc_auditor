# VYPER TUI — Enhanced Architecture Document
## Terminal Command Center untuk Smart Contract Security Platform

> **VYPER TUI v2** — Terminal User Interface generasi berikutnya untuk memonitor, mengendalikan,
> dan berinteraksi dengan seluruh ekosistem VYPER: 20 microservice, pipeline audit 10-stage,
> Antonio AI Agent (ReAct + Team + Daemon), Agent Protocol, observability stack, dan real-time
> event streaming — semuanya dari satu terminal.

> **Filosofi:** *Jangan hanya tahu sehat/sakit — rasakan denyut nadi, pahami pikiran, kendalikan aliran.*

---

## Daftar Isi

1. [Visi & Filosofi Arsitektur](#1-visi--filosofi-arsitektur)
2. [Arsitektur Sistem — Event-Driven TUI](#2-arsitektur-sistem--event-driven-tui)
3. [Komponen Utama](#3-komponen-utama)
   - 3.1 [EventBus — Ganti Polling dengan Streaming](#31-eventbus--ganti-polling-dengan-streaming)
   - 3.2 [ActivityMonitor v2 — Multi-Source Intelligence](#32-activitymonitor-v2--multi-source-intelligence)
   - 3.3 [PipelineTracker — State Machine Visual](#33-pipelinetracker--state-machine-visual)
   - 3.4 [AntonioPanel — ReAct Loop Live](#34-antoniopanel--react-loop-live)
   - 3.5 [TeamOpsPanel — Multi-Agent Team Mode](#35-teamopspanel--multi-agent-team-mode)
   - 3.6 [AgentProtocolPanel — Manifest & Delegation](#36-agentprotocolpanel--manifest--delegation)
   - 3.7 [MetricsPanel — Confusion Matrix & Learning](#37-metricspanel--confusion-matrix--learning)
   - 3.8 [ResourcePanel — Governor & Queue](#38-resourcepanel--governor--queue)
   - 3.9 [ChatPanel v2 — Full Command Registry](#39-chatpanel-v2--full-command-registry)
4. [Desain Layout — Multi-Mode TUI](#4-desain-layout--multi-mode-tui)
   - 4.1 [Mode FULL — 7-Panel Command Center](#41-mode-full--7-panel-command-center)
   - 4.2 [Mode AUDIT — Pipeline Focus](#42-mode-audit--pipeline-focus)
   - 4.3 [Mode AGENT — Antonio Focus](#43-mode-agent--antonio-focus)
   - 4.4 [Mode COMPACT — Headless/SSH](#44-mode-compact--headlesssh)
5. [Real-Time Event Streaming (SSE)](#5-real-time-event-streaming-sse)
6. [Motion & Visualization System v2](#6-motion--visualization-system-v2)
7. [Slash Command Registry — 40+ Commands](#7-slash-command-registry--40-commands)
8. [Pipeline State Machine Visualization](#8-pipeline-state-machine-visualization)
9. [Antonio Integration — ReAct, Team, Daemon, Memory](#9-antonio-integration--react-team-daemon-memory)
10. [Observability Layer — OpenTelemetry di Terminal](#10-observability-layer--opentelemetry-di-terminal)
11. [Keyboard Navigation & Power User Shortcuts](#11-keyboard-navigation--power-user-shortcuts)
12. [State Management — Reactive Architecture](#12-state-management--reactive-architecture)
13. [Konfigurasi Lengkap](#13-konfigurasi-lengkap)
14. [Deployment — Docker, systemd, SSH](#14-deployment--docker-systemd-ssh)
15. [Diagram Arsitektur Lengkap](#15-diagram-arsitektur-lengkap)
16. [Extension Guide](#16-extension-guide)
17. [Lampiran: Contoh Sesi Lengkap](#17-lampiran-contoh-sesi-lengkap)

---

## 1. Visi & Filosofi Arsitektur

### 1.1 Problem Space

VYPER versi sebelumnya memiliki TUI yang baik sebagai *health monitor* — menampilkan status service dan spinner aktivitas. Namun seluruh kekayaan informasi sistem belum tersurface:

| Informasi Tersembunyi | Dampak |
|----------------------|--------|
| Pipeline audit berada di stage mana | Operator buta terhadap progress audit aktif |
| Antonio sedang berpikir apa (ReAct step) | Black box — tidak ada visibility ke reasoning |
| Sub-agent mana yang sedang bekerja | Team mode tidak tervisualisasi |
| Resource governor slot tersedia/terpakai | Tidak bisa predict bottleneck |
| TP/FP metrics per tool real-time | Feedback loop tidak terasa |
| Agent Protocol delegation chain | Multi-agent flow tidak terlacak |
| Memory Antonio — apa yang "diingat" | Konteks agent tidak transparan |

### 1.2 Prinsip Desain v2

```
PRINSIP 1 — Event-Driven, bukan Poll-Driven
  Ganti polling periodik dengan SSE stream dari 15-Dashboard.
  Latency: 1000ms polling → <50ms event push.

PRINSIP 2 — Depth-on-Demand
  Default: ringkas dan bersih.
  Drill-down: tekan satu tombol → full detail panel.
  Operator tidak dibanjiri informasi kecuali diminta.

PRINSIP 3 — Antonio sebagai Co-Pilot, bukan Chatbot
  Antonio bisa bertanya balik ke operator, memberi saran,
  melaporkan anomali — bukan hanya menjawab.

PRINSIP 4 — Setiap Pixel Membawa Makna
  Tidak ada elemen dekoratif. Warna = status.
  Gerakan = aktivitas nyata. Diam = idle nyata.

PRINSIP 5 — Terminal-First, Remote-Ready
  Bekerja sempurna via SSH, tmux, screen.
  No mouse dependency untuk operasi kritis.
```

---

## 2. Arsitektur Sistem — Event-Driven TUI

### 2.1 Arsitektur Tingkat Tinggi

```
╔══════════════════════════════════════════════════════════════════════╗
║                        VYPER TUI v2 (Textual)                        ║
║                                                                      ║
║  ┌──────────────────────────────────────────────────────────────┐   ║
║  │                    LAYOUT MANAGER                            │   ║
║  │  (mengelola mode: FULL / AUDIT / AGENT / COMPACT)           │   ║
║  └──────────────────────────────────────────────────────────────┘   ║
║         │              │              │              │               ║
║         ▼              ▼              ▼              ▼               ║
║  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   ║
║  │Layer     │  │Pipeline  │  │Antonio   │  │  Metrics &       │   ║
║  │Panels    │  │Tracker   │  │Panel     │  │  Resource Panel  │   ║
║  │(6 layer) │  │(10-stage)│  │(ReAct)   │  │  (TP/FP/Slots)  │   ║
║  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘   ║
║                                                                      ║
║  ┌──────────────────────────────────────────────────────────────┐   ║
║  │  ChatPanel v2 (Antonio + 40+ Slash Commands + Co-Pilot mode) │   ║
║  └──────────────────────────────────────────────────────────────┘   ║
║                                                                      ║
║  ┌──────────────────────────────────────────────────────────────┐   ║
║  │  StatusBar (audit aktif | resource slots | uptime | model)   │   ║
║  └──────────────────────────────────────────────────────────────┘   ║
╚══════════════════════════════════════════════════════════════════════╝
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
     ┌──────────────┐ ┌─────────────┐ ┌────────────────┐
     │  EventBus    │ │ StateStore  │ │ CommandRouter  │
     │  (SSE/WS)    │ │ (reactive)  │ │ (slash cmds)   │
     └──────┬───────┘ └─────────────┘ └────────────────┘
            │
            ▼ HTTP SSE stream
┌───────────────────────────────────────────────────────────┐
│           15-Dashboard (port 8000) — SSE Hub              │
│  GET /events (SSE) — unified event stream dari semua svc  │
└──────────────────────────┬────────────────────────────────┘
                           │ internal HTTP
                           ▼
┌──────────────────────────────────────────────────────────┐
│                  VYPER Backend Services                  │
│  01-Config  02-Immunefi  03-Source  04-Scanner  ...     │
│  11-Orchestrator  14-Agent(Antonio)  07-Classifier  ... │
└──────────────────────────────────────────────────────────┘
```

### 2.2 Keunggulan Event-Driven vs Polling

| Aspek | Polling (v1) | SSE Event-Driven (v2) |
|-------|-------------|----------------------|
| **Latency update** | 1000ms interval | <50ms push |
| **Network load** | N_services × requests/detik | 1 persistent connection |
| **Missed events** | Possible (between polls) | Zero missed events |
| **CPU overhead** | Tinggi (loop aktif) | Minimal (wait for event) |
| **Service load** | `/activity` → 20 services × 1/s | Dashboard hub aggregates |
| **Backpressure** | Tidak ada | Built-in (SSE buffer) |

### 2.3 Service Topology yang Dimonitor

TUI merepresentasikan 20 service dalam 6 layer sesuai arsitektur VYPER:

```
Layer 1 — Data & Config     : 01-Config(8011), 02-Immunefi(8001), 03-Source(8002)
Layer 2 — Processing        : 04-Scanner(8003), 04a-Slither(8014), 04b-Echidna(8015)
                              04c-Forge(8016), 04d-Halmos(8017), 05-Mythril(8013)
Layer 3 — Intelligence      : 06-AI(8004), 07-Classifier(8005)
Layer 4 — Exploit & Output  : 08-Exploit(8006), 09-Reporter(8007), 10-Notifier(8008)
Layer 5 — Orchestration     : 11-Orchestrator(8009), 14-Agent/Antonio(8021)
Layer 6 — Infra & Delivery  : 12-Webhook(8010), 13-Upkeep(8012), 15-Dashboard(8000)
                              16-Submission(8018)
```

---

## 3. Komponen Utama

### 3.1 EventBus — Ganti Polling dengan Streaming

`EventBus` adalah komponen core yang menggantikan `ActivityMonitor` berbasis polling.

**Arsitektur EventBus:**

```python
# src/core/event_bus.py

from textual import work
import httpx
import asyncio
from dataclasses import dataclass

@dataclass
class VyperEvent:
    event_type: str          # "service.activity" | "audit.state_change" | ...
    service: str             # "04-scanner" | "11-orchestrator" | ...
    payload: dict            # Data event
    timestamp: str           # ISO 8601
    trace_id: str | None     # OpenTelemetry trace ID (jika tersedia)

class EventBus:
    """
    Subscribe ke SSE stream dari 15-Dashboard.
    Parse event dan dispatch ke handler yang terdaftar.
    """

    EVENT_ENDPOINT = "http://localhost:8000/events"

    def __init__(self, app: "VyperTUI"):
        self.app = app
        self.handlers: dict[str, list[callable]] = {}
        self._reconnect_delay = 1.0   # detik, exponential backoff

    def on(self, event_type: str):
        """Decorator untuk register handler."""
        def decorator(fn):
            self.handlers.setdefault(event_type, []).append(fn)
            return fn
        return decorator

    @work(exclusive=True, thread=False)
    async def connect(self):
        """Persistent SSE connection dengan auto-reconnect."""
        while True:
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream("GET", self.EVENT_ENDPOINT) as r:
                        self._reconnect_delay = 1.0   # reset on success
                        async for line in r.aiter_lines():
                            if line.startswith("data:"):
                                raw = line[5:].strip()
                                event = VyperEvent(**json.loads(raw))
                                await self._dispatch(event)
            except Exception:
                # Exponential backoff: 1s, 2s, 4s, max 30s
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 30.0)

    async def _dispatch(self, event: VyperEvent):
        for handler in self.handlers.get(event.event_type, []):
            await handler(event)
        for handler in self.handlers.get("*", []):    # wildcard handlers
            await handler(event)
```

**Event Types yang Dikirim oleh 15-Dashboard:**

```
service.activity        → status busy/idle/pending/error + task description
service.health          → health check result berubah (up/down)
audit.state_change      → pipeline pindah ke stage baru
audit.finding           → finding baru ditemukan
audit.completed         → audit selesai
agent.step              → Antonio selesaikan satu ReAct step
agent.delegation        → Antonio mendelegasikan task ke sub-agent
agent.thought           → Antonio reasoning (THINK phase)
agent.skill_call        → Antonio memanggil skill (ACT phase)
agent.observation       → Antonio menerima hasil skill (OBSERVE phase)
daemon.cycle            → Daemon menyelesaikan satu cycle
resource.slot_change    → Scanner/AI/Exploit slot berubah
metric.update           → TP/FP/TN/FN metrics diperbarui
memory.stored           → Antonio menyimpan ke vector/episodic memory
```

**Implementasi SSE Hub di 15-Dashboard:**

```python
# services/15-dashboard/src/sse_hub.py

from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse
import asyncio

event_queue = asyncio.Queue(maxsize=1000)

@app.get("/events")
async def sse_events(request: Request):
    """Single SSE endpoint — semua client subscribe ke sini."""
    async def generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=30)
                yield {"data": json.dumps(event)}
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": ""}  # keep-alive

    return EventSourceResponse(generator())


# Setiap service push event via internal HTTP ke Dashboard:
# POST /internal/publish  { event_type, service, payload }
```

---

### 3.2 ActivityMonitor v2 — Multi-Source Intelligence

ActivityMonitor v2 tidak lagi polling — ia hanya memproses event dari EventBus dan memaintain state cache.

```python
# src/monitors/activity_monitor.py

class ActivityMonitorV2:
    """
    State cache untuk activity semua service.
    Diperbarui oleh EventBus, bukan polling.
    """

    def __init__(self, event_bus: EventBus):
        self._cache: dict[str, ServiceActivity] = {}
        self._sparklines: dict[str, deque] = {}   # CPU/latency 60-sample window

        # Register handler
        @event_bus.on("service.activity")
        async def handle_activity(event: VyperEvent):
            self._cache[event.service] = ServiceActivity(
                status=event.payload["status"],
                task=event.payload.get("task", ""),
                progress=event.payload.get("progress"),
                started_at=event.payload.get("started_at"),
                trace_id=event.trace_id,
                updated_at=datetime.now(),
            )
            # Update sparkline (CPU proxy: busy=100, idle=0, pending=50)
            self._sparklines.setdefault(event.service, deque(maxlen=60))
            cpu_proxy = {"busy": 100, "idle": 0, "pending": 50, "error": 0}
            self._sparklines[event.service].append(
                cpu_proxy.get(event.payload["status"], 0)
            )

    def get(self, service: str) -> ServiceActivity | None:
        return self._cache.get(service)

    def get_busy_services(self) -> list[str]:
        return [s for s, a in self._cache.items() if a.status == "busy"]

    def get_sparkline(self, service: str) -> list[int]:
        return list(self._sparklines.get(service, []))
```

**Data model `ServiceActivity`:**

```python
@dataclass
class ServiceActivity:
    status: Literal["idle", "busy", "pending", "error", "unknown"]
    task: str = ""
    progress: int | None = None     # 0-100 jika service support
    started_at: str | None = None
    trace_id: str | None = None     # link ke distributed trace
    updated_at: datetime = field(default_factory=datetime.now)
    p95_latency_ms: float | None = None   # dari Prometheus jika tersedia
```

---

### 3.3 PipelineTracker — State Machine Visual

Komponen baru yang menampilkan progress audit aktif dalam pipeline 10-stage.

```
PIPELINE TRACKER — 3 Audit Aktif
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
aud_001 [0x4c9edd... / USDe / Ethena]   ████████░░░░░ 67% AI_ANALYSIS
  PEND→PROG→SRC→SCAN→HALMOS→[AI]→CLASS→EXP→RPT→NOTIF→DONE
                                    ↑ here

aud_002 [0xdAC17F... / USDT / Tether]   ██░░░░░░░░░░░ 20% SCANNING
  PEND→PROG→SRC→[SCAN]→HALMOS→AI→CLASS→EXP→RPT→NOTIF→DONE
                        ↑ here   (slither: 45% ████████░░░░░░░░░)

aud_003 [0xA0b86... / USDC / Circle]    ░░░░░░░░░░░░░  0% PENDING
  [PEND]→PROG→SRC→SCAN→HALMOS→AI→CLASS→EXP→RPT→NOTIF→DONE
```

```python
# src/panels/pipeline_tracker.py

class PipelineTracker(Widget):
    """
    Subscribe ke audit.state_change events.
    Tampilkan progress bar per audit dengan stage indicator.
    """

    PIPELINE_STAGES = [
        "pending", "fetching_program", "fetching_source", "scanning",
        "halmos_analysis", "ai_analysis", "classifying", "exploiting",
        "reporting", "notifying", "completed"
    ]

    STAGE_WEIGHT = {               # bobot untuk progress bar
        "pending": 0, "fetching_program": 5, "fetching_source": 10,
        "scanning": 35, "halmos_analysis": 50, "ai_analysis": 60,
        "classifying": 70, "exploiting": 80, "reporting": 90,
        "notifying": 95, "completed": 100,
    }

    def on_mount(self):
        self.event_bus.on("audit.state_change")(self._handle_state_change)
        self.event_bus.on("audit.completed")(self._handle_completed)

    async def _handle_state_change(self, event: VyperEvent):
        audit_id = event.payload["audit_id"]
        new_state = event.payload["state"]
        self._audits[audit_id]["state"] = new_state
        self._audits[audit_id]["progress"] = self.STAGE_WEIGHT[new_state]
        self.refresh()
```

---

### 3.4 AntonioPanel — ReAct Loop Live

Panel yang menampilkan step-by-step ReAct loop Antonio secara real-time.

```
╭─ ANTONIO — Lead Auditor (ReAct Loop) ──────────────────── session: agent-abc123 ─╮
│ Task: Full audit USDe contract [0x4c9edd...] — Step 7/25                         │
│                                                                                   │
│ [5] THOUGHT ─────────────────────────────────────────────────────────────────── │
│   "Source fetched. 12 files, 3.2k LOC. I should run static analysis first        │
│    with Slither before moving to symbolic execution."                             │
│                                                                                   │
│ [5] ACTION → scan_contract                                                       │
│   {"contract_address": "0x4c9edd...", "chain": "ethereum", "tools": ["slither"]} │
│                                                                                   │
│ [5] OBSERVE ← 04-Scanner                                                        │
│   "Slither complete: 7 findings (2 HIGH, 3 MEDIUM, 2 LOW)"                      │
│                                                                                   │
│ [6] THOUGHT ─────────────────────────────────────────────────────────────────── │
│   "2 HIGH findings found. Running Mythril for symbolic verification..."           │
│                                                                                   │
│ [7] ACTION → scan_contract    ⣾ RUNNING ...                                     │
│   {"contract_address": "0x4c9edd...", "chain": "ethereum", "tools": ["mythril"]} │
│                                                                                   │
│  LLM: claude-sonnet-4-6 ◆  Memory: 127 entries  ◆  Skills used: 4/10           │
╰──────────────────────────────────────────────────────────────────────────────────╯
```

```python
# src/panels/antonio_panel.py

class AntonioPanel(Widget):
    """Real-time ReAct loop visualization."""

    MAX_VISIBLE_STEPS = 8   # auto-scroll ke step terbaru

    def on_mount(self):
        self.event_bus.on("agent.thought")(self._on_thought)
        self.event_bus.on("agent.skill_call")(self._on_action)
        self.event_bus.on("agent.observation")(self._on_observe)
        self.event_bus.on("agent.delegation")(self._on_delegation)

    async def _on_thought(self, event: VyperEvent):
        step = event.payload["step_number"]
        thought = event.payload["thought"]
        self._steps.append(ReactStep(
            number=step, phase="THOUGHT", content=thought
        ))
        self._auto_scroll()

    async def _on_action(self, event: VyperEvent):
        step = event.payload["step_number"]
        skill = event.payload["skill_name"]
        args = event.payload["action_input"]
        self._steps.append(ReactStep(
            number=step, phase="ACTION",
            content=f"→ {skill}",
            detail=json.dumps(args, indent=2)
        ))
        self._set_skill_running(skill)

    async def _on_observe(self, event: VyperEvent):
        step = event.payload["step_number"]
        result = event.payload["observation_summary"]
        source = event.payload["source_service"]
        self._steps.append(ReactStep(
            number=step, phase="OBSERVE",
            content=f"← {source}: {result}"
        ))
        self._clear_skill_running()
```

---

### 3.5 TeamOpsPanel — Multi-Agent Team Mode

Visualisasi hierarchical AI team saat `/team run` aktif.

```
╭─ TEAM OPS — Lead Auditor Mode ─────────────────────────────────────────────────╮
│                                                                                  │
│   ┌─ LEAD AUDITOR (Antonio) ───────────────────────────────── ⣾ COORDINATING ─┐ │
│   │  "Delegating static analysis to Code Analyst..."                           │ │
│   └──────────────────────────────────────────────────────────────────────────┘ │
│          │                    │                    │                            │
│          ▼                    ▼                    ▼                            │
│  ┌─ CODE ANALYST ─┐  ┌─ EXPLOIT SPEC ─┐  ┌─ REPORT WRITER ─┐                 │
│  │ ⣾ SCANNING     │  │ 💤 idle         │  │ 💤 idle          │                 │
│  │ slither 0x4c9. │  │                │  │                  │                 │
│  │ [████░░░] 45%  │  │                │  │                  │                 │
│  └────────────────┘  └────────────────┘  └──────────────────┘                 │
│                                                                                  │
│  CLASSIFIER: ⏳ pending  │  Delegation chain: Lead→CodeAnalyst (in-progress)   │
╰──────────────────────────────────────────────────────────────────────────────────╯
```

---

### 3.6 AgentProtocolPanel — Manifest & Delegation

Visualisasi Agent Protocol — manifest, discovery, delegation.

```
╭─ AGENT PROTOCOL — Registry ──────────────────────────────────────────────────────╮
│  4 Agents Registered                                                              │
│                                                                                   │
│  Service           Role              Capabilities              Load    Status     │
│  ──────────────────────────────────────────────────────────────────────────────  │
│  14-agent          antonio           scan,analyze,exploit,rpt  1/5     ✅ active  │
│  11-orchestrator   pipeline-coord    audit,queue,schedule       3/∞     ✅ active  │
│  08-exploit        exploit-spec      exploit,poc-gen            0/1     ✅ idle    │
│  09-reporter       report-writer     report,submit              0/∞     ✅ idle    │
│                                                                                   │
│  DELEGATION LOG ──────────────────────────────────────────────────────────────── │
│  [10:23:41] antonio → 08-exploit  "run exploit for finding vuln_001"  ⣾ pending  │
│  [10:22:17] antonio → 11-orch     "check queue for 0x4c9edd..."       ✅ done     │
│  [10:21:55] 11-orch → 04-scanner  "scan 0x4c9edd... slither+mythril"  ✅ done     │
╰──────────────────────────────────────────────────────────────────────────────────╯
```

---

### 3.7 MetricsPanel — Confusion Matrix & Learning

```
╭─ METRICS — Platform Performance ──────────────────────────────────────────────────╮
│  Tool Accuracy (last 200 audits)                                                  │
│                                                                                   │
│  Tool          TP    FP    TN    FN    Precision  Recall    F1                   │
│  ────────────────────────────────────────────────────────────────────────────    │
│  Slither        87    23     0    12    79.1%      87.9%     83.3%               │
│  Mythril        61     8     0     5    88.4%      92.4%     90.3%               │
│  Echidna        34     3     0     2    91.9%      94.4%     93.2%               │
│  Halmos         28     1     0     1    96.6%      96.6%     96.6%               │
│  AI (Claude)    94     4     0     3    95.9%      96.9%     96.4%               │
│                                                                                   │
│  RECENT FINDINGS ─────────────────────────────────────────────────────────────── │
│  [10:24:01] aud_001  reentrancy          HIGH   → AI: TP  Slither: TP           │
│  [10:19:33] aud_002  integer-overflow    MEDIUM → AI: TP  Mythril: FP ⚠️         │
│  [10:15:12] aud_001  unchecked-call      LOW    → AI: TP  Slither: TP           │
│                                                                                   │
│  FALSE NEGATIVE PATTERNS (top 3)                                                 │
│  access-control-complex  · flash-loan-price-manip  · read-only-reentrancy       │
╰──────────────────────────────────────────────────────────────────────────────────╯
```

---

### 3.8 ResourcePanel — Governor & Queue

```
╭─ RESOURCE GOVERNOR ──────────────────────────────────────────────────────────────╮
│                                                                                   │
│  Scanner Slots   [██░░] 1/2 used   AI Slots   [░░░] 0/3 used                    │
│  Exploit Slots   [░░░░] 0/1 used   Timeout    Scanner:900s  AI:120s  Exp:300s   │
│                                                                                   │
│  PRIORITY QUEUE (5 pending)                                                      │
│  ──────────────────────────────────────────────────────────────────────────────  │
│  Rank  Audit ID   Contract         Score   Wait     Program                     │
│   1    aud_004    0x1f97...        9.2     00:04    Aave V3 (critical)          │
│   2    aud_005    0x7fc...         8.7     00:02    Compound V3                 │
│   3    aud_006    0xBeef...        6.1     00:08    Uniswap V4                  │
│   4    aud_007    0x3fC...         4.3     00:15    Curve Finance               │
│   5    aud_008    0x5e28...        3.1     00:22    Lido                        │
│                                                                                   │
│  /boost aud_007 +3.0   /pause   /resume   /clear-queue                         │
╰──────────────────────────────────────────────────────────────────────────────────╯
```

---

### 3.9 ChatPanel v2 — Full Command Registry

ChatPanel v2 mewarisi antarmuka Antonio dengan penambahan autocomplete, history, dan co-pilot mode.

```python
# src/panels/chat_panel.py

class ChatPanelV2(Widget):
    """
    Input bar dengan:
    - Slash command autocomplete (TAB)
    - Command history (↑↓)
    - Co-pilot mode: Antonio push saran tanpa diminta
    - Multi-line input (Shift+Enter)
    """

    def on_key(self, event: Key):
        if event.key == "tab":
            self._trigger_autocomplete()
        elif event.key == "up":
            self._history_prev()
        elif event.key == "down":
            self._history_next()
        elif event.key == "escape":
            self._cancel_current_command()

    async def _on_copilot_suggestion(self, event: VyperEvent):
        """
        Antonio bisa push saran tanpa user bertanya.
        Tampilkan sebagai 'Co-pilot:' bubble, berbeda dari normal response.
        """
        suggestion = event.payload["suggestion"]
        self._add_copilot_bubble(f"💡 Co-pilot: {suggestion}")
```

---

## 4. Desain Layout — Multi-Mode TUI

### 4.1 Mode FULL — 7-Panel Command Center

Default mode. Menampilkan semua panel dalam grid.

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║  VYPER TUI v2  ■ FULL MODE  ■ 3 audits active  ■ Antonio: running  ■ 10:24:01  ║
╠══════════════════╦═══════════════════╦══════════════════════════════════════════╣
║ LAYER PANELS     ║ PIPELINE TRACKER  ║ ANTONIO — ReAct Loop                    ║
║ ──────────────── ║ ───────────────── ║ ──────────────────────────────────────  ║
║ Data & Config    ║ aud_001 ████░ 67% ║ session: agent-abc123  step 7/25        ║
║ 01 ✅ 💤  Config ║ aud_002 ██░░░ 20% ║ [7] ACTION → scan_contract ⣾ running   ║
║ 02 ✅ ⣾  Immun  ║ aud_003 ░░░░░  0% ║   {"tools": ["mythril"]}                ║
║ 03 ✅ 💤  Source ║                   ║                                          ║
║ ──────────────── ║ TEAM OPS          ║ AGENT PROTOCOL                          ║
║ Processing       ║ ───────────────── ║ ──────────────────────────────────────  ║
║ 04 ✅ ⣽  Scannr ║ Lead ⣾ coord     ║ 4 agents registered                     ║
║ 04a✅ ⣾  Slthr  ║ Code ⣾ scanning  ║ antonio → exploit  ⏳ pending            ║
║ 04b✅ ⏳  Ech   ║ Exp  💤 idle      ║ orch → scanner     ✅ done               ║
║ 04c✅ 💤  Forge  ║ Rpt  💤 idle      ║                                          ║
║ 04d✅ ⣾  Halmos ║                   ╠══════════════════════════════════════════╣
║ 05 ✅ ⣾  Myth   ║ RESOURCE GOV      ║ METRICS                                 ║
║ ──────────────── ║ ───────────────── ║ Slither  79.1% precision                ║
║ Intelligence     ║ Scanner [██░░] 1/2║ Mythril  88.4% precision                ║
║ 06 ✅ ⣾  AI     ║ AI      [░░░] 0/3 ║ AI(Cld)  95.9% precision                ║
║ 07 ✅ 💤  Class  ║ Exploit [░] 0/1   ║ FN: access-ctrl, flash-loan             ║
╠══════════════════╩═══════════════════╩══════════════════════════════════════════╣
║  Antonio AI Chat  ■ /help for 40+ commands  ■ TAB to autocomplete              ║
║  > _                                                                            ║
╠══════════════════════════════════════════════════════════════════════════════════╣
║  Scanner:1/2  AI:0/3  Exploit:0/1  ■  Queue:5  ■  LLM:claude-sonnet-4-6      ║
╚══════════════════════════════════════════════════════════════════════════════════╝
```

Aktifkan dengan: `F1` atau `/mode full`

### 4.2 Mode AUDIT — Pipeline Focus

Fokus pada pipeline aktif. Ideal saat memantau audit batch.

```
╔════════════════════════════════════════════════════════════════════╗
║  VYPER TUI  ■ AUDIT MODE  ■ F2=full  F3=agent  F4=compact         ║
╠════════════════════════════════════════════════════════════════════╣
║  PIPELINE — 3 Active Audits                                        ║
║  aud_001 ████████████░░░ 67%  AI_ANALYSIS      0x4c9edd/USDe      ║
║  aud_002 ███░░░░░░░░░░░ 20%  SCANNING          0xdAC17F/USDT      ║
║  aud_003 ░░░░░░░░░░░░░   0%  PENDING            0xA0b86/USDC      ║
║                                                                     ║
║  STAGE DETAIL: aud_002 / SCANNING                                  ║
║  ┌──────────────────────────────────────────────────────────────┐  ║
║  │ Slither     [████████████░░░░] 75%  19 findings so far      │  ║
║  │ Echidna     ⏳ pending (queued)                              │  ║
║  │ Forge       ✅ done (build OK)                               │  ║
║  │ Halmos      ⏳ pending                                       │  ║
║  │ Mythril     🔜 not started                                   │  ║
║  └──────────────────────────────────────────────────────────────┘  ║
╠════════════════════════════════════════════════════════════════════╣
║  > _                                                               ║
╚════════════════════════════════════════════════════════════════════╝
```

Aktifkan dengan: `F2` atau `/mode audit`

### 4.3 Mode AGENT — Antonio Focus

Full-screen Antonio. Ideal saat interaksi intensif dengan AI agent.

```
╔═════════════════════════════════════════════════════════════════════╗
║  ANTONIO — Lead Security Auditor  ■ AGENT MODE  ■ session-abc123   ║
╠════════════════════════════════════════════════════════════════════ ╣
║  ReAct LOOP ─────────────────────────────────────────────────────  ║
║  Step  Phase     Content                                            ║
║  ────────────────────────────────────────────────────────────────  ║
║  1     THOUGHT   "Need to get program info for 0x4c9edd..."        ║
║  1     ACTION    → fetch_program  {"address": "0x4c9edd..."}       ║
║  1     OBSERVE   ← 02-immunefi: "Ethena USDe, bounty $1M"         ║
║  2     THOUGHT   "Program found. Fetch source code next."          ║
║  2     ACTION    → fetch_source  {"address": "0x4c9edd..."}        ║
║  2     OBSERVE   ← 03-source: "12 files, 3219 LOC, Solidity 0.8"  ║
║  ...                                                                ║
║  7     ACTION    → scan_contract  ⣾ RUNNING (mythril)              ║
║                                                                     ║
║  MEMORY ──────────────────────────────────────────────────────     ║
║  Working: 8 keys  │  Vector: 127 entries  │  Episodic: 43 events  ║
║  Graph: 31 nodes  │  Last stored: "USDe reentrancy pattern"        ║
╠══════════════════════════════════════════════════════════════════  ╣
║  > _                                                               ║
║  ──────────────────────────────────────────────────────────────── ║
║  Skills: scan✓  analyze✓  classify  exploit  report  notify       ║
╚═════════════════════════════════════════════════════════════════════╝
```

Aktifkan dengan: `F3` atau `/mode agent`

### 4.4 Mode COMPACT — Headless/SSH

Mode minimal untuk koneksi bandwidth rendah atau monitoring pasif.

```
VYPER v2 [10:24:01] audits:3 queue:5 scanner:1/2 ai:0/3
SVC  01✅💤 02✅⣾ 03✅💤 04✅⣽ 05✅⣾ 06✅⣾ 07✅💤 11✅⣾ 14✅⣾
AUD  aud_001[AI 67%] aud_002[SCAN 20%] aud_003[PEND 0%]
AGENT step=7/25 skill=scan_contract running | LLM=claude-sonnet-4-6
> _
```

Aktifkan dengan: `F4` atau `/mode compact`

---

## 5. Real-Time Event Streaming (SSE)

### 5.1 SSE Event Format Standard

Semua service VYPER yang ingin berpartisipasi dalam event stream harus:

1. **Push event ke Dashboard** via internal endpoint:

```python
# Tambahkan ke setiap service di shared/event_publisher.py

class EventPublisher:
    DASHBOARD_INTERNAL = "http://15-dashboard:8000/internal/publish"

    async def publish(self, event_type: str, payload: dict):
        async with httpx.AsyncClient() as client:
            await client.post(self.DASHBOARD_INTERNAL, json={
                "event_type": event_type,
                "service": self.service_name,
                "payload": payload,
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": get_current_trace_id(),   # OTel integration
            }, timeout=2.0)   # fire-and-forget semantics
```

2. **Contoh: 04-Scanner mempublish event:**

```python
# services/04-scanner/app.py

from shared.event_publisher import EventPublisher

publisher = EventPublisher("04-scanner")

@app.post("/scan")
async def scan(request: ScanRequest):
    # Publikasikan "mulai busy"
    await publisher.publish("service.activity", {
        "status": "busy",
        "task": f"slither scanning {request.contract_address[:10]}...",
        "progress": 0,
    })

    result = await run_slither(request)

    # Publikasikan "selesai"
    await publisher.publish("service.activity", {
        "status": "idle",
        "task": "",
    })

    return result
```

3. **Contoh: 14-Agent (Antonio) mempublish ReAct steps:**

```python
# services/14-agent/src/agent.py  — dalam AgentLoop.run()

async def run(self, ...):
    while ...:
        # THINK
        decision = await self.llm.reason(...)
        await publisher.publish("agent.thought", {
            "session_id": session.session_id,
            "step_number": step,
            "thought": decision["thought"],
        })

        # ACT
        await publisher.publish("agent.skill_call", {
            "session_id": session.session_id,
            "step_number": step,
            "skill_name": decision["action"],
            "action_input": decision["action_input"],
        })

        result = await self.registry.execute(...)

        # OBSERVE
        await publisher.publish("agent.observation", {
            "session_id": session.session_id,
            "step_number": step,
            "observation_summary": str(result)[:200],
            "source_service": result.source_service,
        })
```

### 5.2 Backward Compatibility

Service yang belum mengimplementasikan `EventPublisher` tetap akan di-poll oleh **PollingFallback** — komponen yang hanya aktif untuk service yang belum mengirim event dalam 5 detik terakhir.

```python
# src/core/polling_fallback.py

class PollingFallback:
    """
    Aktif hanya untuk service yang belum push event ke SSE bus.
    Polling-based, interval 5s.
    Akan dihapus ketika semua service sudah publish.
    """
    FALLBACK_INTERVAL = 5.0

    async def poll_service(self, service_name: str, port: int):
        resp = await httpx.get(f"http://localhost:{port}/activity")
        await self.event_bus.inject(VyperEvent(
            event_type="service.activity",
            service=service_name,
            payload=resp.json(),
            source="polling_fallback",  # ditandai sebagai fallback
        ))
```

---

## 6. Motion & Visualization System v2

### 6.1 Status Visual Hierarchy

```
STATUS        VISUAL             WARNA          MAKNA
────────────────────────────────────────────────────────────────
idle          💤                 DIM GREY       Siap, menunggu tugas
busy          ⣾⣽⣻⢿⡿⣟⣯⣷         BRIGHT GREEN   Sedang memproses aktif
pending       ⏳ (blink 2Hz)     YELLOW         Dalam antrian orchestrator
error         ⚠️ (blink 1Hz)     RED            Aktivitas terakhir gagal
unknown       ?(static)          DARK GREY      Belum ada data dari service
running(PoC)  🔥 (pulse)         ORANGE         Exploit/Anvil container aktif
```

### 6.2 Sparkline — Activity History

Setiap service menampilkan sparkline 60-sample terakhir (1 menit aktivitas):

```
04-scanner  ✅  ⣾ busy    scanning 0x4c9edd... (45%)
             ▁▂▃▄▅▆▇█▇▆▅▇██████▇▆▅▄▃▂▁▂▃▄▅▆▇█▇  ← 1 menit
```

### 6.3 Progress Bar untuk Service yang Support `/activity?detail=true`

```json
{
  "status": "busy",
  "task": "slither scanning 0x4c9edd...",
  "progress": 45,
  "sub_tasks": [
    {"name": "compile", "done": true},
    {"name": "detect reentrancy", "done": true},
    {"name": "detect overflow", "done": false},
    {"name": "generate report", "done": false}
  ],
  "started_at": "2026-05-26T10:20:00Z",
  "estimated_completion": "2026-05-26T10:35:00Z"
}
```

TUI akan render:
```
04a-Slither  ⣾  [███████████░░░░░░░░░] 45%  ETA: ~15m
             compile ✓  reentrancy ✓  overflow ⣾  report ○
```

### 6.4 Exploit PoC — Special Visualization

Saat `08-exploit` menjalankan Anvil container:

```
╭─ EXPLOIT ENGINE ──────────────────────────────────────────────────────────────╮
│  🔥 Anvil container spinning up for finding: vuln_001 (reentrancy)            │
│  Chain fork: ethereum @ block 21,500,000                                      │
│  PoC script: poc_reentrancy_0x4c9edd.sol                                      │
│                                                                                │
│  [PHASE 1] Fork chain          ✅ done    (2.3s)                               │
│  [PHASE 2] Deploy attacker     ⣾ running (Foundry compile...)                 │
│  [PHASE 3] Execute attack      ○ waiting                                      │
│  [PHASE 4] Verify profit       ○ waiting                                      │
│  [PHASE 5] Generate tx proof   ○ waiting                                      │
│                                                                                │
│  Attacker contract: 0x0000... (ephemeral)   Gas used: --                      │
╰──────────────────────────────────────────────────────────────────────────────╯
```

---

## 7. Slash Command Registry — 40+ Commands

### 7.1 Audit Commands

| Command | Deskripsi | Contoh |
|---------|-----------|--------|
| `/audit <address> [chain]` | Start audit kontrak | `/audit 0x4c9edd ethereum` |
| `/audit-status <id>` | Status audit spesifik | `/audit-status aud_001` |
| `/audit-list [state]` | List semua audit | `/audit-list scanning` |
| `/audit-stop <id>` | Stop audit berjalan | `/audit-stop aud_002` |
| `/audit-retry <id>` | Retry audit gagal | `/audit-retry aud_003` |
| `/rerun <id>` | Re-run audit (retroactive) | `/rerun aud_001` |
| `/findings <id>` | Tampilkan findings | `/findings aud_001` |

### 7.2 Queue & Priority Commands

| Command | Deskripsi | Contoh |
|---------|-----------|--------|
| `/queue` | Tampilkan priority queue | |
| `/boost <id> [+N]` | Boost prioritas audit | `/boost aud_007 +3.0` |
| `/pause` | Pause processing queue | |
| `/resume` | Resume queue | |
| `/clear-queue` | Hapus semua pending | |

### 7.3 Service Management Commands

| Command | Deskripsi | Contoh |
|---------|-----------|--------|
| `/restart <service>` | Restart service | `/restart 04-scanner` |
| `/logs <service> [lines]` | Lihat logs | `/logs 06-ai 50` |
| `/health` | Health semua service | |
| `/scale <service> <n>` | Scale service | `/scale 04-scanner 3` |
| `/speed <ms>` | Set polling fallback interval | `/speed 2000` |

### 7.4 Antonio Commands

| Command | Deskripsi | Contoh |
|---------|-----------|--------|
| `/agent run <address> [chain]` | Jalankan full audit via Antonio | `/agent run 0x4c9edd eth` |
| `/team run <address>` | Jalankan team audit | `/team run 0x4c9edd` |
| `/agent-stop <session>` | Stop session agent | `/agent-stop agent-abc` |
| `/agent-status` | Status Antonio saat ini | |
| `/skills` | List 10 skills Antonio | |
| `/memory` | Tampilkan memory stats | |
| `/memory-search <query>` | Cari di vector memory | `/memory-search reentrancy` |
| `/daemon start` | Start Antonio daemon | |
| `/daemon stop` | Stop daemon | |
| `/daemon status` | Status + statistik daemon | |
| `/copilot on\|off` | Toggle co-pilot mode | `/copilot on` |

### 7.5 Motion & UI Commands

| Command | Deskripsi | Contoh |
|---------|-----------|--------|
| `/motion on\|off` | Toggle animasi | |
| `/spinner <chars>` | Custom spinner chars | `/spinner "◴◷◶◷"` |
| `/mode <mode>` | Ganti layout mode | `/mode audit` |
| `/focus <panel>` | Focus ke panel | `/focus antonio` |
| `/sparkline on\|off` | Toggle sparklines | |

### 7.6 Config & LLM Commands

| Command | Deskripsi | Contoh |
|---------|-----------|--------|
| `/model <name>` | Ganti LLM model | `/model claude-sonnet-4-6` |
| `/provider <name>` | Ganti LLM provider | `/provider anthropic` |
| `/config get <key>` | Lihat config value | `/config get scanner_timeout` |
| `/config set <key> <val>` | Set config | `/config set agent_max_steps 30` |
| `/api-key <provider>` | Set API key (prompt secure) | `/api-key anthropic` |

### 7.7 Metrics & Reports

| Command | Deskripsi | Contoh |
|---------|-----------|--------|
| `/metrics` | Tampilkan confusion matrix | |
| `/metrics tool <name>` | Metrics per tool | `/metrics tool slither` |
| `/report <id>` | Preview laporan | `/report aud_001` |
| `/report export <id>` | Export laporan ke file | `/report export aud_001` |
| `/submit <id>` | Assist submission ke Immunefi | `/submit aud_001` |
| `/similarity <address>` | Cari kontrak serupa | |

### 7.8 Observability Commands

| Command | Deskripsi | Contoh |
|---------|-----------|--------|
| `/trace <trace_id>` | Tampilkan distributed trace | |
| `/spans <service>` | Lihat OTel spans aktif | `/spans 04-scanner` |
| `/latency` | P50/P95/P99 per service | |
| `/errors` | Error rate 5 menit terakhir | |

---

## 8. Pipeline State Machine Visualization

### 8.1 State Machine 10-Stage

Visualisasi lengkap state machine Orchestrator di TUI:

```
╭─ PIPELINE: aud_001 ─────────────────────────────────────────────────────────────╮
│  0x4c9edd5852cd905f086c759e8383e09bff1e68b3  │  Chain: ethereum  │  Ethena/USDe  │
│                                                                                   │
│  [✅]PEND → [✅]PROG → [✅]SRC → [✅]SCAN → [✅]HALMOS → [⣾]AI → [ ]CLASS → ...  │
│                                                    ↑ now: AI_ANALYSIS             │
│                                                                                   │
│  STAGE HISTORY                                                                    │
│  ──────────────────────────────────────────────────────────────────────────────  │
│  ✅ fetching_program    0.8s   "Ethena USDe — bounty up to $1M"                  │
│  ✅ fetching_source     3.2s   "12 files, 3219 LOC, Solidity ^0.8.19"            │
│  ✅ scanning           127.4s  "Slither:19 Mythril:4 Echidna:0 Halmos:2 Forge:OK"│
│  ✅ halmos_analysis     44.1s  "2 formal violations confirmed"                   │
│  ⣾ ai_analysis          ?.?s  "Claude analyzing 25 findings..."  (running 28s)  │
│                                                                                   │
│  FINDINGS SO FAR: 25 total   │   Estimated TP: ~8   │   Priority: CRITICAL       │
╰──────────────────────────────────────────────────────────────────────────────────╯
```

### 8.2 State Transitions yang Dimonitor

```python
# Mapping state → emoji + warna untuk TUI display

STATE_DISPLAY = {
    "pending":           ("⏸",  "dim"),
    "fetching_program":  ("⬇",  "blue"),
    "fetching_source":   ("⬇",  "blue"),
    "scanning":          ("🔍", "yellow"),
    "halmos_analysis":   ("🔬", "yellow"),
    "ai_analysis":       ("🤖", "green"),
    "classifying":       ("🏷",  "cyan"),
    "exploiting":        ("🔥", "red"),
    "reporting":         ("📄", "blue"),
    "notifying":         ("📢", "purple"),
    "completed":         ("✅", "bright_green"),

    # Failure states
    "source_failed":     ("❌", "red"),
    "scan_failed":       ("❌", "red"),
    "ai_failed":         ("❌", "red"),
    "timeout":           ("⏱",  "red"),
    "aborted":           ("🛑", "red"),
}
```

---

## 9. Antonio Integration — ReAct, Team, Daemon, Memory

### 9.1 ReAct Loop Display (detail implementasi)

Event sequence dari satu step ReAct:

```
[TUI]                  [EventBus]              [14-Agent]
  │                        │                       │
  │                        │  ← agent.thought      │  (THINK selesai)
  │  update AntonioPanel   │                       │
  │◄───────────────────────│                       │
  │                        │  ← agent.skill_call   │  (ACT dimulai)
  │  show "⣾ running..."   │                       │
  │◄───────────────────────│                       │
  │                        │                       │  (skill HTTP call ke backend)
  │                        │  ← agent.observation  │  (OBSERVE selesai)
  │  show result + proceed │                       │
  │◄───────────────────────│                       │
```

### 9.2 Daemon Status Display

```
╭─ ANTONIO DAEMON ────────────────────────────────────────────────────────────────╮
│  Status: RUNNING  │  Uptime: 4h 23m  │  Cycle: #847                            │
│                                                                                   │
│  Task Schedule                                                                   │
│  ──────────────────────────────────────────────────────────────────────────     │
│  health_check          ✅ done    2s ago    Next: 10:25:00                      │
│  auto_hunt             ⣾ running  scanning Immunefi for new contracts...        │
│  program_sync          ✅ done    6m ago    Next: 10:30:00                      │
│  self_assessment       ✅ done    12m ago   Next: 10:36:00                      │
│  memory_consolidation  ⏳ pending           Next: 14:00:00                      │
│  stale_cleanup         ✅ done    just now                                      │
│                                                                                   │
│  Stats: sessions_today=12  findings=87  TP=71  FP=16  bounties_submitted=2     │
╰──────────────────────────────────────────────────────────────────────────────────╯
```

### 9.3 Memory Visualization

```
╭─ ANTONIO MEMORY ────────────────────────────────────────────────────────────────╮
│  Working Memory (current session)                                                │
│  contract_address: 0x4c9edd...  │  chain: ethereum  │  program: ethena          │
│  findings_count: 25  │  high_count: 4  │  current_step: 7                       │
│                                                                                   │
│  Vector Memory (127 entries) — search: /memory-search <query>                  │
│  Recent: "USDe reentrancy", "Ethena access control", "USDT integer overflow"    │
│                                                                                   │
│  Episodic Memory (43 events)                                                    │
│  [10:20:01] session agent-abc123 started — full_audit — 0x4c9edd               │
│  [10:20:04] fetch_program OK — Ethena USDe, $1M bounty                         │
│  [10:20:07] fetch_source OK — 12 files, 3219 LOC                               │
│  [10:22:11] scan_contract OK — 25 findings, 4 HIGH                             │
│                                                                                   │
│  Graph Memory (31 nodes, 47 edges)                                              │
│  Nodes: 12 contracts, 8 vulns, 5 exploits, 3 programs, 3 reports               │
╰──────────────────────────────────────────────────────────────────────────────────╯
```

---

## 10. Observability Layer — OpenTelemetry di Terminal

### 10.1 Distributed Trace Viewer

Saat user mengetik `/trace <trace_id>`, TUI menampilkan span hierarchy:

```
╭─ TRACE: 1a2b3c4d5e6f7890 ───────────────────────────────────────────────────────╮
│  audit: 0x4c9edd...  │  Total: 4m 23s  │  11-orchestrator → 5 children          │
│                                                                                   │
│  11-orchestrator      [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓] 263s total     │
│  ├─ 03-source         [▓▓▓▓] 3.2s                                               │
│  ├─ 04-scanner        [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓] 127.4s                          │
│  │  ├─ 04a-slither    [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓] 112.1s                            │
│  │  ├─ 04b-echidna    [▓▓▓▓] 22.3s                                              │
│  │  └─ 05-mythril     [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓] 168.5s (longest!)       │
│  ├─ 04d-halmos        [▓▓▓▓▓▓▓▓] 44.1s                                          │
│  └─ 06-ai             [▓▓▓▓▓▓▓▓▓▓▓▓] ⣾ running...                               │
│                                                                                   │
│  Critical Path: orchestrator→scanner→mythril (168.5s = bottleneck)              │
╰──────────────────────────────────────────────────────────────────────────────────╯
```

### 10.2 P95 Latency Monitor

```
/latency output:
Service           P50      P95      P99      Error%
────────────────────────────────────────────────────
01-config         2ms      8ms      15ms     0.0%
04-scanner        82s      127s     180s     1.2%
05-mythril        142s     211s     300s     2.1%
06-ai             28s      67s      112s     0.8%
11-orchestrator   15ms     42ms     89ms     0.3%
14-agent          85s      165s     280s     1.1%
```

---

## 11. Keyboard Navigation & Power User Shortcuts

### 11.1 Global Shortcuts

| Key | Aksi |
|-----|------|
| `F1` | Mode FULL |
| `F2` | Mode AUDIT |
| `F3` | Mode AGENT |
| `F4` | Mode COMPACT |
| `Tab` | Pindah fokus antar panel |
| `Shift+Tab` | Fokus sebelumnya |
| `Ctrl+C` | Buka command palette |
| `?` | Quick help overlay |
| `q` | Quit (dengan konfirmasi) |

### 11.2 Panel-Specific Shortcuts

| Panel | Key | Aksi |
|-------|-----|------|
| Layer Panel | `Enter` | Drill-down service detail |
| Layer Panel | `r` | Restart service yang difokus |
| Layer Panel | `l` | Buka logs panel |
| Pipeline Panel | `Enter` | Expand audit detail |
| Pipeline Panel | `s` | Stop audit |
| Antonio Panel | `Enter` | Expand step detail |
| Antonio Panel | `m` | Buka memory panel |
| Resource Panel | `b` | Boost prioritas audit pertama |
| Chat Input | `Tab` | Autocomplete slash command |
| Chat Input | `↑/↓` | Command history |
| Chat Input | `Shift+Enter` | Multi-line input |
| Chat Input | `Ctrl+L` | Clear chat |

### 11.3 Drill-Down Pattern

```
Panel list view  →  [Enter]  →  Detail panel (modal overlay)
                                    │
                                    ├─ Antonio Panel → full ReAct history
                                    ├─ Service row  → logs + metrics
                                    ├─ Audit row    → stage detail + findings
                                    └─ Trace ID     → span waterfall
```

---

## 12. State Management — Reactive Architecture

### 12.1 StateStore — Single Source of Truth

```python
# src/core/state_store.py

from textual.reactive import reactive
from dataclasses import dataclass, field

class VyperState:
    """
    Central reactive state. Semua panel subscribe ke state ini.
    Tidak ada panel yang menyimpan state sendiri.
    """

    # Service states
    service_activities: dict[str, ServiceActivity] = field(default_factory=dict)
    service_health: dict[str, bool] = field(default_factory=dict)
    service_sparklines: dict[str, list[int]] = field(default_factory=dict)

    # Pipeline states
    active_audits: dict[str, AuditRecord] = field(default_factory=dict)
    pipeline_queue: list[QueueItem] = field(default_factory=list)

    # Antonio state
    active_session: AgentSession | None = None
    daemon_status: DaemonStatus | None = None
    memory_stats: MemoryStats | None = None
    agent_protocol: AgentProtocolState | None = None

    # Resource governor
    resource_slots: ResourceSlots | None = None

    # Metrics
    classifier_metrics: dict[str, ToolMetrics] = field(default_factory=dict)

    # UI state
    current_mode: str = "full"       # full | audit | agent | compact
    focused_panel: str = "chat"
    motion_enabled: bool = True
    spinner_frame: int = 0

class AppState:
    """Singleton — satu instance per TUI."""
    _instance: VyperState = VyperState()

    @classmethod
    def update(cls, **kwargs):
        for k, v in kwargs.items():
            setattr(cls._instance, k, v)
        # Trigger Textual reactive update
        cls._app.post_message(StateUpdated(fields=list(kwargs.keys())))
```

### 12.2 Alur Update State

```
EventBus receives SSE event
    │
    ▼
EventHandler processes event
    │
    ▼
AppState.update(**payload)
    │
    ▼
StateUpdated message posted to Textual app
    │
    ▼
Subscribed panels receive StateUpdated
    │
    ▼
Panel.on_state_updated() → self.refresh()
    │
    ▼
Textual re-renders panel
```

---

## 13. Konfigurasi Lengkap

### 13.1 `~/.vyper/tui/config.yaml`

```yaml
# VYPER TUI v2 Configuration
# ────────────────────────────────────────────────────────────────

# ── Koneksi ──────────────────────────────────────────────────────
connections:
  dashboard_url: "http://localhost:8000"    # SSE hub + proxy
  orchestrator_url: "http://localhost:8009"
  agent_url: "http://localhost:8021"
  sse_reconnect_max_delay_s: 30
  health_check_interval_s: 10
  polling_fallback_interval_s: 5            # untuk service tanpa SSE

# ── Layout & UI ──────────────────────────────────────────────────
ui:
  default_mode: "full"                      # full | audit | agent | compact
  motion_enabled: true
  spinner_frames: "⣾⣽⣻⢿⡿⣟⣯⣷"
  spinner_interval_ms: 100
  blink_interval_ms: 500                    # untuk pending/error
  sparkline_window: 60                      # samples (1 menit)
  copilot_mode: true                        # Antonio push saran otomatis
  theme: "dark"                             # dark | light | hacker

# ── Panels ───────────────────────────────────────────────────────
panels:
  layer_panels:
    show_sparklines: true
    show_port: true
    show_task_tooltip: true
  pipeline_tracker:
    max_visible_audits: 5
    auto_expand_active: true
  antonio_panel:
    max_visible_steps: 8
    show_action_input: true
    show_observation_detail: false         # toggle dengan Enter
  metrics_panel:
    refresh_interval_s: 30
    show_false_negatives: true

# ── Slash Commands ───────────────────────────────────────────────
commands:
  history_size: 100
  autocomplete: true
  confirm_destructive: true               # konfirmasi untuk /clear-queue, dll

# ── Observability ────────────────────────────────────────────────
observability:
  show_trace_ids: true
  latency_percentiles: [50, 95, 99]
  otel_endpoint: "http://localhost:4318"  # OTLP HTTP endpoint (opsional)
```

---

## 14. Deployment — Docker, systemd, SSH

### 14.1 Menjalankan TUI

```bash
# Cara 1 — Langsung (development)
cd sc_auditor
python -m vyper_tui

# Cara 2 — Via Docker
docker compose run --rm vyper-tui

# Cara 3 — Via SSH (remote monitoring)
ssh user@server "cd sc_auditor && python -m vyper_tui"

# Cara 4 — Dalam tmux session permanen
tmux new-session -d -s vyper "cd sc_auditor && python -m vyper_tui"
tmux attach -t vyper
```

### 14.2 `docker-compose.yml` — Tambahan Service TUI

```yaml
# Tambahkan ke docker-compose.yml yang sudah ada

services:
  # ... existing services ...

  vyper-tui:
    build:
      context: ./cli
      dockerfile: Dockerfile.tui
    volumes:
      - ~/.vyper:/root/.vyper
    environment:
      - VYPER_DASHBOARD_URL=http://15-dashboard:8000
      - TERM=xterm-256color
    depends_on:
      - 15-dashboard
      - 11-orchestrator
      - 14-agent
    stdin_open: true
    tty: true
    network_mode: host    # akses semua service langsung
    profiles:
      - tui               # hanya start jika `--profile tui`
```

```bash
# Start dengan TUI
docker compose --profile tui up -d
docker compose exec vyper-tui python -m vyper_tui
```

### 14.3 `cli/Dockerfile.tui`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY cli/requirements.txt .
RUN pip install --no-cache-dir \
    textual>=0.60.0 \
    httpx>=0.27.0 \
    sse-starlette>=1.6.0 \
    rich>=13.0.0 \
    pydantic>=2.0.0 \
    python-dotenv>=1.0.0

COPY cli/ .

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "vyper_tui"]
```

### 14.4 `cli/requirements.txt`

```
textual>=0.60.0           # TUI framework
httpx>=0.27.0             # async HTTP + SSE client
rich>=13.0.0              # rich text rendering
pydantic>=2.0.0           # data models
python-dotenv>=1.0.0      # env config
aiofiles>=23.0.0          # async file I/O untuk config
```

---

## 15. Diagram Arsitektur Lengkap

```
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                              VYPER TUI v2 — Full Stack                              ║
╠══════════════════════════════╦═══════════════════════════╦══════════════════════════╣
║       TUI LAYER              ║     CORE LAYER            ║     BACKEND LAYER        ║
║ ┌──────────────────────────┐ ║ ┌──────────────────────┐  ║ ┌────────────────────┐   ║
║ │ VyperTUI (Textual App)   │ ║ │ EventBus             │  ║ │ 15-Dashboard       │   ║
║ │  LayoutManager           │ ║ │  SSE Client          │  ║ │  SSE Hub /events   │   ║
║ │  ├─ LayerPanels (6)      │ ║ │  Event Router        │  ║ │  API Gateway       │   ║
║ │  ├─ PipelineTracker      │ ║ │  Reconnect Logic     │  ║ └──────────┬─────────┘   ║
║ │  ├─ AntonioPanel         │◄╣ ├──────────────────────┤  ║            │ HTTP SSE    ║
║ │  ├─ TeamOpsPanel         │ ║ │ StateStore           │  ║ ┌──────────┴─────────┐   ║
║ │  ├─ AgentProtocolPanel   │ ║ │  Reactive State      │  ║ │ 11-Orchestrator    │   ║
║ │  ├─ MetricsPanel         │ ║ │  State Updater       │  ║ │  Pipeline SM       │   ║
║ │  ├─ ResourcePanel        │ ║ ├──────────────────────┤  ║ │  Priority Queue    │   ║
║ │  └─ ChatPanel v2         │ ║ │ CommandRouter        │  ║ │  ResourceGovernor  │   ║
║ │  StatusBar               │ ║ │  Slash Cmd Parser    │  ║ └────────────────────┘   ║
║ └──────────────────────────┘ ║ │  40+ Handlers        │  ║ ┌────────────────────┐   ║
║                              ║ ├──────────────────────┤  ║ │ 14-Agent (Antonio) │   ║
║ ┌──────────────────────────┐ ║ │ ActivityMonitorV2    │  ║ │  ReAct Loop        │   ║
║ │ PollingFallback          │ ║ │  Cache Manager       │  ║ │  10 Skills         │   ║
║ │ (legacy service support) │ ║ │  Sparkline Generator │  ║ │  4 Memory Types    │   ║
║ └──────────────────────────┘ ║ ├──────────────────────┤  ║ │  Team Mode         │   ║
║                              ║ │ PipelineTracker      │  ║ │  Daemon            │   ║
║ ┌──────────────────────────┐ ║ │  Stage State Machine │  ║ └────────────────────┘   ║
║ │ Config                   │ ║ │  Progress Calculator │  ║ ┌────────────────────┐   ║
║ │ ~/.vyper/tui/config.yaml │ ║ └──────────────────────┘  ║ │ All Other Services │   ║
║ └──────────────────────────┘ ║                           ║ │ 01..13, 16         │   ║
║                              ║                           ║ └────────────────────┘   ║
╚══════════════════════════════╩═══════════════════════════╩══════════════════════════╝
```

### 15.1 Alur Data End-to-End

```
1. 04-Scanner selesai scan
   │
   ▼
2. Scanner publish event ke 15-Dashboard
   POST /internal/publish  {"event_type": "service.activity", "status": "idle", ...}
   │
   ▼
3. 15-Dashboard push ke semua SSE client
   data: {"event_type": "service.activity", "service": "04-scanner", ...}
   │
   ▼
4. EventBus di TUI menerima event
   │
   ▼
5. EventBus dispatch ke registered handlers:
   - ActivityMonitorV2.handle_activity() → update cache
   - AntonioPanel (jika relevan) → update display
   │
   ▼
6. AppState.update(service_activities={...})
   │
   ▼
7. StateUpdated message → Textual reactive system
   │
   ▼
8. LayerPanel.on_state_updated() → self.refresh()
   │
   ▼
9. User melihat spinner berubah dari ⣾ menjadi 💤 di panel
```

---

## 16. Extension Guide

### 16.1 Menambah Panel Baru

```python
# src/panels/my_new_panel.py

from textual.widget import Widget
from textual.reactive import reactive

class MyNewPanel(Widget):
    """Template untuk panel baru."""

    # Subscribe ke event types yang relevan
    EVENT_SUBSCRIPTIONS = ["service.activity", "audit.state_change"]

    def on_mount(self):
        for event_type in self.EVENT_SUBSCRIPTIONS:
            self.app.event_bus.on(event_type)(self._handle_event)

    async def _handle_event(self, event: VyperEvent):
        # Update internal state
        self._data = event.payload
        self.refresh()

    def render(self) -> RenderableType:
        # Render menggunakan Rich
        return Panel(
            self._build_content(),
            title="My Panel",
            border_style="blue"
        )
```

### 16.2 Menambah Slash Command Baru

```python
# src/commands/my_command.py

from src.core.command_router import BaseCommand, CommandResult

class MyCommand(BaseCommand):
    name = "mycommand"
    aliases = ["/mycommand", "/mc"]
    description = "Deskripsi command ini"
    usage = "/mycommand <arg1> [arg2]"

    async def execute(self, args: list[str], state: VyperState) -> CommandResult:
        if not args:
            return CommandResult.error("Usage: " + self.usage)

        # Lakukan sesuatu
        result = await self.app.http.post(
            "http://localhost:8009/something",
            json={"arg": args[0]}
        )

        return CommandResult.success(
            message=f"Done: {result.json()}",
            update_state={"some_key": result.json()}
        )


# Register di src/commands/__init__.py
COMMANDS = [
    ...,
    MyCommand,
]
```

### 16.3 Menambah Event Publisher ke Service Baru

```python
# Tambahkan ke services/XX-newservice/app.py

from shared.event_publisher import EventPublisher

publisher = EventPublisher("XX-newservice")

@app.post("/my-endpoint")
async def my_endpoint(request: MyRequest):
    # Signal busy
    await publisher.publish("service.activity", {
        "status": "busy",
        "task": f"processing {request.id}",
    })

    result = await do_work(request)

    # Signal done
    await publisher.publish("service.activity", {
        "status": "idle",
        "task": "",
    })

    # Optionally publish domain event
    await publisher.publish("my_domain.completed", {
        "id": request.id,
        "result_summary": str(result)[:100],
    })

    return result
```

---

## 17. Lampiran: Contoh Sesi Lengkap

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║  VYPER TUI v2  ■ FULL MODE  ■ 0 audits active  ■ Antonio: idle  ■ 10:00:00    ║
╠══════════════════╦═══════════════════╦══════════════════════════════════════════╣
║ LAYER PANELS     ║ PIPELINE TRACKER  ║ ANTONIO                                 ║
║  (semua 💤 idle) ║ No active audits  ║  Idle. Ready for commands.              ║
╠══════════════════╩═══════════════════╩══════════════════════════════════════════╣
║ > /audit 0x4c9edd5852cd905f086c759e8383e09bff1e68b3 ethereum                  ║
╚══════════════════════════════════════════════════════════════════════════════════╝

[10:00:01] Orchestrator menerima audit request...
[10:00:01] aud_001 created, status: PENDING

╔═ PIPELINE ═══════════════════════════════════════════════════════════════════════╗
║ aud_001 [0x4c9edd / USDe / Ethena]   ░░░░░░░░░░░  0%  PENDING                 ║
╚══════════════════════════════════════════════════════════════════════════════════╝

[10:00:02] → FETCHING_PROGRAM  02-Immunefi ⣾
[10:00:03] ✅ Ethena USDe — max bounty $1,000,000

[10:00:03] → FETCHING_SOURCE   03-Source ⣾
[10:00:06] ✅ 12 files, 3219 LOC, Solidity ^0.8.19

[10:00:06] → SCANNING
║ aud_001 [██░░░░░░░░░] 20%  SCANNING                                            ║
║   Slither:  ⣾ running [███░░░░░░░░░░░░] 25%                                    ║
║   Mythril:  ⏳ pending                                                          ║
║   Echidna:  ⏳ pending                                                          ║

> Service apa yang paling lambat saat ini?
Antonio: 05-Mythril secara historis paling lambat — rata-rata P95 sekitar 211 detik.
         Saat ini sedang pending menunggu Scanner slot. Resource governor membatasi
         concurrent scanners maksimal 2.

> /metrics tool mythril
╭─ METRICS: mythril ────────────────────────────────────────────╮
│  TP: 61  FP: 8  FN: 5  Precision: 88.4%  Recall: 92.4%      │
│  Rata-rata waktu: 142s (P50), 211s (P95), 300s (P99)          │
│  Top FN patterns: symbolic explosion, path timeout            │
╰───────────────────────────────────────────────────────────────╯

[10:02:19] → SCANNING complete
║   Slither:  ✅ 19 findings   Mythril: ✅ 4 findings                             ║
║   Echidna:  ✅ 0 violations  Halmos:  ✅ 2 formal violations                   ║
║   Total: 25 findings (pre-dedup)                                                ║

[10:02:19] → HALMOS_ANALYSIS  04d-Halmos ⣾
[10:03:03] ✅ 2 formal violations confirmed

[10:03:03] → AI_ANALYSIS  06-ai ⣾  model: claude-sonnet-4-6
║ aud_001 [████████░░░] 67%  AI_ANALYSIS  ⣾                                      ║

AntonioPanel:
║ [7] THOUGHT: "25 raw findings. Deduplicate first, then analyze top severity."  ║
║ [7] ACTION  → deduplicate_findings  {"findings": [...]}                        ║
║ [7] OBSERVE ← local: "25 → 18 unique findings after dedup"                    ║
║ [8] THOUGHT: "18 findings. 4 HIGH (slither+mythril agree). Start with those." ║
║ [8] ACTION  → analyze_findings  {"findings": [...top_4...]}  ⣾ RUNNING        ║

[10:04:31] ✅ AI_ANALYSIS complete
│   Verdict: 3 CONFIRMED TP (HIGH), 1 FP, 14 MEDIUM/LOW pending classification  │

[10:04:31] → CLASSIFYING  07-classifier ⣾
[10:04:45] ✅ Classification complete
│   TRUE_POSITIVE: 3 (2 CRITICAL, 1 HIGH)  FALSE_POSITIVE: 1  Others: 14       │

[10:04:45] → EXPLOITING   08-exploit ⣾  (triggered: CRITICAL findings)
╭─ EXPLOIT ENGINE ─────────────────────────────────────────────────────────────╮
│  🔥 Anvil fork: ethereum @ block 21,500,000                                  │
│  Finding: vuln_001 — price manipulation via flash loan                       │
│  [PHASE 1] Fork chain     ✅ 2.1s                                             │
│  [PHASE 2] Deploy         ✅ 8.3s                                             │
│  [PHASE 3] Execute        ⣾ running (PoC executing...)                       │
│  Expected profit: ~$2.4M if exploited                                        │
╰───────────────────────────────────────────────────────────────────────────────╯

[10:05:23] 🔥 EXPLOIT CONFIRMED: tx 0xdeadbeef... profit: $2,418,392

[10:05:23] → REPORTING   09-reporter ⣾
[10:05:31] ✅ Report generated: immunefi.md (Immunefi-ready) + full.md

[10:05:31] → NOTIFYING   10-notifier ⣾
[10:05:32] 📢 Discord notification sent to #vyper-alerts

[10:05:32] ✅ COMPLETED

╭─ 💡 Co-pilot ──────────────────────────────────────────────────────────────────╮
│  Audit selesai! aud_001 menemukan 2 CRITICAL vulnerability. Laporan Immunefi  │
│  siap di ~/.vyper/reporter/aud_001/immunefi.md.                               │
│  Gunakan /submit aud_001 untuk bantuan submission ke Immunefi.                │
╰───────────────────────────────────────────────────────────────────────────────╯

> /submit aud_001
Antonio: Memuat laporan aud_001... Format sudah sesuai Immunefi.
         Severity: Critical. Program: Ethena. Estimasi bounty: $750K–$1M.
         Ingin saya review sekali lagi sebelum submit, atau langsung buka Immunefi?
```

---

> **VYPER TUI v2** — *Scan smarter, hunt faster, see deeper.*
>
> Dokumen ini mencakup arsitektur lengkap TUI generasi berikutnya:
> event-driven SSE architecture, 7-panel multi-mode layout, Antonio ReAct loop
> visualization, team ops, agent protocol, observability layer, 40+ slash commands,
> keyboard navigation, dan blueprint implementasi production-ready.
>
> Kompatibel dengan VYPER Backend v2 (20 services, Docker Compose v3.9).
>
> Last updated: 2026-05-26