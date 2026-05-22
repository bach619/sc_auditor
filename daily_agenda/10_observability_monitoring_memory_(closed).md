# Agenda 10 — Observability, Monitoring & Agent Memory

> **Project**: sc_auditor (Vyper — Smart Contract Bug Hunter)
> **Status**: ✅ CLOSED
> **Severity**: CRITICAL — Zero observability + Agent memory kosong
> **Dependensi**: Agenda 09 (auth harus ada untuk dashboard monitoring)

---

## 1. Latar Belakang

Hasil audit project menemukan **3 critical gaps**:

| Gap | Dampak | Lokasi |
|-----|--------|--------|
| **Zero observability** | Tidak bisa monitor health 20 services, tidak ada metrics, tracing, atau centralized logging | ALL services |
| **Agent memory kosong** | `14-agent/src/memory/` hanya berisi `__init__.py` — learning system tidak berfungsi | `14-agent` |
| **No health dashboard** | Tidak ada visualisasi dependency graph, uptime, atau latency antar service | `15-dashboard` |

---

## 2. Detail Pekerjaan

### 2.1 Metrics Collection (Prometheus + OpenTelemetry)

Setiap service perlu mengexpose metrics endpoint.

File baru: `services/shared/metrics.py` (shared utility)
```python
"""Shared metrics utility untuk semua services.

Menggunakan OpenTelemetry + Prometheus exporter.
Setiap service cukup import dan register.

Usage:
    from shared.metrics import metrics
    
    @app.get("/metrics")
    async def metrics_endpoint():
        return metrics.generate()
        
    # Auto-tracked:
    # - request_count{method, endpoint, status}
    # - request_duration_seconds{method, endpoint}
    # - error_count{method, endpoint, error_type}
    # - service_info{name, version}
"""

import time
from prometheus_client import Counter, Histogram, Gauge, generate_latest

request_count = Counter(
    'vyper_request_count', 'Total requests',
    ['service', 'method', 'endpoint', 'status']
)

request_duration = Histogram(
    'vyper_request_duration_seconds', 'Request latency',
    ['service', 'method', 'endpoint'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0)
)

error_count = Counter(
    'vyper_error_count', 'Total errors',
    ['service', 'method', 'endpoint', 'error_type']
)

service_info = Gauge(
    'vyper_service_info', 'Service metadata',
    ['service', 'version']
)
```

Setiap service perlu:
1. Import `shared/metrics.py`
2. Tambah `@app.get("/metrics")` endpoint
3. Pasang middleware untuk auto-track request count + duration
4. Set `service_info` pada startup

**Service yang perlu di-update (20 services):**
```
01-config  → app.py + /metrics
02-immunefi → app.py + /metrics
... (semua 20 services)
```

### 2.2 Centralized Logging (JSON Structured Logging)

Semua service sudah pakai `structlog`. Perlu distandardisasi:

```python
# Format standar untuk semua services:
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),  # ← JSON untuk log aggregation
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
```

Setiap log entry akan punya format:
```json
{
  "timestamp": "2026-05-20T10:00:00Z",
  "level": "info",
  "service": "04a-scanner-slither",
  "event": "Scan completed",
  "audit_id": "abc-123",
  "findings_count": 5,
  "duration_seconds": 12.5
}
```

**Plus: Correlation ID**

Tambahkan `X-Request-ID` / `trace_id` ke setiap request:
```python
import uuid

@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4())[:8])
    with structlog.contextvars.bind_contextvars(trace_id=trace_id):
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response
```

### 2.3 Health Monitoring Dashboard

File baru: `services/15-dashboard/frontend/src/pages/ServiceHealth.tsx` **(enhance existing)**

Tambahkan fitur ke halaman Service Health yang sudah ada:

```
1. SERVICE DEPENDENCY GRAPH
   Visualisasi DAG (Directed Acyclic Graph) dari dependencies antar service:
   
   01-config ──▶ 02-immunefi ──▶ 03-source ──▶ 04-scanner ──▶ ... ──▶ 11-orchestrator
                     │                                                │
                     └──▶ 16-submission ───────────────────────────────┘
   
   Setiap node:
   - 🟢 Hijau: Healthy (CPU < 70%, memory < 80%, latency < 500ms)
   - 🟡 Kuning: Degraded
   - 🔴 Merah: Down
   - ⚪ Abu-abu: No data

2. REAL-TIME METRICS via SSE
   - Request rate (req/s)
   - Error rate (%)
   - P50 / P95 / P99 latency
   - CPU / Memory usage

3. ALERT CONFIGURATION
   - Threshold settings per service
   - Notification channel (Discord, Telegram, Email)
   - Alert history log
```

File baru: `services/15-dashboard/src/health_monitor.py`

```python
"""Health monitor — periodically checks all 20 services and aggregates status.

Endpoints:
  GET /api/health/graph     → Dependency graph + status per service
  GET /api/health/metrics   → Aggregated metrics across all services
  POST /api/health/alert    → Configure alert thresholds
"""

import httpx
from datetime import datetime, timedelta

class HealthMonitor:
    def __init__(self):
        self.services = {
            "01-config":      {"url": "http://01-config:8000", "depends_on": []},
            "02-immunefi":    {"url": "http://02-immunefi:8000", "depends_on": ["01-config"]},
            "03-source":      {"url": "http://03-source:8000", "depends_on": ["01-config"]},
            "04-scanner":     {"url": "http://04-scanner:8000", "depends_on": ["01-config"]},
            "04a-slither":    {"url": "http://04a-scanner-slither:8000", "depends_on": ["01-config"]},
            "04b-echidna":    {"url": "http://04b-scanner-echidna:8000", "depends_on": ["01-config"]},
            "04c-forge":      {"url": "http://04c-scanner-forge:8000", "depends_on": ["01-config"]},
            "04d-halmos":     {"url": "http://04d-scanner-halmos:8000", "depends_on": ["01-config"]},
            "05-mythril":     {"url": "http://05-scanner-mythril:8000", "depends_on": ["01-config"]},
            "06-ai":          {"url": "http://06-ai:8000", "depends_on": ["01-config"]},
            "07-classifier":  {"url": "http://07-classifier:8000", "depends_on": ["06-ai", "01-config"]},
            "08-exploit":     {"url": "http://08-exploit:8000", "depends_on": ["07-classifier", "01-config"]},
            "09-reporter":    {"url": "http://09-reporter:8000", "depends_on": ["08-exploit", "01-config"]},
            "10-notifier":    {"url": "http://10-notifier:8000", "depends_on": ["09-reporter", "01-config"]},
            "11-orchestrator":{"url": "http://11-orchestrator:8000", "depends_on": ["02-immunefi", "03-source", "04-scanner", "06-ai", "07-classifier", "08-exploit", "09-reporter", "10-notifier", "01-config"]},
            "12-webhook":     {"url": "http://12-webhook:8000", "depends_on": ["01-config"]},
            "13-upkeep":      {"url": "http://13-upkeep:8000", "depends_on": ["01-config"]},
            "14-agent":       {"url": "http://14-agent:8000", "depends_on": ["01-config"]},
            "15-dashboard":   {"url": "http://localhost:8000", "depends_on": ["11-orchestrator", "01-config"]},
            "16-submission":  {"url": "http://16-submission:8000", "depends_on": ["01-config"]},
        }
    
    async def check_all(self) -> dict:
        """Check health of all 20 services in parallel."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            tasks = {name: self._check_one(client, name, info) for name, info in self.services.items()}
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            return {name: r if isinstance(r, dict) else {"status": "error", "error": str(r)} for name, r in zip(self.services.keys(), results)}
    
    async def _check_one(self, client, name, info):
        try:
            resp = await client.get(f"{info['url']}/health")
            if resp.status_code == 200:
                return {"status": "healthy", "code": 200}
            return {"status": "degraded", "code": resp.status_code}
        except Exception as e:
            return {"status": "down", "error": str(e)}
```

### 2.4 Agent Memory System Implementation

**Latar belakang**: `services/14-agent/src/memory/` saat ini hanya stub kosong. Kita perlu implementasi 3 tipe memory yang memungkinkan Agent belajar dari kasus sebelumnya.

**Base memory interface:**

File baru: `services/14-agent/src/memory/base.py`
```python
"""Base memory interface — semua memory type mengikuti interface ini."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Optional

@dataclass
class MemoryEntry:
    id: str
    content: str
    metadata: dict
    timestamp: str
    embedding: Optional[List[float]] = None

class BaseMemory(ABC):
    @abstractmethod
    async def store(self, entry: MemoryEntry) -> str: ...
    @abstractmethod
    async def retrieve(self, query: str, limit: int = 5) -> List[MemoryEntry]: ...
    @abstractmethod
    async def delete(self, entry_id: str) -> bool: ...
    @abstractmethod
    async def clear(self) -> None: ...
```

**1. Vector Memory (Semantic Search)**

File baru: `services/14-agent/src/memory/vector_store.py`

```python
"""Vector memory — semantic search via embedding similarity.

Storage: ~/.sc_auditor/learning/vector_index.json
Embedding: local (sentence-transformers) atau via LLM API

Digunakan untuk:
- Mencari kasus mirip berdasarkan deskripsi bug
- Pattern matching: "bug ini mirip dengan CASE-012 yang bounty $10k"
"""

from sentence_transformers import SentenceTransformer
import numpy as np

class VectorMemory(BaseMemory):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.index: List[MemoryEntry] = []
    
    async def store(self, entry: MemoryEntry) -> str:
        entry.embedding = self.model.encode(entry.content).tolist()
        self.index.append(entry)
        return entry.id
    
    async def retrieve(self, query: str, limit: int = 5) -> List[MemoryEntry]:
        query_emb = self.model.encode(query)
        scores = [
            (np.dot(query_emb, e.embedding) / 
             (np.linalg.norm(query_emb) * np.linalg.norm(e.embedding)), e)
            for e in self.index if e.embedding
        ]
        scores.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scores[:limit]]
```

**2. Episodic Memory (Experience Recall)**

File baru: `services/14-agent/src/memory/episodic.py`

```python
"""Episodic memory — menyimpan pengalaman audit sebelumnya.

Setiap episode = satu siklus audit:
  {contract, scanner_output, findings, actions_taken, outcome}

Digunakan untuk:
- Agent mengingat "waktu terakhir audit contract ini, begini hasilnya"
- Learning dari kegagalan: "waktu itu PoC gagal, coba approach berbeda"
"""

class EpisodicMemory(BaseMemory):
    def __init__(self):
        self.episodes: List[dict] = []
    
    async def store_episode(self, episode: dict) -> str:
        episode["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.episodes.append(episode)
        return episode.get("id", str(uuid.uuid4()))
    
    async def retrieve_similar(self, contract: str, function: str = None) -> List[dict]:
        """Cari episode audit sebelumnya untuk contract yang sama."""
        results = [e for e in self.episodes if e.get("contract") == contract]
        if function:
            results = [e for e in results if e.get("function") == function]
        return sorted(results, key=lambda e: e["timestamp"], reverse=True)[:5]
```

**3. Graph Memory (Knowledge Graph)**

File baru: `services/14-agent/src/memory/graph_memory.py`

```python
"""Graph memory — knowledge graph of vulnerabilities.

Nodes:
  - Contract (address, chain, compiler_version)
  - Function (name, signature)
  - Vulnerability (type, severity, pattern)
  - Fix (pattern, recommendation)

Edges:
  - Contract HAS_FUNCTION Function
  - Function HAS_VULN Vulnerability
  - Vulnerability FIXED_BY Fix
  - Vulnerability SIMILAR_TO Vulnerability
"""

class GraphMemory:
    def __init__(self):
        self.nodes: dict = {}
        self.edges: List[tuple] = []
    
    def add_node(self, node_id: str, node_type: str, properties: dict):
        self.nodes[node_id] = {"type": node_type, "properties": properties}
    
    def add_edge(self, from_id: str, to_id: str, rel: str):
        self.edges.append((from_id, to_id, rel))
    
    def find_path(self, from_type: str, to_type: str, max_depth: int = 3) -> List:
        """Find connection paths between node types."""
        # BFS traversal
        ...
```

**Integrasi dengan Agent:**

File: `services/14-agent/src/memory/__init__.py` (update)

```python
"""Agent memory system — vector + episodic + graph memory.

Integrasi dengan Case Management (Agenda 05):
  - Setiap CASE CLOSED → masuk ke VectorMemory sebagai pattern
  - Setiap audit selesai → masuk ke EpisodicMemory sebagai episode
  - Pattern vulnerability → masuk ke GraphMemory sebagai node/edge
"""

from .vector_store import VectorMemory
from .episodic import EpisodicMemory
from .graph_memory import GraphMemory

class AgentMemory:
    def __init__(self):
        self.vector = VectorMemory()
        self.episodic = EpisodicMemory()
        self.graph = GraphMemory()
    
    async def learn_from_case(self, case_data: dict):
        """Learn from a closed case."""
        # Store as vector for semantic search
        await self.vector.store(MemoryEntry(
            id=case_data["case_id"],
            content=f"{case_data['description']} {case_data['recommendation']}",
            metadata={"severity": case_data['severity'], "bounty": case_data.get('bounty_amount')},
            timestamp=case_data.get('closed_at', datetime.now(timezone.utc).isoformat()),
        ))
        
        # Store as graph node
        self.graph.add_node(
            case_data["case_id"], "vulnerability",
            {"title": case_data["title"], "severity": case_data["severity"]}
        )
    
    async def find_similar_cases(self, description: str, limit: int = 5) -> List:
        """Find similar cases by semantic similarity."""
        return await self.vector.retrieve(description, limit=limit)
```

---

## 3. Struktur File

```
services/
├── shared/
│   └── metrics.py                       # 🆕 Shared Prometheus metrics

services/14-agent/src/memory/
├── __init__.py                          # ✏️ Enhanced with AgentMemory
├── base.py                              # 🆕 Base memory interface
├── vector_store.py                      # 🆕 Vector memory (semantic)
├── episodic.py                          # 🆕 Episodic memory (experiences)
└── graph_memory.py                      # 🆕 Graph memory (knowledge graph)

services/15-dashboard/
├── app.py                               # ✏️ + /api/health/graph, /api/health/metrics
├── src/
│   └── health_monitor.py                # 🆕 Health check aggregator
├── frontend/src/pages/
│   └── ServiceHealth.tsx                # ✏️ Enhanced: dependency graph + metrics

services/*/app.py                        # ✏️ + /metrics endpoint, JSON logging, trace_id
```

---

## 4. Task List

| # | Task | File | Estimasi |
|---|------|------|----------|
| T1 | Buat shared metrics module | `services/shared/metrics.py` | 15 min |
| T2 | Buat base memory interface | `services/14-agent/src/memory/base.py` | 10 min |
| T3 | Implement vector memory | `services/14-agent/src/memory/vector_store.py` | 20 min |
| T4 | Implement episodic memory | `services/14-agent/src/memory/episodic.py` | 15 min |
| T5 | Implement graph memory | `services/14-agent/src/memory/graph_memory.py` | 20 min |
| T6 | Update memory __init__.py dengan AgentMemory | `services/14-agent/src/memory/__init__.py` | 10 min |
| T7 | Buat health monitor aggregator | `services/15-dashboard/src/health_monitor.py` | 20 min |
| T8 | Tambah health graph API endpoints | `services/15-dashboard/app.py` | 10 min |
| T9 | Tambah /metrics endpoint ke semua 20 services | `services/*/app.py` | ~5 min each = 100 min |
| T10 | Standarisasi JSON logging (structlog) | `services/*/app.py` | ~3 min each = 60 min |
| T11 | Tambah trace_id middleware ke semua services | `services/*/app.py` | ~3 min each = 60 min |
| T12 | Enhance ServiceHealth page (dependency graph) | `frontend/src/pages/ServiceHealth.tsx` | 30 min |
| T13 | Tambah requirements (prometheus-client, sentence-transformers) | `services/*/requirements.txt` | 10 min |
| | **Total** | | **~380 menit** |

---

## 5. Quality Gate

| Dimensi | Target | Cara Ukur |
|---------|--------|-----------|
| Correctness | 90% | /metrics endpoint returns valid Prometheus format di semua service |
| Performance | 85% | Metrics collection overhead < 5ms per request |
| Security | 85% | Metrics endpoint tidak expose data sensitif |
| Maintainability | 90% | Shared metrics module, memory interface abstraction |
| Completeness | 100% | Semua 20 services punya metrics + JSON logging |
| Alignment | 100% | Gap dari audit ter-cover semua |

---

*Dibuat: 2026-05-20 | Status: OPEN | Dependensi: Agenda 09*
