# Prioritas 3 — Performance & Final Polish (Bulan 3)

> Target: **82 → 88/100 (Grade A-)** | Timeline: 2-4 minggu

---

## 1. PIPELINE PARALLELIZATION — 6x Faster

**Current**: Scanner tools dijalankan sequential dalam pipeline. Slither → Mythril → Echidna → Halmos → Manticore. Total: 3-10 menit per audit.

**Target**: Semua tools start bersamaan. Total: 30-90 detik.

### Implementasi

```python
# services/11-orchestrator/src/pipeline.py — upgrade step SCANNING
import asyncio

async def execute_scanning_parallel(contract_data: dict) -> dict:
    """Jalankan semua scanner tools secara paralel."""
    tools = {
        "slither": "http://04a-scanner-slither:8000",
        "mythril": "http://05-scanner-mythril:8000",
        "echidna": "http://04b-scanner-echidna:8000",
        "halmos": "http://04d-scanner-halmos:8000",
        "manticore": "http://04e-scanner-manticore:8000",
    }
    
    async def scan_tool(name: str, url: str) -> dict:
        import httpx
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(f"{url}/scan", json=contract_data)
                elapsed = time.monotonic() - start
                return {
                    "tool": name,
                    "success": True,
                    "findings": resp.json().get("findings", []),
                    "duration_ms": int(elapsed * 1000),
                }
        except Exception as exc:
            return {
                "tool": name,
                "success": False,
                "error": str(exc),
                "duration_ms": int((time.monotonic() - start) * 1000),
            }
    
    # Jalankan SEMUA paralel
    tasks = [scan_tool(name, url) for name, url in tools.items()]
    results = await asyncio.gather(*tasks)
    
    # Aggregate
    all_findings = []
    for r in results:
        if r["success"]:
            all_findings.extend(r["findings"])
    
    return {
        "tools_used": len(results),
        "tools_succeeded": sum(1 for r in results if r["success"]),
        "total_findings": len(all_findings),
        "findings": all_findings,
        "tool_results": results,
    }
```

### Performance Impact

```
SEQUENTIAL (current):
  Slither: 30s + Mythril: 45s + Echidna: 60s + Halmos: 45s + Manticore: 90s
  = 270 detik (4.5 menit)

PARALLEL (target):
  max(30s, 45s, 60s, 45s, 90s)
  = 90 detik (1.5 menit)

Speedup: 3x (naik jadi 6x dengan smart router yang hanya pilih 2-3 tools)
```

**Estimasi**: 1 hari
**File**: `services/11-orchestrator/src/pipeline.py`

---

## 2. RESPONSE CACHING — 10x Re-scan

**Current**: Setiap re-scan → compile ulang → scan ulang. 100% redundant.

**Target**: Cache hit → instant (< 10ms). Hanya re-scan kalau source berubah.

### 2A. Compilation Cache (sudah dibangun di Agenda 28)

```python
# services/03-source/src/compilation_cache.py — sudah ada
# Tinggal enable di pipeline
cache = CompilationCache()
compiled = cache.compile_or_get(source_code)
if compiled["cached"]:
    logger.info("Compilation cache HIT — skipping compile")
```

### 2B. Scan Result Cache

```python
# services/04-scanner/src/scan_cache.py
import hashlib
import json
from services.shared.storage import SqliteStore, StoreConfig

class ScanResultCache:
    """Cache hasil scan berdasarkan (contract_hash, tool_name, tool_version)."""
    
    def __init__(self, db_path="/data/scanner/scan_cache.db"):
        self.store = SqliteStore(StoreConfig(db_path=db_path))
        self.store.execute("""
            CREATE TABLE IF NOT EXISTS scan_cache (
                cache_key   TEXT PRIMARY KEY,
                findings    TEXT NOT NULL,
                tool        TEXT NOT NULL,
                contract_hash TEXT NOT NULL,
                tool_version TEXT,
                cached_at   TEXT NOT NULL DEFAULT (datetime('now')),
                ttl_seconds INTEGER DEFAULT 86400
            )
        """)
    
    def get(self, contract_hash: str, tool: str, tool_version: str = "") -> list[dict] | None:
        """Return cached results or None if expired/missing."""
        cache_key = hashlib.sha256(
            f"{contract_hash}:{tool}:{tool_version}".encode()
        ).hexdigest()[:16]
        
        row = self.store.query_one(
            "SELECT * FROM scan_cache WHERE cache_key = ? AND "
            "datetime(cached_at, '+' || ttl_seconds || ' seconds') > datetime('now')",
            (cache_key,)
        )
        if row:
            return json.loads(row["findings"])
        return None
    
    def set(self, contract_hash: str, tool: str, findings: list[dict], tool_version: str = ""):
        cache_key = hashlib.sha256(
            f"{contract_hash}:{tool}:{tool_version}".encode()
        ).hexdigest()[:16]
        
        self.store.upsert("scan_cache", {"cache_key": cache_key}, {
            "findings": json.dumps(findings),
            "tool": tool,
            "contract_hash": contract_hash,
            "tool_version": tool_version,
            "ttl_seconds": 86400,  # 24 jam
        })
```

### 2C. Integrasi ke Pipeline

```python
# services/04-scanner/app.py
cache = ScanResultCache()

@app.post("/scan")
async def scan(request: ScanRequest):
    # Cek cache dulu
    cached = cache.get(request.contract_hash, request.tool)
    if cached:
        return {"findings": cached, "cached": True, "duration_ms": 0}
    
    # Cache miss — scan normally
    result = await run_scanner(request)
    
    # Simpan ke cache
    cache.set(request.contract_hash, request.tool, result["findings"])
    
    return result
```

**Estimasi**: 0.5 hari
**Impact**: Re-scan time: 270s → 0s (cache hit)

---

## 3. HTTPX CONNECTION POOLING

**Current**: Setiap HTTP call buat connection baru. Overhead TCP handshake per call.

**Target**: Connection pool yang reusable sepanjang service lifetime.

```python
# services/shared/http_client.py
import httpx

# Global connection pool — reuse across all requests
_pool: httpx.AsyncClient | None = None

async def get_client() -> httpx.AsyncClient:
    global _pool
    if _pool is None:
        _pool = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=50,
                keepalive_expiry=30.0,
            ),
        )
    return _pool

async def close_client():
    global _pool
    if _pool:
        await _pool.aclose()
        _pool = None

# Usage:
client = await get_client()
response = await client.get("http://02-immunefi:8000/programs")
```

**Estimasi**: 0.5 hari
**Impact**: 2x faster untuk frequent inter-service calls

---

## 4. DASHBOARD LAZY LOADING

**Current**: Dashboard frontend fetch semua data saat load — lambat.

**Target**: Lazy load per-section. Hanya fetch data yang visible di viewport.

```typescript
// services/15-dashboard/frontend/src/hooks/useLazyData.ts
import { useEffect, useRef, useState } from 'react';

export function useLazyData<T>(fetchFn: () => Promise<T>) {
    const [data, setData] = useState<T | null>(null);
    const [loading, setLoading] = useState(false);
    const ref = useRef<HTMLDivElement>(null);
    
    useEffect(() => {
        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting && !data && !loading) {
                    setLoading(true);
                    fetchFn().then(setData).finally(() => setLoading(false));
                }
            },
            { rootMargin: '200px' }  // Pre-fetch 200px sebelum visible
        );
        
        if (ref.current) observer.observe(ref.current);
        return () => observer.disconnect();
    }, []);
    
    return { ref, data, loading };
}
```

**Estimasi**: 1 hari
**Impact**: Dashboard load time: 5s → 1s (initial)

---

## 5. DATABASE INDEX OPTIMIZATION

**Current**: Beberapa tabel SQLite tanpa index — full table scan.

**Target**: Setiap query punya index yang sesuai.

```sql
-- services/11-orchestrator/schema.py — tambah index
CREATE INDEX IF NOT EXISTS idx_audits_created_at ON audits(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audits_chain_status ON audits(chain, status);
CREATE INDEX IF NOT EXISTS idx_pipeline_audit_step ON pipeline_steps(audit_id, step_name);
CREATE INDEX IF NOT EXISTS idx_scan_metrics_scanner_time ON scan_metrics(scanner, scanned_at DESC);

-- services/07-classifier/schema.py — tambah index
CREATE INDEX IF NOT EXISTS idx_findings_severity_created ON findings(severity, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_findings_confidence_score ON findings(confidence);
CREATE INDEX IF NOT EXISTS idx_classifications_verdict_time ON classifications(verdict, classified_at DESC);
```

**Estimasi**: 0.5 hari
**Impact**: Query time 2-5x faster untuk dashboard

---

## 6. GRACEFUL SHUTDOWN

**Current**: Container di-stop → proses langsung mati. Bisa corrupt data di tengah write.

**Target**: Graceful shutdown dengan drain connection + flush writes.

```python
# Setiap service app.py
import signal

@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down gracefully...")
    
    # 1. Stop accepting new requests
    # 2. Tunggu active requests selesai (max 30 detik)
    await asyncio.sleep(2)
    
    # 3. Flush pending writes
    if hasattr(state, 'sqlite_store') and state.sqlite_store:
        state.sqlite_store.close()
    
    # 4. Close connection pools
    from shared.http_client import close_client
    await close_client()
    
    logger.info("Shutdown complete")
```

**Estimasi**: 0.5 hari

---

## 7. 200+ ADDITIONAL TESTS

### Coverage Targets per Service

| Service | Target Coverage | New Tests |
|---------|:--------------:|:---------:|
| 02-immunefi | 70% | 20 |
| 03-source | 70% | 15 |
| 04-scanner | 70% | 15 |
| 04a-slither | 60% | 10 |
| 04b-echidna | 60% | 10 |
| 05-mythril | 60% | 10 |
| 06-ai | 60% | 15 |
| 09-reporter | 80% | 15 |
| 10-notifier | 80% | 10 |
| 14-agent | 50% | 20 |
| 15-dashboard | 50% | 15 |
| 16-submission | 70% | 10 |
| 17-experience | 80% | 5 |
| 18-21 (bounty) | 60% | 20 |
| 22-23 (starknet) | 50% | 10 |
| **TOTAL** | | **200** |

**Estimasi**: 5-7 hari

---

## 8. CHANGELOG.md

```markdown
# Changelog — VYPER (sc_auditor)

## [0.5.0] — 2026-06-04

### Added
- SQLite storage layer (28 services) — replaces JSON files
- 10 overpower scanner enhancements
- Cross-tool consensus engine
- Self-improving detector factory
- Economic exploit calculator
- MEV Guardian + Flashbots integration
- DeFi propagation scanner
- Shared compilation cache (6x faster)
- Smart scan router (3x faster)

### Changed
- JSON → SQLite migration for all 28 services
- Scanner tools run in parallel (3-6x faster)
- HTTP connection pooling for inter-service calls

### Fixed
- VACUUM transaction handling in SqliteStore
- UPDATE/DELETE row count tracking
- Import path normalization (services.shared → shared)
```

---

## Checklist Bulan 3

```
[ ] Pipeline parallelization (asyncio.gather semua scanner)
[ ] Scan result cache (SQLite-backed, 24h TTL)
[ ] Compilation cache enable di pipeline
[ ] HTTPX connection pooling
[ ] Dashboard lazy loading (IntersectionObserver)
[ ] Database index optimization
[ ] Graceful shutdown di semua service
[ ] 200+ additional tests
[ ] CI coverage gate → 70% threshold
[ ] CHANGELOG.md created
[ ] Full E2E test: 1 audit complete pipeline
[ ] Performance benchmark: before/after parallelization
[ ] Code review: 0 files > 500 lines
[ ] Security audit: 0 HIGH/CRITICAL npm audit findings
[ ] Update SYSTEM_LOG.md
```

---

## Final Quality Gate — Target Grade A-

| Dimensi | Sebelum | Target |
|---------|:-------:|:------:|
| Code Quality | 6.5 | 8.0 |
| Security | 7.0 | 8.5 |
| Performance | 6.0 | 8.0 |
| Architecture | 9.0 | 9.5 |
| Testing | 5.0 | 8.0 |
| Error Handling | 6.5 | 7.5 |
| Documentation | 9.5 | 9.5 |
| Observability | 6.5 | 7.5 |
| Deployment | 8.0 | 8.5 |
| **OVERALL** | **71 (B-)** | **88 (A-)** |

---

## 🔴 GAP COVERAGE — Item yang sebelumnya terlewat

### I. STRESS / LOAD TESTING

**Problem**: Tidak tahu berapa batas maksimum sistem. 10 audit paralel? 100?

**File**: `tests/test_stress.py`
**Target**: 5 test scenarios

```python
class TestStressScenarios:
    """Stress test — cari batas maksimum sistem."""

    def test_concurrent_20_audits(self):
        """20 audit paralel → sistem harus tetap responsif."""
        # Spawn 20 audit → ukur response time
        # Target: P95 < 30 detik per audit

    def test_sustained_load_100_audits(self):
        """100 audit dalam 1 jam → tidak ada memory leak."""
        # Kirim 100 audit dalam 60 menit → monitor memory usage
        # Target: memory usage stabil (tidak naik terus)

    def test_large_contract_10k_lines(self):
        """Kontrak 10,000 baris → pipeline tidak timeout."""
        # Target: scan selesai < 5 menit

    def test_sqlite_10k_findings_query(self):
        """10,000 findings di database → query < 50ms."""
        # Insert 10K findings → SELECT WHERE severity=HIGH
        # Target: < 50ms dengan index

    def test_disk_space_under_load(self):
        """100 audit → disk usage < 5GB."""
        # Audit 100x → cek total /data/ size
        # Target: < 5GB dengan pruning
```

**Tool**: `pytest-benchmark` atau `locust` untuk HTTP load test.

```bash
# HTTP load test dengan locust
pip install locust
# locustfile.py → simulate 50 concurrent users → 100 audit requests
locust --headless --users 50 --spawn-rate 10 --run-time 300s
```

---

### J. PRODUCTION DEPLOYMENT GUIDE

**Problem**: Hanya ada Docker Compose. Tidak ada guide untuk production.

**Action**: Buat `docs/DEPLOYMENT.md`.

```markdown
# VYPER — Production Deployment Guide

## Prasyarat
- Docker 24+ & Docker Compose v3.9+
- Minimum: 8 CPU, 32GB RAM, 100GB SSD
- Recommended: 16 CPU, 64GB RAM, 500GB NVMe
- Ubuntu 22.04 LTS (tested) | macOS 14+ (tested)

## Quick Deploy
1. Clone repo: `git clone ...`
2. Copy config: `cp .env.example .env`
3. Edit `.env`: tambahkan API keys (Anthropic, OpenAI, Infura, Alchemy)
4. Build: `docker compose build`
5. Start: `docker compose up -d`
6. Verify: `docker compose ps` → 28/28 Up
7. Dashboard: `http://localhost:8000`

## Production Checklist
- [ ] Non-root user untuk semua container
- [ ] Firewall: hanya expose port 8000 (dashboard), 8011 (config)
- [ ] VPN/tailscale untuk akses remote
- [ ] Disk: mount /data di SSD terpisah
- [ ] Backup: cron job setiap 6 jam (built-in via 13-upkeep)
- [ ] Monitoring: Grafana + Prometheus (opsional)
- [ ] Secrets: API keys via environment variables, bukan hardcoded
- [ ] Resource limits: atur di docker-compose.yml per service

## Troubleshooting
| Symptom | Cause | Fix |
|---------|-------|-----|
| Service restarting | Missing env var | Cek `docker compose logs {service}` |
| Pipeline stuck | Tool timeout | Perbesar `step_timeout_seconds` di config |
| Out of disk | Backup menumpuk | Cek `/data/backups/`, cleanup otomatis 30 hari |
| Slow scan | Kontrak besar | Upgrade resource limits di docker-compose |
```

---

### K. DISASTER RECOVERY PLAN

**Problem**: Tidak ada plan kalau server mati total.

**Action**: Buat `docs/DISASTER_RECOVERY.md`.

```markdown
# VYPER — Disaster Recovery Plan

## Recovery Time Objective (RTO): 30 menit
## Recovery Point Objective (RPO): 6 jam (interval backup)

## Scenario 1: Single Service Crash
1. `docker compose restart {service}`
2. Jika masih crash → `docker compose logs {service} --tail=50`
3. Jika perlu rebuild → `docker compose build {service} && docker compose up -d {service}`

## Scenario 2: Docker Daemon Crash
1. `sudo systemctl restart docker`
2. `docker compose up -d`
3. Verify: `docker compose ps`

## Scenario 3: Server Total Failure
1. Provision server baru (Ubuntu 22.04)
2. Install Docker + Docker Compose
3. Clone repo → copy `.env` dari backup
4. Restore `/data/` dari backup terakhir:
   ```bash
   tar -xzf /backup/full_backup_20260604_120000.tar.gz -C /data/
   ```
5. `docker compose up -d`
6. Verify dashboard: `http://SERVER_IP:8000`
7. Test pipeline: submit 1 audit → verify report generated

## Scenario 4: Data Corruption
1. Stop services: `docker compose down`
2. Restore dari backup terbersih:
   ```bash
   # Cek backup integrity
   for f in /backup/full_backup_*.tar.gz; do
       tar -tzf "$f" > /dev/null && echo "$f: OK" || echo "$f: CORRUPT"
   done
   # Restore yang OK
   tar -xzf /backup/full_backup_LATEST_OK.tar.gz -C /data/
   ```
3. Start: `docker compose up -d`
4. Verify: cek audit history di dashboard

## Backup Locations
- Primary: `/data/backups/` (local)
- Secondary: rsync ke external storage (S3, NAS, etc.) — cron setiap 24 jam
```

---

## Checklist Bulan 3 — UPDATED

```
[ ... checklist sebelumnya ... ]
[ ] Tulis 5 stress/load test scenarios
[ ] Benchmark: max concurrent audits sebelum system degrade
[ ] Benchmark: query performance 10K findings
[ ] Buat docs/DEPLOYMENT.md — production deployment guide
[ ] Buat docs/DISASTER_RECOVERY.md — disaster recovery plan
[ ] Test disaster recovery: restore from backup → verify
[ ] Setup rsync backup ke external storage (opsional)
[ ] Performance baseline: dokumentasi throughput sistem
[ ] Final E2E: 1 audit lengkap dengan semua enhancement
[ ] Final score: re-run 12-dimension assessment
```

---

*Agenda 29 — Prioritas 3 — Bulan 3*
