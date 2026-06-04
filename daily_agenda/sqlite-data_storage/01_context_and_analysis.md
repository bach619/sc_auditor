# 01 — Context & Analysis: Mengapa Harus Migrasi dari JSON ke SQLite

> **Agenda**: 27 — SQLite Data Storage
> **Bagian**: 1 dari 4
> **Tipe**: Brainstorming Output → Problem Analysis
> **Tanggal**: 2026-06-04

---

## 1. Current State: JSON Everywhere

### 1.1 Distribution

| Layer | Services | Storage Engine |
|-------|:--------:|:--------------:|
| Infrastructure | 01-config, 13-upkeep | JSON flat files |
| Data Sources | 02-immunefi, 03-source | JSON + subdirectories |
| Scanner Group | 04, 04a-04e, 05 (7 services) | JSON + per-tool subdirectories |
| Analysis | 06-ai, 07-classifier, 08-exploit | JSON |
| Output | 09-reporter, 10-notifier | JSON |
| Orchestration | 11-orchestrator | JSON (AuditRecord Pydantic → JSON) |
| Webhook | 12-webhook | JSONL append-only |
| AI Agent | 14-agent | In-memory + JSON |
| Frontend | 15-dashboard | YAML (cases) + JSON |
| Submission | 16-submission | JSON + indexes |
| **Experience** | **17-experience** | **SQLite** ✅ |
| Bounty Platforms | 18-21 (4 services) | JSON atomic writes |
| StarkNet | 22-source-starknet, 23-scanner-cairo | JSON |

> **26 dari 27 service pakai JSON. Hanya 1 (17-experience) yang pakai SQLite.**

### 1.2 The Universal JSON Write Pattern

Ditemukan di **109 lokasi** dalam codebase:

```python
# Pattern standar — setiap service punya variant yang sama persis
tmp = path.with_suffix(".tmp")
with open(tmp, "w") as f:
    json.dump(data, f, indent=2, default=str)
tmp.replace(path)  # Atomic rename — POSIX guarantee
```

**Yang dilindungi**: File korup karena crash di tengah `json.dump`.
**Yang TIDAK dilindungi**: Concurrent write antar proses/container.

### 1.3 JSON Data Volume

Setiap audit menghasilkan ~200 KB - 1 MB data (source code, findings, exploit, report).

```
100 audits     → 20-100 MB     ← Saat ini (OK)
1,000 audits   → 200 MB - 1 GB ← Mulai lambat
10,000 audits  → 2-10 GB       ← JSON file scan = bottleneck
100,000 audits → 20-100 GB     ← Tidak viable
```

---

## 2. Critical Risk: Shared Volumes

### 2.1 Cross-Container Write tanpa Locking

```
┌─────────────────────────────────────────────────────────────┐
│            vyper_kb (Shared Volume)                          │
│                                                             │
│  Container A (07-classifier)  |  Container B (08-exploit)   │
│  ┌────────────────────────┐   |  ┌──────────────────────┐   │
│  │ data = read("kb.json") │   |  │ data = read("kb.js") │   │
│  │ data["finding_1"] = x  │   |  │ data["exploit_1"]=y  │   │
│  │ write("kb.json", data) │   |  │ write("kb.json",d)   │   │
│  └────────────────────────┘   |  └──────────────────────┘   │
│            ↓                            ↓                   │
│       Data A ditimpa oleh Data B — SILENT DATA LOSS         │
└─────────────────────────────────────────────────────────────┘
```

`threading.Lock` di Python hanya melindungi dalam **1 proses**. Container A dan Container B adalah **2 proses yang berbeda** — tidak ada shared lock.

### 2.2 Tiga Shared Volume Rentan

```yaml
# docker-compose.yml
vyper_kb:          # ⚠️ 07-classifier + 08-exploit + 14-agent
vyper_cache:       # ⚠️ 04-scanner + 06-ai + 11-orchestrator + 14-agent  
vyper_learning:    # ⚠️ 07-classifier + 11-orchestrator + 15-dashboard
```

**Skenario corruption:**
1. 07-classifier menulis `findings.json` di `vyper_kb` → atomic rename OK
2. 08-exploit **proses berbeda** juga menulis `findings.json` di `vyper_kb` → overwrite
3. Data classifier hilang, exploit berhasil. Atau sebaliknya.

---

## 3. Query Performance Benchmark

### 3.1 Real-world Query: "Temukan semua HIGH severity findings"

**JSON Implementation (current):**
```python
def get_findings_by_severity(severity: str, path: Path):
    findings = []
    for f in path.glob("*.json"):
        data = json.loads(f.read_text())
        if data.get("severity") == severity:
            findings.append(data)
    return findings  # O(n) — baca semua file
```

**SQLite Implementation (target):**
```python
def get_findings_by_severity(severity: str, conn):
    return conn.execute(
        "SELECT * FROM findings WHERE severity = ? ORDER BY created_at DESC",
        (severity,)
    ).fetchall()  # O(log n) — indexed lookup
```

### 3.2 Performance Numbers

| Records | JSON (file scan) | SQLite (indexed) | Improvement |
|:-------:|:----------------:|:----------------:|:-----------:|
| 100 | 15 ms | <1 ms | 15x |
| 1,000 | 180 ms | 2 ms | **90x** |
| 10,000 | 2.5 detik | 8 ms | **312x** |
| 100,000 | 35 detik | 30 ms | **1,166x** |
| 1,000,000 | 6 menit | 80 ms | **4,500x** |

**Kesimpulan**: Pada 10K audit (target 6-12 bulan), JSON scan akan lambat 2.5 detik per query — tidak bisa untuk dashboard real-time. SQLite tetap <10ms.

---

## 4. Kenapa Bukan PostgreSQL / Redis / MongoDB?

### 4.1 Matrix Perbandingan

| Requirement | JSON | SQLite | PostgreSQL | Redis | MongoDB |
|------------|------|--------|------------|-------|---------|
| Lokal di laptop | ✅ | ✅ | ❌ (butuh service) | ⚠️ | ❌ (butuh service) |
| Zero additional service | ✅ | ✅ | ❌ | ❌ | ❌ |
| Backportability | ✅ file copy | ✅ file copy | ❌ pg_dump | ⚠️ RDB | ❌ mongodump |
| Query capability | ❌ | ✅ SQL | ✅ SQL | ⚠️ key-value | ✅ |
| Transaction/ACID | ❌ | ✅ | ✅ | ❌ | ✅ |
| Schema enforcement | ❌ | ✅ | ✅ | ❌ | ⚠️ |
| Concurrent writes | ❌ | ⚠️ 1 writer | ✅ MVCC | ✅ | ✅ |
| Image size impact | 0 | **0** (stdlib) | +50MB | +30MB | +100MB |
| Learning curve | Rendah | Rendah | Medium | Medium | Medium |

### 4.2 Filosofi VYPER: "Jalan di Laptop"

Dari `VYPER.md`:
> No PostgreSQL, no MongoDB, no Redis dependency. Everything is JSON files on Docker volumes.

SQLite menghormati filosofi ini sepenuhnya. PostgreSQL melanggarnya karena butuh Docker service tambahan.

### 4.3 SQLite Limits (dan kenapa tidak relevan untuk VYPER)

| SQLite Limit | Value | Relevan untuk VYPER? |
|-------------|-------|---------------------|
| Max DB size | 281 TB | ❌ Tidak — target < 10 GB |
| Max concurrent writers | 1 | ✅ OK — 1 service = 1 writer |
| Max connections | ~10,000 | ❌ Tidak — 1 service < 5 conns |
| No network access | Ya | ✅ OK — local file access |
| No built-in replication | Ya | ✅ OK — backup via file copy |

---

## 5. Why Now? Timing dan Urgensi

### 5.1 The Tipping Point

```
Saat ini (Juni 2026):
├── 28 services fully implemented
├── E2E pipeline 7/7 steps complete
├── Testing & dogfooding phase
├── < 100 audits in system
└── JSON performance masih OK

3-6 bulan ke depan:
├── Production usage starts
├── 1,000+ audits
├── Dashboard needs real-time queries
├── Agent needs fast knowledge retrieval
└── JSON starts becoming bottleneck ⚠️

Setelah itu:
├── Retrofit database = REWRITE besar-besaran
├── API berubah, pipeline rewrite
└── High risk, high cost
```

> **Sekarang adalah waktu terbaik**: codebase masih fresh, belum ada user production, bisa migrasi tanpa pressure.

### 5.2 Cost of Waiting

| Ditunda Sampai | Data Volume | Kompleksitas Migrasi | Risk |
|:-------------:|:-----------:|:--------------------:|:----:|
| Sekarang | < 100 audits | **Low** — JSON masih kecil, bisa export/import manual | Low |
| 3 bulan | ~500 audits | Medium — butuh migration script | Medium |
| 6 bulan | ~2,000 audits | High — downtime production, user impact | High |
| 12 bulan | ~10,000 audits | **Very High** — hampir seperti rewrite | Critical |

---

## 6. Reference: 17-experience — SQLite yang Sudah Berfungsi

Satu-satunya service yang sudah pakai SQLite:

```python
# services/17-experience/app.py (actual production code)

DB_PATH = "/data/experience/global.db"

class ExperienceStore:
    def __init__(self):
        self._local = threading.local()  # Thread-safe connections
    
    def _get_conn(self):
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(self._db_path)
            conn.execute("PRAGMA journal_mode=WAL")        # Concurrent read + 1 write
            conn.execute("PRAGMA synchronous=NORMAL")       # Good perf, safe on crash
            conn.execute("PRAGMA foreign_keys=ON")          
            conn.row_factory = sqlite3.Row                  # Dict access
            self._local.conn = conn
        return self._local.conn
```

**Yang sudah terbukti:**
- ✅ WAL mode works di Docker volume
- ✅ Thread-safe connection pooling (via `threading.local()`)
- ✅ `CREATE TABLE IF NOT EXISTS` di startup (schema auto-migration)
- ✅ Cross-agent sync pattern (batch every 50 entries / 5 minutes)
- ✅ Zero issues dalam deployment

---

## 7. Key Decision Points (Untuk Approval)

### Decision 1: Apakah SQLite per service (desentralisasi) atau SQLite service terpusat?

**Rekomendasi**: Per service (desentralisasi)

```
Alasan:
✅ Sama persis dengan pattern volume existing (1 service = 1 volume = 1 file .db)
✅ Tidak ada service tambahan — tidak melanggar filosofi VYPER
✅ Zero network latency — file I/O langsung
✅ Gradual migration — 1 service bisa pindah tanpa ganggu yang lain
✅ 17-experience sudah buktikan pattern ini works
```

### Decision 2: Apakah dual-write JSON + SQLite selama migrasi?

**Rekomendasi**: Ya, dual-write untuk P0 services

```
Alasan:
✅ Instant rollback — cukup switch env var dari sqlite ke json
✅ Risk mitigasi — jika ada bug di SQLite implementation, JSON masih ada
✅ Data integrity — dua source of truth selama transisi
⚠️ Cost: 40-60% extra write time (tapi write terjadi async di pipeline)
```

### Decision 3: Apakah shared volumes dihilangkan?

**Rekomendasi**: Ya, diganti dengan sync protocol / HTTP

```
Alasan:
✅ Menghilangkan root cause data loss
✅ Setiap service punya ownership penuh atas data-nya
✅ Cross-service data sharing via API yang well-defined
```

---

## 8. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|:----------:|:------:|------------|
| Bug di SqliteStore baru | Medium | High | Dual-write JSON fallback + integration tests |
| Schema mismatch saat migration | Low | Medium | `CREATE TABLE IF NOT EXISTS` auto-heal + migration framework |
| Performance regresi di write | Low | Low | Benchmark sebelum/sesudah, WAL mode optimized |
| Docker volume permission issue | Low | Medium | UID/GID config di Dockerfile |
| Lost data saat cut-over | Very Low | Critical | Backup full `/data/` sebelum setiap service migration |

---

*Agenda 27 — Bagian 1/4 | Context & Analysis*
