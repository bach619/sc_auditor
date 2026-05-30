# Aturan Implementasi Agenda — WAJIB BACA

> ** Berlaku untuk semua agent** (lore-master, vibe-coder, ui-god, backend-architect, dll).
> Setiap agent WAJIB membaca file ini SEBELUM mengerjakan task apa pun di direktori `daily_agenda/`.

---

## 1. Siklus Implementasi Agenda

Setiap agenda WAJIB melalui 4 fase berurutan. Tidak boleh ada fase yang dilewati.

```
┌─────────────────────────────────────────────────────────┐
│                    SIKLUS IMPLEMENTASI                    │
│                                                          │
│  FASE 1: BRAINSTORMING                                   │
│  ├── Pahami scope, dependensi, risiko                    │
│  ├── Identifikasi file mana saja yg kena dampak          │
│  ├── Tentukan approach (parallel/sequential/hybrid)      │
│  └── Output: pemahaman bersama user (bukan dokumen)      │
│                                                          │
│         ▼                                                │
│                                                          │
│  FASE 2: PLANNING                                        │
│  ├── Bikin rencana implementasi detail                   │
│  ├── Task list dengan estimasi                           │
│  ├── Urutan eksekusi (dependensi antar task)             │
│  ├── File apa yg dibuat/diubah/dihapus                   │
│  └── Output: rencana (bisa di file terpisah atau chat)   │
│                                                          │
│         ▼                                                │
│                                                          │
│  FASE 3: IMPLEMENTASI (HAND-OVER)                        │
│  ├── Auto-handoff ke @vibe-coder dengan kontrak penuh    │
│  ├── @vibe-coder eksekusi pipeline 5-stage               │
│  │   (Spec → Code → Test → Deploy)                       │
│  ├── @code-reviewer quality gate tiap stage              │
│  └── Output: kode berfungsi, test passing                │
│                                                          │
│         ▼                                                │
│                                                          │
│  FASE 4: CLOSED (100%)                                   │
│  ├── Verifikasi semua task selesai 100%                  │
│  ├── Update status file: 🔴 OPEN → ✅ CLOSED            │
│  ├── Update README.md index                              │
│  ├── Catat di activity-log.md                            │
│  └── Ekstrak pelajaran ke lessons-learned.md             │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Aturan Detail per Fase

### Fase 1: Brainstorming

- **PIC**: lore-master
- **WAJIB** dilakukan bersama user — tanya, konfirmasi, klarifikasi
- Jangan asumsikan approach — user tahu persis yang diinginkan
- Identifikasi: scope, dependensi agenda lain, file affected, risk
- **Tidak boleh** langsung lompat ke implementasi

### Fase 2: Planning

- **PIC**: lore-master
- Buat task list dengan file paths yang jelas
- Tentukan prioritas & urutan eksekusi
- Validasi plan ke user sebelum eksekusi
- **Output minimal**: daftar task + file affected + estimasi

### Fase 3: Implementasi (Hand-over ke Vibe-Coder)

- **PIC**: lore-master → @vibe-coder (auto-handoff)
- Lore-master membuat handoff contract lengkap (Section 13 lore-master)
- **WAJIB** menggunakan @vibe-coder untuk eksekusi — bukan lore-master langsung
- @vibe-coder jalankan pipeline 5-stage (Intent → Spec → Code → Test → Deploy)
- @code-reviewer melakukan quality gate setiap stage
- Jika gagal → lore-master介入, revisi planning, re-handoff

### Fase 4: Closed

- **PIC**: lore-master
- **HANYA** ditutup jika 100% berhasil — tidak ada "setengah jadi"
- Jika user tanya "apakah sudah 100%?" → jawab tegas "SUDAH 100%"
- Update: file status (OPEN → CLOSED), README.md, activity-log.md
- Jika ada yg belum selesai → jangan label closed — selesaikan dulu

---

## 3. Larangan (Anti-Patterns)

| # | Larangan | Kenapa |
|---|----------|--------|
| 1 | **Jangan langsung implementasi tanpa brainstorming** | Lompat ke kode = risk salah arah, user tidak konfirmasi |
| 2 | **Jangan lore-master yang implementasi langsung** | lore-master = strategi, vibe-coder = eksekusi. Hand-off wajib |
| 3 | **Jangan label closed sebelum 100%** | Menyesatkan, user kira selesai padahal belum |
| 4 | **Jangan skip planning** | Planning = contract dengan user, tanpanya tidak ada acuan sukses |
| 5 | **Jangan ubah status tanpa update README** | Index harus sinkron dengan status aktual |
| 6 | **Jangan lupa log ke SYSTEM_LOG.md** | Setiap perubahan tanpa log = hilang jejak. Log WAJIB sebelum close fase |

---

## 4.5 System Log — Catat Setiap Perubahan

> **WAJIB** — setiap agent WAJIB mencatat setiap write/modify/delete ke `SYSTEM_LOG.md`.

Setiap kali agent melakukan perubahan file (CREATE, MODIFY, DELETE, REFACTOR, FIX, CONFIG, TEST, DOCS), **WAJIB** mencatatnya di `SYSTEM_LOG.md`.

### Cara Mencatat

**Opsi A: Gunakan script helper (recommended)**
```bash
python scripts/log_change.py --type CREATE --file "path/file.py" --desc "Menambahkan fitur X" --agent lore-master
python scripts/log_change.py --type MODIFY --file "path/file.py" --desc "Refactor fungsi Y" --agent vibe-coder --tag "agenda-14"
python scripts/log_change.py --type DELETE --file "path/old.md" --desc "Hapus file usang"
```

**Opsi B: Edit langsung `SYSTEM_LOG.md`**
Tambahkan baris baru di bagian atas (di bawah `## YYYY-MM-DD`):
```
### `YYYY-MM-DD HH:MM | [TYPE] | File: path | Agent: agent | Deskripsi`
```

### Aturan Logging

| # | Aturan | Konsekuensi Jika Dilanggar |
|---|--------|----------------------------|
| 1 | **Setiap CREATE file → WAJIB log** | Hilang track asal-usul file |
| 2 | **Setiap MODIFY file → WAJIB log** | Tidak ada history perubahan |
| 3 | **Setiap DELETE file → WAJIB log** | File hilang tanpa jejak |
| 4 | **REFACTOR besar → WAJIB log** | Tidak terlihat scope perubahan |
| 5 | **CONFIG change → WAJIB log** | Konfigurasi berubah silent |
| 6 | **Gunakan `--tag` untuk grouping** (misal `--tag "agenda-14"`) | Memudahkan filter &追踪 |
| 7 | **Log di akhir sesi** — kumpulkan semua perubahan, lalu log batch | Efisien, tidak ganggu flow |
| 8 | **Jangan log TEST entry** untuk test script itu sendiri | Hanya log perubahan real |
| 9 | **Deskripsi dalam Bahasa Indonesia** atau English — konsisten | Memudahkan pembacaan |

### Format Detail

```
### `YYYY-MM-DD HH:MM | [TYPE] | File: path | Agent: agent | Deskripsi`
```

| Field | Contoh | Keterangan |
|-------|--------|------------|
| `HH:MM` | `14:30` | Waktu perubahan (24h) |
| `TYPE` | `CREATE` | Salah satu dari 9 tipe |
| `File` | `services/04-scanner/app.py` | Path relative ke root repo |
| `Agent` | `vibe-coder` | Nama agent yang melakukan perubahan |
| `Tag` | `[agenda-14]` | (Opsional) — di awal deskripsi |
| `Deskripsi` | `Tambah endpoint /scan/custom` | Deskripsi singkat & jelas |

### Valid Tipe

| TYPE | Digunakan Untuk |
|------|----------------|
| `CREATE` | File baru |
| `MODIFY` | Edit file existing |
| `DELETE` | Hapus file |
| `REFACTOR` | Restruktur kode besar (rename, move, split) |
| `FIX` | Bug fix |
| `DOCS` | Dokumentasi (README, docs/, komentar) |
| `CONFIG` | Config change (docker, CI, opencode.json) |
| `TEST` | Test files |
| `META` | System log infrastructure itu sendiri |

---

## 5. Format Penamaan File

| Status | Format |
|--------|--------|
| OPEN | `{nomor}_{nama}_{(open)}.md` atau `{nomor}_{nama}_{(open)}.md` |
| CLOSED | `{nomor}_{nama}_{(closed)}.md` |

**Aturan**:
- Saat agenda selesai → rename file dari `(open)` → `(closed)`
- Update header status di dalam file: `🔴 OPEN` → `✅ CLOSED`
- Update README.md index

---

## 5. Quality Gate (Wajib Sebelum Closed)

Setiap agenda WAJIB di-check terhadap 6 dimensi sebelum di-close:

| Dimensi | Target Minimal |
|---------|---------------|
| Correctness | 90% |
| Performance | 85% |
| Security | 85% |
| Maintainability | 85% |
| Completeness | 100% |
| Alignment | 100% |

Jika ada dimensi di bawah target → harus diperbaiki dulu.

---

## 6. Integrasi dengan Agent Lain

| Fase | Agent | Peran |
|------|-------|-------|
| Brainstorming | lore-master | Diskusi dengan user, pahami scope |
| Planning | lore-master | Buat rencana detail |
| Implementasi | vibe-coder | Eksekusi pipeline 5-stage |
| Quality Gate | code-reviewer | Evaluasi 6 dimensi |
| Closed | lore-master | Verifikasi, update status, logging |
| DevOps/Infra | devops-lead | Jika agenda menyentuh CI/CD, Docker, deployment |

---

## 7. Contoh Flow yang Benar

```
User: "Kerjakan agenda 10"
  │
  ▼
[lore-master] Brainstorming: "Agenda 10 itu observability & memory.
  Scope-nya apa? Dependensi ke 09 sudah clear?"
  │ User: "Ya, scope-nya Prometheus + Grafana + agent memory..."
  │
  ▼
[lore-master] Planning: "Ini task list-nya: T1 setup Prometheus,
  T2 integrasi Grafana, T3 agent memory endpoint..."
  │ User: "Setuju, eksekusi."
  │
  ▼
[lore-master] 🔗 AUTO-HANDOFF ke @vibe-coder dengan kontrak penuh
  │
  ▼
[vibe-coder] Pipeline: Spec → Code → Test → Deploy
  │ @code-reviewer quality gate tiap stage
  │
  ▼
[lore-master] Verifikasi 100% → Label ✅ CLOSED
  │ Update README, rename file, log aktivitas
  │
  ▼
  Selesai ✅
```

---

*Dibuat: 2026-05-20 | Berlaku untuk semua agent di workspace sc_auditor*
