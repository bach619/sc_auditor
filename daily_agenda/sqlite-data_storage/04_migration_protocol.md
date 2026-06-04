# 04 — Migration Protocol: Gradual, Zero-Downtime, Rollback-Ready

> **Agenda**: 27 — SQLite Data Storage
> **Bagian**: 4 dari 4
> **Tipe**: Operations → Migration Protocol
> **Tanggal**: 2026-06-04

---

## Prinsip Utama

```
┌─────────────────────────────────────────────────────────┐
│              MIGRATION PRINCIPLES                        │
│                                                         │
│  1. GRADUAL — 1 service per waktu, tidak big-bang       │
│  2. DUAL-WRITE — SQLite + JSON selama transisi          │
│  3. ROLLBACK-READY — instant switch ke JSON via env var │
│  4. VERIFY — setiap step ada validation checkpoint      │
│  5. BACKUP — full /data/ backup sebelum setiap migrasi  │
│  6. ZERO-DOWNTIME — pipeline bisa pause, bukan crash    │
└─────────────────────────────────────────────────────────┘
```

---

## 1. Pre-Migration: Backup Strategy

### 1.1 Full System Backup (Sebelum Mulai)

```bash
#!/bin/bash
# backup_before_migration.sh
# Jalan di host (bukan container)

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups/pre_migration_${TIMESTAMP}"

echo "=== BACKUP FULL /data/ DIRECTORY ==="

# Stop services gracefully (tapi container tetap ada)
docker compose stop

# Copy all volumes to backup
mkdir -p "$BACKUP_DIR"
for vol in $(docker volume ls -q | grep vyper_); do
    echo "Backing up: $vol"
    docker run --rm \
        -v ${vol}:/source:ro \
        -v ${BACKUP_DIR}:/backup \
        alpine cp -a /source "/backup/${vol}"
done

# Also backup docker-compose.yml
cp docker-compose.yml "$BACKUP_DIR/"
cp .env.example "$BACKUP_DIR/"

# Compress
tar -czf "${BACKUP_DIR}.tar.gz" -C "$BACKUP_DIR" .
rm -rf "$BACKUP_DIR"

echo "=== BACKUP COMPLETE: ${BACKUP_DIR}.tar.gz ==="
echo "Size: $(du -h ${BACKUP_DIR}.tar.gz | cut -f1)"
```

### 1.2 Per-Service Backup (Sebelum Setiap Migrasi)

```bash
#!/bin/bash
# backup_service.sh <service_name>
# Jalan sebelum migrasi setiap service

SERVICE=$1
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="./backups/${SERVICE}_${TIMESTAMP}.tar.gz"

echo "=== BACKUP $SERVICE ==="

# Find volume matching service
VOLUME=$(docker volume ls -q | grep "vyper_${SERVICE/_/-}" | head -1)

if [ -z "$VOLUME" ]; then
    echo "Warning: No dedicated volume found for $SERVICE, checking compose..."
    VOLUME="vyper_$(echo $SERVICE | sed 's/^[0-9]*[-]//;s/_/-/g')"
fi

# Backup
docker run --rm \
    -v ${VOLUME}:/source:ro \
    -v $(pwd)/backups:/backup \
    alpine tar -czf "/backup/${SERVICE}_${TIMESTAMP}.tar.gz" -C /source .

echo "Backup saved: ./backups/${SERVICE}_${TIMESTAMP}.tar.gz"
```

---

## 2. Migration Protocol: Per-Service Step-by-Step

### 2.1 Protocol Template (Untuk Setiap Service)

```
┌─────────────────────────────────────────────────────────┐
│  STEP 1: PRE-MIGRATION                                   │
│  ├── Backup volume (script backup_service.sh)            │
│  ├── Verify backup integrity                            │
│  ├── Inform orchestrator: pause new audits               │
│  └── Wait active audits complete                        │
│                                                         │
│  STEP 2: DEPLOY DUAL-WRITE MODE                         │
│  ├── Build service image (docker compose build SERVICE) │
│  ├── Set STORAGE_ENGINE=dual in docker-compose.yml      │
│  ├── Deploy → service writes to BOTH SQLite & JSON      │
│  ├── Health check: GET /health → {storage: "dual"}      │
│  └── Wait 1 jam — verifikasi tidak error               │
│                                                         │
│  STEP 3: MIGRATE HISTORICAL DATA                        │
│  ├── Run migration script (JSON → SQLite import)        │
│  ├── Verify row counts match                            │
│  ├── Verify random sample (5% of data)                  │
│  └── Checksum comparison                                │
│                                                         │
│  STEP 4: VERIFY ZERO REGRESSION                         │
│  ├── Run integration tests                              │
│  ├── Run E2E pipeline (if applicable)                   │
│  ├── Check downstream services OK                       │
│  └── Monitor for 2 jam — no errors                      │
│                                                         │
│  STEP 5: CUT-OVER TO SQLITE ONLY                        │
│  ├── Set STORAGE_ENGINE=sqlite in docker-compose.yml    │
│  ├── Rebuild & redeploy service                         │
│  ├── Health check: GET /health → {storage: "sqlite"}    │
│  └── Verify all data accessible via SQL queries         │
│                                                         │
│  STEP 6: ARCHIVE JSON DATA                              │
│  ├── Move JSON files from volume to backup archive      │
│  ├── Keep backup for 30 days                            │
│  └── Recovery plan documented                           │
│                                                         │
│  STEP 7: LOG & REPORT                                   │
│  ├── Log to SYSTEM_LOG.md                               │
│  ├── Update migration tracker                           │
│  └── Report lessons learned                             │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Dual-Write Environment Variable

```yaml
# docker-compose.yml overlay untuk service yg sedang migrasi
services:
  07-classifier:
    environment:
      # Fase transisi:
      - STORAGE_ENGINE=dual        # Tulis SQLite + JSON
      # Setelah verified:
      # - STORAGE_ENGINE=sqlite    # SQLite only
      # Rollback:
      # - STORAGE_ENGINE=json      # Kembali ke JSON
```

### 2.3 Historical Data Migration Script

```python
#!/usr/bin/env python3
"""migrate_historical.py — One-shot JSON → SQLite migration."""

import json
import sys
from pathlib import Path
from shared.storage import SqliteStore, StoreConfig

def migrate_service(
    service_name: str,
    json_dir: Path,
    sqlite_path: str,
    table_name: str,
    transform: callable = None,  # Optional data transform
):
    """Migrate all JSON files in json_dir to SQLite table."""
    store = SqliteStore(StoreConfig(db_path=sqlite_path))
    
    json_files = list(json_dir.glob("*.json"))
    print(f"[{service_name}] Found {len(json_files)} JSON files to migrate")
    
    migrated = 0
    errors = 0
    
    for jf in json_files:
        try:
            data = json.loads(jf.read_text())
            if transform:
                data = transform(data, jf.stem)
            store.insert(table_name, data)
            migrated += 1
        except Exception as e:
            print(f"  Error migrating {jf.name}: {e}")
            errors += 1
    
    # Verify
    sqlite_count = store.query_one(
        f"SELECT COUNT(*) as cnt FROM {table_name}"
    )["cnt"]
    
    print(f"[{service_name}] Migration complete:")
    print(f"  JSON files:   {len(json_files)}")
    print(f"  Migrated:     {migrated}")
    print(f"  Errors:       {errors}")
    print(f"  SQLite rows:  {sqlite_count}")
    print(f"  Match:        {'✅' if sqlite_count == migrated else '❌ MISMATCH!'}")
    
    return migrated, errors

# Example: migrate 07-classifier
if __name__ == "__main__":
    migrate_service(
        service_name="07-classifier",
        json_dir=Path("/data/classifier/findings/"),
        sqlite_path="/data/classifier/findings.db",
        table_name="findings",
    )
```

---

## 3. Rollback Protocol

### 3.1 Instant Rollback (Per Service)

```bash
# Rollback 07-classifier ke JSON
# 1. Set env var
export STORAGE_ENGINE=json

# 2. Redeploy
docker compose stop 07-classifier
docker compose up -d 07-classifier

# 3. Verify
curl http://localhost:8005/health
# {"storage": "json", "status": "ok"}
```

**Waktu rollback**: <30 detik
**Data integrity**: JSON files tidak dihapus selama dual-write phase. Masih utuh.

### 3.2 Full Rollback (Semua Service)

```bash
#!/bin/bash
# full_rollback.sh
# Kembalikan SEMUA service ke JSON mode

echo "=== FULL ROLLBACK ==="

# 1. Set semua service ke JSON mode
sed -i 's/STORAGE_ENGINE=.*/STORAGE_ENGINE=json/' docker-compose.yml

# 2. Redeploy all
docker compose down
docker compose up -d

# 3. Health check all services
sleep 10
python scripts/health_check_all.py

echo "=== ROLLBACK COMPLETE ==="
```

### 3.3 Disaster Recovery (Worst Case)

```bash
#!/bin/bash
# disaster_recovery.sh
# Jika backup perlu di-restore dari full backup

BACKUP_TAR="./backups/pre_migration_20260604_120000.tar.gz"
RESTORE_DIR="./restore_temp"

echo "=== DISASTER RECOVERY ==="

# 1. Stop everything
docker compose down -v  # Hapus containers + volumes

# 2. Extract backup
mkdir -p "$RESTORE_DIR"
tar -xzf "$BACKUP_TAR" -C "$RESTORE_DIR"

# 3. Restore volumes
for vol_dir in "$RESTORE_DIR"/vyper_*; do
    vol_name=$(basename "$vol_dir")
    docker volume create "$vol_name"
    docker run --rm \
        -v ${vol_name}:/target \
        -v ${vol_dir}:/source:ro \
        alpine cp -a /source/. /target/
done

# 4. Restart
docker compose up -d

echo "=== RECOVERY COMPLETE ==="
```

---

## 4. Validation Checklist (Per Service Migration)

### 4.1 Pre-Deployment Validation

| Check | Command/Verification | Expected |
|-------|---------------------|----------|
| Backup exists | `ls -la backups/*.tar.gz` | File > 0 bytes |
| Backup integrity | `tar -tzf backups/XYZ.tar.gz > /dev/null` | No errors |
| No active audits | `curl orchestrator:8009/active-audits` | `{"count": 0}` |
| Current health OK | `curl service:PORT/health` | `{"status":"ok"}` |

### 4.2 Post-Deployment Validation (Dual-Write)

| Check | Command/Verification | Expected |
|-------|---------------------|----------|
| Service running | `docker compose ps` | `Up (healthy)` |
| Storage mode | `curl service:PORT/health` | `{"storage":"dual"}` |
| SQLite write OK | Trigger a write via API | SQLite file timestamp updated |
| JSON write OK | Check JSON file timestamp | JSON file timestamp updated |
| Data identical | Diff SQLite row vs JSON entry | Match |

### 4.3 Post-Migration Validation (SQLite Only)

| Check | Command/Verification | Expected |
|-------|---------------------|----------|
| Data complete | `SELECT COUNT(*) FROM table` vs JSON file count | Equal |
| Random sample | Pick 5% of rows, compare with JSON | 100% match |
| Performance | Query time for 10K rows | <20ms |
| No errors in logs | `docker compose logs service \| grep -i error` | No errors |
| Downstream OK | Call downstream service endpoints | 200 OK |

---

## 5. Orchestrator Integration: Pipeline Pause/Resume

### 5.1 Pause Pipeline Sebelum Migrasi

```python
# curl -X POST orchestrator:8009/admin/pause
# Response: {"status": "paused", "active_audits": 3}

# Orchestrator akan:
# 1. Menghentikan polling audit baru
# 2. Menunggu audit aktif selesai (max 30 menit timeout)
# 3. Return ketika semua selesai atau timeout
```

### 5.2 Resume Setelah Migrasi

```python
# curl -X POST orchestrator:8009/admin/resume
# Response: {"status": "running", "queued_audits": 12}
```

---

## 6. Migration Tracker

### 6.1 Progress Table (di-update real-time)

```markdown
| Service | Phase | Storage | Date | Duration | Status | Rollback? |
|---------|-------|---------|------|----------|--------|-----------|
| 01-config | P0 | dual | - | - | ⬜ | - |
| 07-classifier | P0 | dual | - | - | ⬜ | - |
| 08-exploit | P0 | dual | - | - | ⬜ | - |
| 11-orchestrator | P0 | dual | - | - | ⬜ | - |
| ... | | | | | | |
```

### 6.2 Health Dashboard

Setelah semua service migrasi, health check menunjukkan:

```
STORAGE STATUS DASHBOARD
========================
01-config       sqlite  ✅ DB: 128KB
02-immunefi     sqlite  ✅ DB: 1.2MB  (234 programs)
03-source       sqlite  ✅ DB: 3.4MB  (89 contracts)
04-scanner      sqlite  ✅ DB: 4.2MB
04a-slither     sqlite  ✅ DB: 1.8MB
04b-echidna     sqlite  ✅ DB: 2.1MB
04c-forge       sqlite  ✅ DB: 0.9MB
04d-halmos      sqlite  ✅ DB: 0.5MB
04e-manticore   sqlite  ✅ DB: 1.2MB
05-mythril      sqlite  ✅ DB: 3.1MB
06-ai           sqlite  ✅ DB: 5.4MB  (cache: 127 entries)
07-classifier   sqlite  ✅ DB: 12.3MB (findings: 1,847)
08-exploit      sqlite  ✅ DB: 2.1MB
09-reporter     sqlite  ✅ DB: 1.5MB
10-notifier     sqlite  ✅ DB: 0.3MB
11-orchestrator sqlite  ✅ DB: 8.7MB  (audits: 89)
12-webhook      sqlite  ✅ DB: 0.2MB
13-upkeep       sqlite  ✅ DB: 4.1MB
14-agent        sqlite  ✅ DB: 6.8MB  (memory entries: 3,241)
15-dashboard    sqlite  ✅ DB: 2.1MB
16-submission   sqlite  ✅ DB: 0.5MB
17-experience   sqlite  ✅ DB: 1.2MB  (was already SQLite)
18-code4rena    sqlite  ✅ DB: 0.8MB
19-sherlock     sqlite  ✅ DB: 0.6MB
20-cantina      sqlite  ✅ DB: 0.4MB
21-hats         sqlite  ✅ DB: 0.5MB
22-source-stark sqlite  ✅ DB: 0.3MB
23-scanner-cairo sqlite ✅ DB: 0.2MB
─────────────────────────────────────
TOTAL STORAGE:  64.5 MB  (was ~180 MB JSON)
```

---

## 7. Monitoring & Alerts Selama Migrasi

### 7.1 Metrics to Watch

| Metric | Threshold | Action |
|--------|:---------:|--------|
| SQLite write latency | >100ms | Investigate WAL checkpoint config |
| SQLite query latency | >50ms | Add index |
| Disk usage growth rate | >10%/day | Check for runaway writes |
| WAL file size | >100MB | Trigger manual checkpoint |
| Error rate | >1% | Rollback service |
| Connection count | >50 per service | Check connection leak |

### 7.2 Alert Rules

```
ALERT StorageMigrationError
  IF error_count{service="*"} > 0
  FOR 5m
  LABELS { severity: "critical" }
  ANNOTATIONS {
    summary: "Migration error on {{ $labels.service }}",
    action: "Check logs: docker compose logs {{ $labels.service }}"
  }

ALERT StorageDiskSpace
  IF vyper_total_storage_mb > 1000
  FOR 10m
  LABELS { severity: "warning" }
  ANNOTATIONS {
    summary: "Total storage approaching 1GB",
    action: "Run vacuum on large databases"
  }
```

---

## 8. Lessons Learned Template

Setelah setiap service selesai migrasi, catat di `daily_agenda/lessons-learned.md`:

```markdown
### Migration: 07-classifier (2026-06-05)
- **Duration**: 45 menit (termasuk historical data import)
- **Issues**: WAL checkpoint triggered during peak write → 2 detik latency spike
  - **Fix**: Adjusted `wal_autocheckpoint` to 1000 pages
- **Rollback count**: 0
- **Data loss**: 0
- **Performance gain**: Query time dari 850ms → 3ms (283x faster)
- **Surprise**: JSON directory hierarchy nesting tidak cocok dengan flat SQLite
  - **Workaround**: Split into `findings` + `finding_files` tables
```

---

*Agenda 27 — Bagian 4/4 | Migration Protocol*
