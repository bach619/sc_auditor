# Prioritas 1 — Stabilitas & Testing Foundation (Bulan 1)

> Target: **71 → 75/100 (Grade B)** | Timeline: 2 minggu

---

## 1. FIX 11 CRASHING SERVICES → 28/28 UP

**Current**: 17 Up, 11 Restarting. Tidak bisa production.

### Step 1: Diagnosa

```bash
# Kumpulkan semua log error
docker compose logs 01-config --tail=15    > crash_logs/01-config.log
docker compose logs 04-scanner --tail=15   > crash_logs/04-scanner.log
docker compose logs 04b-echidna --tail=15  > crash_logs/04b-echidna.log
docker compose logs 04c-forge --tail=15    > crash_logs/04c-forge.log
docker compose logs 07-classifier --tail=15> crash_logs/07-classifier.log
docker compose logs 18-code4rena --tail=15 > crash_logs/18-code4rena.log
docker compose logs 19-sherlock --tail=15  > crash_logs/19-sherlock.log
docker compose logs 20-cantina --tail=15   > crash_logs/20-cantina.log
docker compose logs 21-hats --tail=15      > crash_logs/21-hats.log
docker compose logs 22-source-starknet --tail=15 > crash_logs/22-starknet.log
docker compose logs 23-scanner-cairo --tail=15   > crash_logs/23-cairo.log
```

### Step 2: Kategorikan Error

| Error Type | Kemungkinan Service | Fix |
|------------|---------------------|-----|
| `ModuleNotFoundError: No module named 'shared'` | 01-config? 07-classifier? | Cek Dockerfile COPY path |
| `Connection refused` ke service lain | 04-scanner? 04b-echidna? | Tambah `depends_on` + `condition: service_healthy` |
| `Missing env var` | 18-21 bounty platforms? | Tambah di docker-compose environment |
| `solc` / tool binary not found | 04c-forge? 22-23 starknet? | Cek Docker image build |
| `Permission denied` | 01-config? | Cek volume mount UID/GID |
| Timeout startup | 04b-echidna? 04e-manticore? | Tambah `start_period` di healthcheck |

### Step 3: Fix per Kategori

```yaml
# Contoh: tambah depends_on + health condition
# docker-compose.yml
  04-scanner:
    depends_on:
      01-config:
        condition: service_healthy
      03-source:
        condition: service_healthy
```

### Step 4: Verifikasi

```bash
docker compose down
docker compose build 01-config 04-scanner 04b-echidna 04c-forge 07-classifier 18-23
docker compose up -d
sleep 30
docker compose ps
# Target: semua 28 service = Up
```

**Estimasi**: 3-4 jam
**Success criteria**: `docker compose ps` → 28/28 Up

---

## 2. TESTING — 50+ Unit Tests untuk Critical Path

**Current**: 314 tests / 100,720 lines = 0.3%. Target Bulan 1: 25% coverage.

### 2A. Orchestrator Pipeline Tests (PALING PENTING)

**File**: `tests/test_pipeline_states.py`
**Target**: 20 tests

```python
class TestPipelineStateMachine:
    """Pipeline 8-stage state machine — setiap transisi harus di-test."""

    def test_initial_state_is_pending(self):
        """Audit harus mulai dari PENDING."""

    def test_pending_to_fetching_program_success(self):
        """PENDING → FETCHING_PROGRAM transisi sukses."""

    def test_pending_to_fetching_program_http_error(self):
        """Jika 02-immunefi return 500 → FETCH_FAILED."""

    def test_fetching_source_from_etherscan(self):
        """FETCHING_SOURCE → SCANNING dengan source code valid."""

    def test_fetching_source_not_verified(self):
        """Source tidak verified → FETCH_FAILED."""

    def test_scanning_all_tools_success(self):
        """5 scanner tools jalan paralel → semua sukses."""

    def test_scanning_one_tool_fails_others_continue(self):
        """1 tool crash → tool lain tetap jalan → partial results."""

    def test_ai_analysis_with_findings(self):
        """Findings dikirim ke 06-ai → hasil analisis kembali."""

    def test_ai_analysis_no_findings(self):
        """Tidak ada findings → skip AI → langsung REPORTING."""

    def test_classifying_tp_fp_tn_fn(self):
        """Classifier return TP, FP, TN, FN dengan benar."""

    def test_exploit_generation_for_critical(self):
        """CRITICAL finding → trigger exploit generation di 08-exploit."""

    def test_exploit_skip_for_low_severity(self):
        """LOW severity → skip exploit generation."""

    def test_reporting_generates_markdown(self):
        """REPORTING → 09-reporter generate immunefi.md + full.md."""

    def test_notifying_sends_discord_telegram(self):
        """NOTIFYING → 10-notifier kirim ke Discord + Telegram."""

    def test_completed_state_final(self):
        """COMPLETED → audit selesai, data tersimpan."""

    def test_retry_on_transient_failure(self, mocker):
        """Fetch gagal → retry 3x dengan exponential backoff."""

    def test_max_retries_exceeded_triggers_failed(self):
        """Retry 3x gagal → state = FETCH_FAILED."""

    def test_saga_rollback_on_step_failure(self):
        """SCANNING gagal → rollback FETCHING_SOURCE + FETCHING_PROGRAM."""

    def test_concurrent_audits_independent(self):
        """3 audit paralel → tidak corrupt state satu sama lain."""

    def test_audit_timeout_kills_stuck_pipeline(self):
        """Pipeline step > 300 detik → timeout → FAILED."""
```

### 2B. Classifier Logic Tests

**File**: `tests/test_classifier_logic.py`
**Target**: 15 tests

```python
class TestClassifier:
    def test_true_positive_detection(self):
        """Known reentrancy → classifier harus return TP."""

    def test_false_positive_filtering(self):
        """Compiler warning → classifier harus return FP."""

    def test_true_negative_handling(self):
        """Clean code → classifier harus return TN."""

    def test_false_negative_learning(self):
        """PatternLearner harus belajar dari human feedback."""

    def test_confidence_scoring_tp(self):
        """3 tool confirm → confidence > 0.9."""

    def test_confidence_scoring_fp(self):
        """1 tool only → confidence < 0.3."""

    def test_metrics_tracking_accuracy(self):
        """MetricsTracker harus hitung precision, recall, F1."""

    def test_pattern_effectiveness_decay(self):
        """Pattern yang sudah lama tidak match → turun score."""

    def test_cross_tool_consensus_high(self):
        """Slither + Mythril + Echidna agree → HIGH confidence."""

    def test_cross_tool_consensus_low(self):
        """Hanya Slither → LOW confidence."""
```

### 2C. Exploit Engine Tests (Mock Anvil)

**File**: `tests/test_exploit_engine.py`
**Target**: 10 tests

```python
class TestExploitEngine:
    def test_fork_mainnet_success(self, mocker):
        """Fork mainnet di block tertentu → Anvil container jalan."""

    def test_exploit_execution_reentrancy(self):
        """Reentrancy PoC → exploit sukses, profit > 0."""

    def test_exploit_execution_fails_gracefully(self):
        """PoC gagal → return failure, bukan crash."""

    def test_hypothesis_generation_ai(self, mocker):
        """AI generate 3-5 exploit hypotheses."""

    def test_hypothesis_testing_sequential(self):
        """Test hypotheses satu per satu sampai ketemu yang works."""

    def test_sanitization_removes_sensitive(self):
        """Output sanitizer hapus private key, RPC URL, etc."""

    def test_docker_cleanup_after_exploit(self):
        """Anvil container di-cleanup setelah exploit selesai."""
```

### 2D. Config Service Tests

**File**: `tests/test_config_service.py`
**Target**: 10 tests

```python
class TestConfigService:
    def test_load_defaults(self):
        """Config kosong → load defaults."""

    def test_get_existing_key(self):
        """Key yang ada → return value."""

    def test_get_missing_key_returns_none(self):
        """Key tidak ada → return None."""

    def test_set_new_key_persists(self):
        """Set key baru → restart service → key masih ada."""

    def test_delete_key_removes(self):
        """Delete key → key hilang."""

    def test_bulk_upsert_atomic(self):
        """Bulk upsert 10 keys → semua tersimpan."""

    def test_reset_restores_defaults(self):
        """Reset → semua key kembali ke default."""

    def test_dual_write_sqlite_and_json(self):
        """STORAGE_ENGINE=dual → data di SQLite dan JSON identik."""

    def test_sqlite_to_json_rollback(self):
        """Switch STORAGE_ENGINE=json → data tetap bisa dibaca."""
```

### 2E. Immunefi Sync Tests

**File**: `tests/test_immunefi_sync.py`
**Target**: 5 tests

```python
class TestImmunefiSync:
    def test_sync_programs_from_github(self):
        """Fetch program list dari GitHub → parse JSON."""

    def test_detect_new_programs(self):
        """Program baru terdeteksi → di-add ke database."""

    def test_detect_updated_programs(self):
        """Program update → history tercatat."""

    def test_indexing_by_chain(self):
        """Filter program by chain → return results."""

    def test_rate_limit_handling(self):
        """GitHub rate limit → exponential backoff retry."""
```

**Estimasi**: 3-4 hari untuk 50 tests
**Verifikasi**: `pytest tests/test_pipeline_states.py tests/test_classifier_logic.py tests/test_exploit_engine.py tests/test_config_service.py tests/test_immunefi_sync.py -v`

---

## 3. CI/CD COVERAGE GATE

### Update `.github/workflows/ci.yml`

```yaml
# Tambah setelah existing test step
- name: Run tests with coverage
  run: |
    pip install pytest-cov
    pytest \
      --cov=services/ \
      --cov-report=xml \
      --cov-report=term-missing \
      --cov-fail-under=25 \
      tests/

- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v4
  with:
    files: ./coverage.xml
    fail_ci_if_error: false

- name: Coverage Report
  if: always()
  run: |
    echo "## Coverage Report" >> $GITHUB_STEP_SUMMARY
    grep "TOTAL" coverage.txt >> $GITHUB_STEP_SUMMARY || echo "Coverage: check CI logs"
```

### Threshold Progression

```yaml
# Bertahap naik setiap bulan:
# Bulan 1: --cov-fail-under=25
# Bulan 2: --cov-fail-under=50
# Bulan 3: --cov-fail-under=70
# Production: --cov-fail-under=80
```

**Estimasi**: 1 jam
**Verifikasi**: PR dengan coverage < 25% → CI fail

---

## Checklist Bulan 1

```
[ ] Diagnosa 11 crashed services — kumpulkan logs
[ ] Kategorikan error (import / env / dependency / binary / permission)
[ ] Fix batch 1 — import & env issues
[ ] Fix batch 2 — dependency & healthcheck issues
[ ] Rebuild semua affected services
[ ] Verify: docker compose ps → 28/28 Up
[ ] Tulis 20 orchestrator pipeline tests
[ ] Tulis 15 classifier logic tests
[ ] Tulis 10 exploit engine tests
[ ] Tulis 10 config service tests
[ ] Tulis 5 immunefi sync tests
[ ] Run semua 60 tests → green
[ ] Setup coverage gate di CI (25% threshold)
[ ] Verify: CI pipeline passes with coverage check
[ ] Update SYSTEM_LOG.md
```

---

## 🔴 GAP COVERAGE — Item yang sebelumnya terlewat

### A. INTEGRATION TESTS — Cross-Service E2E Flow

**Problem**: Unit test hanya uji 1 service. Tidak ada yang uji pipeline dari Immunefi → Report.

**File**: `tests/test_e2e_pipeline.py`
**Target**: 5 tests

```python
class TestE2EPipeline:
    """Full pipeline integration — dari program Immunefi sampai report."""

    def test_immunefi_to_report_complete_flow(self, docker_services):
        """1 audit lengkap: Immunefi → Source → Scanner → AI → Classify → Report."""
        # 1. Fetch program dari Immunefi (mock)
        # 2. Fetch source code (mock Etherscan)
        # 3. Scan dengan semua tools (mock scanner responses)
        # 4. AI analysis (mock AI)
        # 5. Classify findings
        # 6. Generate report
        # 7. Verify report exists + format benar

    def test_pipeline_handles_service_down(self):
        """Jika 1 service down, pipeline harus graceful degradation."""

    def test_pipeline_with_real_slither(self):
        """Integration test dengan Slither asli (bukan mock)."""

    def test_concurrent_5_audits_no_interference(self):
        """5 audit paralel → data masing-masing tidak tercampur."""

    def test_audit_resume_after_crash(self):
        """Audit di tengah jalan → restart orchestrator → resume dari step terakhir."""
```

### B. STANDARDIZED ERROR RESPONSE FORMAT

**Problem**: Setiap service return error format berbeda. Tidak konsisten.

**Action**: Standardize semua service ke format:

```python
# Semua service pakai format ini:
{
    "meta": {
        "status": "error",
        "code": "PIPELINE_STEP_FAILED",
        "message": "Scanner slither failed: connection timeout",
        "request_id": "a1b2c3d4",
        "timestamp": "2026-06-04T12:00:00Z"
    },
    "data": null,
    "error": {
        "type": "SCANNER_ERROR",
        "detail": "Connection to 04a-scanner-slither:8014 timed out after 30s",
        "retryable": true,
        "retry_after_seconds": 5
    }
}
```

**Implementation**:

```python
# services/shared/errors.py
from fastapi.responses import JSONResponse

class VyperError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 500, 
                 retryable: bool = False, detail: str = ""):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.detail = detail

def error_response(error: VyperError, request_id: str = "") -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "meta": {
                "status": "error",
                "code": error.code,
                "message": error.message,
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "data": None,
            "error": {
                "type": error.code,
                "detail": error.detail or error.message,
                "retryable": error.retryable,
            }
        }
    )

# Usage di service:
@app.get("/config/{key:path}")
async def get_config(request: Request, key: str):
    value = mgr.get(key)
    if value is None and key not in mgr.get_all():
        raise HTTPException(status_code=404, detail=f"Key '{key}' not found")
    return {"meta": {"status": "ok"}, "data": {key: value}}
```

### C. DRY — Extract JSON Pattern (109 locations → 1)

**Problem**: Atomic JSON write pattern diulang 109 kali. Setiap perubahan pattern = edit 109 file.

**Action**: Buat shared utility, ganti semua 109 lokasi.

```python
# services/shared/json_utils.py
import json, os, shutil, tempfile
from pathlib import Path

def atomic_json_write(path: Path, data: dict | list) -> None:
    """Atomic JSON write — tmp file + os.replace. Thread-safe."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".tmp", prefix="json_", dir=str(path.parent))
    try:
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            f.flush()
        shutil.move(tmp, str(path))
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise

def atomic_json_read(path: Path, default=None) -> dict | list | None:
    """Read JSON with fallback default."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default
```

```bash
# Migrasi bertahap: ganti pattern di semua service
# Pattern lama:
#   tmp = path.with_suffix(".tmp")
#   json.dump(data, ...)
#   tmp.replace(path)
#
# Pattern baru:
#   from shared.json_utils import atomic_json_write, atomic_json_read
#   atomic_json_write(path, data)
#   data = atomic_json_read(path, default={})
```

---

## Checklist Bulan 1 — UPDATED

```
[ ... checklist sebelumnya ... ]
[ ] Tulis 5 integration tests (E2E pipeline)
[ ] Standardize error response format (shared/errors.py)
[ ] Terapkan error format ke 4 P0 services
[ ] Buat shared/json_utils.py (atomic read/write)
[ ] Migrasi 10 lokasi JSON pattern pertama (P0 services)
[ ] Verify: format error konsisten di /health + /config + /classify
[ ] Verify: atomic_json_write() dipakai di 01-config, 07-classifier
```

---

*Agenda 29 — Prioritas 1 — Bulan 1*
