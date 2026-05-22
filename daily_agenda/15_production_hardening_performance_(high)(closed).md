# Agenda 15 — Production Hardening & Performance Tuning

> **Project**: sc_auditor (Vyper — Smart Contract Bug Hunter)
> **Status**: ✅ CLOSED
> **Severity**: HIGH — Pipeline bisa jalan tapi belum production-grade: rawan OOM, slow startup, no caching
> **Dependensi**: Agenda 07 (infrastructure), Agenda 10 (observability), Agenda 11-14 (all new features)

---

## 1. Latar Belakang

Setelah pipeline E2E berfungsi + semua fitur baru terintegrasi (Halmos, Agent, CI, Custom Detectors), Vyper perlu **production hardening**:

| Gap | Dampak | Area |
|-----|--------|------|
| **No resource governor** | Laptop bisa hang saat scan 10 kontrak parallel | All services |
| **Cold startup lambat** | 20 service butuh ~2-3 menit start | Docker Compose |
| **No caching layer** | Kontrak yang sama di-scan berulang | Scanner + Immunefi |
| **Error recovery rapuh** | Satu service down = pipeline gagal total | Orchestrator |
| **No backup/restore** | Data hilang jika volume corrupt | Upkeep |
| **Container bloat** | ~6GB untuk semua images | Docker images |
| **No performance baselines** | Tidak tau mana yang lambat | Benchmarking |

---

## 2. Detail Pekerjaan

### 2.1 Resource Governor

File baru: `services/13-upkeep/src/resource_governor.py`

```python
"""Resource Governor — mencegah laptop hang karena Vyper.

Monitoring:
- CPU usage per service
- Memory usage per service  
- Disk I/O
- Docker container stats

Actions:
- Throttle parallel scans jika CPU > 80%
- Kill OOM containers
- Pause daemon jika battery low (laptop)
- Queue delay jika resource contention

Architecture:
┌──────────────────┐
│  ResourceGovernor │
│  ┌──────────────┐│
│  │ SystemMonitor││──▶ CPU, Memory, Disk, Battery
│  └──────┬───────┘│
│  ┌──────▼───────┐│
│  │ ThrottleCtrl ││──▶ Semaphore, Queue, Kill
│  └──────────────┘│
└──────────────────┘
"""

import psutil
import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SystemLoad(Enum):
    IDLE = "idle"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ResourceState:
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_io_mbps: float = 0.0
    battery_percent: Optional[float] = None
    is_on_battery: bool = False
    docker_container_count: int = 0
    load: SystemLoad = SystemLoad.IDLE


class ResourceGovernor:
    """Central resource manager untuk semua service.
    
    Policy:
    - CPU < 50%: IDLE — full speed, max 5 parallel scans
    - CPU 50-70%: MODERATE — max 3 parallel scans
    - CPU 70-90%: HIGH — max 1 scan, delay daemon
    - CPU > 90%: CRITICAL — pause all, notify user
    - Battery < 20%: REDUCED — min resource mode
    """
    
    def __init__(self):
        self._scan_semaphore = asyncio.Semaphore(5)
        self._state = ResourceState()
        self._monitoring = False
        
    async def start_monitoring(self, interval: float = 5.0):
        """Start background monitoring loop."""
        self._monitoring = True
        while self._monitoring:
            self._state = await self._collect_stats()
            await self._apply_policy()
            await asyncio.sleep(interval)
    
    async def _collect_stats(self) -> ResourceState:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory().percent
        state = ResourceState(cpu_percent=cpu, memory_percent=mem)
        
        # Battery check
        if hasattr(psutil, "sensors_battery"):
            batt = psutil.sensors_battery()
            if batt:
                state.battery_percent = batt.percent
                state.is_on_battery = not batt.power_plugged
        
        # Load classification
        if cpu > 90 or mem > 90:
            state.load = SystemLoad.CRITICAL
        elif cpu > 70 or mem > 80:
            state.load = SystemLoad.HIGH
        elif cpu > 50 or mem > 60:
            state.load = SystemLoad.MODERATE
        else:
            state.load = SystemLoad.IDLE
        
        return state
    
    async def _apply_policy(self):
        """Adjust resource allocation based on current load."""
        load = self._state.load
        battery = self._state
        
        # Adjust scan parallelism
        if load == SystemLoad.IDLE:
            new_limit = 5
        elif load == SystemLoad.MODERATE:
            new_limit = 3
        elif load == SystemLoad.HIGH:
            new_limit = 1
        else:  # CRITICAL
            new_limit = 0  # Pause
        
        # Resize semaphore
        while self._scan_semaphore._value < new_limit:
            self._scan_semaphore.release()
        
        log.info("governor.policy", load=load.value, 
                 scan_limit=new_limit, cpu=self._state.cpu_percent)
    
    async def acquire_scan_slot(self) -> bool:
        """Acquire scan slot — blocks if resource constrained."""
        if self._state.load == SystemLoad.CRITICAL:
            log.warning("governor.scan_rejected", reason="critical_load")
            return False
        await self._scan_semaphore.acquire()
        return True
    
    def release_scan_slot(self):
        self._scan_semaphore.release()
```

### 2.2 Smart Caching Layer

File baru: `services/shared/cache.py`

```python
"""Shared caching layer — Redis atau file-based fallback.

Caching strategy:
1. Contract source: cache 1 jam (Etherscan rate limit)
2. Scan results: cache 24 jam (same contract, same tools)
3. AI analysis: cache 7 hari (same findings)
4. Immunefi programs: cache 30 menit

Storage:
- Primary: Redis (jika tersedia)  
- Fallback: JSON file di /data/cache/

TTL Strategy:
┌────────────────┬────────┬───────────┐
│ Cache Key      │ TTL    │ Reason    │
├────────────────┼────────┼───────────┤
│ contract:{addr}│ 1 hour │ Etherscan │
│ scan:{hash}    │ 24 jam │ Same out  │
│ ai:{hash}      │ 7 hari │ Expensive │
│ immunefi:progs │ 30 mnt │ Freshness │
└────────────────┴────────┴───────────┘
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional


class CacheLayer:
    """Multi-tier cache dengan Redis primary, file fallback."""
    
    def __init__(self, redis_url: str = None, cache_dir: str = "/data/cache"):
        self.redis = None
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0
        
        if redis_url:
            try:
                import redis.asyncio as aioredis
                self.redis = aioredis.from_url(redis_url, decode_responses=True)
            except ImportError:
                log.info("cache.redis_unavailable", fallback="file")
    
    def _key(self, prefix: str, data: Any) -> str:
        """Generate deterministic cache key."""
        raw = json.dumps(data, sort_keys=True)
        return f"{prefix}:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"
    
    async def get(self, prefix: str, data: Any) -> Optional[Any]:
        """Get from cache — try Redis first, fallback to file."""
        key = self._key(prefix, data)
        
        # Try Redis
        if self.redis:
            val = await self.redis.get(key)
            if val:
                self.hits += 1
                return json.loads(val)
        
        # Try file
        file_path = self.cache_dir / f"{key}.json"
        if file_path.exists():
            try:
                cached = json.loads(file_path.read_text())
                if cached.get("expires_at", 0) > time.time():
                    self.hits += 1
                    return cached["value"]
                file_path.unlink()
            except (json.JSONDecodeError, OSError):
                pass
        
        self.misses += 1
        return None
    
    async def set(self, prefix: str, data: Any, value: Any, ttl_seconds: int = 3600):
        """Store in cache."""
        key = self._key(prefix, data)
        payload = json.dumps({"value": value, "expires_at": time.time() + ttl_seconds})
        
        if self.redis:
            await self.redis.setex(key, ttl_seconds, payload)
        
        file_path = self.cache_dir / f"{key}.json"
        file_path.write_text(payload)
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
```

### 2.3 Pipeline Error Recovery & Resilience

File: `services/11-orchestrator/src/pipeline.py` (enhance)

```python
"""Enhanced pipeline dengan error recovery & partial results.

Saga Pattern untuk error recovery:
┌────────────────────────────────────────────┐
│                 PIPELINE                     │
│                                              │
│  STEP FAILED?                                │
│  ├── Auto-retry (3x, exponential backoff)   │
│  ├── Skip if non-critical (log warning)     │
│  ├── Fallback to cached result              │
│  └── Notify user + continue with partial    │
│                                              │
│  ALL STEPS DONE?                             │
│  ├── Full success → COMPLETED               │
│  ├── Partial success → COMPLETED_WITH_WARN  │
│  └── All failed → FAILED (but data aman)    │
└──────────────────────────────────────────────┘
"""

# Enhanced pipeline step dengan retry + fallback
class ResilientPipelineStep:
    def __init__(self, name: str, max_retries: int = 3, 
                 fallback_fn=None, critical: bool = True):
        self.name = name
        self.max_retries = max_retries
        self.fallback_fn = fallback_fn
        self.critical = critical  # If True, step failure = pipeline failure
    
    async def execute(self, context: dict) -> dict:
        last_error = None
        for attempt in range(1, self.max_retries + 2):
            try:
                result = await self._do_execute(context)
                return {"status": "success", "data": result}
            except Exception as e:
                last_error = e
                if attempt <= self.max_retries:
                    wait = 2 ** attempt  # Exponential backoff
                    log.warning("pipeline.retry", step=self.name, 
                               attempt=attempt, wait=wait, error=str(e))
                    await asyncio.sleep(wait)
        
        # All retries exhausted
        if self.fallback_fn:
            log.info("pipeline.fallback", step=self.name)
            fallback = await self.fallback_fn(context)
            return {"status": "degraded", "data": fallback, 
                    "error": str(last_error)}
        
        if self.critical:
            raise PipelineError(f"Critical step '{self.name}' failed: {last_error}")
        
        log.warning("pipeline.skipped", step=self.name, error=str(last_error))
        return {"status": "skipped", "error": str(last_error)}
```

### 2.4 Docker Image Optimization

File: `docker-compose.yml` & `services/*/Dockerfile` — konsolidasi multi-stage build

```dockerfile
# FROM python:3.11-slim (all services) → base image
# Optimasi:
# 1. Gunakan --no-cache-dir untuk pip
# 2. .dockerignore untuk exclude tests, __pycache__, .git
# 3. pip install --only-binary untuk avoid build from source
# 4. Layer caching: requirements.txt dulu, code kemudian
# 5. Hapus apt cache setelah install system deps

# Template optimal:
FROM python:3.11-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip

FROM base AS deps
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM deps AS runtime
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Action items:**
1. Buat `.dockerignore` di root project (exclude `__pycache__`, `.git`, `tests`, `node_modules`)
2. Standarisasi semua Dockerfile ke pattern di atas
3. Implementasi layer caching: `COPY requirements.txt` → `RUN pip install` → `COPY .`
4. Analisis dan hapus dependency yang tidak terpakai dari requirements.txt

### 2.5 Automated Backup & Restore

File: `services/13-upkeep/src/backup.py`

```python
"""Automated backup & restore system.

Backup Strategy:
- Full backup: setiap hari Minggu 03:00
- Incremental: setiap 6 jam (hanya data yang berubah)
- Retensi: 7 full backup, 30 hari incremental
- Storage: /data/backups/ (Docker volume)

Data yang di-backup:
  /data/ (semua service volumes)
  docker-compose.yml
  .env (encrypted)

Restore:
  vyper backup list          → show available backups
  vyper backup create        → manual backup
  vyper backup restore <id>  → restore to specific point
"""

class BackupManager:
    def __init__(self, backup_dir: str = "/data/backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    async def create_backup(self, name: str = None) -> str:
        """Create full backup of all service data."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = name or f"vyper_backup_{timestamp}"
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # Backup all volume data
        data_dirs = ["/data"]  # Root data directory
        for data_dir in data_dirs:
            src = Path(data_dir)
            if src.exists():
                dest = backup_path / "data"
                await self._copy_tree(src, dest)
        
        # Save backup metadata
        metadata = {
            "name": backup_name,
            "created_at": timestamp,
            "services": list(self._get_service_list()),
            "size_bytes": self._get_dir_size(backup_path),
        }
        (backup_path / "metadata.json").write_text(json.dumps(metadata, indent=2))
        
        log.info("backup.created", name=backup_name, size=metadata["size_bytes"])
        return backup_name
    
    async def list_backups(self) -> list[dict]:
        """List all available backups."""
        backups = []
        for dir in self.backup_dir.iterdir():
            if dir.is_dir():
                meta_file = dir / "metadata.json"
                if meta_file.exists():
                    backups.append(json.loads(meta_file.read_text()))
        return sorted(backups, key=lambda x: x["created_at"], reverse=True)
    
    async def restore(self, backup_name: str) -> bool:
        """Restore from backup."""
        backup_path = self.backup_dir / backup_name
        if not backup_path.exists():
            raise ValueError(f"Backup '{backup_name}' not found")
        
        # Restore data
        data_backup = backup_path / "data"
        if data_backup.exists():
            for item in data_backup.iterdir():
                dest = Path("/data") / item.name
                await self._copy_tree(item, dest, overwrite=True)
        
        log.info("backup.restored", name=backup_name)
        return True
```

### 2.6 Performance Benchmarking

File baru: `tests/benchmarks/test_performance.py`

```python
"""Performance benchmark suite untuk Vyper.

Benchmark:
1. Service startup time (cold → healthy)
2. Scan time per kontrak size (small/medium/large)
3. Pipeline throughput (contracts/minute)
4. Memory usage per scan
5. Docker image size per service

Setiap benchmark record baseline + history.
"""

BENCHMARK_THRESHOLDS = {
    "service_startup": {
        "cold": 30.0,    # 30 detik max cold start per service
        "warm": 5.0,     # 5 detik max warm start
    },
    "scan_time": {
        "small": 30.0,   # < 500 lines
        "medium": 120.0, # 500-2000 lines
        "large": 300.0,  # > 2000 lines
    },
    "pipeline_throughput": 2.0,  # Minimal 2 contracts/minute
    "max_memory_per_scan": 1024,  # MB
    "max_image_size": {
        "base": 200,     # MB — base Python service
        "scanner": 800,  # MB — scanner with tools
        "ai": 500,       # MB — AI service
    },
}


async def benchmark_service_startup():
    """Test startup time untuk setiap service."""
    ...

async def benchmark_scan_performance():
    """Test scan time untuk berbagai ukuran kontrak."""
    ...

async def benchmark_pipeline_throughput():
    """Test pipeline throughput — contracts/minute."""
    ...

async def benchmark_memory_usage():
    """Test memory usage selama scan."""
    ...
```

---

## 3. Struktur File

```
services/
├── shared/
│   └── cache.py                        # 🆕 Multi-tier caching layer

services/13-upkeep/src/
├── resource_governor.py                # 🆕 Resource governor
└── backup.py                           # 🆕 Backup & restore manager

services/11-orchestrator/src/
├── pipeline.py                         # ✏️ + ResilientPipelineStep, saga pattern
├── error_recovery.py                   # 🆕 Error recovery strategies

tests/benchmarks/
├── test_performance.py                 # 🆕 Performance benchmark suite
└── thresholds.json                     # 🆕 Benchmark thresholds

.dockerignore                           # 🆕 Docker build ignore
docker-compose.yml                      # ✏️ + resource limits per service

services/*/Dockerfile                   # ✏️ Standarisasi multi-stage build
```

---

## 4. Task List

| # | Task | File | Estimasi | Prioritas |
|---|------|------|----------|-----------|
| T1 | Resource governor — monitoring + throttling | `13-upkeep/src/resource_governor.py` | 40 min | P0 |
| T2 | Resource governor — API endpoints | `13-upkeep/app.py` | 10 min | P0 |
| T3 | Multi-tier caching layer (Redis + file) | `shared/cache.py` | 30 min | P0 |
| T4 | Integrasi cache ke scanner service | `04-scanner/app.py` | 15 min | P1 |
| T5 | Integrasi cache ke immunefi service | `02-immunefi/app.py` | 10 min | P1 |
| T6 | Pipeline error recovery (retry + fallback) | `11-orchestrator/src/pipeline.py` | 30 min | P0 |
| T7 | Partial results & COMPLETED_WITH_WARN | `11-orchestrator/src/pipeline.py` | 15 min | P1 |
| T8 | .dockerignore + standarisasi Dockerfiles | `.dockerignore` + `services/*/Dockerfile` | 30 min | P1 |
| T9 | Backup system | `13-upkeep/src/backup.py` | 25 min | P1 |
| T10 | Backup CLI commands | `cli/commands/backup.py` | 15 min | P2 |
| T11 | Resource limits di docker-compose | `docker-compose.yml` | 10 min | P1 |
| T12 | Performance benchmark suite | `tests/benchmarks/test_performance.py` | 30 min | P2 |
| T13 | Cache hit/miss metrics di dashboard | `frontend/src/pages/ServiceHealth.tsx` | 15 min | P2 |
| | **Total** | | **~275 menit** | |

---

## 5. Quality Gate

| Dimensi | Target | Cara Ukur |
|---------|--------|-----------|
| Correctness | 95% | All services start < 30s, backup restore data intact |
| Performance | 90% | Cache hit rate > 50%, cold start < 30s per service |
| Security | 85% | Backup encrypted, resource governor prevent OOM |
| Maintainability | 90% | Caching layer shared, resource governor modular |
| Completeness | 100% | Resource governor aktif, caching berfungsi, backup/restore work |
| Alignment | 100% | All hardening tanpa mengubah existing behavior |

---

## 6. Risiko & Mitigasi

| Risiko | Likelihood | Dampak | Mitigasi |
|--------|-----------|--------|----------|
| psutil tidak available di container | Rendah | Resource governor broken | Fallback ke Docker stats API |
| Redis tidak available | Sedang | Cache ke file fallback | Graceful degradation |
| Backup consume disk besar | Sedang | Disk penuh | Retensi policy: 7 full backup max |
| Multi-stage build complexity | Rendah | Build lebih kompleks | Template standar untuk semua service |
| Performance regression | Sedang | Pipeline lebih lambat | Benchmark threshold + CI gate |

---

*Dibuat: 2026-05-20 | Status: OPEN | Dependensi: Agenda 07, 10, 11, 12, 13, 14*
