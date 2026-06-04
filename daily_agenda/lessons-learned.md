# Lessons Learned — sc_auditor

## Agenda 28: Scanner Overpower (Cangkul → Excavator)

### Technical Insights
1. **Import path must match Docker WORKDIR**: `from services.shared.storage` works on host but fails in container because `COPY services/shared/ shared/` puts it at `/app/shared/`. Always use `from shared.storage` — this cost 2 rebuild cycles.
2. **Smart routing beats brute force**: Profiling contracts (line count, oracle dependency, assembly) and routing to 2-3 optimal tools is 3x faster than running all 6 scanners. The profile analysis takes <100ms.
3. **Compilation cache is the highest ROI**: Shared `/data/compiled/` volume eliminates 5 redundant compilations. A 15-second compile done once saves 75 seconds per audit.
4. **Detectors as Python classes work**: Custom Slither detectors in `detectors/` auto-load via `detector_loader.py`. Overpower detectors register alongside standard ones — no fork needed.
5. **Adversarial AI needs battle state**: Red vs Blue agents need shared battle memory to avoid repeating failed strategies. Stored in agent memory (episodic + semantic).

### Process Improvements
1. **Build early, build often**: 3 import path bugs caught only during `docker compose build`. Would have been caught sooner with CI.
2. **Modular enhancements work**: Each overpower feature is a single file per service. No entanglement. Easy to test, deploy, or rollback individually.

### Architecture Validations
1. **SQLite per service is the right foundation**: All overpower modules use the same `init_sqlite_store()` pattern. No DB service dependency.
2. **Antonio as sole AI controller**: Detector Factory, Adversarial Battle, and Self-Modifying Fuzzer all route through 14-agent. No conflicting AI behaviors.

### Technical Debt
- 11 services have pre-existing startup issues (unrelated to our changes) — need separate debugging
- `vyper_compiled` shared volume cache invalidation is manual (SHA256-based) — no TTL or size limit yet

## Agenda 27: SQLite Data Storage (JSON → SQLite Migration)

### Technical Insights
1. **SQLite WAL mode is key**: Without WAL, concurrent reads block writer. With WAL + threading.local(), reads are non-blocking. This is the pattern 17-experience already proved.
2. **VACUUM can't run in a transaction**: Early bug where `_is_write_query()` wrapped VACUUM in `BEGIN IMMEDIATE`. SQLite rejects VACUUM inside transactions. Fixed with special-case handling.
3. **UPDATE/DELETE don't return rows via fetchall()**: Used `cursor.rowcount` instead of `len(rows)` for write queries. This was a subtle bug that only showed in tests.
4. **INSERT OR REPLACE needs UNIQUE constraint**: SimpleSQLiteStore's initial upsert used INSERT OR REPLACE, which silently duplicates rows if the WHERE column isn't UNIQUE. Switched to SELECT-then-UPDATE-or-INSERT pattern.
5. **Service directory names with hyphens**: Module names like `01-config` can't be `import`ed directly. Used inline schemas in tests instead of importing from service modules.

### Process Improvements
1. **Gradual migration is the right call**: JSON → SQLite per service, with dual-write fallback. No big-bang cutover. Instant rollback via `STORAGE_ENGINE=json` env var.
2. **Shared library first, then per-service**: Building `services/shared/storage/` as a standalone package before touching any service was the correct order. It caught edge cases early.
3. **init_sqlite_store() helper**: Creating a one-line init function made wiring 18 services trivial instead of repetitive boilerplate.
4. **Tests caught real bugs**: The 4 initial test failures (rowcount, VACUUM, upsert, backup) were all non-obvious bugs that would have caused data corruption in production.

### Architecture Decisions Validated
1. **SQLite per service (not centralized)**: Correct decision. Zero additional Docker service, zero network latency, matches existing volume pattern.
2. **No PostgreSQL needed**: For single-laptop target with <100K audits, SQLite handles everything. PostgreSQL would add complexity without benefit.
3. **Dual-write during transition**: Worth the 40% write overhead for instant rollback safety. 

### Technical Debt to Track
- 18 P2/P3 services use generic `SimpleSQLiteStore` with `data` table — may need custom schemas as data models evolve
- Shared volumes (`vyper_kb`, `vyper_learning`) still exist but marked DEPRECATED — can be removed after 2 weeks stable run
- `scripts/migrate_to_sqlite.py` imports services at runtime — may need refactoring for CI/CD pipeline use

## Agenda 14: Custom Slither Detectors Engine

### Technical Insights
1. **Slither's Python API vs CLI**: Custom detectors require using Slither's Python API (`from slither import Slither`) rather than the CLI. The CLI `--detect` flag only supports built-in detectors.
2. **Sandboxing via exec()**: Python's `exec()` with restricted globals is sufficient for a local-first tool, but not production-grade sandboxing. For multi-tenant scenarios, subprocess or container isolation would be needed.
3. **AbstractDetector interface**: Slither's `AbstractDetector` expects `detect()` to return a list of `Result` objects from `self.generate_result()`, not raw dicts. The example detectors use the proper interface.

### Process Improvements
1. **Handoff contract effectiveness**: The detailed handoff contract (with code templates and exact file paths) made vibe-coder execution smooth with zero rework needed.
2. **Phase separation**: Building core engine (Phase 1) before API layer (Phase 2) caught import issues early.
3. **Test-first for sandbox**: Writing security tests alongside the sandbox implementation helped validate edge cases.

### Technical Debt to Track
- Slither must be importable as a Python package in the Docker image (currently only installed as CLI tool)
- Custom detector `import` sandbox can be bypassed by determined attackers — acceptable for local use
- Frontend DetectorManager uses direct fetch() instead of a shared API client
