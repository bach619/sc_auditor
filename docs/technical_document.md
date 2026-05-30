# Technical Document — VYPER (sc_auditor)

> **Smart Contract Bug Hunter** — Platform audit kontrak pintar berbasis microservice.
> 20 services, 1 laptop. Docker Compose, Python FastAPI, React Dashboard, AI Agent Antonio.

---

## Daftar Isi

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Service Catalog](#3-service-catalog)
4. [Audit Pipeline & Workflow](#4-audit-pipeline--workflow)
5. [Antonio AI Agent](#5-antonio-ai-agent)
   - 5.1 [ReAct Loop](#51-react-loop)
   - 5.2 [Skills Registry](#52-skills-registry)
   - 5.3 [Memory Systems](#53-memory-systems)
   - 5.4 [Team Organization](#54-team-organization)
   - 5.5 [Autonomous Daemon](#55-autonomous-daemon)
   - 5.6 [Agent Protocol](#56-agent-protocol)
6. [API Reference](#6-api-reference)
   - 6.1 [Orchestrator API](#61-orchestrator-api)
   - 6.2 [Antonio Agent API](#62-antonio-agent-api)
   - 6.3 [Service Health API](#63-service-health-api)
7. [CLI Design — Antonio Chat-Controlled](#7-cli-design--antonio-chat-controlled)
   - 7.1 [Vision & Philosophy](#71-vision--philosophy)
   - 7.2 [Architecture](#72-architecture)
   - 7.3 [Commands](#73-commands)
   - 7.4 [Chat Mode](#74-chat-mode)
   - 7.5 [Implementation Plan](#75-implementation-plan)
8. [Docker Setup](#8-docker-setup)
9. [Data Storage](#9-data-storage)
10. [Development Guide](#10-development-guide)
11. [Quick Start](#11-quick-start)

---

## 1. Project Overview

### 1.1 What is VYPER?

VYPER adalah platform **smart contract security auditing** yang berjalan sepenuhnya di lokal via Docker Compose. Dirancang untuk:

| Peran | Use Case |
|-------|----------|
| **Bug Bounty Hunter** | Scan kontrak dari program Immunefi, temukan True Positive, hasilkan laporan siap-submit |
| **Security Researcher** | Eksploitasi temuan dengan Anvil fork engine, buktikan kerentanan |
| **Platform Metrics** | Lacak presisi tiap tool (Slither, Mythril, AI), belajar dari False Negative |

### 1.2 Filosofi Arsitektur

VYPER menggunakan arsitektur **microservice** dengan 20 service independen yang berkomunikasi via HTTP/REST. Setiap service:

- Berjalan di **container Docker sendiri**
- Punya **kode sumber sendiri** di `services/{N}-nama/`
- Punya **Dockerfile sendiri**
- Punya **volume data sendiri** di `~/.vyper/{service}/`
- Bisa **di-scale independently** (`docker compose up --scale 04-scanner=3`)

### 1.3 Kenapa Microservice?

| Faktor | Monolith | VYPER (Microservice) |
|--------|----------|----------------------|
| **Isolasi** | Slither crash → semua berhenti | Scanner crash → service lain tetap jalan |
| **Scale** | Satu proses | `docker compose up --scale scanner=3` |
| **Update** | Deploy ulang semua | Update Scanner v2 tanpa sentuh AI |
| **Debug** | Log campur aduk | `docker logs vyper-04-scanner-1` |
| **Dependency** | Satu requirements.txt (konflik) | Masing-masing service punya sendiri |
| **Memory** | Semua dalam 1 proses | Masing-masing container 256MB-512MB |

### 1.4 Tech Stack

| Layer | Teknologi |
|-------|-----------|
| **Bahasa** | Python 3.11+ (19 service) + TypeScript (Dashboard) |
| **Framework API** | FastAPI + Pydantic v2 |
| **HTTP Client** | httpx (async, connection pooling) |
| **Run** | uvicorn per service |
| **Container** | python:3.11-slim |
| **Orkestrasi** | Docker Compose v3.9 |
| **Dashboard** | React 18 + TypeScript + Tailwind v4 + Vite 8 |
| **AI Agent** | OpenAI GPT-4o / Anthropic Claude 3.5 Sonnet |
| **Storage** | File-based JSON (Docker volumes) |
| **LLM Provider** | OpenAI, Anthropic (configurable via frontend) |

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  USER                                                                   │
│   │                                                                    │
│   ├──► http://localhost:8000  ───  15-Dashboard (React SPA + Gateway)  │
│   │                                                                    │
│   └──► http://localhost:8021  ───  14-Agent (Antonio — AI Chat CLI)   │
│                                                                        │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ HTTP/REST
                           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  11-ORCHESTRATOR (port 8009)  Pipeline Coordinator                      │
│  ─────────────────────────────────────────────────────────────────────── │
│  • Priority queue & daemon mode                                         │
│  • State machine — 10 stage audit                                       │
│  • Contract similarity & retroactive re-run                             │
│  • Resource governor (tool concurrency)                                 │
│  • Agent Protocol (manifest + delegate + negotiate)                     │
└──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬───────────────────────────┘
   │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
   ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼
┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐
│CFG ││ IM ││SRC ││SCN ││SLS ││ECH ││FRG ││HAL ││MTH ││ AI ││CLS ││EXP ││RPT ││NTF │
│8011││8001││8002││8003││8014││8015││8016││8017││8013││8004││8005││8006││8007││8008│
└────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘
   │    │    │    │                                                    │    │
   ▼    ▼    ▼    ▼                                                    ▼    ▼
┌────┐┌────┐┌────┐┌────┐                                              ┌────┐┌────┐
│WHK ││UPK ││AGNT││SUB │                                              │DSH ││LRN │
│8010││8012││8021││8018│                                              │8000││vol │
└────┘└────┘└────┘└────┘                                              └────┘└────┘
```

### 2.2 Service Communication Pattern

Semua komunikasi antar service via **HTTP/REST synchronous** dengan timeout:

| Service Call | Timeout | Retry |
|-------------|---------|-------|
| Orchestrator → Scanner | 900s (15 min) | 3x |
| Orchestrator → AI | 120s | 2x |
| Orchestrator → Exploit | 300s | 1x |
| Orchestrator → Others | 30s | 3x |
| Agent → All services | 60s | 3x |

Format response semua service menggunakan **envelope** yang konsisten:

```python
{
    "data": { ... },           # Payload
    "meta": {
        "status": "ok",        # atau "error"
        "error": null,         # Pesan error jika status="error"
        "timestamp": "2026-05-26T10:00:00Z"
    }
}
```

---

## 3. Service Catalog

### 3.1 Full Service List

| # | Service | Port | Fungsi | Dockerfile |
|---|---------|------|--------|------------|
| 01 | **Config** | 8011 | Konfigurasi global + API keys | `services/01-config/Dockerfile` |
| 02 | **Immunefi** | 8001 | Sync 234+ program bug bounty, deteksi repo | `services/02-immunefi/Dockerfile` |
| 03 | **Source** | 8002 | Multi-source fetch (GitHub, Sourcify, Etherscan, Blockscout) | `services/03-source/Dockerfile` |
| 04 | **Scanner** | 8003 | Main scanner — routing ke tool spesifik | `services/04-scanner/Dockerfile` |
| 04a | **Scanner Slither** | 8014 | Static analysis (control flow, inheritance) | `services/04a-scanner-slither/Dockerfile` |
| 04b | **Scanner Echidna** | 8015 | Fuzzing & property-based testing | `services/04b-scanner-echidna/Dockerfile` |
| 04c | **Scanner Forge** | 8016 | Build verification (Foundry) | `services/04c-scanner-forge/Dockerfile` |
| 04d | **Scanner Halmos** | 8017 | Formal verification (symbolic execution) | `services/04d-scanner-halmos/Dockerfile` |
| 05 | **Scanner Mythril** | 8013 | Symbolic execution (deep path) | `services/05-scanner-mythril/Dockerfile` |
| 06 | **AI** | 8004 | LLM analysis — verdict, severity, fix suggestion | `services/06-ai/Dockerfile` |
| 07 | **Classifier** | 8005 | TP/FP/TN/FN classification + metrics | `services/07-classifier/Dockerfile` |
| 08 | **Exploit** | 8006 | Anvil Docker engine + PoC generation | `services/08-exploit/Dockerfile` |
| 09 | **Reporter** | 8007 | Generate laporan Immunefi + full report | `services/09-reporter/Dockerfile` |
| 10 | **Notifier** | 8008 | Discord / Telegram / Email / Desktop | `services/10-notifier/Dockerfile` |
| 11 | **Orchestrator** | 8009 | Pipeline coordinator — state machine | `services/11-orchestrator/Dockerfile` |
| 12 | **Webhook** | 8010 | Webhook delivery + signing | `services/12-webhook/Dockerfile` |
| 13 | **Upkeep** | 8012 | Backup, update, metrics agregat | `services/13-upkeep/Dockerfile` |
| 14 | **Agent** | 8021 | Antonio — AI Agent ReAct + Skills + Memory | `services/14-agent/Dockerfile` |
| 15 | **Dashboard** | 8000 | React SPA + API Gateway + SSE events | `services/15-dashboard/Dockerfile` |
| 16 | **Submission** | 8018 | Track bounties & submission assistant | `services/16-submission/Dockerfile` |

**Shared module**: `services/shared/` — package bersama untuk:
- `observability.py` — setup logging, metrics, tracing
- `metrics.py` — Prometheus metrics middleware
- `cache.py` — Simple JSON cache
- `agent_protocol/` — Agent discovery, delegation, negotiation protocol

### 3.2 Service Detail

#### 01-Config (port 8011)
Config management service — **single source of truth** untuk konfigurasi global.

**Endpoints:**
```
GET  /config/{key}     — Ambil config value
POST /config/{key}     — Set config value
GET  /config           — List semua config
```

**Config keys:**
```yaml
openai_api_key: ""
anthropic_api_key: ""
openai_model: "gpt-4o"
anthropic_model: "claude-3-5-sonnet-20241022"
agent_max_steps: 25
scanner_timeout: 900
notifier_discord_webhook: ""
notifier_telegram_token: ""
```

#### 02-Immunefi (port 8001)
Sync program dari Immunefi bounty platform. Maintain database 234+ program.

**Endpoints:**
```
GET  /programs              — List semua program
GET  /programs/{slug}       — Detail program
POST /programs/sync         — Trigger sync dari GitHub
POST /programs/sync-all     — Full sync semua program
GET  /program/{address}     — Cari program oleh contract address
```

**Storage:** `~/.vyper/immunefi/` — JSON files per program + indexes.

#### 03-Source (port 8002)
Multi-source code fetcher. Mendukung 5 provider:

| Provider | Source | Chain Support |
|----------|--------|---------------|
| **Etherscan** | API | Ethereum, Polygon, Arbitrum, BSC, Optimism, Base |
| **Sourcify** | Public repo | 20+ chains (multi-chain) |
| **Blockscout** | API | Gnosis, Celo, POA, etc |
| **GitHub** | Clone repo | All |
| **Manual** | Upload | All |

**Endpoints:**
```
GET  /fetch/{address}?chain=ethereum     — Fetch source code
GET  /info/{address}                     — Info contract + metadata
GET  /providers                          — List active providers
```

#### 04-Scanner (port 8003)
Scanner router — menerima request scan dan mendistribusikan ke tool spesifik.

**Endpoints:**
```
POST /scan                          — Full scan (semua tools)
POST /scan/slither                  — Slither only
POST /scan/mythril                  — Mythril only
POST /scan/echidna                  — Echidna only
POST /scan/forge                    — Forge build check
POST /scan/halmos                   — Halmos formal verification
GET  /results/{audit_id}            — Get scan results
```

#### 04a-Scanner-Slither (port 8014)
Static analysis via Slither. Detects:
- Reentrancy
- Unchecked calls
- Integer overflow/underflow
- Access control issues
- tx.origin usage
- Timestamp dependence
- Shadow variable
- Uninitialized state
- Plus 100+ detectors

#### 04b-Scanner-Echidna (port 8015)
Fuzzing & property-based testing via Echidna.

#### 04c-Scanner-Forge (port 8016)
Build verification via Foundry Forge.

#### 04d-Scanner-Halmos (port 8017)
Symbolic execution & formal verification via Halmos.

#### 05-Scanner-Mythril (port 8013)
Symbolic execution (deep path exploration) via Mythril.

#### 06-AI (port 8004)
LLM-powered vulnerability analysis. Mendukung:

| Provider | Model Default |
|----------|---------------|
| OpenAI | GPT-4o |
| Anthropic | Claude 3.5 Sonnet |

**Endpoints:**
```
POST /analyze                    — Analyze findings, return verdict
POST /fix-suggestion             — Generate fix recommendation
GET  /cache/{hash}               — Get cached analysis
```

**Flow:** Terima raw findings + source code → Kirim ke LLM → Return TP/FP classification + severity + fix recommendation.

#### 07-Classifier (port 8005)
TP/FP/TN/FN classification engine. Maintain confusion matrix per tool.

**Endpoints:**
```
POST /classify                   — Classify findings
GET  /metrics                    — Get platform metrics
POST /feedback                   — Submit feedback (TP/FP correction)
GET  /false-negatives            — List false negative patterns
```

#### 08-Exploit (port 8006)
Anvil-based exploit engine. Fork chain, execute exploit, confirm vulnerability.

**Endpoints:**
```
POST /exploit/run                — Run exploit for finding
POST /exploit/test               — Test PoC
GET  /exploit/{id}               — Get exploit result
GET  /exploit/templates          — List exploit templates
```

**Architecture:** Menggunakan `docker-py` untuk manage Anvil container ephemeral:
1. User request exploit untuk finding
2. Exploit service spin up Anvil container (fork dari chain real)
3. Execute PoC script via Foundry
4. Return result + tx hash
5. Destroy Anvil container

#### 09-Reporter (port 8007)
Report generator. Output format: Markdown.

**Endpoints:**
```
POST /reporter/generate          — Generate report
GET  /reporter/{audit_id}        — Get generated report
```

**Report Types:**
- `immunefi.md` — TP-ONLY, format Immunefi, siap submit
- `full.md` — Lengkap + metrics + semua findings

#### 10-Notifier (port 8008)
Multi-channel notification.

**Channels:**
- Discord (webhook)
- Telegram (bot)
- Email (SMTP)
- Desktop (notifikasi)

#### 11-Orchestrator (port 8009)
**Jantung pipeline.** Coordinator yang menjalankan state machine audit. Lihat [Section 4](#4-audit-pipeline--workflow) untuk detail.

#### 12-Webhook (port 8010)
Webhook delivery service. Signature support (HMAC-SHA256).

#### 13-Upkeep (port 8012)
Maintenance tasks: backup, restore, metrics aggregation.

#### 14-Agent (port 8021)
**Antonio — AI Agent.** Autonomous smart contract audit agent. Lihat [Section 5](#5-antonio-ai-agent) untuk detail lengkap.

#### 15-Dashboard (port 8000)
React SPA + FastAPI backend. API Gateway yang proxy ke semua service.

**Pages:**
| Route | Halaman |
|-------|---------|
| `/` | Overview — metrics, findings, filters |
| `/programs` | Daftar program Immunefi |
| `/programs/:slug` | Detail program & kontrak |
| `/audits` | Riwayat audit |
| `/audits/:id` | Detail audit — findings, exploit, report |
| `/scanner` | Scanner detail per tool |
| `/exploit` | Exploit viewer |
| `/reports` | Report center |
| `/config` | Config editor (API keys, settings) |
| `/webhooks` | Webhook logs |
| `/settings` | Settings |
| `/scheduler` | Scheduled audits |

#### 16-Submission (port 8018)
Submission assistant — bantu track dan submit bug bounty ke berbagai platform.

---

## 4. Audit Pipeline & Workflow

### 4.1 State Machine

Setiap audit melalui 10 stage yang dijalankan **sekuensial** oleh Orchestrator:

```
                    ┌─────────────┐
                    │  PENDING    │
                    └──────┬──────┘
                           │ start
                           ▼
               ┌─────────────────────┐
               │  FETCHING_PROGRAM   │ ← 02-Immunefi:8001
               └──────────┬──────────┘
                          │ success
                          ▼
               ┌─────────────────────┐
               │  FETCHING_SOURCE    │ ← 03-Source:8002
               └──────────┬──────────┘
                     ╱          ╲
               success          fail
                  ▼              ▼
        ┌──────────────┐  ┌──────────────┐
        │  SCANNING    │  │SOURCE_FAILED │ ← Abort, retry
        │ Slither +    │  └──────────────┘
        │ Mythril +    │
        │ Echidna +    │
        │ Halmos +     │
        │ Forge        │
        └──────┬───────┘
               │ success
               ▼
        ┌──────────────────┐
        │  HALMOS_ANALYSIS │ ← 04d-Halmos formal verification
        └──────┬───────────┘
               │ success
               ▼
        ┌──────────────┐
        │  AI_ANALYSIS │ ← 06-AI (LLM verdict)
        └──────┬───────┘
               │ success
               ▼
        ┌──────────────┐
        │  CLASSIFYING │ ← 07-Classifier (TP/FP)
        └──────┬───────┘
               │ success
               ▼
        ┌──────────────┐
        │  EXPLOITING  │ ← 08-Exploit (Anvil)
        │  HANYA jika  │
        │  TP critical │
        │  / high      │
        └──────┬───────┘
               │ success
               ▼
        ┌──────────────┐
        │  REPORTING   │ ← 09-Reporter
        └──────┬───────┘
               │ success
               ▼
        ┌──────────────┐
        │  NOTIFYING   │ ← 10-Notifier
        │  HANYA jika  │
        │  critical/   │
        │  high        │
        └──────┬───────┘
               │ success
               ▼
        ┌──────────────┐
        │  COMPLETED   │ ✓
        └──────────────┘

State: pending → fetching_program → fetching_source → scanning →
       halmos_analysis → ai_analysis → classifying → exploiting? →
       reporting → notifying → completed
```

### 4.2 State Definitions

```python
class PipelineState(str, Enum):
    PENDING            = "pending"
    FETCHING_PROGRAM   = "fetching_program"
    FETCHING_SOURCE    = "fetching_source"
    SCANNING           = "scanning"
    HALMOS_ANALYSIS    = "halmos_analysis"
    AI_ANALYSIS        = "ai_analysis"
    CLASSIFYING        = "classifying"
    EXPLOITING         = "exploiting"
    REPORTING          = "reporting"
    NOTIFYING          = "notifying"
    COMPLETED          = "completed"

    # Failure states — retry or user action needed
    SOURCE_FAILED      = "source_failed"
    SCAN_FAILED        = "scan_failed"
    HALMOS_FAILED      = "halmos_failed"
    AI_FAILED          = "ai_failed"
    CLASSIFY_FAILED    = "classify_failed"
    EXPLOIT_FAILED     = "exploit_failed"
    REPORT_FAILED      = "report_failed"
    TIMEOUT            = "timeout"
    ABORTED            = "aborted"
```

### 4.3 Resource Governor

Orchestrator punya **ResourceGovernor** yang manage concurrency:

| Tool Type | Max Concurrent | Timeout |
|-----------|---------------|---------|
| Scanner | 2 (default) | 900s |
| AI | 3 (default) | 120s |
| Exploit | 1 | 300s |

### 4.4 Priority Queue

Setiap audit masuk ke priority queue. Skor prioritas dihitung dari:

```python
# src/priority.py
priority_score = (
    program_criticality * 0.4 +    # Seberapa critical program (Immunefi)
    contract_value * 0.3 +         # TVL / value at risk
    time_in_queue * 0.2 +          # Lama nunggu
    manual_boost * 0.1             # Manual priority override (0-10)
)
```

### 4.5 Retroactive Re-run

Orchestrator bisa re-run audit yang gagal atau False Negative:

```python
POST /rerun
{
    "audit_ids": ["aud_001", "aud_002"],   # Spesifik audit
    "pattern_type": "reentrancy",           # Atau pattern FN
    "reason": "New reentrancy detector"
}
```

### 4.6 Contract Similarity

Orchestrator maintain similarity database untuk contract clustering:

```python
GET /similarity/{contract_id}?threshold=0.7
# Returns: similar contracts with similarity score
```

Fingerprint berdasarkan:
- Jumlah function
- Jumlah state variable
- Source lines of code
- Opcode patterns

---

## 5. Antonio AI Agent

### 5.1 ReAct Loop

Antonio menggunakan **ReAct** (Reasoning + Acting) pattern:

```
                   ┌──────────────────┐
                   │   THINK           │
                   │  (LLM reasoning)  │
                   └────────┬─────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │   ACT             │
                   │  (Call a skill)   │
                   └────────┬─────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │   OBSERVE         │
                   │  (Process result) │
                   └────────┬─────────┘
                            │
                  ┌─────────┴──────────┐
                  │                    │
            task selesai         masih ada step
                  │                    │
                  ▼                    ▼
           ┌──────────┐     kembali ke THINK
           │ FINAL    │
           │ ANSWER   │
           └──────────┘
```

**Implementation** (`src/agent.py`):

```python
class AgentLoop:
    async def run(self, task_type, input_data, goal, max_steps):
        session = AgentSession(session_id, task_type, goal, input_data)

        while session.status == AgentState.RUNNING and step < max_steps:
            # 1. THINK — LLM decides next action
            context = self._build_context(session, self.memory)
            skills_desc = self.registry.get_skills_description()
            decision = await self.llm.reason(context, skills_desc)

            # 2. ACT — Execute skill
            result = await self.registry.execute(
                decision["action"],
                **decision.get("action_input", {})
            )

            # 3. OBSERVE — Store result
            self.memory.set_working(f"last_result", result)
            session.add_step(AgentStep(
                thought=decision["thought"],
                action=decision["action"],
                observation=result
            ))

            # Check for FINAL_ANSWER
            if decision["action"] == "FINAL_ANSWER":
                session.complete(decision["final_answer"])

        return session
```

**System Prompt** (`src/llm.py`):

```
You are Vyper, an expert smart contract security AI agent.

Your goal is to audit smart contracts and find security vulnerabilities.
You have access to a set of SKILLS that you can call.

## How to Think (ReAct Pattern)
For each step, follow this format:
THOUGHT: What is the current situation? What should I do next?
ACTION: skill_name
ACTION_INPUT: {"param": "value"}
OBSERVATION: (result from skill)

## Output Format (JSON)
{
  "thought": "your reasoning here",
  "action": "skill_name or FINAL_ANSWER",
  "action_input": { "param": "value" },
  "final_answer": "final summary or null"
}
```

### 5.2 Skills Registry

Antonio memiliki **10 skills** yang terdaftar. Setiap skill adalah class Python yang meng-extend `BaseSkill`:

| Skill | Fungsi | HTTP Call |
|-------|--------|-----------|
| `fetch_program` | Ambil info program dari Immunefi | → 02-Immunefi `/program/{address}` |
| `fetch_source` | Fetch source code kontrak | → 03-Source `/fetch/{address}` |
| `scan_contract` | Scan kontrak dengan semua tools | → 04-Scanner `/scan` |
| `analyze_findings` | Analisis findings via LLM | → 06-AI `/analyze` |
| `classify_finding` | Klasifikasi TP/FP | → 07-Classifier `/classify` |
| `exploit_test` | Generate & run exploit | → 08-Exploit `/exploit/run` |
| `generate_report` | Generate laporan audit | → 09-Reporter `/reporter/generate` |
| `notify` | Kirim notifikasi | → 10-Notifier `/notify` |
| `deduplicate_findings` | Deduplikasi temuan serupa | Local (no HTTP) |
| `delegate_task` | Delegasi task ke backend agent lain | → Agent Registry |

**Skill Interface:**
```python
class BaseSkill(ABC):
    name: str
    description: str
    parameters: dict  # JSON Schema untuk parameter

    @abstractmethod
    async def execute(self, **kwargs) -> SkillResult:
        pass
```

**Contoh Skill** (`src/skills/scan_contract.py`):
```python
class ScanContractSkill(BaseSkill):
    def __init__(self, http_client):
        self.name = "scan_contract"
        self.description = "Scan a smart contract using all available tools"
        self.parameters = {
            "contract_address": {"type": "string", "required": True},
            "chain": {"type": "string", "required": True}
        }

    async def execute(self, **kwargs) -> SkillResult:
        resp = await self.http_client.post(
            "http://04-scanner:8000/scan",
            json=kwargs
        )
        return SkillResult(success=True, data=resp.json())
```

### 5.3 Memory Systems

Antonio memiliki **4 jenis memory**:

| Memory Type | Storage | Fungsi |
|-------------|---------|--------|
| **Working Memory** | In-memory dict | Konteks sesi berjalan (task_type, goal, findings) |
| **Vector Memory** | TF-IDF + JSON file | Search pengalaman dari session sebelumnya |
| **Episodic Memory** | JSON file (append) | Catat kronologi setiap step |
| **Graph Memory** | JSON file | Relasi antara contract, vuln, exploit |

**Vector Memory** (`src/memory/vector_store.py`):
```python
class VectorStore:
    def __init__(self):
        self.entries: list[dict] = []  # [{key, text, metadata, embedding}]

    async def store(self, key, text, metadata=None):
        # Simple TF-IDF + cosine similarity
        self.entries.append({
            "key": key, "text": text,
            "metadata": metadata or {},
            "embedding": self._tfidf_vectorize(text),
        })

    async def retrieve(self, query, limit=5):
        query_vec = self._tfidf_vectorize(query)
        scored = [(e, self._cosine_sim(query_vec, e["embedding"]))
                  for e in self.entries]
        return sorted(scored, key=lambda x: -x[1])[:limit]
```

**Memory Location:** Semua persistent memory di `~/.vyper/agent/`:
```
~/.vyper/agent/
├── vector_index.json      # Vector memory entries
├── episodic.json          # Session history
└── graph.json             # Knowledge graph
```

### 5.4 Team Organization

Antonio mengimplementasikan **Lead Auditor pattern** — hierarchical AI team:

```
                    ┌──────────────────┐
                    │   LEAD AUDITOR   │  — Strategi, planning, synthesis
                    │  (Antonio utama) │
                    └────────┬─────────┘
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │ CODE ANALYST│  │  EXPLOIT    │  │  REPORT     │  — Sub-agents
    │ - Scan      │  │  SPECIALIST │  │  WRITER     │
    │ - Slither   │  │  - Anvil    │  │  - Markdown │
    │ - Mythril   │  │  - PoC gen  │  │  - Immunefi │
    └─────────────┘  └─────────────┘  └─────────────┘
```

**Organizational Personas** (`src/organization.py`):

```python
def get_all_personas():
    return [
        Persona(
            role=AgentRole.LEAD_AUDITOR,
            title="Lead Security Auditor",
            expertise=["audit strategy", "vulnerability assessment", "risk analysis"],
            allowed_skills=["delegate_task", "analyze_findings"],
        ),
        Persona(
            role=AgentRole.CODE_ANALYST,
            title="Static Analysis Specialist",
            expertise=["slither", "static analysis", "pattern detection"],
            allowed_skills=["fetch_source", "scan_contract", "fetch_program"],
        ),
        Persona(
            role=AgentRole.EXPLOIT_SPECIALIST,
            title="Exploit Development Specialist",
            expertise=["foundry", "anvil", "poc development"],
            allowed_skills=["exploit_test"],
        ),
        Persona(
            role=AgentRole.REPORT_WRITER,
            title="Security Report Writer",
            expertise=["technical writing", "immunefi format", "vulnerability disclosure"],
            allowed_skills=["generate_report", "notify"],
        ),
        Persona(
            role=AgentRole.CLASSIFIER,
            title="Finding Classification Specialist",
            expertise["false positive analysis", "vulnerability taxonomy"],
            allowed_skills=["classify_finding", "deduplicate_findings"],
        ),
    ]
```

### 5.5 Autonomous Daemon

Antonio memiliki **background daemon** yang bisa di-start/stop via API:

```
POST /daemon/start      → Start daemon
POST /daemon/stop       → Stop daemon
GET  /daemon/status     → Status + statistik
```

**Daemon Tasks** (interval configurable):

| Task | Interval | Deskripsi |
|------|----------|-----------|
| Health check | Setiap cycle | Cek health semua dependent services |
| Program sync | Every 6 cycles | Sync program baru dari Immunefi |
| Self-assessment | Every 12 cycles | Evaluasi performa sendiri |
| Auto-hunt | Every 3 cycles | Cari kontrak baru untuk diaudit |
| Memory consolidation | Every 24 cycles | Kompres dan optimize memory |
| Stale session cleanup | Every cycle | Cleanup session yang timeout |

### 5.6 Agent Protocol

Antonio menggunakan **Agent Protocol** untuk komunikasi antar agent:

**Agent Registry** (`services/shared/agent_protocol/registry.py`):
```python
class AgentRegistry:
    async def register(self, manifest):     # Daftarkan diri
    async def discover(self, capability):   # Cari agent dengan capability
    async def delegate(self, target, task): # Delegasi task ke agent lain
```

**Agent Manifest:**
```python
{
    "service_name": "14-agent",
    "agent_role": "antonio",
    "version": "0.2.0",
    "capabilities": ["scan", "analyze", "exploit", "report"],
    "constraints": {
        "max_concurrent_tasks": 5,
        "requires_api_key": True
    },
    "current_load": {
        "active_tasks": 0,
        "status": "idle"
    }
}
```

**Flow Delegation:**
1. Antonio terima task kompleks
2. Antonio decide untuk delegate subtask (misal: exploit testing)
3. Antonio cari agent dengan capability `exploit` via AgentRegistry
4. Antonio kirim `DelegationRequest` ke agent tujuan
5. Agent proses, return result
6. Antonio synthesize semua hasil

---

## 6. API Reference

### 6.1 Orchestrator API

Base URL: `http://localhost:8009`

#### Health
```
GET /health
Response: {
    "service": "orchestrator",
    "daemon": "running" | "stopped",
    "pipeline": { "total_audits": N, "completed": N, "failed": N, "in_progress": N },
    "resources": { "scanner_slots": {...}, "ai_slots": {...} },
    "queue_size": N
}
```

#### Audit Pipeline
```
POST /audit
Body: {
    "chain": "ethereum",
    "address": "0x4c9edd5852cd905f086c759e8383e09bff1e68b3",
    "program": "ethena",      // optional
    "priority": 5,             // optional, 0-10
    "use_ai": true,
    "metadata": {}
}
Response: { "audit_id": "aud_abc123", "state": "pending" }

GET /audit/{audit_id}
Response: Full audit record with all steps

GET /audits?state=completed&program=ethena&limit=100&offset=0
Response: List of audit records
```

#### Queue Management
```
POST /queue
Body: { "address": "0x...", "chain": "ethereum", "priority_score": 8.5 }

GET /queue?sorted=true&limit=100
Response: Priority queue
```

#### Daemon
```
POST /daemon/start        → Start daemon loop
POST /daemon/stop         → Stop daemon
GET  /daemon/status       → Daemon state
```

#### Retroactive Rerun
```
POST /rerun
Body: {
    "audit_ids": ["aud_001"],
    "reason": "New detector added",
    "pattern_type": "reentrancy"
}
```

#### Pipeline Retry
```
POST /pipeline/retry/{audit_id}
```

#### Stats & Resources
```
GET /stats           → Pipeline statistics
GET /resources       → Resource governor status
```

#### Contract Similarity
```
GET /similarity/{contract_id}?threshold=0.7
GET /similarity      → List all clusters
```

#### Agent Protocol (Orchestrator sebagai agent)
```
GET  /agent/manifest       → OrchestratorAgent manifest
POST /agent/delegate       → Terima delegasi task
POST /agent/negotiate      → Negosiasi task feasibility
```

### 6.2 Antonio Agent API

Base URL: `http://localhost:8021`

#### Health
```
GET /health
Response: {
    "service": "antonio",
    "version": "0.2.0",
    "active_sessions": N,
    "skills_loaded": N,
    "memory_entries": N
}
```

#### Agent Run
```
POST /agent/run
Body: {
    "task_type": "full_audit",
    "input_data": {
        "contract_address": "0x4c9edd...",
        "chain": "ethereum",
        "program_slug": "ethena"
    },
    "goal": "Full audit of USDe contract",
    "max_steps": 25
}
Response: { "session_id": "agent-abc123", "status": "running", ... }

GET /agent/sessions?limit=20&status=completed
Response: List of sessions

GET /agent/{session_id}
Response: Full session with all ReAct steps
```

#### Skills
```
GET /skills
Response: { "total": 10, "skills": [...] }

GET /skills/metrics
Response: Skill usage statistics
```

#### Memory
```
GET /memory
Response: Current memory contents

POST /memory/search
Body: { "query": "reentrancy", "store": "vector", "limit": 10 }
Response: Search results

GET /memory/stats
Response: Memory store statistics
```

#### Daemon
```
POST /daemon/start
POST /daemon/stop
GET  /daemon/status
```

#### Team Audit (Lead Auditor)
```
POST /team/run
Body: {
    "task_type": "full_audit",
    "input_data": { "contract_address": "0x...", "chain": "ethereum" },
    "goal": "Full audit of USDe contract",
    "max_delegations": 15
}

GET /team/sessions?limit=20
GET /team/{session_id}
GET /team/structure
```

#### Learning & Feedback
```
POST /learning/feedback
Body: { "session_id": "agent-abc", "rating": 4, "comment": "Good", "tags": [] }
Response: Feedback stored in vector memory

GET /learning/stats
Response: Learning statistics

GET /learning/recommendations?task_type=full_audit
Response: Learning-based recommendations
```

#### Circuit Breakers
```
GET /circuit-breakers
POST /circuit-breakers/reset
```

#### Agent Protocol
```
GET /agent/manifest         → Antonio manifest untuk discovery
GET /agent/registry          → List semua backend agent yang terdiscovery
```

### 6.3 Service Health API

Semua service punya endpoint health yang konsisten:

```
GET /health
Response: ApiResponse {
    "data": {
        "service": "nama-service",
        "version": "x.y.z",
        "status": "ok"
    },
    "meta": { "status": "ok" }
}
```

Service yang bisa di-check via Dashboard proxy:
```
GET /api/health/all    → Dashboard proxy ke semua service → return aggregated health
```

---

## 7. CLI Design — Antonio Chat-Controlled

### 7.1 Vision & Philosophy

CLI baru VYPER bukan sekadar tool untuk menjalankan perintah — tapi **antarmuka percakapan** dengan Antonio AI Agent. Filosofi:

> **"Talk to Antonio, not to the terminal."**

| Old CLI (Deleted) | New CLI Vision |
|-------------------|----------------|
| Manual commands | Chat dengan Antonio |
| User harus tahu syntax | User bilang apa yang mau |
| Output text mentah | AI menjelaskan hasil |
| Stateless | Antonio ingat konteks |
| Satu arah | Dialog dua arah |

### 7.2 Architecture

```
┌────────────────────────────────────────────────────────────┐
│  USER                                                        │
│    │                                                         │
│    ├──► vyper audit 0x4c9edd...    (command mode)          │
│    │                                                         │
│    └──► vyper chat                 (chat mode)              │
│          "Antonio, audit USDe contract di Ethereum"          │
│                                                              │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│  vyper CLI (Python Typer — lightweight)                     │
│  ─────────────────────────────────────────────────────────  │
│  • Command mode: parse args → call Antonio API             │
│  • Chat mode: stdin/stdout dialog → streaming ke Antonio   │
│  • Output: Rich formatted (tables, panels, progress)       │
│  • Config: ~/.vyper/config.yml                             │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTP/REST
                         ▼
┌────────────────────────────────────────────────────────────┐
│  14-Agent (Antonio) — port 8021                            │
│  ─────────────────────────────────────────────────────────  │
│  • POST /agent/run — execute task                          │
│  • GET /agent/{id} — cek status & hasil                    │
│  • POST /agent/chat — streaming chat                       │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTP/REST
                         ▼
┌────────────────────────────────────────────────────────────┐
│  Backend Services (01-16)                                   │
│  ─────────────────────────────────────────────────────────  │
│  • Antonio yang call service via skills                     │
│  • CLI tidak perlu tau service mana yang dipanggil          │
└────────────────────────────────────────────────────────────┘
```

### 7.3 Commands

#### Command Mode

```bash
vyper audit <address> [--chain] [--program] [--async]
vyper scan <file> [--tools]
vyper status [audit-id]
vyper list [--state] [--program]
vyper stats
vyper health

vyper chat                    # → Chat mode (default jika no args)
vyper run "<pertanyaan>"      # → One-shot chat

vyper daemon start|stop|status
vyper config [show|set|path]
vyper version
```

#### Output Format

Semua command output menggunakan **Rich** formatting:

```bash
$ vyper health

╭─────────────────────────────────────────────────────╮
│              VYPER — Service Health                  │
├─────────────────────────────────────────────────────┤
│  ✅ 01-config      8011  Config Management           │
│  ✅ 02-immunefi    8001  234 Programs Synced         │
│  ✅ 03-source      8002  Multi-source ready          │
│  ✅ 04-scanner     8003  5 tools registered          │
│  ✅ 04a-slither    8014  Static analysis              │
│  ✅ 04b-echidna    8015  Fuzzing ready                │
│  ✅ 04c-forge      8016  Build verification           │
│  ✅ 04d-halmos     8017  Formal verification          │
│  ✅ 05-mythril     8013  Symbolic execution           │
│  ✅ 06-ai          8004  LLM: OpenAI GPT-4o           │
│  ✅ 07-classifier  8005  89% precision                │
│  ✅ 08-exploit     8006  Anvil engine ready           │
│  ✅ 09-reporter    8007  Report generator             │
│  ✅ 10-notifier    8008  3 channels configured        │
│  ✅ 11-orchestrator 8009  Pipeline coordinator        │
│  ✅ 12-webhook     8010  Webhook dispatcher           │
│  ✅ 13-upkeep      8012  Backup ready                 │
│  ✅ 14-agent       8021  Antonio AI Agent             │
│  ✅ 15-dashboard   8000  React SPA                    │
│  ✅ 16-submission  8018  Submission assistant         │
│                                                       │
│  🟢 Antonio: idle (0 active sessions)                 │
│  🟢 Daemon: running                                   │
│                                                       │
│  20/20 services healthy                               │
╰─────────────────────────────────────────────────────╯
```

### 7.4 Chat Mode

Chat mode adalah **default mode** CLI — user ngobrol dengan Antonio langsung:

```bash
$ vyper
╭─────────────────────────────────────────────────────╮
│  🦊 Antonio — VYPER AI Agent                         │
│  "I'm Antonio, your smart contract audit specialist.  │
│   How can I help you today?"                         │
│                                                      │
│  Commands: /help, /skills, /memory, /session         │
╰─────────────────────────────────────────────────────╯

You: audit USDe contract 0x4c9edd... di Ethereum

Antonio: 🎯 Saya akan audit USDe contract.

Step 1/5: Fetching program dari Immunefi...
  → Program: Ethena (critical)
Step 2/5: Fetching source code...
  → Source fetched (3 files: USDe.sol, StakedUSDe.sol, EthenaMinting.sol)
Step 3/5: Scanning contract...
  → Slither: 12 warnings
  → Mythril: 3 issues
  → Echidna: 1 property violation
  → Halmos: Formal verification passed
Step 4/5: Analyzing findings via AI...
  → 1 Critical: Reentrancy in unstake()
  → 2 High: Oracle price manipulation, Flash loan attack
  → 3 Medium: Unchecked return values
Step 5/5: Generating report...
  ✅ Report ready: /data/reporter/USDe_2026-05-26/immunefi.md

📋 Summary:
├── Critical: 1 (Reentrancy in unstake())
├── High: 2 (Oracle manipulation, Flash loan)
├── Medium: 3
└── Low: 6

💥 Exploit confirmed: Reentrancy in unstake() — value at risk: $2.4M

Want me to:
  1. Generate PoC exploit
  2. Show detailed findings
  3. Submit to Immunefi
  4. /new task
```

**Slash Commands** (dalam chat):

| Command | Fungsi |
|---------|--------|
| `/help` | Help & available commands |
| `/skills` | Lihat skills Antonio |
| `/memory` | Lihat memory contents |
| `/session` | Status sesi saat ini |
| `/sessions` | List semua sesi |
| `/daemon` | Status daemon |
| `/health` | Cek semua service |
| `/config` | Lihat config |
| `/stats` | Pipeline statistics |
| `/new` | Reset sesi, mulai baru |
| `/exit` | Keluar CLI |

### 7.5 Implementation Plan

#### Phase 1: Core CLI (Minimal Viable)

```python
# cli/main.py — Typer app
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()

class AntonioClient:
    """HTTP client ke Antonio Agent API."""
    BASE_URL = "http://localhost:8021"

    async def run_agent(self, task_type, input_data, goal=""):
        resp = await httpx.post(f"{BASE_URL}/agent/run", json={
            "task_type": task_type,
            "input_data": input_data,
            "goal": goal,
        })
        return resp.json()

    async def get_session(self, session_id):
        resp = await httpx.get(f"{BASE_URL}/agent/{session_id}")
        return resp.json()

@app.command()
def audit(address: str, chain: str = "ethereum", program: str = None):
    """Full audit pipeline via Antonio AI Agent."""
    ...

@app.command()
def chat():
    """Interactive chat mode dengan Antonio."""
    ...

@app.command()
def health():
    """Check all services health via orchetrator."""
    ...
```

#### Phase 2: Chat Mode (Streaming)

```python
# cli/chat.py — Rich + httpx streaming
class ChatSession:
    def __init__(self):
        self.client = AntonioClient()
        self.history = []
        self.session_id = None

    async def start(self):
        """Interactive chat loop with Rich live display."""
        with Live(console=console, refresh_per_second=4) as live:
            while True:
                user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
                if user_input == "/exit":
                    break
                elif user_input.startswith("/"):
                    await self._handle_slash(user_input)
                else:
                    await self._chat_with_antonio(user_input, live)
```

#### Phase 3: Rich Output + Progress

```python
# cli/output.py
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.markdown import Markdown

def render_health(data):
    """Render health check sebagai Rich table."""
    table = Table(title="VYPER — Service Health")
    table.add_column("Status", style="bold")
    table.add_column("Service")
    table.add_column("Port")
    table.add_column("Description")
    for svc in data["services"]:
        status = "✅" if svc["healthy"] else "❌"
        table.add_row(status, svc["name"], str(svc["port"]), svc["desc"])
    return table

def render_agent_steps(session):
    """Render ReAct steps sebagai timeline."""
    steps = []
    for step in session["steps"]:
        icon = "💭" if step["action"] == "think" else "🔧"
        steps.append(f"{icon} **{step['action']}**: {step['observation'][:100]}")
    return "\n".join(steps)
```

#### File Structure

```
cli/
├── __init__.py              # Package init
├── __main__.py              # python -m cli
├── main.py                  # Typer app — all commands
├── client.py                # Antonio HTTP client
├── config.py                # ~/.vyper/config.yml manager
├── output.py                # Rich formatters
├── chat.py                  # Interactive chat mode
├── commands/
│   ├── audit.py             # vyper audit
│   ├── health.py            # vyper health
│   ├── status.py            # vyper status / list / stats
│   ├── daemon.py            # vyper daemon
│   └── config_cmd.py        # vyper config
└── requirements.txt         # typer, rich, httpx, pyyaml
```

#### Dependencies

```txt
# cli/requirements.txt
typer>=0.12.0
rich>=13.0.0
httpx>=0.27.0
pyyaml>=6.0
```

---

## 8. Docker Setup

### 8.1 Base Image

```dockerfile
# Dockerfile.base
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
```

### 8.2 Docker Compose

```yaml
# docker-compose.yml — 20 services
x-service-base: &service-base
  networks: [vyper-net]
  restart: unless-stopped
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
  deploy:
    resources:
      limits: { cpus: "0.5", memory: "512M" }
      reservations: { cpus: "0.1", memory: "128M" }

services:
  01-config:
    build: services/01-config
    ports: ["8011:8000"]
    volumes: [vyper_config:/data/config]
    # ... (20 services)

volumes:
  vyper_agent:
  vyper_dashboard:
  vyper_config:
  vyper_scanner_slither:
  vyper_scanner_echidna:
  vyper_scanner_forge:
  vyper_scanner_halmos:
  vyper_immunefi:
  vyper_source:
  vyper_scanner:
  vyper_scanner_mythril:
  vyper_ai:
  vyper_classifier:
  vyper_exploit:
  vyper_reporter:
  vyper_notifier:
  vyper_orchestrator:
  vyper_webhook:
  vyper_upkeep:
  vyper_submission:
  vyper_learning:

networks:
  vyper-net:
    driver: bridge
```

### 8.3 Docker Commands

```bash
# Build & start semua service
docker compose up --build -d

# Start service tertentu
docker compose up -d 14-agent

# Lihat log
docker compose logs -f 14-agent
docker compose logs -f 11-orchestrator

# Scale scanner
docker compose up --scale 04-scanner=3 -d

# Stop
docker compose down

# Build ulang satu service
docker compose build 14-agent

# Hapus volume (data hilang!)
docker compose down -v
```

### 8.4 Service Dependencies Graph

```
01-config (tidak depend on anyone)
  ├── 02-immunefi
  ├── 03-source
  ├── 04-scanner
  ├── 04a-scanner-slither
  ├── 04b-scanner-echidna
  ├── 04c-scanner-forge
  ├── 04d-scanner-halmos
  ├── 05-scanner-mythril
  ├── 06-ai
  ├── 07-classifier
  ├── 08-exploit
  ├── 09-reporter
  ├── 10-notifier
  ├── 11-orchestrator (depends on 02,03,04,04a-d,05,06,07,08,09,10)
  ├── 12-webhook
  ├── 13-upkeep
  ├── 14-agent (depends on 02,03,04,06,07,08,09,10)
  ├── 15-dashboard (depends on 11, 01)
  └── 16-submission (depends on 02,03,06,08,11)
```

---

## 9. Data Storage

### 9.1 Volume Structure

Semua data persist di Docker volumes, mount dari `~/.vyper/`:

```
~/.vyper/
│
├── config/config.json                    # Global config (shared read-only)
│
├── immunefi/
│   ├── programs/{slug}.json             # Detail per program
│   ├── history/{slug}.jsonl             # Append-only change log
│   └── indexes/                         # Fast lookup indexes
│
├── source/
│   ├── contracts/{chain}/{addr}/        # Source code cache
│   └── repos/{slug}/                    # Cloned GitHub repos
│
├── scanner/
│   ├── results/{audit_id}/              # Raw scan output
│   └── solc/{version}/solc             # Cached solc binaries
│
├── ai/cache/{finding_hash}.json         # LLM response cache
│
├── classifier/
│   ├── findings.json                    # All findings
│   ├── patterns.json                    # Vulnerability patterns
│   └── metrics.json                     # TP/FP/TN/FN metrics
│
├── exploit/results/{finding_id}/        # PoC scripts + results
│
├── reporter/reports/{audit_id}/         # immunefi.md + full.md
│
├── notifier/delivery.log               # Delivery log
│
├── orchestrator/
│   ├── queue.json                       # Priority queue
│   ├── audit_log.json                   # Audit history
│   └── similarity.json                  # Contract clusters
│
├── agent/                               # Antonio memory
│   ├── vector_index.json                # Vector memory
│   ├── episodic.json                    # Session history
│   └── graph.json                       # Knowledge graph
│
├── webhook/delivery.log                # Webhook log
│
├── upkeep/backups/{name}.tar.gz        # Backup archives
│
├── submission/                          # Submission data
│
└── learning/                            # Shared learning data
    ├── feedback.json                    # All feedback
    ├── false_negatives.json            # FN tracker
    └── false_positives.json            # FP tracker
```

### 9.2 Kenapa JSON, Bukan SQL?

| Faktor | Database Engine | JSON Files |
|--------|----------------|------------|
| Setup | Install, config, migrations, pooling | `mkdir -p ~/.vyper/` — selesai |
| Startup | 5-30 detik | 0ms |
| Backup | Tool spesifik | `cp -r ~/.vyper/ backup/` |
| Portabilitas | Bind ke versi | Bisa di-`git`, di-`rsync`, di-`zip` |
| Debuggable | Query | `vim`, `grep`, `jq`, `cat` |

---

## 10. Development Guide

### 10.1 Prasyarat

```bash
# 1. Python 3.11+
python --version  # >= 3.11

# 2. Docker & Docker Compose
docker --version       # >= 24.0
docker compose version

# 3. Git
git --version

# 4. (Optional) Go — hanya jika develop Go components
go version
```

### 10.2 Setup Development

```bash
# Clone
git clone <repo-url> sc_auditor
cd sc_auditor

# Setup Python venv (untuk development tools)
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dev dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
# Isi API key jika perlu
```

### 10.3 Development Workflow

```bash
# 1. Build & start semua service
docker compose up --build -d

# 2. Cek health
curl http://localhost:8009/health

# 3. Cek service tertentu
curl http://localhost:8021/health  # Antonio

# 4. Test audit
curl -X POST http://localhost:8009/audit \
  -H "Content-Type: application/json" \
  -d '{"address": "0xdAC17F958D2ee523a2206206994597C13D831ec7", "chain": "ethereum"}'

# 5. Cek status
curl http://localhost:8009/audit/{audit_id}

# 6. Lihat log
docker compose logs -f 11-orchestrator
```

### 10.4 Testing

```bash
# Run all tests
pytest

# Test specific service
pytest tests/services/test_agent.py -v

# E2E test (requires Docker)
pytest tests/e2e/ -v --docker

# Coverage
pytest --cov=services --cov-report=html
```

### 10.5 Service Pattern

Setiap service mengikuti pola yang sama:

```
services/{N}-nama/
├── Dockerfile
├── requirements.txt
├── app.py                    # FastAPI app + endpoints
├── src/
│   ├── __init__.py
│   ├── models.py             # Pydantic models
│   ├── config.py             # Service-specific config
│   └── *.py                  # Business logic
└── tests/                    # (optional) Unit tests
```

**app.py template:**
```python
"""Service name — description."""

from fastapi import FastAPI
from shared.observability import setup_observability

app = FastAPI(title="Service Name", version="1.0.0")
logger = setup_observability(app, "N-service-name", "1.0.0")

@app.get("/health")
async def health():
    return {"data": {"service": "name", "status": "ok"}, "meta": {"status": "ok"}}
```

---

## 11. Quick Start

### 11.1 Production

```bash
# 1. Clone & setup
git clone <repo-url> sc_auditor
cd sc_auditor

# 2. (Optional) API keys
cp .env.example .env
# Isi OPENAI_API_KEY, ANTHROPIC_API_KEY, dll

# 3. Start semua service
docker compose up --build -d

# 4. Buka Dashboard
start http://localhost:8000

# 5. Audit via Dashboard atau API
curl -X POST http://localhost:8009/audit \
  -H "Content-Type: application/json" \
  -d '{"address": "0x4c9edd5852cd905f086c759e8383e09bff1e68b3", "chain": "ethereum"}'
```

### 11.2 Chat dengan Antonio

```bash
# Via API langsung
curl -X POST http://localhost:8021/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "full_audit",
    "input_data": {
      "contract_address": "0x4c9edd5852cd905f086c759e8383e09bff1e68b3",
      "chain": "ethereum"
    },
    "goal": "Full audit USDe contract — cari semua vulnerability",
    "max_steps": 25
  }'

# Cek hasil
curl http://localhost:8021/agent/agent-abc123

# Team audit
curl -X POST http://localhost:8021/team/run \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "full_audit",
    "input_data": {
      "contract_address": "0x4c9edd5852cd905f086c759e8383e09bff1e68b3",
      "chain": "ethereum"
    },
    "goal": "Full audit with team — Code Analyst + Exploit Specialist + Report Writer"
  }'
```

### 11.3 System Check

```bash
# Cek health orchestrator
curl http://localhost:8009/health

# Cek Antonio status
curl http://localhost:8021/health

# Cek Antonio skills
curl http://localhost:8021/skills

# Cek daemon status
curl http://localhost:8021/daemon/status

# Start Antonio daemon
curl -X POST http://localhost:8021/daemon/start

# Lihat memory Antonio
curl http://localhost:8021/memory
```

### 11.4 Pipeline Stats

```bash
# Pipeline statistics
curl http://localhost:8009/stats

# Priority queue
curl http://localhost:8009/queue

# Resource governor
curl http://localhost:8009/resources

# Contract similarity
curl http://localhost:8009/similarity
```

---

> **VYPER** — Scan smarter, hunt faster.
>
> Dokumentasi ini mencakup arsitektur lengkap, 20 service, pipeline audit, Antonio AI Agent,
> API reference, dan blueprint CLI baru berbasis chat dengan Antonio.
>
> Last updated: 2026-05-26
