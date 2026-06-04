# Prioritas 2 — Code Quality & Security Hardening (Bulan 2)

> Target: **75 → 82/100 (Grade B+)** | Timeline: 2-4 minggu

---

## 1. FILE SPLITTING — 0 files > 500 lines

**Current**: 28 files di atas 500 lines. Target: 0.

### 1A. Split 5 Files Terbesar

#### `services/08-exploit/src/planner.py` (1,344 lines)

```
planner.py (1,344)
├── planner_core.py        (~400 lines) — ExploitPlanner class, orchestration
├── planner_strategies.py  (~350 lines) — Strategy selection, ranking
├── planner_validation.py  (~300 lines) — Payload validation, constraints
└── planner_types.py       (~150 lines) — Dataclasses, enums
```

#### `services/11-orchestrator/src/pipeline.py` (1,120 lines)

```
pipeline.py (1,120)
├── pipeline_states.py     (~350 lines) — State machine + transitions
├── pipeline_executor.py   (~400 lines) — Step execution + HTTP calls
├── pipeline_saga.py       (~250 lines) — Rollback logic + compensation
└── pipeline_types.py      (~120 lines) — AuditRecord, PipelineStep
```

#### `services/02-immunefi/app.py` (1,145 lines)

```
app.py (1,145)
├── routes_programs.py     (~400 lines) — /programs endpoints
├── routes_sync.py         (~350 lines) — /sync, /refresh endpoints
├── routes_admin.py        (~200 lines) — /admin endpoints
└── app.py                 (~195 lines) — FastAPI init, middleware, lifespan
```

#### `services/14-agent/app.py` (1,087 lines)

```
app.py (1,087)
├── routes_agent.py        (~400 lines) — Agent delegation + negotiation
├── routes_memory.py       (~250 lines) — Memory CRUD endpoints
├── routes_skills.py       (~250 lines) — Skill listing + execution
└── app.py                 (~187 lines) — Core setup
```

#### `services/08-exploit/src/engine.py` (1,018 lines)

```
engine.py (1,018)
├── engine_core.py         (~400 lines) — ExploitEngine orchestration
├── engine_hypotheses.py   (~300 lines) — Hypothesis generation + testing
├── engine_execution.py    (~200 lines) — Anvil fork + exploit execution
└── engine_types.py        (~118 lines) — ExploitResult, config
```

### 1B. Split Rule

```
Rule: Tidak ada file > 500 lines.
      Tidak ada fungsi > 50 lines.
      Tidak ada class > 300 lines.
```

### 1C. Verification

```bash
# Cek file > 500 lines
find services/ -name "*.py" -exec wc -l {} + | awk '$1 > 500 {print $0}' | sort -rn

# Cek fungsi > 50 lines (gunakan radon)
pip install radon
radon cc services/ -a -n C  # C = complexity too high
```

**Estimasi**: 3-4 hari untuk 5 file
**Success criteria**: `find ... | awk '$1 > 500'` → empty output

---

## 2. SECURITY HARDENING

### 2A. Rate Limiting di API Gateway (15-dashboard)

```python
# services/15-dashboard/app.py
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda r, e: JSONResponse(
    status_code=429,
    content={"error": "Too many requests. Slow down.", "retry_after": 60}
))

# Apply ke semua proxy endpoint
@app.get("/api/proxy/{service}/{path:path}")
@limiter.limit("100/minute")
async def proxy(service: str, path: str, request: Request):
    ...
```

### 2B. Service-to-Service Auth Token

```python
# services/shared/auth.py
import os
import hashlib
import hmac

SHARED_SECRET = os.environ.get("VYPER_SERVICE_TOKEN", "dev-secret-change-me")

def generate_service_token() -> str:
    """Token sederhana untuk internal service auth."""
    import time
    timestamp = str(int(time.time()))
    signature = hmac.new(
        SHARED_SECRET.encode(),
        timestamp.encode(),
        hashlib.sha256
    ).hexdigest()[:16]
    return f"{timestamp}.{signature}"

def verify_service_token(token: str, max_age_seconds: int = 300) -> bool:
    """Verifikasi token (maks 5 menit)."""
    try:
        timestamp_str, signature = token.split(".")
        timestamp = int(timestamp_str)
        import time
        if abs(time.time() - timestamp) > max_age_seconds:
            return False
        expected = hmac.new(
            SHARED_SECRET.encode(),
            timestamp_str.encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        return hmac.compare_digest(signature, expected)
    except (ValueError, AttributeError):
        return False
```

```python
# Setiap service tambah middleware:
from shared.auth import verify_service_token
from fastapi import Request, HTTPException

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)  # Skip health check
    token = request.headers.get("X-Vyper-Token", "")
    if not verify_service_token(token):
        raise HTTPException(status_code=401, detail="Invalid service token")
    return await call_next(request)

# Service caller tambah header:
headers = {"X-Vyper-Token": generate_service_token()}
response = await client.get("http://07-classifier:8000/findings", headers=headers)
```

### 2C. Docker Security — 08-exploit Hardening

```yaml
# docker-compose.yml — update 08-exploit
  08-exploit:
    security_opt:
      - no-new-privileges:true
    read_only: true  # Root filesystem read-only
    tmpfs:
      - /tmp:exec     # /tmp writable untuk Anvil
    cap_drop:
      - ALL
    cap_add:
      - NET_ADMIN     # Hanya network (Anvil butuh port)
    user: "1000:1000" # Non-root
```

### 2D. Audit Trail untuk Config Changes

```python
# services/01-config/app.py
import structlog
logger = structlog.get_logger()

@app.put("/config/{key:path}")
async def upsert_config(request: Request, key: str, body: ConfigValue):
    old_value = mgr.get(key)
    mgr.set(key, body.value)
    # AUDIT LOG
    logger.info("config_changed",
        key=key,
        old_value=str(old_value)[:100],
        new_value=str(body.value)[:100],
        client_ip=request.client.host if request.client else "unknown",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    return ConfigResponse(data={key: body.value})
```

### 2E. Input Validation — Pydantic Strict Mode

```python
# Semua model pakai strict mode
from pydantic import BaseModel, Field, validator

class ConfigValue(BaseModel):
    model_config = {"strict": True, "extra": "forbid"}  # Tolak field tidak dikenal
    value: Any = Field(..., description="Configuration value")

class BulkConfig(BaseModel):
    model_config = {"strict": True, "extra": "forbid"}
    config: dict[str, Any] = Field(..., min_length=1, max_length=100)
```

**Estimasi**: 2-3 hari untuk semua security items
**Success criteria**: Rate limit tested, auth token working, Docker non-root, audit log recorded

---

## 3. OBSERVABILITY UPGRADE

### 3A. Structured Logging (semua service)

```python
# services/shared/observability.py — upgrade
import structlog

def setup_observability(app, service_name, version):
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer() if os.environ.get("ENV") != "production"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logger = structlog.get_logger().bind(
        service=service_name,
        version=version,
    )
    return logger
```

### 3B. Request ID Propagation

```python
# services/shared/middleware.py
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

# Pasang di setiap service app.py
app.add_middleware(RequestIDMiddleware)
```

### 3C. Health Aggregation (13-upkeep)

```python
# services/13-upkeep/src/health_aggregator.py
import httpx

SERVICES = {
    "01-config": "http://01-config:8000",
    "02-immunefi": "http://02-immunefi:8000",
    # ... semua 28 service
}

async def aggregate_health() -> dict:
    """Cek health semua service, return aggregate status."""
    results = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in SERVICES.items():
            try:
                resp = await client.get(f"{url}/health")
                results[name] = {"status": "up", "data": resp.json()}
            except Exception:
                results[name] = {"status": "down"}
    
    up_count = sum(1 for r in results.values() if r["status"] == "up")
    return {
        "total": len(SERVICES),
        "up": up_count,
        "down": len(SERVICES) - up_count,
        "services": results,
    }
```

**Estimasi**: 1-2 hari
**Success criteria**: Setiap request punya trace ID, log JSON-structured

---

## Checklist Bulan 2

```
[ ] Split planner.py → 4 files (< 500 lines each)
[ ] Split pipeline.py → 4 files
[ ] Split immunefi/app.py → 4 files
[ ] Split agent/app.py → 4 files
[ ] Split engine.py → 4 files
[ ] Verify: 0 files > 500 lines
[ ] Rate limiting di 15-dashboard API Gateway
[ ] Service-to-service auth token di semua service
[ ] 08-exploit Docker hardening (non-root, read-only, seccomp)
[ ] Audit trail untuk config changes
[ ] Pydantic strict mode di semua model
[ ] Structured logging upgrade (JSON format)
[ ] Request ID middleware di semua service
[ ] Health aggregation endpoint di 13-upkeep
[ ] Run full test suite → green
[ ] CI coverage gate → 50% threshold
[ ] Update SYSTEM_LOG.md
```

---

## 🔴 GAP COVERAGE — Item yang sebelumnya terlewat

### D. CIRCUIT BREAKER — Inter-Service Resilience

**Problem**: Service A call Service B. B mati → A hang 30 detik → cascade failure.

**Action**: Circuit breaker pattern di semua inter-service HTTP call.

```python
# services/shared/circuit_breaker.py
import time
import asyncio
from enum import Enum

class CircuitState(str, Enum):
    CLOSED = "closed"             # Normal — requests flow
    OPEN = "open"                 # Tripped — requests rejected instantly
    HALF_OPEN = "half_open"       # Testing — limited requests allowed

class CircuitBreaker:
    """Melindungi service dari cascade failure."""
    
    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_timeout: float = 30.0, half_open_max: int = 3):
        self.name = name
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max
        self.half_open_count = 0
    
    async def call(self, coro):
        """Panggil service dengan circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_count = 0
            else:
                raise CircuitOpenError(f"Circuit {self.name} is OPEN")
        
        try:
            result = await coro
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise exc
    
    def _on_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_count += 1
            if self.half_open_count >= self.half_open_max:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
        else:
            self.failure_count = 0
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

class CircuitOpenError(Exception):
    pass

# Global circuit breakers per service
CIRCUITS = {
    "immunefi": CircuitBreaker("02-immunefi"),
    "source": CircuitBreaker("03-source"),
    "classifier": CircuitBreaker("07-classifier"),
    "exploit": CircuitBreaker("08-exploit"),
    "ai": CircuitBreaker("06-ai", failure_threshold=3),  # AI mahal — lebih sensitif
}

# Usage di orchestrator:
from shared.circuit_breaker import CIRCUITS
try:
    result = await CIRCUITS["immunefi"].call(
        client.get("http://02-immunefi:8000/programs")
    )
except CircuitOpenError:
    # Circuit open — skip Immunefi, gunakan data cache
    result = cached_programs
```

**Estimasi**: 1 hari
**Impact**: Mencegah cascade failure. Pipeline tetap jalan walau 1 service mati.

---

### E. DISTRIBUTED TRACING — OpenTelemetry

**Problem**: Request lewat 8 service dalam pipeline. Debugging = cek log 8 service manual.

**Action**: OpenTelemetry auto-instrumentation di semua service.

```python
# services/shared/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

def setup_tracing(service_name: str, app):
    """Setup OpenTelemetry tracing untuk 1 service."""
    trace.set_tracer_provider(TracerProvider())
    
    # Export ke Jaeger / Grafana Tempo (opsional — local development skip)
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        trace.get_tracer_provider().add_span_processor(
            BatchSpanProcessor(exporter)
        )
    
    # Auto-instrument FastAPI + HTTPX
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    
    return trace.get_tracer(service_name)

# Usage di setiap service app.py:
# tracer = setup_tracing("11-orchestrator", app)
```

**Estimasi**: 1 hari
**Impact**: Debug pipeline dalam 1 view. Temukan bottleneck real-time.

---

### F. ALERTING RULES — Proactive Monitoring

**Problem**: Service mati → tidak ada yang tahu sampai user komplain.

**Action**: Alert rules di 13-upkeep + 10-notifier.

```python
# services/13-upkeep/src/alerting.py
import asyncio

ALERT_RULES = [
    {
        "name": "service_down",
        "condition": lambda health: health["status"] == "down",
        "severity": "CRITICAL",
        "message": "Service {service} is DOWN",
        "cooldown_seconds": 300,  # Jangan spam — max 1 alert per 5 menit
    },
    {
        "name": "high_error_rate",
        "condition": lambda metrics: metrics.get("error_rate", 0) > 0.05,
        "severity": "HIGH",
        "message": "Service {service} error rate: {error_rate:.1%}",
        "cooldown_seconds": 600,
    },
    {
        "name": "disk_space_low",
        "condition": lambda metrics: metrics.get("disk_free_mb", 9999) < 1000,
        "severity": "WARNING",
        "message": "Service {service} disk space: {disk_free_mb}MB free",
        "cooldown_seconds": 3600,
    },
    {
        "name": "pipeline_stuck",
        "condition": lambda state: state.get("stuck_audits", 0) > 3,
        "severity": "CRITICAL",
        "message": "{stuck_audits} audits stuck in pipeline for > 10 minutes",
        "cooldown_seconds": 300,
    },
]

class AlertManager:
    def __init__(self, notifier_url="http://10-notifier:8000"):
        self.notifier_url = notifier_url
        self._last_alerted = {}  # alert_name → timestamp
    
    async def evaluate(self, health_data: dict, metrics_data: dict):
        for rule in ALERT_RULES:
            if self._in_cooldown(rule["name"]):
                continue
            
            # Check condition
            try:
                context = {**health_data, **metrics_data}
                if rule["condition"](context):
                    await self._send_alert(rule, context)
            except Exception as exc:
                logger.error("Alert eval failed: %s", exc)
    
    async def _send_alert(self, rule: dict, context: dict):
        message = rule["message"].format(**context)
        # Kirim via 10-notifier → Discord + Telegram
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(f"{self.notifier_url}/alert", json={
                "severity": rule["severity"],
                "message": message,
                "rule": rule["name"],
            })
        self._last_alerted[rule["name"]] = time.monotonic()
```

**Estimasi**: 0.5 hari

---

### G. SHARED VOLUMES — Complete Removal

**Problem**: `vyper_kb`, `vyper_learning` masih di-mount. Risk data corruption.

**Action**: 
1. Konfirmasi semua service yang sebelumnya akses shared volume sudah pakai SQLite + sync protocol
2. Hapus dari docker-compose.yml
3. Hapus dari `volumes:` top-level

```yaml
# docker-compose.yml — REMOVE these lines
# vyper_kb:           ← HAPUS
# vyper_learning:      ← HAPUS

# Dari 07-classifier, 08-exploit, 14-agent, 11-orchestrator, 15-dashboard:
#   - vyper_kb:/data/knowledge       ← HAPUS
#   - vyper_learning:/data/learning  ← HAPUS
```

**Verification**:
```bash
docker compose down -v vyper_kb vyper_learning  # Hapus volumes
docker compose up -d
# Verify: tidak ada service yang error karena missing volume
docker compose logs | grep -i "vyper_kb\|vyper_learning"
# → harus kosong (tidak ada reference)
```

---

### H. BACKUP/RESTORE AUTOMATION — 13-upkeep

**Problem**: Tidak ada automated backup. Manual `tar -czf` tidak reliable.

**Action**: Backup scheduler di 13-upkeep.

```python
# services/13-upkeep/src/backup.py — upgrade
import schedule
import tarfile
from pathlib import Path
from datetime import datetime, timezone

class BackupScheduler:
    def __init__(self, backup_dir="/data/backups", retention_days=30):
        self.backup_dir = Path(backup_dir)
        self.retention_days = retention_days
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    async def backup_all(self) -> dict:
        """Backup SEMUA data volume ke compressed archive."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"full_backup_{timestamp}.tar.gz"
        
        # Backup semua SQLite databases
        data_dirs = [
            "/data/config", "/data/immunefi", "/data/source",
            "/data/scanner", "/data/classifier", "/data/exploit",
            "/data/orchestrator", "/data/agent", "/data/experience",
            # ... semua 28 service
        ]
        
        with tarfile.open(backup_file, "w:gz") as tar:
            for d in data_dirs:
                path = Path(d)
                if path.exists():
                    tar.add(path, arcname=path.name)
        
        size_mb = backup_file.stat().st_size / (1024*1024)
        return {
            "file": str(backup_file),
            "size_mb": round(size_mb, 2),
            "timestamp": timestamp,
        }
    
    async def cleanup_old_backups(self) -> int:
        """Hapus backup > retention_days."""
        cutoff = datetime.now(timezone.utc).timestamp() - self.retention_days * 86400
        removed = 0
        for f in self.backup_dir.glob("full_backup_*.tar.gz"):
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        return removed
    
    async def verify_backup(self, backup_file: str) -> dict:
        """Verifikasi integritas backup — test restore."""
        # Extract ke temp, cek SQLite integrity
        # Return: {valid: true/false, errors: [...]}
        pass

# Schedule: backup setiap 6 jam
# schedule.every(6).hours.do(backup_all)
```

**Estimasi**: 0.5 hari

---

## Checklist Bulan 2 — UPDATED

```
[ ... checklist sebelumnya ... ]
[ ] Circuit breaker di orchestrator (semua inter-service calls)
[ ] Circuit breaker di 14-agent, 07-classifier, 08-exploit
[ ] OpenTelemetry auto-instrumentation (4 P0 services dulu)
[ ] Trace propagation: request ID lewat HTTP headers
[ ] Alert rules: service_down, high_error_rate, pipeline_stuck
[ ] Alert cooldown: max 1 alert per 5 menit per rule
[ ] Hapus vyper_kb dari docker-compose (3 service)
[ ] Hapus vyper_learning dari docker-compose (3 service)
[ ] Backup scheduler di 13-upkeep (setiap 6 jam)
[ ] Backup verify: test restore SQLite integrity
[ ] Backup cleanup: hapus > 30 hari
```

---

*Agenda 29 — Prioritas 2 — Bulan 2*
