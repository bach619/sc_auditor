# Resolve vyper_lib import ambiguity between file and package [critical][open]

**Labels:** `critical` + `closed`

## Deskripsi

Terdapat **dua entitas dengan nama yang sama** di root project:

1. **`vyper_lib.py`** — file Python tunggal (165 baris) berisi model lama sederhana, helper JSON, dan `ConfigClient`
2. **`vyper_lib/`** — package direktori (dengan `__init__.py`) berisi model Pydantic yang lebih lengkap, solc_manager, deps, slither_config

Ketika kode melakukan `import vyper_lib`, Python akan meresolve ke **file** (`vyper_lib.py`) terlebih dahulu, **bukan** ke package (`vyper_lib/`). Ini menyebabkan import ambiguity yang sulit dideteksi.

**Lokasi:**
- `/mnt/e/APP-TERMINAL/project/sc_auditor/vyper_lib.py` (root-level file)
- `/mnt/e/APP-TERMINAL/project/sc_auditor/vyper_lib/` (package direktori)

**Dampak:**
- Service yang menggunakan `from vyper_lib.models import ...` bisa gagal tergantung urutan sys.path
- `vyper_lib/__init__.py` mengekspor model berbeda dari `vyper_lib.py`
- Sulit di-debug karena error bergantung pada state interpreter

## Langkah Implementasi

- [ ] Analisis semua file yang meng-import `vyper_lib` (sebagai module) vs yang meng-import dari submodule spesifik
- [ ] **Opsi A (rekomendasi):** Hapus `vyper_lib.py` dan pindahkan fungsionalitasnya ke dalam package `vyper_lib/`
- [ ] Pindahkan `read_json`, `write_json`, `parse_standard_input_json` ke `vyper_lib/utils.py`
- [ ] Pindahkan `ConfigClient` ke `vyper_lib/config_client.py`
- [ ] Pindahkan `HealthResponse`, `ErrorResponse` (jika masih diperlukan) ke `vyper_lib/models.py`
- [ ] Update `vyper_lib/__init__.py` untuk mengekspor semua fungsi dan kelas yang dipindahkan
- [ ] Update semua import di service dan CLI yang merujuk ke `vyper_lib.py`
- [ ] Hapus file `vyper_lib.py` setelah migrasi selesai
- [ ] Update `setup.py` jika perlu menyesuaikan paths
- [ ] Jalankan seluruh test suite untuk memastikan tidak ada broken import

## Kriteria Selesai

- [ ] Tidak ada lagi file `vyper_lib.py` di root project
- [ ] Semua fungsi dari `vyper_lib.py` sudah dipindahkan ke dalam package `vyper_lib/`
- [ ] Semua service yang membutuhkan fungsi tersebut meng-import dari package
- [ ] `import vyper_lib` selalu meresolve ke package (bukan file)
- [ ] Semua test lulus

## Catatan Tambahan

Fungsi unik di `vyper_lib.py` yang belum ada di package:
- `read_json(path)` — helper baca JSON file
- `write_json(path, data)` — helper tulis JSON file atomically
- `ConfigClient` — HTTP client untuk Config Service
- `parse_standard_input_json(raw)` — parser Etherscan/Blockscout JSON input
- `HealthResponse`, `ErrorResponse` — model Pydantic (duplikasi dari `vyper_lib/models.py`)
