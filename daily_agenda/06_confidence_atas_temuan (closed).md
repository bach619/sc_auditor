# 06 — Confidence atas Temuan ✅ CLOSED

> **Status**: ✅ CLOSED (confidence.py 286 baris + 7 test pass — Agenda 06 full spec implemented)
> **Closed**: 2026-06-04 | lore-master verified

> **Definisi**: Sistem penilaian keyakinan (Confidence) terhadap setiap temuan bug dalam Case Management. Confidence membantu User memprioritaskan case mana yang harus segera dilaporkan ke platform bug-bounty.

---

## 1. Faktor yang Mempengaruhi Confidence

### Faktor A: Jumlah Scanner

Semakin banyak scanner tools yang mendeteksi bug yang sama, semakin tinggi confidence-nya.

| Scanner Mendeteksi | Label |
|--------------------|-------|
| 1 scanner | `Medium` |
| 2 scanner | `High` |
| 3+ scanner | `Critical` |

### Faktor B: Ketersediaan PoC Exploit

**Siapa yang menentukan**: **Agent** — Agent membuat PoC, menjalankannya, dan melaporkan hasilnya.

**Ukuran berhasil**: Exploit berhasil mengeksekusi attack vector dan mengubah state kontrak sesuai ekspektasi (misal: balance berkurang, transfer berhasil ke address tidak sah, dll).

| Kondisi | Pengaruh |
|---------|----------|
| PoC berhasil dijalankan | ⬆️ Naik 1 level |
| PoC belum ada / gagal | Netral |

### Faktor C: Pattern dari Kasus Sebelumnya (Learning)

Berdasarkan data historis di `~/.sc_auditor/learning/patterns.yaml`.

| Weight | Pengaruh |
|--------|----------|
| 0 (pola baru) | Netral |
| 1 - 2 (pernah confirmed) | ⬆️ Naik 1 level |
| 3+ (banyak confirmed) | ⬆️ Naik 1 level (cap) |
| -1 (pernah false positive) | ⬇️ Turun 1 level |

> Weight adalah akumulasi dari riwayat case sebelumnya. Batas maksimal booster adalah **1 level**, tidak peduli berapa pun weight-nya.

### Faktor D: Kategori Vulnerability

Aturan umum (tidak perlu daftar panjang):

| Kategori | Efek |
|----------|------|
| **Security vulnerability** (reentrancy, access control, overflow, flash loan, dll) | Normal — tidak ada perubahan |
| **Informational / best practice** (unused return, floating pragma, naming convention, dll) | ⬇️ Turun ke `Low` |
| **Gas optimization** | ⬇️ Turun ke `Low` |

---

## 2. Label Confidence

Hanya ada 4 label — berbentuk tulisan, bukan numerik:

```
Low  →  Medium  →  High  →  Critical
```

**Critical adalah level tertinggi. Tidak ada level di atas Critical.**

### Penentuan Label

Setiap case dimulai dari **Medium** (default dari scanner).

Alur penentuan:

```
Scanner menemukan bug
        │
        ▼
  ┌─ Faktor A: Jumlah Scanner
  │  1 scanner    → Medium
  │  2 scanner    → High
  │  3+ scanner   → Critical (MAX)
  │
  ▼
  ┌─ Faktor B: PoC Exploit
  │  Ada PoC      → Naik 1 level (jika belum Critical)
  │  Tidak ada    → Tetap
  │
  ▼
  ┌─ Faktor C: Learning Pattern
  │  Pernah confirmed  → Naik 1 level (jika belum Critical)
  │  Pernah false pos  → Turun 1 level
  │  Baru              → Tetap
  │
  ▼
  ┌─ Faktor D: Kategori Vuln
  │  Informational / Gas Optimization → Low (FINAL)
  │  Security vulnerability           → Tetap
  │
  ▼
    LABEL FINAL
```

### Contoh Perhitungan

| Case | Scanner | PoC | Learning | Kategori | Hasil |
|------|---------|-----|----------|----------|-------|
| CASE-001 | 2 → **High** | Ada → **Critical** | Confirmed → cap **Critical** | Reentrancy → tetap | ✅ **Critical** |
| CASE-002 | 1 → **Medium** | Ada → **High** | Baru → **High** | Access Control → tetap | ✅ **High** |
| CASE-003 | 1 → **Medium** | Tidak → **Medium** | FP → **Low** | Unused Return → cap **Low** | ✅ **Low** |
| CASE-004 | 1 → **Medium** | Tidak → **Medium** | Baru → **Medium** | Gas Optimization → **Low** | ✅ **Low** |
| CASE-005 | 3 → **Critical** | Ada → cap **Critical** | Confirmed → cap **Critical** | Flash Loan → tetap | ✅ **Critical** |

---

## 3. Tampilan di UI

Semua temuan scanner tetap dibuat case — confidence **hanya untuk prioritas, bukan untuk filter**.

| Halaman | Elemen Confidence |
|---------|------------------|
| **`/cases`** (tabel OPEN) | Badge warna per baris |
| **`/cases`** (tabel OPEN) | Sort by confidence — Critical di atas |
| **`/cases`** (tabel OPEN) | Filter "Tampilkan hanya High+" |
| **`/cases/:id`** (detail) | Label + alasan (confidence_factors) |
| **`/archive`** (tabel CLOSED) | Badge confidence (read-only) |
| **`/dashboard`** (statistik) | Pie chart distribusi confidence |

### Tampilan Tabel

```
| ID        | Title                          | Scanner       | Confidence | Aksi |
|-----------|--------------------------------|---------------|------------|------|
| CASE-005  | Flash Loan di Swap()           | Slither+E...  | 🔴 Critical | [Download] |
| CASE-001  | Reentrancy di Vault.withdraw() | Slither+I...  | 🔴 Critical | [Download] |
| CASE-002  | Access Control di Token.mint() | Slither       | 🟠 High     | [Download] |
| CASE-004  | Unused Return di Vault.deposit | Slither       | ⚪ Low      | [Download] |
                                   ▲                              ▲
                                   │ Filter / Sort                │ Badge warna
```

### Tampilan Detail

```
┌─────────────────────────────────────────────┐
│ CASE-001                          🔴 Critical │
│                                                 │
│ Confidence Factors:                             │
│   ✅ 2 scanner mendeteksi                       │
│   ✅ PoC berhasil dibuat                        │
│   ✅ Pola reentrancy sebelumnya confirmed       │
└─────────────────────────────────────────────┘
```

### Warna Badge

| Label | Warna | Posisi Urutan |
|-------|-------|---------------|
| **Critical** | 🔴 Merah | Paling atas |
| **High** | 🟠 Orange | Kedua |
| **Medium** | 🟡 Kuning | Ketiga |
| **Low** | ⚪ Abu | Paling bawah |

---

## 4. Setelah Case Closed

### Jika Confirmed (Bounty Didapat)

```yaml
# Data masuk ke learning/patterns.yaml
- pattern_id: reentrancy-vault-withdraw
  vulnerability: reentrancy
  contract_pattern: "withdraw() + call()"
  status: confirmed
  bounty: 5000
  weight: 1            # +1 dari sebelumnya
```

Efek ke depan: Case serupa dapat **booster +1 level** dari Faktor C (max 1 level).

### Jika False Positive / Rejected

```yaml
- pattern_id: unused-return-vault-deposit
  vulnerability: unused-return
  contract_pattern: "deposit() + call()"
  status: false_positive
  weight: -1           # Bobot turun
```

Efek ke depan: Case serupa dapat **booster -1 level** dari Faktor C.

### Contoh Akumulasi Weight

```
reentrancy-vault-withdraw:
  CASE-001 → confirmed (weight: 1)
  CASE-012 → confirmed (weight: 2)
  CASE-020 → confirmed (weight: 3)
  # Case baru dengan pola ini → booster tetap 1 level (cap)
```

---

## 5. Implementasi

### Struktur Data Case (di `meta.yaml`)

```yaml
CASE-001:
  status: OPEN
  confidence: "Critical"           # Low / Medium / High / Critical
  confidence_factors:              # Alasan untuk ditampilkan di UI
    - "2 scanner mendeteksi"
    - "PoC berhasil dibuat"
    - "Pola reentrancy sebelumnya confirmed"
  scanners:
    - name: "Slither"
      detector: "reentrancy"
    - name: "Mythril"
      detector: "reentrancy"
  title: "Reentrancy di Vault.withdraw()"
  ...
```

### Pattern Learning (di `learning/patterns.yaml`)

```yaml
patterns:
  - id: reentrancy-vault-withdraw
    vulnerability: reentrancy
    function_pattern: "withdraw"
    call_pattern: "external_call_before_state_update"
    status: confirmed
    weight: 3              # Akumulasi dari 3 case confirmed
    cases:
      - CASE-001
      - CASE-012
      - CASE-020
```

### Backend Logic

File baru: `services/15-dashboard/src/confidence.py`

```python
def hitung_confidence(scanner_count, ada_poc, pattern_weight, kategori):
    label = "Medium"

    # Faktor A: Jumlah scanner
    if scanner_count >= 3:
        label = "Critical"
    elif scanner_count >= 2:
        label = "High"

    # Faktor B: PoC (naik 1, cap di Critical)
    if ada_poc and label == "Medium":
        label = "High"
    elif ada_poc and label == "High":
        label = "Critical"
    # Jika sudah Critical, tetap

    # Faktor C: Pattern learning (naik/turun 1, cap di Critical / Low)
    if pattern_weight >= 1:
        if label == "Medium":
            label = "High"
        elif label == "High":
            label = "Critical"
    elif pattern_weight == -1:
        if label == "High":
            label = "Medium"
        elif label == "Medium":
            label = "Low"

    # Faktor D: Kategori (final, override)
    if kategori in ("informational", "best-practice", "gas-optimization"):
        label = "Low"

    return label
```

### Endpoint API

| Method | Endpoint | Perubahan |
|--------|----------|-----------|
| `GET` | `/api/cases` | Tambah parameter `?confidence=Critical` untuk filter |
| `GET` | `/api/cases` | Response include field `confidence` dan `confidence_factors` |
| `GET` | `/api/cases/stats` | Tambah distribusi confidence |

---

## 6. Integrasi dengan 05_each_bug_is_cases.md

| Dokumen | Fokus |
|---------|-------|
| `05_each_bug_is_cases.md` | Lifecycle case: trigger, status OPEN/CLOSED, close oleh User |
| `06_confidence_atas_temuan.md` | Confidence scoring: prioritas case berdasarkan bukti |

**Hubungan**: Setiap case yang dibuat di `05` akan memiliki `confidence` yang dihitung berdasarkan aturan di dokumen ini.

---

*Dokumen ini menjadi acuan implementasi Confidence Scoring System.*
