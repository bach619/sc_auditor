# Standardize API response format across all services [mid][open]

**Labels:** `mid` + `open`

## Deskripsi

Terdapat **inkonsistensi format API response** antar service. Dari dokumentasi test di `tests/test_api_format.py`:

### Type A — Flat HealthResponse
Beberapa service mengembalikan response flat tanpa envelope:
```json
{"status": "ok", "service": "config", "version": "0.1.0", "timestamp": "..."}
```
Service: `config`, `classifier`

### Type B — Wrapped ApiResponse
Service lain mengembalikan response dengan envelope `{data, meta}`:
```json
{"data": {...}, "meta": {"status": "ok", "timestamp": "..."}}
```
Service: `immunefi`, `orchestrator`, dan lainnya

**Lokasi:**
- `tests/test_api_format.py` — mendokumentasikan inkonsistensi dan memiliki test untuk kedua format
- `services/01-config/app.py` — kemungkinan menggunakan flat response
- `services/07-classifier/app.py` — kemungkinan menggunakan flat response

**Dampak:**
- Klien (CLI, dashboard) harus menangani dua format berbeda → kode kompleks
- Integrasi service baru harus memilih format mana yang diikuti
- Dokumentasi API menjadi tidak konsisten
- Menyulitkan pembuatan client library generik

## Langkah Implementasi

- [ ] Tentukan format standar yang akan digunakan untuk semua service
- [ ] **Rekomendasi:** Gunakan Type B (`{data, meta}` envelope) untuk semua endpoint, termasuk /health
- [ ] Update `01-config/app.py` untuk menggunakan `ApiResponse` dari `vyper_lib` pada endpoint /health
- [ ] Update `07-classifier/app.py` untuk konsistensi yang sama
- [ ] Update `tests/test_api_format.py` untuk hanya mengakui satu format (Type B)
- [ ] Update dokumentasi API contract di `VYPER.md` jika ada
- [ ] Jalankan test untuk memverifikasi semua service menggunakan format yang sama

## Kriteria Selesai

- [ ] Semua endpoint `/health` di semua service menggunakan format `{data, meta}` yang konsisten
- [ ] `TYPE_A_HEALTH_SERVICES` di test bisa dihapus karena tidak ada lagi yang menggunakan Type A
- [ ] Semua test API format lulus
- [ ] Dokumentasi API contract diperbarui

## Catatan Tambahan

Format standar yang direkomendasikan:

```python
# Success response
{"data": <payload>, "meta": {"status": "ok", "timestamp": "2026-05-20T..."}}

# Error response
{"data": None, "meta": {"status": "error", "error": "message", "timestamp": "..."}}

# Health response (also wrapped)
{"data": {"status": "ok", "service": "...", "version": "..."}, "meta": {"status": "ok", "timestamp": "..."}}
```

Model yang sudah ada di `vyper_lib/models.py`:
- `ApiResponse` — envelope `{data, meta}`
- `Meta` — metadata dengan status dan timestamp
- `HealthData` — data payload untuk health check
