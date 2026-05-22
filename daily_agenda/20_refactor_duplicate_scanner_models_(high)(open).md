# Refactor duplicate scanner models to use shared vyper_lib [high][open]

**Labels:** `high` + `open`

## Deskripsi

Terdapat **duplikasi model Pydantic** antara service scanner lama dan yang sudah di-split:

1. **`services/04-scanner/app.py`** (monolith scanner lama) — menggunakan model lokal dari `src/models.py`:
   - `ApiResponse`, `Finding`, `HealthData`, `InstallResult`, `Meta`, `ScanRequest`, `ScanResponse`, `ToolInfo`, `ToolResult`
   - Juga menggunakan `src/solc_manager.py`, `src/deps.py`, `src/slither_config.py` (lokal)

2. **`services/04a-scanner-slither/app.py`** (scanner split baru) — sudah menggunakan `vyper_lib.models` dan `vyper_lib.solc_manager`, `vyper_lib.deps`, `vyper_lib.slither_config`

**Lokasi:**
- `services/04-scanner/src/models.py` — model duplikat
- `services/04-scanner/src/solc_manager.py` — duplikat dari `vyper_lib/solc_manager.py`
- `services/04-scanner/src/deps.py` — duplikat dari `vyper_lib/deps.py`
- `services/04-scanner/src/slither_config.py` — duplikat dari `vyper_lib/slither_config.py`

**Dampak:**
- Setiap perubahan model harus diupdate di dua tempat (rentan inkonsistensi)
- Maintenance overhead lebih tinggi
- Kode sulit di-refactor karena model tidak terpusat

## Langkah Implementasi

- [ ] Analisis perbedaan antara model di `04-scanner/src/models.py` dan `vyper_lib/models.py`
- [ ] Jika ada field unik di model lokal, pindahkan ke `vyper_lib/models.py`
- [ ] Update `04-scanner/src/models.py` menjadi re-export dari `vyper_lib.models`
- [ ] Lakukan hal yang sama untuk `solc_manager.py`, `deps.py`, `slither_config.py`
- [ ] Update import di `04-scanner/app.py` untuk menggunakan `vyper_lib` langsung
- [ ] Hapus file `src/models.py`, `src/solc_manager.py`, `src/deps.py`, `src/slither_config.py` setelah migrasi
- [ ] Update test yang terkait dengan scanner lama
- [ ] Jalankan full test suite untuk verifikasi

## Kriteria Selesai

- [ ] `04-scanner/app.py` hanya meng-import model dari `vyper_lib` (tidak ada model lokal)
- [ ] Tidak ada file duplikat di `04-scanner/src/` yang sudah ada di `vyper_lib/`
- [ ] Semua test yang melibatkan scanner lulus
- [ ] Tidak ada perubahan behaviour dari endpoint scanner

## Catatan Tambahan

Service `04-scanner` masih diperlukan sebagai "gateway" yang mengoordinasikan multiple tools (Slither, Echidna, Forge, Mythril, Halmos). Refactor ini hanya menyatukan model, bukan menghapus service.
