# Add technical documentation for microservices and API contracts [low][open]

**Labels:** `low` + `open`

## Deskripsi

Direktori `docs/` saat ini **hanya berisi satu file** (`INTELLIGENCE_API.md`). Dokumentasi teknis untuk 20 microservice hampir tidak ada. Beberapa dokumentasi yang ada tersebar di:

- `VYPER.md` — dokumentasi arsitektur utama (API specs, state machines)
- `README.md` — overview project dan daftar service
- `ARCHITECTURE.md` — desain lama (gRPC/protobuf, sudah tidak relevan)

**Yang kurang:**
- Dokumentasi API contract untuk setiap service (endpoints, request/response schemas)
- Dokumentasi setup development environment (cara menjalankan service secara individu)
- Dokumentasi contribution guidelines
- Dokumentasi environment variables yang diperlukan per service
- API reference yang dapat diakses tanpa membaca source code

**Lokasi:** `docs/`

**Dampak:**
- Developer baru butuh waktu lama untuk memahami arsitektur
- Sulit melakukan debugging tanpa dokumentasi API yang jelas
- Tidak ada panduan kontribusi → menghambat kolaborasi
- Environment variables tidak terdokumentasi dengan baik

## Langkah Implementasi

- [ ] Buat `docs/API_REFERENCE.md` — dokumentasi API untuk setiap service:
  - Endpoint list per service
  - Request/response schema (acu pada model di `vyper_lib/models.py`)
  - Contoh curl command
- [ ] Buat `docs/DEVELOPMENT.md` — panduan setup development:
  - Cara clone dan install dependencies
  - Cara menjalankan service individu vs via Docker Compose
  - Cara menjalankan test
  - Tips debugging
- [ ] Buat `docs/CONTRIBUTING.md` — panduan kontribusi:
  - Branch strategy
  - Code style (ruff conventions)
  - Pull request template
  - Test requirements
- [ ] Update `docs/INTELLIGENCE_API.md` jika perlu diselaraskan dengan implementasi terbaru
- [ ] Buat `docs/ENVIRONMENT.md` — dokumentasi semua environment variable yang digunakan:
  - `CONFIG_URL`, `LOG_LEVEL`, `MYTHRIL_URL`, `HALMOS_URL`, dll.
- [ ] Update `README.md` dengan link ke file-file docs baru

## Kriteria Selesai

- [ ] `docs/API_REFERENCE.md` mencakup setidaknya 5 service utama (config, scanner, ai, orchestrator, dashboard)
- [ ] `docs/DEVELOPMENT.md` memberikan instruksi yang cukup untuk developer baru mulai berkontribusi
- [ ] `docs/CONTRIBUTING.md` ada dan jelas
- [ ] `docs/ENVIRONMENT.md` mendokumentasikan semua env var yang digunakan
- [ ] `README.md` memiliki link ke file-file docs baru

## Catatan Tambahan

Referensi untuk dokumentasi API bisa diambil dari:
- `VYPER.md` — sudah memiliki API specs untuk setiap service (meski mungkin ada yang outdated)
- Source code setiap service — `app.py` memiliki endpoint FastAPI yang jelas
- `vyper_lib/models.py` — semua schema API terpusat di sini

Jangan lupa untuk menyertakan informasi tentang format response yang digunakan (standarisasi dari agenda 22 jika sudah dilakukan).
