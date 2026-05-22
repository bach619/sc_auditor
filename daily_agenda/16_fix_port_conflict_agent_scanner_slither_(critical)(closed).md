# Fix port 8014 conflict between agent and scanner_slither [critical][open]

**Labels:** `critical` + `closed`

## Deskripsi

Dalam file `tests/conftest.py`, terdapat **port conflict** pada port `8014` yang digunakan oleh dua service berbeda secara bersamaan:

- `scanner_slither` (baris 28): `"scanner_slither": "http://localhost:8014"`
- `agent` (baris 41): `"agent": "http://localhost:8014"`

Ketika kedua service berjalan bersamaan (misalnya dalam integration test atau pipeline E2E), akan terjadi benturan port. Salah satu service tidak dapat bind ke port tersebut, menyebabkan test gagal secara intermiten (flaky test).

**Lokasi:** `tests/conftest.py`, baris 28 dan 41

**Dampak:**
- Integration test yang melibatkan kedua service menjadi tidak reliable
- Pipeline E2E testing sering gagal secara acak
- Sulit menjalankan kedua service secara simultan untuk development lokal

## Langkah Implementasi

- [ ] Tentukan port baru yang unik untuk service `agent` (port kosong: 8019+)
- [ ] Periksa service `14-agent/app.py` untuk memastikan port yang di-expose konsisten
- [ ] Periksa `docker-compose.yml` untuk memastikan port mapping service `agent` tidak bentrok
- [ ] Update `tests/conftest.py` baris 41 dengan port baru yang unik
- [ ] Update environment variable defaults di service code jika ada yang hardcode port 8014
- [ ] Update dokumentasi port mapping di `VYPER.md` atau `README.md`
- [ ] Jalankan ulang seluruh test suite untuk memastikan tidak ada efek samping

## Kriteria Selesai

- [ ] Port `agent` di `tests/conftest.py` tidak lagi bentrok dengan service manapun
- [ ] Tidak ada port duplikat di seluruh `_SERVICE_URLS` dictionary
- [ ] Semua test lulus tanpa error port conflict
- [ ] Port mapping di `docker-compose.yml` konsisten dengan perubahan

## Catatan Tambahan

Port yang saat ini sudah digunakan di `tests/conftest.py`:
- 8000: dashboard
- 8001: immunefi
- 8002: source
- 8003: scanner
- 8004: ai
- 8005: classifier
- 8006: exploit
- 8007: reporter
- 8008: notifier
- 8009: orchestrator
- 8010: webhook
- 8011: config
- 8012: upkeep
- 8013: scanner_mythril
- **8014: scanner_slither & agent ← BENTROK**
- 8015: scanner_echidna
- 8016: scanner_forge
- 8017: scanner_halmos
- 8018: submission

Port tersedia: 8019+. Disarankan port **8019** untuk service `agent`.
