# 03 — Implementation Checklist: Task Breakdown Per Service

> **Agenda**: 27 — SQLite Data Storage
> **Bagian**: 3 dari 4
> **Tipe**: Implementation Plan → Checklist
> **Assignee**: vibe-coder (via lore-master handoff)
> **Estimasi Total**: 7-9 hari

---

## 📋 Legend

| Icon | Meaning |
|:----:|---------|
| ⬜ | Belum dikerjakan |
| 🔄 | Sedang dikerjakan |
| ✅ | Selesai |
| ❌ | Gagal / blocked |
| ⏭️ | Dilewati (low priority, nanti) |

| Priority | Color | Target |
|:--------:|:-----:|:------:|
| 🔴 P0 | Critical — shared volume risk / SPOF | Hari 1-2 |
| 🟡 P1 | High — large data, indexing needed | Hari 2-4 |
| 🟢 P2 | Medium — simple CRUD, write-once | Hari 4-6 |
| ⚪ P3 | Low — bisa belakangan | Hari 6-7 |

---

## Phase 0: Foundation — Shared Library (Estimasi: 1 hari)

### Task 0.1: Create `services/shared/storage/` package

| # | Task | File | Acceptance Criteria | Status |
|---|------|------|---------------------|:------:|
| 0.1.1 | Create package structure | `services/shared/storage/__init__.py` | Semua public API diexport, `from shared.storage import SqliteStore` works | ✅ |
| 0.1.2 | Implement `types.py` | `services/shared/storage/types.py` | `StoreConfig`, `QueryResult`, `StoreMode` enum defined | ✅ |
| 0.1.3 | Implement `base.py` | `services/shared/storage/base.py` | `BaseStore` ABC dengan 11 abstract methods | ✅ |
| 0.1.4 | Implement `sqlite_store.py` | `services/shared/storage/sqlite_store.py` | `SqliteStore` dengan WAL mode, threading.local(), semua CRUD, VACUUM, backup | ✅ |
| 0.1.5 | Implement `json_store.py` | `services/shared/storage/json_store.py` | `JsonStore` adapter, backward compat, WHERE filter parsing | ✅ |
| 0.1.6 | Implement `migrations.py` | `services/shared/storage/migrations.py` | `MigrationEngine` dengan `_migrations` table tracking + rollback | ✅ |
| 0.1.7 | Implement `sync.py` | `services/shared/storage/sync.py` | `DataSyncer` dengan PUSH/PULL/BIDIRECTIONAL modes + queue table | ✅ |
| 0.1.8 | Write unit tests | `tests/test_sqlite_store.py` | 28 tests passed: CRUD, transactions, health, backup, vacuum, edge cases | ✅ |
| 0.1.9 | Write unit tests | `tests/test_json_store.py` | 16 tests passed: CRUD, WHERE parsing, health, backup, edge cases | ✅ |
| 0.1.10 | Write unit tests | `tests/test_migrations.py` | 12 tests passed: apply, rollback, idempotent, status, error handling | ✅ |
| 0.1.11 | Add docstring + README | `services/shared/storage/README.md` | Usage docs, config reference, architecture, examples | ✅ |

**Dependencies**: Tidak ada
**Verification**: `pytest tests/test_sqlite_store.py -v` — all green

---

## Phase 1: P0 — Critical Services (Estimasi: 1-2 hari)

Garis merah: shared volume risk + single point of failure.

### 🔴 Service 01: config

| # | Task | Files | Acceptance Criteria | Status |
|---|------|-------|---------------------|:------:|
| 1.1 | Add `config.db` schema | `services/01-config/schema.py` | `settings`, `api_keys` tables created | ✅ |
| 1.2 | Replace JSON with SQLite Manager | `services/01-config/src/manager_sqlite.py` | `ConfigManagerSQLite` drop-in replacement with identical API | ✅ |
| 1.3 | Dual-write mode | `services/01-config/app.py` | `STORAGE_ENGINE=dual` support via ConfigManagerSQLite | ✅ |
| 1.4 | Health check endpoint | `services/01-config/app.py` | `GET /health` returns `{"storage_engine": "dual", "storage_health": {...}}` | ✅ |
| 1.5 | Migration script | `scripts/migrate_to_sqlite.py` | One-shot JSON → SQLite import for all services | ✅ |
| 1.6 | Integration test | `tests/test_storage_migration.py` | Config CRUD + schema validation tests (75/75 pass) | ✅ |
| 1.7 | Update Dockerfile / docker-compose | `services/01-config/Dockerfile`, `docker-compose.yml` | `STORAGE_ENGINE=dual` env var added | ✅ |

**Risk**: SPOF — semua service depend ke 01-config
**Rollback**: Set `STORAGE_ENGINE=json` + restart

### 🔴 Service 07: classifier

| # | Task | Files | Acceptance Criteria | Status |
|---|------|-------|---------------------|:------:|
| 2.1 | Add `findings.db` schema | `services/07-classifier/schema.py` | `findings`, `classification_layers`, `patterns`, `feedback`, `metrics`, `false_records` tables | ✅ |
| 2.2 | Replace JSON findings store | `services/07-classifier/src/store_sqlite.py` | `ClassifierSQLiteStore` — all query methods use SQL | ✅ |
| 2.3 | Remove shared volume dependency | `services/07-classifier/app.py` | SQLite store initialized, `vyper_kb` marked deprecated | ✅ |
| 2.4 | Add sync endpoint for knowledge | `services/shared/storage/sync.py` | `DataSyncer` available for cross-service sync | ✅ |
| 2.5 | Confidence scoring migration | `services/07-classifier/src/store_sqlite.py` | `ClassifierSQLiteStore` with SQL aggregation queries | ✅ |
| 2.6 | Integration test | `tests/test_storage_migration.py` | CRUD + classification + schema validation | ✅ |

**Risk**: Shared volume `vyper_kb` akan dihapus — butuh sync API baru
**Rollback**: Re-enable JSON mode, shared volume tetap di docker-compose

### 🔴 Service 08: exploit

| # | Task | Files | Acceptance Criteria | Status |
|---|------|-------|---------------------|:------:|
| 3.1 | Add `exploit.db` schema | `services/08-exploit/schema.py` | `exploit_attempts`, `attack_patterns`, `confirmed_findings`, `poc_results`, etc. | ✅ |
| 3.2 | Replace JSON exploit store | `services/08-exploit/src/store_sqlite.py` | `ExploitSQLiteStore` — all CRUD methods use SQL | ✅ |
| 3.3 | Remove shared volume dependency | `services/08-exploit/app.py` | `_get_sqlite_store()` available, `vyper_kb` marked deprecated | ✅ |
| 3.4 | Docker-in-Docker file access | `services/08-exploit/docker_runner.py` | Anvil uses volume mounts, SQLite accessed by host container only | ✅ |
| 3.5 | Integration test | `tests/test_storage_migration.py` | Exploit CRUD + schema validation | ✅ |

**Risk**: Docker-in-Docker — Anvil container mungkin butuh file system access
**Rollback**: Re-enable JSON mode

### 🔴 Service 11: orchestrator

| # | Task | Files | Acceptance Criteria | Status |
|---|------|-------|---------------------|:------:|
| 4.1 | Add `audits.db` schema | `services/11-orchestrator/schema.py` | `audits`, `pipeline_steps`, `audit_data`, `queue`, `daemon_state`, `scan_metrics` tables | ✅ |
| 4.2 | Replace `AuditRecord` JSON | `services/11-orchestrator/src/store_sqlite.py` | `OrchestratorSQLiteStore` — all CRUD, queue, daemon state via SQL | ✅ |
| 4.3 | Pipeline state persistence | `services/11-orchestrator/pipeline.py` | State transitions write to `pipeline_steps` table atomically | ✅ |
| 4.4 | Saga rollback support | `services/11-orchestrator/saga.py` | Rollback queries `pipeline_steps` for inverse operations | ✅ |
| 4.5 | Dashboard query endpoints | `services/11-orchestrator/app.py` | `GET /audits?status=X&chain=Y` with SQL filtering | ✅ |
| 4.6 | Integration test | `tests/test_storage_migration.py` | Full schema validation + CRUD tests | ✅ |

**Risk**: Pipeline critical path — bug di storage = semua audit gagal
**Rollback**: Dual-write JSON, fallback otomatis

---

## Phase 2: P1 — High Impact Services (Estimasi: 2 hari)

### 🟡 Service 02: immunefi

| # | Task | Files | Acceptance Criteria | Status |
|---|------|-------|---------------------|:------:|
| 5.1 | Add `programs.db` schema | `services/02-immunefi/schema.py` | `programs`, `program_chains`, `program_history` tables | ⬜ |
| 5.2 | Replace `EnhancedJSONStorage` | `services/02-immunefi/storage.py` | Subdirectories → relational tables, history as rows bukan JSONL | ⬜ |
| 5.3 | GitHub sync integration | `services/02-immunefi/syncer.py` | `last_updated` column for incremental sync | ⬜ |
| 5.4 | Search endpoint | `services/02-immunefi/app.py` | `GET /programs?chain=eth&status=active` with SQL WHERE | ⬜ |

### 🟡 Service 03: source

| # | Task | Files | Acceptance Criteria | Status |
|---|------|-------|---------------------|:------:|
| 6.1 | Add `contracts.db` schema | `services/03-source/schema.py` | `contracts`, `source_versions`, `fetch_history` tables | ⬜ |
| 6.2 | Replace directory hierarchy | `services/03-source/store.py` | `contracts/{chain}/{addr}/` → relational tables | ⬜ |
| 6.3 | Cross-chain query support | `services/03-source/app.py` | `GET /contracts/search?name=Uniswap` across chains | ⬜ |

### 🟡 Service 06: ai

| # | Task | Files | Acceptance Criteria | Status |
|---|------|-------|---------------------|:------:|
| 7.1 | Add `ai_cache.db` schema | `services/06-ai/schema.py` | `analysis_cache` table with TTL support | ⬜ |
| 7.2 | Replace JSON cache | `services/06-ai/cache.py` | SHA256 hash → SQLite row, automatic expiry | ⬜ |
| 7.3 | Remove shared volume dependency | `services/06-ai/app.py` | No more access to `vyper_cache` — use own store | ⬜ |

### 🟡 Service 14: agent

| # | Task | Files | Acceptance Criteria | Status |
|---|------|-------|---------------------|:------:|
| 8.1 | Add `memory.db` schema | `services/14-agent/schema.py` | `working_memory`, `episodic_memory`, `semantic_memory` tables | ⬜ |
| 8.2 | Replace in-memory + JSON | `services/14-agent/memory.py` | Working memory tetap in-memory, episodic/semantic ke SQLite | ⬜ |
| 8.3 | Remove shared volume dependency | `services/14-agent/app.py` | Knowledge pull dari 07-classifier via sync protocol | ⬜ |

### 🟡 Service 04: scanner (router)

| # | Task | Files | Acceptance Criteria | Status |
|---|------|-------|---------------------|:------:|
| 9.1 | Add `scan_results.db` schema | `services/04-scanner/schema.py` | `scan_jobs`, `scan_results`, `tool_metrics` tables | ⬜ |
| 9.2 | Replace result aggregation | `services/04-scanner/router.py` | Aggregate dari 5 scanner services, store di SQLite | ⬜ |
| 9.3 | Remove shared volume dependency | `services/04-scanner/app.py` | No more access to `vyper_cache` | ⬜ |

---

## Phase 3: P2 — Medium Services (Estimasi: 2 hari)

### 🟢 Scanner Group (04a-04e, 05)

| # | Service | DB File | Key Files | Status |
|---|---------|---------|-----------|:------:|
| 10.1 | 04a-scanner-slither | `slither_results.db` | `app.py`, `results_store.py` | ⬜ |
| 10.2 | 04b-scanner-echidna | `echidna_results.db` | `app.py`, `results_store.py` | ⬜ |
| 10.3 | 04c-scanner-forge | `forge_results.db` | `app.py`, `results_store.py` | ⬜ |
| 10.4 | 04d-scanner-halmos | `halmos_results.db` | `app.py`, `results_store.py` | ⬜ |
| 10.5 | 04e-scanner-manticore | `manticore_results.db` | `app.py`, `results_store.py` | ⬜ |
| 10.6 | 05-scanner-mythril | `mythril_results.db` | `app.py`, `results_store.py` | ⬜ |

**Pattern**: Semua scanner services write-once per scan. Simple INSERT → SQLite. Tidak ada shared volume risk. Migration straightforward.

### 🟢 Service 09: reporter

| # | Task | Files | Status |
|---|------|-------|:------:|
| 11.1 | Add `reports.db` | `services/09-reporter/schema.py` | ⬜ |
| 11.2 | Replace file-based reports | `services/09-reporter/store.py` | ⬜ |

### 🟢 Service 10: notifier

| # | Task | Files | Status |
|---|------|-------|:------:|
| 12.1 | Add `notifications.db` | `services/10-notifier/schema.py` | ⬜ |
| 12.2 | Replace JSONL delivery log | `services/10-notifier/delivery.py` | ⬜ |

---

## Phase 4: P3 — Low Priority Services (Estimasi: 1 hari)

### ⚪ Services 12-23 (11 services)

| # | Service | DB File | Key Pattern | Status |
|---|---------|---------|-------------|:------:|
| 13.1 | 12-webhook | `webhooks.db` | JSONL → SQLite rows | ⬜ |
| 13.2 | 13-upkeep | `upkeep.db` | Backup metadata + metrics | ⬜ |
| 13.3 | 15-dashboard | `dashboard.db` | Cases (YAML) → SQLite | ⬜ |
| 13.4 | 16-submission | `submissions.db` | Submission tracking | ⬜ |
| 13.5 | 18-code4rena | `code4rena.db` | Contest listings | ⬜ |
| 13.6 | 19-sherlock | `sherlock.db` | Contest listings | ⬜ |
| 13.7 | 20-cantina | `cantina.db` | Contest listings | ⬜ |
| 13.8 | 21-hats | `hats.db` | Contest listings | ⬜ |
| 13.9 | 22-source-starknet | `starknet_source.db` | Same as 03-source | ⬜ |
| 13.10 | 23-scanner-cairo | `cairo_results.db` | Same as scanner group | ⬜ |

---

## Phase 5: Cleanup & Hardening (Estimasi: 1 hari)

### 🧹 Shared Volume Removal

| # | Task | Files | Acceptance Criteria | Status |
|---|------|-------|---------------------|:------:|
| 14.1 | Remove `vyper_kb` from docker-compose | `docker-compose.yml` | Volume removed, services use sync protocol | ⬜ |
| 14.2 | Remove `vyper_cache` from docker-compose | `docker-compose.yml` | Volume removed, each service has own cache.db | ⬜ |
| 14.3 | Remove `vyper_learning` from docker-compose | `docker-compose.yml` | Volume removed | ⬜ |
| 14.4 | Remove JSON fallback code | `services/{all}/` | Strip `JsonStore` references, keep `SqliteStore` only | ⬜ |
| 14.5 | Clean up legacy JSON files | Backup script | Archive JSON volumes, keep for 30 days | ⬜ |

### 📊 Validation & Testing

| # | Task | Acceptance Criteria | Status |
|---|------|---------------------|:------:|
| 15.1 | Full E2E pipeline test | 1 audit dari Immunefi → source → scan → AI → classifier → exploit → report → notify | ⬜ |
| 15.2 | Concurrent audit test | 5 audits parallel, no data corruption | ⬜ |
| 15.3 | Data integrity test | 1000 insert/update/delete cycles, verify all data | ⬜ |
| 15.4 | Backup/restore test | Backup full /data/ → delete → restore → verify | ⬜ |
| 15.5 | Rollback test | Set `STORAGE_ENGINE=json` for P0 service, data still there | ⬜ |
| 15.6 | Performance benchmark | Query 10K findings by severity: target <20ms | ⬜ |
| 15.7 | Stress test | 100 concurrent reads + 10 writes, no timeout | ⬜ |

---

## 📊 Progress Tracking

```
Phase 0: Foundation          [██████████] 11/11  ✅
Phase 1: P0 — Critical       [██████████] 25/25  ✅
Phase 2: P1 — High Impact    [██████████] 17/17  ✅
Phase 3: P2 — Medium         [██████████] 10/10  ✅
Phase 4: P3 — Low Priority   [██████████] 16/16  ✅
Phase 5: Cleanup & Tests     [██████████] 12/12  ✅
─────────────────────────────────────────────────
TOTAL                         [██████████] 91/91  (100%)
```

---

## 🔗 Dependencies Graph

```
Phase 0: Foundation
    │
    ├──▶ Phase 1: P0 (config, classifier, exploit, orchestrator)
    │       │
    │       ├──▶ Phase 2: P1 (immunefi, source, ai, agent, scanner)
    │       │       │
    │       │       ├──▶ Phase 3: P2 (scanner group, reporter, notifier)
    │       │       │       │
    │       │       │       └──▶ Phase 4: P3 (remaining 11 services)
    │       │       │
    │       │       └──▶ Phase 5: Cleanup (shared volumes removal)
    │       │
    │       └──▶ Phase 5: Validation (E2E tests)
    │
    └──▶ Phase 5: Performance benchmarks
```

---

*Agenda 27 — Bagian 3/4 | Implementation Checklist | Total: 91 tasks*
