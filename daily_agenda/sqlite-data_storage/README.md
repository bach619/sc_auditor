# Agenda 27 — Migrasi Storage: JSON → SQLite (Data Persistence Layer)

> **Project**: sc_auditor (Vyper — Smart Contract Bug Hunter)
> **Status**: 🔴 OPEN
> **Severity**: HIGH
> **Labels**: `architecture` `storage` `data-persistence` `performance` `migration`
> **Assignee**: lore-master → vibe-coder
> **Milestone**: v0.5.0 — Data Integrity & Performance Foundation
> **Dependensi**: Tidak ada (agenda mandiri, no blocking dependency)
> **Estimasi**: 5-7 hari kerja (gradual migration, 1 service per hari)
> **Sumber**: Deep-dive storage architecture analysis — sesi brainstorming lore-master

---

## Ringkasan Eksekutif

> **VYPER saat ini menyimpan 100% data di JSON files pada Docker volumes. Ini cukup untuk skala kecil (< 100 audit), tapi akan menjadi showstopper begitu mencapai ratusan audit: query O(n) lambat, concurrent write antar-container risk lost update, no transaction/ACID, no schema enforcement.**

**Solusi**: Migrasi bertahap dari JSON ke **SQLite** — database embedded yang:
- ✅ **Zero additional dependency** — `import sqlite3` adalah Python stdlib
- ✅ **Zero additional Docker service** — file `.db` di volume, sama seperti JSON
- ✅ **Zero impact ke Docker image size** — SQLite sudah ada di Python 3.11-slim
- ✅ **Sudah proven di codebase** — 17-experience sudah pakai SQLite dengan WAL mode
- ✅ **200-500x faster queries** — indexed `SELECT` vs JSON file scan
- ✅ **ACID transactions** — data integrity terjamin

---

## Mengapa Ini Penting? (Problem Statement)

### Kondisi Saat Ini

```
JSON File Pattern (109 lokasi di codebase):
┌─────────────────────────────────────────────┐
│  ❌ Query = O(n) file scan                  │
│  ❌ Concurrent write = lost update risk     │
│  ❌ No transactions = no rollback           │
│  ❌ No schema = runtime type errors         │
│  ❌ 3 shared volumes tanpa cross-process    │
│     locking antar Docker container          │
└─────────────────────────────────────────────┘
```

### Shared Volume Risk (Kritis)

Tiga volume diakses oleh **multiple containers** secara bersamaan:

| Volume | Containers | Risk |
|--------|-----------|------|
| `vyper_kb` | 07-classifier + 08-exploit + 14-agent | 🔴 Silent data loss |
| `vyper_cache` | 04-scanner + 06-ai + 11-orchestrator + 14-agent | 🔴 Cache corruption |
| `vyper_learning` | 07-classifier + 11-orchestrator + 15-dashboard | 🔴 Inconsistent state |

`threading.Lock` hanya works dalam **1 process**. Dua container berbeda → dua proses berbeda → locking tidak berlaku. Atomic rename (`tmp → final`) mencegah file corrupt, tapi **lost update tetap terjadi** — proses A baca, proses B baca, A tulis, B tulis → data A hilang.

### Data Growth Projection

| Scale | Volume Size (JSON) | Volume Size (SQLite) | Query Performance |
|-------|:------------------:|:--------------------:|:-----------------:|
| 100 audits | ~20 MB | ~8 MB | JSON: OK / SQLite: instant |
| 1K audits | ~200 MB | ~60 MB | JSON: mulai lambat / SQLite: <10ms |
| 10K audits | ~2 GB | ~600 MB | JSON: unusable / SQLite: <50ms |
| 100K audits | ~20 GB | ~6 GB | SQLite masih viable dengan indexing |

---

## Solusi: SQLite Per Service

```
┌─────────────────────────────────────────────────────────┐
│              ARSITEKTUR SQLite PER SERVICE               │
│                                                         │
│  Service 01-config          Service 02-immunefi         │
│  ┌──────────────────┐      ┌──────────────────────┐    │
│  │ /data/config/    │      │ /data/immunefi/       │    │
│  │   config.db      │      │   programs.db         │    │
│  │                  │      │   indexes.db          │    │
│  │ import sqlite3   │      │   history.db          │    │
│  └──────────────────┘      └──────────────────────┘    │
│                                                         │
│  Service 07-classifier      Service 11-orchestrator     │
│  ┌──────────────────┐      ┌──────────────────────┐    │
│  │ /data/classifier/ │      │ /data/orchestrator/   │    │
│  │   findings.db     │      │   audits.db           │    │
│  │   metrics.db      │      │   pipeline_state.db   │    │
│  │                  │      │                        │    │
│  │ Shared volumes    │      │                        │    │
│  │ vyper_kb, vyper_  │      │                        │    │
│  │ learning → OWN db │      │                        │    │
│  └──────────────────┘      └──────────────────────┘    │
│                                                         │
│  ┌──────────────────────────────────────────────┐      │
│  │  SHARED LIBRARY: services/shared/storage/     │      │
│  │  ├── base.py          # Abstract BaseStore    │      │
│  │  ├── sqlite_store.py  # SQLite implementation │      │
│  │  ├── json_store.py    # JSON adapter (compat) │      │
│  │  ├── migrations.py    # Schema migration      │      │
│  │  └── sync.py          # Cross-service sync    │      │
│  └──────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────┘
```

**Prinsip kunci:**
1. **1 service = 1 file `.db` (atau beberapa)** — sama seperti pattern volume existing
2. **Tidak ada service database terpusat** — setiap service akses file lokal
3. **Shared volumes dihilangkan** — diganti sync protocol HTTP
4. **Gradual migration** — dual-write JSON + SQLite selama transisi

---

## Dokumen dalam Agenda Ini

| # | Dokumen | Deskripsi | Status |
|---|---------|-----------|:------:|
| 1 | `01_context_and_analysis.md` | **Problem statement lengkap**, analisis storage saat ini, risiko, rationale pemilihan SQLite, benchmark perbandingan JSON vs SQLite | ✅ Done |
| 2 | `02_architecture_design.md` | **Desain teknis** — shared library `SqliteStore`, abstract interface, schema per service, WAL configuration, connection pooling, indexing strategy | ✅ Done |
| 3 | `03_implementation_checklist.md` | **Checklist implementasi** — task breakdown per service (28 services), file paths, acceptance criteria, priority ordering (P0-P3) | ✅ Done |
| 4 | `04_migration_protocol.md` | **Protokol migrasi** — dual-write strategy, data export/import, rollback plan, zero-downtime migration per service, validation steps | ✅ Done |

---

## Prioritas Migrasi (P0 → P3)

| Priority | # Services | Alasan | Target |
|:--------:|:----------:|--------|--------|
| 🔴 **P0** | 4 services | Shared volume risk, SPOF, critical path | Hari 1-2 |
| 🟡 **P1** | 5 services | Banyak data, indexing needed | Hari 2-4 |
| 🟢 **P2** | 8 services | Write-once pattern, simple CRUD | Hari 4-6 |
| ⚪ **P3** | 11 services | Low traffic, bisa belakangan | Hari 6-7 |

### P0 — Critical (Hari 1-2)
| # | Service | DB File | Alasan |
|---|---------|---------|--------|
| 01 | **config** | `config.db` | SPOF — semua service depend ke 01-config |
| 07 | **classifier** | `findings.db`, `metrics.db` | Shared volume `vyper_kb` risk, frequent writes |
| 08 | **exploit** | `exploit.db` | Shared volume `vyper_kb` risk, Docker-in-Docker |
| 11 | **orchestrator** | `audits.db` | Pipeline critical path, state machine data |

### P1 — High Impact (Hari 2-4)
| # | Service | DB File | Alasan |
|---|---------|---------|--------|
| 02 | immunefi | `programs.db` | Banyak data (234+ programs), indexing needed |
| 03 | source | `contracts.db` | Chain/address hierarchy — perfect for relational |
| 06 | ai | `analysis_cache.db` | Shared volume `vyper_cache` risk |
| 14 | agent | `memory.db` | Shared volume `vyper_kb` risk, session state |
| 04 | scanner | `scan_results.db` | Shared volume `vyper_cache` risk |

### P2 — Medium (Hari 4-6)
04a-04e scanner group, 05-mythril, 09-reporter, 10-notifier

### P3 — Low (Hari 6-7)
12-webhook, 13-upkeep, 15-dashboard, 16-submission, 18-21 bounty platforms, 22-23 starknet

---

## Estimasi Effort

| Fase | Tasks | Estimasi | Output |
|------|-------|:--------:|--------|
| **Foundation** | Shared library `services/shared/storage/` (5 files) | 1 hari | SqliteStore, BaseStore, migrations, sync |
| **P0 Migration** | 4 critical services | 1-2 hari | config, classifier, exploit, orchestrator |
| **P1 Migration** | 5 high-impact services | 2 hari | immunefi, source, ai, agent, scanner |
| **P2 Migration** | 8 medium services | 2 hari | Scanner group, reporter, notifier |
| **P3 Migration** | 11 low-priority services | 1 hari | Sisanya |
| **Testing** | Integration + migration tests | 1 hari | Test suite |
| **TOTAL** | | **7-9 hari** | Full migration |

---

## Status & Next Steps

- [x] 🔵 **Fase 1: Brainstorming** ✅ SELESAI — dokumen ini adalah output brainstorming (sesi storage deep-dive)
- [ ] 🟡 **Fase 2: Planning** — breakdown sub-task, prioritasi, hand-off plan
- [ ] 🟢 **Fase 3: Implementasi** — hand-off ke vibe-coder
- [ ] ✅ **Fase 4: Closed** — semua service migrated, test passing

### Immediate Action Items
1. **Review dokumen ini** — validasi approach, priority ordering, dan desain
2. **Approve shared library design** — `services/shared/storage/` sebagai fondasi
3. **Pilih 1 P0 service** untuk pilot migration — rekomendasi: 01-config (paling sederhana)
4. **Hand-off ke vibe-coder** setelah planning approved

---

## Related

- `ARCHITECTURE.md` — Overview arsitektur VYPER
- `VYPER.md` — Filosofi desain dan keputusan arsitektur
- `services/17-experience/app.py` — Existing SQLite reference implementation
- `services/shared/cache.py` — Shared cache abstraction pattern
- `docker-compose.yml` — Volume topology referensi
- `SYSTEM_LOG.md` — Change log untuk tracking

---

*Dibuat: 2026-06-04 | Agenda: 27 | Status: 🔴 OPEN | Assignee: lore-master → vibe-coder*
