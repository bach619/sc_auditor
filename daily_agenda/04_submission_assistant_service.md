# Submission Assistant Service — Komunikasi dengan Immunefi

> **Masalah**: Kamu menemukan bug (apa pun tipenya — reentrancy, oracle manipulation, MEV, bridge exploit, zero-day, dll), lapor ke Immunefi, lalu Immunefi balas dengan pertanyaan.  
> Kamu bingung harus jawab apa. Atau takut jawabanmu kurang meyakinkan.  
> **Solusi**: Service yang membantu menyusun jawaban berdasarkan bukti (PoC, scan result, math engine) — disesuaikan dengan **tipe bug** yang dilaporkan.

---

## Daftar Isi

1. [Alur Komunikasi dengan Immunefi](#1-alur-komunikasi-dengan-immunefi)
2. [Apa yang Dibutuhkan](#2-apa-yang-dibutuhkan)
3. [Desain Service](#3-desain-service)
4. [Flow Lengkap](#4-flow-lengkap)
5. [Integrasi dengan Pipeline](#5-integrasi-dengan-pipeline)
6. [Endpoint API](#6-endpoint-api)
7. [Contoh Skenario](#7-contoh-skenario)
8. [Rencana Implementasi](#8-rencana-implementasi)

---

## 1. Alur Komunikasi dengan Immunefi

```
Kamu                                          Immunefi
 │                                              │
 │  1. Submit finding (any bug type) + PoC      │
 ├─────────────────────────────────────────────►│
 │                                              │
 │                                              │
 │  2. Immunefi balas (via dashboard/email):    │
 │     ┌──────────────────────────────┐         │
 │     │ "We need more evidence that  │         │
 │     │  this is exploitable. Can    │◄────────┤
 │     │  you demonstrate with a     │         │
 │     │  different approach?"       │         │
 │     └──────────────────────────────┘         │
 │                                              │
 │  ❌ Kamu bingung jawab apa                   │
 │                                              │
 │  3. Service ini bantu kamu:                  │
 │     • Analisa pertanyaan Immunefi            │
 │     • Deteksi tipe bug + konteksnya          │
 │     • Cari data pendukung dari pipeline      │
 │       (sesuai kategori bug)                  │
 │     • Generate draft jawaban                 │
 │     • Sertakan bukti tambahan                │
 │                                              │
 │  4. Kamu kirim jawaban                       │
 ├─────────────────────────────────────────────►│
 │                                              │
 │  5. Immunefi balas lagi...                   │
 │  (ulang sampai finding diterima/ditolak)     │
 ```

### Jenis Respons dari Immunefi

| Jenis | Contoh | Yang Dilakukan Service Ini |
|-------|--------|---------------------------|
| **Need more evidence** | "Can you show the exact transaction?" | Ambil tx hash dari Anvil fork, generate calldata — disesuaikan kategori bug |
| **Severity dispute** | "This is medium, not critical" | Hitung ulang impact dengan MathEngine berdasarkan kategori bug |
| **Duplicate claim** | "Already reported by X" | Bantu buat argumen kenapa ini berbeda (attack vector, impact scope) |
| **Out of scope** | "This contract is not covered" | Tunjukkan bukti dari Service 02 (program scope) + argumen kenapa tetap relevan |
| **Fix suggestion** | "Will this fix work?" | Test fix di Anvil fork, kirim hasilnya — termasuk regression test untuk kategori terkait |
| **Questions** | "How did you find this?" | Generate penjelasan teknis dari pipeline + methodology per kategori bug |

### Kategori Bug yang Didukung

Service ini menangani **semua kategori bug** yang dideteksi pipeline:

| Kategori | Contoh | Evidence Khas | Strategi Argumentasi |
|----------|--------|---------------|---------------------|
| **Reentrancy** | Read-only reentrancy, cross-function | Anvil trace, state diff, call graph | Tunjukkan exploit flow + fund flow |
| **Oracle Manipulation** | TWAP manipulation, LP price | MathEngine AMM calc, price impact graph | Hitung biaya manipulasi vs profit |
| **Flash Loan Attack** | Economic exploit via flash loan | Tx simulation, profit calculation | Demonstrasi end-to-end dengan flash loan |
| **MEV / Sandwich** | Front-running, timestamp manipulation | MEV optimizer output, profit calc | Tunjukkan MEV profit + probability |
| **Access Control** | Privilege escalation, missing check | Role hierarchy, affected functions | Tunjukkan siapa yang bisa exploit |
| **Integer Overflow** | Arithmetic underflow/overflow | SAT solver output, boundary conditions | Hitung exact values yang trigger overflow |
| **Precision Loss** | Fee calculation, rounding | Fixed-point analyzer, loss per tx | Hitung akumulasi loss |
| **Bridge Exploit** | Message passing, validator set | Cross-chain proof, merkle proof | Tunjukkan attack path across chains |
| **Zero-Day / Novel** | New attack pattern, unknown vector | Full PoC + math proof + video | Argumen bahwa ini original + novel finding |
| **Governance Attack** | Proposal manipulation, vote buying | Governance simulation, vote analysis | Tunjukkan voting power needed |
| **Signature Replay** | ECDSA nonce reuse, cross-chain replay | Modular arithmetic, signature pairs | Tunjukkan signature yang sama di chain beda |
| **Storage Collision** | Struct packing, slot overlap | LLL lattice output, storage diff | Tunjukkan storage layout collision |
| **Donation Attack** | Inflation via donation, share calculation | AMM math, share price impact | Hitung share inflation percentage |

---

## 2. Apa yang Dibutuhkan

### Data yang Harus Disimpan Service Ini

```python
@dataclass
class Submission:
    """Satu submission ke Immunefi — untuk semua tipe bug."""
    
    id: str                          # UUID
    program_slug: str                # e.g. "euler-finance"
    finding_id: str                  # ID dari pipeline kita (F-001)
    
    # Kategori bug — penting untuk strategi argumentasi
    bug_category: str                # reentrancy / oracle_manipulation / flash_loan / 
                                     # mev / access_control / overflow / precision_loss /
                                     # bridge / zero_day / governance / signature_replay /
                                     # storage_collision / donation / other
    
    # Initial submission
    title: str
    description: str
    severity: str                    # critical / high / medium / low
    poc_solidity: str                # PoC dari Service 08 (sesuai kategori)
    tx_hash: str | None              # Tx hash dari Anvil run
    exploit_sequence: list[dict]     # Step-by-step exploit
    
    # Evidence spesifik per kategori
    category_specific_evidence: dict | None = None
    # Contoh per kategori:
    # reentrancy:       {"call_graph": [...], "state_diff": {...}}
    # oracle:           {"price_impact": {...}, "manipulation_cost": 123.45}
    # flash_loan:       {"flash_loan_amount": 1e6, "profit": 500000}
    # mev:              {"mev_score": 0.87, "sandwich_probability": 0.92}
    # overflow:         {"exact_values": [2**255-1], "trigger_condition": "x > max"}
    # precision_loss:   {"loss_per_tx": 0.001, "accumulated_loss": 10000}
    # bridge:           {"source_chain": "eth", "dest_chain": "polygon", "validator_set": [...]}
    # zero_day:         {"novelty_arguments": [...], "prior_art_search": "none"}
    # governance:       {"proposal_id": 42, "required_votes": 1_000_000}
    # signature_replay: {"chain_ids": [1, 137], "same_v_r_s": true}
    # storage_collision:{"slot_mapping": {...}, "collision_variables": [...]}
    # donation:         {"share_inflation": "12.5%", "donation_amount": 100}
    
    # Communication thread
    messages: list[Message]          # Semua chat dengan Immunefi
    
    # Status
    status: str                      # submitted / in_review / accepted / rejected / paid
    immunefi_submission_id: str | None  # ID dari Immunefi
    
    created_at: datetime
    updated_at: datetime


@dataclass
class Message:
    """Satu pesan dalam thread komunikasi."""
    
    role: str                        # "us" atau "immunefi"
    content: str                     # Isi pesan
    attachments: list[str]           # File yang dilampirkan
    created_at: datetime
    
    # Analisa dari service ini
    intent: str                      # "request_evidence" / "severity_dispute" / dll
    intent_context: dict | None      # Konteks tambahan: bug_category, severity, dll
    suggested_reply: str | None      # Draft jawaban yang di-generate
    supporting_data: dict | None     # Data pendukung dari pipeline
```

### Integrasi yang Diperlukan

| Integration | Source | Untuk Apa |
|-------------|--------|-----------|
| **PoC Exploit** | Service 08 | Bukti utama (semua kategori) |
| **Scan Results** | Service 04a-d, 05 | Evidence tambahan per kategori |
| **MathEngine** | Service 08 (maths/) | Hitung ulang impact per kategori |
| **Contract Source** | Service 03 | Tunjukkan lokasi bug |
| **Program Info** | Service 02 | Cek scope, bounty |
| **AI** | Service 06 | Generate draft jawaban (dengan konteks kategori bug) |
| **Notification** | Service 10 | Alert ketika Immunefi balas |
| **Exploit Database** | Internal DB | Cari comparable bugs per kategori untuk severity argument |

---

## 3. Desain Service

### Nama: `16-submission` (port 8018)

Kenapa terpisah dari Service 02:
- Service 02 fokus pada **program listing** (read-only GitHub mirror)
- Service 16 fokus pada **komunikasi dua arah** dengan Immunefi (write)
- Keduanya bisa jalan independen

### Arsitektur

```
                        ┌────────────────────┐
                        │    Immunefi API     │
                        │  (api.immunefi.com) │
                        └────────┬───────────┘
                                 │ HTTPS
                                 ▼
┌─────────────────────────────────────────────────────┐
│              16-submission (port 8018)               │
│                                                      │
│  ┌──────────────────┐    ┌──────────────────────┐   │
│  │  Submission DB   │    │  Communication Engine │   │
│  │  (PostgreSQL)    │◄──►│                      │   │
│  │                  │    │  • Intent classifier  │   │
│  │  submissions     │    │  • Reply generator    │   │
│  │  messages        │    │  • Evidence collector  │   │
│  │  attachments     │    │  • Deadline tracker   │   │
│  └──────────────────┘    └──────────┬───────────┘   │
│                                     │               │
│  ┌──────────────────────────────────┴───────────┐   │
│  │           Evidence Collector                  │   │
│  │                                              │   │
│  │  • 03-Source  → ambil source + ABI           │   │
│  │  • 04a-d/05  → ambil scan results            │   │
│  │  • 08-Exploit → ambil PoC + tx hash          │   │
│  │  • 08-Maths  → ambil parameter exact         │   │
│  │  • 06-AI     → generate draft reply          │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  FastAPI Endpoints                                   │
│  ┌──────────────────────────────────────────────┐   │
│  │ POST /submissions          (buat submission)  │   │
│  │ GET  /submissions/{id}     (detail + thread)  │   │
│  │ POST /submissions/{id}/respond (kirim jawab)  │   │
│  │ POST /submissions/{id}/draft (generate draft) │   │
│  │ GET  /submissions/{id}/evidence (bukti auto)  │   │
│  │ POST /webhook/immunefi    (terima balasan)    │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
         │              │              │
         ▼              ▼              ▼
   ┌─────────┐   ┌──────────┐   ┌──────────┐
   │ 08-     │   │ 04a-d/05│   │ 06-AI    │
   │ Exploit │   │ Scanner │   │          │
   └─────────┘   └──────────┘   └──────────┘
```

### Database Schema

```sql
-- Enum: kategori bug yang didukung pipeline
CREATE TYPE bug_category AS ENUM (
    'reentrancy', 'oracle_manipulation', 'flash_loan', 'mev',
    'access_control', 'overflow', 'precision_loss', 'bridge',
    'zero_day', 'governance', 'signature_replay', 'storage_collision',
    'donation', 'other'
);

-- Submissions (untuk semua kategori bug)
CREATE TABLE submissions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_slug            TEXT NOT NULL,
    finding_id              TEXT NOT NULL,
    
    -- Kategori bug — penting untuk routing strategi argumentasi
    bug_category            bug_category NOT NULL DEFAULT 'other',
    
    -- Initial submission data
    title                   TEXT NOT NULL,
    description             TEXT NOT NULL,
    severity                TEXT NOT NULL,  -- critical/high/medium/low
    poc_solidity            TEXT,
    tx_hash                 TEXT,
    exploit_sequence        JSONB DEFAULT '[]',
    
    -- Evidence spesifik per kategori (disimpan sebagai JSON)
    category_evidence       JSONB DEFAULT '{}',
    -- Contoh per kategori:
    -- reentrancy:      {"call_graph": [...], "state_diff": {...}, "call_depth": 3}
    -- oracle:         {"manipulation_cost": 120000, "profit": 2400000, "twap_window": 5}
    -- overflow:       {"exact_values": [...], "trigger_condition": "..."}
    -- zero_day:       {"novelty_arguments": [...], "prior_art_search": "none"}
    -- mev:            {"mev_score": 0.87, "sandwich_profit": 500000}
    -- lihat dataclass Submission.category_specific_evidence untuk detail
    
    -- Immunefi tracking
    immunefi_submission_id  TEXT,
    status                  TEXT DEFAULT 'draft',
    -- draft / submitted / in_review / accepted / rejected / paid
    
    -- Metadata
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    submitted_at            TIMESTAMPTZ,
    
    UNIQUE(finding_id)
);

-- Messages (communication thread)
CREATE TABLE messages (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id           UUID REFERENCES submissions(id) ON DELETE CASCADE,
    role                    TEXT NOT NULL,  -- 'us' atau 'immunefi'
    content                 TEXT NOT NULL,
    
    -- Analysis
    intent                  TEXT,           -- request_evidence / severity_dispute / etc
    intent_context          JSONB DEFAULT '{}',  -- {bug_category, severity, confidence}
    suggested_reply         TEXT,
    reply_used              BOOLEAN DEFAULT FALSE,
    
    -- Attachments
    attachments             JSONB DEFAULT '[]',
    
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- Evidence cache (data pendukung dari pipeline — category-aware)
CREATE TABLE evidence_cache (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id           UUID REFERENCES submissions(id) ON DELETE CASCADE,
    evidence_type           TEXT NOT NULL,
    -- scan_result / exploit_output / math_parameters / source_code / etc
    bug_category            bug_category,   -- untuk routing query
    data                    JSONB NOT NULL,
    source_service          TEXT NOT NULL,  -- 03 / 04a / 08 / etc
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- Index: cari evidence per kategori
CREATE INDEX idx_evidence_category ON evidence_cache(submission_id, bug_category);

-- Attachments (file storage)
CREATE TABLE attachments (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id           UUID REFERENCES submissions(id) ON DELETE CASCADE,
    message_id              UUID REFERENCES messages(id) ON DELETE CASCADE,
    filename                TEXT NOT NULL,
    file_type               TEXT,  -- sol / json / txt / png
    file_size               INT,
    storage_path            TEXT NOT NULL,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- Index: cari submission per kategori
CREATE INDEX idx_submissions_category ON submissions(bug_category);

-- Index: cari submission per status + kategori
CREATE INDEX idx_submissions_status_category ON submissions(status, bug_category);
```

---

## 4. Flow Lengkap

### 4.1 Submit Finding Baru

```
Klik "Submit ke Immunefi" di dashboard
         │
         ▼
┌─────────────────────────────────────────────┐
│ 16-submission:  POST /submissions           │
│                                             │
│  Otomatis mengumpulkan:                     │
│  • PoC dari Service 08                      │
│  • Scan results dari 04a-d + 05             │
│  • Source code dari 03                      │
│  • Program info dari 02                     │
│  • Math parameters dari MathEngine          │
│                                             │
│  Hasil: satu paket submission lengkap       │
└─────────────────────────────────────────────┘
         │
         ▼
Kamu review → edit → kirim ke Immunefi
```

### 4.2 Immunefi Balas — Service Otomatis Merespon

```
Immunefi mengirim pesan:
  "Can you show the exact calldata for the exploit?"
         │
         ▼
┌─────────────────────────────────────────────┐
│ Webhook /api/immunefi/message              │
│                                             │
│ Langkah 1: Intent Classifier                │
│   Input: "Can you show the exact calldata?" │
│   Output: "request_evidence" (confidence 95%)│
│                                             │
│ Langkah 2: Evidence Collector               │
│   Intent = request_evidence                 │
│   → Ambil tx_hash dari Anvil run            │
│   → Ambil calldata raw                      │
│   → Format sebagai attachment               │
│                                             │
│ Langkah 3: Draft Generator (via AI)         │
│   Prompt:                                    │
│     "Immunefi requests calldata evidence    │
│      for finding X. Here is the data: ...   │
│      Generate a professional response."     │
│   Output: draft jawaban + attachment        │
│                                             │
│ Langkah 4: Notifikasi ke kamu               │
│   "[16] Immunefi membalas: request calldata │
│    Draft jawaban siap, review di sini: URL" │
└─────────────────────────────────────────────┘
         │
         ▼
Kamu review draft → edit jika perlu → kirim
```

### 4.3 Jenis Intent yang Dideteksi

Intent classifier bekerja dalam dua lapisan:
1. **Intent utama** — apa yang Immunefi minta (sama untuk semua bug)
2. **Konteks kategori bug** — bagaimana service merespons (berbeda per kategori)

```python
INTENTS = {
    "request_evidence": {
        "description": "Immunefi minta bukti tambahan",
        "confidence_threshold": 0.7,
        "action": "Kumpulkan data dari pipeline sesuai kategori bug",
        "evidence_needed": {
            "default": ["tx_hash", "calldata", "forge_output", "anvil_logs", "state_diff"],
            "reentrancy":      ["call_graph", "reentrancy_guard_check", "state_diff_per_call"],
            "oracle_manipulation": ["price_impact_graph", "manipulation_cost", "twap_snapshots"],
            "flash_loan":      ["flash_loan_provider", "profit_calculation", "repay_flow"],
            "mev":             ["mev_score", "priority_gas_analysis", "sandwich_profit"],
            "overflow":        ["exact_overflow_values", "boundary_conditions", "sat_solver_output"],
            "precision_loss":  ["loss_per_tx_calc", "accumulated_loss", "affected_functions"],
            "bridge":          ["cross_chain_proof", "validator_set", "message_relay_logs"],
            "zero_day":        ["novelty_proof", "prior_art_analysis", "full_math_breakdown"],
            "governance":      ["proposal_simulation", "vote_weight_analysis", "timelock_bypass"],
            "signature_replay":["signature_pairs", "chain_ids", "recover_addresses"],
            "storage_collision":["slot_layout", "collision_proof", "overwritten_variables"],
            "donation":        ["share_price_history", "donation_simulation", "inflation_percentage"],
            "access_control":  ["role_hierarchy", "permission_matrix", "exploit_tx_analysis"],
        },
    },
    
    "severity_dispute": {
        "description": "Immunefi menganggap severity terlalu tinggi",
        "confidence_threshold": 0.8,
        "action": "Hitung ulang impact dengan MathEngine — parameter tergantung kategori bug",
        "evidence_needed": [
            "math_impact_analysis",
            "comparable_bugs_per_category",
            "market_impact_data",
        ],
        "category_impact_calculation": {
            "reentrancy":       "max_drainable_per_tx + affected_pools",
            "oracle_manipulation": "manipulation_cost_vs_tvl + affected_oracles",
            "flash_loan":       "max_profit_per_flash_loan + protocol_tvl",
            "mev":              "extractable_value_per_block + affected_users",
            "overflow":         "max_mintable_tokens + total_supply",
            "precision_loss":   "accumulated_loss_per_year + affected_users",
            "bridge":           "max_bridge_capacity + affected_chains",
            "zero_day":         "novelty_score + max_theoretical_loss",
            "governance":       "controllable_funds + proposal_success_rate",
            "signature_replay": "replayable_value_per_chain + chain_count",
            "storage_collision": "corrupted_storage_value + affected_contracts",
            "donation":         "max_donation_impact + tvl_impact",
            "access_control":   "funds_at_risk + privilege_level",
        },
    },
    
    "duplicate_claim": {
        "description": "Immunefi klaim sudah ada yang report",
        "confidence_threshold": 0.85,
        "action": "Analisa perbedaan dengan finding yang diklaim duplicate — perhatikan kategori bug",
        "evidence_needed": [
            "diff_analysis_per_category",
            "unique_attack_vector",
            "different_impact_scope",
            "original_contribution",
        ],
    },
    
    "out_of_scope": {
        "description": "Immunefi anggap di luar scope",
        "confidence_threshold": 0.8,
        "action": "Check scope dari Service 02 + argumen kenapa relevan",
        "evidence_needed": [
            "program_scope",
            "contract_address_match",
            "previous_accepted_findings_same_category",
            "impact_on_in_scope_contracts",
        ],
    },
    
    "fix_question": {
        "description": "Immunefi tanya tentang fix",
        "confidence_threshold": 0.75,
        "action": "Test fix di Anvil fork — verifikasi tidak hanya bug asli tapi juga edge cases terkait kategori",
        "evidence_needed": [
            "fixed_version_test_result",
            "gas_diff",
            "regression_test_per_category",
            "bypass_attempts",
        ],
    },
    
    "general_question": {
        "description": "Pertanyaan umum tentang finding",
        "confidence_threshold": 0.6,
        "action": "Generate jawaban dari data yang ada — sesuaikan penjelasan dengan kategori bug",
        "evidence_needed": [
            "finding_summary_per_category",
            "attack_timeline",
            "methodology_explanation",
            "related_findings_same_category",
        ],
    },
    
    "accepted": {
        "description": "Immunefi menerima finding! 🎉",
        "confidence_threshold": 0.9,
        "action": "Tracking pembayaran + arsipkan sebagai reference untuk kategori yang sama",
        "evidence_needed": [],
    },
    
    "rejected": {
        "description": "Immunefi menolak finding",
        "confidence_threshold": 0.9,
        "action": "Analisa alasan penolakan → saran perbaikan spesifik kategori",
        "evidence_needed": [
            "rejection_reason_analysis",
            "improvement_suggestions_per_category",
            "resubmission_strategy",
        ],
    },
}
```

### 4.4 Draft Generator (via AI Service 06)

```python
class SubmissionAIAssistant:
    """Generate draft jawaban menggunakan AI — category-aware."""
    
    # Template strategi argumentasi per kategori bug
    CATEGORY_ARGUMENT_TEMPLATES = {
        "reentrancy": """
        This is a classic reentrancy vulnerability, but with a novel twist:
        - Attack vector: {attack_vector}
        - Call graph depth: {call_depth} levels
        - Affected functions: {affected_functions}
        - Read-only reentrancy? {is_read_only}
        - Cross-function reentrancy? {is_cross_function}
        
        The PoC demonstrates a full exploit flow: {exploit_steps}
        
        What makes this particularly dangerous is {unique_aspect}.
        """,
        
        "oracle_manipulation": """
        This oracle manipulation attack exploits {oracle_type} price feeds.
        
        Key parameters from MathEngine:
        - Manipulation cost: ${manipulation_cost:,.0f}
        - Profit at manipulation cost: ${profit_at_cost:,.0f}
        - Break-even manipulation size: {break_even_size}
        - TWAP window exploited: {twap_window} blocks
        
        The exploit is economically viable because {economic_argument}.
        """,
        
        "flash_loan": """
        This flash loan attack requires:
        - Flash loan amount: ${flash_loan_amount:,.0f}
        - Protocol TVL affected: ${affected_tvl:,.0f}
        - Net profit: ${net_profit:,.0f}
        - Steps: {exploit_steps}
        
        The attack is {is_profitable} because {profit_analysis}.
        """,
        
        "mev": """
        This MEV vulnerability enables:
        - MEV score: {mev_score}/1.0
        - Sandwich profit per block: ${sandwich_profit:,.0f}
        - Affected user loss per tx: ${user_loss:,.0f}
        - Probability of exploitation: {probability}
        
        The key insight is {mev_insight}.
        """,
        
        "overflow": """
        Integer overflow/underflow in {contract} at {function}:
        - Variable: {variable}
        - Type: {var_type} ({bits}-bit)
        - Overflow value: {overflow_value}
        - Trigger condition: {trigger_condition}
        - Max exploit value: ${max_value:,.0f}
        
        The SAT solver confirmed: {sat_result}
        """,
        
        "precision_loss": """
        Precision loss in fee calculation:
        - Function: {function}
        - Division order: {division_order}
        - Loss per transaction: {loss_per_tx}
        - Accumulated loss over {time_period}: {accumulated_loss}
        - Affected users: {affected_users}
        
        The fixed-point analyzer shows {fp_analysis}.
        """,
        
        "bridge": """
        Cross-chain bridge vulnerability:
        - Source chain: {source_chain}
        - Destination chain: {dest_chain}
        - Bridge type: {bridge_type}
        - Validator set size: {validator_count}
        - Compromised validators needed: {needed_validators}
        
        The attack path: {attack_path}
        """,
        
        "zero_day": """
        **NOVEL VULNERABILITY** — No prior art found.
        
        This is a novel attack pattern because:
        1. {novelty_point_1}
        2. {novelty_point_2}
        3. {novelty_point_3}
        
        Search conducted across: {search_sources}
        Closest prior art: {closest_prior_art} (but differs because {difference})
        
        Full mathematical proof available via MathEngine: {math_proof_available}
        """,
        
        "governance": """
        Governance attack via {attack_vector}:
        - Proposal ID: {proposal_id}
        - Required votes: {required_votes}
        - Attacker-controlled votes: {attacker_votes}
        - Vote manipulation: {vote_manipulation_method}
        - Time lock bypass? {timelock_bypass}
        - Funds at risk: ${funds_at_risk:,.0f}
        """,
        
        "signature_replay": """
        Signature replay vulnerability:
        - Same signature valid on: {chain_ids}
        - Reusable value: ${reusable_value:,.0f}
        - ECDSA nonce: {nonce} (reused across chains)
        - Affected functions: {affected_functions}
        
        The modular arithmetic proof: {modular_proof}
        """,
        
        "storage_collision": """
        Storage collision via struct packing:
        - Contract: {contract}
        - Slot {slot}: {variable_1} collides with {variable_2}
        - LLL-reduced basis: {lll_basis}
        - Exploit: write to {variable_1} corrupts {variable_2}
        - Impact: {impact}
        """,
        
        "donation": """
        Donation attack / share inflation:
        - Exchange rate manipulation: {exchange_rate_change}
        - Donation amount: ${donation_amount:,.0f}
        - Share inflation: {share_inflation}
        - Victims: {victim_count} LP holders
        - Profit: ${profit:,.0f}
        """,
        
        "access_control": """
        Access control bypass:
        - Missing check in: {function}
        - Required role: {required_role}
        - Current access: {current_access}
        - Exploitable by: {exploitable_by}
        - Funds at risk: ${funds_at_risk:,.0f}
        - Privilege escalation path: {escalation_path}
        """,
    }
    
    async def generate_draft(
        self,
        submission: Submission,
        immunefi_message: str,
        intent: str,
        evidence: dict,
    ) -> str:
        """Generate draft jawaban yang profesional — category-aware."""
        
        # Ambil konteks submission
        poc_summary = self._summarize_poc(submission.poc_solidity)
        scan_highlights = self._get_scan_highlights(submission.finding_id)
        program = await self._get_program_info(submission.program_slug)
        
        # Dapatkan template argumen spesifik kategori
        category = submission.bug_category
        cat_template = self.CATEGORY_ARGUMENT_TEMPLATES.get(category, "")
        category_arguments = cat_template.format(**evidence.get("category_data", {})) if cat_template else ""
        
        prompt = f"""
        You are a professional smart contract security researcher 
        responding to Immunefi's bug bounty team.
        
        ## Finding Context
        Title: {submission.title}
        Bug Category: {category}
        Severity: {submission.severity}
        Program: {program.name}
        Bounty: ${program.max_bounty:,.0f}
        
        ## Category-Specific Analysis
        {category_arguments}
        
        ## PoC Summary
        {poc_summary}
        
        ## Scan Results
        {scan_highlights}
        
        ## Immunefi's Message
        "{immunefi_message}"
        
        ## Detected Intent
        {intent}: {INTENTS[intent]['description']}
        
        ## Available Evidence
        {json.dumps(evidence, indent=2)}
        
        ## Crafting Instructions
        Generate a professional response that:
        1. Acknowledges Immunefi's message professionally
        2. References the CATEGORY-SPECIFIC analysis above
        3. Uses technical language appropriate for {category} vulnerabilities
        4. Is concise (under 300 words unless necessary)
        5. Maintains a respectful, collaborative tone
        6. If this is a NOVEL/zero-day finding, emphasize the uniqueness
        7. If this is a known pattern (reentrancy, oracle, etc.), 
           emphasize the unique aspects of your specific exploit
        
        Return ONLY the response text, no additional commentary.
        """
        
        # Kirim ke AI Service
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://06-ai:8004/chat/completions",
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": prompt},
                    ],
                    "temperature": 0.3,  # Low = konsisten, profesional
                    "max_tokens": 1000,
                },
                timeout=30.0,
            )
            
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            
            # Fallback: template-based response per category
            return self._template_response(intent, evidence, category)
    
    def _template_response(self, intent: str, evidence: dict, category: str = "default") -> str:
        """Template fallback jika AI tidak reachable — category-aware."""
        
        templates = {
            "request_evidence": {
                "default": (
                    "Thank you for your review. Regarding your request for additional "
                    "evidence, please find attached the following:\n\n"
                    "1. Transaction hash: {tx_hash}\n"
                    "2. Complete calldata\n"
                    "3. Forge test output showing the exploit\n\n"
                    "The exploit was tested in an isolated Anvil environment (no real "
                    "funds at risk). Please let me know if you need any clarification."
                ),
                "reentrancy": (
                    "Thank you for your review. Please find the reentrancy-specific evidence:\n\n"
                    "1. Full call graph showing reentrancy loop ({call_depth} levels)\n"
                    "2. State diff at each call frame\n"
                    "3. Reentrancy guard bypass demonstration\n"
                    "4. Anvil trace with exact instruction stepping\n\n"
                    "The exploit was tested with both read-only and write reentrancy patterns."
                ),
                "oracle_manipulation": (
                    "Thank you for your review. Attached is the oracle manipulation evidence:\n\n"
                    "1. Price impact graph across {n_pools} pools\n"
                    "2. Manipulation cost breakdown: ${manipulation_cost:,.0f}\n"
                    "3. TWAP window analysis ({twap_window} blocks)\n"
                    "4. MathEngine profit calculation\n\n"
                    "The economic analysis confirms the attack is profitable at {break_even_size} manipulation size."
                ),
                "zero_day": (
                    "Thank you for your review. This is a NOVEL vulnerability finding.\n\n"
                    "Attached evidence:\n"
                    "1. Full mathematical proof of the exploit\n"
                    "2. Prior art search results (no matching findings)\n"
                    "3. Multiple PoC variants demonstrating different attack paths\n"
                    "4. Anvil fork simulation with exact fund flows\n\n"
                    "I believe this represents an original contribution to the program's security."
                ),
                "overflow": (
                    "Thank you for your review. Attached are the overflow-specific details:\n\n"
                    "1. SAT solver output confirming exact overflow values\n"
                    "2. Boundary condition analysis\n"
                    "3. Minimal PoC demonstrating the overflow\n"
                    "4. Maximum extractable value calculation\n\n"
                    "The overflow is triggered when {trigger_condition}."
                ),
            },
            "severity_dispute": {
                "default": (
                    "I appreciate the thorough review. Regarding the severity "
                    "classification, I'd like to highlight that:\n\n"
                    "1. The maximum potential loss is ${max_loss:,.0f}\n"
                    "2. This affects {affected_users} users\n"
                    "3. The exploit requires no special privileges\n\n"
                    "Based on Immunefi's own severity guidelines for {program}, "
                    "this meets the criteria for {current_severity}."
                ),
                "oracle_manipulation": (
                    "I respectfully disagree with the severity classification.\n\n"
                    "Per Immunefi's oracle manipulation severity guidelines:\n"
                    "- Manipulation cost (${manipulation_cost:,.0f}) is only {pct_of_tvl}% of TVL\n"
                    "- Profit potential (${profit:,.0f}) exceeds {pct_threshold}% of pool\n"
                    "- {n_oracles}/{total_oracles} oracles are manipulable\n\n"
                    "This clearly meets the criteria for {current_severity} severity."
                ),
                "reentrancy": (
                    "Regarding the severity classification, please consider:\n\n"
                    "1. The reentrancy allows DRAINING {max_drainable} per transaction\n"
                    "2. No reentrancy guard present in {affected_functions}\n"
                    "3. Can be combined with flash loan for amplified impact\n"
                    "4. Affects {n_pools} pools totaling ${tvl_affected:,.0f} TVL\n\n"
                    "Per Immunefi's reentrancy severity matrix, this is {current_severity}."
                ),
                "zero_day": (
                    "I understand the severity concern, but I believe this novel vulnerability "
                    "warrants {current_severity} classification:\n\n"
                    "1. No existing mitigations exist for this attack pattern\n"
                    "2. Maximum theoretical loss: ${max_loss:,.0f}\n"
                    "3. Novel attack vector means no current monitoring covers it\n"
                    "4. Comparable novel vulnerabilities in similar protocols were classified {comparable_severity}\n\n"
                    "The novelty premium is justified by the lack of existing defenses."
                ),
            },
        }
        
        # Coba template spesifik category, fallback ke default
        category_templates = templates.get(intent, {})
        template = category_templates.get(category, category_templates.get("default", 
            "Thank you for your message. {response}"))
        return template.format(**evidence)
```

---

## 5. Integrasi dengan Pipeline

```
                    ┌──────────────────┐
                    │  Dashboard (15)   │
                    │  "Immunefi balas!"│
                    └────────┬─────────┘
                             │
              ┌──────────────┴──────────────┐
              │                              │
              ▼                              ▼
┌────────────────────────┐    ┌────────────────────────┐
│ 02-Immunefi             │    │ 16-Submission           │
│ • Program list          │    │ • Submission thread     │
│ • Scope info            │    │ • Draft jawaban        │
│ • Bounty amount         │    │ • Evidence collector   │
└────────────────────────┘    └────────────────────────┘
         │                              │
         └──────────────┬───────────────┘
                        ▼
              ┌────────────────────────┐
              │  06-AI                 │
              │  Generate draft reply  │
              └────────────────────────┘
                        │
                        ▼
              ┌────────────────────────┐
              │  10-Notifier            │
              │  "Kamu punya pesan baru"│
              └────────────────────────┘
```

### Koneksi ke Service Lain

```python
# src/integrations.py

class PipelineIntegrations:
    """Koleksi semua koneksi ke service lain — category-aware."""
    
    # Mapping kategori bug → service mana yang paling relevan
    CATEGORY_SERVICE_PRIORITY = {
        "reentrancy":       ["08-exploit", "04a-slither", "11-orchestrator"],
        "oracle_manipulation": ["08-exploit", "08-maths", "04a-slither"],
        "flash_loan":       ["08-exploit", "08-maths", "04a-slither"],
        "mev":              ["08-exploit", "08-maths"],
        "access_control":   ["04a-slither", "03-source", "08-exploit"],
        "overflow":         ["08-exploit", "08-maths", "04a-slither"],
        "precision_loss":   ["08-exploit", "08-maths"],
        "bridge":           ["08-exploit", "03-source", "04a-slither"],
        "zero_day":         ["08-exploit", "08-maths", "04a-slither", "04d-halmos"],
        "governance":       ["08-exploit", "03-source", "04a-slither"],
        "signature_replay": ["08-exploit", "08-maths"],
        "storage_collision":["08-exploit", "08-maths", "04a-slither"],
        "donation":         ["08-exploit", "08-maths", "04a-slither"],
        "other":            ["08-exploit", "04a-slither", "11-orchestrator"],
    }
    
    async def collect_all_evidence(
        self, finding_id: str, bug_category: str = "other"
    ) -> dict[str, Any]:
        """Kumpulkan semua bukti dari pipeline — disesuaikan kategori bug."""
        
        # Evidence umum (semua kategori)
        evidence = {
            "source": await self._get_source(finding_id),
            "scan_results": await self._get_scans(finding_id, bug_category),
            "exploit_poc": await self._get_exploit(finding_id, bug_category),
            "math_params": await self._get_math(finding_id, bug_category),
            "program_info": await self._get_program(finding_id),
        }
        
        # Evidence spesifik kategori
        category_data = await self._get_category_specific_evidence(
            finding_id, bug_category
        )
        evidence["category_data"] = category_data
        
        return evidence
    
    async def _get_category_specific_evidence(
        self, finding_id: str, bug_category: str
    ) -> dict:
        """Kumpulkan evidence spesifik untuk kategori bug tertentu."""
        
        if bug_category == "reentrancy":
            return await self._collect_reentrancy_evidence(finding_id)
        elif bug_category == "oracle_manipulation":
            return await self._collect_oracle_evidence(finding_id)
        elif bug_category == "overflow":
            return await self._collect_overflow_evidence(finding_id)
        elif bug_category == "bridge":
            return await self._collect_bridge_evidence(finding_id)
        elif bug_category == "zero_day":
            return await self._collect_zeroday_evidence(finding_id)
        elif bug_category == "mev":
            return await self._collect_mev_evidence(finding_id)
        elif bug_category == "donation":
            return await self._collect_donation_evidence(finding_id)
        # ... sisanya pattern sama
        return {}
    
    async def _collect_reentrancy_evidence(self, finding_id: str) -> dict:
        """Kumpulkan bukti spesifik untuk reentrancy."""
        async with httpx.AsyncClient() as client:
            # Ambil call graph dari Service 08
            resp = await client.get(
                f"http://08-exploit:8006/exploit/{finding_id}/call-graph"
            )
            call_graph = resp.json() if resp.status_code == 200 else {}
            
            # Ambil detail state diff
            resp2 = await client.get(
                f"http://08-exploit:8006/exploit/{finding_id}/state-diff"
            )
            state_diff = resp2.json() if resp2.status_code == 200 else {}
            
        return {
            "call_graph": call_graph,
            "state_diff": state_diff,
            "call_depth": len(call_graph.get("levels", [])),
            "is_read_only": self._detect_readonly_reentrancy(call_graph),
            "is_cross_function": self._detect_cross_function(call_graph),
        }
    
    async def _collect_oracle_evidence(self, finding_id: str) -> dict:
        """Kumpulkan bukti spesifik untuk oracle manipulation."""
        async with httpx.AsyncClient() as client:
            # Hitung manipulation cost via MathEngine
            resp = await client.post(
                "http://08-exploit:8006/math/fixed-point",
                json={"finding_id": finding_id}
            )
            fp_result = resp.json() if resp.status_code == 200 else {}
            
            # Hitung AMM impact
            resp2 = await client.post(
                "http://08-exploit:8006/math/mev-calc",
                json={"finding_id": finding_id, "type": "oracle"}
            )
            mev_result = resp2.json() if resp2.status_code == 200 else {}
            
        return {
            "manipulation_cost": fp_result.get("manipulation_cost", 0),
            "profit": mev_result.get("extractable_value", 0),
            "twap_window": fp_result.get("twap_window", 0),
            "break_even_size": fp_result.get("break_even", 0),
            "oracle_type": fp_result.get("oracle_type", "unknown"),
            "pools_affected": mev_result.get("pools_affected", []),
        }
    
    async def _collect_overflow_evidence(self, finding_id: str) -> dict:
        """Kumpulkan bukti spesifik untuk integer overflow."""
        async with httpx.AsyncClient() as client:
            # Gunakan SAT solver
            resp = await client.post(
                "http://08-exploit:8006/math/sat-solve",
                json={"finding_id": finding_id, "type": "overflow"}
            )
            sat_result = resp.json() if resp.status_code == 200 else {}
            
        return {
            "exact_values": sat_result.get("solutions", []),
            "trigger_condition": sat_result.get("condition", ""),
            "variable": sat_result.get("variable", ""),
            "var_type": sat_result.get("variable_type", ""),
            "max_loss": sat_result.get("max_extractable", 0),
            "sat_proof": sat_result.get("proof", ""),
        }
    
    async def _collect_zeroday_evidence(self, finding_id: str) -> dict:
        """Kumpulkan bukti spesifik untuk zero-day / novel finding."""
        async with httpx.AsyncClient() as client:
            # Novelty check
            resp = await client.get(
                f"http://08-exploit:8006/exploit/{finding_id}/novelty"
            )
            novelty = resp.json() if resp.status_code == 200 else {}
            
        return {
            "novelty_points": novelty.get("unique_aspects", []),
            "prior_art": novelty.get("prior_art_search", "none"),
            "closest_prior_art": novelty.get("closest_match", None),
            "difference": novelty.get("difference_from_prior", ""),
            "search_sources": novelty.get("search_sources", []),
            "math_proof_available": novelty.get("has_math_proof", False),
        }
    
    async def _collect_mev_evidence(self, finding_id: str) -> dict:
        """Kumpulkan bukti spesifik untuk MEV."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://08-exploit:8006/math/mev-calc",
                json={"finding_id": finding_id, "type": "mev"}
            )
            mev = resp.json() if resp.status_code == 200 else {}
            
        return {
            "mev_score": mev.get("mev_score", 0.0),
            "sandwich_profit": mev.get("sandwich_profit", 0),
            "frontrun_probability": mev.get("probability", 0.0),
            "affected_users": mev.get("affected_users", 0),
            "user_loss_per_tx": mev.get("user_loss", 0),
            "priority_gas_required": mev.get("priority_gas", 0),
        }
    
    async def _get_source(self, finding_id: str) -> dict | None:
        """Ambil source code dari Service 03."""
        finding = await self.db.get_finding(finding_id)
        if finding and finding.contract_address and finding.chain:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"http://03-source:8002/source/"
                    f"{finding.chain}/{finding.contract_address}"
                )
                if resp.status_code == 200:
                    return resp.json()["data"]
        return None
    
    async def _get_scans(self, finding_id: str, bug_category: str = "other") -> list[dict]:
        """Ambil scan results dari Orchestrator — filter relevansi kategori."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"http://11-orchestrator:8009/findings/{finding_id}/scans"
            )
            if resp.status_code == 200:
                results = resp.json()["data"]
                # Filter scan results yang relevan untuk kategori ini
                # Misal: reentrancy → prioritaskan Slither reentrancy detector
                return self._filter_by_category(results, bug_category)
        return []
    
    async def _get_exploit(self, finding_id: str, bug_category: str = "other") -> dict | None:
        """Ambil exploit PoC dari Service 08 — dengan parameter kategori."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"http://08-exploit:8006/exploit/{finding_id}",
                params={"category": bug_category}  # Minta PoC spesifik kategori
            )
            if resp.status_code == 200:
                return resp.json()["data"]
        return None
    
    async def _get_math(self, finding_id: str, bug_category: str = "other") -> dict | None:
        """Ambil parameter MathEngine — spesifik kategori."""
        async with httpx.AsyncClient() as client:
            # Panggil endpoint math yang sesuai kategori
            math_endpoints = {
                "oracle_manipulation": "/math/fixed-point",
                "overflow": "/math/sat-solve",
                "mev": "/math/mev-calc",
                "reentrancy": "/math/sat-solve",  # untuk parameter exact
            }
            endpoint = math_endpoints.get(bug_category, "/math/status")
            resp = await client.get(f"http://08-exploit:8006{endpoint}")
            if resp.status_code == 200:
                return resp.json()["data"]
        return None
    
    async def _get_program(self, finding_id: str) -> dict | None:
        """Ambil info program dari Service 02."""
        finding = await self.db.get_finding(finding_id)
        if finding and finding.program_slug:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"http://02-immunefi:8001/programs/{finding.program_slug}"
                )
                if resp.status_code == 200:
                    return resp.json()["data"]
        return None
    
    def _filter_by_category(self, results: list, category: str) -> list:
        """Filter scan results berdasarkan relevansi kategori bug."""
        category_relevance = {
            "reentrancy": ["reentrancy", "callback", "external-call"],
            "oracle_manipulation": ["oracle", "price-feed", "twap"],
            "overflow": ["overflow", "arithmetic", "underflow"],
            "access_control": ["access-control", "authorization", "role"],
            "bridge": ["bridge", "cross-chain", "message-passing"],
        }
        relevant_checks = category_relevance.get(category, [])
        if not relevant_checks:
            return results
        return [r for r in results if any(
            c in r.get("check_name", "").lower() for c in relevant_checks
        )]
    
    def _detect_readonly_reentrancy(self, call_graph: dict) -> bool:
        """Deteksi apakah ini read-only reentrancy."""
        for level in call_graph.get("levels", []):
            if level.get("type") == "staticcall" and level.get("state_changing"):
                return True
        return False
    
    def _detect_cross_function(self, call_graph: dict) -> bool:
        """Deteksi cross-function reentrancy."""
        functions_called = set()
        for level in call_graph.get("levels", []):
            func = level.get("function_signature", "")
            if func in functions_called:
                return True
            functions_called.add(func)
        return False
```

---

## 6. Endpoint API

### Core Endpoints

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `POST` | `/submissions` | Buat submission baru dari finding |
| `GET` | `/submissions` | List semua submission |
| `GET` | `/submissions/{id}` | Detail submission + thread |
| `PUT` | `/submissions/{id}` | Update submission |
| `DELETE` | `/submissions/{id}` | Hapus submission |
| `POST` | `/submissions/{id}/send` | Kirim submission ke Immunefi |
| `POST` | `/submissions/{id}/respond` | Kirim jawaban ke Immunefi |
| `POST` | `/submissions/{id}/draft` | Generate draft jawaban |
| `GET` | `/submissions/{id}/evidence` | Kumpulkan semua bukti dari pipeline |
| `POST` | `/submissions/{id}/test-fix` | Test fix di Anvil fork |

### Webhook (dari Immunefi)

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `POST` | `/webhook/immunefi` | Terima pesan baru dari Immunefi |
| `GET` | `/webhook/health` | Health check untuk webhook |

### AI & Draft

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `POST` | `/ai/classify-intent` | Klasifikasi intent pesan Immunefi |
| `POST` | `/ai/generate-draft` | Generate draft jawaban |
| `POST` | `/ai/suggest-evidence` | Rekomendasi bukti tambahan |

### Stats & Tracking (Category-Aware)

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `GET` | `/stats` | Statistik submission + success rate (all categories) |
| `GET` | `/stats/categories` | Breakdown per kategori bug |
| `GET` | `/stats/categories/{category}` | Statistik spesifik satu kategori |
| `GET` | `/stats/response-time` | Rata-rata response time |
| `GET` | `/stats/response-time/{category}` | Response time per kategori bug |
| `GET` | `/stats/success-rate` | Persentase finding accepted |
| `GET` | `/stats/success-rate/{category}` | Success rate per kategori bug |
| `GET` | `/stats/common-intents` | Intent paling sering per kategori |

### Request & Response Models

```python
# src/models.py

# Enum kategori bug
class BugCategory(str, Enum):
    REENTRANCY = "reentrancy"
    ORACLE_MANIPULATION = "oracle_manipulation"
    FLASH_LOAN = "flash_loan"
    MEV = "mev"
    ACCESS_CONTROL = "access_control"
    OVERFLOW = "overflow"
    PRECISION_LOSS = "precision_loss"
    BRIDGE = "bridge"
    ZERO_DAY = "zero_day"
    GOVERNANCE = "governance"
    SIGNATURE_REPLAY = "signature_replay"
    STORAGE_COLLISION = "storage_collision"
    DONATION = "donation"
    OTHER = "other"


class CreateSubmissionRequest(BaseModel):
    """Buat submission baru — semua kategori bug."""
    finding_id: str
    program_slug: str
    bug_category: BugCategory = BugCategory.OTHER
    title: str
    description: str
    severity: Literal["critical", "high", "medium", "low"]
    poc_solidity: str
    tx_hash: str | None = None
    exploit_sequence: list[dict] = []
    category_evidence: dict = {}
    # Contoh category_evidence per BugCategory:
    # reentrancy:       {"call_graph": [], "call_depth": 3, "is_read_only": true}
    # oracle:           {"manipulation_cost": 120000, "profit": 2400000, "twap_window": 5}
    # flash_loan:       {"flash_loan_amount": 1e6, "net_profit": 500000}
    # mev:              {"mev_score": 0.87, "sandwich_profit": 500000}
    # overflow:         {"exact_values": ["57896044..."], "max_loss": 4200000}
    # precision_loss:   {"loss_per_tx": 0.001, "accumulated": 10000}
    # bridge:           {"source_chain": "eth", "dest_chain": "polygon"}
    # zero_day:         {"novelty_points": [], "prior_art": "none"}
    # governance:       {"proposal_id": 42, "required_votes": 1_000_000}
    # signature_replay: {"chain_ids": [1, 137], "same_v_r_s": true}
    # storage_collision:{"slot_mapping": {}, "collision_vars": []}
    # donation:         {"share_inflation": "12.5%", "donation_amount": 100}


class SubmitResponse(BaseModel):
    """Kirim jawaban ke Immunefi."""
    message: str
    attachments: list[str] = []


class DraftRequest(BaseModel):
    """Generate draft jawaban — category-aware."""
    immunefi_message: str
    bug_category: BugCategory | None = None  # Override jika perlu
    tone: Literal["professional", "detailed", "concise"] = "professional"


class DraftResponse(BaseModel):
    """Draft jawaban + rekomendasi — category-aware."""
    draft: str
    intent: str
    confidence: float
    bug_category: BugCategory
    suggested_evidence: list[str]
    category_specific_tips: list[str] = []
    alternative_drafts: list[str] = []


class IntentClassification(BaseModel):
    """Hasil klasifikasi intent — category-aware."""
    intent: str
    confidence: float
    bug_category: BugCategory | None
    category_specific_evidence: list[str]
    required_evidence: list[str]
    suggested_action: str
```

---

## 7. Contoh Skenario (Multi-Bug-Category)

### Skenario 1: Oracle Manipulation — Severity Dispute + MathEngine Proof

```
Bug: Oracle manipulation pada Uniswap V3 TWAP — kategori oracle_manipulation
Severity kamu: Critical
Immunefi: "We classify this as Medium severity. The manipulation 
           cost is too high to be practical."

                                      ↓
Service 16 → Intent: "severity_dispute" (confidence: 0.88)
             Bug category: oracle_manipulation
                                      ↓
Evidence Collector:
  • MathEngine hitung manipulation cost exact:
    - Manipulasi 5 block TWAP: $120,000
    - Profit dari 1 tx: $2.4M (20x ROI)
    - Break-even: $60,000 manipulation → profit $800K
  • Cari comparable oracle bugs di database:
    - Euler (2023): oracle manipulation, classified Critical, $8M loss
    - Mango Markets (2022): TWAP manipulation, classified Critical
  • Hitung affected TVL: $47M di 12 pools
                                      ↓
Draft Generator (category-aware template):
  "I respectfully disagree with the Medium classification.
   
   Per the MathEngine economic analysis:
   ┌──────────────────────────────────────────────┐
   │  Parameter                    Value           │
   ├──────────────────────────────────────────────┤
   │  TWAP window exploited       5 blocks        │
   │  Manipulation cost           $120,000        │
   │  Profit per tx               $2,400,000      │
   │  ROI                          20x            │
   │  Break-even manipulation      $60,000        │
   │  Affected TVL                $47,000,000     │
   │  Affected pools              12              │
   └──────────────────────────────────────────────┘
   
   The 20x ROI shows this IS economically viable.
   Per Immunefi's oracle manipulation severity guidelines:
   - Category 1 (Critical): ROI > 5x + TVL > $10M ← WE ARE HERE
   - Category 2 (High): ROI > 2x + TVL > $1M
   
   Additionally, comparable oracle manipulation findings:
   • Euler: $8M loss → Critical
   • Mango Markets: $47M → Critical
   • Compound: $89M → Critical
   
   I await your reconsideration."
                                      ↓
Kamu review → kirim → Immunefi setuju → upgrade ke Critical 🎉
```

### Skenario 2: Read-Only Reentrancy — Need More Evidence

```
Bug: Read-only reentrancy pada lending protocol — kategori reentrancy
Immunefi: "We need to see the exact call sequence. Can you 
           provide a step-by-step trace?"

                                      ↓
Service 16 → Intent: "request_evidence" (confidence: 0.95)
             Bug category: reentrancy
                                      ↓
Evidence Collector:
  • Ambil call graph dari Anvil trace:
    Level 0: flashLoan() → call to attacker contract
    Level 1:   └─ withdraw() → callback to pool
    Level 2:       └─ sync() → read oracle price (read-only)
    Level 3:           └─ getReserves() → manipulate view
  • State diff per call frame
  • Reentrancy guard check: ❌ NONE in affected functions
                                      ↓
Draft Generator (category-aware):
  "Thank you for the thorough review. Please find attached 
   the complete call trace:
   
   REENTRANCY CALL GRAPH (depth: 3)
   ─────────────────────────────────
   
   [TX] attacker.flashLoan(pool, 1_000_000 ETH)
     │
     ├─ [1] pool.flashLoan() → mints tokens
     │    │
     │    ├─ [2] pool._mint(attacker, 1_000_000)
     │    │    │
     │    │    └─ [2a] attacker.receiveFlashLoan()
     │    │         │
     │    │         ├─ [3] pool.withdraw(1_000_000)  ← REENTRANCY!
     │    │         │    │                              pool.state is INCONSISTENT
     │    │         │    │                              (tokens minted but not tracked)
     │    │         │    │
     │    │         │    └─ [4] pool.sync() → reads manipulated price
     │    │         │         │
     │    │         │         └─ [5] oracle.getReserves() → inflated
     │    │         │
     │    │         └─ [6] pool.withdraw(another_1_000_000) ← DOUBLE DRAIN
     │    │
     │    └─ [7] pool._burn(debt check) ← fails! but already drained
   
   State diff summary (attachment: state_diff.json):
   • Pool balance: -2,000,000 ETH
   • Attacker balance: +2,000,000 ETH
   • Debt tracked: only 1,000,000 ETH
   • Profit: 1,000,000 ETH ($2B at current price)
   
   This is a CRITICAL read-only reentrancy. The view function
   (sync/getReserves) creates the reentrancy opportunity because
   it reads state that changes during the callback.
   
   Full Anvil trace attached as anvil_trace.json."
                                      ↓
Kamu review → kirim → Immunefi accepts within 24h 🎉
```

### Skenario 3: Integer Overflow — SAT Solver Proof + Precision Argument

```
Bug: Integer overflow di uncovered _mint function — kategori overflow
Immunefi: "The overflow requires very specific values. 
           We consider this Low probability."

                                      ↓
Service 16 → Intent: "severity_dispute" (confidence: 0.82)
             Bug category: overflow
                                      ↓
Evidence Collector:
  • SAT solver (z3) menghasilkan exact values:
    - depositAmount = 57896044618658097711785492504343953926634992332820282019728792003956564819968
    - Trigger: depositAmount + totalSupply > max(uint256)
    - Result: totalSupply wraps to near-zero, attacker withdraws full pool
  • Hitung max extractable value: $4.2M
  • Probabilitas: 100% jika attacker punya $1 ETH (biaya gas)
                                      ↓
Draft Generator (category-aware):
  "I appreciate the probability concern, but I believe 
   the exploit is more practical than it seems.
   
   SAT SOLVER RESULTS
   ─────────────────
   The z3 solver found the exact trigger condition:
   
   `deposit(57896044618658097711785492504343953926634992332820282019728792003956564819968)`
   
   This value is NOT random — it's exactly:
   max_uint256 / 2 + 1 + current_totalSupply_offset
   
   The attacker only needs:
   1. ~1 ETH for gas (~$3,000)
   2. One transaction
   3. No special privileges
   
   Result: totalSupply wraps from near-max to near-zero
   Attacker can now withdraw the ENTIRE pool: ${max_loss:,.0f}
   
   Per Immunefi's overflow severity guidelines:
   'Any overflow that allows draining >10% of TVL is Critical'
   
   Additionally, this overflow bypasses the existing `onlyMintLimit` 
   check because the check uses `balanceOf[attacker]` not `totalSupply`.
   
   Full z3 proof and Foundry PoC attached."
                                      ↓
Kamu review → kirim → Immunefi reclassifies → Critical 🎉
```

### Skenario 4: Bridge Exploit — Novel Cross-Chain Attack

```
Bug: Bridge message relaying — kategori bridge
Immunefi: "This is out of scope. Our bridge contract 
           is not part of the bug bounty program."

                                      ↓
Service 16 → Intent: "out_of_scope" (confidence: 0.80)
             Bug category: bridge
                                      ↓
Evidence Collector:
  • Service 02: cek scope dokumen program
  • Ternyata bridge contract emang out of scope TAPI:
    - Bridge message diproses oleh in-scope contract (Vault)
    - Vault tidak validasi message origin
    - Impact: dana vault bisa ditarik via bridge message
  • Ambil source dari Service 03 untuk bukti koneksi
  • Cari precedent: similar findings accepted sebagai in-scope
                                      ↓
Draft Generator (category-aware):
  "I understand the bridge contract itself is out of scope.
   However, the vulnerability is in the VAULT contract (in-scope)
   which processes bridge messages without origin verification.
   
   ATTACK PATH
   ───────────
   [Source Chain]                  [Destination Chain]
   Attacker                        Vault (IN SCOPE)
   │                                │
   ├─ Submit message to bridge      │
   │  with arbitrary action         │
   │                                │
   │          ┌─────────────────────┤
   │          │ message relayed     │
   │          ▼                     ▼
   │      Bridge (out of scope) ──► Vault (IN SCOPE)
   │                                │
   │                         ┌──────┤
   │                         │ no origin check!
   │                         ▼      │
   │                     Vault.processMessage()
   │                     executes attacker's action
   │                     with bridge's privileges
   
   The vulnerability IS in an in-scope contract:
   - Vault.sol#L142: `processMessage()` does NOT check `msg.sender == bridge`
   - Any cross-chain message can impersonate the bridge
   - Impact: ${impact_amount:,.0f} at risk
   
   I've attached:
   1. Source code highlighting the missing check (vault/Vault.sol)
   2. Proof that bridge contract is manipulated (bridge/Bridge.sol)
   3. Previous accepted findings with similar scope-bridge pattern
   
   The scope exclusion of the bridge contract shouldn't shield 
   the vault's missing validation. I request reconsideration."
                                      ↓
Kamu review → kirim → Immunefi setuju in-scope → finding diterima 🎉
```

### Skenario 5: Donation Attack (Inflation Attack) — Fix Verification

```
Bug: Donation/inflation attack pada liquidity pool — kategori donation
Immunefi: "We've proposed a fix using virtual shares. 
           Can you verify?"

                                      ↓
Service 16 → Intent: "fix_question" (confidence: 0.91)
             Bug category: donation
                                      ↓
Evidence Collector:
  • Ambil fix dari fork repo
  • Deploy fixed contract di Anvil
  • Jalankan original exploit
  • Jalankan variasi: 
    - Donation dengan jumlah lebih besar (100x)
    - Donation bertahap (10 tx kecil)
    - Flash loan + donation kombinasikan
    - Donation + withdraw berulang
                                      ↓
Draft Generator (category-aware):
  "I have tested the proposed virtual shares fix.
   
   FIX VERIFICATION RESULTS
   ─────────────────────────────────────────────
   Original exploit:        ✅ SUCCESS (unfixed)
   Original exploit:        ❌ BLOCKED (fixed)  ← GOOD
   ─────────────────────────────────────────────
   Bypass attempts:
   - 100x larger donation:  ❌ BLOCKED
   - 10-step gradual:       ❌ BLOCKED
   - Flash loan + donate:   ❌ BLOCKED
   - Repeated donate/claim: ❌ BLOCKED (rounding in attacker's favor detected)
   ─────────────────────────────────────────────
   Gas impact:              +1,800 gas (+0.4%)
   
   PREVIOUS_ATTEMPT_VERIFICATION
   ─────────────────────────────
   Previous donation/Inflation attacks (same pattern):
   - Curve (2023): donation attack → $47M → Fixed with virtual shares ✅
   - Balancer (2022): inflation → $15M → Fixed with virtual shares ✅
   
   Your fix follows the same battle-tested pattern.
   One small concern: the virtual shares constant (1e18) 
   might be too low for pools with >1e18 TVL. 
   Recommend MINIMUM_LIQUIDITY = 1e18 * decimals_multiplier.
   
   Overall: Fix is effective ✅"
                                      ↓
Kamu review → kirim → Immunefi terima saran → 
Meningkatkan MINIMUM_LIQUIDITY → fix deployed 🎉
```

### Skenario 6: MEV / Sandwich — Accepted + Payout Tracking

```
Bug: Sandwich MEV pada swap function — kategori mev
Immunefi: "We've reviewed and accept this finding. 
           Payout will be processed within 30 days."

                                      ↓
Service 16 → Intent: "accepted" (confidence: 0.97)
             Bug category: mev
                                      ↓
Evidence Collector:
  • Track pembayaran: schedule reminder 30 hari
  • Catat accepted finding sebagai reference:
    - MEV score: 0.92
    - Sandwich profit: $1.2M/month estimated
    - Included in MEV dashboard for future submissions
                                      ↓
Draft Generator:
  "Thank you for accepting the finding! 🎉
   
   Finding Summary for Records:
   ┌──────────────────────────────────────────┐
   │  ID:           F-0042 (MEV-008)          │
   │  Category:     MEV / Sandwich            │
   │  Severity:     High                       │
   │  Bounty:       $50,000                    │
   │  Accepted:     {date}                     │
   │  Payout Due:   {date + 30 days}           │
   └──────────────────────────────────────────┘
   
   I confirm the payout timeline of 30 days.
   Please let me know if you need any additional 
   information for the payout process.
   
   I've added this finding to my MEV research database.
   This pattern (sandwich via minimizeOutputAmount) 
   affects {n_similar} similar functions in your codebase 
   that I can provide details on separately."
                                      ↓
Kamu → system → add reminder 30 hari → payout tracking aktif 🎉
```

---

## 8. Rencana Implementasi

### File Structure

```
services/16-submission/
├── app.py                          # FastAPI app + endpoints
├── Dockerfile
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── models.py                   # Pydantic models
│   ├── db.py                       # Database operations
│   ├── intent_classifier.py        # Klasifikasi intent pesan
│   ├── draft_generator.py          # Generate draft jawaban
│   ├── evidence_collector.py       # Kumpulkan bukti dari pipeline
│   ├── webhook_handler.py          # Terima webhook dari Immunefi
│   └── integrations.py            # Koneksi ke service lain
└── tests/
    ├── test_intent_classifier.py
    ├── test_draft_generator.py
    └── test_evidence_collector.py
```

### Dependency ke Service Lain

| Service | Port | Untuk |
|---------|------|-------|
| 02-Immunefi | 8001 | Program info, scope |
| 03-Source | 8002 | Source code |
| 06-AI | 8004 | Generate draft |
| 08-Exploit | 8006 | PoC, MathEngine |
| 10-Notifier | 800? | Notifikasi |
| 11-Orchestrator | 8009 | Scan results |
| 15-Dashboard | 8014 | UI untuk manage submission |

### Milestone

| Fase | Deliverable | SP |
|------|-------------|----|
| **Fase 1** | DB schema + CRUD submission + message (dengan `bug_category`) | 8 |
| **Fase 2** | Intent classifier (rule-based + AI) — category-aware | 13 |
| **Fase 3** | Draft generator (AI integration) — category-aware templates + fallback | 13 |
| **Fase 4** | Evidence collector (integrasi pipeline) — category-specific collectors | 21 |
| **Fase 5** | Webhook handler + notifikasi + intent routing per kategori | 8 |
| **Fase 6** | Endpoint lengkap + testing (termasuk per-category endpoints) | 13 |
| **Fase 7** | Dashboard integration (15) — submission view per kategori | 8 |
| **Fase 8** | Auto-submit + auto-respond mode (category-aware routing) | 21 |
| **Fase 9** | Post-acceptance: payout tracking + knowledge base per kategori | 13 |
| **Total** | | **~118 SP** (+13 untuk kategori expansion) |

---

> **Kesimpulan**: Service 16 ini mengubah pengalaman submit bug — **untuk semua kategori**:
> - **Sebelum**: Kamu send PoC (reentrancy/oracle/MEV/bridge/dll) → Immunefi tanya → kamu pusing jawab → finding rejected
> - **Sesudah**: Kamu send PoC → Immunefi tanya → Service 16 deteksi kategori bug + intent → kumpulkan evidence spesifik kategori → generate draft → finding accepted 🎉
>
> **13 kategori bug** didukung dengan evidence collector, argument template, dan severity calculator masing-masing.
>
> Ini adalah **AI co-pilot untuk bug bounty hunter** — bukan cuma menemukan bug (apa pun tipenya), tapi juga **memenangkan argumentasi** dengan tim keamanan proyek.
