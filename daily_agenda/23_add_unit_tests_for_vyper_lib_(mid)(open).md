# Add unit tests for vyper_lib shared library [mid][open]

**Labels:** `mid` + `open`

## Deskripsi

Package `vyper_lib/` saat ini **tidak memiliki unit test sama sekali**. Padahal package ini adalah shared library yang digunakan oleh banyak service dan berisi:

- `models.py` — 13+ Pydantic model yang menjadi kontrak data antar service
- `solc_manager.py` — Manajemen instalasi dan versi Solidity compiler
- `deps.py` — Dependency resolver untuk tools keamanan
- `slither_config.py` — Builder konfigurasi Slither
- `__init__.py` — Central re-export module

**Dampak:**
- Perubahan pada model tidak terverifikasi → bisa merusak service yang bergantung
- Tanpa test, tidak ada jaminan bahwa factory functions berfungsi dengan benar
- Risiko regresi tinggi ketika menambahkan field baru ke model
- Menyulitkan refactor atau migrasi model

## Langkah Implementasi

- [ ] Buat file `tests/unit/test_vyper_lib_models.py`:
  - Test instantiasi semua Pydantic model dengan data valid
  - Test validasi field (required fields, type constraints)
  - Test serialisasi/deserialisasi JSON
  - Test field defaults
- [ ] Buat file `tests/unit/test_vyper_lib_solc_manager.py`:
  - Test factory function `create_solc_manager()`
  - Test version parsing logic
- [ ] Buat file `tests/unit/test_vyper_lib_deps.py`:
  - Test dependency resolver mock
- [ ] Buat file `tests/unit/test_vyper_lib_slither_config.py`:
  - Test config builder untuk berbagai preset (strict, default, noisy)
- [ ] Tambahkan marker `pytest.mark.unit` untuk memisahkan dari integration test
- [ ] Jalankan test dan pastikan coverage minimal 80% untuk `vyper_lib/`

## Kriteria Selesai

- [ ] Ada minimal 4 file test untuk `vyper_lib/` (models, solc_manager, deps, slither_config)
- [ ] Test mencakup validasi input, serialisasi, dan factory functions
- [ ] Semua test lulus
- [ ] Coverage untuk package `vyper_lib/` minimal 80%
- [ ] Test dapat dijalankan tanpa Docker (hanya pytest)

## Catatan Tambahan

Contoh test untuk model:

```python
# tests/unit/test_vyper_lib_models.py
import pytest
from vyper_lib.models import Finding, ScanRequest, ApiResponse, Meta


class TestFinding:
    def test_minimal_instantiation(self):
        finding = Finding(tool="slither", title="Reentrancy")
        assert finding.tool == "slither"
        assert finding.severity == "informational"  # default

    def test_serialization_roundtrip(self):
        finding = Finding(tool="slither", title="Test", severity="high")
        data = finding.model_dump()
        restored = Finding(**data)
        assert restored == finding


class TestApiResponse:
    def test_default_meta(self):
        resp = ApiResponse(data={"key": "value"})
        assert resp.meta.status == "ok"
        assert resp.data == {"key": "value"}
```

Jalankan dengan: `python -m pytest tests/unit/ -v --cov=vyper_lib`
