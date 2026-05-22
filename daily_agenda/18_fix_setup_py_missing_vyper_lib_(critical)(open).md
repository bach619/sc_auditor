# Fix setup.py missing vyper_lib from find_packages [critical][open]

**Labels:** `critical` + `open`

## Deskripsi

File `setup.py` pada baris 20 menggunakan `find_packages()` dengan parameter `include` yang **tidak mencakup `vyper_lib`**:

```python
packages=find_packages(include=["cli", "cli.*", "services", "services.shared", "services.shared.*"]),
```

Akibatnya, ketika package diinstal via `pip install -e .`, package `vyper_lib/` **tidak akan terinstal**. Service-service yang meng-import dari `vyper_lib` akan gagal dengan `ModuleNotFoundError` saat dijalankan di luar Docker.

**Lokasi:** `setup.py`, baris 20

**Dampak:**
- `pip install -e .` tidak menginstal `vyper_lib` → runtime error
- Developer yang menjalankan service di luar Docker mendapatkan `ModuleNotFoundError`
- CLI tool (`vyper`) tidak dapat berfungsi penuh di lingkungan non-Docker

## Langkah Implementasi

- [ ] Tambahkan `"vyper_lib"` dan `"vyper_lib.*"` ke dalam daftar `include` di `find_packages()`
- [ ] Jalankan `pip install -e .` dan verifikasi instalasi dengan `python -c "import vyper_lib; print(vyper_lib.__version__)"`
- [ ] Jalankan test suite untuk memastikan semua import berfungsi

## Kriteria Selesai

- [ ] `find_packages()` di `setup.py` mencakup `vyper_lib` dan `vyper_lib.*`
- [ ] `pip install -e .` berhasil menginstal `vyper_lib`
- [ ] Semua service yang depend pada `vyper_lib` dapat berjalan di luar Docker
- [ ] Tidak ada `ModuleNotFoundError` terkait `vyper_lib`

## Catatan Tambahan

Baris setelah perbaikan:

```python
packages=find_packages(include=[
    "cli", "cli.*",
    "services", "services.shared", "services.shared.*",
    "vyper_lib", "vyper_lib.*",
]),
```

Ini adalah bug kritis karena memblokir instalasi package yang benar — tanpa fix ini, developer tidak bisa menggunakan `vyper` CLI dengan benar di lingkungan non-Docker.
