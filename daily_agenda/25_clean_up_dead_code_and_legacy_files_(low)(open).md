# Clean up dead code and legacy file patterns [low][open]

**Labels:** `low` + `open`

## Deskripsi

Beberapa area kode mati (dead code) dan file legacy yang perlu dibersihkan:

### 1. `daily_agenda/` — File closed/cancelled yang tidak relevan lagi
Beberapa file agenda sudah berstatus `(closed)` atau `(cancelled)` tetapi masih ada di direktori dan bisa membingungkan:
- `09_auth_security_hardening_(cancelled-no-auth-needed).md`
- `09_security_hardening_(closed).md`
- `12_autonomous_agent_intelligence_(critical)(closed).md`
- `07_ci_cd_infrastructure_hardening_(closed).md`
- `08_comprehensive_test_suite_(closed).md`
- dll.

### 2. `ARCHITECTURE.md` — Dokumentasi usang
File `ARCHITECTURE.md` berisi desain lama (gRPC/protobuf) yang sudah tidak relevan dengan arsitektur saat ini (FastAPI REST). Dapat menyesatkan developer baru.

### 3. Test fixtures yang tidak terpakai
Beberapa file di `tests/fixtures/` mungkin sudah tidak sesuai dengan model terbaru.

### 4. File Windows-specific scripts
`rename_services.ps1`, `git_push.ps1`, `test_e2e.ps1`, `install-cli.ps1` — utility scripts yang mungkin sudah tidak relevan.

**Lokasi:**
- `daily_agenda/*(closed)*.md` dan `daily_agenda/*(cancelled)*.md`
- `ARCHITECTURE.md`
- `rename_services.ps1`, `git_push.ps1`, `test_e2e.ps1`
- `scripts/install-cli.ps1`

## Langkah Implementasi

- [ ] **Agenda files:**
  - [ ] Pindahkan file closed/cancelled ke subdirektori `daily_agenda/archived/`
  - [ ] Update `daily_agenda/Rules.md` jika ada referensi ke file yang dipindahkan
- [ ] **ARCHITECTURE.md:**
  - [ ] Tambahkan banner "OUTDATED — refer to VYPER.md instead" di bagian atas file
  - [ ] Atau pindahkan ke `docs/archived/ARCHITECTURE_OLD.md`
- [ ] **Scripts:**
  - [ ] Review `rename_services.ps1`, `git_push.ps1`, `test_e2e.ps1` — apakah masih diperlukan?
  - [ ] Jika tidak, pindahkan ke `scripts/archived/`
- [ ] Jalankan test suite untuk memastikan tidak ada yang broken setelah cleanup

## Kriteria Selesai

- [ ] Semua file agenda closed/cancelled dipindahkan ke `daily_agenda/archived/`
- [ ] `ARCHITECTURE.md` sudah diberi label outdated atau dipindahkan
- [ ] Script yang tidak terpakai sudah diarsipkan
- [ ] Semua test masih lulus setelah cleanup

## Catatan Tambahan

Jangan hapus permanen file-file ini — cukup pindahkan ke subdirektori `archived/` untuk referensi historis. Keputusan untuk menghapus permanen bisa diambil nanti setelah masa observasi.

File-file yang mungkin perlu diarsipkan:
- `daily_agenda/*(closed).md` — sudah selesai, tidak perlu aktif
- `daily_agenda/*(cancelled)*.md` — dibatalkan, tidak relevan
- `rename_services.ps1` — kemungkinan script satu kali untuk renaming service
- `ARCHITECTURE.md` — desain lama yang sudah digantikan oleh `VYPER.md`
