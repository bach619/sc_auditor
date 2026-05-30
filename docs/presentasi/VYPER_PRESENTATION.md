---
marp: true
theme: uncover
class:
  - lead
  - invert
paginate: true
---

<!-- 
Speaker Note: Slide ini adalah presentasi tentang VYPER — Smart Contract Bug Hunter.
Target audiens: Investor, partner potensial, atau tim internal.
Gunakan arrow keys untuk navigasi.
-->

# **VYPER**

## Smart Contract Bug Hunter

Platform audit kontrak pintar berbasis microservice — Scan, Analisis, Exploit, dan Report dalam satu pipeline otomatis.

---

<!-- 
Slide 2: Masalah yang dipecahkan
-->

# **Masalah**

### Bug bounty hunter menghadapi 3 tantangan utama:

| # | Tantangan | Dampak |
|---|-----------|--------|
| 1 | **Tool terpisah-pisah** | Slither, Mythril, Echidna — setup sendiri-sendiri, output format beda |
| 2 | **False Positive** | 60-80% temuan tool adalah false alarm — buang waktu berjam-jam |
| 3 | **Butuh bukti exploit** | Immunefi require PoC untuk critical/high — harus buktikan manual |

---

<!-- 
Slide 3: Solusi VYPER
-->

# **Solusi: VYPER**

### Satu platform, 8 stage pipeline otomatis

```text
Immunefi → Source → Scanner → AI → Classifier → Exploit → Report → Notify
```

| Tahap | Fungsi | Waktu |
|-------|--------|-------|
| 1-3 | **Discover** — Cari program + ambil source | ~40 detik |
| 4-5 | **Analyze** — Scan + AI verdict | ~5-30 menit |
| 6 | **Classify** — TP/FP filtering | ~5 detik |
| 7 | **Exploit** — Buktikan dengan Anvil fork | ~2-10 menit |
| 8 | **Report** — Laporan siap submit | ~10 detik |

---

<!-- 
Slide 4: Business Logic — 4 Quadrant Classification
-->

# **Business Logic Inti**

### 4-Quadrant Detection Matrix

|  | **Bug Nyata** | **Tidak Ada Bug** |
|---|:---:|:---:|
| **Terdeteksi** | ✅ **TP** (True Positive) → Submit | ❌ **FP** (False Positive) → Filter |
| **Tidak Terdeteksi** | ⚠️ **FN** (False Negative) → Learning | ✅ **TN** (True Negative) |

### Aturan Klasifikasi
- AI confidence > 0.9 + critical/high → **Auto TP**
- AI confidence < 0.3 → **Auto FP**
- Match known pattern → override sesuai pattern

**Hasil:** Hunter hanya lihat True Positive — hemat 60-80% waktu.

---

<!-- 
Slide 5: Arsitektur — 20 Microservices
-->

# **Arsitektur**

### 20 microservices, 1 laptop

```text
┌────────────────────────────────────────────┐
│            DASHBOARD (React SPA)           │
│            API Gateway :8000               │
└────────────────┬───────────────────────────┘
                 │
┌────────────────▼───────────────────────────┐
│         ORCHESTRATOR (Pipeline) :8009       │
└──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬────┘
   │  │  │  │  │  │  │  │  │  │  │  │  │
   ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼
 IM  SRC SCN AI  CLS EXP RPT NTF CFG WHK AGT
```

### Kenapa Microservice?
- **Isolasi** — Satu service crash, lainnya tetap jalan
- **Scale** — `--scale scanner=3` untuk parallel scan
- **Update** — Update per-service tanpa restart semua
- **Stack** — Python 3.11 + FastAPI (semua service)

---

<!-- 
Slide 6: Target Market
-->

# **Target Market**

### 🎯 **Bug Bounty Hunter** (Individual)
- Hunting di Immunefi (234+ program)
- Ingin automasi scanning dengan kontrol penuh
- Need PoC untuk submit critical/high

### 🔬 **Security Researcher**
- Research kerentanan baru
- Validasi temuan dengan exploit real
- Track akurasi tool preference

### 🏢 **DeFi Protocol** (Enterprise)
- Continuous monitoring kontrak
- Pre-launch audit
- Due diligence M&A

---

<!-- 
Slide 7: Revenue Model — 3 Pilar
-->

# **Revenue Model**

| Model | Target | Revenue | Timeline |
|-------|--------|---------|----------|
| **A: Freemium SaaS** | Individual hunter | $29-99/bln per user | 1-2 bulan |
| **B: Bounty Split** | Hunter + Protocol | 10% fee dari bounty | Immediate |
| **C: Enterprise** | DeFi Protocol | $1k-5k/bln per client | 3-6 bulan |

### Model A — Freemium Tiers

| Free | Premium ($49/bln) | Pro ($99/bln) |
|------|-------------------|---------------|
| 5 scan/bln | Unlimited scans | Unlimited + priority |
| 1 AI/scan | Multiple AI models | All models + custom |
| Basic report | Full report + PoC | Full + white-label |
| 1 chain | All chains | All + custom chains |

---

<!-- 
Slide 8: Bounty Split Model
-->

# **Model B — Bounty Split**

### Cara Kerja
```text
Hunter scan via VYPER → Temukan TP → Submit via platform
                         ↓
              Protocol verifikasi + bayar bounty
                         ↓
              VYPER ambil 10% fee ($500 off $5k)
```

### Potensi Revenue

| Bounty | Fee 10% | Frekuensi/bln | Revenue/bln |
|--------|---------|---------------|-------------|
| $5,000 | $500 | 5 TP | $2,500 |
| $10,000 | $1,000 | 3 TP | $3,000 |
| $50,000+ | $5,000+ | 1 TP | $5,000+ |
| | | **Total** | **$10,500+** |

**Value Proposition:** Hunter bayar cuma kalau dapet bounty — zero risk.

---

<!-- 
Slide 9: Revenue Projection (3 Tahun)
-->

# **Revenue Projection**

### Model A (Freemium) + B (Bounty Split)

```text
Tahun 1:  500 user × $49 avg + 20 TP × $500 = $414,000
Tahun 2:  1,000 user × $49 avg + 50 TP × $500 = $888,000
Tahun 3:  1,500 user × $49 avg + 100 TP × $500 = $1,482,000
```

### Monthly Runway

| Tahun | MRR (Monthly) | ARR (Annual) |
|-------|:------------:|:------------:|
| 1 | $34,500 | $414,000 |
| 2 | $74,000 | $888,000 |
| 3 | $123,500 | $1,482,000 |

### Biaya Operasional
- Hosting: ~$500-2,000/bln (AWS/GCP)
- AI API: ~$0.50-2.00 per scan (pay-as-you-go)
- **Margin: 70-85%** setelah skala

---

<!-- 
Slide 10: Competitive Advantage
-->

# **Competitive Advantage**

### VYPER vs Kompetitor

| Aspek | Slither | Mythril | Tenderly | **VYPER** |
|-------|---------|---------|----------|-----------|
| **Pipeline** | ❌ Tool only | ❌ Tool only | ✅ | **✅ Full** |
| **AI Analysis** | ❌ | ❌ | ❌ | **✅** |
| **TP/FP Filter** | ❌ | ❌ | ❌ | **✅** |
| **Exploit Proof** | ❌ | ❌ | ✅ | **✅** |
| **Pattern Learning** | ❌ | ❌ | ❌ | **✅** |
| **Report Auto** | ❌ | ❌ | ❌ | **✅** |
| **Lokal/Offline** | ✅ | ✅ | ❌ | **✅** |

### Moat: **Integrasi + Learning Loop**
Semakin banyak dipakai → semakin banyak feedback → semakin akurat klasifikasi → semakin berharga.

---

<!-- 
Slide 11: Roadmap
-->

# **Roadmap**

### Phase 1 — Sekarang (v0.4.x)
- ✅ E2E Pipeline (8 stage)
- ✅ 19 microservices running
- ✅ TP/FP Classification + Pattern Learning
- ✅ Exploit Engine (Anvil)
- ✅ Dashboard React SPA

### Phase 2 — Q3 2026 (Monetisasi)
- 🔄 Freemium tier implementation
- 🔄 Payment & subscription system
- 🔄 Bounty split platform
- 🔄 API access for developers

### Phase 3 — Q4 2026 (Enterprise)
- 📋 Continuous monitoring
- 📋 Enterprise dashboard
- 📋 White-label reports
- 📋 SLA & support

---

<!-- 
Slide 12: Tim & Ask
-->

# **Call to Action**

### Yang Kami Cari

| Kebutuhan | Detail |
|-----------|--------|
| **Technical Co-founder** | DevOps / Platform Engineer — scale dari local ke cloud |
| **Initial Users** | 10 bug bounty hunter untuk beta testing + feedback |
| **Partnership** | DeFi protocol untuk enterprise pilot program |
| **Funding** | $50k-100k seed untuk hosting + development |

### Hubungi Kami

**VYPER** — Scan smarter, hunt faster.

---

<!-- 
Slide 13: Thank You
-->

# **Terima Kasih**

### **VYPER**
#### Smart Contract Bug Hunter

```text
github.com/vyper-audit
vyper.audit platform
```

> "Scan smarter, hunt faster."

---
