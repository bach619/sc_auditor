# Implementation Plan: Service 02 — Immunefi Bug Bounty Intelligence

> **Acuan**: `daily_agenda/01_enhancement_02_immunefi.md`, `VYPER.md`, `IMPLEMENTATION_PLAN.md`
> **Service**: `02-immunefi` (port 8001)
> **Storage**: Enhanced JSON (no SQL — lihat VYPER.md §3a)
> **Target**: Personal use — private app, bukan SaaS

---

## Daftar Isi

1. [Ringkasan](#1-ringkasan)
2. [Task Dependency Graph](#2-task-dependency-graph)
3. [Phase 1 — Foundation (Storage + Core)](#3-phase-1--foundation-storage--core)
4. [Phase 2 — Multi-Source Providers](#4-phase-2--multi-source-providers)
5. [Phase 3 — Automated Sync Engine](#5-phase-3--automated-sync-engine)
6. [Phase 4 — Intelligence Layer](#6-phase-4--intelligence-layer)
7. [Phase 5 — Cross-Service Integration](#7-phase-5--cross-service-integration)
8. [Phase 6 — Repository Forking](#8-phase-6--repository-forking)
9. [File Map — Perubahan + File Baru](#9-file-map--perubahan--file-baru)
10. [Cross-Service Impact Analysis](#10-cross-service-impact-analysis)
11. [Daftar Lengkap Tasks](#11-daftar-lengkap-tasks)

---

## 1. Ringkasan

| Level | Fokus | Tasks | Est. Waktu | Depends On |
|-------|-------|-------|------------|------------|
| **Phase 1** | Enhanced JSON Storage + migration + refactor | 5 tasks | ~30 min | — |
| **Phase 2** | Multi-source provider protocol + 4 providers | 4 tasks | ~25 min | Phase 1 |
| **Phase 3** | Auto sync (periodic + incremental) + 4 endpoints | 4 tasks | ~20 min | Phase 2 |
| **Phase 4** | Scoring engine + trend analysis + repo deep dive | 5 tasks | ~35 min | Phase 1 |
| **Phase 5** | Contract auto-fetch (→ 03-source), scan trigger (→ 11) | 3 tasks | ~15 min | Phase 2 + 03-source |
| **Phase 6** | GitHub fork client + endpoints + integrasi 03/08 | 4 tasks | ~25 min | Phase 1 + GitHub token |
| **Total** | | **25 tasks** | **~150 min** | |

---

## 2. Task Dependency Graph

```
Phase 1 (Storage)
  │
  ├──→ T1 EnhancedJSONStorage class
  ├──→ T2 Legacy migration
  ├──→ T3 Refactor SyncManager → EnhancedJSONStorage
  ├──→ T4 Refactor app.py → EnhancedJSONStorage
  └──→ T5 Unit tests for EnhancedJSONStorage
        │
        ▼
Phase 2 (Multi-Source)
  │
  ├──→ T6 Provider protocol + registry
  ├──→ T7 ImmunefiOfficialProvider
  ├──→ T8 External providers (HackerOne, Cantina, Code4rena, Sherlock)
  └──→ T9 Sync → iterate all providers
        │
        ▼
Phase 3 (Auto Sync)
  │
  ├──→ T10 Periodic sync (asyncio background task)
  ├──→ T11 Incremental sync (commit hash diff)
  ├──→ T12 Sync schedule endpoints
  └──→ T13 History + contracts + chains endpoints
        │
        ▼
Phase 4 (Intelligence)
  │
  ├──→ T14 Program scoring engine
  ├──→ T15 Trend analyzer
  ├──→ T16 Anomaly detection + alerts
  ├──→ T17 Repo deep intelligence (GitHub API)
  └──→ T18 Intelligence endpoints
        │
        ▼
Phase 5 (Cross-Service)
  │
  ├──→ T19 Contract auto-fetch → 03-source
  ├──→ T20 Scan trigger → 11-orchestrator
  └──→ T21 Fork-aware source provider (03-source patch)
        │
        ▼
Phase 6 (Forking)
  │
  ├──→ T22 GitHubForkClient
  ├──→ T23 Fork endpoints (POST + GET + DELETE)
  ├──→ T24 Fork integration with 03-source (ForkAwareSourceProvider)
  └──→ T25 Fork integration with 08-exploit (ExploitPusher)
```

---

## 3. Phase 1 — Foundation (Storage + Core)

**Goal**: Ganti flat `programs.json` dengan Enhanced JSON Storage. Semua perubahan harus backward-compatible — data lama tidak hilang.

### T1 — EnhancedJSONStorage Class

| Aspek | Detail |
|-------|--------|
| **File** | `services/02-immunefi/src/storage.py` (BARU) |
| **Kelas** | `EnhancedJSONStorage` |
| **Methods** | `write_atomic()`, `save_program()`, `load_program()`, `save_all()` (batch), `load_all_programs()` |
| | `append_history()`, `get_history()` |
| | `rebuild_indexes()`, `read_meta()`, `write_meta()` |
| | `_ensure_dirs()`, `_migrate_from_legacy()` |
| **Pola** | Singleton per `data_dir` — dipakai SyncManager + app |
| **Atomic write** | `file.json.tmp` → tulis → `os.replace()` → atomic |
| **History** | Append-only `.jsonl` — setiap baris: `{"timestamp": "...", "snapshot": {...}}` |

**Directory structure yang dibuat**:
```
/data/immunefi/
├── programs/{slug}.json       # Satu file per program
├── history/{slug}.jsonl       # Change log per program
├── indexes/
│   ├── by_chain.json
│   ├── by_status.json
│   ├── by_bounty.json
│   └── by_last_updated.json
├── sync_log.jsonl             # Sync operation history
└── _meta.json                 # schema_version, last_synced, commit_hash
```

**Model tambahan** (di `models.py`):
- Tidak perlu model baru — semua tetap pake Pydantic `Program`, `Contract`, `Repo`

**Kode kunci**:
```python
class EnhancedJSONStorage:
    SCHEMA_VERSION = "2.0"
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._ensure_dirs()

    def write_atomic(self, path: Path, data: Any) -> bool:
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            tmp.replace(path)
            return True
        except OSError:
            if tmp.exists(): tmp.unlink()
            return False
```

**Acceptance Criteria**:
- ✅ `save_program()` membuat file di `programs/{slug}.json`
- ✅ `load_program()` mengembalikan `Program` yang sama persis
- ✅ `append_history()` menambah satu baris ke `.jsonl`
- ✅ `get_history()` mengembalikan N entry terakhir, reverse chronological
- ✅ `rebuild_indexes()` membuat 4 file index yang benar
- ✅ Atomic write: kalau crash di tengah, file target tidak corrupt
- ✅ Semua path menggunakan Path, cross-platform

---

### T2 — Legacy Migration

**File**: `services/02-immunefi/src/storage.py` (method `_migrate_from_legacy`)

**Logika**:
1. Cek apakah `programs.json` (legacy) ada
2. Cek apakah `_meta.json` sudah ada — jika sudah, skip (already migrated)
3. Baca legacy `programs.json`
4. Iterasi semua program → `self.save_program(p)`
5. Preserve metadata: `last_synced`, `commit_hash`
6. `self.rebuild_indexes(programs)`
7. Rename `programs.json` → `programs.json.bak`

**Acceptance Criteria**:
- ✅ Legacy `programs.json` otomatis terdeteksi di startup
- ✅ Semua program tersimpan ke format baru
- ✅ File lama di-rename ke `.bak` (bukan dihapus)
- ✅ Kalau `_meta.json` sudah ada, tidak re-migrate
- ✅ Logging: `"storage.migrated", count=N`

---

### T3 — Refactor SyncManager

**File**: `services/02-immunefi/src/sync.py` (MODIFIKASI)

**Perubahan**:
| Method | Dari | Ke |
|--------|------|----|
| `__init__` | `self.programs_path = data_dir / programs.json` | `self.storage = EnhancedJSONStorage(data_dir)` |
| `load_programs()` | Baca `programs.json` langsung | `self.storage.load_all_programs()` |
| `save_programs()` | Write `programs.json` | `self.storage.save_all(programs)` + `rebuild_indexes()` |
| `sync_all()` | Baca list → detail → save flat | Baca list → detail → `save_program()` per program |
| — (baru) | — | `get_history(slug)` — delegasi ke storage |
| — (baru) | — | `save_sync_log()` — append ke `sync_log.jsonl` |

**Sync log entry** (format `.jsonl`):
```json
{"sync_id": "abc123", "status": "completed", "programs_synced": 234, "total": 234, "started_at": "...", "completed_at": "..."}
```

**Acceptance Criteria**:
- ✅ `load_programs()` otomatis migrasi dari legacy kalau perlu
- ✅ `save_programs()` menghasilkan file per-program
- ✅ Sync log tercatat di `sync_log.jsonl`
- ✅ Semua endpoint di app.py tetap berfungsi tanpa perubahan

---

### T4 — Refactor app.py

**File**: `services/02-immunefi/app.py` (MODIFIKASI)

**Perubahan minimal** — karena SyncManager API-nya tidak berubah (hanya internal):

| Endpoint | Perubahan |
|----------|-----------|
| `/health` | Tambah `schema_version` dari `_meta.json` |
| `/programs` | Tidak berubah — masih pake `sync_manager.programs` |
| `/programs/{slug}` | Tidak berubah |
| `/sync` | Tidak berubah — `sync_manager.sync_all()` masih sama |
| `/stats` | Tidak berubah — aggregasi masih sama |

**Tambahan**:
- Startup log: tampilkan `schema_version`, `programs count`, `last_synced`

**Acceptance Criteria**:
- ✅ Semua endpoint existing tetap return response yang sama
- ✅ `GET /health` return `schema_version`
- ✅ Log startup menunjukkan informasi migrasi

---

### T5 — Unit Tests for EnhancedJSONStorage

**File**: `tests/test_immunefi_storage.py` (BARU)

**Test cases**:
```python
# test_atomic_write_integrity
# test_save_and_load_program
# test_load_all_programs_empty
# test_load_all_programs_multiple
# test_append_history
# test_get_history_limit
# test_get_history_empty
# test_rebuild_indexes_by_chain
# test_rebuild_indexes_by_bounty
# test_rebuild_indexes_by_status
# test_meta_read_write
# test_migrate_from_legacy
# test_migrate_idempotent
# test_concurrent_write_safety (single-thread)
```

**Acceptance Criteria**:
- ✅ Semua test pass
- ✅ Coverage > 85% untuk `storage.py`
- ✅ Test migrasi menggunakan fixture legacy `programs.json`

---

## 4. Phase 2 — Multi-Source Providers

**Goal**: Tambahkan 5 provider untuk fetching program dari berbagai platform bounty.

### T6 — Provider Protocol + Registry

**File**: `services/02-immunefi/src/providers/__init__.py` (BARU)

**Protocol**:
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class BountyProvider(Protocol):
    """Protocol untuk semua bounty program provider."""
    name: str
    priority: int  # lower = tried first
    
    async def fetch_program_list(self) -> list[dict]:
        """Fetch list semua program dari provider ini."""
        ...
    
    async def fetch_program_detail(self, slug: str) -> dict | None:
        """Fetch detail satu program. Return None jika tidak ditemukan."""
        ...
    
    def is_available(self) -> bool:
        """Cek apakah provider bisa digunakan (API key ada, dll)."""
        ...
```

**Registry** (di `__init__.py`):
```python
PROVIDER_REGISTRY: list[type[BountyProvider]] = [
    ImmunefiOfficialProvider,
    ImmunefiMirrorProvider,
    HackerOneProvider,
    CantinaProvider,
    Code4renaProvider,
    SherlockProvider,
]
```

**Model** (di `models.py`):
```python
class ProviderStatus(BaseModel):
    name: str
    available: bool
    priority: int
    programs_count: int = 0
    last_sync: str | None = None
    error: str | None = None
```

**Acceptance Criteria**:
- ✅ Protocol didefinisikan dengan `@runtime_checkable`
- ✅ Registry bisa di-iterasi semua provider
- ✅ `is_available()` dikembalikan dengan benar per provider
- ✅ Setiap provider bisa di-test secara independen

---

### T7 — ImmunefiOfficialProvider

**File**: `services/02-immunefi/src/providers/immunefi_official.py` (BARU)

**API Reference** (dari dokumen):
```python
class ImmunefiOfficialProvider:
    name = "immunefi_official"
    priority = 1  # Highest priority — official API
    
    BASE_URL = "https://api.immunefi.com/v1"
    
    async def fetch_program_list(self) -> list[dict]:
        api_key = await self._get_api_key()  # via 01-config or env
        headers = {"Authorization": f"Bearer {api_key}"}
        resp = await self.client.get(f"{self.BASE_URL}/programs", headers=headers)
        return resp.json()["data"]  # adjust based on actual API response
    
    async def fetch_program_detail(self, slug: str) -> dict | None:
        api_key = await self._get_api_key()
        headers = {"Authorization": f"Bearer {api_key}"}
        resp = await self.client.get(f"{self.BASE_URL}/programs/{slug}", headers=headers)
        if resp.status_code == 404:
            return None
        return resp.json()["data"]
    
    def is_available(self) -> bool:
        return bool(os.getenv("IMMUNEFI_API_KEY"))
```

**Error handling**:
- Rate limit: exponential backoff (pakai tenacity — sudah ada)
- 401/403: log warning "Immunefi API key invalid"
- Network error: retry 3x, lalu skip provider

**Acceptance Criteria**:
- ✅ Fetch program list dari API resmi
- ✅ Fetch program detail
- ✅ Graceful fallback kalau API key tidak ada
- ✅ Retry dengan exponential backoff

---

### T8 — External Providers (HackerOne, Cantina, Code4rena, Sherlock)

**File**:
- `services/02-immunefi/src/providers/hackerone.py` (BARU)
- `services/02-immunefi/src/providers/cantina.py` (BARU)
- `services/02-immunefi/src/providers/code4rena.py` (BARU)
- `services/02-immunefi/src/providers/sherlock.py` (BARU)

**Strategi per provider**:

| Provider | Strategy | API Key? | Priority |
|----------|----------|----------|----------|
| **HackerOne** | Scrape program listing (public) | Optional | 3 |
| **Cantina** | Fetch dari cantina.xyz (public) | No | 4 |
| **Code4rena** | Fetch dari code4rena.com (public) | No | 5 |
| **Sherlock** | Sherlock API (public) | No | 6 |
| **Immunefi Mirror** | GitHub mirror (existing) — fallback | No | 7 (lowest) |

**Parsing per provider** — masing-masing punya format data berbeda. Semua return ke format `list[dict]` dengan keys minimal: `slug`, `name`, `chains`, `maxBounty`.

**Acceptance Criteria**:
- ✅ Setiap provider mengimplementasi `BountyProvider` protocol
- ✅ Semua provider return format yang konsisten (`list[dict]`)
- ✅ Provider yang gagal (network error, rate limit) tidak menghentikan provider lain
- ✅ Logging per provider: sukses/gagal + jumlah program

---

### T9 — Sync: Iterasi Semua Provider

**File**: `services/02-immunefi/src/sync.py` (MODIFIKASI)

**Perubahan `sync_all()`**:
```python
async def sync_all(self, client=None) -> SyncStatus:
    """Sync dari semua provider — merge + deduplicate."""
    all_programs: dict[str, Program] = {}
    provider_stats: dict[str, int] = {}
    
    for provider_cls in PROVIDER_REGISTRY:
        provider = provider_cls(client=client)
        if not provider.is_available():
            log.info("sync.provider_skipped", name=provider.name)
            continue
        
        try:
            raw_list = await provider.fetch_program_list()
            
            for item in raw_list:
                slug = item.get("slug", "") or item.get("id", "")
                if not slug:
                    continue
                
                # Ambil detail (jika provider support)
                detail = None
                try:
                    detail = await provider.fetch_program_detail(slug)
                except Exception:
                    detail = item  # fallback ke list data
                
                # Merge: provider priority lebih tinggi overwrite
                if slug not in all_programs:
                    all_programs[slug] = self._build_program(item, detail)
                else:
                    # Update fields yang ada, tanpa overwrite existing
                    existing = all_programs[slug]
                    merged = self._merge_programs(existing, item, detail, provider.name)
                    all_programs[slug] = merged
            
            provider_stats[provider.name] = len(raw_list)
            log.info("sync.provider_complete", provider=provider.name, count=len(raw_list))
            
        except Exception as e:
            log.warning("sync.provider_failed", provider=provider.name, error=str(e))
            provider_stats[f"{provider.name}_error"] = str(e)[:100]
    
    # Save dengan Enhanced JSON Storage
    self.storage.save_all(all_programs)
    self.storage.rebuild_indexes(all_programs)
    self._programs = all_programs
    
    # ...
```

**Method baru** `_merge_programs()`:
```python
def _merge_programs(self, existing: Program, list_item: dict, detail: dict, source: str) -> Program:
    """Merge data dari provider baru ke program existing.
    - Tidak overwrite field yang sudah punya value
    - Tambah chains, contracts, repos dari semua source
    - Simpan source attribution
    """
    # ... implementasi merge logic
```

**Acceptance Criteria**:
- ✅ Sync jalan untuk semua provider yang available
- ✅ Program yang sama dari provider berbeda di-merge, bukan duplicate
- ✅ Provider failure tidak menghentikan provider lain
- ✅ Log lengkap: per provider, total merged, total unique

---

## 5. Phase 3 — Automated Sync Engine

**Goal**: Sync otomatis tanpa perlu POST manual.

### T10 — Periodic Sync (Background Task)

**File**: `services/02-immunefi/app.py` (MODIFIKASI)

**Implementasi** di `lifespan`:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load programs + start background sync scheduler."""
    # Load existing
    count = len(sync_manager.load_programs())
    log.info("app.startup", count=count)
    
    # Start background sync task
    sync_task = asyncio.create_task(_periodic_sync_loop())
    
    yield
    
    # Cleanup
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass
    log.info("app.shutdown")
```

**Periodic sync loop**:
```python
async def _periodic_sync_loop():
    """Run sync periodically based on config."""
    interval_minutes = 30  # default, bisa dari config
    while True:
        try:
            await asyncio.sleep(interval_minutes * 60)
            
            # Cek dulu apakah ada update (commit hash check)
            async with httpx.AsyncClient(timeout=30.0) as client:
                has_updates = await sync_manager.has_updates(client)
                
                if has_updates:
                    await sync_manager.sync_all(client=client)
                else:
                    log.info("sync.periodic.no_changes")
                    
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error("sync.periodic.error", error=str(e))
            await asyncio.sleep(60)  # Tunggu 1 menit sebelum retry
```

**Config sumber interval**:
1. Environment variable `SYNC_INTERVAL_MINUTES`
2. Config Service 01 (`GET /config/sync_interval`)
3. Default: 30 menit

**Acceptance Criteria**:
- ✅ Sync otomatis berjalan setiap N menit
- ✅ Tidak ada duplikasi sync (cek commit hash dulu)
- ✅ Service tetap bisa serve endpoint selama sync berjalan
- ✅ Graceful shutdown — task dibatalkan saat app mati

---

### T11 — Incremental Sync

**File**: `services/02-immunefi/src/sync.py` (MODIFIKASI — tambah method)

**Method baru** `sync_incremental()`:
```python
async def sync_incremental(self, client) -> SyncStatus:
    """Only fetch programs that changed since last sync.
    
    Untuk Immunefi mirror: compare commit hash → get changed files → sync those only.
    Untuk provider lain: fallback ke full sync.
    """
    last_commit = self.storage.read_meta().get("commit_hash")
    if not last_commit:
        return await self.sync_all(client)  # Full sync first time
    
    # Get latest remote commit
    latest_commit = await self._fetch_latest_commit(client)
    if latest_commit == last_commit:
        return SyncStatus(status="skipped", reason="no_changes")
    
    # Get changed files between commits
    changes = await self._get_changed_files(client, last_commit, latest_commit)
    changed_slugs = [f["slug"] for f in changes if f["type"] == "program"]
    
    # Only sync changed programs
    synced = 0
    for slug in changed_slugs:
        try:
            detail = await scraper.fetch_program_detail(slug)
            program = self._build_program(detail, detail)
            self.storage.save_program(program)
            self._programs[slug] = program
            synced += 1
        except ProgramNotFoundError:
            self._programs.pop(slug, None)
            # Also remove from storage
            prog_file = self.storage.data_dir / "programs" / f"{slug}.json"
            if prog_file.exists():
                prog_file.unlink()
    
    # Update commit hash
    self.storage.write_meta(commit_hash=latest_commit)
    self.storage.rebuild_indexes(self._programs)
    
    return SyncStatus(status="completed", programs_synced=synced)
```

**Method** `_get_changed_files()`:
```python
async def _get_changed_files(self, client, base_sha, head_sha) -> list[dict]:
    """GitHub API compare: get list of changed files between two commits."""
    url = (
        f"https://api.github.com/repos/"
        f"infosec-us-team/Immunefi-Bug-Bounty-Programs-Unofficial/"
        f"compare/{base_sha}...{head_sha}"
    )
    resp = await client.get(url)
    resp.raise_for_status()
    
    files = resp.json().get("files", [])
    changes = []
    for f in files:
        # Parse slug from filename: "project/{slug}.json"
        if f["filename"].startswith("project/") and f["filename"].endswith(".json"):
            slug = f["filename"][8:-5]  # Remove "project/" and ".json"
            changes.append({
                "slug": slug,
                "status": f["status"],  # added, modified, removed
                "filename": f["filename"],
            })
    
    return changes
```

**Acceptance Criteria**:
- ✅ Incremental sync hanya fetch program yang berubah
- ✅ Program yang dihapus di remote juga dihapus lokal
- ✅ Kalau first-time atau commit hash hilang, fallback ke full sync
- ✅ Jauh lebih cepat dari full sync (2-5 detik vs 2-5 menit)

---

### T12 — Sync Schedule Endpoints

**File**: `services/02-immunefi/app.py` (MODIFIKASI)

**Endpoint baru**:
```python
@router.get("/sync/schedule")
async def get_sync_schedule() -> ApiResponse:
    """Lihat jadwal sync yang aktif."""
    return ok({
        "interval_minutes": sync_manager.interval_minutes,
        "next_sync_at": sync_manager.next_sync_at,
        "last_sync": sync_manager.last_synced,
        "sync_mode": "incremental" if sync_manager._commit_hash else "full",
        "state": "running" if sync_manager._sync_task and not sync_manager._sync_task.done() else "idle",
    })


@router.put("/sync/schedule")
async def update_sync_schedule(interval: int = Body(..., ge=5, le=1440)) -> ApiResponse:
    """Update interval sync (menit)."""
    sync_manager.interval_minutes = interval
    # Simpan ke config
    await save_config("sync_interval_minutes", interval)
    return ok({"interval_minutes": interval})


@router.post("/sync/trigger")
async def trigger_immediate_sync() -> ApiResponse:
    """Trigger sync immediately, outside of schedule."""
    sync_id = str(uuid.uuid4())
    asyncio.create_task(_run_background_sync(sync_id))
    return ok({"sync_id": sync_id, "status": "triggered"})
```

**Acceptance Criteria**:
- ✅ `GET /sync/schedule` return konfigurasi sync saat ini
- ✅ `PUT /sync/schedule` update interval, persist ke config
- ✅ `POST /sync/trigger` trigger sync langsung

---

### T13 — History + Contracts + Chains Endpoints

**File**: `services/02-immunefi/app.py` (MODIFIKASI)

**Endpoint baru**:
```python
@router.get("/programs/{slug}/history")
async def get_program_history(slug: str, days: int = Query(30, ge=1, le=365)) -> ApiResponse:
    """Lihat perubahan program dalam N hari terakhir."""
    program = sync_manager.programs.get(slug)
    if not program:
        raise HTTPException(404, "Program not found")
    
    history = sync_manager.storage.get_history(slug)
    
    # Filter by days
    if days and history:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        history = [
            h for h in history
            if datetime.fromisoformat(h["timestamp"]) > cutoff
        ]
    
    return ok({
        "slug": slug,
        "name": program.name,
        "history": history,
        "total_changes": len(history),
    })


@router.get("/programs/{slug}/contracts")
async def get_program_contracts(slug: str) -> ApiResponse:
    """List semua kontrak yang terkait dengan program."""
    program = sync_manager.programs.get(slug)
    if not program:
        raise HTTPException(404, "Program not found")
    
    return ok({
        "slug": slug,
        "name": program.name,
        "contracts": [c.model_dump(mode="json") for c in program.contracts],
        "total": len(program.contracts),
    })


@router.get("/programs/chains")
async def list_chains() -> ApiResponse:
    """List unique chains dari semua program + count."""
    programs = sync_manager.programs.values()
    chains: dict[str, int] = {}
    for p in programs:
        for c in p.chains:
            chains[c] = chains.get(c, 0) + 1
    
    return ok({
        "chains": [
            {"name": k, "program_count": v}
            for k, v in sorted(chains.items(), key=lambda x: -x[1])
        ],
        "total": len(chains),
    })


@router.get("/sync/log")
async def get_sync_log(limit: int = Query(20, ge=1, le=100)) -> ApiResponse:
    """Lihat history sync operations."""
    log_path = sync_manager.storage.data_dir / "sync_log.jsonl"
    if not log_path.exists():
        return ok({"entries": [], "total": 0})
    
    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    entries = [json.loads(l) for l in lines[-limit:][::-1]]
    return ok({"entries": entries, "total": len(lines)})
```

**Acceptance Criteria**:
- ✅ Semua endpoint baru return response konsisten dengan format `ApiResponse`
- ✅ Error handling 404 untuk program tidak ditemukan
- ✅ History bisa difilter by days
- ✅ Chains di-sort descending by count

---

## 6. Phase 4 — Intelligence Layer

### T14 — Program Scoring Engine

**File**: `services/02-immunefi/src/intelligence/scoring.py` (BARU)

**Kelas**: `ProgramScorer`

**Scoring dimensions**:
| Dimension | Weight | Source | Description |
|-----------|--------|--------|-------------|
| `bounty_attractiveness` | 30% | `max_bounty` | Higher bounty = higher priority |
| `contract_complexity` | 20% | `contracts[]` | Contract count + complexity signals |
| `chain_popularity` | 15% | `chains[]` | Ethereum > Arbitrum > others |
| `repo_quality` | 15% | `repos[]` | Ada GitHub repo? Tests? Stars? |
| `freshness` | 10% | `updated_at` | Program baru lebih menarik |
| `multi_source` | 10% | Provider data | Program yang muncul di banyak provider |

```python
class ProgramScorer:
    """Score setiap program berdasarkan multiple dimensions."""
    
    def score(self, program: Program) -> dict:
        return {
            "slug": program.slug,
            "overall": self._calculate_overall(program),
            "dimensions": {
                "bounty_attractiveness": self._bounty_score(program),
                "contract_complexity": self._complexity_score(program),
                "chain_popularity": self._chain_score(program),
                "repo_quality": self._repo_score(program),
                "freshness": self._freshness_score(program),
                "multi_source": self._source_score(program),
            },
            "recommendation": self._recommend_action(overall_score),
        }
    
    def _bounty_score(self, p: Program) -> float:
        bounty = p.max_bounty or 0
        if bounty >= 1_000_000: return 1.0
        if bounty >= 100_000: return 0.8
        if bounty >= 10_000: return 0.5
        if bounty >= 1_000: return 0.2
        return 0.0
    
    def _recommend_action(self, score: float) -> str:
        if score >= 0.8: return "audit_immediately"
        if score >= 0.5: return "high_priority"
        if score >= 0.3: return "medium_priority"
        return "low_priority"
```

**Acceptance Criteria**:
- ✅ Score dihitung dari semua dimensi
- ✅ Overall score 0.0 - 1.0
- ✅ Recommendation actionable
- ✅ Bisa di-call untuk satu program atau semua program

---

### T15 — Trend Analyzer

**File**: `services/02-immunefi/src/intelligence/trends.py` (BARU)

**Kelas**: `TrendAnalyzer`

```python
class TrendAnalyzer:
    """Analisis tren dari historical data (history/{slug}.jsonl)."""
    
    async def analyze(self, storage: EnhancedJSONStorage) -> dict:
        return {
            "new_programs": await self._detect_new(storage, days=7),
            "closed_programs": await self._detect_closed(storage, days=7),
            "bounty_changes": await self._detect_bounty_changes(storage, days=7),
            "hot_chains": await self._hot_chains(storage),
            "summary": "...",
        }
    
    async def _detect_new(self, storage, days: int) -> list[dict]:
        """Program yang baru muncul dalam N hari."""
        # Dari history: cari first entry dalam N hari terakhir
        # Atau dari _meta.json: created_at field
        ...
    
    async def _detect_bounty_changes(self, storage, days: int) -> list[dict]:
        """Program yang bounty-nya naik/turun."""
        # Bandingkan snapshot pertama dan terakhir dalam range
        ...
```

**Acceptance Criteria**:
- ✅ Bounty changes terdeteksi dari diff history
- ✅ Hot chains di-rank by program count + bounty total
- ✅ Output format siap untuk dashboard

---

### T16 — Anomaly Detection + Alerts

**File**: `services/02-immunefi/src/intelligence/alerts.py` (BARU)

**Kelas**: `AlertEngine`

```python
class AlertEngine:
    """Deteksi anomali dan generate alerts."""
    
    async def check(self, storage, programs) -> list[dict]:
        alerts = []
        
        # 1. High-value new program
        new_progs = await self._detect_new(storage, days=1)
        for p in new_progs:
            if p.max_bounty and p.max_bounty >= 100_000:
                alerts.append({
                    "type": "high_value_new_program",
                    "severity": "high",
                    "message": f"New program: {p.name} — ${p.max_bounty:,.0f} bounty",
                    "slug": p.slug,
                })
        
        # 2. Bounty increase on tracked program
        increases = await self._detect_bounty_increases(storage, days=7)
        for p in increases:
            alerts.append({
                "type": "bounty_increased",
                "severity": "medium",
                "message": f"{p['name']} bounty increased: ${p['old_bounty']:,.0f} → ${p['new_bounty']:,.0f}",
                "slug": p["slug"],
            })
        
        # 3. Program closed (sudah tidak aktif)
        closed = await self._detect_closed(storage, days=1)
        for p in closed:
            alerts.append({
                "type": "program_closed",
                "severity": "low",
                "message": f"Program closed: {p.name}",
                "slug": p.slug,
            })
        
        return alerts
```

**Acceptance Criteria**:
- ✅ Alert untuk high-value program baru
- ✅ Alert untuk bounty increase
- ✅ Alert untuk program closed
- ✅ Format alert konsisten

---

### T17 — Repo Deep Intelligence

**File**: `services/02-immunefi/src/intelligence/repo_analyzer.py` (BARU)

```python
class RepoDeepAnalyzer:
    """Analisis mendalam GitHub repository via GitHub API."""
    
    async def analyze(self, repo: Repo) -> dict:
        """Analyze a single GitHub repo using GitHub API."""
        return {
            "url": repo.url,
            "stars": await self._get_stargazers(repo),
            "forks": await self._get_forks(repo),
            "last_commit": await self._get_last_commit(repo),
            "open_issues": await self._count_open_issues(repo),
            "security": {
                "dependabot_alerts": await self._get_dependabot_alerts(repo),
                "codeql_findings": await self._get_codeql_findings(repo),
            },
            "activity": {
                "commit_frequency_30d": await self._get_commit_frequency(repo, 30),
                "contributors": await self._count_contributors(repo),
            },
            "audit_history": {
                "previous_audits": await self._find_previous_audits(repo),
            },
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def _get_stargazers(self, repo: Repo) -> int:
        """GET /repos/{owner}/{repo} → stargazers_count."""
        ...
    
    async def _get_dependabot_alerts(self, repo: Repo) -> list:
        """GET /repos/{owner}/{repo}/dependabot/alerts."""
        # Requires token with `security_events` scope
        ...
```

**GitHub API Rate Limit**:
- Without token: 60 req/hour — tidak cukup
- With token: 5,000 req/hour — cukup untuk batch analisis
- Cache hasil di `indexes/repo_intel/{owner}_{repo}.json`

**Acceptance Criteria**:
- ✅ Basic repo info (stars, forks, last commit)
- ✅ Security info dari GitHub API
- ✅ Cache hasil analisis (tidak re-fetch setiap kali)
- ✅ Graceful handling kalau GitHub API rate limited

---

### T18 — Intelligence Endpoints

**File**: `services/02-immunefi/app.py` (MODIFIKASI)

```python
@router.get("/programs/{slug}/intelligence")
async def get_program_intelligence(slug: str) -> ApiResponse:
    """Full intelligence score untuk satu program."""
    program = sync_manager.programs.get(slug)
    if not program:
        raise HTTPException(404, "Program not found")
    
    scorer = ProgramScorer()
    score = scorer.score(program)
    
    # Tambah repo analysis jika ada repo
    repo_intel = None
    if program.repos:
        analyzer = RepoDeepAnalyzer()
        try:
            repo_intel = await analyzer.analyze(program.repos[0])
        except Exception as e:
            repo_intel = {"error": str(e)}
    
    return ok({
        "score": score,
        "repo_intelligence": repo_intel,
    })


@router.get("/programs/recommendations")
async def get_program_recommendations(
    min_bounty: float = Query(10000, ge=0),
    chain: str = Query(None),
    limit: int = Query(10, ge=1, le=50),
) -> ApiResponse:
    """Rekomendasi program berdasarkan preference."""
    programs = list(sync_manager.programs.values())
    
    # Filter
    if min_bounty:
        programs = [p for p in programs if (p.max_bounty or 0) >= min_bounty]
    if chain:
        programs = [p for p in programs if chain.lower() in [c.lower() for c in p.chains]]
    
    # Score + sort
    scorer = ProgramScorer()
    scored = [(p, scorer.score(p)) for p in programs]
    scored.sort(key=lambda x: x[1]["overall"], reverse=True)
    
    return ok({
        "recommendations": [
            {"program": p.model_dump(mode="json"), "score": s}
            for p, s in scored[:limit]
        ],
        "total_matching": len(scored),
    })


@router.get("/programs/trends")
async def get_trends(days: int = Query(30, ge=1, le=365)) -> ApiResponse:
    """Trend analysis untuk semua program."""
    analyzer = TrendAnalyzer()
    trends = await analyzer.analyze(sync_manager.storage)
    return ok(trends)


@router.get("/programs/alerts")
async def get_alerts() -> ApiResponse:
    """Alert untuk high-value programs baru, bounty changes, dll."""
    engine = AlertEngine()
    alerts = await engine.check(sync_manager.storage, sync_manager.programs)
    return ok({"alerts": alerts, "total": len(alerts)})
```

**Acceptance Criteria**:
- ✅ Semua endpoint return format konsisten
- ✅ Error handling untuk program tidak ditemukan
- ✅ Performance: endpoints harus < 100ms (gunakan index cache)

---

## 7. Phase 5 — Cross-Service Integration

### T19 — Contract Auto-Fetch (→ 03-source)

**File**: `services/02-immunefi/src/intelligence/contract_fetcher.py` (BARU)

```python
class ContractAutoFetcher:
    """Auto-fetch source code via 03-source service untuk semua kontrak baru."""
    
    SOURCE_SERVICE_URL = "http://03-source:8002"
    
    async def fetch_all_new_contracts(self):
        """Iterasi semua program, fetch source untuk kontrak yang belum."""
        for program in self.active_programs:
            for contract in program.contracts:
                if await self._already_fetched(contract):
                    continue
                
                source = await self._fetch_source(contract)
                if source:
                    await self._record_fetch(contract, source)
                    await self._notify_orchestrator(program.slug, contract)
    
    async def _fetch_source(self, contract: Contract) -> dict | None:
        """POST /fetch ke 03-source service."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.SOURCE_SERVICE_URL}/fetch",
                json={
                    "chain": contract.chain,
                    "address": contract.address,
                },
            )
            if resp.status_code == 200:
                return resp.json().get("data")
            return None
    
    async def _notify_orchestrator(self, slug: str, contract: Contract):
        """Notify 11-orchestrator untuk trigger scan pipeline."""
        ...
```

**Cache tracker**: `indexes/fetched_contracts.json` — simpan address yang sudah di-fetch.
Ini penting agar tidak re-fetch kontrak yang sama setiap sync.

**Acceptance Criteria**:
- ✅ Call 03-source untuk fetch source kontrak baru
- ✅ Skip kontrak yang sudah pernah di-fetch (cache)
- ✅ Logging: kontrak di-fetch, sukses/gagal

---

### T20 — Scan Trigger (→ 11-orchestrator)

**File**: `services/02-immunefi/src/intelligence/contract_fetcher.py` (lanjutan)

```python
async def trigger_scan(self, slug: str, contract: Contract):
    """Kirim ke orchestrator untuk full scan pipeline."""
    ORCHESTRATOR_URL = "http://11-orchestrator:8000"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{ORCHESTRATOR_URL}/audit",
            json={
                "immunefi_program_id": slug,
                "contract_addresses": [contract.address],
                "chain": contract.chain,
                "source": contract.source,
            },
        )
        if resp.status_code == 200:
            audit = resp.json()
            await self._track_audit(slug, contract, audit["audit_id"])
```

**Acceptance Criteria**:
- ✅ POST ke `/audit` orchestrator dengan data yang benar
- ✅ Tracking: audit_id dicatat di storage 02-immunefi
- ✅ Error handling kalau orchestrator down

---

### T21 — Fork-Aware Source Provider (03-source patch)

**File**: `services/03-source/src/providers/fork_aware.py` (BARU)

```python
class ForkAwareGitHubProvider:
    """GitHub provider yang cek fork dulu sebelum clone dari original.
    
    Priority: lebih tinggi dari GitHubProvider biasa.
    """
    name = "fork_aware_github"
    priority = 0  # Even higher than regular GitHub
    
    def __init__(self):
        self.fork_index_path = Path("/data/immunefi/indexes/forks.json")
    
    async def fetch(self, chain: str, address: str) -> SourceResult | None:
        """Cek apakah address ini ada di repo yang sudah di-fork."""
        # 1. Cari repo yang mengandung address ini
        repo_info = await self._find_repo_for_address(chain, address)
        if not repo_info:
            return None
        
        # 2. Cek apakah repo sudah di-fork
        fork_url = await self._get_fork_url(repo_info["owner"], repo_info["repo"])
        if not fork_url:
            return None
        
        # 3. Fetch dari fork
        return await self._fetch_from_github(fork_url, address)
    
    async def _get_fork_url(self, owner: str, repo: str) -> str | None:
        """Read fork index from 02-immunefi storage."""
        if not self.fork_index_path.exists():
            return None
        
        forks = json.loads(self.fork_index_path.read_text())
        key = f"{owner}/{repo}"
        if key in forks:
            return forks[key]["clone_url"]
        return None
```

**Acceptance Criteria**:
- ✅ Cek fork index sebelum fetch dari original
- ✅ Fallback ke provider normal kalau tidak ada fork
- ✅ Tidak perlu API call ke GitHub — baca dari index file

---

## 8. Phase 6 — Repository Forking

### T22 — GitHubForkClient

**File**: `services/02-immunefi/src/github_fork.py` (BARU)

**Kelas**: `GitHubForkClient`

**Methods**:
| Method | Deskripsi |
|--------|-----------|
| `fork_repo(owner, repo)` | Fork single repo → return fork info |
| `fork_multiple(repos)` | Batch fork banyak repo |
| `check_fork_exists(owner, repo)` | Cek apakah sudah pernah di-fork |
| `delete_fork(owner, repo)` | Hapus fork (butuh token dengan scope `delete_repo`) |
| `get_username()` | Ambil username dari token |

**Token management**:
1. Cek env var `GITHUB_TOKEN`
2. Kalau tidak ada, cek dari 01-config service
3. Kalau tidak ada, raise `RuntimeError("GITHUB_TOKEN diperlukan")`

**Acceptance Criteria**:
- ✅ Fork single repo via GitHub API
- ✅ Batch fork dengan error isolation (satu gagal, lainnya lanjut)
- ✅ Cek fork existing sebelum fork ulang
- ✅ Error handling untuk rate limit, 403, 404

---

### T23 — Fork Endpoints

**File**: `services/02-immunefi/app.py` (MODIFIKASI)

**Endpoint baru**:
```python
@router.post("/programs/{slug}/fork")
async def fork_program_repos(slug: str) -> ApiResponse:
    """Fork semua repo dari program tertentu."""
    program = sync_manager.programs.get(slug)
    if not program:
        raise HTTPException(404, "Program not found")
    
    github = GitHubForkClient()
    try:
        repos_data = [
            {"owner": r.owner, "repo": r.repo}
            for r in program.repos if r.owner and r.repo
        ]
        if not repos_data:
            raise HTTPException(400, "No detectable GitHub repos")
        
        results = await github.fork_multiple(repos_data)
        
        # Save fork index
        fork_index = {}
        for r in results:
            if r["status"] == "success":
                fork_index[r["original"]] = r
        sync_manager.save_fork_index(fork_index)
        
        return ok({
            "program": slug,
            "results": results,
            "successful": sum(1 for r in results if r["status"] == "success"),
            "failed": sum(1 for r in results if r["status"] == "failed"),
        })
    finally:
        await github.close()


@router.get("/programs/{slug}/forks")
async def list_program_forks(slug: str) -> ApiResponse:
    """Lihat status fork dari program."""
    fork_index = sync_manager.load_fork_index()
    program = sync_manager.programs.get(slug)
    if not program:
        raise HTTPException(404, "Program not found")
    
    forks = []
    for repo in program.repos:
        key = f"{repo.owner}/{repo.repo}"
        forks.append({
            "original": key,
            **fork_index.get(key, {"forked": False}),
        })
    
    return ok({"program": slug, "forks": forks})
```

**Fork index storage**: `indexes/forks.json`

**Acceptance Criteria**:
- ✅ POST fork → fork semua repo → save index
- ✅ GET forks → baca dari index, tanpa API call
- ✅ Error 400 kalau program tidak punya repo
- ✅ Error 404 kalau program tidak ditemukan

---

### T24 — Fork Integration with 03-source

**File**: `services/02-immunefi/src/github_fork.py` (tambah method)

Method `get_fork_clone_url()` untuk 03-source:
```python
async def get_fork_clone_url(self, owner: str, repo: str) -> str | None:
    """Dapatkan clone URL dari fork. Return None jika belum di-fork."""
    username = await self._get_username()
    resp = await self.client.get(
        f"https://api.github.com/repos/{username}/{repo}"
    )
    if resp.status_code == 200:
        return resp.json().get("clone_url")
    return None
```

**Updated di** `ForkAwareSourceProvider` (T21) untuk menggunakan method ini.

**Acceptance Criteria**:
- ✅ `get_fork_clone_url()` return URL yang valid
- ✅ Return None kalau belum di-fork

---

### T25 — Fork Integration with 08-exploit

**File**: `services/02-immunefi/src/github_fork.py` (tambah method)

```python
async def push_poc_to_fork(
    self,
    owner: str,
    repo: str,
    finding_id: str,
    poc_code: str,
) -> bool:
    """Push PoC exploit sebagai file ke repo fork di branch poc/{finding_id}.
    
    GitHub API: PUT /repos/{owner}/{repo}/contents/{path}
    """
    path = f"pocs/{finding_id}.t.sol"
    content = base64.b64encode(poc_code.encode()).decode()
    
    resp = await self.client.put(
        f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
        json={
            "message": f"PoC: {finding_id}",
            "content": content,
            "branch": f"poc/{finding_id}",
        },
    )
    return resp.status_code == 201
```

**Acceptance Criteria**:
- ✅ Push PoC file ke repo fork
- ✅ Branch name: `poc/{finding_id}`
- ✅ Error handling kalau branch sudah ada

---

## 9. File Map — Perubahan + File Baru

### Files Baru

| File | Phase | Est. Lines |
|------|-------|-----------|
| `services/02-immunefi/src/storage.py` | P1 | ~200 |
| `services/02-immunefi/src/providers/__init__.py` | P2 | ~60 |
| `services/02-immunefi/src/providers/immunefi_official.py` | P2 | ~100 |
| `services/02-immunefi/src/providers/hackerone.py` | P2 | ~80 |
| `services/02-immunefi/src/providers/cantina.py` | P2 | ~60 |
| `services/02-immunefi/src/providers/code4rena.py` | P2 | ~60 |
| `services/02-immunefi/src/providers/sherlock.py` | P2 | ~60 |
| `services/02-immunefi/src/intelligence/__init__.py` | P4 | ~10 |
| `services/02-immunefi/src/intelligence/scoring.py` | P4 | ~120 |
| `services/02-immunefi/src/intelligence/trends.py` | P4 | ~100 |
| `services/02-immunefi/src/intelligence/alerts.py` | P4 | ~80 |
| `services/02-immunefi/src/intelligence/repo_analyzer.py` | P4 | ~150 |
| `services/02-immunefi/src/intelligence/contract_fetcher.py` | P5 | ~100 |
| `services/02-immunefi/src/github_fork.py` | P6 | ~180 |
| `tests/test_immunefi_storage.py` | P1 | ~150 |
| `services/03-source/src/providers/fork_aware.py` | P5+6 | ~80 |
| **Total baru** | | **~1,590** |

### Files Dimodifikasi

| File | Phase | Perubahan |
|------|-------|-----------|
| `services/02-immunefi/src/sync.py` | P1, P2, P3 | Refactor: SyncManager → EnhancedJSONStorage. Tambah: multi-provider sync, incremental sync, merge, sync log |
| `services/02-immunefi/src/models.py` | P1, P2 | Tambah: `ProviderStatus` |
| `services/02-immunefi/app.py` | P1, P3, P4, P5, P6 | Tambah: lifespan sync task, 10+ endpoints |
| `services/02-immunefi/Dockerfile` | — | Tidak perlu diubah |
| `services/02-immunefi/requirements.txt` | P2 | Mungkin tambah dependency (kalau ada) |
| `services/03-source/src/detector.py` | P5+P6 | Tambah ForkAwareGitHubProvider ke registry |
| `IMPLEMENTATION_PLAN.md` | — | Tambah cross-reference ke plan ini |

---

## 10. Cross-Service Impact Analysis

### Service 01 — Config

**Impact**: Low
- **Dari**: — (tidak ada dependensi)
- **Ke**: 02-immunefi perlu baca API keys (Immunefi, GitHub) dari 01-config
- **Endpoint dipakai**: `GET /config/{key}`
- **Keys baru**: `immunefi_api_key`, `github_token`, `sync_interval_minutes`

### Service 03 — Source

**Impact**: Medium
- **Dari**: — (tidak tergantung 02-immunefi)
- **Ke**: 
  - 02-immunefi panggil `POST /fetch` untuk kontrak baru (T19)
  - 03-source bisa baca fork index dari 02-immunefi (T21, T24)
- **Endpoint baru di 03**: Tidak perlu — pakai existing `POST /fetch`
- **File baru di 03**: `src/providers/fork_aware.py`

### Service 11 — Orchestrator

**Impact**: Low-Medium
- **Dari**: — (tidak tergantung 02-immunefi)
- **Ke**: 02-immunefi trigger scan via `POST /audit` (T20)
- **Endpoint dipakai**: `POST /audit` (existing)
- **Catatan**: 02-immunefi hanya trigger, orchestrator tetap manage pipeline sendiri

### Service 06 — AI

**Impact**: None saat ini
- Belum ada integrasi langsung. Nanti di Level 4 (AI matching) baru butuh.

### Service 08 — Exploit

**Impact**: Low
- **Ke**: 02-immunefi push PoC ke repo fork (T25)
- **Via**: `GitHubForkClient.push_poc_to_fork()`
- **Catatan**: Ini langsung ke GitHub API, bukan melalui 08-exploit service

### Service 15 — Dashboard

**Impact**: None saat ini
- Endpoint intelligence, trend, alerts bisa dipakai dashboard nanti
- Tapi untuk sekarang, 02-immunefi standalone dulu

---

## 11. Daftar Lengkap Tasks

| # | Task | File | Est. | Depends On |
|---|------|------|------|------------|
| **Phase 1 — Foundation** | | | | |
| T1 | EnhancedJSONStorage class | `src/storage.py` (B) | 10 min | — |
| T2 | Legacy migration handler | `src/storage.py` (T1) | 5 min | T1 |
| T3 | Refactor SyncManager | `src/sync.py` (M) | 5 min | T1 |
| T4 | Refactor app.py (minor) | `app.py` (M) | 3 min | T3 |
| T5 | Unit tests storage | `tests/test_immunefi_storage.py` (B) | 7 min | T1 |
| **Phase 2 — Multi-Source** | | | | |
| T6 | Provider protocol + registry | `src/providers/__init__.py` (B) | 5 min | T3 |
| T7 | ImmunefiOfficialProvider | `src/providers/immunefi_official.py` (B) | 7 min | T6 |
| T8 | HackerOne, Cantina, C4, Sherlock | `src/providers/*.py` (B) | 10 min | T6 |
| T9 | Sync: iterate all providers | `src/sync.py` (M) | 5 min | T7, T8 |
| **Phase 3 — Auto Sync** | | | | |
| T10 | Periodic sync (background task) | `app.py` (M) | 5 min | T9 |
| T11 | Incremental sync | `src/sync.py` (M) | 5 min | T10 |
| T12 | Sync schedule endpoints | `app.py` (M) | 3 min | T10 |
| T13 | History + contracts + chains | `app.py` (M) | 5 min | T3 |
| **Phase 4 — Intelligence** | | | | |
| T14 | Program scoring engine | `src/intelligence/scoring.py` (B) | 8 min | T3 |
| T15 | Trend analyzer | `src/intelligence/trends.py` (B) | 7 min | T3 |
| T16 | Anomaly detection + alerts | `src/intelligence/alerts.py` (B) | 5 min | T15 |
| T17 | Repo deep intelligence | `src/intelligence/repo_analyzer.py` (B) | 8 min | T3 |
| T18 | Intelligence endpoints | `app.py` (M) | 7 min | T14-T17 |
| **Phase 5 — Cross-Service** | | | | |
| T19 | Contract auto-fetch (→ 03) | `src/intelligence/contract_fetcher.py` (B) | 5 min | T3 |
| T20 | Scan trigger (→ 11) | `src/intelligence/contract_fetcher.py` (T19) | 3 min | T19 |
| T21 | Fork-aware 03-source provider | `services/03-source/.../fork_aware.py` (B) | 5 min | T24 |
| **Phase 6 — Forking** | | | | |
| T22 | GitHubForkClient | `src/github_fork.py` (B) | 8 min | — |
| T23 | Fork endpoints (POST + GET) | `app.py` (M) | 5 min | T22 |
| T24 | Fork-aware source provider | `src/github_fork.py` (M) | 3 min | T22 |
| T25 | Exploit PoC push | `src/github_fork.py` (M) | 3 min | T22 |
| | **Total** | | **~146 min** | |

> **Legend**: (B) = Baru, (M) = Modifikasi

### Execution Order Recommendation

Untuk **personal use**, urutan yang paling memberi value cepat:

```
Priority 1 (Hari ini juga):
  T1  → T2 → T3 → T4 → T5    [Storage upgrade — zero risk, immediate benefit]
  
Priority 2 (Besok):
  T10 → T11 → T12 → T13       [Auto sync — tidak perlu manual POST lagi]
  
Priority 3:
  T6  → T7 → T9               [Multi-source — dapat program dari mana saja]
  
Priority 4:
  T14 → T15 → T16 → T18       [Intelligence — tahu program mana yang must audit]
  
Priority 5:
  T22 → T23 → T24             [Forking — clone repo ke akun pribadi]
  
Priority 6:
  T19 → T20                    [Auto-trigger scan pipeline]
```

### Filsafat Eksekusi

```
1. Setiap task harus bisa di-commit sendiri-sendiri
   → git commit -m "T1: EnhancedJSONStorage class"
   
2. Setiap task harus ada acceptance criteria yang jelas
   → Tahu kapan "selesai"

3. Jangan takut refactor — ini personal app, bukan production SaaS
   → Tidak ada SLA, tidak ada user yang complain

4. Test setelah setiap task (pytest)
   → Kalau test merah, jangan lanjut ke task berikutnya

5. Kalau macet > 10 menit di satu task → skip dulu, lanjut task lain
   → Blocking task biasanya karena kurang informasi
```

---

> **Plan ini siap dieksekusi**. Setiap task bisa dikerjakan dalam 3-10 menit.
> Total ~25 tasks, ~2.5 jam kerja efektif.
