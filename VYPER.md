# VYPER — Microservice Smart Contract Bug Hunter

> **Arsitektur Final**: Microservice, Docker Compose, HTTP/REST, Python FastAPI
>
> **Catatan**: CLI (Go + Python) telah dihapus dari project. Semua interaksi via Dashboard React SPA (port 8000) atau API langsung ke service. Lihat `docker-compose.yml` untuk port mapping.
> **Target**: Personal Use — Scan Immunefi Contracts, Find TP Bugs, Generate Reports
> **Tanggal**: 20 Mei 2026

---

## 1. Filosofi

**Vyper adalah kumpulan microservice yang jalan di laptop Anda via Docker Compose.**

```
┌──────────────────────────────────────────────────────────────┐
│                        VYPER                                  │
│                                                              │
│  20 microservices, 1 laptop.                                 │
│                                                              │
│  docker compose up                                          │
│    ↓                                                         │
│  Semua service jalan, komunikasi via HTTP/REST.              │
│                                                              │
│  Dashboard: http://localhost:8000                            │
│  API Gateway: http://localhost:8000/api/*                    │
└──────────────────────────────────────────────────────────────┘
```

### Kenapa Microservice?

| Faktor | Monolith | Microservice |
|--------|----------|--------------|
| **Scanner** | Satu proses — kalau Slither crash, semua berhenti | Isolasi — Scanner crash, service lain tetap jalan |
| **AI** | Blokir pipeline sampai AI selesai | Async — AI bisa jalan sendiri, Orchestrator polling |
| **Exploit** | Anvil container dalam subprocess | Exploit service manage container sendiri |
| **Scale** | Tidak bisa scale per komponen | Scanner bisa di-scale 3 instance parallel |
| **Update** | Update semua atau tidak sama sekali | Update per service — Scanner v2 tanpa sentuh AI |
| **Bahasa** | Python untuk semua | Python semua service (25% bisa ganti nanti) |

### Kenapa Tetap Lokal (Docker Compose)?

```
✅ pip install → docker compose up   # Satu baris
✅ Semua data di ~/.vyper/           # Tetap file-based
✅ Tidak perlu Kubernetes            # Laptop cukup
✅ Bisa jalan tanpa internet         # AI service aja yang perlu API
✅ Portable — backup satu folder     # Sama seperti monolith
```

---

## 2. Tech Stack — 20 Service, 1 Stack

Semua service dalam **satu bahasa, satu framework, satu pola**.

### Stack per Service

| Service | Framework | HTTP Client | Storage | Eksternal |
|---------|-----------|-------------|---------|-----------|
| **Dashboard** | FastAPI + React SPA | httpx | JSON file | Semua service (proxy) |
| **Immunefi** | FastAPI | httpx | JSON file | GitHub API |
| **Source** | FastAPI | httpx | JSON file + git | Etherscan API, Sourcify, GitHub |
| **Scanner Router** | FastAPI | subprocess + httpx | JSON file | 5 scanner tools (internal) |
| **AI** | FastAPI | httpx | JSON cache | OpenAI / Anthropic API |
| **Classifier** | FastAPI | — | JSON file | — |
| **Exploit** | FastAPI | Docker SDK | JSON file | Anvil (Foundry) |
| **Reporter** | FastAPI | Jinja2 | Markdown file | — |
| **Notifier** | FastAPI | httpx | Log file | Discord API, Telegram API, SMTP |
| **Orchestrator** | FastAPI | httpx async | JSON file | Semua service di atas |
| **Webhook** | FastAPI | httpx | Log file | Slack, PagerDuty, etc |
| **Config** | FastAPI | — | JSON file | — |
| **Upkeep** | FastAPI | httpx + subprocess | JSON file | pip, GitHub |
| **Scanner Mythril** | FastAPI | subprocess | JSON file | Mythril (isolated sidecar) |
| **Scanner Slither** | FastAPI | subprocess | JSON file | Slither |
| **Scanner Echidna** | FastAPI | subprocess | JSON file | Echidna binary |
| **Scanner Forge** | FastAPI | subprocess | JSON file | Foundry (forge) |
| **Scanner Halmos** | FastAPI | subprocess | JSON file | Halmos (formal verif) |
| **Agent** | FastAPI | httpx | JSON file | LLM, orchestrator |
| **Submission** | FastAPI | httpx | JSON file | Immunefi, bounty platforms |

### Stack Foundation

```
Bahasa:         Python 3.11+ (19 services) + TypeScript (Dashboard React SPA)
Framework:      FastAPI (19 services) + React 18 (Dashboard)
HTTP Client:    httpx (async, standard)
Run:            uvicorn (tiap service) + Vite (Dashboard)
Container:      python:3.11-slim (base image) + node:20 (Dashboard build)
Orkestrasi:     Docker Compose
Storage:        Docker volumes (JSON + Markdown)

Dashboard FE:   React 18 SPA + TypeScript + Tailwind v4 + Vite
AI Provider:    OpenAI GPT-4 / Anthropic Claude (optional)
Blockchain:     Slither, Mythril, Echidna, Foundry (Anvil)
Compiler:       solc-select (otomatis install versi)
Package:        pip (requirements.txt per service)
```

### Kenapa Python Semua?

| Tools | Bahasa | Alasan |
|-------|--------|--------|
| Slither | **Python** | Native — langsung import? Gak, ini microservice. Tapi subprocess gampang |
| Mythril | **Python** | Sama — `subprocess.run(["mythril", ...])` |
| Echidna | **Haskell** (binary) | Binary — `subprocess.run(["echidna", ...])` |
| Anvil | **Rust** (binary) | Binary — Docker container |
| solc-select | **Python** | Native pip package |
| OpenZeppelin | Solidity | Dependency — `forge install` |

Tidak perlu ganti bahasa. Semua tools bisa dipanggil via subprocess atau HTTP.

### Summary Variabel

| Variabel | Value |
|----------|-------|
| `PYTHON_VERSION` | `3.11-slim` |
| `FASTAPI_PORT` | `8000`-`8018` |
| `DOCKER_COMPOSE` | `3.9` |
| `STORAGE` | Docker volumes + JSON |
| `LOG_FORMAT` | JSON (semua service) |
| `CONFIG_FORMAT` | JSON (semua service) |
| `BASE_IMAGE` | `python:3.11-slim` |
| Slither/Mythril/Echidna | ✅ Native Python packages | ❌ Subprocess call |
| Hermes Agent | ✅ Same ecosystem, reuse skills | ❌ Rewrite needed |
| LLM/AI Libraries | ✅ OpenAI, Anthropic SDK mature | ✅ Also good |
| CLI Apps | ✅ Click/Typer = gold standard | ✅ Also good |
| JSON handling | ✅ Native | ✅ Native |
| Anvil (Docker) | ✅ docker-py | ✅ Dockerode |
| **Winner** | **✅ Langsung kerja** | Perlu bridging |

**Keputusan**: **Python 3.11+** (19 services). Dashboard pakai **TypeScript + React** untuk SPA modern. Hermes sudah Python, tools audit sudah Python — satu bahasa utama = langsung jalan.

---

## 3. Storage: Per-Service Volume

**Setiap service punya data sendiri.** Semua di-mount dari host `~/.vyper/`.

```
~/.vyper/
│
├── config/                           # Config Service
│   └── config.json                   # Global config (shared read-only)
│
├── immunefi/                         # Immunefi Service
│   ├── programs/{slug}.json         # Detail per program (multi-file)
│   ├── history/{slug}.jsonl         # Append-only change log
│   ├── sync_log.jsonl               # Sync operation log
│   ├── indexes/                      # Fast lookup indexes
│   │   ├── by_chain.json
│   │   ├── by_status.json
│   │   ├── by_bounty.json
│   │   └── by_last_updated.json
│   └── _meta.json                   # Schema version, last sync info
│
├── source/                           # Source Service
│   ├── contracts/{chain}/{addr}/     # Source code cache
│   └── repos/{slug}/                # Cloned GitHub repos
│
├── scanner/                          # Scanner Service
│   ├── results/{audit_id}/          # Slither/Mythril/Echidna raw output
│   └── solc/{version}/solc         # Cached solc binaries
│
├── ai/                               # AI Service
│   └── cache/{finding_hash}.json    # LLM response cache
│
├── classifier/                       # Classifier Service
│   ├── findings.json                 # All findings
│   ├── patterns.json                 # Vulnerability patterns
│   └── metrics.json                  # TP/FP/TN/FN metrics
│
├── exploit/                          # Exploit Service
│   └── results/{finding_id}/        # PoC scripts + results
│
├── reporter/                         # Reporter Service
│   └── reports/{audit_id}/          # immunefi.md + full.md
│
├── notifier/                         # Notifier Service
│   └── delivery.log                 # Log pengiriman notifikasi
│
├── orchestrator/                     # Orchestrator Service
│   ├── queue.json                    # Priority queue
│   ├── audit_log.json                # Riwayat audit
│   └── similarity.json               # Contract similarity clusters
│
├── dashboard/                        # Dashboard Service
│   └── sessions/                    # Session data (optional)
│
├── webhook/                          # Webhook Service
│   └── delivery.log                 # Log pengiriman webhook
│
├── config/                           # Config Service
│   └── config.json                   # Global config
│
├── upkeep/                           # Upkeep Service
│   ├── backups/{name}.tar.gz        # Backup archives
│   ├── update/VERSION               # Pattern version
│   └── update/changelog.md          # Changelog
│
└── learning/                         # Shared — learning data
    ├── feedback.json                 # Semua feedback
    ├── false_negatives.json          # FN tracker
    └── false_positives.json          # FP tracker
```

### Aturan Storage Microservice

| Aturan | Penjelasan |
|--------|------------|
| **Setiap service mount volume sendiri** | `docker compose volumes:` mapping |
| **Config Service read-only untuk yang lain** | Service lain baca config via HTTP, bukan langsung file |
| **Learning/ adalah shared volume** | Feedback perlu diakses classifier + orchestrator |
| **Tidak ada service akses volume service lain langsung** | Semua via API — ini microservice |
│
├── audits/                          # Hasil audit (per kontrak)
│   └── ethena-USDe-2026-05-17/
│       ├── audit.json               # Metadata audit
│       │   {
│       │     "id": "aud_abc123",
│       │     "program": "ethena",
│       │     "contract": "0x4c9edd...",
│       │     "chain": "ethereum",
│       │     "status": "completed",
│       │     "started_at": 1717890123,
│       │     "duration_seconds": 845
│       │   }
│       │
│       ├── findings.json            # Semua findings + klasifikasi
│       │   {
│       │     "findings": [
│       │       {
│       │         "id": "F-001",
│       │         "title": "Reentrancy in withdraw()",
│       │         "tool": "slither",
│       │         "severity": "critical",
│       │         "classification": "true_positive",
│       │         "confidence": 0.95,
│       │         "source": "ai_verdict",
│       │         "source_prov": "github",  # 🆕 etherscan|github|sourcify|blockscout|manual
│       │         "exploit_confirmed": true,
│       │         "final": true,
│       │         "ai_reasoning": "...",
│       │         "fix_recommendation": "..."
│       │       }
│       │     ],
│       │     "metrics": {
│       │       "tp": 2, "fp": 1, "tn": 3, "fn": 0,
│       │       "precision": 0.667,
│       │       "recall": 1.0,
│       │       "f1_score": 0.8,
│       │       "overall_score": 7.2
│       │     }
│       │   }
│       │
│       ├── scans/                   # Raw output per tool
│       │   ├── slither.json
│       │   └── mythril.json
│       │
│       ├── exploit/                 # Exploit results
│       │   ├── result.json
│       │   └── poc.sol              # PoC dalam Hardhat format
│       │
│       └── reports/                 # Generated reports
│           ├── immunefi.md           # ✅ TP-ONLY — siap submit
│           └── full.md               # Lengkap + metrics
│
├── metrics.json                     # Agregat semua audit
│   {
│     "total_audits": 47,
│     "total_findings": 312,
│     "tp": 89, "fp": 45, "tn": 156, "fn": 22,
│     "precision": 0.664,
│     "recall": 0.802,
│     "f1_score": 0.727,
│     "top_tools": {
│       "slither": { "tp": 45, "fp": 20, "precision": 0.692 },
│       "mythril": { "tp": 38, "fp": 18, "precision": 0.679 },
│       "echidna": { "tp": 6, "fp": 7, "precision": 0.462 }
│     }
│   }
│
└── learning/                        # Continuous improvement
    ├── false_negatives.json         # ⚠️ PRIORITAS — missed bugs
    │   [
    │     {
    │       "id": "FN-001",
    │       "contract": "0x...",
    │       "bug_type": "oracle_manipulation",
    │       "found_by": "immunefi_rejection",
    │       "root_cause": "Slither tidak detect oracle price validation",
    │       "pattern_added": true,
    │       "resolved_at": 1717890500
    │     }
    │   ]
    │
    └── false_positives.json         # False alarms
```

**Tidak ada CSV.** JSON untuk data terstruktur, Markdown untuk laporan manusiawi.

### Aturan File Naming

```
Jenis        Format        Contoh
───────────────────────────────────────────────
Config       JSON          config.json
Immunefi     JSON          ethena.json
Source       .sol          USDe.sol
Findings     JSON          findings.json
Exploit      JSON/Sol      result.json + poc.sol
Report       Markdown      immunefi.md
Metrics      JSON          metrics.json
Learning     JSON          false_negatives.json
```

---

## 3a. Why JSON, Not SQL

**VYPER adalah 100% JSON file-based.** Tidak menggunakan database engine apapun. Semua data adalah JSON files.

Ini adalah **keputusan arsitektur yang disengaja**, bukan tradeoff.

### Kenapa JSON, Bukan Database

| Faktor | Database Engine | JSON Files |
|--------|----------------|------------|
| **Setup** | Install, config, migrations, pooling | `mkdir -p ~/.vyper/` — selesai |
| **Startup** | 5-30 detik (container spin up) | 0 (file langsung dibaca) |
| **Memory** | Ratusan MB untuk database engine | Beberapa KB (isi file) |
| **Backup** | Tool spesifik | `cp -r ~/.vyper/ backup/` |
| **Restore** | Setup ulang — menit | `cp -r backup/ ~/.vyper/` — detik |
| **Portabilitas** | Bind ke versi tertentu | Bisa di-`git`, di-`rsync`, di-`zip` |
| **Debuggable** | Tool spesifik, perlu query | `vim`, `grep`, `jq`, `cat`, `tail -f` |
| **Rollback** | `ROLLBACK;` — selama session belum close | Git checkout / undo file |
| **Concurrent writers** | ✅ MVCC | ⚠️ Single writer (cukup untuk personal) |
| **Complex queries** | ✅ JOIN, GROUP BY | ⚠️ Filter di Python (cukup untuk 234 program) |

### Kenapa JSON Menang untuk VYPER

```python
# Realita: jumlah data VYPER
234  program           # <<<<<<< Tidak ada yang besar
1,247 kontrak         # <<<<<<< Muat di satu file
~500 findings/bulan   # <<<<<<< Muat di satu folder
~50MB total storage   # <<<<<<< Kurang dari 1 foto HP
```

**Pada skala ini, database engine tidak memberikan keuntungan berarti:**

```
Query time: JSON (in-memory dict) — semua < 10ms:
──────────────────────────────────────────────────
- List all programs:           0.3ms
- Filter by chain:             0.5ms
- Sort by bounty:              0.4ms
- Search by name:              0.6ms
- Full-text search:            1.2ms

Semua masih < 10ms. Perbedaan tidak relevan untuk UX.
```

### Keunggulan JSON untuk VYPER

| Kemampuan | Keterangan |
|-----------|------------|
| **Bisa di-commit ke git** | `git add . && git commit -m "update"` |
| **Bisa di-diff** | `git diff programs.json` |
| **Bisa di-edit pake vim** | Ya — langsung edit JSON |
| **Bisa di-grep** | `grep -r "reentrancy" ~/.vyper/` |
| **Bisa di-copy via rsync** | `rsync -av ~/.vyper/ laptop2:~/.vyper/` |
| **Zero dependencies** | ✅ Bawaan Python (json module) |
| **Berfungsi offline** | ✅ Full — tanpa koneksi apapun |
| **Tidak bisa corrupt** | ✅ Atomic write + backup otomatis |

### Enhanced JSON Storage — Fitur yang Melengkapi JSON

Meskipun JSON dipilih, kita tetap butuh beberapa fitur yang biasanya identik dengan database engine. Solusinya **bukan mengganti format, tapi menambahkan tools**:

| Fitur | Padanan di VYPER |
|-------|-----------------|
| **ACID** | Atomic write (`.tmp` → rename) + append-only logs |
| **Indexes** | File `indexes/by_chain.json`, `by_status.json`, dll |
| **History / audit trail** | Append-only `.jsonl` — bisa di-`tail`, di-`grep` |
| **Schema enforcement** | Pydantic `BaseModel` — validation di load/save |
| **Migrations** | `_meta.json` → `schema_version` → auto-migrate di startup |
| **Consistency** | Rebuild indexes setelah setiap write batch |
| **Concurrency** | asyncio lock + single-process (cukup untuk personal) |

### Ringkasan

> **JSON files lebih sederhana, lebih portable, dan zero-ops untuk personal use case VYPER.**

---

## 4. Arsitektur Microservice — 20 Services

Setiap service adalah **FastAPI app sendiri** dalam **Docker container sendiri**.

### Service Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   USER                                                              │
│    │                                                                │
│    ▼                                                                │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  DASHBOARD (port 8000)      API Gateway + React SPA         │   │
│  │  React 18 SPA + TypeScript + Tailwind v4                    │   │
│  └────────┬────────────────────────────────────────────────────┘   │
│           │ HTTP/REST                                              │
│           ▼                                                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ORCHESTRATOR (port 8009)    Pipeline Coordinator           │   │
│  │  - Audit pipeline                                             │   │
│  │  - Priority queue                                             │   │
│  │  - Daemon mode                                                │   │
│  │  - Contract similarity                                        │   │
│  │  - Retroactive re-run                                         │   │
│  └──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──────────────────────┘   │
│     │  │  │  │  │  │  │  │  │  │  │  │  │                        │
│     ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼                        │
│  ┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐│
│  │ IM ││SRC ││SRT ││ AI ││CLS ││EXP ││RPT ││NTF ││WHK ││CFG ││UPK ││
│  │    ││    ││    ││    ││    ││    ││    ││    ││    ││    ││    ││
│  │8001││8002││8003││8004││8005││8006││8007││8008││8010││8011││8012││
│  └────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘└────┘│
│                                                                     │
│  ┌── Scanner Tools (routed via SRT:8003) ──────────────────────┐   │
│  │                                                              │   │
│  │  ┌────┐┌────┐┌────┐┌────┐┌────┐                            │   │
│  │  │MYT ││SLT ││ECH ││FRG ││HAL │                            │   │
│  │  │8013││8014││8015││8016││8017│                            │   │
│  │  └────┘└────┘└────┘└────┘└────┘                            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌── Additional Services ──────────────────────────────────────┐   │
│  │  ┌────┐┌────┐                                               │   │
│  │  │AGT ││SUB │                                               │   │
│  │  │8018││    │                                               │   │
│  │  └────┘└────┘                                               │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Semua komunikasi via HTTP/REST.                                   │
│  Setiap service punya volume sendiri di ~/.vyper/{service}/         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Service Detail

| # | Service | Port | Tanggung Jawab | Bahasa |
|---|---------|------|---------------|--------|
| 1 | **Dashboard** | 8000 | React SPA + API Gateway + SSE | TypeScript |
| 2 | **Immunefi** | 8001 | Sync program, detect repos | Python |
| 3 | **Source** | 8002 | Multi-source fetch (GitHub/Sourcify/Etherscan/Blockscout) | Python |
| 4 | **Scanner Router** | 8003 | Route ke scanner tools + solc mgmt + deps | Python |
| 5 | **AI** | 8004 | LLM analysis + verdict + severity | Python |
| 6 | **Classifier** | 8005 | TP/FP/TN/FN + metrics + similarity | Python |
| 7 | **Exploit** | 8006 | Anvil Docker engine + PoC generation | Python |
| 8 | **Reporter** | 8007 | Generate immunefi.md + full.md | Python |
| 9 | **Notifier** | 8008 | Discord/Telegram/Email/Desktop | Python |
| 10 | **Orchestrator** | 8009 | Pipeline + queue + daemon + re-run | Python |
| 11 | **Webhook** | 8010 | Webhook delivery + signature | Python |
| 12 | **Config** | 8011 | Config management + API keys | Python |
| 13 | **Upkeep** | 8012 | Self-update + backup + restore + metrics | Python |
| 14 | **Scanner Mythril** | 8013 | Symbolic execution (sidecar, isolated) | Python |
| 15 | **Scanner Slither** | 8014 | Static analysis (split from main scanner) | Python |
| 16 | **Scanner Echidna** | 8015 | Fuzzing & property testing | Python |
| 17 | **Scanner Forge** | 8016 | Build verification (Foundry) | Python |
| 18 | **Scanner Halmos** | 8017 | Symbolic execution & formal verification | Python |
| 19 | **Agent** | 8018 | Autonomous agent orchestration + memory | Python |
| 20 | **Submission** | 8019 | Track bounties across platforms | Python |

### Repository Structure

```
vyper/
│
├── docker-compose.yml              # Orchestrate semua service (20 services)
├── Dockerfile.base                 # Base Python image
├── .env.example                    # API keys template
├── README.md
├── VYPER.md                        # Dokumentasi arsitektur
├── VYPER_ROADMAP.md                # Roadmap pengembangan
├── ARCHITECTURE.md                 # Detail arsitektur
├── IMPLEMENTATION_PLAN.md          # Implementation plan
│
├── vyper_lib/                      # Shared library (models + utilities)
│   ├── __init__.py
│   └── models.py                   # Pydantic models shared across services
│
├── services/                       # 20 microservices
│   ├── 01-immunefi/
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── scraper.py
│   │       ├── sync.py
│   │       ├── repo_detector.py
│   │       └── models.py
│   │
│   ├── 02-source/
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── detector.py
│   │       ├── models.py
│   │       └── providers/
│   │           ├── etherscan.py
│   │           ├── github.py
│   │           ├── sourcify.py
│   │           ├── blockscout.py
│   │           └── manual.py
│   │
│   ├── 03-scanner-router/          # Router → tool services
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── router.py
│   │       ├── solc_manager.py
│   │       ├── deps.py
│   │       └── slither_config.py
│   │
│   ├── 04a-scanner-slither/        # Static analysis
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       └── analyzer.py
│   │
│   ├── 04b-scanner-echidna/        # Fuzzing & property testing
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       └── fuzzer.py
│   │
│   ├── 04c-scanner-forge/          # Build verification (Foundry)
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       └── builder.py
│   │
│   ├── 04d-scanner-halmos/         # Formal verification
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       └── prover.py
│   │
│   ├── 05-scanner-mythril/         # Symbolic execution (sidecar)
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       └── analyzer.py
│   │
│   ├── 06-ai/
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── llm.py
│   │       ├── analyzer.py
│   │       └── fixer.py
│   │
│   ├── 07-classifier/
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── classify.py
│   │       ├── metrics.py
│   │       └── improver.py
│   │
│   ├── 08-exploit/
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── engine.py
│   │       ├── anvil.py
│   │       ├── executor.py
│   │       ├── impersonator.py
│   │       └── poc_generator.py
│   │
│   ├── 09-reporter/
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── immunefi.py
│   │       ├── full.py
│   │       └── templates/
│   │
│   ├── 10-notifier/
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── discord.py
│   │       ├── telegram.py
│   │       ├── desktop.py
│   │       └── email.py
│   │
│   ├── 11-orchestrator/
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── pipeline.py
│   │       ├── batch.py
│   │       ├── daemon.py
│   │       ├── priority.py
│   │       ├── similarity.py
│   │       ├── git_analysis.py
│   │       ├── test_intel.py
│   │       └── resource_governor.py
│   │
│   ├── 12-webhook/
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       └── dispatcher.py
│   │
│   ├── 13-config/
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       └── manager.py
│   │
│   ├── 14-upkeep/
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── update.py
│   │       ├── backup.py
│   │       └── metrics.py
│   │
│   ├── 15-agent/                   # Autonomous agent
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── memory.py           # Vector + Episodic + Graph memory
│   │       ├── daemon.py           # Autonomous hunting daemon
│   │       └── learner.py          # Feedback loop learning
│   │
│   ├── 16-dashboard/               # React SPA
│   │   ├── Dockerfile              # Multi-stage: Node 20 → Python 3.11
│   │   ├── app.py                  # FastAPI + static mount
│   │   ├── requirements.txt
│   │   ├── proxy.py                # API Gateway proxy to all services
│   │   └── frontend/               # React SPA source
│   │       ├── package.json
│   │       ├── vite.config.ts
│   │       ├── tsconfig.json
│   │       ├── tailwind.config.ts
│   │       ├── index.html
│   │       └── src/
│   │           ├── App.tsx
│   │           ├── main.tsx
│   │           ├── api.ts          # API client
│   │           ├── Layout.tsx
│   │           └── pages/          # 10 pages
│   │               ├── ServiceHealth.tsx
│   │               ├── Pipeline.tsx
│   │               ├── ScannerDetail.tsx
│   │               ├── ExploitViewer.tsx
│   │               ├── ConfigEditor.tsx
│   │               ├── NotifierStatus.tsx
│   │               ├── WebhookLogs.tsx
│   │               ├── SourceViewer.tsx
│   │               ├── ReportCenter.tsx
│   │               └── Scheduler.tsx
│   │
│   └── 17-submission/              # Bounty tracker
│       ├── Dockerfile
│       ├── app.py
│       ├── requirements.txt
│       └── src/
│           └── tracker.py
│
├── daily_agenda/                   # Agenda harian pengembangan
│   ├── README.md
│   ├── 01_immunefi_refactor_(high).md
│   ├── 02_source_service_(high).md
│   ├── 03_vyper_cli_tool_(critical).md
│   ├── 04_exploit_service_(critical).md
│   ├── 05_scanner_echidna_forge_(critical).md
│   ├── 06_notifier_service_(high).md
│   ├── 07_reporter_refactor_(high).md
│   ├── 08_orchestrator_refactor_(high).md
│   ├── 09_dashboard_react_spa_(critical).md
│   ├── 10_vyper_lib_refactor_(high).md
│   ├── 11_halmos_formal_verification_(critical).md
│   ├── 12_autonomous_agent_intelligence_(critical).md
│   ├── 13_github_actions_cicd_pipeline_(high).md
│   ├── 14_custom_slither_detectors_engine_(high).md
│   └── 15_production_hardening_performance_(high).md
│
├── tests/                          # Integration tests
│   ├── test_pipeline.py
│   └── test_services.py
│
├── scripts/
│   ├── install.sh
│   ├── install-cli.ps1
│   └── dev.sh                      # docker compose up --build
│
└── docs/                           # Dokumentasi tambahan
    ├── VYPER.md
    ├── ARCHITECTURE.md
    ├── IMPLEMENTATION_PLAN.md
    ├── DASHBOARD.md
    ├── SCANNER_SPLIT_PLAN.md
    └── VYPER_ROADMAP.md
```

### Docker Compose

```yaml
# docker-compose.yml — 20 services

services:
  # ─── Gateway & Orchestrator ───────────────────────────────
  dashboard:
    build: services/16-dashboard
    ports: ["8000:8000"]
    volumes: [vyper_data:/data/dashboard, vyper_learning:/data/learning]
    depends_on: [orchestrator, config]

  orchestrator:
    build: services/11-orchestrator
    ports: ["8009:8009"]
    volumes: [vyper_orchestrator:/data/orchestrator, vyper_learning:/data/learning]
    depends_on:
      - immunefi
      - source
      - scanner-router
      - ai
      - classifier
      - exploit
      - reporter
      - notifier
      - config

  # ─── Data Services ───────────────────────────────────────
  immunefi:
    build: services/01-immunefi
    ports: ["8001:8001"]
    volumes: [vyper_immunefi:/data/immunefi]

  source:
    build: services/02-source
    ports: ["8002:8002"]
    volumes: [vyper_source:/data/source]

  # ─── Scanner Router → Tool Services ──────────────────────
  scanner-router:
    build: services/03-scanner-router
    ports: ["8003:8003"]
    volumes: [vyper_scanner:/data/scanner]
    depends_on:
      - scanner-slither
      - scanner-echidna
      - scanner-forge
      - scanner-halmos
      - scanner-mythril

  scanner-slither:
    build: services/04a-scanner-slither
    ports: ["8014:8014"]
    volumes: [vyper_scanner:/data/scanner]

  scanner-echidna:
    build: services/04b-scanner-echidna
    ports: ["8015:8015"]
    volumes: [vyper_scanner:/data/scanner]

  scanner-forge:
    build: services/04c-scanner-forge
    ports: ["8016:8016"]
    volumes: [vyper_scanner:/data/scanner]

  scanner-halmos:
    build: services/04d-scanner-halmos
    ports: ["8017:8017"]
    volumes: [vyper_scanner:/data/scanner]

  scanner-mythril:
    build: services/05-scanner-mythril
    ports: ["8013:8013"]
    volumes: [vyper_scanner:/data/scanner]

  # ─── Analysis Services ───────────────────────────────────
  ai:
    build: services/06-ai
    ports: ["8004:8004"]
    volumes: [vyper_ai:/data/ai]
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}

  classifier:
    build: services/07-classifier
    ports: ["8005:8005"]
    volumes: [vyper_classifier:/data/classifier, vyper_learning:/data/learning]

  # ─── Exploit & Reporting ─────────────────────────────────
  exploit:
    build: services/08-exploit
    ports: ["8006:8006"]
    volumes:
      - vyper_exploit:/data/exploit
      - /var/run/docker.sock:/var/run/docker.sock:rw  # Docker socket for Anvil

  reporter:
    build: services/09-reporter
    ports: ["8007:8007"]
    volumes: [vyper_reporter:/data/reporter]

  notifier:
    build: services/10-notifier
    ports: ["8008:8008"]
    volumes: [vyper_notifier:/data/notifier]

  # ─── Infrastructure ──────────────────────────────────────
  webhook:
    build: services/12-webhook
    ports: ["8010:8010"]
    volumes: [vyper_webhook:/data/webhook]

  config:
    build: services/13-config
    ports: ["8011:8011"]
    volumes: [vyper_config:/data/config]

  upkeep:
    build: services/14-upkeep
    ports: ["8012:8012"]
    volumes: [vyper_upkeep:/data/upkeep]

  # ─── Advanced Services ───────────────────────────────────
  agent:
    build: services/15-agent
    ports: ["8018:8018"]
    volumes: [vyper_agent:/data/agent, vyper_learning:/data/learning]
    depends_on: [orchestrator]

  submission:
    build: services/17-submission
    ports: ["8019:8019"]
    volumes: [vyper_submission:/data/submission]

volumes:
  vyper_immunefi:
  vyper_source:
  vyper_scanner:
  vyper_ai:
  vyper_classifier:
  vyper_exploit:
  vyper_reporter:
  vyper_notifier:
  vyper_orchestrator:
  vyper_webhook:
  vyper_config:
  vyper_upkeep:
  vyper_agent:
  vyper_submission:
  vyper_data:
  vyper_learning:
```

### Inter-Service Communication Pattern

```
┌───────────────────────────────────────────────────────────────────┐
│                 ORCHESTRATOR                                       │
│                                                                   │
│  POST /audit/start {address, chain}                               │
│    │                                                               │
│    ├─→ GET /immunefi/program/{address}     ← Immunefi:8001       │
│    ├─→ GET /source/fetch/{address}         ← Source:8002         │
│    ├─→ POST /scanner-router/scan {source}  ← Scanner Router:8003 │
│    │      └─→ routes to → [Slither:8014] [Echidna:8015]          │
│    │                    → [Forge:8016] [Halmos:8017] [Mythril:8013]│
│    ├─→ POST /ai/analyze {findings}         ← AI:8004             │
│    ├─→ POST /classifier/classify {data}    ← Classifier:8005     │
│    ├─→ POST /exploit/run {finding}         ← Exploit:8006        │
│    ├─→ POST /agent/analyze {findings}      ← Agent:8018          │
│    ├─→ POST /reporter/generate {data}      ← Reporter:8007       │
│    └─→ POST /notifier/send {notification}  ← Notifier:8008       │
│                                                                   │
│  Semua synchronous HTTP call dengan timeout 30s-300s.             │
│  Kalau service down → error boundary → partial result.            │
└───────────────────────────────────────────────────────────────────┘
```

### Kenapa Bukan Monolith?

| Aspek | Monolith | Microservice (sekarang) |
|-------|----------|------------------------|
| **Isolasi** | Slither crash → semua berhenti | Scanner crash → Orchestrator coba lagi |
| **Scale** | Satu proses | `docker compose up --scale scanner=3` |
| **Bahasa** | Python wajib | Scanner Python → AI Python → Exploit TypeScript nanti |
| **Update** | Deploy ulang semua | Update Scanner v2 tanpa sentuh AI |
| **Debug** | Log campur aduk | `docker logs vyper-scanner-1` |
| **Memory** | Semua dalam 1 proses | Masing-masing container 256MB-1GB |
| **Dependency** | Satu requirements.txt (konflik) | Masing-masing service punya sendiri |

### Kenapa Tetap Lokal?

```
✅ docker compose up   # Satu baris, semua jalan
✅ Data di volume Docker   # Tetap backup-able
✅ Tidak perlu Kubernetes  # Laptop cukup
✅ Bisa jalan tanpa internet  # AI aja yang perlu API
✅ Sama portabelnya dengan monolith
✅ Tapi dapet benefit microservice
```

---

## 5. Orchestrator & Workflow — Jantung Microservice

**Orchestrator** adalah satu-satunya service yang tahu urutan pipeline. Service lain tidak tahu — mereka hanya terima request, proses, return hasil.

### Workflow State Machine

Setiap audit memiliki state yang jelas. Orchestrator yang pegang state.

```
                          ┌─────────────┐
                          │  PENDING    │
                          └──────┬──────┘
                                 │ start
                                 ▼
                     ┌─────────────────────┐
                     │  FETCHING_PROGRAM   │ ← Immunefi Service
                     └──────────┬──────────┘
                                │ success
                                ▼
                     ┌─────────────────────┐
                     │  FETCHING_SOURCE    │ ← Source Service
                     └──────────┬──────────┘
                           ╱          ╲
                     success          fail
                        ▼              ▼
              ┌──────────────┐  ┌──────────────┐
               │ SCANNING     │  │ SOURCE_FAILED│ ← Abort, retry next cycle
               └──────┬───────┘  └──────────────┘
                      │ success
                      ▼
               ┌──────────────────┐
               │ HALMOS_ANALYSIS  │ ← Halmos formal verification
               └──────┬───────────┘
                      │ success
                      ▼
               ┌──────────────┐
               │ AI_ANALYSIS  │ ← AI Service
               └──────┬───────┘
                      │ success
                      ▼
               ┌──────────────┐
               │ CLASSIFYING  │ ← Classifier Service
               └──────┬───────┘
                      │ success
                      ▼
               ┌──────────────┐
               │ EXPLOITING   │ ← Exploit Service (HANYA jika TP critical/high)
               └──────┬───────┘
                      │ success
                      ▼
               ┌──────────────┐
               │ REPORTING    │ ← Reporter Service
               └──────┬───────┘
                      │ success
                      ▼
               ┌──────────────┐
               │ NOTIFYING    │ ← Notifier Service (HANYA jika critical/high)
               └──────┬───────┘
                      │ success
                      ▼
               ┌──────────────┐
               │  COMPLETED   │ ✓
               └──────────────┘

  State transitions dicatat di orchestrator/audit_log.json
  Setiap state punya: id, status, started_at, finished_at, duration, error
```

### State Definitions

```python
# orchestrator/src/workflow.py

from enum import Enum

class AuditState(str, Enum):
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

    # Failure states — perlu user action atau retry
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

### Orchestrator API

Orchestrator expose endpoint untuk dashboard dan CLI:

```python
# orchestrator/app.py (FastAPI)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Vyper Orchestrator")

# ============ Endpoints ============

@app.post("/audit/start")
async def start_audit(req: StartAuditRequest):
    """
    Mulai audit untuk satu kontrak.
    Workflow:
    1. Cek program di Immunefi Service
    2. Fetch source dari Source Service
    3. Scan via Scanner Service
    4. Analisis via AI Service
    5. Klasifikasi via Classifier Service
    6. Exploit (jika critical/high TP)
    7. Generate report via Reporter Service
    8. Notify via Notifier Service (jika critical/high)
    """
    audit_id = generate_id()
    workflow = WorkflowEngine(audit_id)
    
    # Async — langsung return audit_id
    asyncio.create_task(workflow.run(req.address, req.chain, req.program))
    
    return {"audit_id": audit_id, "status": "started"}

@app.get("/audit/{audit_id}/status")
async def get_status(audit_id: str):
    """Lihat state + progress audit"""
    state = load_audit_state(audit_id)
    if not state:
        raise HTTPException(404)
    return state

@app.post("/audit/{audit_id}/retry")
async def retry_audit(audit_id: str):
    """Retry dari state terakhir yang gagal"""
    workflow = WorkflowEngine(audit_id)
    asyncio.create_task(workflow.retry())
    return {"status": "retrying"}

@app.post("/audit/{audit_id}/abort")
async def abort_audit(audit_id: str):
    """Batalkan audit yang sedang berjalan"""
    abort_workflow(audit_id)
    return {"status": "aborted"}

@app.get("/queue")
async def get_queue():
    """Lihat priority queue"""
    return load_queue()

@app.post("/queue/reorder")
async def reorder_queue(items: list[QueueItem]):
    """Manual reorder queue"""
    save_queue(items)
    return {"status": "ok"}
```

### Workflow Engine — The Brain

```python
# orchestrator/src/workflow.py

import asyncio
import httpx
from datetime import datetime

class WorkflowEngine:
    """
    Menjalankan pipeline audit sebagai async workflow.
    Setiap step adalah HTTP call ke service lain.
    """

    SERVICES = {
        "immunefi":      "http://01-immunefi:8001",
        "source":        "http://02-source:8002",
        "scanner":       "http://03-scanner-router:8003",
        "scanner-slither":  "http://04a-scanner-slither:8014",
        "scanner-echidna":  "http://04b-scanner-echidna:8015",
        "scanner-forge":    "http://04c-scanner-forge:8016",
        "scanner-halmos":   "http://04d-scanner-halmos:8017",
        "scanner-mythril":  "http://05-scanner-mythril:8013",
        "ai":            "http://06-ai:8004",
        "classifier":    "http://07-classifier:8005",
        "exploit":       "http://08-exploit:8006",
        "reporter":      "http://09-reporter:8007",
        "notifier":      "http://10-notifier:8008",
        "agent":         "http://15-agent:8018",
    }

    def __init__(self, audit_id: str):
        self.audit_id = audit_id
        self.state = AuditState.PENDING
        self.context = {}  # Data yang di-pass antar step
        self.client = httpx.AsyncClient(timeout=30.0)

    async def run(self, address: str, chain: str, program: str = None):
        """Execute full workflow"""
        self.audit = {
            "id": self.audit_id,
            "address": address,
            "chain": chain,
            "program": program,
            "started_at": datetime.utcnow().isoformat(),
            "state": AuditState.PENDING,
        }
        self._save_state()

        try:
            # Step 1: Fetch Immunefi program
            await self._step(
                AuditState.FETCHING_PROGRAM,
                "immunefi",
                f"/program/{address}",
                key="program"
            )

            # Step 2: Fetch source code
            await self._step(
                AuditState.FETCHING_SOURCE,
                "source",
                f"/fetch/{address}",
                params={"chain": chain},
                key="source"
            )

            # Step 3: Scan (INI PALING LAMA — bisa 5-15 menit)
            await self._step(
                AuditState.SCANNING,
                "scanner",
                "/scan",
                method="POST",
                json={"source_path": self.context["source"]["path"],
                      "chain": chain},
                key="scan_results",
                timeout=900  # 15 menit
            )

            # Step 3b: Halmos formal verification (parallel after scan)
            await self._step(
                AuditState.HALMOS_ANALYSIS,
                "scanner-halmos",
                "/prove",
                method="POST",
                json={"source_path": self.context["source"]["path"],
                      "chain": chain},
                key="halmos_results",
                timeout=600  # 10 menit
            )

            # Step 4: AI analysis
            await self._step(
                AuditState.AI_ANALYSIS,
                "ai",
                "/analyze",
                method="POST",
                json={"findings": self.context["scan_results"]["findings"],
                      "source": self.context["source"]},
                key="ai_verdicts",
            )

            # Step 5: Classify
            await self._step(
                AuditState.CLASSIFYING,
                "classifier",
                "/classify",
                method="POST",
                json={"findings": self.context["scan_results"]["findings"],
                      "verdicts": self.context["ai_verdicts"]},
                key="classified",
            )

            # Step 6: Exploit (conditional)
            tp_critical = [
                f for f in self.context["classified"]["tp"]
                if f["severity"] in ("critical", "high")
            ]
            if tp_critical:
                await self._step(
                    AuditState.EXPLOITING,
                    "exploit",
                    "/exploit",
                    method="POST",
                    json={"findings": tp_critical,
                          "source": self.context["source"]},
                    key="exploit_results",
                    timeout=600  # 10 menit
                )

            # Step 7: Generate reports
            await self._step(
                AuditState.REPORTING,
                "reporter",
                "/generate",
                method="POST",
                json=self.context["classified"],
                key="reports",
            )

            # Step 8: Notify (conditional)
            if tp_critical:
                await self._step(
                    AuditState.NOTIFYING,
                    "notifier",
                    "/send",
                    method="POST",
                    json={
                        "type": "audit_complete",
                        "findings": tp_critical,
                        "audit_id": self.audit_id,
                    }
                )

            # Selesai
            self.audit["state"] = AuditState.COMPLETED
            self.audit["completed_at"] = datetime.utcnow().isoformat()
            self._save_state()

            # Update metrics
            await self._call("upkeep", "/metrics/update", method="POST",
                           json={"audit_id": self.audit_id})

        except Exception as e:
            self.audit["state"] = self._determine_failure_state(e)
            self.audit["error"] = str(e)
            self._save_state()
            raise

    async def _step(self, state: AuditState, service: str, path: str,
                    method: str = "GET", key: str = None,
                    params: dict = None, json: dict = None,
                    timeout: int = 30):
        """Execute one workflow step with state tracking"""
        self.audit["state"] = state
        self.audit["current_step"] = service + path
        self._save_state()

        url = f"{self.SERVICES[service]}{path}"
        result = await self._call(service, path, method, params, json, timeout)

        if key:
            self.context[key] = result

        logger.info(f"[{self.audit_id}] {state.value} ✅ ({result.get('status', 'ok')})")

    async def _call(self, service: str, path: str, method: str = "GET",
                    params: dict = None, json: dict = None,
                    timeout: int = 30) -> dict:
        """HTTP call ke service lain dengan retry logic"""
        url = f"{self.SERVICES[service]}{path}"

        for attempt in range(3):
            try:
                if method == "GET":
                    resp = await self.client.get(url, params=params, timeout=timeout)
                else:
                    resp = await self.client.post(url, params=params, json=json, timeout=timeout)

                if resp.status_code == 503:
                    # Service sibuk — retry with backoff
                    await asyncio.sleep(2 ** attempt)
                    continue

                resp.raise_for_status()
                return resp.json()

            except httpx.TimeoutException:
                logger.warning(f"Timeout {url} (attempt {attempt+1})")
                await asyncio.sleep(2 ** attempt)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 422:
                    raise  # Validation error — no retry
                logger.warning(f"HTTP {e.response.status_code} {url} (attempt {attempt+1})")
                await asyncio.sleep(2 ** attempt)

        raise WorkflowStepFailed(f"Step {service}{path} failed after 3 retries")

    def _save_state(self):
        """Persist state ke file"""
        path = Path(f"/data/orchestrator/audits/{self.audit_id}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.audit, indent=2, default=str))

    def _determine_failure_state(self, error: Exception) -> AuditState:
        """Map error ke failure state"""
        error_str = str(error).lower()
        if "source" in error_str: return AuditState.SOURCE_FAILED
        if "scan" in error_str: return AuditState.SCAN_FAILED
        if "ai" in error_str: return AuditState.AI_FAILED
        if "classify" in error_str: return AuditState.CLASSIFY_FAILED
        if "exploit" in error_str: return AuditState.EXPLOIT_FAILED
        if "report" in error_str: return AuditState.REPORT_FAILED
        if "timeout" in error_str: return AuditState.TIMEOUT
        return AuditState.ABORTED
```

### API Contracts — Antar Service

Setiap service harus punya API contract yang jelas. Orchestrator tidak tahu implementasi — hanya tahu API.

```python
# contracts.py — Shared contracts (bisa di file terpisah atau di docs)

# ============ Immunefi Service ============
# GET /program/{address}
#   Response: { program_id, name, max_bounty, chain, repos[], assets[] }

# ============ Source Service ============
# GET /fetch/{address}?chain=ethereum
#   Response: {
#     provider: "github"|"sourcify"|"etherscan"|"blockscout",
#     path: "/data/source/contracts/ethereum/0x.../",
#     files: ["USDe.sol", "STETH.sol"],
#     metadata: { has_tests, has_foundry, file_count, is_full_repo }
#   }

# ============ Scanner Service ============
# POST /scan
#   Request: { source_path, chain, tools: ["slither", "mythril"] }
#   Response: {
#     findings: [
#       { id, tool, title, severity, description,
#         swc_id, file, line, code_context }
#     ],
#     tool_errors: [],
#     duration_seconds: 245
#   }

# ============ AI Service ============
# POST /analyze
#   Request: { findings, source }
#   Response: {
#     verdicts: [
#       { finding_id, is_vulnerability: bool, confidence: 0.95,
#         reassessed_severity: "critical",
#         reasoning: "...", fix_recommendation: "..." }
#     ]
#   }

# ============ Classifier Service ============
# POST /classify
#   Request: { findings, verdicts }
#   Response: {
#     tp: [{ finding_id, confidence, exploit_confirmed, ... }],
#     fp: [{ finding_id, reason, ... }],
#     tn: [{ finding_id, ... }],
#     fn: [{ finding_id, ... }],
#     metrics: { precision, recall, f1_score }
#   }

# ============ Exploit Service ============
# POST /exploit
#   Request: { findings, source }
#   Response: {
#     results: [
#       { finding_id, success: bool, poc_script: "contract.sol",
#         tx_hash, gas_used, value_at_risk, account_impersonated }
#     ]
#   }

# ============ Reporter Service ============
# POST /generate
#   Request: { tp, fp, tn, fn, metrics, audit_id }
#   Response: {
#     immunefi_report: "/data/reporter/reports/{audit_id}/immunefi.md",
#     full_report: "/data/reporter/reports/{audit_id}/full.md"
#   }

# ============ Notifier Service ============
# POST /send
#   Request: { type, findings, audit_id }
#   Response: { delivered: ["discord", "telegram", "desktop"] }

# ============ Webhook Service ============
# POST /dispatch
#   Request: { event: "finding.critical", payload: {...} }
#   Response: { delivered: 2, failed: 0 }
```

### Workflow Parallelism

Beberapa step bisa jalan parallel:

```
┌──────────────────┐
│ FETCHING_PROGRAM │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ FETCHING_SOURCE  │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐     ┌───────────────┐
│ SCANNING         │──┬──│ Git Analysis  │ ← Parallel (Orchestrator local)
│ Slither + Mythril│  │  └───────────────┘
└──────┬───────────┘  │  ┌───────────────┐
       │              └──│ Test Intel    │ ← Parallel
       ▼                 └───────────────┘
┌──────────────────┐
│ AI_ANALYSIS      │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ CLASSIFYING      │ ← Pakai hasil Git + Test intel
└──────┬───────────┘
```

### Failure Handling — Saga Pattern

```python
# Setiap step punya compensating action untuk rollback

COMPENSATIONS = {
    AuditState.FETCHING_SOURCE: {
        "service": "source",
        "action": "/cleanup/{source_path}"
    },
    AuditState.SCANNING: {
        "service": "scanner",
        "action": "/cleanup/{scan_id}"
    },
    AuditState.EXPLOITING: {
        "service": "exploit",
        "action": "/cleanup/{exploit_id}"
    },
}

async def compensate(self, failed_state: AuditState):
    """Rollback — bersihkan resource dari step yang sudah jalan"""
    for step in self.executed_steps[::-1]:  # Reverse order
        if step in COMPENSATIONS:
            comp = COMPENSATIONS[step]
            try:
                await self._call(comp["service"], comp["action"],
                               method="DELETE")
            except Exception as e:
                logger.warning(f"Compensation failed for {step}: {e}")
```

### Dashboard Integration

Dashboard bisa subscribe ke state changes:

```python
# Dashboard SSE endpoint
@app.get("/api/events")
async def event_stream(audit_id: str = None):
    async def generate():
        while True:
            if audit_id:
                state = load_audit_state(audit_id)
                yield f"data: {json.dumps(state)}\n\n"
            else:
                queue = load_queue()
                yield f"data: {json.dumps(queue)}\n\n"
            await asyncio.sleep(2)
    return StreamingResponse(generate(), media_type="text/event-stream")
```

@click.group()
def cli():
    """Vyper — Smart Contract Bug Hunter"""
    pass

@cli.command()
def sync():
    """Sync all Immunefi programs"""
    scraper = ImmunefiScraper()
    result = scraper.sync_all()
    click.echo(f"Synced {result.total} programs ({result.new} new)")

@cli.command()
@click.argument("address")
@click.option("--chain", default="ethereum")
def audit(address: str, chain: str):
    """Full audit pipeline for a contract"""
    pipeline = AuditPipeline()
    result = pipeline.run(address, chain)
    
    click.echo(f"\n{'='*50}")
    click.echo(f"Audit Complete: {address}")
    click.echo(f"{'='*50}")
    click.echo(f"  TP: {result.tp_count}  FP: {result.fp_count}")
    click.echo(f"  TN: {result.tn_count}  FN: {result.fn_count}")
    click.echo(f"  Score: {result.score}/10")
    click.echo(f"  Report: ~/.vyper/audits/{result.id}/reports/")
    click.echo(f"{'='*50}")

@cli.command()
@click.argument("audit_id")
def report(audit_id: str):
    """Open Immunefi report for submission"""
    reporter = ImmunefiReporter()
    path = reporter.open_report(audit_id)
    click.echo(f"Report ready: {path}")

@cli.command()
def metrics():
    """Show platform learning metrics"""
    tracker = MetricsTracker()
    tracker.display()

@cli.command()
def learn():
    """Show false negatives (missed bugs)"""
    fn = FNTracker()
    fn.show_pending()

if __name__ == "__main__":
    cli()
```

---

## 6. Yang Berubah dari Arsitektur Sebelumnya

| Komponen | Sebelumnya (SaaS) | Sekarang (Local-First) |
|----------|-------------------|------------------------|
| **Bahasa** | TypeScript + Python + Go | **Python saja** |
| **Database** | Database per service | **JSON files (zero DB)** |
| **Message Queue** | NATS/RabbitMQ | **Function calls** |
| **Services** | 14 microservices | **1 Python package** |
| **Auth** | JWT, RBAC, API keys | **Tidak perlu** |
| **API Gateway** | Kong/Envoy | **CLI langsung** |
| **Storage** | MinIO/S3 | **~/.vyper/ direktori** |
| **Deploy** | Kubernetes / Docker Compose | **pip install vyper** |
| **Proto** | gRPC Protobuf | **Python dataclasses** |
| **Observability** | Grafana + Tempo + Loki | **File logging** |
| **UI** | React 181 komponen | **CLI + Markdown reports** |
| **Container** | 14+ containers | **Hanya Anvil (Docker)** |
| **Biaya** | $50-100/bulan cloud | **Gratis (localhost)** |

### Yang TETAP Sama (hanya formatnya berubah)

| Fitur | Dulu | Sekarang |
|-------|------|----------|
| Immunefi 234+ programs | DB tables | JSON files |
| TP/FP/TN/FN classification | DB table | JSON field |
| AI Analysis | Python service | Python module |
| Exploit Engine (Anvil) | Isolated service | Isolated via Docker |
| PoC generation | Service output | File in audit dir |
| Report Immunefi | Service output | MD file |
| Learning from FN | DB table | JSON log |
| 20 skills | Service | MD files in skills/ |

---

## 7. Instalasi & Penggunaan

### One-Command Install

```bash
# Prerequisites
pip install vyper          # Install tool
docker pull ghcr.io/foundry-rs/foundry  # For Anvil exploit engine

# Usage
vyper sync                 # Download all Immunefi programs
vyper list                  # See all programs
vyper audit 0x4c9edd...    # Full audit pipeline
vyper report aud_abc123    # Open Immunefi report
vyper metrics              # See your accuracy metrics
```

### Data Portability

Karena semua file-based, Anda bisa:
- **Backup**: `cp -r ~/.vyper/ backup/`
- **Sync**: `rsync -av ~/.vyper/ laptop2:~/.vyper/`
- **Git**: `cd ~/.vyper && git init && git add .`
- **Share**: Kirim folder `audits/*/reports/immunefi.md` ke Immunefi

---

## 8. Yang Masih Perlu Docker

Hanya Exploit Engine yang butuh Docker (Anvil):

```python
# vyper/exploit/anvil.py

class AnvilManager:
    """Manages isolated Anvil instances via Docker"""
    
    def start(self, chain: str, block: int) -> str:
        """Start anvil container with --network=none"""
        container = self.docker.containers.run(
            image="ghcr.io/foundry-rs/foundry",
            command=[
                "anvil",
                "--load-mode", "fork",
                "--fork-url", self.get_rpc(chain),
                "--fork-block-number", str(block),
                "--network", "none",          # 🔴 KRITIS: no internet
                "--host", "0.0.0.0",
                "--port", "8545"
            ],
            network_mode="none",              # No network access
            tmpfs={"/data": "size=1G"},       # RAM disk
            mem_limit=self.config.memory_limit,
            ports={"8545/tcp": None},         # Random host port
            detach=True,
            auto_remove=True
        )
        return container
    
    def stop(self, container_id: str):
        """Force stop and remove"""
        container = self.docker.containers.get(container_id)
        container.stop(timeout=5)
```

---

## 9. Skill System

20 skills disimpan sebagai **Markdown files** di `skills/`:

```markdown
# Skill: reentrancy-detector

## Pattern
Reentrancy terjadi ketika contract melakukan external call
sebelum update state (checks-effects-interactions violation).

## Detection Rules
- Cari external call (call, delegatecall, send, transfer)
- Cek apakah state update terjadi SETELAH external call
- Flag sebagai potential reentrancy

## Severity
- If ETH transfer: critical
- If ERC20 transfer: high
- If only read: medium

## Example (Bad)
```solidity
function withdraw(uint amount) external {
    require(balances[msg.sender] >= amount);
    (bool ok,) = msg.sender.call{value: amount}("");  // external call BEFORE state update
    balances[msg.sender] -= amount;                    // state update AFTER
}
```

## Example (Good)
```solidity
function withdraw(uint amount) external {
    require(balances[msg.sender] >= amount);
    balances[msg.sender] -= amount;                    // state update FIRST
    (bool ok,) = msg.sender.call{value: amount}("");   // external call AFTER
}
```

## Reference
- SWC-107: https://swcregistry.io/docs/SWC-107
```

Skill di-load oleh `vyper/skills/loader.py` dan digunakan oleh AI analyzer + pattern matcher untuk meningkatkan deteksi.

---

## 10. First-Run Experience — `vyper init`

Saat pertama kali dijalankan, Vyper otomatis setup semua yang dibutuhkan.

```
┌──────────────────────────────────────────────────────────────┐
│  VYPER SETUP WIZARD                                          │
│                                                              │
│  $ vyper init                                                 │
│                                                              │
│  🐍 Vyper v0.1.0 — First run setup                          │
│  ──────────────────────────────────────────                   │
│                                                              │
│  [1/5] 📁 Membuat direktori ~/.vyper/ ... ✅                │
│                                                              │
│  [2/5] 🔑 API Keys                                           │
│        Etherscan API key [https://etherscan.io/myapikey]: █  │
│        OpenAI API key    [sk-...]: ██████                    │
│                                                              │
│  [3/5] 🔗 RPC Endpoints                                     │
│        ethereum: https://eth.llamarpc.com (default) ✅       │
│        arbitrum: https://arb1.arbitrum.io/rpc (default) ✅   │
│        optimism: https://opt.llamarpc.com (default) ✅       │
│                                                              │
│  [4/5] 🐳 Docker Check                                       │
│        Docker: ✅ installed                                  │
│        Foundry: ⏳ pulling ghcr.io/foundry-rs/foundry...     │
│        Anvil image: ✅ ready                                 │
│                                                              │
│  [5/5] 📡 Initial Sync                                      │
│        Downloading Immunefi programs...                      │
│        234 programs synced ✅                                │
│        1,247 contracts indexed                               │
│                                                              │
│  ──────────────────────────────────────────                   │
│  ✅ Vyper siap digunakan!                                    │
│                                                              │
│  Next steps:                                                 │
│    vyper list          → Lihat program Immunefi              │
│    vyper audit <addr>  → Audit kontrak pertama              │
│    vyper ui            → Buka dashboard                      │
└──────────────────────────────────────────────────────────────┘
```

### Init Data Structure

```python
# vyper/config.py — auto-run on first import

def ensure_vyper_dir():
    """Buat ~/.vyper/ structure jika belum ada"""
    dirs = [
        "~/.vyper/immunefi/programs",
        "~/.vyper/contracts",
        "~/.vyper/audits",
        "~/.vyper/learning",
        "~/.vyper/skills",
    ]
    for d in dirs:
        Path(d).expanduser().mkdir(parents=True, exist_ok=True)

def create_default_config():
    """Buat config.json default"""
    config = {
        "rpc_endpoints": {
            "ethereum": "https://eth.llamarpc.com",
            "arbitrum": "https://arb1.arbitrum.io/rpc",
            "optimism": "https://opt.llamarpc.com",
            "base": "https://base.llamarpc.com",
            "polygon": "https://polygon.llamarpc.com"
        },
        "api_keys": {
            "etherscan": "",
            "openai": "",
            "anthropic": ""
        },
        "scan": {
            "tools": ["slither", "mythril"],
            "auto_exploit": True,
            "max_concurrent": 2,
            "sync_interval_hours": 6
        },
        "exploit": {
            "max_instances": 2,
            "memory_limit": "4g",
            "timeout_seconds": 300
        },
        "analytics": {
            "auto_improve": True,
            "retroactive_rerun": True
        }
    }
    save_json("~/.vyper/config.json", config)
```

---

## 11. Error Handling — Graceful di Setiap Step

Pipeline tidak boleh crash total karena satu step gagal. Setiap step punya error boundary.

### Pipeline Error Boundaries

```python
# vyper/orchestration/pipeline.py

class AuditPipeline:
    """Pipeline dengan error boundary di setiap step"""
    
    def run(self, address: str, chain: str) -> AuditResult:
        result = AuditResult()
        step_errors = []
        
        # Step 1: Fetch source
        try:
            source = SourceFetcher(chain).fetch(address)
            result.source = source
        except SourceNotFoundError:
            step_errors.append("Source code tidak terverifikasi di Etherscan")
            result.partial = True
        except EtherscanRateLimitError:
            step_errors.append("Etherscan rate limit — coba lagi nanti")
            result.partial = True
        except Exception as e:
            step_errors.append(f"Source fetch gagal: {e}")
            result.partial = True
            result.can_continue = False  # Fatal — tidak bisa lanjut
        
        # Step 2: Static analysis
        if result.can_continue:
            try:
                scanner = Scanner(source)
                result.raw_findings = scanner.run_all()
            except ToolNotFoundError as e:
                step_errors.append(f"Tool tidak terinstall: {e}")
                result.raw_findings = []
            except ToolTimeoutError as e:
                step_errors.append(f"Tool timeout: {e}")
                result.raw_findings = []
            except Exception as e:
                step_errors.append(f"Static analysis gagal: {e}")
                result.raw_findings = []
        
        # Step 3: Pattern matching (safe — DB lookup)
        if result.raw_findings:
            try:
                matcher = PatternMatcher()
                result.matched = matcher.match(result.raw_findings)
            except Exception as e:
                step_errors.append(f"Pattern matching gagal: {e}")
                result.matched = []
        
        # Step 4: AI analysis
        if result.raw_findings:
            try:
                ai = AIAnalyzer()
                result.verdicts = ai.analyze(result.raw_findings, source)
            except OpenAIError as e:
                step_errors.append(f"AI gagal (API error): {e}")
                result.verdicts = self._fallback_no_ai(result.raw_findings)
            except Exception as e:
                step_errors.append(f"AI analysis gagal: {e}")
                result.verdicts = self._fallback_no_ai(result.raw_findings)
        
        # Step 5: Exploit (hanya jika TP critical/high)
        result.exploit_results = []
        for finding in result.tp_findings:
            if finding.severity in ("critical", "high"):
                try:
                    engine = ExploitEngine()
                    expl = engine.execute(source, finding)
                    result.exploit_results.append(expl)
                except DockerNotAvailableError:
                    step_errors.append("Docker tidak tersedia — exploit skipped")
                    break  # Skip semua exploit
                except AnvilForkError as e:
                    step_errors.append(f"Anvil fork gagal: {e}")
                except Exception as e:
                    step_errors.append(f"Exploit {finding.id} gagal: {e}")
        
        # Step 6: Report (selalu jalan, walau partial)
        try:
            reporter = Reporter()
            result.report_paths = reporter.save_all(result)
        except Exception as e:
            step_errors.append(f"Report gagal: {e}")
        
        # Simpan error ke audit log
        if step_errors:
            result.errors = step_errors
            save_json(result.audit_dir / "errors.json", step_errors)
        
        return result
```

### Error Categories & Response

| Error | Dampak | Response |
|-------|--------|----------|
| Source tidak terverifikasi | ❌ Tidak bisa audit | Skip, tandai "unverified" |
| Etherscan rate limit | ⏳ Delay | Auto-retry exponential backoff |
| Slither/Mythril not installed | ⚠️ Tool skip | Warning, lanjut tool lain |
| Tool timeout (>15 min) | ⚠️ Tool skip | Catat, lanjut tool lain |
| OpenAI API down | ⚠️ AI skip | Fallback: severity dari tool saja |
| Docker not available | ⚠️ No exploit | Skip exploit, report tanpa PoC |
| Anvil fork error | ⚠️ Specific exploit skip | Skip finding, lanjut finding lain |
| Disk full | ❌ Fatal | Hentikan, kasih tahu user |
| JSON corrupt | ⚠️ Data skip | Backup file, regenerate |

### Dashboard Error Display

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠️ Audit Partial — ethena-USDe-2026-05-17                  │
│                                                              │
│  Steps completed: 4/6                                        │
│                                                              │
│  🟢  Fetch Source         ✅                                 │
│  🟢  Static Analysis      ✅ (Slither OK, Mythril timeout)   │
│  🟢  Pattern Match        ✅                                 │
│  🟡  AI Analysis          ⚠️ Fallback (No API key)          │
│  🔴  Exploit              ❌ Docker not installed            │
│  🔴  Report               ❌ (skipped due to no results)     │
│                                                              │
│  ⚠️ 3 warnings — [View Details ▾]                          │
│                                                              │
│  Recommendations:                                            │
│  ├─ Install Docker: https://docker.com                      │
│  ├─ Set OpenAI key: vyper config --set openai_key=...       │
│  └─ Install Mythril: pip install mythril                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 12. CLI UX Polish — Terminal Experience

Pakai library **Rich** untuk output yang cantik di terminal.

### Progress Bar Saat Audit

```python
# vyper/cli.py

from rich.console import Console
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, 
    BarColumn, TimeRemainingColumn
)

@cli.command()
@click.argument("address")
def audit(address: str):
    """Full audit pipeline"""
    console = Console()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        
        task = progress.add_task("Fetching source...", total=6)
        source = fetch_source(address)
        progress.update(task, advance=1, description="Running Slither...")
        
        slither = run_slither(source)
        progress.update(task, advance=1, description="Running Mythril...")
        
        mythril = run_mythril(source)
        progress.update(task, advance=1, description="AI Analysis...")
        
        verdicts = ai_analyze(slither + mythril, source)
        progress.update(task, advance=1, description="Testing Exploit...")
        
        exploit = run_exploit(source, verdicts)
        progress.update(task, advance=1, description="Generating Report...")
        
        report = generate_report(verdicts, exploit)
        progress.update(task, advance=1, description="✅ Complete!")
```

### Output di Terminal

```
┌──────────────────────────────────────────────────────────────┐
│  🐍 VYPER AUDIT                                              │
│  ──────────────────────────────────────────                   │
│                                                              │
│  Contract: 0x4c9edd5852cd905f086c759e8383e09bff1e68b3       │
│  Chain:    Ethereum                                          │
│  Program:  Ethena                                            │
│                                                              │
│  ═══════════════════════════════════════════════════════════  │
│                                                              │
│  ████████████████████████████████████████████████████ 100%   │
│  Fetch ▶ Static ▶ Pattern ▶ AI ▶ Exploit ▶ Report          │
│                                                              │
│  ═══════════════════════════════════════════════════════════  │
│                                                              │
│  RESULTS                                                     │
│  ┌──────┬────────────┬──────────┬────────┬──────────────┐   │
│  │  ID  │ Severity   │ Finding  │ Class  │ Exploit      │   │
│  ├──────┼────────────┼──────────┼────────┼──────────────┤   │
│  │ F001 │ 🔴 CRITICAL│Reentrancy│ TP ✅  │ $1.25M atk  │   │
│  │ F002 │ 🟠 HIGH    │Flash Loan│ TP ✅  │ $890K atk   │   │
│  │ F003 │ 🟡 MEDIUM  │Unused Ret│ FP ❌  │ —           │   │
│  │ F004 │ ℹ️ INFO    │Low Call  │ TN ✅  │ —           │   │
│  └──────┴────────────┴──────────┴────────┴──────────────┘   │
│                                                              │
│  Score: 8.5/10  │  Precision: 66%  │  TP: 2  │  FP: 1     │
│                                                              │
│  📄 Report: ~/.vyper/audits/ethena-USDe/reports/            │
│  🌐 Dashboard: vyper ui                                     │
└──────────────────────────────────────────────────────────────┘
```

### Semua CLI Commands dengan Rich

```bash
vyper sync              # Progress bar with live count
vyper audit <addr>      # Full progress bar + results table
vyper list              # Table with sortable columns
vyper metrics           # Cards + bar charts in terminal
vyper learn             # Colored FN/FP list with priority
vyper feedback <id>     # Interactive form
vyper ui                # "Opening dashboard at localhost:3000"
vyper init              # Interactive wizard
```

---

## 13. Feedback Loop — FP/FN Kembali ke Sistem

Ini adalah **mekanisme paling penting** untuk pembelajaran. Tanpa ini, Vyper tidak akan pernah improve.

### Feedback Flow

```
USER FLOW:
═══════════════════════════════════════════════════════════════

                        ┌──────────────────┐
                        │  FINDING DI       │
                        │  DASHBOARD        │
                        │                   │
                        │  [✅ TP] [❌ FP]  │
                        │  [⚠️ FN]          │
                        └────────┬─────────┘
                                 │
              User klik tombol feedback
                                 │
                                 ▼
              ┌──────────────────────────────┐
              │  FEEDBACK FORM                │
              │                               │
              │  Finding: F-001               │
              │  Current: TRUE POSITIVE       │
              │                               │
              │  Actually this is:            │
              │  ○ True Positive (confirm)    │
              │  ● False Positive (reject)    │
              │  ○ False Negative (missed)    │
              │                               │
              │  Notes: "Immunefi rejected —  │
              │  they said this is a design   │
              │  choice, not a vulnerability" │
              │                               │
              │  [Submit Feedback]            │
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  FEEDBACK PROCESSOR           │
              │                               │
              │  1. Reclassify finding        │
              │  2. Log ke learning/          │
              │  3. Update metrics.json       │
              │  4. Trigger improvement:      │
              │     ├─ Jika FP → turunkan    │
              │     │  confidence pattern     │
              │     └─ Jika FN → buat        │
              │        pattern baru           │
              └──────────────────────────────┘
```

### Feedback Data Model

```json
// ~/.vyper/learning/feedback.json
{
  "entries": [
    {
      "id": "FB-001",
      "finding_id": "F-001",
      "audit_id": "ethena-USDe-2026-05-17",
      "type": "reclassification",
      "from": "true_positive",
      "to": "false_positive",
      "source": "immunefi_rejection",
      "reason": "Immunefi rejected: design choice, not a vuln",
      "improvement_triggered": true,
      "improvement_action": "Adjust Slither reentrancy detector — add whitelist for specific patterns",
      "created_at": 1717890500
    },
    {
      "id": "FB-002",
      "finding_id": null,
      "audit_id": "ethena-USDe-2026-05-17",
      "type": "new_fn",
      "from": null,
      "to": "false_negative",
      "source": "immunefi_feedback",
      "reason": "Immunefi found oracle manipulation bug that we missed",
      "improvement_triggered": true,
      "improvement_action": "Created new pattern: oracle-manipulation. Added to Vuln DB.",
      "created_at": 1717890600
    }
  ]
}
```

### CLI Feedback Command

```bash
# Feedback dari CLI
vyper feedback F-001 --type=fp --reason="Immunefi rejected: design choice"
vyper feedback --new-fn --finding="Oracle manipulation missed" --audit="ethena-USDe"

# Atau interactive
vyper feedback
→ Pilih finding dari list
→ Pilih: reject (FP) / confirm (TP) / missed (FN)
→ Tulis alasan
→ Otomatis trigger improvement
```

### Improvement Engine

```python
# vyper/learning/improver.py

class ImprovementEngine:
    """Trigger improvement actions based on feedback"""
    
    def process_feedback(self, feedback: Feedback):
        if feedback.to == "false_positive":
            # Turunkan confidence pattern
            pattern = self.find_pattern(feedback.finding_id)
            pattern.confidence *= 0.7  # Turun 30%
            pattern.fp_count += 1
            log_learning(f"FP: {pattern.name} confidence turun")
            
        elif feedback.to == "false_negative":
            # Buat pattern baru
            new_pattern = self.suggest_pattern(feedback)
            save_vuln_pattern(new_pattern)
            
            # Trigger retroactive re-run
            if config.analytics.retroactive_rerun:
                self.schedule_rerun(new_pattern)
            
            log_learning(f"FN: Pattern baru: {new_pattern.name}")
```

---

## 14. Multi-Source Source Code Fetching — Source Code dari Mana Saja

Source code kontrak tidak selalu di Etherscan. Vyper punya multi-provider fallback.

### Provider Priority Chain

```
Input: address (0x4c9edd...) + chain (ethereum)
                │
                ▼
┌─────────────────────────────────────┐
│  REPO CHECK (Immunefi program)      │ ← Ada GitHub? Langsung clone repo
│  - program.repos[].url = github     │
│  - git clone → ~/.vyper/repos/      │
│  ✅ BEST: Full project + tests      │
└──────────────┬──────────────────────┘
               │ (no repo found)
               ▼
┌─────────────────────────────────────┐
│  SOURCIFY                           │ ← Decentralized verification
│  - GET /files/{chain}/{address}     │
│  ✅ No API key needed               │
│  ✅ All chains supported            │
└──────────────┬──────────────────────┘
               │ (not verified)
               ▼
┌─────────────────────────────────────┐
│  ETHERSCAN                          │ ← Fallback utama
│  - GET /api?module=contract         │
│  ⚠️ Perlu API key                  │
│  ⚠️ Hanya chain populer            │
└──────────────┬──────────────────────┘
               │ (not verified)
               ▼
┌─────────────────────────────────────┐
│  BLOCKSCOUT                         │ ← L2 chains
│  - GET /api?module=contract         │
│  ✅ Optimism, Arbitrum, Polygon     │
└──────────────┬──────────────────────┘
               │ (not found)
               ▼
┌─────────────────────────────────────┐
│  MANUAL                             │ ← User-provided path
│  - File path dari user              │
│  - `vyper audit --source ./src/`   │
│  ✅ Tetap bisa audit                │
└─────────────────────────────────────┘
```

### Provider Implementation

```python
# vyper/source/detector.py

from dataclasses import dataclass
from pathlib import Path

@dataclass
class SourceMetadata:
    """Metadata sumber kontrak"""
    provider: str           # "github" | "sourcify" | "etherscan" | "blockscout" | "manual"
    url: str                # URL sumber
    local_path: Path        # ~/.vyper/contracts/{chain}/{address}/
    has_tests: bool         # Ada test files? (hanya untuk github)
    has_foundry: bool       # Ada foundry.toml? (hanya untuk github)
    file_count: int         # Total file solidity
    is_full_repo: bool      # Full project atau single file?

class SourceDetector:
    """Try multiple providers, return best available source"""
    
    def __init__(self, chain: str):
        self.chain = chain
        self.providers = [
            RepoProvider(),       # Check program.repos → git clone
            SourcifyProvider(),   # No API key needed
            EtherscanProvider(),  # Need API key
            BlockscoutProvider(), # L2 chains
        ]
    
    def fetch(self, address: str, program: Program = None) -> SourceResult:
        """Try each provider in order. Return first success."""
        
        for provider in self.providers:
            if provider.is_available(address, program):
                try:
                    result = provider.fetch(address, program)
                    if result.success:
                        return result
                except ProviderUnavailable:
                    continue
        
        # Last resort: return error with guidance
        return SourceResult(
            success=False,
            error=f"No source found for {address} on {self.chain}",
            suggestion="Use --source to provide file path manually"
        )
```

### RepoProvider — Git Clone Full Project

Provider paling powerful. Kloning seluruh repo program.

```python
# vyper/source/providers/github.py

class RepoProvider:
    """Clone GitHub repo — best source quality"""
    
    def is_available(self, address, program):
        """Ada GitHub URL di Immunefi program?"""
        return bool(program and program.repos)
    
    def fetch(self, address, program) -> SourceResult:
        repo = self._best_repo(program.repos)  # Pilih repo terbaik
        dest = self.repos_dir / program.slug
        
        if not (dest / ".git").exists():
            # Clone pertama
            subprocess.run(["git", "clone", repo.url, str(dest)], check=True)
            subprocess.run(["git", "-C", str(dest), "pull"], check=True)
        else:
            # Update
            subprocess.run(["git", "-C", str(dest), "pull"], check=True)
        
        # Map address → file path dalam repo
        file_map = self._resolve_address_to_file(address, dest)
        
        # Copy source ke storage
        for src_path in file_map.values():
            shutil.copy2(src_path, self.storage_dir / src_path.name)
        
        return SourceResult(
            success=True,
            provider="github",
            local_path=self.storage_dir,
            metadata=SourceMetadata(
                provider="github",
                url=repo.url,
                local_path=self.storage_dir,
                has_tests=(dest / "test").exists(),
                has_foundry=(dest / "foundry.toml").exists(),
                file_count=len(file_map),
                is_full_repo=True
            )
        )
    
    def _resolve_address_to_file(self, address, repo_path):
        """
        Cari file yang berisi kontrak address ini.
        Strategy: parse foundry.toml → cari deploy scripts → AST grep
        """
        # Strategy 1: Cek vyper-meta.json (cache hasil mapping)
        meta = repo_path / "vyper-meta.json"
        if meta.exists():
            return json.loads(meta.read_text()).get(address, {})
        
        # Strategy 2: Grep address di semua .sol files
        result = {}
        for sol_file in repo_path.rglob("*.sol"):
            content = sol_file.read_text()
            if address.lower() in content.lower():
                # This contract is deployed/used here
                result[str(sol_file.relative_to(repo_path))] = sol_file
        
        # Cache hasil mapping
        mapping = {address: {str(k): str(v) for k, v in result.items()}}
        meta.write_text(json.dumps(mapping, indent=2))
        
        return result
```

### SourcifyProvider — No API Key Needed

Sourcify is decentralized, supports all chains, no API key.

```python
# vyper/source/providers/sourcify.py

class SourcifyProvider:
    """Sourcify — decentralized contract verification"""
    
    SOURCIFY_API = "https://sourcify.dev/server"
    
    def is_available(self, address, program=None):
        return True  # Always try Sourcify first (no API key)
    
    def fetch(self, address, program=None) -> SourceResult:
        # Try full match first, then partial match
        for match_type in ["full_match", "partial_match"]:
            url = f"{self.SOURCIFY_API}/files/{self.chain}/{address}/{match_type}"
            resp = requests.get(url)
            if resp.status_code == 200:
                files = resp.json()
                # Save files to storage
                for f in files:
                    path = self.storage_dir / f["name"]
                    path.write_text(f["content"])
                
                return SourceResult(
                    success=True,
                    provider="sourcify",
                    local_path=self.storage_dir,
                    metadata=SourceMetadata(
                        provider="sourcify",
                        url=url,
                        local_path=self.storage_dir,
                        has_tests=False,
                        has_foundry=False,
                        file_count=len(files),
                        is_full_repo=False
                    )
                )
        
        raise ProviderUnavailable("Not verified on Sourcify")
```

### Immunefi Repo Detection

Saat sync Immunefi, Vyper otomatis deteksi repo dari program:

```python
# vyper/immunefi/repo_detector.py

class RepoDetector:
    """Cari GitHub/web repo dari data Immunefi program"""
    
    def detect(self, program: dict) -> list[RepoInfo]:
        repos = []
        
        # Source 1: Project links dari Immunefi
        for link in program.get("links", []):
            if "github.com" in link["url"]:
                repos.append(RepoInfo(
                    url=link["url"],
                    type="github",
                    detected_via="project_links"
                ))
        
        # Source 2: Website → scrape GitHub link
        if program.get("website"):
            github_urls = self._scrape_github_links(program["website"])
            repos.extend(github_urls)
        
        # Source 3: Asset description
        for asset in program.get("assets", []):
            if asset.get("description") and "github" in asset["description"]:
                repos.append(RepoInfo(
                    url=asset["description"],
                    type="github",
                    detected_via="asset_description"
                ))
        
        # Source 4: Search GitHub API
        repos.extend(self._search_github_api(program["name"]))
        
        return repos
    
    def _search_github_api(self, project_name: str) -> list:
        """GitHub API search: cari repo yang match"""
        url = f"https://api.github.com/search/repositories?q={project_name}+solidity&sort=stars&per_page=3"
        resp = requests.get(url)
        if resp.status_code == 200:
            return [
                RepoInfo(url=item["clone_url"], type="github", detected_via="github_api_search")
                for item in resp.json()["items"]
            ]
        return []
```

### Pipeline: Source → Scanner Integration

```python
# Pipeline dengan multi-source
class AuditPipeline:
    def run(self, address: str, chain: str, program: Program = None):
        # 1. Detect source — multi-provider fallback
        detector = SourceDetector(chain)
        source = detector.fetch(address, program)
        
        if not source.success:
            logger.error(f"Cannot audit {address}: {source.error}")
            return AuditResult.error(source.error)
        
        # 2. Scanner — full repo vs single file
        scanner = Scanner(source)
        if source.metadata.is_full_repo:
            # Scan seluruh proyek (cross-contract analysis)
            raw_findings = scanner.run_all()
        else:
            # Scan single contract
            raw_findings = scanner.run_single(source.primary_file)
        
        # ... rest of pipeline
```

### Dampak ke Storage

| Sebelum | Sesudah |
|---------|---------|
| Hanya `~/.vyper/contracts/{chain}/{address}/` | + `~/.vyper/repos/{program}/` (full git repo) |
| Satu file `.sol` | Banyak file + test + config |
| Tidak tahu asal source | `metadata.json` berisi `source_prov` |
| Tidak ada mapping | `vyper-meta.json` untuk address → file |

### Dampak ke Priority Scoring

Source quality naikkan priority score:

```python
def calculate_priority(program: Program) -> float:
    score = 0.0
    
    # ... existing scoring ...
    
    # 🆕 Source availability bonus (+10)
    if program.repos:
        score += 10  # Ada GitHub → full repo analysis
    
    # 🆕 Test files bonus (+5)
    if any(r.has_tests for r in program.repos):
        score += 5   # Bisa run test → konfirmasi bug lebih cepat
```

### Summary

| Provider | API Key | Chains | Quality | Priority |
|----------|---------|--------|---------|----------|
| **GitHub** (clone) | No | All | ⭐⭐⭐⭐⭐ Full project | Best |
| **Sourcify** | No | All | ⭐⭐⭐⭐ Verified | High |
| **Etherscan** | Yes | Main chains | ⭐⭐⭐ Single file | Medium |
| **Blockscout** | No | L2s | ⭐⭐⭐ Single file | Medium |
| **Manual** | - | - | ⭐⭐ User-provided | Low |

---

## 15. Priority Scoring Engine — Audit Kontrak Paling Bernilai Dulu

Tidak semua program sama. Vyper prioritaskan kontrak berdasarkan skor.

### Formula Prioritas

```python
def calculate_priority(program: Program) -> float:
    """Skor prioritas 0-100"""
    score = 0
    
    # Bounty weight (40%)
    bounty_score = min(program.max_bounty_usd / 100000, 40)  # $4M = 40pts
    
    # TP history weight (25%)
    tp_rate = program.tp_found / max(program.times_audited, 1)
    tp_score = tp_rate * 25
    
    # Chain weight (15%)
    chain_multiplier = {
        "ethereum": 1.0, "arbitrum": 0.9, "optimism": 0.8,
        "base": 0.8, "polygon": 0.7, "bsc": 0.6,
        "avalanche": 0.6, "fantom": 0.5, "other": 0.3
    }
    chain_score = 15 * chain_multiplier.get(program.chain, 0.3)
    
    # Freshness weight (10%)
    days_since_added = (datetime.now() - program.added_at).days
    freshness = max(0, 10 - days_since_added * 0.1)  # Turun 0.1/hari
    
    # Contract count weight (10%)
    contract_score = 10 * min(len(program.contracts) / 20, 1)
    
    # 🆕 Source availability bonus (+10)
    source_bonus = 0
    if program.repos:
        for repo in program.repos:
            if repo.url and "github.com" in repo.url:
                source_bonus += 10  # Full repo analysis is better
                if repo.has_tests:
                    source_bonus += 5  # Can run tests to confirm bugs
                break  # Max 10 (not 10 per repo)
    
    return bounty_score + tp_score + chain_score + freshness + contract_score + source_bonus
```

### Priority Queue di Terminal & Dashboard

```bash
vyper list --sort=priority

# Output:
# ┌──────────┬────────────┬────────┬──────────┬────────┐
# │ Priority │ Program    │ Bounty │ Contracts│ Score  │
# ├──────────┼────────────┼────────┼──────────┼────────┤
# │ 🥇 98    │ Ethena     │ $3,000K│ 26       │ 98/100 │
# │ 🥈 85    │ Lido       │ $2,000K│ 12       │ 85/100 │
# │ 🥉 72    │ Aave       │ $1,500K│ 8        │ 72/100 │
# │ 68       │ Uniswap    │ $1,000K│ 15       │ 68/100 │
# │ 45       │ PancakeSwap│ $750K  │ 6        │ 45/100 │
# └──────────┴────────────┴────────┴──────────┴────────┘
```

```bash
vyper batch --top=10    # Audit 10 program prioritas tertinggi
vyper batch --all       # Audit semua (butuh waktu)
```

---

## 16. Contract Similarity Detection — Force Multiplier

**Konsep**: Jika contract A punya bug X, contract B yang mirip dengan A kemungkinan juga punya bug X.

### Cara Kerja

```
┌──────────────────────────────────────────────────────────────┐
│  CONTRACT SIMILARITY ENGINE                                  │
│                                                              │
│  1. Audit contract A → find bug X                            │
│  2. Ekstrak AST signatures dari bug X                        │
│     ├─ Function selector                                     │
│     ├─ Control flow graph fragment                           │
│     └─ Storage access pattern                                │
│                                                              │
│  3. Cari contract B, C, D yang punya AST mirip              │
│     ├─ Same function selector?                              │
│     ├─ Similar control flow?                                │
│     └─ Same storage pattern?                                │
│                                                              │
│  4. Prioritaskan contract B, C, D untuk audit               │
│     ⚡ "Contract ini mirip dengan Ethena yang punya bug!"   │
│                                                              │
│  5. Saat audit contract B, focus pada area yang mirip       │
│     → AI diberi konteks: "bug serupa ditemukan di X"       │
└──────────────────────────────────────────────────────────────┘
```

### Similarity Data Model

```json
// ~/.vyper/learning/similarity.json
{
  "clusters": [
    {
      "id": "CL-001",
      "pattern": "reentrancy_withdraw",
      "contracts": [
        {"address": "0x4c9edd...", "program": "Ethena", "has_bug": true},
        {"address": "0x8a9b7c...", "program": "Lido", "has_bug": false, "priority_boost": 0.8},
        {"address": "0x3e4f5a...", "program": "Aave", "has_bug": false, "priority_boost": 0.6}
      ],
      "ast_signature": "withdraw(uint256) → call → balance_update",
      "similarity_threshold": 0.85
    }
  ]
}
```

### Dashboard — Similar Contracts Section

```
┌──────────────────────────────────────────────────────────────┐
│  🔗 SIMILAR CONTRACTS                                        │
│                                                              │
│  Bug: Reentrancy in withdraw() — ditemukan di USDe.sol      │
│                                                              │
│  Contract ini mirip dengan:                                  │
│  ┌──────────┬──────────────┬──────────┬──────────────────┐  │
│  │ Similar  │ Contract     │ Program  │ Priority Boost  │  │
│  ├──────────┼──────────────┼──────────┼──────────────────┤  │
│  │ 92% 🔥   │ 0x8a9b7c... │ Lido     │ +80% 🚀          │  │
│  │ 85% 🔥   │ 0x3e4f5a... │ Aave     │ +60% 🚀          │  │
│  │ 67%      │ 0x1b2c3d... │ Maker    │ +20%             │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  [Audit Similar Contracts →]                                │
└──────────────────────────────────────────────────────────────┘
```

---

## 17. Submission Tracker — Lacak Bounty

Lacak semua submission ke Immunefi: apa yang di-submit, statusnya, berapa bounty-nya.

### Data Model

```json
// ~/.vyper/submissions.json
{
  "submissions": [
    {
      "id": "SUB-001",
      "finding_id": "F-001",
      "audit_id": "ethena-USDe-2026-05-17",
      "program": "Ethena",
      "title": "Reentrancy in withdraw()",
      "severity": "critical",
      "submitted_at": 1717891000,
      "status": "pending",        // pending, under_review, accepted, rejected, paid
      "immunefi_ticket_url": "https://immunefi.com/bounty/ethena/123",
      "response": null,
      "bounty_usd": null,
      "paid_at": null,
      "notes": ""
    },
    {
      "id": "SUB-002",
      "finding_id": "F-002",
      "audit_id": "lido-stETH-2026-05-18",
      "program": "Lido",
      "title": "Flash Loan Oracle Manipulation",
      "severity": "high",
      "submitted_at": 1717977400,
      "status": "accepted",
      "immunefi_ticket_url": "https://immunefi.com/bounty/lido/456",
      "response": "Confirmed, bounty awarded",
      "bounty_usd": 50000,
      "paid_at": 1718063800,
      "notes": "Paid in USDC"
    }
  ],
  "stats": {
    "total_submitted": 15,
    "pending": 3,
    "accepted": 10,
    "rejected": 2,
    "total_bounty_earned": 245000,
    "top_program": "Ethena",
    "last_submission": 1717891000
  }
}
```

### CLI & Dashboard

```bash
vyper submit F-001                           # Mark sebagai submitted
vyper submit F-001 --status=accepted --bounty=50000  # Update status
vyper submissions                            # Lihat semua submission

# Output:
# ┌──────┬──────────┬──────────────┬──────────┬───────────┬────────┐
# │ ID   │ Program  │ Bug          │ Status   │ Bounty    │ Total  │
# ├──────┼──────────┼──────────────┼──────────┼───────────┼────────┤
# │ 001  │ Ethena   │ Reentrancy   │ Pending  │ —         │ —      │
# │ 002  │ Lido     │ Oracle Manip │ ✅ Paid  │ $50,000   │ $50K   │
# └──────┴──────────┴──────────────┴──────────┴───────────┴────────┘
```

Dashboard — Submission Tracker Page:
```
┌──────────────────────────────────────────────────────────────┐
│  💰 SUBMISSION TRACKER                          Total: $245K │
│                                                              │
│  ┌────────┬────────────────┬────────┬────────┬────────────┐ │
│  │ Status │ Finding        │ Program│ Bounty │ Date       │ │
│  ├────────┼────────────────┼────────┼────────┼────────────┤ │
│  │ ⏳     │ Reentrancy     │ Ethena │ —      │ 2h ago     │ │
│  │ ✅     │ Oracle Manip   │ Lido   │ $50K   │ 2 days ago│ │
│  │ ✅     │ Access Control │ Aave   │ $25K   │ 1 week ago│ │
│  │ ❌     │ Integer Over   │ Uniswap│ —      │ 2 weeks ago│ │
│  │ ✅     │ Flash Loan     │ Euler  │ $150K  │ 3 weeks ago│ │
│  └────────┴────────────────┴────────┴────────┴────────────┘ │
│                                                              │
│  📊 Stats: 15 submitted │ 10 accepted │ $245K earned        │
│  Best program: Euler ($150K)                                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 18. Audit Re-Run — Retroactive Improvement

Ketika pattern baru ditambahkan (karena FN), Vyper otomatis re-run audit lama untuk lihat apakah pattern baru menangkap bug yang terlewat.

### Cara Kerja

```
┌──────────────────────────────────────────────────────────────┐
│  RETROACTIVE RE-RUN                                          │
│                                                              │
│  1. Pattern baru: oracle-manipulation                        │
│     (dari FN feedback — "kita miss oracle bug")             │
│                                                              │
│  2. Vyper cari semua audit lama yang:                        │
│     ├─ Menggunakan Chainlink/Harga feed                     │
│     └─ Belum di-scan dengan pattern oracle                  │
│                                                              │
│  3. Re-run hanya untuk pattern baru (cepat — ~5 detik)      │
│     ├─ Bukan full audit ulang                               │
│     └─ Hanya pattern matching + AI analysis                 │
│                                                              │
│  4. Jika ketemu bug baru → update finding + reclassify      │
│     ├─ Finding baru: TP ✅                                   │
│     └─ FN yang lalu: sekarang terdeteksi 🎉                 │
│                                                              │
│  5. Report di-update, metrics di-update                     │
│     "FN rate turun 15% setelah pattern oracle-manipulation" │
└──────────────────────────────────────────────────────────────┘
```

### Re-Run Data

```json
// ~/.vyper/learning/reruns.json
{
  "reruns": [
    {
      "id": "RR-001",
      "trigger": "new_pattern: oracle-manipulation",
      "date": 1717892000,
      "audits_affected": 12,
      "new_tp_found": 3,
      "fn_converted": 2,
      "fn_rate_before": 0.15,
      "fn_rate_after": 0.11,
      "improvement": "+4% accuracy"
    }
  ]
}
```

### Dashboard — Improvement Metrics

```
┌──────────────────────────────────────────────────────────────┐
│  📈 IMPROVEMENT OVER TIME                                    │
│                                                              │
│  Pattern: oracle-manipulation                                │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  FN Rate                                                │ │
│  │  20% ┤        ╭──╮                                     │ │
│  │  15% ┤ ╭──╮ ╭╯  ╰╮  ╭──╮ 🔥 pattern added             │ │
│  │  10% ┤╭╯  ╰─╯    ╰──╯  ╰╮──╮                          │ │
│  │   5% ┤╯                   ╰──╰──                       │ │
│  │      └──┬──┬──┬──┬──┬──┬──┬──┬──┬──                    │ │
│  │        W1 W2 W3 W4 W5 W6 W7 W8                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Results:                                                    │
│  ├─ 3 new TP ditemukan dari audit lama                      │
│  ├─ 2 FN dikonversi ke TP                                   │
│  └─ Akurasi naik 4%                                         │
└──────────────────────────────────────────────────────────────┘
```

---

## 19. Autonomous Daemon — Full Auto-Hunt Mode

**Mode utama Vyper.** Setelah setup, Vyper bisa berjalan 24/7 tanpa intervensi — mencari bug sendiri, memprioritaskan kontrak paling bernilai, dan memberi notifikasi ketika menemukan critical TP.

### Filosofi Autonomous

```
┌──────────────────────────────────────────────────────────────┐
│                    VYPER DAEMON                               │
│                                                              │
│  "Setel dan lupakan."                                        │
│                                                              │
│  vyper daemon start                                          │
│    ↓                                                         │
│  Vyper otomatis:                                             │
│  ├─ 🔄 Sync Immunefi tiap 6 jam                             │
│  ├─ 📊 Hitung priority score semua kontrak                  │
│  ├─ 🔍 Audit kontrak prioritas tertinggi                    │
│  ├─ 💥 Exploit critical/high TP                             │
│  ├─ 📄 Generate report + PoC                                │
│  ├─ 🔔 Notifikasi ke desktop + dashboard                    │
│  ├─ 📈 Update metrics                                       │
│  └─ 🔄 Belajar dari setiap hasil                            │
│                                                              │
│  User hanya perlu:                                           │
│  1. Buka dashboard lihat hasil                              │
│  2. Klik "Submit" untuk kirim ke Immunefi                   │
│  3. Klik feedback jika klasifikasi salah                    │
└──────────────────────────────────────────────────────────────┘

### Cara Pakai

```bash
vyper daemon start          # Mulai autonomous hunter
vyper daemon status         # Cek status
vyper daemon stop           # Hentikan
vyper daemon logs           # Lihat log real-time
vyper daemon stats          # Statistik sesi berjalan
```

### Daemon Architecture

```python
# vyper/daemon.py — Autonomous Hunter

import time
import asyncio
from datetime import datetime, timedelta
from rich.live import Live
from rich.table import Table

class VyperDaemon:
    """Autonomous bug hunter — jalan 24/7 tanpa intervensi"""
    
    def __init__(self):
        self.running = False
        self.stats = {
            "started_at": None,
            "total_audits": 0,
            "tp_found": 0,
            "critical_found": 0,
            "exploits_success": 0,
            "bounty_earned": 0,
            "contracts_scanned": [],
            "errors": []
        }
        self.schedule = {
            "sync": timedelta(hours=6),
            "audit": timedelta(hours=1),     # Audit cycle tiap jam
            "rerun": timedelta(days=1),       # Re-run audit lama tiap hari
            "cleanup": timedelta(days=7)      # Cleanup tiap minggu
        }
    
    async def run(self):
        """Main daemon loop"""
        self.running = True
        self.stats["started_at"] = datetime.now()
        
        last_sync = datetime.min
        last_rerun = datetime.min
        last_cleanup = datetime.min
        
        notify("🚀 Vyper daemon started — hunting for bugs...")
        
        while self.running:
            now = datetime.now()
            
            # ⏰ TASK 1: Sync Immunefi (tiap 6 jam)
            if now - last_sync >= self.schedule["sync"]:
                await self.sync_immunefi()
                last_sync = now
            
            # ⏰ TASK 2: Audit kontrak prioritas (tiap jam)
            await self.audit_cycle()
            
            # ⏰ TASK 3: Retroactive re-run (tiap hari)
            if now - last_rerun >= self.schedule["rerun"]:
                await self.retroactive_rerun()
                last_rerun = now
            
            # ⏰ TASK 4: Cleanup (tiap minggu)
            if now - last_cleanup >= self.schedule["cleanup"]:
                await self.cleanup()
                last_cleanup = now
            
            # Simpan stats
            self.save_stats()
            
            # Tidur 5 menit sebelum cek lagi
            await asyncio.sleep(300)
    
    async def sync_immunefi(self):
        """Sync program Immunefi"""
        logger.info("[daemon] Syncing Immunefi programs...")
        try:
            scraper = ImmunefiScraper()
            result = scraper.sync_all()
            if result.new_programs > 0:
                notify(f"📡 {result.new_programs} program baru dari Immunefi!")
            logger.info(f"[daemon] Sync done: {result.total} programs")
        except Exception as e:
            logger.error(f"[daemon] Sync failed: {e}")
            self.stats["errors"].append({"task": "sync", "error": str(e)})
    
    async def audit_cycle(self):
        """Audit kontrak prioritas tertinggi"""
        # 1. Hitung priority semua unscanned contracts
        priorities = self.calculate_priorities()
        
        if not priorities:
            logger.info("[daemon] No unscanned contracts to audit")
            return
        
        # 2. Ambil top N
        batch_size = config.get("daemon", {}).get("batch_size", 3)
        top = priorities[:batch_size]
        
        logger.info(f"[daemon] Auditing top {len(top)} contracts")
        
        for contract in top:
            if not self.running:
                break
            
            try:
                # 3. Full audit
                result = await self.run_audit(contract)
                
                # 4. Update stats
                self.stats["total_audits"] += 1
                self.stats["contracts_scanned"].append(contract.address)
                
                # 5. Notify jika critical/high TP
                critical_tp = [f for f in result.tp if f.severity == "critical"]
                high_tp = [f for f in result.tp if f.severity == "high"]
                
                if critical_tp:
                    self.stats["critical_found"] += len(critical_tp)
                    for finding in critical_tp:
                        notify(
                            f"🔴 CRITICAL BUG FOUND in {contract.program}!\n"
                            f"{finding.title}\n"
                            f"💰 Value at risk: ${finding.estimated_impact_usd:,.0f}\n"
                            f"📄 Report: ~/.vyper/audits/{result.id}/reports/immunefi.md"
                        )
                
                if high_tp:
                    for finding in high_tp:
                        notify(
                            f"🟠 HIGH BUG FOUND in {contract.program}!\n"
                            f"{finding.title}"
                        )
                
                # 6. Exploit otomatis
                if critical_tp or high_tp:
                    for finding in critical_tp + high_tp:
                        try:
                            engine = ExploitEngine()
                            expl = engine.execute(contract.source, finding)
                            if expl.success:
                                self.stats["exploits_success"] += 1
                        except Exception as e:
                            logger.error(f"Exploit failed: {e}")
                
                # 7. Kirim event ke dashboard
                self.notify_dashboard(result)
                
            except Exception as e:
                logger.error(f"[daemon] Audit failed for {contract.address}: {e}")
                self.stats["errors"].append({
                    "task": "audit", 
                    "contract": contract.address,
                    "error": str(e)
                })
        
        # 8. Update metrics setelah batch
        MetricsTracker().update_aggregate()
    
    def calculate_priorities(self) -> list:
        """Hitung priority semua contract, urutkan"""
        priorities = []
        
        for program in load_all_programs():
            for contract in program.contracts:
                if contract.audit_status == "done":
                    continue  # Skip yang sudah di-audit
                
                score = PriorityEngine.calculate(program, contract)
                priorities.append({
                    "program": program.name,
                    "address": contract.address,
                    "chain": contract.chain,
                    "bounty": program.max_bounty_usd,
                    "priority": score,
                    "similar_bonus": self.get_similarity_bonus(contract)
                })
        
        # Urutkan: priority + similarity bonus
        priorities.sort(key=lambda x: x["priority"] + x["similar_bonus"], reverse=True)
        return priorities
    
    def get_similarity_bonus(self, contract) -> float:
        """Bonus priority jika kontrak mirip dengan yang punya bug"""
        for cluster in load_similarity_clusters():
            for c in cluster.contracts:
                if c.address == contract.address and not c.has_bug:
                    # Kontrak mirip dengan yang punya bug → bonus
                    return cluster.similarity_score * 50  # Max +50pts
        return 0
    
    def notify_dashboard(self, result):
        """Kirim event ke dashboard via SSE"""
        write_event({
            "type": "daemon.audit_completed",
            "audit_id": result.id,
            "program": result.program,
            "tp_count": result.tp_count,
            "critical_count": result.critical_count,
            "score": result.score,
            "timestamp": time.time()
        })
    
    def stop(self):
        """Hentikan daemon"""
        self.running = False
        self.save_stats()
        notify("🛑 Vyper daemon stopped")
    
    def save_stats(self):
        """Simpan stats ke file"""
        self.stats["last_active"] = datetime.now().isoformat()
        save_json("~/.vyper/daemon_stats.json", self.stats)
```

### Daemon Priority Queue

```
DAEMON PRIORITY QUEUE:
═══════════════════════════════════════════════════════════════

Setiap cycle (default: tiap jam), daemon:

1. Filter kontrak yang belum pernah di-audit
2. Beri priority score:
     Program Bounty (40%)      +$3M = 40pts,      +$100K = 4pts
     Similarity Bonus (30%)    Mirip kontrak dgn bug = +50pts max
     Chain Weight (15%)        ETH=1.0, ARB=0.9, OP=0.8...
     Freshness (10%)           Program baru = 10pts, turun 0.1/hari
     TP History (5%)           Program sering dpt TP = bonus

3. Ambil top N (default: 3 kontrak per cycle)
4. Audit berurutan (bukan paralel — biar tidak overload laptop)
5. Jika audit berhasil → tandai "done" → tidak akan di-audit lagi
   KECUALI ada pattern baru → retroactive re-run

 EXAMPLE PRIORITY QUEUE:
 ┌───┬────────────┬────────────┬──────────┬────────┬──────────┐
 │ # │ Contract   │ Program    │ Bounty   │ Score  │ Reason   │
 ├───┼────────────┼────────────┼──────────┼────────┼──────────┤
 │ 1 │ 0x4c9edd…  │ Ethena     │ $3,000K  │ 98/100 │ 🥇 Top bounty |
 │ 2 │ 0x8a9b7c…  │ Lido       │ $2,000K  │ 91/100 │ 🔥 Mirip    │
 │   │            │            │          │        │    Ethena    │
 │ 3 │ 0x3e4f5a…  │ Aave       │ $1,500K  │ 72/100 │ 🆕 Baru       │
 │ 4 │ 0x1b2c3d…  │ Euler      │ $250K    │ 25/100 │ 💤 Bounty kecil│
 └───┴────────────┴────────────┴──────────┴────────┴──────────┘
```

### Status Dashboard (Terminal)

```bash
vyper daemon status
```

```
┌──────────────────────────────────────────────────────────────┐
│  🐍 VYPER DAEMON — RUNNING                                   │
│  ──────────────────────────────────────────                   │
│                                                              │
│  Status:      ✅ Active (since 2026-05-17 14:00)             │
│  Uptime:      3h 24m                                         │
│  Next audit:  in 12 minutes                                  │
│  Next sync:   in 2h 15 minutes                               │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  STATS                                                │   │
│  │  Total audited:  7 contracts                          │   │
│  │  TP Found:       12 (3 critical, 5 high, 4 medium)   │   │
│  │  Exploits OK:    3                                    │   │
│  │  Reports gen:    7                                    │   │
│  │  Errors:         1 (Mythril timeout on 0xabc...)     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  QUEUE (Next 5)                                       │   │
│  │  ⏳ 0x4c9edd...  Ethena      🔴 Priority 98         │   │
│  │  ⏳ 0x8a9b7c...  Lido        🔥 Similar to Ethena   │   │
│  │  ⏳ 0x3e4f5a...  Aave        🆕 New program          │   │
│  │  ⏳ 0x1b2c3d...  Euler       💤 Low priority          │   │
│  │  ⏳ 0x5e6f7a...  Maker       💤 Low priority          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  🔔 Last notification: 12m ago — Critical bug in Ethena!    │
│                                                              │
│  Commands: vyper daemon [stop|logs|stats]                   │
└──────────────────────────────────────────────────────────────┘
```

### Desktop Notifications

Vyper kirim notifikasi native ke OS saat menemukan bug penting.

```python
# vyper/notifier.py

import platform
import subprocess

class DesktopNotifier:
    """Kirim notifikasi ke OS desktop"""
    
    def notify(self, title: str, message: str, urgency: str = "normal"):
        system = platform.system()
        
        if system == "Darwin":  # macOS
            subprocess.run([
                "osascript", "-e",
                f'display notification "{message}" with title "{title}"'
            ])
        elif system == "Linux":
            subprocess.run([
                "notify-send", 
                "-u", urgency,  # low, normal, critical
                title, message
            ])
        elif system == "Windows":
            try:
                from win10toast import ToastNotifier
                toaster = ToastNotifier()
                toaster.show_toast(title, message, duration=10)
            except ImportError:
                logger.warning("win10toast not installed — skip notification")

# Global helper
_notifier = DesktopNotifier()

def notify(title: str, message: str, urgency: str = "normal"):
    """Kirim notifikasi desktop + log"""
    _notifier.notify(title, message, urgency)
    logger.info(f"[NOTIFY] {title}: {message}")
```

### Dashboard — Daemon View

```
┌──────────────────────────────────────────────────────────────┐
│  🟢 DAEMON ACTIVE                                            │
│  ─────────────────────────────────────                       │
│  Running since: 2026-05-17 14:00                             │
│  Uptime: 3h 24m                                              │
│  Audits performed: 7                                         │
│  Critical found: 3 🔴                                        │
│  Next audit: ~12 minutes                                     │
│                                                              │
│  [⏸ Pause] [⏹ Stop] [📊 Live Logs]                         │
│                                                              │
│  ┌─LIVE LOG───────────────────────────────────────────────┐  │
│  │ 14:00  🚀 Daemon started                               │  │
│  │ 14:05  📡 Synced Immunefi — 234 programs               │  │
│  │ 14:10  🔍 Auditing Ethena/0x4c9edd...                  │  │
│  │ 14:25  🔴 CRITICAL FOUND! Reentrancy — $1.25M at risk │  │
│  │ 14:26  💥 Exploit successful — PoC generated           │  │
│  │ 14:30  📄 Report generated                             │  │
│  │ 14:35  🔍 Auditing Lido/0x8a9b7c...                    │  │
│  │ 14:50  🟠 HIGH FOUND! Oracle Manipulation              │  │
│  │ 15:00  🔄 Waiting for next cycle (60 min)              │  │
│  │ 16:00  🔍 Auditing Aave/0x3e4f5a...                    │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  [Auto-scroll ▼]  [Clear]                                    │
└──────────────────────────────────────────────────────────────┘
```

### Daemon Configuration

```json
// ~/.vyper/config.json — daemon section
{
  "daemon": {
    "enabled": true,
    "batch_size": 3,              // Kontrak per cycle
    "cycle_minutes": 60,          // Audit cycle tiap 1 jam
    "sync_interval_hours": 6,     // Sync Immunefi tiap 6 jam
    "notifications": {
      "desktop": true,            // Notifikasi OS native
      "on_critical_only": false,  // false = semua TP, true = critical aja
      "sound": true               // Bunyi saat critical ditemukan
    },
    "max_daily_audits": 20,       // Batas harian (biar tidak overload)
    "skip_unverified": true,      // Skip kontrak yang tidak terverifikasi
    "auto_exploit": true,         // Exploit otomatis untuk critical/high
    "retroactive_rerun": true,    // Re-run audit lama saat pattern baru
    "schedule": {
      "quiet_hours_start": null,  // "23:00" — tidak audit di jam ini
      "quiet_hours_end": null     // "07:00"
    }
  }
}
```

### Autonomous Flow — End to End

```
DAEMON LIFECYCLE (1 cycle = ~1 jam):
═══════════════════════════════════════════════════════════════

START
  │
  ▼
① HITUNG PRIORITAS (1 detik)
  ├── Load semua program Immunefi
  ├── Filter: unscanned + verified only
  ├── Hitung priority score (bounty + similarity + chain + freshness)
  └── Ambil top 3
       │
       ▼
② AUDIT KONTRAK #1 (10-30 menit)
  ├── Fetch source dari Etherscan
  ├── Slither scan
  ├── Mythril scan
  ├── Pattern matching
  ├── AI analysis → TP/FP/TN/FN
  ├── Exploit (jika TP critical/high & auto_exploit=true)
  ├── Generate report + PoC
  └── Notify dashboard
       │
       ▼
③ AUDIT KONTRAK #2 (10-30 menit)
  └── (sama seperti di atas)
       │
       ▼
④ AUDIT KONTRAK #3 (10-30 menit)
  └── (sama seperti di atas)
       │
       ▼
⑤ UPDATE METRICS (1 detik)
  ├── Update metrics.json
  ├── Update similarity clusters (jika ada TP baru)
  ├── Schedule retroactive re-run (jika ada pattern baru)
  └── Save daemon_stats.json
       │
       ▼
⑥ TIDUR (sisa waktu hingga 1 jam)
  └────▶ Kembali ke ①

 TOTAL: 3 kontrak per jam = ~72 kontrak per hari (24h non-stop)
 DENGAN CATATAN: max_daily_audits = 20 (default)
```

### Yang Terjadi Saat Critical TP Ditemukan

```
┌──────────────────────────────────────────────────────────────┐
│  🔴 CRITICAL BUG FOUND!                                      │
│  ─────────────────────────────                                │
│                                                              │
│  Program:  Ethena                                            │
│  Contract: USDe.sol (0x4c9edd...)                           │
│  Finding:  Reentrancy in withdraw()                         │
│  Severity: Critical                                          │
│  Value at risk: $1,250,000                                   │
│                                                              │
│  ⏱  Timestamp: 2026-05-17 14:25:30                         │
│                                                              │
│  AUTOMATIC RESPONSE:                                         │
│  ✅ AI Analysis — Confirmed TP (confidence: 95%)            │
│  ✅ Exploit Engine — Executing...                           │
│  💥 Exploit — SUCCESS (tx: 0xabcd...)                      │
│  📄 PoC Generated — ~/.vyper/audits/.../exploit/poc.sol    │
│  📄 Report Generated — immunefi.md ready for submission     │
│  🔔 Desktop Notification — Sent                              │
│  🌐 Dashboard — Updated via SSE                             │
│                                                              │
│  NEXT STEPS FOR YOU:                                         │
│  1. Buka dashboard: vyper ui                               │
│  2. Review finding di halaman Audit Detail                 │
│  3. Klik "Submit" → mark sebagai submitted ke Immunefi     │
│  4. Tunggu bounty 💰                                       │
└──────────────────────────────────────────────────────────────┘
```

### Perbandingan Mode: Manual vs Daemon

| Aspek | Manual (CLI) | Daemon (Autonomous) |
|-------|-------------|---------------------|
| User action | `vyper audit <addr>` | `vyper daemon start` — sekali |
| Kontrak target | User pilih sendiri | Auto-prioritized berdasarkan bounty + similarity |
| Frekuensi | Saat user ingat | 24/7, tiap jam |
| Notifikasi | Tidak ada | Desktop + dashboard real-time |
| Exploit | Manual jalan | Auto untuk critical/high |
| Report | Manual generate | Auto generate setiap audit |
| Learning | Manual feedback | Auto-improve dari hasil audit |
| Cocok untuk | Testing, eksplorasi | Production bug hunting |

---

## 20. Foundry `forge` Integration — Compile, Test, Verify

Kita clone repo, tapi gak pakai Foundry-nya. Padahal `forge` bisa compile, test, dan verify exploit.

### Kenapa Perlu

| Tanpa forge | Dengan forge |
|-------------|--------------|
| Slither parse file `.sol` langsung | `forge build` → AST sudah ready |
| Gak tahu contract compile atau error | Compile dulu → tahu dependency lengkap |
| Exploit gak bisa di-test | `forge test` → run PoC against fork |
| Gak bisa verifikasi fix | `forge test` → pastikan fix gak broken |

### Architecture

```python
# vyper/scanner/forge.py

class ForgeManager:
    """Manage Foundry project compilation & testing"""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.foundry_toml = repo_path / "foundry.toml"

    def is_foundry_project(self) -> bool:
        """Cek apakah repo ini Foundry project"""
        return self.foundry_toml.exists()

    def build(self) -> BuildResult:
        """forge build — kompilasi semua kontrak"""
        result = subprocess.run(
            ["forge", "build", "--via-ir"],
            cwd=self.repo_path,
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            # Coba tanpa --via-ir
            result = subprocess.run(
                ["forge", "build"],
                cwd=self.repo_path,
                capture_output=True, text=True, timeout=120
            )
        return BuildResult(
            success=result.returncode == 0,
            artifacts=self._find_artifacts(),
            errors=self._parse_errors(result.stderr)
        )

    def test_selector(self, signature: str) -> list[str]:
        """Cari test yang relevan dengan function signature"""
        test_files = list(self.repo_path.rglob("*.t.sol"))
        matches = []
        for tf in test_files:
            content = tf.read_text()
            if signature in content:
                matches.append(tf.name)
        return matches

    def run_tests(self, test_pattern: str = None) -> TestResult:
        """forge test — run specific or all tests"""
        cmd = ["forge", "test", "-vvv"]
        if test_pattern:
            cmd.extend(["--match-path", test_pattern])
        result = subprocess.run(
            cmd, cwd=self.repo_path,
            capture_output=True, text=True, timeout=300
        )
        return TestResult(
            passed=result.returncode == 0,
            output=result.stdout,
            failed_tests=self._parse_failures(result.stdout)
        )
```

### Integration dengan Pipeline

```python
# Dalam pipeline audit
class AuditPipeline:
    def run(self, address, chain, program=None):
        source = SourceDetector(chain).fetch(address, program)

        # 🔥 FORGE BUILD — compile dulu
        if source.metadata.has_foundry:
            forge = ForgeManager(source.metadata.local_path)
            build = forge.build()
            if not build.success:
                logger.warning(f"Forge build failed: {build.errors}")
                # Fallback: Slither langsung dari file

        # Forge Test — cari test coverage
        if source.metadata.has_tests:
            forge.run_tests()
            # Test failures = potential bugs?
```

### Pipeline Integration Flow

```
Source fetched (GitHub repo)
    │
    ▼
┌────────────────────────────┐
│ forge build                 │ ← Compile dulu
│   ├─ Success → artifacts    │
│   └─ Fail    → log + fallback
└────────┬───────────────────┘
         ▼
┌────────────────────────────┐
│ forge test                  │ ← Run existing tests
│   ├─ All pass → baseline   │
│   └─ Failures → potential  │
│       bugs?                 │
└────────┬───────────────────┘
         ▼
┌────────────────────────────┐
│ Slither/Mythril analysis   │ ← Menggunakan artifacts
└────────┬───────────────────┘
         ▼
┌────────────────────────────┐
│ forge test --fx           │ ← Verify exploit
│   (simulasi tx di fork)   │
└────────────────────────────┘
```

---

## 21. Compiler Version Management — `solc-select` Otomatis

Slither butuh `solc` versi yang tepat. Contract A 0.8.20, Contract B 0.6.12. Vyper harus manage ini otomatis.

### Masalah

```
Slither error: Solc 0.8.20 not installed
                ⬇
Install solc 0.8.20... (30 detik)
                ⬇
Slither error: Solc 0.6.12 not installed
                ⬇
... loop terus
```

### Solusi: SolcVersionManager

```python
# vyper/scanner/solc_manager.py

import json
import subprocess
from pathlib import Path
from packaging.version import Version

class SolcVersionManager:
    """Auto-detect & install compiler version"""

    SOLC_CACHE = Path("~/.vyper/solc").expanduser()

    def detect_version(self, source_path: Path) -> str:
        """Detect pragma solidity dari file"""
        for sol_file in source_path.rglob("*.sol"):
            content = sol_file.read_text()
            for line in content.splitlines():
                if "pragma solidity" in line:
                    return self._parse_pragma(line)
        return "0.8.20"  # Default fallback

    def _parse_pragma(self, pragma: str) -> str:
        """0.8.0 || >=0.8.0 <0.9.0 → 0.8.20"""
        import re
        versions = re.findall(r'(\d+\.\d+\.\d+)', pragma)
        if not versions:
            return "0.8.20"
        # Ambil versi tertinggi dalam range
        return str(max(Version(v) for v in versions))

    def ensure_installed(self, version: str):
        """Install solc via solc-select jika belum ada"""
        if not (self.SOLC_CACHE / f"solc-{version}").exists():
            subprocess.run(
                ["solc-select", "install", version],
                check=True, timeout=120
            )
            # Symlink juga boleh
            subprocess.run(["solc-select", "use", version], check=True)

    def set_for_slither(self, version: str):
        """Set SOLC_VERSION env var untuk Slither"""
        os.environ["SOLC_VERSION"] = version
        os.environ["SOLC_BINARY"] = str(
            self.SOLC_CACHE / f"solc-{version}" / "solc"
        )
```

### Integration

```python
# Pipeline — sebelum Slither
solc_mgr = SolcVersionManager()
version = solc_mgr.detect_version(source_path)
solc_mgr.ensure_installed(version)
solc_mgr.set_for_slither(version)
# Sekarang Slither bisa jalan
```

### Storage

```
~/.vyper/solc/
├── solc-0.8.20/
│   └── solc (binary)
├── solc-0.8.19/
│   └── solc
└── solc-0.6.12/
    └── solc
```

---

## 22. Dependency Resolution — OpenZeppelin, Solmate, Libs

Contract import `@openzeppelin/contracts/token/ERC20.sol`. Vyper harus resolve path ini.

### Dependency Detection

```python
# vyper/scanner/deps.py

class DependencyResolver:
    """Resolve Solidity imports — Foundry & Hardhat mode"""

    FOUNDRY_REMAPPINGS = {
        "@openzeppelin/": "lib/openzeppelin-contracts/",
        "@solmate/": "lib/solmate/",
        "@uniswap/": "lib/v3-periphery/",
        "@chainlink/": "lib/chainlink/",
        "@aave/": "lib/aave-v3-core/",
    }

    def resolve(self, repo_path: Path) -> ResolveResult:
        """Install dependencies + setup remappings"""
        if (repo_path / "foundry.toml").exists():
            return self._resolve_foundry(repo_path)
        elif (repo_path / "hardhat.config.ts").exists():
            return self._resolve_hardhat(repo_path)
        else:
            return self._resolve_manual(repo_path)

    def _resolve_foundry(self, repo_path: Path) -> ResolveResult:
        """forge install — install dependencies"""
        result = subprocess.run(
            ["forge", "install"],
            cwd=repo_path, capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            # Fallback: git submodule update --init --recursive
            subprocess.run(
                ["git", "submodule", "update", "--init", "--recursive"],
                cwd=repo_path, capture_output=True, text=True, timeout=300
            )
        return ResolveResult(
            success=result.returncode == 0,
            lib_path=repo_path / "lib",
            remappings=self._parse_remappings(repo_path)
        )

    def _resolve_hardhat(self, repo_path: Path) -> ResolveResult:
        """npm install untuk Hardhat project"""
        result = subprocess.run(
            ["npm", "install"],
            cwd=repo_path, capture_output=True, text=True, timeout=120
        )
        return ResolveResult(
            success=result.returncode == 0,
            node_modules=repo_path / "node_modules",
            remappings={}
        )

    def _parse_remappings(self, repo_path: Path) -> dict:
        """Baca remappings.txt atau dari foundry.toml"""
        remappings = {}
        remap_file = repo_path / "remappings.txt"
        if remap_file.exists():
            for line in remap_file.read_text().splitlines():
                if "=" in line:
                    key, val = line.split("=", 1)
                    remappings[key.strip()] = val.strip()
        return {**self.FOUNDRY_REMAPPINGS, **remappings}

    def create_slither_config(self, repo_path: Path) -> dict:
        """Generate slither-config.json untuk import mapping"""
        remappings = self._parse_remappings(repo_path)
        config = {
            "solc_remaps": [f"{k}={v}" for k, v in remappings.items()],
            "filter_paths": "lib|node_modules|test|script"
        }
        config_path = repo_path / "slither-config.json"
        config_path.write_text(json.dumps(config, indent=2))
        return config
```

### Pipeline Integration

```
Pipeline start
    │
    ▼
┌─────────────────────────────┐
│ Detektif dependency type     │
│ ├─ foundry.toml → forge install
│ ├─ hardhat.config → npm install
│ └─ manual → scan imports
└──────────┬──────────────────┘
           ▼
┌─────────────────────────────┐
│ Generate slither-config.json│ ← remappings + filter
└──────────┬──────────────────┘
           ▼
┌─────────────────────────────┐
│ Slither --config slither-   │
│ config.json                 │
└─────────────────────────────┘
```

---

## 23. Multi-Chain RPC Management

Kita punya RPC di config tapi kalau LlamaRPC down? Rate-limited?

### Architecture

```python
# vyper/config/rpc.py

from dataclasses import dataclass, field
from typing import Optional
import time
import random

@dataclass
class RPCProvider:
    url: str
    chain: str
    priority: int = 0        # Lower = tried first
    weight: int = 1           # For load balancing
    rate_limit_rpm: int = 60  # Requests per minute
    last_error: Optional[str] = None
    last_health_check: float = 0
    is_healthy: bool = True

class RPCRouter:
    """
    Multi-chain RPC with failover + rate limiting + health check.
    Auto-discover from popular free providers.
    """

    DEFAULT_PROVIDERS = {
        "ethereum": [
            "https://eth.llamarpc.com",
            "https://rpc.ankr.com/eth",
            "https://eth-mainnet.public.blastapi.io",
            "https://eth-mainnet.g.alchemy.com/v2/demo",
        ],
        "arbitrum": [
            "https://arb1.arbitrum.io/rpc",
            "https://arbitrum.llamarpc.com",
            "https://rpc.ankr.com/arbitrum",
        ],
        "optimism": [
            "https://opt.llamarpc.com",
            "https://mainnet.optimism.io",
            "https://rpc.ankr.com/optimism",
        ],
        "base": [
            "https://base.llamarpc.com",
            "https://mainnet.base.org",
            "https://base.rpc.subquery.network/public",
        ],
        "polygon": [
            "https://polygon.llamarpc.com",
            "https://polygon-rpc.com",
            "https://rpc.ankr.com/polygon",
        ],
        "bsc": [
            "https://binance.llamarpc.com",
            "https://bsc-dataseed.binance.org",
            "https://rpc.ankr.com/bsc",
        ],
    }

    def __init__(self):
        self.providers: dict[str, list[RPCProvider]] = {}
        self._load_or_discover()

    def _load_or_discover(self):
        """Load from config, fallback to defaults"""
        config = load_config()
        chains = config.get("rpc_endpoints", {})

        for chain, rpcs in chains.items():
            if isinstance(rpcs, str):
                rpcs = [rpcs]
            self.providers[chain] = [
                RPCProvider(url=url, chain=chain, priority=i)
                for i, url in enumerate(rpcs)
            ]

        # Tambah default untuk chain yang belum ada
        for chain, defaults in self.DEFAULT_PROVIDERS.items():
            if chain not in self.providers:
                self.providers[chain] = [
                    RPCProvider(url=url, chain=chain, priority=i)
                    for i, url in enumerate(defaults)
                ]

    def get_rpc(self, chain: str) -> str:
        """Get best available RPC untuk chain"""
        providers = self.providers.get(chain, [])
        healthy = [p for p in providers if p.is_healthy]

        if not healthy:
            # Semua down — coba health check ulang
            healthy = [p for p in providers if self._health_check(p)]
        if not healthy:
            raise RPCUnavailable(f"All RPCs down for {chain}")

        # Sort by priority, then random within same priority
        healthy.sort(key=lambda p: (p.priority, random.random()))
        return healthy[0].url

    def record_error(self, chain: str, url: str):
        """Catat error — auto-failover ke provider lain"""
        for p in self.providers.get(chain, []):
            if p.url == url:
                p.last_error = f"Error at {time.time()}"
                if p.priority < 100:
                    p.priority += 10  # Turunkan prioritas
                if p.rate_limit_rpm > 10:
                    p.rate_limit_rpm -= 5  # Kurangi rate limit

    def _health_check(self, provider: RPCProvider) -> bool:
        """Cek apakah RPC hidup — eth_blockNumber"""
        try:
            resp = requests.post(
                provider.url,
                json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
                timeout=5
            )
            provider.is_healthy = resp.status_code == 200
            provider.last_health_check = time.time()
            return provider.is_healthy
        except Exception:
            provider.is_healthy = False
            return False

    def auto_discover(self):
        """Coba discover RPC dari chainlist.org atau GitHub"""
        # Bisa fetch dari https://chainlist.org/chain/{id}/rpc
        pass
```

### Integration di Pipeline

```python
# Daripada langsung pakai RPC:
rpc_router = RPCRouter()
rpc_url = rpc_router.get_rpc("arbitrum")

# ... fork block with this RPC
anvil = AnvilManager()
container = anvil.start(rpc_url=rpc_url)

# Kalau error:
rpc_router.record_error("arbitrum", rpc_url)
# Next call will use different provider
```

### Rate Limiter

```python
class RPCRateLimiter:
    """Token bucket per provider"""

    def __init__(self):
        self.buckets: dict[str, TokenBucket] = {}

    def wait_if_needed(self, url: str, rpm: int = 60):
        if url not in self.buckets:
            self.buckets[url] = TokenBucket(rate=rpm / 60, capacity=rpm)
        bucket = self.buckets[url]
        if not bucket.consume():
            sleep_time = 60 / rpm
            time.sleep(sleep_time)
```

---

## 24. Slither Detector Tuning — Filter False Positive

Slither punya 50+ detector. Banyak false positive. Vyper harus konfigurasi detector per kontrak.

### Detector Configuration

```python
# vyper/scanner/slither_config.py

class SlitherConfig:
    """
    Slither detector tuning — disable noise, enable relevant.
    Berbeda untuk setiap jenis kontrak.
    """

    # Detector yang selalu dimatikan (noise)
    ALWAYS_DISABLE = [
        "pragma",              # "Different pragma" — noise
        "naming-convention",   # Gak relevan untuk security
        "solc-version",        # Versi compiler bukan bug
        "too-many-digits",     # Gaya kode
        "constable-states",    # Bisa constant — bukan security
        "unused-return",       # Kadang false positive
    ]

    # Detector yang dimatikan untuk kontrak lama (<0.8.0)
    LEGACY_DISABLE = [
        "assembly",            # Kontrak lama pake assembly
        "low-level-calls",     # Wajar di kontrak lama
        "block-timestamp",     # Dulu gak masalah
    ]

    # Detector yang WAJIB ON (security-critical)
    CRITICAL_ENABLE = [
        "reentrancy",
        "reentrancy-benign",
        "reentrancy-events",
        "tx-origin",
        "unchecked-transfer",
        "arbitrary-send",
        "controlled-delegatecall",
        "controlled-array-length",
        "incorrect-equality",
        "uninitialized-state",
        "uninitialized-storage",
        "write-after-write",
        "controlled-delegatecall",
    ]

    def generate_config(self, solc_version: str, repo_path: Path) -> dict:
        """Generate slither config JSON"""
        disable = list(self.ALWAYS_DISABLE)
        if Version(solc_version) < Version("0.8.0"):
            disable.extend(self.LEGACY_DISABLE)

        return {
            "detectors_to_exclude": disable,
            "detectors_to_include": self.CRITICAL_ENABLE,
            "filter_paths": "lib|node_modules|test|script|migrations",
            "solc_remaps": self._load_remappings(repo_path),
            "exclude_informational": True,
            "exclude_low": False,
            "exclude_medium": False,
            "exclude_high": False,
        }

    def generate_config_for_contract_type(self, contract_type: str) -> dict:
        """Config spesifik untuk jenis kontrak"""
        configs = {
            "amm": {"detectors_to_exclude": ["timestamp"]},
            "lending": {"detectors_to_include": ["flash-loan"]},
            "token": {"detectors_to_include": ["erc20-interface"]},
            "bridge": {"detectors_to_include": ["controlled-delegatecall"]},
        }
        return configs.get(contract_type, {})
```

### Integration

```python
# Pipeline
slither_config = SlitherConfig()
version = solc_mgr.detect_version(source_path)
config = slither_config.generate_config(version, repo_path)

# Save config
config_path = repo_path / "slither-config.json"
config_path.write_text(json.dumps(config, indent=2))

# Run Slither with config
subprocess.run([
    "slither", ".",
    "--config-file", str(config_path),
    "--json", str(result_path)
], cwd=repo_path)
```

---

## 25. Notifications — Discord, Telegram, Email

Daemon 24/7 nemu critical jam 3 pagi. Desktop notification gak cukup.

### Architecture

```python
# vyper/notify/__init__.py

from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class Notification:
    type: str           # "critical", "high", "medium", "info", "error"
    title: str
    message: str
    finding_id: str = None
    program: str = None
    bounty: int = 0
    poc_path: str = None

class Notifier(ABC):
    @abstractmethod
    def send(self, notification: Notification):
        pass

class NotifierManager:
    """
    Send notifications to all configured channels.
    Support multi-channel: Discord + Telegram + Email + Desktop + Webhook.
    """

    def __init__(self):
        self.channels: list[Notifier] = []
        self._load_config()

    def _load_config(self):
        config = load_config()
        for channel_config in config.get("notifications", []):
            channel_type = channel_config.get("type")
            if channel_type == "discord":
                self.channels.append(DiscordNotifier(channel_config["webhook_url"]))
            elif channel_type == "telegram":
                self.channels.append(TelegramNotifier(
                    channel_config["bot_token"],
                    channel_config["chat_id"]
                ))
            elif channel_type == "email":
                self.channels.append(EmailNotifier(
                    channel_config["smtp_server"],
                    channel_config["smtp_port"],
                    channel_config["from"],
                    channel_config["to"]
                ))
            elif channel_type == "desktop":
                self.channels.append(DesktopNotifier())

    def notify(self, notification: Notification):
        """Send to all channels — each channel independently"""
        for channel in self.channels:
            try:
                channel.send(notification)
            except Exception as e:
                logger.error(f"Notification failed ({channel.__class__.__name__}): {e}")
```

### Channel Implementations

```python
# vyper/notify/discord.py

class DiscordNotifier(Notifier):
    """Send to Discord channel via webhook"""

    SEVERITY_COLORS = {
        "critical": 0xFF0000,
        "high": 0xFF6600,
        "medium": 0xFFCC00,
        "low": 0x66CC66,
        "info": 0x3399FF,
    }

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, notification: Notification):
        embed = {
            "title": f"🚨 {notification.title}",
            "description": notification.message[:2000],
            "color": self.SEVERITY_COLORS.get(notification.type, 0x999999),
            "fields": [
                {"name": "Program", "value": notification.program or "N/A", "inline": True},
                {"name": "Bounty", "value": f"${notification.bounty:,}", "inline": True},
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        if notification.poc_path:
            embed["fields"].append({
                "name": "PoC", "value": f"[View PoC](file://{notification.poc_path})"
            })
        requests.post(self.webhook_url, json={"embeds": [embed]})

# vyper/notify/telegram.py

class TelegramNotifier(Notifier):
    """Send to Telegram via bot API"""

    def __init__(self, bot_token: str, chat_id: str):
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.chat_id = chat_id

    def send(self, notification: Notification):
        text = (
            f"🚨 *{notification.title}*\n"
            f"{notification.message}\n\n"
            f"📍 Program: {notification.program}\n"
            f"💰 Bounty: ${notification.bounty:,}\n"
            f"🔍 Finding: [{notification.finding_id}](http://localhost:3000/findings/{notification.finding_id})"
        )
        requests.post(f"{self.api_url}/sendMessage", json={
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        })

# vyper/notify/desktop.py

class DesktopNotifier(Notifier):
    """OS-native desktop notification"""

    def send(self, notification: Notification):
        if sys.platform == "darwin":
            subprocess.run([
                "osascript", "-e",
                f'display notification "{notification.message}" with title "{notification.title}"'
            ])
        elif sys.platform == "linux":
            subprocess.run(["notify-send", notification.title, notification.message])
        elif sys.platform == "win32":
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(notification.title, notification.message, duration=10)
```

### Config

```json
{
  "notifications": [
    {
      "type": "discord",
      "webhook_url": "https://discord.com/api/webhooks/..."
    },
    {
      "type": "telegram",
      "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
      "chat_id": "-1001234567890"
    },
    {
      "type": "desktop",
      "enabled": true
    }
  ],
  "notify_on": ["critical", "high", "daemon_error"]
}
```

### Daemon Integration

```python
# Dalam daemon cycle
class VyperDaemon:
    async def run_cycle(self):
        findings = self.audit(contract)
        for f in findings.tp:
            if f.severity in ("critical", "high"):
                self.notifier.notify(Notification(
                    type=f.severity,
                    title=f"🔴 Critical TP: {f.title} — {f.program}",
                    message=f"$1.25M at risk! PoC: {f.poc_path}",
                    bounty=program.max_bounty
                ))
```

---

## 26. Immunefi API Integration — Auto Submit Report

Report udah dibuat. Tinggal klik submit.

### Immunefi API

Immunefi tidak punya public API untuk submission (semua manual via dashboard). Tapi kita bisa semi-automasi:

1. **Generate report → buka browser langsung ke halaman submit**
2. **Copy report ke clipboard → paste di Immunefi**
3. **Crawl Immunefi dashboard** (jika memungkinkan)

```python
# vyper/reporter/submit.py

class ImmunefiSubmitter:
    """
    Semi-automated Immunefi submission.
    Immunefi doesn't have public API — we do browser-assisted submit.
    """

    def prepare_submit(self, finding: Finding) -> SubmitPackage:
        """Siapkan semua yang dibutuhkan untuk submit"""
        return SubmitPackage(
            # Report content
            title=f"Critical: {finding.title} in {finding.program}",
            severity=finding.severity.upper(),
            description=self._format_immunefi_description(finding),
            impact=finding.impact_description,
            poc=finding.poc_content,

            # Metadata
            program_slug=finding.program_slug,
            contract_address=finding.address,
            asset_type="smart_contract",

            # File attachments
            attachments=[finding.poc_path] if finding.poc_path else [],
        )

    def _format_immunefi_description(self, finding: Finding) -> str:
        """Format sesuai template Immunefi"""
        return f"""
## Vulnerability Description

{finding.ai_reasoning or finding.description}

## Affected Contract

- Address: {finding.address}
- Chain: {finding.chain}
- File: {finding.source_file}

## Technical Details

{finding.technical_detail}

## References

- {finding.swc_link}
- {finding.cwe_link}
"""

    def open_submit_page(self, package: SubmitPackage):
        """Buka halaman submit Immunefi di browser"""
        # Copy report ke clipboard
        pyperclip.copy(package.to_clipboard_text())
        print("✅ Report copied to clipboard")

        # Buka halaman submit
        submit_url = f"https://immunefi.com/bounty/{package.program_slug}/submit/"
        webbrowser.open(submit_url)
        print(f"🌐 Browser opened: {submit_url}")
        print("📋 Paste report (Ctrl+V) and submit manually")

    def save_draft(self, package: SubmitPackage):
        """Save draft untuk submit manual nanti"""
        draft_path = Path(f"~/.vyper/submissions/draft_{package.finding_id}.json")
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(json.dumps({
            "status": "draft",
            "created_at": datetime.now().isoformat(),
            "program": package.program_slug,
            "title": package.title,
            "severity": package.severity,
            "poc_path": package.poc_path,
            "clipboard_ready": True,
        }, indent=2))
        return draft_path
```

### CLI Command

```bash
vyper submit F-001                    # Siapkan + copy ke clipboard + buka browser
vyper submit F-001 --auto             # Siapkan + langsung submit (jika API ada)
vyper submit --drafts                  # Lihat draft yang belum di-submit
vyper submit --status F-001            # Cek status submission
```

### Submission Status Tracker

```python
class SubmissionTracker:
    """Track status setiap submission"""

    STATUSES = ["draft", "prepared", "submitted", "in_review", "accepted", "rejected", "paid"]

    def update_status(self, finding_id: str, status: str, note: str = ""):
        """Update status submission"""
        tracker = self._load()
        tracker[finding_id] = {
            "status": status,
            "updated_at": datetime.now().isoformat(),
            "note": note,
        }
        self._save(tracker)

    def earnings_report(self) -> str:
        """Total bounty earned"""
        tracker = self._load()
        paid = sum(
            f["bounty"] for f in tracker.values()
            if f.get("status") == "paid"
        )
        return f"💰 Total earned: ${paid:,}"
```

---

## 27. Git History Analysis — Git Blame untuk Risk Scoring

Kita clone repo — tinggal `git blame`. Contract yang sering diubah = lebih berisiko.

### Implementasi

```python
# vyper/analysis/git_history.py

from datetime import datetime, timedelta
from collections import Counter

class GitHistoryAnalyzer:
    """
    Analyze git history for risk indicators.
    Digunakan untuk boost priority score.
    """

    def __init__(self, repo_path: Path):
        self.repo = repo_path

    def analyze_contract(self, contract_file: str) -> dict:
        """Analyze single contract file"""
        return {
            "commit_count": self._commit_count(contract_file),
            "unique_authors": self._unique_authors(contract_file),
            "last_modified_days": self._days_since_last_edit(contract_file),
            "recent_changes_30d": self._changes_in_days(contract_file, 30),
            "security_fixes": self._security_related_commits(contract_file),
            "has_fix_commits": self._detect_fix_commits(contract_file),
            "risk_score": 0,  # Calculated below
        }

    def calculate_risk_score(self, analysis: dict) -> float:
        """0-100 risk score based on git history"""
        score = 0

        # Many commits = complex contract
        if analysis["commit_count"] > 50:
            score += 20
        elif analysis["commit_count"] > 20:
            score += 10

        # Many authors = multiple devs, coordination complexity
        if analysis["unique_authors"] > 5:
            score += 15
        elif analysis["unique_authors"] > 3:
            score += 8

        # Recently modified = active development (bugs being introduced)
        if analysis["last_modified_days"] < 7:
            score += 25
        elif analysis["last_modified_days"] < 30:
            score += 15

        # Many recent changes = churn
        if analysis["recent_changes_30d"] > 10:
            score += 20
        elif analysis["recent_changes_30d"] > 5:
            score += 10

        # Security fix commits = previous bugs found
        if analysis["security_fixes"] > 0:
            score += 10  # Might have remaining bugs

        return min(score, 100)

    def _commit_count(self, file_path: str) -> int:
        result = subprocess.run(
            ["git", "log", "--oneline", "--follow", file_path],
            cwd=self.repo, capture_output=True, text=True
        )
        return len(result.stdout.splitlines())

    def _unique_authors(self, file_path: str) -> int:
        result = subprocess.run(
            ["git", "shortlog", "-sne", "--", file_path],
            cwd=self.repo, capture_output=True, text=True
        )
        return len(result.stdout.splitlines())

    def _days_since_last_edit(self, file_path: str) -> int:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct", file_path],
            cwd=self.repo, capture_output=True, text=True
        )
        if result.stdout.strip():
            last_ts = int(result.stdout.strip())
            return (datetime.now() - datetime.fromtimestamp(last_ts)).days
        return 999

    def _changes_in_days(self, file_path: str, days: int) -> int:
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = subprocess.run(
            ["git", "log", "--oneline", "--after", since, "--follow", file_path],
            cwd=self.repo, capture_output=True, text=True
        )
        return len(result.stdout.splitlines())

    def _security_related_commits(self, file_path: str) -> int:
        """Cari commit yang mention security/fix/audit"""
        keywords = ["fix", "security", "audit", "bug", "patch", "vulnerability", "reentrancy"]
        count = 0
        for kw in keywords:
            result = subprocess.run(
                ["git", "log", "--oneline", "--grep", kw, "--follow", file_path],
                cwd=self.repo, capture_output=True, text=True
            )
            count += len(result.stdout.splitlines())
        return count

    def _detect_fix_commits(self, file_path: str) -> bool:
        """Detect if commit message mentions 'fix security' or similar"""
        result = subprocess.run(
            ["git", "log", "--oneline", "-20", "--follow", file_path],
            cwd=self.repo, capture_output=True, text=True
        )
        fix_patterns = ["fix", "patch", "audit", "review"]
        return any(p in result.stdout.lower() for p in fix_patterns)
```

### Integration

```python
# Pipeline — setelah source fetched
if source.metadata.is_full_repo:
    git_analyzer = GitHistoryAnalyzer(source.metadata.local_path)
    for contract_file in source.files:
        analysis = git_analyzer.analyze_contract(contract_file)
        risk_score = git_analyzer.calculate_risk_score(analysis)

        # Boost priority untuk contract berisiko tinggi
        if risk_score > 50:
            finding_priority.boost(risk_score * 0.1)
            logger.info(f"Git risk score {risk_score}: {contract_file}")
```

---

## 28. Test File Intelligence — Ekstrak Insight dari Test Files

Test file adalah goldmine. `test_reentrancy.t.sol` → developer tahu ada risiko reentrancy.

### Implementasi

```python
# vyper/analysis/test_intel.py

import re

class TestIntelligence:
    """Extract vulnerability hints from test files"""

    # Mapping: test name pattern → potential vulnerability
    TEST_PATTERNS = {
        "reentrancy": "reentrancy",
        "re-entrancy": "reentrancy",
        "flash.loan": "flash_loan",
        "oracle": "oracle_manipulation",
        "manipul": "oracle_manipulation",
        "access.control": "access_control",
        "permission": "access_control",
        "admin": "access_control",
        "front.run": "frontrunning",
        "sandwich": "frontrunning",
        "approve": "permit_frontrunning",
        "donation": "donation_attack",
        "inflation": "erc4626_inflation",
        "share.price": "erc4626_inflation",
        "underflow": "arithmetic",
        "overflow": "arithmetic",
        "precision": "precision_loss",
        "rounding": "precision_loss",
        "scenario": "complex_scenario",
        "fuzz": "fuzzing_target",
        "invariant": "invariant_test",
    }

    def analyze_tests(self, repo_path: Path) -> dict:
        """Analyze all test files for vulnerability hints"""
        test_files = []
        for pattern in ["**/*.t.sol", "**/*Test.sol", "**/test/**/*.sol"]:
            test_files.extend(repo_path.glob(pattern))

        results = {
            "vulnerability_hints": [],
            "test_coverage": self._estimate_coverage(test_files),
            "high_risk_functions": [],
            "test_quality_score": 0,
        }

        for tf in test_files:
            content = tf.read_text()
            hints = self._scan_test_file(tf.name, content)
            results["vulnerability_hints"].extend(hints)

            # Extract function names being tested
            functions = self._extract_tested_functions(content)
            results["high_risk_functions"].extend(functions)

        # Aggregate
        hint_count = len(results["vulnerability_hints"])
        coverage = results["test_coverage"]

        # More hints = more awareness = complex code
        # Low coverage = more risk
        results["test_quality_score"] = self._calculate_score(hint_count, coverage)

        return results

    def _scan_test_file(self, filename: str, content: str) -> list[dict]:
        """Scan test file untuk vulnerability hints"""
        hints = []

        # Check filename
        for pattern, vuln in self.TEST_PATTERNS.items():
            if re.search(pattern, filename, re.I):
                hints.append({
                    "type": vuln,
                    "source": "filename",
                    "file": filename,
                    "confidence": 0.9  # High — filename explicit
                })

        # Check function names
        funcs = re.findall(r'function\s+(test\w+)\s*\(', content)
        for func in funcs:
            for pattern, vuln in self.TEST_PATTERNS.items():
                if re.search(pattern, func, re.I):
                    hints.append({
                        "type": vuln,
                        "source": "function_name",
                        "file": filename,
                        "function": func,
                        "confidence": 0.8
                    })

        # Check comments
        comments = re.findall(r'//(.+)', content)
        for comment in comments:
            for pattern, vuln in self.TEST_PATTERNS.items():
                if re.search(pattern, comment, re.I):
                    hints.append({
                        "type": vuln,
                        "source": "comment",
                        "file": filename,
                        "comment": comment.strip(),
                        "confidence": 0.5
                    })

        return hints

    def _estimate_coverage(self, test_files: list[Path]) -> float:
        """
        Estimate test coverage (0-1).
        Proxy: lines of test / 100. If >100 lines per test, decent coverage.
        """
        if not test_files:
            return 0.0
        total_lines = sum(
            len(f.read_text().splitlines()) for f in test_files
        )
        coverage = min(total_lines / 500, 1.0)
        return coverage

    def _extract_tested_functions(self, content: str) -> list[str]:
        """Extract function names from test setups & calls"""
        funcs = set()
        # Match: vault.withdraw(...), token.transfer(...)
        calls = re.findall(r'(\w+)\.(\w+)\s*\(', content)
        for contract, func in calls:
            if func not in ("assertEq", "assertTrue", "vm", "console"):
                funcs.add(f"{contract}.{func}")
        return list(funcs)
```

### Integration

```python
# Pipeline — setelah source fetched
if source.metadata.has_tests:
    test_intel = TestIntelligence()
    insights = test_intel.analyze_tests(source.metadata.local_path)

    # Add vulnerability hints as findings
    for hint in insights["vulnerability_hints"]:
        if hint["confidence"] > 0.7:
            pipeline.add_prefinding(
                type=hint["type"],
                confidence=hint["confidence"],
                source="test_intelligence",
                note=f"Test file {hint['file']} mentions {hint['type']}"
            )

    # Low coverage = boost priority
    if insights["test_coverage"] < 0.3:
        priority_boost += 10  # Kurang test = lebih mungkin ada bug
```

---

## 29. Self-Update — Vyper Update Otomatis

Pola vulnerabilitas baru ditemukan tiap minggu. Vyper harus bisa update pattern + dirinya sendiri.

### Update Sources

```python
# vyper/update.py

class VyperUpdater:
    """
    Self-update system:
    1. Update vulnerability patterns (JSON)
    2. Update core skills (markdown)
    3. Update Vyper itself (pip)
    """

    PATTERN_REPO = "https://raw.githubusercontent.com/vyper-hunter/patterns/main"
    SKILL_REPO = "https://raw.githubusercontent.com/vyper-hunter/skills/main"

    def check_updates(self) -> UpdateStatus:
        """Cek apakah ada update tersedia"""
        status = UpdateStatus()

        # Pattern version
        local_ver = self._local_pattern_version()
        remote_ver = self._fetch_version(f"{self.PATTERN_REPO}/VERSION")
        status.pattern_update = remote_ver > local_ver
        status.pattern_old_ver = local_ver
        status.pattern_new_ver = remote_ver

        # Vyper version
        try:
            result = subprocess.run(
                ["pip", "index", "versions", "vyper"],
                capture_output=True, text=True
            )
            # Parse latest version
            if result.returncode == 0:
                status.vyper_update = "vyper" in result.stdout
        except Exception:
            pass

        return status

    def update_patterns(self):
        """Update vulnerability patterns"""
        patterns_url = f"{self.PATTERN_REPO}/patterns.json"
        resp = requests.get(patterns_url)
        if resp.status_code == 200:
            patterns = resp.json()
            # Merge dengan local patterns
            local = self._load_local_patterns()
            local["patterns"].extend(patterns["patterns"])
            # Deduplicate by ID
            seen = set()
            unique = []
            for p in local["patterns"]:
                if p["id"] not in seen:
                    seen.add(p["id"])
                    unique.append(p)
            local["patterns"] = unique
            local["version"] = patterns["version"]
            local["updated_at"] = datetime.now().isoformat()
            self._save_local_patterns(local)
            logger.info(f"Updated patterns: +{len(patterns['patterns'])} new")

    def update_skills(self):
        """Update core skills dari repo"""
        skill_list = ["reentrancy-detector", "oracle-manipulation", "access-control"]
        for skill in skill_list:
            url = f"{self.SKILL_REPO}/{skill}.md"
            resp = requests.get(url)
            if resp.status_code == 200:
                skill_path = Path(f"~/.vyper/skills/{skill}.md").expanduser()
                skill_path.write_text(resp.text)
                logger.info(f"Updated skill: {skill}")

    def update_vyper(self):
        """pip install --upgrade vyper"""
        logger.info("Updating Vyper...")
        result = subprocess.run(
            ["pip", "install", "--upgrade", "vyper"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            logger.info("✅ Vyper updated. Restart daemon.")
            return True
        logger.error(f"Update failed: {result.stderr}")
        return False
```

### CLI

```bash
vyper update check          # Check update
vyper update patterns       # Update vulnerability patterns only
vyper update skills         # Update analysis skills only
vyper update all            # Update everything
```

### Auto-Update di Daemon

```python
# Daemon — daily update check
class VyperDaemon:
    async def daily_maintenance(self):
        """Jadwal: setiap hari jam 03:00"""
        updater = VyperUpdater()
        status = updater.check_updates()
        if status.pattern_update:
            updater.update_patterns()
            logger.info("🔄 Patterns updated — scheduling retroactive re-runs")
            self.schedule_rerun_for_all_contracts()
```

### Storage

```
~/.vyper/update/
├── VERSION                # Versi lokal pattern
├── changelog.md           # Riwayat perubahan
└── last_check.json        # Kapan terakhir cek update
```

---

## 30. Backup & Restore — `~/.vyper/` Aman

`~/.vyper/` berisi bulanan learning data. Kalau laptop rusak, ilang semua.

### Implementasi

```python
# vyper/backup.py

import tarfile
import shutil
from datetime import datetime

class BackupManager:
    """Backup & restore ~/.vyper/"""

    BACKUP_DIR = Path("~/.vyper/backups").expanduser()

    def create_backup(self, name: str = None) -> Path:
        """Create compressed backup"""
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = name or f"vyper_backup_{timestamp}"
        backup_path = self.BACKUP_DIR / f"{name}.tar.gz"

        vyper_dir = Path("~/.vyper").expanduser()

        # Exclude large dirs like repos/ and solc/
        exclude_dirs = {"repos", "solc", "contracts", "backups"}

        with tarfile.open(backup_path, "w:gz") as tar:
            for item in vyper_dir.iterdir():
                if item.name in exclude_dirs:
                    continue
                tar.add(item, arcname=item.name)

        return backup_path

    def list_backups(self) -> list[dict]:
        """List all available backups"""
        backups = []
        for f in sorted(self.BACKUP_DIR.glob("*.tar.gz"), reverse=True):
            size_mb = f.stat().st_size / (1024 * 1024)
            created = datetime.fromtimestamp(f.stat().st_mtime)
            backups.append({
                "name": f.stem,
                "path": str(f),
                "size_mb": round(size_mb, 2),
                "created": created.isoformat(),
            })
        return backups

    def restore_backup(self, name: str):
        """Restore from backup"""
        backup_path = self.BACKUP_DIR / f"{name}.tar.gz"
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {name}")

        vyper_dir = Path("~/.vyper").expanduser()

        # Backup current state first
        pre_restore = self.create_backup("pre_restore")

        # Clear current (keep repos, solc, contracts)
        for item in vyper_dir.iterdir():
            if item.name not in {"repos", "solc", "contracts", "backups"}:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

        # Extract backup
        with tarfile.open(backup_path, "r:gz") as tar:
            tar.extractall(vyper_dir)

        logger.info(f"✅ Restored from {name}. Old state saved to {pre_restore.name}")

    def auto_backup(self):
        """Auto backup — jalan tiap minggu"""
        backups = self.list_backups()
        if not backups:
            self.create_backup("weekly_auto")
            return

        last_backup = datetime.fromisoformat(backups[0]["created"])
        days_since = (datetime.now() - last_backup).days

        if days_since >= 7:
            path = self.create_backup(f"auto_{datetime.now().strftime('%Y%m%d')}")
            logger.info(f"Auto backup created: {path}")
```

### CLI

```bash
vyper backup                    # Create backup
vyper backup --name pre-update  # Named backup
vyper backup list               # List backups
vyper backup restore weekly     # Restore
vyper backup auto               # Auto backup (daemon mode)
```

### Daemon Auto-Backup

```python
# Auto backup setiap minggu
class VyperDaemon:
    async def weekly_maintenance(self):
        """Jadwal: setiap Minggu jam 04:00"""
        backup = BackupManager()
        backup.auto_backup()
```

---

## 31. Resource Governor — Jangan Habiskan CPU/Laptop

Slither/Mythril bisa makan 100% CPU. Kalau daemon jalan lama, laptop jadi lemot.

### Implementasi

```python
# vyper/daemon/resource_governor.py

import psutil
import time

class ResourceGovernor:
    """
    Throttle resource usage when laptop is in use.
    Pause heavy analysis when battery low or CPU high.
    """

    def __init__(self):
        self.config = self._load_config()

    def should_throttle(self) -> bool:
        """Cek apakah perlu throttle — based on multiple signals"""

        # Signal 1: CPU usage > 80%
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 80:
            return True

        # Signal 2: Memory > 80%
        mem = psutil.virtual_memory()
        if mem.percent > 80:
            return True

        # Signal 3: Battery low (<20%) and not charging
        battery = psutil.sensors_battery()
        if battery and battery.percent < 20 and not battery.power_plugged:
            return True

        # Signal 4: User is active (keyboard/mouse)
        if self._user_active():
            return True

        return False

    def _user_active(self) -> bool:
        """Cek apakah user sedang pakai laptop"""
        # Linux/Mac: cek idle time
        if sys.platform in ("darwin", "linux"):
            try:
                result = subprocess.run(
                    ["who", "-b"], capture_output=True, text=True
                )
                # Simple heuristic
                return psutil.cpu_percent() > 30
            except Exception:
                return False
        return False

    def get_safe_concurrency(self) -> int:
        """Dynamic concurrency — turunkan kalau laptop sibuk"""
        if self.should_throttle():
            return 1  # One at a time, slow mode
        return self.config.get("max_concurrent", 2)

    def get_analysis_mode(self) -> str:
        """'full', 'quick', or 'silent' — tergantung resource"""
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory().percent

        if cpu > 70 or mem > 80:
            return "quick"     # Skip fuzzing, only Slither
        if cpu > 50 or mem > 60:
            return "normal"    # Slither + Mythril, no fuzz
        return "full"          # Slither + Mythril + Echidna
```

### Detection modes by resource availability

```python
# Pipeline — adaptif
class AuditPipeline:
    def run(self, address, chain, program=None):
        governor = ResourceGovernor()
        mode = governor.get_analysis_mode()

        if mode == "quick":
            # Only Slither, no exploit
            findings = scanner.run_slither_only()
        elif mode == "normal":
            # Slither + Mythril
            findings = scanner.run_all(exclude=["echidna"])
        else:
            # Full analysis
            findings = scanner.run_all()

        # Saat laptop dipakai, throttle
        if governor.should_throttle():
            self.pause(60)  # Istirahat 1 menit
```

### Daemon Schedule

```
Jam 08:00-18:00 → Quick mode (user aktif)
Jam 18:00-23:00 → Normal mode
Jam 23:00-08:00 → Full mode (laptop nganggur)
```

---

## 32. Webhook System — Integrasi dengan Tool Lain

Webhook = Vyper bisa integrasi dengan apa aja.

### Implementasi

```python
# vyper/notify/webhook.py

import hmac
import hashlib
from fastapi import APIRouter, Request

class WebhookManager:
    """
    Webhook system — kirim event ke URL eksternal.
    Support signature verification + retry.
    """

    def __init__(self):
        self.webhooks = self._load_config()

    def _load_config(self) -> list[dict]:
        config = load_config()
        return config.get("webhooks", [])

    def dispatch(self, event_type: str, payload: dict):
        """Kirim event ke semua webhook terdaftar"""
        for wh in self.webhooks:
            if event_type in wh.get("events", ["*"]):
                self._send(wh, event_type, payload)

    def _send(self, webhook: dict, event_type: str, payload: dict):
        """POST ke webhook URL dengan signature"""
        body = json.dumps({
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload,
        }, indent=2)

        headers = {"Content-Type": "application/json"}

        # Signature untuk verifikasi
        secret = webhook.get("secret")
        if secret:
            signature = hmac.new(
                secret.encode(), body.encode(), hashlib.sha256
            ).hexdigest()
            headers["X-Vyper-Signature"] = signature
            headers["X-Vyper-Event"] = event_type

        # Send with retry
        for attempt in range(3):
            try:
                resp = requests.post(
                    webhook["url"],
                    data=body,
                    headers=headers,
                    timeout=10
                )
                if resp.status_code < 300:
                    return
                logger.warning(f"Webhook attempt {attempt+1} failed: {resp.status_code}")
            except Exception as e:
                logger.warning(f"Webhook attempt {attempt+1} error: {e}")
            time.sleep(2 ** attempt)  # Exponential backoff

    # ============ Events ============

    CRITICAL_FOUND = "finding.critical"
    HIGH_FOUND = "finding.high"
    AUDIT_COMPLETE = "audit.complete"
    DAEMON_STARTED = "daemon.started"
    DAEMON_STOPPED = "daemon.stopped"
    DAEMON_ERROR = "daemon.error"
    UPDATE_AVAILABLE = "update.available"
```

### Event Payloads

```python
# finding.critical — payload
{
  "event": "finding.critical",
  "data": {
    "id": "F-001",
    "title": "Reentrancy in withdraw()",
    "program": "Ethena",
    "contract": "0x4c9edd...",
    "severity": "critical",
    "value_at_risk": 1250000,
    "poc_path": "/home/user/.vyper/audits/.../poc.sol",
    "dashboard_url": "http://localhost:3000/findings/F-001"
  }
}
```

### Dashboard Webhook Config Page

Di halaman Settings webhook:

```
┌──────────────────────────────────────────────┐
│  🔗 WEBHOOKS                                 │
│                                               │
│  ┌──────────────────────────────────────────┐│
│  │ URL: https://hooks.slack.com/...        ││
│  │ Events: [x] Critical [x] High [ ] Info  ││
│  │ Secret: ********                        ││
│  │ Status: ✅ Last delivery: 2m ago       ││
│  │                               [Delete]   ││
│  └──────────────────────────────────────────┘│
│                                               │
│  ┌──────────────────────────────────────────┐│
│  │ URL: https://pagerduty.com/hooks/...    ││
│  │ Events: [x] Critical [ ] High [ ] Info  ││
│  │ Secret: ********                        ││
│  │ Status: ✅ Last delivery: 5h ago        ││
│  │                               [Delete]   ││
│  └──────────────────────────────────────────┘│
│                                               │
│  [+ Add Webhook]                              │
└──────────────────────────────────────────────┘
```

---

## 33. CLI Auto-Completion — Shell Completion

`vyper sc<TAB>` → scan. Vyper harus support auto-completion.

### Implementation

```python
# vyper/cli.py (tambahan)

import click

class VyperCLI:
    """CLI with auto-completion support"""

    @classmethod
    def install_completion(cls, shell: str = "auto"):
        """Install shell completion"""
        shell = shell or "auto"
        if shell == "auto":
            shell = cls._detect_shell()

        if shell == "bash":
            path = Path("~/.bashrc").expanduser()
            script = cls._bash_completion()
        elif shell == "zsh":
            path = Path("~/.zshrc").expanduser()
            script = cls._zsh_completion()
        elif shell == "powershell":
            path = Path("~/.config/powershell/Microsoft.PowerShell_profile.ps1").expanduser()
            script = cls._powershell_completion()
        else:
            click.echo(f"Unknown shell: {shell}")
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(f"\n# Vyper completion\n{script}\n")

        click.echo(f"✅ Completion installed for {shell}")
        click.echo(f"   Restart your terminal or run: source {path}")

    @classmethod
    def _detect_shell(cls) -> str:
        """Auto-detect current shell"""
        shell = os.environ.get("SHELL", "")
        if "zsh" in shell:
            return "zsh"
        elif "bash" in shell:
            return "bash"
        elif "pwsh" in shell or "powershell" in shell:
            return "powershell"
        return "bash"

    @classmethod
    def _bash_completion(cls) -> str:
        return """
_vyper_completion() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    opts="scan audit batch sync list dashboard daemon init update backup submit config"

    case "${prev}" in
        scan|audit)
            # Suggest contract addresses from known contracts
            local contracts=$(vyper list --addresses 2>/dev/null)
            COMPREPLY=($(compgen -W "${contracts}" -- ${cur}))
            return 0
            ;;
        daemon)
            COMPREPLY=($(compgen -W "start stop status logs stats" -- ${cur}))
            return 0
            ;;
        backup)
            COMPREPLY=($(compgen -W "list restore auto" -- ${cur}))
            return 0
            ;;
        update)
            COMPREPLY=($(compgen -W "check patterns skills all" -- ${cur}))
            return 0
            ;;
        *)
            COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
            return 0
            ;;
    esac
}
complete -F _vyper_completion vyper
"""

    @classmethod
    def _zsh_completion(cls) -> str:
        return """
#compdef vyper
_vyper() {
    local line
    _arguments -C \
        "1: :(scan audit batch sync list dashboard daemon init update backup submit config)" \
        "*::arg:->args"
    case $line[1] in
        daemon)
            _arguments "2: :(start stop status logs stats)"
            ;;
        backup)
            _arguments "2: :(list restore auto)"
            ;;
        update)
            _arguments "2: :(check patterns skills all)"
            ;;
    esac
}
compdef _vyper vyper
"""
```

### CLI

```bash
vyper install-completion           # Auto-detect + install
vyper install-completion --bash    # Force Bash
vyper install-completion --zsh     # Force Zsh
vyper install-completion --powershell  # PowerShell
```

---

## 34. RPC Rate Limiter — Jangan Kena Block

Public RPC punya rate limit. Vyper perlu queue + backoff.

### Implementasi

```python
# vyper/config/rpc_rate_limiter.py

import asyncio
import time
import threading
from collections import defaultdict, deque

class TokenBucket:
    """Token bucket rate limiter"""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate          # Token per second
        self.capacity = capacity  # Max tokens
        self.tokens = capacity    # Current tokens
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        """Consume tokens. Returns True if allowed."""
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def wait_and_consume(self, tokens: int = 1):
        """Block until tokens available"""
        while not self.consume(tokens):
            sleep_time = (tokens - self.tokens) / self.rate
            time.sleep(max(sleep_time, 0.1))

    def _refill(self):
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now


class RPCRequestQueue:
    """
    Smart queue that respects rate limits per provider.
    Batches requests and distributes across providers.
    """

    def __init__(self):
        self.buckets: dict[str, TokenBucket] = {}
        self.history: dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.router = RPCRouter()

    def execute(self, chain: str, method: str, params: list = None) -> dict:
        """Execute RPC call with rate limiting + failover"""
        provider = self.router.get_rpc(chain)
        bucket = self._get_bucket(provider)

        # Wait if rate limited
        bucket.wait_and_consume()

        # Execute
        try:
            resp = requests.post(
                provider,
                json={
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params or [],
                    "id": int(time.time() * 1000)
                },
                timeout=30
            )
            self.history[provider].append(("success", time.time()))
            return resp.json()
        except Exception as e:
            self.history[provider].append(("error", time.time()))
            self.router.record_error(chain, provider)

            # Retry with different provider
            return self.execute(chain, method, params)

    def _get_bucket(self, url: str) -> TokenBucket:
        if url not in self.buckets:
            # Default: 60 RPM = 1 per second, burst 10
            self.buckets[url] = TokenBucket(rate=1.0, capacity=10)
        return self.buckets[url]

    def stats(self) -> dict:
        """Rate limiting stats per provider"""
        stats = {}
        for url, history in self.history.items():
            successes = sum(1 for s, _ in history if s == "success")
            errors = sum(1 for e, _ in history if e == "error")
            stats[url] = {
                "total_requests": len(history),
                "success_rate": successes / max(len(history), 1),
                "error_count": errors,
            }
        return stats
```

### Integration

```python
# Vyper-wide RPC queue — semua RPC call melalui sini
rpc_queue = RPCRequestQueue()

# Etherscan API call
result = rpc_queue.execute("ethereum", "eth_call", [tx_data, "latest"])

# Storage stats
rpc_stats = rpc_queue.stats()  # Untuk dashboard
```

---

## 35. Ringkasan: Vyper Complete

```
VYPER — MICROSERVICE SMART CONTRACT BUG HUNTER
══════════════════════════════════════════════════════════════════════

 Arsitektur:    20 microservices (Docker Compose)
 Komunikasi:    HTTP/REST (httpx async)
 Orchestrator:  Workflow Engine — 11 state state machine
 Storage:       Per-service Docker volumes (JSON + Markdown)
 Bahasa:        Python 3.11+ (19 service) + TypeScript (Dashboard React SPA)
 Dashboard FE:  React 18 SPA + TypeScript + Tailwind v4 + Vite
 Docker:        Semua service di-container (exploit butuh Docker socket)

 SERVICE MAP:
 ══════════════════════════════════════════════════════════════════
 8000  Dashboard     — React SPA + API Gateway + SSE
 8001  Immunefi     — Sync 234+ program, detect repos
 8002  Source       — Multi-source fetch (GitHub/Sourcify/Etherscan/Blockscout)
 8003  Scanner Rtr  — Router ke 5 scanner tool services
 8004  AI           — LLM analysis + severity + fix recommendation
 8005  Classifier   — TP/FP/TN/FN + metrics + similarity
 8006  Exploit      — Anvil Docker engine + PoC generation
 8007  Reporter     — Immunefi + full report generation
 8008  Notifier     — Discord + Telegram + Email + Desktop
 8009  Orchestrator — Workflow engine + queue + daemon + re-run
 8010  Webhook      — Webhook delivery + signature verification
 8011  Config       — Config management + API keys
 8012  Upkeep       — Self-update + backup + restore + metrics
 8013  Mythril      — Symbolic execution (sidecar, isolated)
 8014  Slither      — Static analysis (split from main scanner)
 8015  Echidna      — Fuzzing & property testing
 8016  Forge        — Build verification (Foundry)
 8017  Halmos       — Formal verification & symbolic execution
 8018  Agent        — Autonomous agent orchestration + memory
 8019  Submission   — Track bounties across platforms

 WORKFLOW STATE MACHINE:
 ══════════════════════════════════════════════════════════════════
 PENDING → FETCHING_PROGRAM → FETCHING_SOURCE → SCANNING →
 HALMOS_ANALYSIS → AI_ANALYSIS → CLASSIFYING → [EXPLOITING] →
 REPORTING → [NOTIFYING] → COMPLETED
 └─ Failure states: SOURCE_FAILED, SCAN_FAILED, HALMOS_FAILED,
    AI_FAILED, CLASSIFY_FAILED, EXPLOIT_FAILED, TIMEOUT, ABORTED

 40+ FITUR LENGKAP:
 ══════════════════════════════════════════════════════════════════
 ✅ 20 microservices     — Setiap service independen, volume sendiri
 ✅ Workflow engine      — State machine 11 state + saga compensation
 ✅ API contracts        — Contract-first, tiap service punya spec
 ✅ Immunefi sync        — 234+ program, contract addresses
 ✅ Scanner split        — 5 independent scanner services (router + tools)
 ✅ Halmos formal verif  — Symbolic execution & formal verification
 ✅ Static analysis      — Slither + Mythril + Echidna + Forge
 ✅ AI analysis          — LLM verdict + severity + fix
 ✅ TP/FP/TN/FN          — 4-quadrant classification
 ✅ Exploit engine       — Anvil isolated, PoC generation
 ✅ Priority scoring     — Audit kontrak paling bernilai dulu
 ✅ Contract similarity  — Satu bug → detect di kontrak mirip
 ✅ Feedback loop        — FP/FN → reclassify + improve
 ✅ Retroactive re-run   — Pattern baru → scan ulang audit lama
 ✅ Submission tracker   — Lacak bounty, status, earnings
 ✅ React SPA dashboard  — 10 pages, real-time SSE, TypeScript
 ✅ Error handling       — Graceful, partial results + retry
 ✅ First-run wizard     — Auto setup, config, Docker check
 ✅ Dual reporting       — Immunefi ready + Full internal
 ✅ Multi-source fetch   — GitHub → Sourcify → Etherscan → Blockscout
 ✅ Foundry forge        — Compile, test, verify exploits
 ✅ solc-select          — Auto-detect + install compiler version
 ✅ Dependency resolver  — OpenZeppelin, Solmate, lib resolver
 ✅ RPC failover         — Multi-chain + health check + rate limit
 ✅ Slither tuning       — Detector config per kontrak + contract type
 ✅ Notifications        — Discord + Telegram + Email + Desktop
 ✅ Immunefi submit      — Semi-auto, clipboard, browser, draft tracking
 ✅ Git history analysis — Blame + risk score dari commit history
 ✅ Test intelligence    — Extract vulnerability hints from test files
 ✅ Self-update          — Auto-update patterns, skills, vyper itself
 ✅ Backup & restore     — Weekly auto-backup, named snapshots
 ✅ Resource governor    — Throttle saat laptop dipakai / battery low
 ✅ Webhook system       — POST events ke Slack, PagerDuty, etc
 ✅ CLI tool             — Removed. Semua interaksi via Dashboard atau API langsung.
 ✅ API Gateway          — Dashboard React SPA proxy ke semua service (port 8000)
 ✅ RPC rate limiter     — Token bucket + queue + failover per provider
 ✅ Autonomous daemon    — 24/7 auto-hunt via orchestrator
 ✅ Agent intelligence   — Memory system + autonomous agent daemon
 ✅ Custom detectors     — Extensible Slither/Halmos detection engine
 ✅ CI/CD pipeline       — GitHub Actions + GHCR + PR comments
 ✅ Production hardening — Resource governor + caching + saga recovery

 TOTAL:   20 services, ~40+ fitur, ~12,000+ baris (est.)
 DEPLOY:  docker compose up
 DATA:    Docker volumes (JSON + Markdown)
```

---

> **Vyper — Microservice Smart Contract Bug Hunter**
> 20 services. HTTP/REST. Docker Compose.
> Self-improving. Belajar dari setiap feedback.
> Local-first, microservice-powered.
>
> *Generated by lore-master — 20 Mei 2026*
