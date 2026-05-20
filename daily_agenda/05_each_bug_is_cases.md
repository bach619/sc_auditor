# Each Bug Is Cases — Spesifikasi Case Management

> **Project**: sc_auditor (Vyper — Smart Contract Bug Hunter)
> **Dokumen ini**: Spesifikasi fitur Case Management System yang akan diimplementasikan di Frontend React + Backend FastAPI yang sudah ada.

---

## 1. Definisi

**Kasus** adalah representasi formal dari sebuah temuan bug oleh Scanner Tools. Setiap temuan scanner otomatis menjadi Case (OPEN). User menutup Case (CLOSED) setelah bounty diterima atau bug dianggap tidak valid.

| Atribut | Nilai |
|---------|-------|
| **Trigger** | Scanner Tools menemukan potensi bug |
| **Pembuka** | Agent (otomatis) |
| **Pelapor** | Private User (pengguna aplikasi) — *bukan Agent* |
| **Status** | `OPEN` atau `CLOSED` |
| **Penutup** | Private User |

---

## 2. Alur Case Lifecycle

### 2.1 Trigger: Scanner → Case OPEN

Scanner Tools mengeluarkan output → Agent membaca → Case langsung OPEN.

Tidak perlu:
- ❌ Verifikasi manual
- ❌ Proof-of-Concept (PoC) berhasil
- ❌ Konfirmasi dari siapa pun

Scanner Tools yang menjadi trigger:
| Scanner | Fungsi |
|---------|--------|
| **Slither** | Static analysis |
| **Mythril** | Symbolic execution |
| **Echidna** | Fuzzing / invariant testing |
| **Foundry** | forge test, fuzz, invariant |
| **Semgrep** | Custom pattern matching |
| **Aderyn** | Solidity static analyzer |
| **Manticore** | Symbolic execution |
| **Halmos** | Symbolic testing |

### 2.2 Status: Hanya 2

```
                   ┌──────────────┐
                   │              │
  Scanner menemukan│   OPEN 🟢    │──User close──▶  CLOSED 🔴
  bug              │              │
                   └──────────────┘

  TIDAK ADA status lain. Dari OPEN langsung ke CLOSED — atau tetap OPEN.
```

**OPEN 🟢** — Kasus aktif:
- Agent: analisis, klasifikasi severity, buat PoC, siapkan data teknis
- User: lihat di UI, download report, submit ke Immunefi

**CLOSED 🔴** — Kasus selesai:
- User tutup manual setelah bounty diterima (confirmed) atau tidak valid (false positive, duplicate)
- Agent: arsipkan data untuk learning
- User: catat bounty amount

### 2.3 Struktur Data

```yaml
CASE-001:
  status: OPEN
  project: "Project A"
  scanners:                        # Daftar scanner yang menemukan
    - name: "Slither"
      detector: "reentrancy"
      confidence: 0.8
    - name: "Mythril"
      detector: "reentrancy"
      confidence: 0.9
  confidence: 0.85                 # Rata-rata confidence dari semua scanner
  scanner_count: 2                 # Berapa scanner yang menemukan bug ini
  severity: "High"                 # Critical/High/Medium/Low/Info
  title: "Reentrancy di Vault.withdraw()"
  contract: "Vault.sol"
  function: "withdraw"
  line: 45
  description: "External call before state update"
  recommendation: "Gunakan Checks-Effects-Interactions pattern"
  proof_of_concept: ""             # Diisi Agent
  platform: "Immunefi"
  bounty_amount: null              # Diisi user saat close
  notes: ""
  created_at: "2026-05-20T10:00:00Z"
  closed_at: null
  closed_reason: null              # confirmed/rejected/duplicate/false_positive
```

### 2.4 Aturan Agent

1. **Auto-create**: Temuan scanner pertama → 1 Case (OPEN)
2. **Dedup + Confidence**: Scanner lain temukan bug SAMA → **bukan case baru**, tapi update case yang sudah ada → **confidence naik**
3. **No auto-close**: Hanya user yang CLOSE
4. **No auto-submit**: Agent **TIDAK** boleh submit ke platform manapun
5. **Context retention**: Agent simpan konteks per-case untuk bantu user jika diperlukan
6. **No ghost cases**: Case CLOSED tidak bisa di-reopen

### 2.5 Logika Dedup & Confidence

Dua temuan dari scanner berbeda dianggap **bug yang sama** jika memenuhi semua:
1. Contract yang sama (`Vault.sol`)
2. Function yang sama (`withdraw()`)
3. Vulnerability class yang sama (`reentrancy`)

**Pengaruh terhadap Confidence:**

| Kondisi | Confidence | Arti |
|---------|-----------|------|
| 1 scanner menemukan | 0.6 - 0.8 | Perlu verifikasi manual |
| 2 scanner menemukan | 0.8 - 0.9 | Kemungkinan besar valid |
| 3+ scanner menemukan | 0.9 - 1.0 | Sangat yakin ini bug |

> **Catatan**: Jika scanner berbeda menemukan di contract/function/vuln class yang berbeda → tetap jadi **Case terpisah**.

---

## 3. Skenario End-to-End

### 3.1 Audit Berhasil — Bounty Didapat

```
Step 1: User jalankan scanner tools
        ├─ slither . --detect reentrancy,access-control
        └─ mythril . --detect reentrancy

Step 2: Scanner output:
        ┌────────────────────────────────────────────┐
        │ Slither: [Reentrancy] Vault.withdraw()     │
        │ Slither: [Access Control] Token.mint()     │
        │ Mythril: [Reentrancy] Vault.withdraw()     │
        └────────────────────────────────────────────┘

Step 3: Agent buat CASE:
        ├─ CASE-001: Reentrancy di Vault.withdraw()
        │   Slither + Mythril → confidence: HIGH ✅
        │   (BUKAN 2 case terpisah — digabung)
        │
        └─ CASE-002: Access Control di Token.mint()
            Slither saja → confidence: MEDIUM

Step 4: Agent analisis masing-masing:
        ├─ CASE-001 (confidence HIGH — prioritas)
        └─ CASE-002

Step 5: User lihat di UI → buka /cases
        ├─ CASE-001 ⭐ High Confidence — prioritaskan submit
        └─ CASE-002 Medium Confidence

Step 6: Download report CASE-001 → submit MANUAL ke Immunefi

Step 7: Immunefi konfirmasi valid → bayar bounty

Step 8: User tutup CASE:
        ├─ CASE-001 → CLOSED (confirmed, bounty: $5,000)
        └─ CASE-002 → CLOSED (confirmed, bounty: $2,000)

Step 9: Case masuk halaman /archive
```

### 3.2 False Positive

```
Step 1: Slither deteksi "Unused Return" — Low
Step 2: Agent buat CASE-003: OPEN
Step 3: Agent analisis → return sengaja tidak dipakai (safe pattern)
Step 4: User lihat, setuju false positive
Step 5: User tutup CASE-003 → CLOSED (false_positive)
```

---

## 4. Implementasi: Yang Akan Dibangun

### 4.1 Backend (FastAPI) — Service 15-dashboard

File: `services/15-dashboard/app.py`

**Endpoint API baru:**

| Method | Endpoint | Fungsi |
|--------|----------|--------|
| `GET` | `/api/cases` | List semua case OPEN (filter, search, sort, pagination) |
| `GET` | `/api/cases/archive` | List semua case CLOSED |
| `GET` | `/api/cases/{id}` | Detail satu case |
| `POST` | `/api/cases` | Agent: create case baru |
| `PUT` | `/api/cases/{id}/close` | User: close case (body: reason, bounty) |
| `GET` | `/api/cases/{id}/report.md` | Download report Markdown |
| `GET` | `/api/cases/{id}/report.pdf` | Download report PDF |
| `GET` | `/api/cases/stats` | Statistik untuk dashboard |

### 4.2 Frontend (React) — Pages Baru

File: `services/15-dashboard/frontend/src/pages/`

| File | Route | Fungsi |
|------|-------|--------|
| `Cases.tsx` | `/cases` | Tabel daftar kasus OPEN |
| `CaseDetail.tsx` | `/cases/:id` | Detail kasus + tombol download & close |
| `Archive.tsx` | `/archive` | Tabel daftar kasus CLOSED |

**Yang perlu diupdate:**
- `App.tsx` — tambah route `/cases`, `/cases/:id`, `/archive`
- `Layout.tsx` — tambah navigasi sidebar ke Cases & Archive
- `lib/api.ts` — tambah fungsi API untuk cases

### 4.3 Storage Engine (Python Baru)

File baru: `services/15-dashboard/src/storage.py`

- Baca/tulis file YAML di `~/.sc_auditor/cases/`
- Generate report Markdown dari template
- Generate PDF (via weasyprint / pdfkit)
- Kelola folder learning/

### 4.4 Agent Integration

Di skill `smartcontract-auditor` (file `.opencode/skills/smartcontract-auditor/SKILL.md`):
- Trigger: scanner output → POST `/api/cases` (auto-create)
- Analisis: isi field `proof_of_concept`, `description`, `recommendation`
- Export: sediakan data untuk report template

---

## 5. Struktur Penyimpanan (File System)

**Lokasi**: `~/.sc_auditor/` — 100% lokal, tanpa database.

```
~/.sc_auditor/
│
├── cases/                          # Semua kasus (OPEN + CLOSED)
│   ├── CASE-001/
│   │   ├── meta.yaml               # Metadata case
│   │   ├── report.md               # Laporan Markdown
│   │   ├── report.pdf              # Laporan PDF
│   │   ├── poc/                    # PoC exploit files
│   │   │   └── exploit.sol
│   │   └── evidence/               # Screenshot, logs
│   ├── CASE-002/
│   └── ...
│
├── learning/                       # Memory learning
│   ├── patterns.yaml               # Pola vulnerability
│   ├── knowledge.json              # Pengetahuan terakumulasi
│   └── index.json                  # Index retrieval
│
├── config.yaml                     # Konfigurasi user
└── app.log
```

| Aspek | Detail |
|-------|--------|
| Backup | Cukup copy folder `~/.sc_auditor/` |
| Portable | Pindah ke PC lain dengan copy folder |
| Privasi | 100% lokal. Tidak ada data ke server |

---

## 6. Local Learning / Memory

Setiap case menjadi **bahan pembelajaran** aplikasi:

| Komponen | Fungsi |
|----------|--------|
| **Pattern Recognition** | Aplikasi belajar pola vulnerability dari kasus sebelumnya |
| **Knowledge Base** | Semua PoC, fix, recommendation jadi referensi |
| **Smarter Analysis** | Agent makin pintar karena punya memori kasus sebelumnya |

Cara kerja:
1. Setiap CASE → datanya masuk ke `learning/`
2. Agent bisa baca pattern dari kasus sebelumnya
3. Scanner temukan bug mirip → Agent bilang: *"Ini mirip CASE-012 (bounty $10,000)"*
4. User bisa cari "kasus mirip"

---

## 7. Ringkasan Peran

```
AGENT (Otomatis)                     USER (Private User)
─────────────────────                ─────────────────────
• Baca output scanner                • Buka UI aplikasi (localhost)
• Buat Case (OPEN)                   • Lihat daftar kasus di halaman /cases
• Analisis bug                       • Klik detail kasus
• Klasifikasi severity               • Download report (MD/PDF)
• Buat PoC exploit                   • Submit laporan ke Immunefi (manual)
• Generate report template           • Tutup case (CLOSED)
• Maintain konteks per-case          • Catat bounty amount
• Learning dari kasus lama           • Akses archive /archive

APLIKASI (Frontend + Backend)
─────────────────────
• /cases         → Tabel kasus OPEN
• /cases/:id     → Detail + download + close
• /archive       → Tabel kasus CLOSED
• /dashboard     → Statistik (bagian dari halaman Dashboard yang sudah ada)
• API            → CRUD cases, generate report, stats
```

---

## 8. Integrasi dengan Smartcontract-Auditor Skill

Flow ini akan diintegrasikan ke skill `smartcontract-auditor` sebagai tambahan **Case Management** yang mencakup:
- Trigger scanner → auto-create case via API
- Agent analysis → klasifikasi, PoC, data teknis
- Export data untuk report template
- Context retention per-case

---

*Dokumen ini menjadi dasar pengembangan Case Management System untuk aplikasi sc_auditor (Vyper).*
