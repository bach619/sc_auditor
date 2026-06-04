# SC Auditor Platform — Brainstorming Summary

> ⚠️ **SUPERSEDED — June 4, 2026**
> 
> This document is a historical brainstorming artifact. The architecture described here evolved significantly.  
> See **[ARCHITECTURE.md](./ARCHITECTURE.md)** for the canonical 28-service architecture.  
> Full historical copy archived at **[docs/historical/BRAINSTORMING_v1.md](./docs/historical/BRAINSTORMING_v1.md)**.
> 
> **Original status**: Brainstorming (Belum Eksekusi)
> **Original date**: 17 Mei 2026
> **Sumber**: Hermes Agent (Python) + Immunefi + Opencode
> **Lokasi**: `E:\website\project\sc_auditor\learning\`

**⚠️ 17 Mei 2026 — PIVOT: SaaS → Local-First CLI**

Arsitektur awal dirancang sebagai SaaS dengan 14 microservices, NATS, Kubernetes + database terpusat. Setelah diskusi, diputuskan:
- **Bukan SaaS** → CLI tool personal
- **Bukan microservices** → 1 Python package modular
- **No database** → JSON + Markdown files (100% file-based)
- **Bukan NATS** → Direct function calls
- **Bukan TypeScript** → Python (Hermes native, tools native)

Detail arsitektur baru: **Lihat [`VYPER.md`](./VYPER.md)**

---

## 1. Visi Besar

**Vyper** — Local-First Smart Contract Bug Hunter. CLI tool yang jalan di laptop, scan kontrak Immunefi, cari True Positive bugs, generate PoC, hasilin laporan siap-submit.

| Sumber | Peran | Kenapa |
|--------|-------|--------|
| **Immunefi** | Target source | 234+ program dengan contract addresses + bounty + severity |
| **Hermes Agent** | Audit patterns | Python-native, security/blockchain skills, exploit patterns |
| **Opencode** | Skills + classification | 20 deduplicated skills, TP/FP/TN/FN framework |

**Tujuan Akhir:**
```bash
pip install vyper
vyper sync                    # Download semua program Immunefi
vyper audit 0x4c9edd...       # Full audit → TP/FP/TN/FN + PoC
vyper report aud_abc123       # Buka laporan siap-submit ke Immunefi
vyper metrics                 # Lihat akurasi: precision, recall, F1
```

---

## 2. Keputusan Arsitektur

### ⚠️ ARCHITECTURE CHANGE NOTICE

Setelah pivot ke Local-First CLI, arsitektur berubah total dari 14 microservices → 1 Python package.

**Dokumen arsitektur final: [`VYPER.md`](./VYPER.md)**
**Dokumen arsitektur lama (riwayat): [`ARCHITECTURE.md`](./ARCHITECTURE.md)**

### 2.1 True Microservices Architecture (HISTORICAL — Lihat VYPER.md)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SC AUDITOR PLATFORM                               │
│                        MICROSERVICES ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ CLIENTS  │  │ WEB UI   │  │ CLI/SDK  │  │ CI/CD    │               │
│  │(Browser) │  │(React    │  │(Terminal)│  │ Plugins  │               │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └─────┬────┘               │
│        └──────────────┴─────────────┴──────────────┘                   │
│                               │                                        │
│                       ┌───────▼───────┐                               │
│                       │  API GATEWAY  │                               │
│                       │ Kong / Envoy  │                               │
│                       │ Auth+Routing  │                               │
│                       └───────┬───────┘                               │
│                               │                                        │
│    ┌──────────────────────────┼──────────────────────────┐            │
│    │                          │                          │            │
│    ▼                          ▼                          ▼            │
│ ┌─────────┐            ┌──────────┐              ┌──────────┐        │
│ │  AUTH   │            │ PROJECT  │              │ORCHESTR  │        │
│ │ SERVICE │            │ SERVICE  │              │ -ATOR    │        │
│ │         │            │          │              │ SERVICE  │        │
│ │• Users  │            │• Audit   │              │          │        │
│ │• Roles  │            │  Projects│              │• Pipeline│        │
│ │• JWT    │            │• Version │              │• Workflow│        │
│ │• API key│            │• Teams   │              │• Skill   │        │
│ ├─────────┤            ├──────────┤              │  Dispatch│        │
 │ │JSON Files│            │ JSON Files│              ├──────────┤        │
│ └─────────┘            └──────────┘              │No State  │        │
│                                                   └──────────┘        │
│                                                                        │
│ ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│ │ STATIC  │  │ EXPLOIT │  │   AI    │  │  VULN   │  │ REPORT  │     │
│ │ANALYSIS │  │ ENGINE  │  │ANALYSIS │  │   DB    │  │ SERVICE │     │
│ │ SERVICE │  │(ISOLATED)│  │ SERVICE │  │ SERVICE │  │         │     │
│ │         │  │         │  │         │  │         │  │         │     │
│ │• Slither│  │• Anvil  │  │• LLM    │  │• Pattern│  │• PDF    │     │
│ │• Mythril│  │• Fork   │  │  Detect │  │• CVE    │  │• HTML   │     │
│ │• Echidna│  │• Replay │  │• Scoring│  │• Custom │  │• MD     │     │
│ │         │  │• Impers │  │• Fix Rec│  │• Known  │  │• Score  │     │
│ ├─────────┤  ├─────────┤  ├─────────┤  │  Vulns  │  ├─────────┤     │
│ │JSON Files │  │ No Net  │  │JSON Files │  ├─────────┤  │ JSON Files│     │
│ └─────────┘  └─────────┘  └─────────┘  │ JSON Files│  └─────────┘     │
│                                        └─────────┘                   │
│ ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐                  │
│ │  SKILL  │  │ STORAGE │  │   GAS   │  │ NOTIF   │                  │
│ │ SERVICE │  │ SERVICE │  │OPTIMIZER│  │ SERVICE │                  │
│ │         │  │         │  │         │  │         │                  │
│ │• Hermes │  │• Source │  │• Gas    │  │• Webhook│                  │
│ │• Opencode│  │• Artifact│  │  Report │  │• Email  │                  │
│ │• Custom │  │• S3/Min │  │• Op-Code│  │• Discord│                  │
│ │         │  │  io     │  │  Analyze│  │• Slack  │                  │
│ ├─────────┤  ├─────────┤  ├─────────┤  ├─────────┤                  │
│ │JSON Files │  │ Object  │  │ JSON Files │  │ JSON Files│                  │
│ └─────────┘  │ Storage │  └─────────┘  └─────────┘                  │
│              └─────────┘                                             │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    MESSAGE QUEUE                               │   │
│  │              (RabbitMQ / NATS / Kafka)                        │   │
│  │                                                                 │   │
│  │ Orchestrator ──▶ Static ──▶ VulnDB ──▶ AI ──▶ Exploit ──▶ Gas │   │
│  │       │                                                         │   │
│  │       └──────────────────────┬──────────────────────┘           │   │
│  │                              ▼                                   │   │
│  │                        ┌──────────┐                             │   │
│  │                        │  Report  │                             │   │
│  │                        │  Service │                             │   │
│  │                        └──────────┘                             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  OBSERVABILITY STACK                           │   │
│  │  OpenTelemetry → Grafana Tempo (traces)                       │   │
│  │               → Grafana Loki (logs)                           │   │
│  │               → Grafana Mimir (metrics)                       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Service Decomposition — 14 Services (HISTORICAL — Lihat VYPER.md)

| # | Service | Stack | Data Store | Tanggung Jawab |
|---|---------|-------|------------|----------------|
| 1 | **API Gateway** | Kong / Envoy | No state | Auth validation, rate limiting, request routing, API versioning |
| 2 | **Auth Service** | Python | JSON files | Users, roles, JWT, API keys, RBAC, team management |
| 3 | **Immunefi Scraper Service** | Python | JSON files + Cache | Sync 234+ Immunefi programs, track changes, detect new contracts, prioritize by bounty |
| 4 | **Project Service** | Python | JSON files | Audit projects (auto-created dari Immunefi), version tracking, team assignment |
| 6 | **Static Analysis Service** | Python + Slither/Mythril/Echidna | JSON files + Cache | Static scan execution, vulnerability detection, raw output parsing |
| 8 | **AI Analysis Service** | Python + LLM | JSON files + Vector | AI vuln detection, severity scoring, fix recommendation |
| 9 | **Vulnerability DB Service** | Python | JSON files | Pattern library, CVE database, known vulns, custom rules |
| 10 | **Report Service** | Python | JSON files | PDF/HTML/MD report generation, template management, scoring |
| 12 | **Skill Service** | Python (Hermes skills adapted) | JSON files + File Store | Skill loading & execution, versioning, lifecycle management |
| 13 | **Gas Optimizer Service** | Python | JSON files | Gas analysis, optimization suggestions, opcode-level profiling |
| 14 | **Notification Service** | Python | JSON files | Webhooks, email, Slack/Discord alerts, event broadcasting |

### 2.3 Immunefi Integration — Sumber Semua Job

Platform **tidak membuat project manual**. Semua target berasal dari **234+ program Immunefi**.

```
IMMUNEFI DATA FLOW:
═══════════════════════════════════════════════════════════════

Github Repo (Unofficial API)
https://raw.githubusercontent.com/infosec-us-team/
Immunefi-Bug-Bounty-Programs-Unofficial/main/
  │
  ├── projects.json              → Daftar 234+ program (id, nama, max bounty)
  └── project/{slug}.json        → Detail per program:
       │                             • Smart contract addresses (etherscan link)
       │                             • Chain (Ethereum, Arbitrum, Solana, dll)
       │                             • Max bounty (contoh: Ethena = $3.000.000)
       │                             • Severity levels & rewards
       │                             • Impacts in-scope & out-of-scope
       │                             • PoC requirements
       │                             • KYC requirements
       │                             • Previous audits
       │                             • Known issues
       │                             • Features (Managed Triage, Arbitration, dll)
       │
       ▼
  ┌──────────────────────────────────────────────┐
  │           IMMUNEFI SCRAPER SERVICE            │
  │  ──────────────────────────────               │
  │  • Auto-sync setiap N jam                     │
  │  • Track perubahan (git diff otomatis)        │
  │  • Deteksi program baru / contract baru       │
  │  • Prioritaskan berdasarkan max bounty        │
  │  • Filter: butuh PoC? KYC?                   │
  └──────────────────┬───────────────────────────┘
                     │
                     ▼
  ┌──────────────────────────────────────────────┐
  │           PROJECT SERVICE                     │
  │  • Auto-create project untuk tiap contract   │
  │  • Simpan metadata Immunefi (bounty, chain)  │
  │  • Track status: unscanned / scanning / done │
  └──────────────────────────────────────────────┘
```

**Data real dari Immunefi (contoh: Ethena):**
```json
{
  "project": "Ethena",
  "maxBounty": 3000000,
  "assets": [
    {
      "url": "https://etherscan.io/address/0x4c9edd5852cd905f086c759e8383e09bff1e68b3",
      "type": "smart_contract",
      "description": "USDe.sol"
    }
    // 25 kontrak lainnya di Ethereum, Mantle, Arbitrum, TON
  ],
  "features": ["Managed Triage", "Arbitration"],
  "pocPerTypeAndSeverity": [
    "smart_contract - critical",
    "smart_contract - high",
    "smart_contract - medium"
  ]
}
```

### 2.4 Exploit Engine — Service Paling Kritis

```
┌──────────────────────────────────────────────────────────┐
│                  EXPLOIT ENGINE SERVICE                    │
│                    (WAJIB ISOLATED)                       │
│                                                          │
│  ┌────────────────┐   ┌────────────────┐                │
│  │  API LAYER     │   │  POOL MANAGER  │                │
│  │  (gRPC/REST)   │──▶│                │                │
│  │                │   │  • Instance Pool│                │
│  │  • start       │   │  • Auto-scale   │                │
│  │  • deploy      │   │  • Health check │                │
│  │  • execute     │   │  • Cleanup      │                │
│  │  • trace       │   └────────┬───────┘                │
│  └────────────────┘            │                         │
│                                ▼                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │              ANVIL INSTANCE (Container)           │   │
│  │  ┌────────────────────────────────────────────┐  │   │
│  │  │ --network=none                             │  │   │
│  │  │ --load-mode fork                           │  │   │
│  │  │ --fork-url <ARCHIVED RPC>                  │  │   │
│  │  │ --fork-block-number <N>                    │  │   │
│  │  │                                            │  │   │
│  │  │  Setiap audit = 1 instance                 │  │   │
│  │  │  Instance hidup = durasi audit             │  │   │
│  │  │  Auto-destroy setelah selesai               │  │   │
│  │  └────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ISOLATION LAYERS:                                       │
│  1. Network: --network=none                              │
│  2. Resource: cgroups (CPU/RAM limit)                    │
│  3. Storage: ephemeral, tmpfs (RAM disk)                 │
│  4. Secrets: no private keys persistent                  │
│  5. Logging: stdout only, no external sink               │
└──────────────────────────────────────────────────────────┘
```

Kemampuan Exploit Engine:
- Fork mainnet/testnet pada block tertentu
- Impersonate account (owner, whale, management)
- Snapshot/reset state untuk multiple exploit variants
- Manipulasi balance, storage, timestamp
- Debug trace hingga opcode level
- Eksekusi transaksi exploit di lingkungan aman

---

## 3. Communication Patterns

```
┌──────────────────────────────────────────────────────────┐
│              COMMUNICATION MATRIX                         │
├────────────┬────────────────────┬────────────────────────┤
│ PATTERN    │ DIGUNAKAN UNTUK    │ TEKNOLOGI              │
├────────────┼────────────────────┼────────────────────────┤
│ Sync REST  │ Query cepat:       │ HTTP/2 + gRPC          │
│            │ get project, user  │                        │
├────────────┼────────────────────┼────────────────────────┤
│ Event      │ Pipeline orchestr. │ NATS / RabbitMQ        │
│ Async      │ Step → step        │                        │
├────────────┼────────────────────┼────────────────────────┤
│ Stream     │ Real-time audit    │ WebSocket + SSE        │
│            │ progress to UI     │                        │
├────────────┼────────────────────┼────────────────────────┤
│ gRPC       │ Internal service   │ Protocol Buffers       │
│            │ to service (perf)  │                        │
└────────────┴────────────────────┴────────────────────────┘
```

### Audit Pipeline (Event-Driven)

```
[UI] Submit contract                          [Event: audit.requested]
  │                                                   │
  ▼                                                   ▼
Orchestrator ─────────────────────────────── [Event: audit.started]
  │                                                   │
  ├─▶ Static Analysis Service ────────────── [Event: scan.completed]
  ├─▶ Vulnerability DB Service ──────────── [Event: patterns.matched]
  ├─▶ AI Analysis Service ───────────────── [Event: ai.analyzed]
  ├─▶ Exploit Engine (if vuln found) ────── [Event: exploit.completed]
  ├─▶ Gas Optimizer Service ─────────────── [Event: gas.analyzed]
  ├─▶ Skill Service ─────────────────────── [Event: skills.evaluated]
  └─▶ Report Service ────────────────────── [Event: report.generated]
              │                                         │
              ▼                                         │
         [UI] Audit complete ←──────────────────────────┘
         Notification Service ───▶ Webhook/Email/Slack
```

---

## 4. Data Ownership Per Service

Setiap service **hanya mengakses datanya sendiri**. Tidak ada shared database.

```
┌────────────────────────────────────────────────────────────────────┐
│                   DATA OWNERSHIP PER SERVICE                       │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  SERVICE              OWNS DATA                   ACCESS           │
│  ─────────────────────────────────────────────────────────────     │
│  Auth Service     │  users, roles, api_keys,    │ Read: Gateway   │
│                    │  sessions, audit_log         │ Write: Self     │
├───────────────────┼──────────────────────────────┼─────────────────┤
│  Project Service  │  projects, versions, teams   │ Read: Any auth  │
│                    │  audit_metadata              │ Write: Self     │
├───────────────────┼──────────────────────────────┼─────────────────┤
│  Static Analysis  │  scan_results, findings      │ Read: Report    │
│  Service          │  raw_output, caches          │ Write: Self     │
├───────────────────┼──────────────────────────────┼─────────────────┤
│  Exploit Engine   │  NO PERSISTENT DATA          │ Read: None      │
│                    │  (ephemeral session only)    │ Write: None     │
├───────────────────┼──────────────────────────────┼─────────────────┤
│  Vuln DB Service  │  patterns, cve_entries,      │ Read: Analysis  │
│                    │  known_vulnerabilities       │ Write: Admin    │
├───────────────────┼──────────────────────────────┼─────────────────┤
│  AI Analysis      │  ai_predictions, scores,     │ Read: Report    │
│  Service          │  fix_recommendations, vector  │ Write: Self     │
├───────────────────┼──────────────────────────────┼─────────────────┤
│  Report Service   │  reports, templates,         │ Read: User      │
│                    │  exports, scoring            │ Write: Self     │
├───────────────────┼──────────────────────────────┼─────────────────┤
│  Skill Service    │  skill_definitions,          │ Read: Orchestr  │
│                    │  skill_versions, usage stats │ Write: Admin    │
├───────────────────┼──────────────────────────────┼─────────────────┤
│  Storage Service  │  source_files, artifacts     │ Read: All svc   │
│                    │  (MinIO/S3 blob)             │ Write: Self     │
├───────────────────┼──────────────────────────────┼─────────────────┤
│  Gas Optimizer    │  gas_reports, opcode_analysis │ Read: Report    │
│  Service          │  optimization_suggestions     │ Write: Self     │
├───────────────────┼──────────────────────────────┼─────────────────┤
│  Notification     │  webhooks, templates,        │ Read: All svc   │
│  Service          │  delivery_logs               │ Write: Self     │
└────────────────────────────────────────────────────────────────────┘
```

---

## 5. Kekuatan Setiap Framework

### Dari Hermes Agent (Python)
| Komponen | Untuk SC Auditor | Service |
|----------|------------------|---------|
| Security/ skills | Pattern deteksi kerentanan | Skill Service |
| Blockchain/ (optional) | EVM, Solana, Hyperliquid analysis | AI Analysis Service |
| Red-teaming/godmode/ | Simulated attack framework | Exploit Engine |
| Software-development/ | Debugging, code review patterns | Skill Service |
| trajectory_compressor.py | Rekam & improve proses audit | Orchestrator Service |
| curator.py | Skill lifecycle management | Skill Service |
| 80+ tools | File ops, search, code execution | Skill Service |
| 22 platform gateways | Multi-platform alerts | Notification Service |

### Dari Paperclip (TypeScript)
| Komponen | Untuk SC Auditor | Service |
|----------|------------------|---------|
| 181 UI components | Audit dashboard, code viewer, report | Web UI |
| 36 routes + 110 services | Audit pipeline API | API Gateway + Services |
| 79 database tables | Audit, scan, vuln, report storage | Per-service DB |
| 10 agent adapters | Integrasi multi-agent | Orchestrator Service |
| Plugin SDK | Ekstensi pihak ketiga | Plugin System |
| MCP server | Integrasi tool eksternal | API Gateway |
| Eval framework (promptfoo) | Quality evaluation | All Services |
| CI/CD pipeline | Deployment | DevOps |

### Dari Opencode
| Komponen | Untuk SC Auditor | Service |
|----------|------------------|---------|
| Lore-master orchestrator | Audit planning & execution | Orchestrator Service |
| 58 skills | General development, database security | Skill Service |
| Self-improving system | Continuous learning dari audit | Orchestrator Service |
| app-quality scoring | Audit scoring rubric | Report Service |
| Decision logs | Audit trail | Orchestrator Service |

---

## 6. Struktur Direktori

```
E:\website\project\sc-auditor-platform/
│
├── gateway/                      # API Gateway
├── services/
│   ├── auth/                     # #1 Auth Service
│   ├── immunefi-scraper/         # #2 🔥 Immunefi Scraper
│   ├── project/                  # #3 Project Service
│   ├── orchestrator/             # #4 Orchestrator (lore-master)
│   ├── static-analysis/          # #5 Static Analysis (Slither/Mythril)
│   ├── exploit-engine/           # #6 🔴 Exploit Engine (isolated)
│   ├── ai-analysis/              # #7 AI Vuln Detection
│   ├── vulndb/                   # #8 Vulnerability DB
│   ├── report/                   # #9 Report Generator
│   ├── storage/                  # #10 Storage (MinIO/S3)
│   ├── skill/                    # #11 Skill Service (Hermes + Opencode)
│   ├── gas-optimizer/            # #12 Gas Optimizer
│   └── notification/             # #13 Notification Service
│
├── ui/                           # React 19 + Vite
├── cli/                          # CLI client
├── packages/                     # Shared packages (types, validators, proto)
│   ├── shared/                   #   Types + validators
│   ├── proto/                    #   Protobuf definitions
│   └── sdk/                      #   Client SDK
├── docs/                         # Documentation
├── scripts/                      # Build/deploy scripts
├── docker/                       # Docker Compose + Dockerfiles
├── k8s/                          # Kubernetes manifests
├── evals/                        # Evaluation suite
├── proto/                        # Protobuf definitions (root)
├── .github/                      # CI/CD workflows
├── pnpm-workspace.yaml           # Monorepo config
└── tsconfig.base.json            # Base TypeScript config
```

Setiap service di `services/*/` memiliki struktur:

```
services/auth/
├── src/
│   ├── index.ts          # Entry point
│   ├── routes/           # HTTP/gRPC handlers
│   ├── services/         # Business logic
│   ├── repository/       # Data access
│   ├── events/           # Event producers/consumers
│   └── types.ts          # Service-specific types
├── Dockerfile
├── package.json
├── tsconfig.json
└── vitest.config.ts
```

---

## 7. Audit Pipeline

```
                     AUDIT PIPELINE
═══════════════════════════════════════════════════════════════

Phase 1: INPUT
  User upload contract source
  → Storage Service: save source code
  → Project Service: create audit project
  → Event: audit.requested

Phase 2: STATIC ANALYSIS
  Orchestrator receives event
  → Dispatch to Static Analysis Service
  → Slither / Mythril / Echidna scan
  → Simpan findings ke database
  → Event: scan.completed

Phase 3: PATTERN MATCHING
  → Vulnerability DB Service: match findings against known patterns
  → Cross-reference with CVE database
  → Event: patterns.matched

Phase 4: AI ANALYSIS
  → AI Analysis Service: LLM-enhanced analysis
  → Severity scoring (0-10)
  → Fix recommendations
  → Event: ai.analyzed

Phase 5: EXPLOIT TESTING (if vuln found)
  → Exploit Engine: spin up Anvil instance
  → Fork mainnet at specific block
  → Execute proof-of-concept exploit
  → Record transaction trace
  → Event: exploit.completed

Phase 6: GAS ANALYSIS
  → Gas Optimizer Service
  → Opcode-level profiling
  → Optimization suggestions
  → Event: gas.analyzed

Phase 7: SKILL EVALUATION
  → Skill Service: run Hermes + Opencode skills
  → Cross-domain security analysis
  → Event: skills.evaluated

Phase 8: REPORT
  → Report Service: compile all results
  → Generate PDF/HTML/MD
  → Calculate final score
  → Event: report.generated

Phase 9: DELIVERY
  → Notification Service: send alerts
  → Webhook, email, Slack/Discord
  → UI: real-time update via WebSocket
```

---

## 8. Unique Selling Points

| Fitur | SC Auditor | Kompetitor Lain |
|-------|------------|------------------|
| **Exploit Engine Isolated** | ✅ Eksekusi exploit nyata di Anvil fork | ❌ Static analysis saja |
| **Live Immunefi Sync** | ✅ Auto-scan 234+ program, detect contract baru | ❌ Manual hunting |
| **Full Microservices** | ✅ 14 services, independent deploy | ❌ Banyak monolithic |
| **109 Skills Unified** | ✅ Hermes + Paperclip + Opencode | ❌ Terbatas proprietary |
| **Self-Improving** | ✅ Belajar dari setiap audit | ❌ Tidak ada |
| **Isolasi Berlapis** | ✅ 4 layer isolation di Exploit Engine | ❌ Rata-rata 1 layer |
| **PoC Otomatis** | ✅ Exploit Engine generate PoC (syarat WAJIB Immunefi) | ❌ Manual bikin PoC |
| **AI + Pattern Matching** | ✅ Hybrid analysis (LLM + DB) | ❌ Salah satu saja |
| **Report siap-Submit** | ✅ Format sesuai Immunefi + severity classification | ❌ Report generic |
| **Gas Optimization** | ✅ Built-in gas analyzer | ❌ Tool terpisah |

---

## 9. Risiko yang Teridentifikasi

| Risiko | Dampak | Mitigasi |
|--------|--------|----------|
| Hermes (Python) tidak bisa langsung jalan di Paperclip (TS) | Perlu adaptasi format skill | Skill adalah markdown — format agnostik, bisa di-parse oleh service manapun |
| Microservices complexity | Network latency, distributed debugging | Observability stack (Tempo + Loki + Mimir) wajib dari awal |
| Anvil butuh resource besar | Biaya infrastruktur | Limit concurrent instances + pool management |
| Exploit Engine bisa jadi attack vector ke internal | Kompromi platform | Isolasi total: --network=none, tmpfs, cgroups |
| Duplikasi skill antar framework | Konflik dan confusion | Registry terpadu + deduplikasi di Skill Service |
| Event-driven pipeline failure | Satu event hilang → pipeline stuck | Dead letter queue + retry mechanism |
| Service discovery & config | Service tidak bisa komunikasi | Service mesh (Istio/Linkerd) |

---

## 10. Service Inventory (Final)

```
 TOTAL: 14 Services — ALL MANDATORY
═══════════════════════════════════════

 INFRASTRUCTURE (2):
 ├── API Gateway            — Kong/Envoy       — Entry & routing
 └── Message Queue          — NATS/RabbitMQ    — Async communication

 CORE SERVICES (12):
 ├── Auth Service           — TypeScript       — Users, auth, RBAC
 ├── Immunefi Scraper       — TypeScript       — 🔥 Sync 234+ program
 ├── Project Service        — TypeScript       — Audit projects (auto)
 ├── Orchestrator           — TypeScript       — Pipeline engine
 ├── Static Analysis        — Python           — Slither/Mythril/Echidna
 ├── Exploit Engine         — Go/TS + Anvil    — 🔴 Isolated sandbox
 ├── AI Analysis            — Python           — LLM vuln detection
 ├── Vuln DB Service        — TypeScript       — Pattern & CVE database
 ├── Report Service         — TypeScript       — Report generation
 ├── Storage Service        — TypeScript       — Source & artifacts
 ├── Skill Service          — TypeScript       — Hermes/Opencode skills
 ├── Gas Optimizer          — TypeScript       — Gas analysis
 └── Notification           — TypeScript       — Alerts & webhooks
```

---

## 11. Detail Arsitektur

Untuk API contracts, event schema, database schema per service, dan pipeline flow yang detail:

➡️ **Lihat** [`ARCHITECTURE.md`](./ARCHITECTURE.md) (file terpisah, ~700+ baris)

Dokumen tersebut mencakup:
- Protobuf definitions untuk semua 14 services (Auth, Immunefi Scraper, Orchestrator, Static Analysis, Exploit Engine, AI Analysis, Vuln DB, Report, Storage, Skill, Gas Optimizer, Notification)
- 23+ NATS JetStream event topics dengan envelope format
- Database schema: 9 service databases (~40+ tables) termasuk indexes
- Pipeline lifecycle lengkap: 9 phase dari Discovery sampai Delivery
- Immunefi data model & sync strategy
- Proto file structure untuk code generation

## 12. Keputusan yang Sudah Dimatangkan

| Keputusan | Status | Detail |
|-----------|--------|--------|
| **Komunikasi Antar Service** | ✅ Event-driven + gRPC | NATS JetStream untuk events, Protobuf gRPC untuk sync calls |
| **Event Envelope Format** | ✅ Standar | id, type, source, correlation_id, timestamp, version, data, metadata |
| **Pipeline Orchestration** | ✅ Event-driven | Setiap stage emit event → orchestrator dispatch stage berikutnya |
| **Exploit Engine Isolation** | ✅ 5 layers | --network=none, cgroups, tmpfs, no secrets, stdout only |
| **Immunefi Sync Strategy** | ✅ 6-hour full sync | 30-min quick check, on-demand, diff-based detection |
| **Database per Service** | ✅ Tidak ada shared DB | Masing-masing service punya JSON storage sendiri |
| **Exploit Engine DB** | ✅ No persistent state | All state ephemeral, hasil disimpan oleh Storage Service |
| **Report Template Default** | ✅ Immunefi Standard | Template markdown siap-submit ke Immunefi |
| **PoC Generation** | ✅ Wajib untuk critical/high | Exploit Engine output dalam format Hardhat/Foundry |

## 13. Bug Classification System

Platform mengklasifikasikan setiap finding ke 4 kategori untuk akurasi dan pembelajaran:

| Klasifikasi | Definisi | Action |
|-------------|----------|--------|
| **True Positive (TP)** | Bug nyata, exploit confirmed | ✅ Masuk laporan Immunefi |
| **False Positive (FP)** | Alat salah detect | ❌ Catat, update pattern |
| **True Negative (TN)** | Alat benar nyatakan aman | ✅ Catat, confidence naik |
| **False Negative (FN)** | Bug terlewat (⚠️ PALING KRITIS) | 🚨 Trigger improvement cycle |

**Reporting Dual-Level:**
- **Level 1 (Immunefi)**: Hanya TP — siap submit, dengan PoC wajib
- **Level 2 (Internal)**: Semua klasifikasi + confusion matrix + learning recommendations

**Scoring**: Berbasis weighted confusion matrix — TP naikkan skor, FP/FN turunkan.

## 16. Keputusan Final

| # | Item | Keputusan | Alasan |
|---|------|-----------|--------|
| 1 | **Arsitektur** | ✅ **Microservice** (Docker Compose) | 12 service independen, HTTP/REST, isolasi + scale per service |
| 2 | **Storage** | ✅ **JSON + Markdown** (per-service volume) | File-based di volume Docker. No database, no CSV |
| 3 | **Bahasa** | ✅ **Python 3.11+** (semua service) | Hermes native, Slither/Mythril/Echidna semua Python |
| 4 | **Blockchain** | ✅ **EVM** (Ethereum + L2s) | 90% Immunefi EVM, tools mature |
| 5 | **Orchestrator** | ✅ **Workflow Engine** (async state machine) | 9 state, saga pattern, retry 3x, compensating actions |
| 6 | **Pipeline** | ✅ **HTTP/REST antar service** | Async httpx, timeout per step, state tracking |
| 7 | **Exploit Engine** | ✅ **Docker-in-Docker** (Anvil) | Exploit service manage container sendiri |
| 8 | **Skills** | ✅ **20 core skills (MD files)** | Hermes security + Opencode general |
| 9 | **Nama** | ✅ **VYPER** | 5 huruf, unik, metafora ular berbisa |
| 10 | **Interface** | ✅ **Dashboard + CLI** | Dashboard port 8000, CLI via orchestrator API |
| 11 | **Deploy** | ✅ **docker compose up** | Satu baris. Semua service jalan. |

Detail lengkap: **[`VYPER.md`](./VYPER.md)** (CLI) + **[`DASHBOARD.md`](./DASHBOARD.md)** (Web UI)

## 15. Vyper — Complete Feature List

### CLI (Terminal)
| Perintah | Fungsi |
|----------|--------|
| `vyper init` | Setup wizard pertama kali |
| `vyper sync` | Sync 234+ program Immunefi |
| `vyper audit <addr>` | Full audit pipeline (progress bar + rich output) |
| `vyper list` | List program (sort by priority, bounty) |
| `vyper batch --top=N` | Audit N kontrak prioritas tertinggi |
| `vyper feedback <id>` | Beri feedback klasifikasi finding |
| `vyper submit <id>` | Tandai submission ke Immunefi |
| `vyper submissions` | Lihat semua submission + bounty |
| `vyper report <id>` | Generate report |
| `vyper metrics` | Lihat metrik platform |
| `vyper learn` | Lihat learning opportunities (FN) |
| `vyper ui` | Buka dashboard localhost:3000 |
| `vyper daemon start` | Autonomous hunter — 24/7 cari bug sendiri |
| `vyper daemon status` | Status daemon + queue + stats |
| `vyper daemon stop` | Hentikan daemon |
| `vyper daemon logs` | Log real-time |
| `vyper update check` | Cek update pattern/skills |
| `vyper update patterns` | Update vulnerability patterns |
| `vyper update all` | Update semuanya (patterns + vyper) |
| `vyper backup` | Backup ~/.vyper/ ke tar.gz |
| `vyper backup list` | List backup yang tersedia |
| `vyper backup restore <name>` | Restore dari backup |
| `vyper install-completion` | Install shell completion (bash/zsh/pwsh) |
| `vyper config` | Edit config dari CLI |

### Dashboard (Browser — localhost:3000)
| Halaman | Isi |
|---------|-----|
| **Dashboard /** | Stat cards + list semua findings (TP/FP/TN/FN) + expandable detail + feedback button |
| **Programs** | List 234+ program + filter + sort + priority score |
| **Audits** | Riwayat audit + status |
| **Audit Detail** | Findings detail + AI reasoning + code + exploit + fix |
| **Report** | Laporan siap-submit ke Immunefi |
| **Submissions** | Tracker bounty + status + earnings chart |
| **Metrics** | Confusion matrix + per-tool precision + FN learning |
| **Settings** | Config editor + RPC + API keys + notifications + webhooks |
| **Updates** | Pattern versions, changelog, update button |
| **Backups** | List backup, create, restore |
| **Daemon Live** | Real-time log + queue + control panel |

### Core Engine
| Komponen | Deskripsi |
|----------|-----------|
| **Immunefi Sync** | Auto-download 234+ program, detect baru/update/closed |
| **Static Analysis** | Slither + Mythril + Echidna dengan error boundary |
| **Pattern Matching** | Vuln DB + CVE cache lokal |
| **AI Analysis** | LLM verdict (TP/FP), severity reassessment, fix recommendation |
| **TP/FP/TN/FN Classification** | 5-stage lifecycle + reclassification + confidence scoring |
| **Exploit Engine** | Anvil isolated Docker — --network=none, PoC generation |
| **Priority Scoring** | Bounty 40% + TP history 25% + Chain 15% + Freshness 10% + Contracts 10% + Source Bonus 10/15 |
| **Source Fetching** | Multi-provider: Immunefi → GitHub repo → Sourcify → Etherscan → Blockscout → Manual |
| **Foundry Integration** | `forge build` compile + `forge test` verify + exploit testing |
| **Compiler Version Mgmt** | Auto-detect pragma + install solc via solc-select |
| **Dependency Resolver** | Foundry `lib/` + Hardhat `node_modules/` + remappings → Slither config |
| **Multi-Chain RPC Mgmt** | Failover + health check + rate limiter + auto-discover providers |
| **Slither Detector Tuning** | Disable noise detectors, enable security-critical per contract type |
| **Notifications** | Discord webhook + Telegram bot + Email SMTP + Desktop native |
| **Immunefi Submission** | Semi-auto: clipboard + browser + draft tracker |
| **Git History Analysis** | Git blame → risk score dari commit frequency + authors + fix history |
| **Test File Intelligence** | Scan test files for vulnerability hints + coverage estimation |
| **Contract Similarity** | AST signature matching — satu bug, detect di kontrak mirip |
| **Feedback Loop** | User confirm/reject → reclassify → adjust pattern → improve |
| **Retroactive Re-run** | Pattern baru → scan ulang audit lama → update findings |
| **Submission Tracker** | Lacak status + bounty + earnings per program |
| **Autonomous Daemon** | 24/7 auto-hunt: sync → priority → audit → exploit → report → notify |
| **Daemon Priority Queue** | Auto-prioritize berdasarkan bounty + similarity + chain + freshness |
| **Desktop Notifications** | OS-native notify saat critical/high TP ditemukan |
| **Daemon Control** | Start/stop/pause dari CLI + dashboard |
| **Daemon Live Log** | Real-time log di terminal + dashboard |
| **Self-Update System** | Auto-update patterns, skills, vyper itself via pip |
| **Backup & Restore** | `vyper backup` → tar.gz + weekly auto-backup |
| **Resource Governor** | Throttle analysis saat laptop dipakai / battery low |
| **Webhook System** | POST events ke Slack/PagerDuty/webhook URL dengan signature |
| **CLI Auto-Completion** | Shell completion untuk Bash/Zsh/PowerShell |
| **RPC Rate Limiter** | Token bucket + queue + failover per provider |
| **Error Handling** | Graceful di setiap step, partial results, fallback |
| **Dual Reporting** | immunefi.md (TP-only) + full.md (semua klasifikasi) |
| **SSE Auto-Refresh** | Dashboard real-time update saat audit/daemon selesai |

### Storage (~/.vyper/)
| File | Format | Isi |
|------|--------|-----|
| `config.json` | JSON | RPC endpoints, API keys, scan config |
| `immunefi/programs.json` | JSON | List 234+ program |
| `immunefi/programs/{slug}.json` | JSON | Detail per program + contract addresses + repos[] |
| `repos/{program_slug}/` | Dir | 🆕 Cloned GitHub repos + vyper-meta.json |
| `audits/{id}/findings.json` | JSON | Semua findings + classifications |
| `audits/{id}/scans/{tool}.json` | JSON | Raw tool output |
| `audits/{id}/exploit/result.json` | JSON | Exploit result |
| `audits/{id}/exploit/poc.sol` | Solidity | PoC script |
| `audits/{id}/reports/immunefi.md` | Markdown | Laporan siap-submit |
| `audits/{id}/reports/full.md` | Markdown | Laporan lengkap + metrics |
| `contracts/{chain}/{addr}/` | .sol | Source code cache |
| `submissions.json` | JSON | Tracker submission + bounty |
| `metrics.json` | JSON | Agregat TP/FP/TN/FN + per-tool precision |
| `learning/feedback.json` | JSON | Semua feedback user |
| `learning/false_negatives.json` | JSON | Log FN + root cause + improvement |
| `learning/false_positives.json` | JSON | Log FP + pattern adjustment |
| `learning/similarity.json` | JSON | Contract similarity clusters |
| `learning/reruns.json` | JSON | Retroactive re-run history |
| `daemon_stats.json` | JSON | Stats daemon: uptime, total audits, errors |
| `update/VERSION` | Text | Versi pattern saat ini |
| `update/changelog.md` | Markdown | Riwayat perubahan pattern |
| `backups/{name}.tar.gz` | Archive | Compressed backup ~/.vyper/ |

---

> **Dokumen ini adalah ringkasan brainstorming.**
> Belum ada eksekusi sampai diumumkan siap.

*Generated by lore-master — 17 Mei 2026*
