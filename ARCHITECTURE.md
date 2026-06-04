# VYPER — Architecture

> **Canonical architecture document for VYPER v0.4.x**
> **Last updated**: June 4, 2026
> **Status**: IMPLEMENTED — reflects actual running system

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Complete Service Catalog](#3-complete-service-catalog)
4. [Service Groups](#4-service-groups)
5. [Communication Patterns](#5-communication-patterns)
6. [Audit Pipeline](#6-audit-pipeline)
7. [Storage Architecture](#7-storage-architecture)
8. [Bug Classification System](#8-bug-classification-system)
9. [Antonio Supremacy — AI Agent Controller](#9-antonio-supremacy--ai-agent-controller)
10. [Key Design Decisions](#10-key-design-decisions)
11. [Deployment](#11-deployment)
12. [Historical Context](#12-historical-context)

---

## 1. Overview

**VYPER** is a local-first smart contract security auditing platform. It runs **28 microservices** on a single machine via Docker Compose.

### Core Numbers

| Metric | Value |
|--------|-------|
| Services | **28** (all Python 3.11+ FastAPI) |
| Dashboard | React 18 + TypeScript + Tailwind v4 + Vite |
| Communication | HTTP/REST (httpx) |
| Storage | JSON + Markdown files (Docker volumes) |
| Deployment | `docker compose up` |
| Dashboard Port | `8000` |
| Service Ports | `8001`–`8028` |

### Philosophy

```
┌──────────────────────────────────────────────────────────────┐
│                        VYPER v0.4.x                          │
│                                                              │
│  28 microservices, 1 laptop, 1 command.                      │
│                                                              │
│  docker compose up                                          │
│    ↓                                                         │
│  All services run, communicate via HTTP/REST.               │
│                                                              │
│  Dashboard: http://localhost:8000                            │
│  API Gateway: http://localhost:8000/api/*                    │
└──────────────────────────────────────────────────────────────┘
```

### Why Microservices?

| Factor | Monolith | VYPER (Microservice) |
|--------|----------|----------------------|
| **Isolation** | Slither crash → all stops | Scanner crash → other services keep running |
| **Scaling** | One process | `docker compose up --scale 04-scanner=3` |
| **Updates** | Redeploy everything | Update Scanner v2 without touching AI |
| **Debugging** | Mixed logs | `docker logs vyper-04-scanner-1` |
| **Dependencies** | One requirements.txt (conflicts) | Each service has its own |

---

## 2. Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│  USER                                                                    │
│   │                                                                      │
│   ▼                                                                      │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  15-DASHBOARD (port 8000)  React SPA + API Gateway               │   │
│  │  Proxy to all backend services via ServiceProxy                   │   │
│  └────────┬─────────────────────────────────────────────────────────┘   │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  11-ORCHESTRATOR (port 8009)  Pipeline Heart                      │   │
│  │  - Priority queue & daemon mode                                    │   │
│  │  - State machine (8 stage)                                         │   │
│  │  - HTTP/REST calls to all services                                 │   │
│  └──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──────────────────────┘   │
│     │  │  │  │  │  │  │  │  │  │  │  │  │  │  │                         │
│     ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼                         │
│  ┌────── SCANNER GROUP ──────────────────────────────────────────┐      │
│  │ ┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐                          │      │
│  │ │04a ││04b ││04c ││04d ││04e ││ 05 │  6 Scanner Services      │      │
│  │ │Slit││Echd││Forg││Halm││Mant││Myth│                          │      │
│  │ │8014││8015││8016││8017││8020││8013│                          │      │
│  │ └────┘└────┘└────┘└────┘└────┘└────┘                          │      │
│  └────────────────────────────────────────────────────────────────┘      │
│                                                                          │
│  ┌────── CORE SERVICES ─────────────────────────────────────────┐      │
│  │ ┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐                  │      │
│  │ │ CFG││ IM ││ SRC││SCN ││ AI ││CLS ││EXP │                  │      │
│  │ │8011││8001││8002││8003││8004││8005││8006│                  │      │
│  │ └────┘└────┘└────┘└────┘└────┘└────┘└────┘                  │      │
│  │ ┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐                  │      │
│  │ │RPT ││NTF ││WHK ││UPK ││SUB ││EXP ││AGNT│                  │      │
│  │ │8007││8008││8010││8012││8018││8019││8021│                  │      │
│  │ └────┘└────┘└────┘└────┘└────┘└────┘└────┘                  │      │
│  └────────────────────────────────────────────────────────────────┘      │
│                                                                          │
│  ┌────── BOUNTY PLATFORMS ──────────────────────────────────────┐      │
│  │ ┌──────┐┌──────┐┌──────┐┌──────┐                              │      │
│  │ │18 C4 ││19 SHL││20 CNT││21 HAT│  4 Platform Integrations    │      │
│  │ │ 8022 ││ 8023 ││ 8024 ││ 8025 │                              │      │
│  │ └──────┘└──────┘└──────┘└──────┘                              │      │
│  └────────────────────────────────────────────────────────────────┘      │
│                                                                          │
│  ┌────── MULTI-CHAIN ──────────────────────────────────────────┐      │
│  │ ┌──────────┐┌──────────┐                                      │      │
│  │ │22 STARK  ││23 CAIRO  │  StarkNet/Cairo support              │      │
│  │ │  8026    ││  8028    │                                      │      │
│  │ └──────────┘└──────────┘                                      │      │
│  └────────────────────────────────────────────────────────────────┘      │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    SHARED VOLUMES                                  │   │
│  │  vyper_learning/  vyper_kb/  vyper_config/ (JSON + Markdown)     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Complete Service Catalog

### 28 Services — Port Mapping & Dependencies

| # | Service Name | Host Port | Depends On | Category |
|---|-------------|-----------|------------|----------|
| 01 | **config** | 8011 | — | Infrastructure |
| 02 | **immunefi** | 8001 | 01-config | Data Source |
| 03 | **source** | 8002 | 01-config | Data Source |
| 04 | **scanner** | 8003 | 01-config, 04a, 04b, 04c, 04d, 04e, 05 | Scanner Router |
| 04a | **scanner-slither** | 8014 | 01-config | Scanner |
| 04b | **scanner-echidna** | 8015 | 01-config | Scanner |
| 04c | **scanner-forge** | 8016 | 01-config | Scanner |
| 04d | **scanner-halmos** | 8017 | 01-config | Scanner |
| 04e | **scanner-manticore** | 8020 | 04a-scanner-slither | Scanner |
| 05 | **scanner-mythril** | 8013 | 01-config | Scanner |
| 06 | **ai** | 8004 | 01-config | Analysis |
| 07 | **classifier** | 8005 | 01-config | Analysis |
| 08 | **exploit** | 8006 | 01-config | Analysis |
| 09 | **reporter** | 8007 | 01-config | Output |
| 10 | **notifier** | 8008 | 01-config | Output |
| 11 | **orchestrator** | 8009 | 02–10, 01-config | Orchestration |
| 12 | **webhook** | 8010 | 01-config | Output |
| 13 | **upkeep** | 8012 | 01-config | Infrastructure |
| 14 | **agent** | 8021 | 01, 02, 03, 04, 06, 07, 08, 09, 10 | AI Agent |
| 15 | **dashboard** | 8000 | 11, 01, 14 | Frontend |
| 16 | **submission** | 8018 | 01, 02, 03, 06, 08, 11 | Platform |
| 17 | **experience** | 8019 | 01-config | Learning |
| 18 | **code4rena** | 8022 | 01-config | Bounty Platform |
| 19 | **sherlock** | 8023 | 01-config | Bounty Platform |
| 20 | **cantina** | 8024 | 01-config | Bounty Platform |
| 21 | **hats** | 8025 | 01-config | Bounty Platform |
| 22 | **source-starknet** | 8026 | 01-config | Multi-Chain |
| 23 | **scanner-cairo** | 8028 | 01, 22 | Multi-Chain |

### Per-Service Details

#### Infrastructure (2 services)

| # | Service | Port | Responsibility |
|---|---------|------|----------------|
| 01 | **config** | 8011 | Global configuration, API keys, RPC endpoints. All services read config via HTTP. |
| 13 | **upkeep** | 8012 | Backups, updates, aggregate metrics, health monitoring. |

#### Data Sources (2 services)

| # | Service | Port | Responsibility |
|---|---------|------|----------------|
| 02 | **immunefi** | 8001 | Sync 234+ Immunefi programs from GitHub. Track changes, detect new contracts, prioritize by bounty. |
| 03 | **source** | 8002 | Multi-source code fetch: Etherscan, Sourcify, GitHub, Blockscout, Manual upload. |

#### Scanner Group (7 services)

| # | Service | Port | Tool | Method |
|---|---------|------|------|--------|
| 04 | **scanner** | 8003 | Router | Routes scan requests to appropriate tool service |
| 04a | **scanner-slither** | 8014 | Slither | Static analysis (control flow, inheritance, reentrancy) |
| 04b | **scanner-echidna** | 8015 | Echidna | Fuzzing & property-based testing |
| 04c | **scanner-forge** | 8016 | Foundry Forge | Build verification, test runner |
| 04d | **scanner-halmos** | 8017 | Halmos | Symbolic execution & formal verification |
| 04e | **scanner-manticore** | 8020 | Manticore | Symbolic execution (HIGH/CRITICAL focus) |
| 05 | **scanner-mythril** | 8013 | Mythril | Symbolic execution (deep path exploration) |

#### Analysis (3 services)

| # | Service | Port | Responsibility |
|---|---------|------|----------------|
| 06 | **ai** | 8004 | LLM analysis (OpenAI/Anthropic). Pure delegation receiver — no autonomous routing. |
| 07 | **classifier** | 8005 | TP/FP/TN/FN classification, metrics, confusion matrix. |
| 08 | **exploit** | 8006 | Anvil Docker engine. Fork mainnet, impersonate accounts, execute PoC, generate exploit scripts. |

#### Output (3 services)

| # | Service | Port | Responsibility |
|---|---------|------|----------------|
| 09 | **reporter** | 8007 | Generate Immunefi reports (immunefi.md) + full reports (full.md). |
| 10 | **notifier** | 8008 | Discord, Telegram, Email, Desktop notifications. |
| 12 | **webhook** | 8010 | Webhook delivery + signing for external integrations. |

#### Orchestration & AI (2 services)

| # | Service | Port | Responsibility |
|---|---------|------|----------------|
| 11 | **orchestrator** | 8009 | Pipeline coordinator. State machine, priority queue, daemon mode. |
| 14 | **agent** | 8021 | **ANTONIO** — The absolute AI agent controller. ReAct loop, AgentRegistry, memory, learning. |

#### Frontend (1 service)

| # | Service | Port | Responsibility |
|---|---------|------|----------------|
| 15 | **dashboard** | 8000 | React SPA + FastAPI backend. API Gateway proxying to all services. SSE real-time events. |

#### Platform Features (2 services)

| # | Service | Port | Responsibility | Added |
|---|---------|------|----------------|-------|
| 16 | **submission** | 8018 | Bug bounty submission agent. Auto-submit to Immunefi, track status, bounty tracking. | June 1, 2026 |
| 17 | **experience** | 8019 | Cross-agent learning system. SQLite-backed experience store. Feedback loop central. | June 2, 2026 |

#### Bounty Platform Integrations (4 services)

| # | Service | Port | Platform | API Type | Added |
|---|---------|------|----------|----------|-------|
| 18 | **code4rena** | 8022 | Code4rena | GraphQL | June 3, 2026 |
| 19 | **sherlock** | 8023 | Sherlock | REST | June 3, 2026 |
| 20 | **cantina** | 8024 | Cantina | REST | June 3, 2026 |
| 21 | **hats** | 8025 | Hats Finance | REST | June 3, 2026 |

#### Multi-Chain Expansion (2 services)

| # | Service | Port | Chain | Language | Added |
|---|---------|------|-------|----------|-------|
| 22 | **source-starknet** | 8026 | StarkNet | Cairo | June 3, 2026 |
| 23 | **scanner-cairo** | 8028 | StarkNet | Cairo | June 3, 2026 |

---

## 4. Service Groups

```
┌────────────────────────────────────────────────────────────┐
│                    SERVICE GROUPS                           │
│                                                            │
│  INFRASTRUCTURE (2):   01-config, 13-upkeep               │
│  DATA SOURCES (2):     02-immunefi, 03-source              │
│  SCANNERS (7):         04-router, 04a-slither, 04b-echidna,│
│                        04c-forge, 04d-halmos,               │
│                        04e-manticore, 05-mythril            │
│  ANALYSIS (3):         06-ai, 07-classifier, 08-exploit    │
│  OUTPUT (3):           09-reporter, 10-notifier, 12-webhook│
│  ORCHESTRATION (2):    11-orchestrator, 14-agent           │
│  FRONTEND (1):         15-dashboard                        │
│  PLATFORM (2):         16-submission, 17-experience        │
│  BOUNTY PLATFORMS (4): 18-code4rena, 19-sherlock,          │
│                        20-cantina, 21-hats                  │
│  MULTI-CHAIN (2):      22-source-starknet, 23-scanner-cairo│
│                                                            │
│  TOTAL: 28 services                                       │
└────────────────────────────────────────────────────────────┘
```

---

## 5. Communication Patterns

### 5.1 HTTP/REST (Primary)

All inter-service communication uses **HTTP/REST** via Python `httpx` (async).

```
┌──────────────────────────────────────────────────────────┐
│              COMMUNICATION MATRIX                         │
├────────────┬────────────────────┬────────────────────────┤
│ PATTERN    │ USE CASE           │ TECHNOLOGY             │
├────────────┼────────────────────┼────────────────────────┤
│ Sync REST  │ Service-to-service │ httpx (async)          │
│            │ API calls          │ FastAPI endpoints      │
├────────────┼────────────────────┼────────────────────────┤
│ SSE        │ Real-time pipeline │ Server-Sent Events     │
│            │ progress to UI     │ (Dashboard ↔ Orch)     │
├────────────┼────────────────────┼────────────────────────┤
│ Docker API │ Anvil container    │ docker-py              │
│            │ lifecycle mgmt     │ /var/run/docker.sock   │
└────────────┴────────────────────┴────────────────────────┘
```

### 5.2 Service Dependency Graph

```
01-config ──────────────── (all services read config via HTTP)
    │
    ├── 02-immunefi ────── GitHub API
    ├── 03-source ──────── Etherscan, Sourcify, GitHub
    ├── 04-scanner ─────── 04a, 04b, 04c, 04d, 04e, 05
    ├── 06-ai ──────────── OpenAI / Anthropic API
    ├── 07-classifier
    ├── 08-exploit ─────── Docker socket (Anvil)
    ├── 09-reporter
    ├── 10-notifier ────── Discord, Telegram, SMTP
    ├── 11-orchestrator ── (calls: 02, 03, 04, 06, 07, 08, 09, 10)
    ├── 12-webhook
    ├── 13-upkeep
    ├── 14-agent ───────── (calls: 02, 03, 04, 06, 07, 08, 09, 10, 11)
    ├── 15-dashboard ───── (calls: all services via proxy)
    ├── 16-submission ──── (calls: 02, 03, 06, 08, 11)
    ├── 17-experience
    ├── 18-code4rena ───── Code4rena GraphQL API
    ├── 19-sherlock ────── Sherlock REST API
    ├── 20-cantina ─────── Cantina REST API
    ├── 21-hats ────────── Hats Finance REST API
    ├── 22-source-starknet Voyager + Starkscan API
    └── 23-scanner-cairo ─ (calls: 22-source-starknet)
```

### 5.3 Config Service Pattern

All services read configuration from **01-config** via HTTP:

```python
# Every service does this at startup:
config = httpx.get("http://01-config:8000/config").json()
```

Config Service is the **only shared dependency**. No service reads another service's data directly — all access goes through APIs.

---

## 6. Audit Pipeline

### 6.1 Pipeline Stages

Each audit goes through **8 stages**, orchestrated by **11-orchestrator**:

```
                          ┌─────────────┐
                          │  PENDING    │
                          └──────┬──────┘
                                 │ start
                                 ▼
                     ┌─────────────────────┐
                     │  FETCHING_PROGRAM   │ ← 02-immunefi:8001
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  FETCHING_SOURCE    │ ← 03-source:8002
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  SCANNING           │ ← 04-scanner → 04a/b/c/d/e + 05
                     │  Slither + Mythril  │
                     │  + Echidna + Halmos │
                     │  + Manticore        │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  AI_ANALYSIS        │ ← 06-ai (LLM verdict)
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  CLASSIFYING        │ ← 07-classifier (TP/FP)
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  EXPLOITING         │ ← 08-exploit (Anvil)
                     │  (only if TP        │
                     │   critical/high)    │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  REPORTING          │ ← 09-reporter
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  NOTIFYING          │ ← 10-notifier
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  COMPLETED          │ ✓
                     └─────────────────────┘

  States: pending → fetching_program → fetching_source → scanning →
  ai_analysis → classifying → exploiting? → reporting → notifying → completed
```

### 6.2 Orchestrator State Machine

The Orchestrator uses a **10-state async state machine** with:

- **Retry mechanism** (3 attempts with exponential backoff)
- **Saga pattern** for rollback on failure
- **Timeout per stage** (configurable)
- **Daemon mode** for autonomous operation

### 6.3 Time Estimates

| Stage | Time (per contract) |
|-------|---------------------|
| Source Fetch | ~10s |
| Slither | ~60s |
| Mythril | 5–30 min |
| Echidna | 5–15 min |
| Halmos | 2–10 min |
| Manticore | 5–20 min |
| AI Analysis | ~30s |
| Classification | ~5s |
| Exploit (if TP) | 2–10 min |
| Report | ~10s |
| **Total (all tools)** | **15–60 min** |

---

## 7. Storage Architecture

### 7.1 JSON File-Based Storage

**No database engines.** All data stored as JSON files in Docker volumes.

```
~/.vyper/
│
├── config/config.json              # Global config
├── immunefi/programs/{slug}.json   # Per program
├── source/contracts/{chain}/{addr}/# Source cache
├── scanner/results/{audit_id}/     # Scan results
├── ai/cache/{hash}.json            # LLM response cache
├── classifier/metrics.json         # TP/FP metrics
├── exploit/results/{id}/           # PoC scripts
├── reporter/reports/{audit_id}/    # immunefi.md + full.md
├── learning/feedback.json          # User feedback
└── experience/*.db                 # SQLite (17-experience only)
```

### 7.2 Data Ownership

| Rule | Description |
|------|-------------|
| **Per-service volume** | Each service has its own Docker volume |
| **No cross-volume access** | Services never read another service's files directly |
| **Config read-only** | All services read config via HTTP, not direct file access |
| **Shared learning** | `vyper_learning` volume shared by classifier + orchestrator |
| **Shared knowledge base** | `vyper_kb` volume shared by classifier + exploit |

### 7.3 Why JSON, Not SQL

| Factor | Database | JSON Files |
|--------|----------|------------|
| Setup | Install, config, migrations | `mkdir -p ~/.vyper/` — done |
| Backup | Tool-specific | `cp -r ~/.vyper/ backup/` |
| Portability | Bound to version | Git, rsync, zip |
| Debugging | Need query tool | `vim`, `grep`, `jq`, `cat` |
| Data size | Overhead for small data | Matches actual needs (~50MB) |

> **Exception**: 17-experience uses SQLite for structured learning data.

---

## 8. Bug Classification System

### 8.1 The 4-Quadrant Detection Matrix

Every finding is classified into 4 categories:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DETECTION MATRIX (Confusion Matrix)              │
├─────────────────────────────┬───────────────────────────────────────┤
│                             │  ACTUAL VULNERABILITY                 │
│                             ├──────────────┬────────────────────────┤
│                             │  YES (Bug)   │  NO (No Bug)           │
├────────────┬────────────────┼──────────────┼────────────────────────┤
│ DETECTED   │ POSITIVE (P)   │  TRUE POS    │  FALSE POS             │
│ (Tool says │                │  (TP)        │  (FP)                  │
│  "is bug") │                │  ✅ Real bug │  ❌ False alarm        │
│            │                │  → Submit    │  → Record, adjust      │
│            ├────────────────┼──────────────┼────────────────────────┤
│            │ NEGATIVE (N)   │  FALSE NEG   │  TRUE NEG              │
│            │                │  (FN)        │  (TN)                  │
│            │                │  ⚠️ Missed!  │  ✅ Correctly safe     │
│            │                │  → MOST       │  → Record, increase   │
│            │                │    IMPORTANT  │    confidence         │
└────────────┴────────────────┴──────────────┴────────────────────────┘
```

### 8.2 Finding Lifecycle

```
STAGE 0: RAW (from Scanner)        → classification: unknown
STAGE 1: AI VERDICT (06-ai)        → TP (confirmed) / FP (rejected)
STAGE 2: EXPLOIT TEST (08-exploit) → exploit success → TP confirmed
                                   → exploit fail → FP (or human review)
STAGE 3: HUMAN REVIEW (Dashboard)  → final classification
STAGE 4: IMMUNEFI SUBMISSION       → accepted = TP final
                                   → rejected = trigger reclassification
STAGE 5: LEARNING LOOP             → TP → reinforce pattern
                                   → FP → update filter
                                   → FN → 🚨 critical: create new pattern
```

### 8.3 Dual Reporting

| Level | Audience | Content |
|-------|----------|---------|
| **immunefi.md** | Bug bounty submission | TP-only, PoC required, Immunefi format |
| **full.md** | Internal learning | All classifications + confusion matrix + metrics |

---

## 9. Antonio Supremacy — AI Agent Controller

> **Antonio (14-agent)** is the **single absolute AI agent controller**. All services, all agents, all pipelines operate under Antonio's command.

### 9.1 Chain of Command

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CHAIN OF COMMAND — VYPER PLATFORM                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  LEVEL 0: USER (Human Operator)                                         │
│  │ Only communicates with ANTONIO                                       │
│  │ NO direct access to service agents                                   │
│  │ Input: "Antonio, audit contract 0x..."                               │
│         │                                                               │
│         ▼                                                               │
│  LEVEL 1: ANTONIO (14-agent) — ABSOLUTE CONTROLLER                      │
│  │ Only AI Agent with full ReAct loop                                   │
│  │ Single owner of AgentRegistry                                        │
│  │ Controls all delegation (DelegateTaskSkill)                          │
│  │ Centralized memory (vector + episodic + semantic + graph)            │
│  │ Central learning (FeedbackLearner)                                   │
│         │                                                               │
│         ▼                                                               │
│  LEVEL 2: ORCHESTRATOR (11) — Antonio's subordinate                     │
│  │ Pipeline state machine — NO AI autonomy                              │
│  │ Daemon only active when Antonio/Dashboard enables it                 │
│         │                                                               │
│         ▼                                                               │
│  LEVEL 3: SERVICE AGENTS (02-23, except 14)                             │
│  │ All are BaseAgents — receive delegation, no initiative               │
│  │ No access to Antonio's AgentRegistry                                 │
│  │ No AI ReAct loop — pure task executors                               │
│  │ Report back to Antonio, not to user                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Antonio Supremacy Rules (Unbreakable)

| Rule | Description | Status |
|------|-------------|--------|
| **R1** | Antonio is the ONLY AI — no other service has LLM/ReAct | ✅ Enforced |
| **R2** | AgentRegistry belongs to Antonio alone | ✅ Enforced |
| **R3** | All delegation goes through Antonio | ✅ Enforced |
| **R4** | No autonomy without Antonio's permission | ✅ Enforced |
| **R5** | User only talks to Antonio (Dashboard has 1 AI chat) | ✅ Enforced |
| **R6** | Memory & learning centralized in Antonio | ✅ Enforced |

### 9.3 Service 06-ai: Stripped to Pure Delegation

**06-ai was stripped (June 2, 2026)** to comply with Antonio Supremacy:

- ❌ Removed: SkillRegistry, autonomous routing, severity-based strategy selection
- ✅ Kept: `LLMClient` as technical execution layer (no AI agency)
- ✅ Kept: REST endpoints for backward compatibility (Antonio controls when to call)

---

## 10. Key Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **HTTP/REST only** (not gRPC) | Simpler debugging, all services in same Docker network |
| 2 | **Python 3.11+ exclusively** | Slither/Mythril/Echidna all Python-native. Single language = simpler. |
| 3 | **JSON file storage** | No database setup. Portable. Debuggable with standard tools. |
| 4 | **Docker Compose** (not K8s) | Single laptop target. No need for orchestration complexity. |
| 5 | **Per-service Dockerfile** | Independent builds. Smaller images. Isolated dependencies. |
| 6 | **Config Service as single dependency** | All services read config via HTTP. Centralized API key management. |
| 7 | **Scanner isolation** | Each scanner is a separate service. One crash doesn't affect others. |
| 8 | **Antonio as sole AI** | Single AI brain prevents conflicting autonomous decisions. |
| 9 | **Dashboard as API Gateway** | React SPA proxies to all backend services. Single entry point. |
| 10 | **No message queue** | Direct HTTP calls simpler than NATS/Kafka for single-machine use. |

---

## 11. Deployment

### 11.1 Quick Start

```bash
# Build & start all 28 services
docker compose up --build -d

# Check health
docker compose ps

# View logs
docker compose logs -f 15-dashboard
docker compose logs -f 11-orchestrator

# Scale scanners
docker compose up --scale 04-scanner=3 -d
```

### 11.2 Access Points

| URL | Service |
|-----|---------|
| `http://localhost:8000` | Dashboard (React SPA) |
| `http://localhost:8000/api/*` | API Gateway (proxied to all services) |
| `http://localhost:8009/audit/start` | Direct Orchestrator API |

### 11.3 Resource Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 4 core | 8 core |
| RAM | 8 GB | 16 GB |
| Disk | 20 GB | 50 GB SSD |

---

## 12. Historical Context

This architecture evolved through several iterations:

```
May 17, 2026       May 17, 2026       May 20, 2026       June 1-3, 2026      June 4, 2026
    │                   │                   │                   │                   │
    ▼                   ▼                   ▼                   ▼                   ▼
┌─────────┐       ┌─────────┐       ┌─────────────┐    ┌─────────────┐    ┌──────────────┐
│ 14 svc  │──────▶│ 1 CLI   │──────▶│ 20 services  │───▶│ +8 services  │───▶│ 28 SERVICES  │
│ SaaS    │       │ package │       │ Docker       │    │ (04e, 16-23) │    │ RUNNING      │
│ proto   │       │ Python  │       │ Compose      │    │              │    │              │
│ gRPC    │       │ (PIVOT) │       │ REST         │    │              │    │              │
│ NATS    │       │         │       │              │    │              │    │              │
└─────────┘       └─────────┘       └─────────────┘    └─────────────┘    └──────────────┘
    │                   │                   │                   │                   │
    ▼                   ▼                   ▼                   ▼                   ▼
 ARCHITECTURE.md    BRAINSTORMING       VYPER.md           (no docs)         THIS DOC
 (archived →        _SUMMARY.md        (partially         (ghost           
  docs/historical/)  (archived →        outdated)          services)        
                     docs/historical/)                                       
```

### Archived Documents

| Document | Archive Location | Why Archived |
|----------|-----------------|--------------|
| `ARCHITECTURE.md` (proto/gRPC) | `docs/historical/ARCHITECTURE_v1_proto.md` | Never implemented |
| `BRAINSTORMING_SUMMARY.md` | `docs/historical/BRAINSTORMING_v1.md` | Multiple pivots, outdated |

---

> **This document is the canonical source of truth for VYPER architecture.**
> **Last updated**: June 4, 2026 — reflects 28 services running via Docker Compose.
>
> *Maintained by lore-master*
