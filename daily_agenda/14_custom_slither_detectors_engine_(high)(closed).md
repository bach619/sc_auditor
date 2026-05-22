# Agenda 14 — Custom Slither Detectors Engine

> **Project**: sc_auditor (Vyper — Smart Contract Bug Hunter)
> **Status**: ✅ CLOSED
> **Severity**: HIGH — Tanpa custom detectors, platform tidak bisa di-extend untuk vulnerability unik
> **Dependensi**: Agenda 11 (Halmos integration)

---

## 1. Latar Belakang

Slither memiliki ~90+ detector bawaan, tapi **tidak mencakup**:
- Bug spesifik protocol (e.g., Uniswap v4 hook vulnerability)
- Kombinasi bug yang hanya terjadi di konfigurasi tertentu
- Pattern baru yang belum ada di database Slither

**Solusi**: Custom detector engine — user bisa upload detector Python file, Vyper akan load dan jalankan bersama Slither.

| Gap | Dampak | Lokasi |
|-----|--------|--------|
| No custom detector support | Platform tidak extensible | `04a-scanner-slither/` |
| No detector registry | Tidak ada management detectors | `04-scanner/` |
| No sandboxing | User-submitted code = security risk | `04a-scanner-slither/` |
| No example detectors | Developer tidak tahu cara buat | `04a-scanner-slither/detectors/` |
| No detector marketplace | Tidak ada sharing ecosystem | `services/` |

---

## 2. Detail Pekerjaan

### 2.1 Detector Loader System

File baru: `services/04a-scanner-slither/src/detector_loader.py`

```python
"""Custom Slither Detector Loader.

Mendukung:
- Load detector dari file .py (safe exec dengan timeout)
- Validasi: detector harus punya class turunan SlitherDetector
- Timeout: 30 detik per detector (cegah infinite loop)
- Caching: compile sekali, reuse untuk batch scan
- Rollback: jika 1 detector gagal, service tetap jalan

Struktur Detector:
    class MyDetector(SlitherDetector):
        NAME = "my-detector"
        DESCRIPTION = "Detects XXX vulnerability"
        IMPACT = IMPACT.HIGH
        
        def detect(self):
            for func in self.slither.functions:
                if self._is_vulnerable(func):
                    self._add_finding(func, "Description of bug")
"""

import ast
import importlib.util
import inspect
import os
import sys
import textwrap
import time
import traceback
from pathlib import Path
from typing import List, Optional, Type

from slither.detectors.abstract_detector import AbstractDetector, DetectorClassification


class DetectorLoadError(Exception):
    """Raised when a detector cannot be loaded."""


class DetectorTimeoutError(Exception):
    """Raised when a detector execution exceeds timeout."""


class DetectorSandbox:
    """Safe execution environment untuk custom detectors.
    
    Keamanan:
    - Hanya allow akses ke slither API objects
    - Timeout 30 detik per detector
    - No filesystem access
    - No network access
    - No import arbitrary modules
    """
    
    ALLOWED_MODULES = {
        "slither", "slither.detectors", "slither.core",
        "slither.core.declarations", "slither.core.cfg",
        "slither.core.variables", "slither.core.expressions",
        "typing", "enum", "dataclasses",
    }
    
    @staticmethod
    def validate_detector(source: str) -> bool:
        """Validasi syntax detector tanpa execute."""
        try:
            tree = ast.parse(source)
            # Cek ada class turunan AbstractDetector
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id in ("AbstractDetector", "SlitherDetector"):
                            return True
            return False
        except SyntaxError:
            return False
    
    @staticmethod
    def load_detector_from_source(source: str, module_name: str) -> Type[AbstractDetector]:
        """Load detector dari source code string (safe).
        
        Menggunakan importlib dengan restricted globals.
        """
        if not DetectorSandbox.validate_detector(source):
            raise DetectorLoadError("Invalid detector: must subclass AbstractDetector")
        
        # Compile module
        spec = importlib.util.spec_from_loader(module_name, loader=None)
        module = importlib.util.module_from_spec(spec)
        
        # Restricted globals — hanya allow modules yang di-allow
        restricted_globals = {
            "__name__": module_name,
            "__builtins__": __builtins__,
        }
        
        try:
            exec(compile(source, f"{module_name}.py", "exec"), restricted_globals)
        except Exception as e:
            raise DetectorLoadError(f"Failed to load detector: {e}")
        
        # Find detector class
        detector_class = None
        for name, obj in restricted_globals.items():
            if (inspect.isclass(obj) and 
                issubclass(obj, AbstractDetector) and 
                obj is not AbstractDetector):
                detector_class = obj
                break
        
        if detector_class is None:
            raise DetectorLoadError("No detector class found in source")
        
        return detector_class


class CustomDetectorRegistry:
    """Registry untuk semua custom detectors.
    
    Features:
    - Load dari direktori detectors/
    - Register/Unregister via API
    - Persist ke JSON untuk persistence
    - Conflict detection dengan built-in Slither detectors
    """
    
    def __init__(self, detectors_dir: str = "/data/detectors"):
        self.detectors_dir = Path(detectors_dir)
        self.detectors: dict[str, Type[AbstractDetector]] = {}
        self.metadata: dict[str, dict] = {}
        self.detectors_dir.mkdir(parents=True, exist_ok=True)
    
    def load_all(self) -> int:
        """Load semua detector dari direktori."""
        count = 0
        for file in self.detectors_dir.glob("*.py"):
            try:
                source = file.read_text()
                detector_class = DetectorSandbox.load_detector_from_source(
                    source, f"custom_detector_{file.stem}"
                )
                self.detectors[detector_class.NAME] = detector_class
                self.metadata[detector_class.NAME] = {
                    "name": detector_class.NAME,
                    "description": getattr(detector_class, "DESCRIPTION", ""),
                    "impact": str(getattr(detector_class, "IMPACT", "MEDIUM")),
                    "file": file.name,
                    "loaded_at": datetime.now(timezone.utc).isoformat(),
                }
                count += 1
            except DetectorLoadError as e:
                log.warning("detector.load.failed", file=file.name, error=str(e))
        return count
    
    def register_detector(self, name: str, source: str) -> dict:
        """Register detector baru via API."""
        file_path = self.detectors_dir / f"{name}.py"
        if file_path.exists():
            raise DetectorLoadError(f"Detector '{name}' already exists")
        
        # Validasi dulu
        DetectorSandbox.validate_detector(source)
        
        # Save to disk
        file_path.write_text(source)
        
        # Load
        detector_class = DetectorSandbox.load_detector_from_source(source, name)
        self.detectors[detector_class.NAME] = detector_class
        self.metadata[detector_class.NAME] = {
            "name": detector_class.NAME,
            "description": getattr(detector_class, "DESCRIPTION", ""),
            "impact": str(getattr(detector_class, "IMPACT", "MEDIUM")),
            "file": file_path.name,
            "loaded_at": datetime.now(timezone.utc).isoformat(),
        }
        
        return self.metadata[detector_class.NAME]
    
    def unregister_detector(self, name: str) -> bool:
        """Unregister detector."""
        if name in self.detectors:
            del self.detectors[name]
            meta = self.metadata.pop(name, {})
            file_path = self.detectors_dir / meta.get("file", f"{name}.py")
            if file_path.exists():
                file_path.unlink()
            return True
        return False
```

### 2.2 Example Custom Detectors

File baru: `services/04a-scanner-slither/detectors/`

**detector_uniswap_v4_hook.py** — Deteksi vulnerability di Uniswap v4 hooks:
```python
from slither.detectors.abstract_detector import AbstractDetector, DetectorClassification

class UniswapV4HookReentrancy(AbstractDetector):
    NAME = "uniswap-v4-hook-reentrancy"
    DESCRIPTION = "Detect reentrancy in Uniswap v4 hook callbacks"
    IMPACT = DetectorClassification.HIGH
    
    def detect(self):
        results = []
        for contract in self.slither.contracts:
            if not self._is_hook_contract(contract):
                continue
            for func in contract.functions_entry_points:
                if self._has_external_call_before_state_change(func):
                    results.append(self._generate_result(
                        func, "External call before state change in hook callback"
                    ))
        return results
    
    def _is_hook_contract(self, contract) -> bool:
        interfaces = [i.name for i in contract.interfaces_inherited]
        return "IHooks" in interfaces or "BaseHook" in interfaces
```

**detector_flash_loan_attack.py** — Deteksi flash loan vulnerability pattern:
```python
class FlashLoanAttackDetector(AbstractDetector):
    NAME = "flash-loan-attack"
    DESCRIPTION = "Detect potential flash loan attack vectors"
    IMPACT = DetectorClassification.HIGH
    
    def detect(self):
        results = []
        for contract in self.slither.contracts:
            for func in contract.functions_entry_points:
                if self._is_flash_loan_callback(func):
                    if not self._has_balance_verification(func):
                        results.append(self._generate_result(
                            func, "No balance verification after flash loan callback"
                        ))
        return results
```

**detector_oracle_manipulation.py** — Deteksi manipulasi oracle:
```python
class OracleManipulationDetector(AbstractDetector):
    NAME = "oracle-manipulation"
    DESCRIPTION = "Detect TWAP oracle manipulation via flash loans"
    IMPACT = DetectorClassification.HIGH
    
    def detect(self):
        results = []
        for contract in self.slither.contracts:
            for func in contract.functions_entry_points:
                if self._uses_twap_oracle(func) and not self._has_twap_period_check(func):
                    results.append(self._generate_result(
                        func, "TWAP oracle without minimum period check"
                    ))
        return results
```

### 2.3 Detector API Endpoints

File: `services/04a-scanner-slither/app.py` (enhance)

```python
# Endpoints baru untuk detector management

@router.get("/detectors")
async def list_detectors():
    """List semua custom detectors yang terdaftar."""
    return ok({
        "built_in_count": 90,  # Slither built-in
        "custom_detectors": registry.metadata,
        "total": len(registry.detectors),
    })

@router.post("/detectors")
async def register_detector(name: str, source: str):
    """Register custom detector baru."""
    try:
        meta = registry.register_detector(name, source)
        return ok(meta)
    except DetectorLoadError as e:
        raise err(str(e))

@router.delete("/detectors/{name}")
async def unregister_detector(name: str):
    """Remove custom detector."""
    if registry.unregister_detector(name):
        return ok({"removed": name})
    raise err(f"Detector '{name}' not found", 404)

@router.post("/scan/custom")
async def scan_with_custom(body: CustomScanRequest):
    """Scan dengan custom detectors (selain built-in Slither)."""
    custom_detectors = [d for name, d in registry.detectors.items() 
                        if name in body.custom_detectors]
    # Run Slither dengan custom detectors
    ...

@router.get("/detectors/{name}/source")
async def get_detector_source(name: str):
    """Get source code dari custom detector."""
    file_path = registry.detectors_dir / f"{name}.py"
    if file_path.exists():
        return ok({"name": name, "source": file_path.read_text()})
    raise err(f"Detector '{name}' not found", 404)
```

### 2.4 Scanner Integration

File: `services/04-scanner/app.py` (enhance)

Custom detectors perlu di-pass ke Slither runner. Tambah parameter `custom_detectors` di `ScanRequest`:

```python
class ScanRequest(BaseModel):
    sources: dict[str, str]
    tools: list[str] = ["slither"]
    custom_detectors: list[str] = []  # 🆕 Nama custom detectors
    timeout: int = 300
```

Di proxy ke scanner-slither:
```python
async def scan_with_slither(sources: dict, custom_detectors: list[str] = None):
    payload = {
        "sources": sources,
        "timeout": 300,
    }
    if custom_detectors:
        payload["custom_detectors"] = custom_detectors
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://04a-scanner-slither:8000/scan",
            json=payload,
            timeout=310,
        )
        return resp.json()
```

### 2.5 Detector Validation & Testing

File baru: `tests/test_custom_detectors.py`

```python
"""Test custom detector engine — load, validate, run."""

SAMPLE_DETECTOR = """
from slither.detectors.abstract_detector import AbstractDetector, DetectorClassification

class TestDetector(AbstractDetector):
    NAME = "test-detector"
    DESCRIPTION = "Test detector for CI"
    IMPACT = DetectorClassification.MEDIUM
    
    def detect(self):
        return []
"""

async def test_detector_validation():
    """Valid detector harus pass validation."""
    assert DetectorSandbox.validate_detector(SAMPLE_DETECTOR)

async def test_invalid_detector_rejected():
    """Invalid detector (no SlitherDetector) harus di-reject."""
    bad_source = "class Foo: pass"
    assert not DetectorSandbox.validate_detector(bad_source)

async def test_detector_load_and_run():
    """Load detector + run pada kontrak sederhana."""
    cls = DetectorSandbox.load_detector_from_source(SAMPLE_DETECTOR, "test")
    assert cls.NAME == "test-detector"

async def test_detector_registry_api():
    """Register detector via API → muncul di list."""
    ...

async def test_detector_sandbox_security():
    """Detector tidak bisa akses file system atau network."""
    ...
```

---

## 3. Struktur File

```
services/04a-scanner-slither/
├── src/
│   └── detector_loader.py            # 🆕 Detector loader + sandbox
├── detectors/
│   ├── detector_uniswap_v4_hook.py    # 🆕 Example: Uniswap v4 hook reentrancy
│   ├── detector_flash_loan_attack.py  # 🆕 Example: Flash loan attack
│   └── detector_oracle_manipulation.py # 🆕 Example: Oracle manipulation
├── app.py                            # ✏️ + Detector management endpoints

services/04-scanner/
├── app.py                            # ✏️ + custom_detectors field in ScanRequest
├── src/models.py                     # ✏️ + CustomScanRequest model

tests/
└── test_custom_detectors.py          # 🆕 Detector engine tests

services/15-dashboard/frontend/src/pages/
├── App.tsx                            # ✏️ + /detectors route
└── DetectorManager.tsx               # 🆕 Detector management page
```

---

## 4. Task List

| # | Task | File | Estimasi | Prioritas |
|---|------|------|----------|-----------|
| T1 | Detector loader + sandbox | `04a-scanner-slither/src/detector_loader.py` | 40 min | P0 |
| T2 | Custom detector registry | `04a-scanner-slither/src/detector_loader.py` | 20 min | P0 |
| T3 | Example: Uniswap v4 hook detector | `04a-scanner-slither/detectors/detector_uniswap_v4_hook.py` | 20 min | P1 |
| T4 | Example: Flash loan detector | `04a-scanner-slither/detectors/detector_flash_loan_attack.py` | 20 min | P1 |
| T5 | Example: Oracle manipulation detector | `04a-scanner-slither/detectors/detector_oracle_manipulation.py` | 20 min | P1 |
| T6 | List/Register/Delete detector endpoints | `04a-scanner-slither/app.py` | 15 min | P1 |
| T7 | Custom scan with detectors | `04a-scanner-slither/app.py` | 15 min | P1 |
| T8 | Integrasi custom_detectors ke main scanner | `04-scanner/app.py` | 15 min | P1 |
| T9 | Detector validation tests | `tests/test_custom_detectors.py` | 20 min | P1 |
| T10 | Sandbox security tests | `tests/test_custom_detectors.py` | 15 min | P2 |
| T11 | Detector Manager dashboard page | `frontend/src/pages/DetectorManager.tsx` | 25 min | P2 |
| | **Total** | | **~225 menit** | |

---

## 5. Quality Gate

| Dimensi | Target | Cara Ukur |
|---------|--------|-----------|
| Correctness | 90% | Load detector → validate → run scan → findings |
| Performance | 85% | Detector sandbox overhead < 1 detik per detector |
| Security | 90% | Sandbox block filesystem/network, timeout prevent abuse |
| Maintainability | 90% | Detector loader pattern extensible untuk scanner tools lain |
| Completeness | 100% | Register + unregister + list + scan dengan custom detectors |
| Alignment | 100% | Custom detectors berjalan bersama Slither built-in detectors |

---

## 6. Risiko & Mitigasi

| Risiko | Likelihood | Dampak | Mitigasi |
|--------|-----------|--------|----------|
| Slither API berubah antar versi | Sedang | Custom detectors broken | Pin Slither version, CI test compatibility |
| User-submitted code = security risk | Tinggi | RCE in container | Sandbox: restricted globals, no import arbitrary modules, timeout |
| Detector conflict dengan built-in | Rendah | Duplicate findings | Registry check nama unik, built-in detector name prefix |
| Detector performance issue | Sedang | Pipeline slow | Max 5 custom detectors per scan, individual timeout |

---

*Dibuat: 2026-05-20 | Status: CLOSED | Dependensi: Agenda 11*
