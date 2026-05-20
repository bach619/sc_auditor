# 🛡️ VYPER — Smart Contract Bug Hunter

> **Platform audit kontrak pintar berbasis microservice yang jalan di laptop Anda.**
> Scan, analisis, exploit, dan report dalam satu pipeline otomatis.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)](https://docker.com)
[![React](https://img.shields.io/badge/React_18-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat)](LICENSE)

---

## 📋 Daftar Isi

- [Apa Itu VYPER?](#apa-itu-vyper)
- [Arsitektur](#arsitektur)
- [Pipeline Audit](#pipeline-audit)
- [19 Microservices](#19-microservices)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [CLI Tool](#cli-tool)
- [Dashboard](#dashboard)
- [Status Pengembangan](#status-pengembangan)
- [Struktur Project](#struktur-project)
- [FAQ](#faq)

---

## Apa Itu VYPER?

**VYPER** adalah platform **smart contract security auditing** yang berjalan sepenuhnya di lokal via Docker Compose. Dirancang untuk:

- 🎯 **Bug Bounty Hunter** — Scan kontrak dari program Immunefi, temukan True Positive, hasilkan laporan siap-submit
- 🔬 **Security Researcher** — Eksploitasi temuan dengan Anvil fork engine, buktikan kerentanan
- 📊 **Platform Metrics** — Lacak presisi tiap tool (Slither, Mythril, AI), belajar dari False Negative

### Filosofi

```
┌──────────────────────────────────────────────────────────────┐
│                        VYPER                                  │
│                                                              │
│  19 microservices, 1 laptop.                                 │
│                                                              │
│  docker compose up                                          │
│    ↓                                                         │
│  Semua service jalan, komunikasi via HTTP/REST.              │
│                                                              │
│  Dashboard: http://localhost:8000                            │
│  CLI:       vyper audit 0x4c9edd...                         │
└──────────────────────────────────────────────────────────────┘
```

### Kenapa Microservice?

| Faktor | Monolith | VYPER (Microservice) |
|--------|----------|----------------------|
| **Isolasi** | Slither crash → semua berhenti | Scanner crash → service lain tetap jalan |
| **Scale** | Satu proses | `docker compose up --scale scanner=3` |
| **Update** | Deploy ulang semua | Update Scanner v2 tanpa sentuh AI |
| **Debug** | Log campur aduk | `docker logs vyper-04-scanner-1` |
| **Dependency** | Satu requirements.txt (konflik) | Masing-masing service punya sendiri |

---

## Arsitektur

```
┌──────────────────────────────────────────────────────────────────┐
│  USER                                                             │
│   │                                                              │
│   ▼                                                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  15-DASHBOARD (port 8000)  React SPA + API Gateway       │   │
│  │  Proxy ke semua service backend via ServiceProxy         │   │
│  └────────┬─────────────────────────────────────────────────┘   │
│           │                                                    │
│           ▼                                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  11-ORCHESTRATOR (port 8009)  Jantung Pipeline            │   │
│  │  - Priority queue & daemon mode                           │   │
│  │  - State machine 10 stage                                  │   │
│  │  - Contract similarity & retroactive re-run               │   │
│  │  - Resource governor (tool concurrency)                   │   │
│  └──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬───────────────────┘   │
│     │  │  │  │  │  │  │  │  │  │  │  │  │                      │
│     ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼                      │
│  ┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐ │
│  │ CFG││ IM ││ SRC││SCN ││ SLS││ECH ││ FRG││HAL ││MTH ││ AI │ │
│  │8011││8001││8002││8003││8014││8015││8016││8017││8013││8004│ │
│  └────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘ │
│     │    │    │    │                                            │
│     ▼    ▼    ▼    ▼                                            │
│  ┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐             │
│  │CLS ││EXP ││RPT ││NTF ││WHK ││UPK ││AGNT││DSH │             │
│  │8005││8006││8007││8008││8010││8012││8018││8000│             │
│  └────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘             │
└──────────────────────────────────────────────────────────────────┘
```

### Service Map

| # | Service | Port | Peran |
|---|---------|------|-------|
| 01 | **Config** | 8011 | Konfigurasi global + API keys |
| 02 | **Immunefi** | 8001 | Sync 234+ program bug bounty, deteksi repo |
| 03 | **Source** | 8002 | Multi-source fetch (GitHub, Sourcify, Etherscan, Blockscout) |
| 04 | **Scanner** | 8003 | Main scanner — routing ke tool spesifik |
| 04a | **Scanner Slither** | 8014 | Static analysis (control flow, inheritance) |
| 04b | **Scanner Echidna** | 8015 | Fuzzing & property-based testing |
| 04c | **Scanner Forge** | 8016 | Build verification (Foundry) |
| 04d | **Scanner Halmos** | 8017 | Symbolic execution & formal verification |
| 05 | **Scanner Mythril** | 8013 | Symbolic execution (deep path exploration) |
| 06 | **AI** | 8004 | LLM analysis (OpenAI/Anthropic), verdict, fix suggestion |
| 07 | **Classifier** | 8005 | TP/FP/TN/FN classification + metrics |
| 08 | **Exploit** | 8006 | Anvil Docker engine + PoC generation |
| 09 | **Reporter** | 8007 | Generate laporan Immunefi + full report |
| 10 | **Notifier** | 8008 | Discord / Telegram / Email / Desktop |
| 11 | **Orchestrator** | 8009 | Pipeline coordinator + state machine |
| 12 | **Webhook** | 8010 | Webhook delivery + signing |
| 13 | **Upkeep** | 8012 | Backup, update, metrics agregat |
| 14 | **Agent** | 8018 | Autonomous agent orchestration |
| 15 | **Dashboard** | 8000 | React SPA + API Gateway + SSE events |

---

## Pipeline Audit

Setiap audit melalui **8 stage** yang dijalankan secara sekuensial oleh Orchestrator:

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
                                │ success
                                ▼
                     ┌─────────────────────┐
                     │  SCANNING      │ ← 04-Scanner + 04a/b/c/d + 05
                     │  Slither + Mythril  │
                     │  + Echidna + Halmos │
                     └──────┬──────────────┘
                            │ success
                            ▼
                     ┌─────────────────────┐
                     │  AI_ANALYSIS       │ ← 06-AI (LLM verdict)
                     └──────┬──────────────┘
                            │ success
                            ▼
                     ┌─────────────────────┐
                     │  CLASSIFYING    │ ← 07-Classifier (TP/FP)
                     └──────┬──────────────┘
                            │ success
                            ▼
                     ┌─────────────────────┐
                     │  EXPLOITING     │ ← 08-Exploit (Anvil)
                     │  HANYA jika TP      │
                     │  critical/high      │
                     └──────┬──────────────┘
                            │ success
                            ▼
                     ┌─────────────────────┐
                     │  REPORTING      │ ← 09-Reporter
                     └──────┬──────────────┘
                            │ success
                            ▼
                     ┌─────────────────────┐
                     │  NOTIFYING      │ ← 10-Notifier
                     └──────┬──────────────┘
                            │ success
                            ▼
                     ┌─────────────────────┐
                     │  COMPLETED       │ ✓
                     └─────────────────────┘

  State: pending → fetching_program → fetching_source → scanning →
  ai_analysis → classifying → exploiting? → reporting → notifying → completed
```

Setiap state punya **failure state** (source_failed, scan_failed, timeout, dll) dengan retry mechanism dan Saga pattern untuk rollback.

---

## Tech Stack

### Foundation

| Layer | Teknologi |
|-------|-----------|
| **Bahasa** | Python 3.11+ (19 service) |
| **Framework** | FastAPI + Pydantic v2 |
| **HTTP Client** | httpx (async, connection pooling) |
| **Run** | uvicorn per service |
| **Container** | python:3.11-slim |
| **Orkestrasi** | Docker Compose v3.9 |
| **Storage** | File-based JSON (Docker volumes) |

### Audit Tools

| Tool | Fungsi | Bahasa |
|------|--------|--------|
| **Slither** | Static analysis (control flow, inheritance, reentrancy) | Python |
| **Mythril** | Symbolic execution (deep path exploration) | Python |
| **Echidna** | Fuzzing & property-based testing | Haskell (binary) |
| **Halmos** | Symbolic execution & formal verification | Python |
| **Foundry (Forge)** | Build verification, test runner | Rust (binary) |
| **Anvil** | Local fork Ethereum node untuk exploit | Rust (Docker) |

### Frontend & CLI

| Layer | Teknologi |
|-------|-----------|
| **Dashboard** | React 18 + TypeScript + Tailwind v4 |
| **CLI** | Typer + Rich + httpx async |
| **Build** | Vite 8 |

---

## Quick Start

### Prasyarat

```bash
# 1. Install Docker & Docker Compose
# 2. Clone repo
git clone <repo-url> sc_auditor
cd sc_auditor

# 3. (Opsional) Salin environment
cp .env.example .env
# isi API key jika perlu (OpenAI, Anthropic, Etherscan, dll)
```

### Jalankan Semua Service

```bash
# Build & start 19 service
docker compose up --build -d

# Cek health semua service
docker compose ps

# Lihat log service tertentu
docker compose logs -f 15-dashboard
docker compose logs -f 11-orchestrator
```

### Akses Dashboard

```
http://localhost:8000
```

Dashboard React SPA dengan:
- 📊 Overview metrics & findings
- 📋 Daftar program Immunefi
- 🔍 Detail audit per kontrak
- 📈 Platform metrics & tool performance
- ⚙️ Settings & konfigurasi

### Pipeline CLI

```bash
# Install CLI tool
pip install -e .

# Lihat semua command
vyper --help

# Docker lifecycle
vyper up          # Start semua service
vyper down        # Stop semua service
vyper status      # Cek status service
vyper logs        # Stream log

# Audit pipeline
vyper audit 0x4c9edd5852cd905f086c759e8383e09bff1e68b3 --chain ethereum
vyper scan contract.sol --tools slither,mythril
vyper exploit finding-001 --attack reentrancy

# Monitoring
vyper dashboard          # Buka dashboard di browser
vyper status aud_abc123  # Cek status audit
vyper list               # Lihat semua audit
vyper stats              # Lihat metrics platform
```

### Data Storage

Semua data persist di Docker volumes:

```
~/.vyper/
├── config/config.json           # Global config
├── immunefi/programs.json       # 234+ program
├── scanner/results/{audit_id}/  # Scan results
├── ai/cache/                    # LLM response cache
├── classifier/metrics.json      # TP/FP metrics
├── exploit/results/{id}/        # PoC scripts
├── reports/{audit_id}/          # immunefi.md + full.md
└── learning/                    # Feedback & improvements
```

---

## CLI Tool

17 commands via **Typer** CLI:

| Perintah | Fungsi |
|----------|--------|
| `vyper up` | Start Docker Compose services |
| `vyper down` | Stop semua service |
| `vyper logs` | Stream logs |
| `vyper ps` | Status containers |
| `vyper restart` | Restart services |
| `vyper audit` | Full pipeline audit |
| `vyper scan` | Quick scan (scanner only) |
| `vyper exploit` | Generate PoC |
| `vyper status` | Cek status audit |
| `vyper list` | List semua audit |
| `vyper stats` | Platform metrics |
| `vyper queue` | Lihat priority queue |
| `vyper health` | Health check semua service |
| `vyper dashboard` | Buka dashboard browser |
| `vyper config` | Config management |
| `vyper init` | Init config file |

---

## Dashboard

Dashboard adalah **React SPA** yang berjalan di port 8000, menggantikan Jinja2 templates.

### Halaman Utama

| Route | Halaman |
|-------|---------|
| `/` | Dashboard overview — metrics, findings, filters |
| `/programs` | Daftar program Immunefi |
| `/programs/:slug` | Detail program & kontrak |
| `/audits` | Riwayat audit |
| `/audits/:id` | Detail audit — findings, exploit, report |
| `/scanner` | Scanner detail per tool |
| `/exploit` | Exploit viewer |
| `/reports` | Report center |
| `/config` | Config editor |
| `/webhooks` | Webhook logs |
| `/settings` | Settings |
| `/scheduler` | Scheduled audits |

### Fitur

- 🔍 **Filter & Search** — Filter findings by classification (TP/FP/TN/FN), severity, program
- 💥 **Exploit Detail** — Lihat PoC, tx hash, value at risk, impersonated accounts
- 📊 **Metrics** — Per-tool precision/recall/F1, confusion matrix, trend charts
- ⚡ **SSE Events** — Real-time update pipeline progress
- 🌙 **Dark Mode** — Built-in theme toggle

---

## Status Pengembangan

### ✅ Selesai (v0.4.x)

| Prioritas | Status |
|-----------|--------|
| **P1: E2E Pipeline** | ✅ 7/7 steps — Immunefi → Source → Scanner → AI → Classifier → Exploit → Reporter → Notifier |
| **P2: CLI Tool** | ✅ 17 commands — Typer + Rich + httpx |
| **Scanner Split** | ✅ 04 → 04a (Slither) + 04b (Echidna) + 04c (Forge) + 05 (Mythril) + 04d (Halmos) |
| **Mythril Sidecar** | ✅ Modular isolation via container |
| **Dashboard React SPA** | ✅ Migrasi dari Jinja2 → React + Vite + Tailwind |
| **15 Services** | ✅ Semua service running, healthcheck OK |

### 🔄 Dalam Progress

| Prioritas | Target |
|-----------|--------|
| **Halmos Integration** | Symbolic execution formal verification |
| **Custom Slither Detectors** | Plugin system for custom detectors |
| **GitHub Actions** | Auto-audit tiap PR |

### 📅 Roadmap

```
Minggu:    1    2    3    4    5    6    7    8
E2E:       ████████░░░░░░░░░░░░░░░░░░░░░░░░░░
CLI:       ░░░░░░░░████████░░░░░░░░░░░░░░░░░░
Halmos:    ░░░░░░░░░░░░░░░░████████░░░░░░░░░░
GitHub:    ░░░░░░░░░░░░░░░░░░░░░░░░████░░░░░░
Detectors: ░░░░░░░░░░░░░░░░░░░░░░░░░░░░████░░
```

---

## Struktur Project

```
sc_auditor/
│
├── docker-compose.yml           # Orkestrasi 19 service
├── Dockerfile.base              # Base Python 3.11-slim image
├── .env.example                 # Template environment
│
├── vyper_lib/                   # Shared library (model, solc manager)
│   ├── models.py                # Finding, ToolResult, ApiResponse
│   └── solc_manager.py          # Compiler version management
│
├── cli/                         # CLI tool (Typer)
│   ├── main.py                  # Entry point
│   ├── client.py                # HTTP client wrapper
│   ├── output.py                # Rich output formatter
│   ├── config.py                # Config management
│   └── commands/                # 6 command groups
│       ├── docker.py            # up/down/logs/ps/restart
│       ├── audit.py             # Full pipeline
│       ├── scan.py              # Quick scan
│       ├── exploit.py           # PoC generation
│       ├── status.py            # Status monitoring
│       └── config_cmd.py        # Config CLI
│
├── services/                    # 19 microservices
│   ├── 01-config/               # Config management
│   ├── 02-immunefi/             # Immunefi scraper
│   ├── 03-source/               # Multi-source fetcher
│   ├── 04-scanner/              # Main scanner router
│   ├── 04a-scanner-slither/     # Slither
│   ├── 04b-scanner-echidna/     # Echidna
│   ├── 04c-scanner-forge/       # Foundry Forge
│   ├── 04d-scanner-halmos/      # Halmos
│   ├── 05-scanner-mythril/      # Mythril
│   ├── 06-ai/                   # LLM analysis
│   ├── 07-classifier/           # TP/FP classifier
│   ├── 08-exploit/              # Anvil exploit engine
│   ├── 09-reporter/             # Report generator
│   ├── 10-notifier/             # Discord/Telegram/Email
│   ├── 11-orchestrator/         # Pipeline coordinator
│   ├── 12-webhook/              # Webhook dispatcher
│   ├── 13-upkeep/               # Backup & metrics
│   ├── 14-agent/                # Autonomous agent
│   └── 15-dashboard/            # React SPA + API Gateway
│
├── tests/                       # Integration tests
├── scripts/                     # Utility scripts
│
├── VYPER.md                     # Arsitektur lengkap
├── VYPER_ROADMAP.md             # Roadmap & prioritas
├── ARCHITECTURE.md              # Detailed architecture (protobuf)
├── DASHBOARD.md                 # Dashboard spec
├── SCANNER_SPLIT_PLAN.md        # Scanner split plan
└── IMPLEMENTATION_PLAN.md       # Build plan
```

---

## FAQ

### Apakah butuh internet?

Se bagian. Service yang butuh internet:
- **AI Service** — API call ke OpenAI/Anthropic (opsional, bisa skip)
- **Immunefi** — Sync data program dari GitHub
- **Source** — Fetch source dari Etherscan/GitHub

Service lain berjalan **offline** penuh.

### Berapa resource yang dibutuhkan?

| Resource | Minimum | Rekomendasi |
|----------|---------|-------------|
| **CPU** | 4 core | 8 core |
| **RAM** | 8 GB | 16 GB |
| **Disk** | 20 GB | 50 GB (SSD) |
| **Docker** | 24 GB | 50 GB |

### Apakah bisa scan kontrak arbitrum/polygon/bsc?

Ya. Source Service mendukung 5 provider:
- Etherscan (Ethereum, Polygon, Arbitrum, BSC, dll)
- Sourcify (multi-chain)
- GitHub (full repo)
- Blockscout (Gnosis, Celo, dll)
- Manual (upload file)

### Bagaimana cara submit ke Immunefi?

Pipeline menghasilkan `immunefi.md` — format yang Immunefi harapkan:
- TP-ONLY (false positive otomatis difilter)
- Title, severity, SWC/CWE, description, impact, PoC, fix, references
- Siap copy-paste ke dashboard Immunefi

### Apakah bisa scale?

Ya. Semua service stateless dan bisa di-scale via Docker Compose:
```bash
docker compose up --scale 04-scanner=3 -d
```

---

## Lisensi

MIT License — lihat [LICENSE](LICENSE) untuk detail.

---

## Credits

Dibangun dengan ❤️ untuk ekosistem Web3 security.

> **VYPER** — Scan smarter, hunt faster.
