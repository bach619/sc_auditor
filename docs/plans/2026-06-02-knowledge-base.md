# Plan: Unified Knowledge Base + Integration Test

**Date:** 2026-06-02
**Status:** Draft — review sebelum eksekusi
**Agent:** lore-master

---

## Latar Belakang

Saat ini ada **dua learning system terpisah** yang tidak saling berbagi data:

| Aspek | Classifier (07) | Exploit (08) |
|-------|----------------|--------------|
| **File** | `src/improver.py` → `PatternLearner` | `src/learner.py` → `ExploitLearner` |
| **Belajar dari** | Human feedback, exploit confirmation | Attack pattern success rate |
| **Output** | Vulnerability patterns (TP/FP/FN) | Attack hypotheses + success stats |
| **Data** | `/data/classifier/patterns.json` | `/data/exploit/knowledge/` |
| **Digunakan oleh** | `Classifier.classify()` | `ExploitPlanner.create_plan()` |

**Masalah:** Dua knowledge base ini gak nyambung. Exploit yang berhasil gak otomatis ningkatin akurasi classifier. Feedback human gak bikin exploit planner lebih pintar.

---

## Solusi: Unified Knowledge Base

Bukan service baru. Cuma **shared volume + shared schema** yang diakses kedua service.

### Arsitektur

```
┌─────────────────────┐      ┌──────────────────────┐
│   Classifier (07)   │      │    Exploit (08)       │
│                     │      │                        │
│  PatternLearner ◄───┼──────┼──► ExploitLearner      │
│       │             │      │          │             │
│       ▼             │      │          ▼             │
│  /data/classifier/  │      │  /data/exploit/        │
│                     │      │                        │
└─────────┬───────────┘      └──────────┬─────────────┘
          │                             │
          ▼                             ▼
    ┌────────────────────────────────────────┐
    │         Shared Volume: vyper_kb        │
    │  /data/knowledge/                       │
    │                                        │
    │  ├── patterns.json     (dari classifier)│
    │  ├── attack_patterns.json (dari exploit)│
    │  ├── confirmed_tp.json  (dari exploit)  │
    │  └── feedback.json    (dari human)      │
    └────────────────────────────────────────┘
```

### Shared Volume

Docker volume baru: `vyper_kb` → mount di `/data/knowledge/`

Di **docker-compose.yml**:
```yaml
volumes:
  vyper_kb:

services:
  07-classifier:
    volumes:
      - vyper_kb:/data/knowledge

  08-exploit:
    volumes:
      - vyper_kb:/data/knowledge
```

### Shared Schema — File: `shared/knowledge_base/models.py`

File shared yang dipake kedua service:

```python
@dataclass
class ConfirmedFinding:
    """Finding yang terkonfirmasi (dari exploit atau human)."""
    finding_id: str
    audit_id: str
    contract_hash: str
    title: str
    severity: str
    attack_type: str
    confirmed_by: Literal["exploit", "human", "immunefi"]
    exploit_successful: bool | None  # None jika human feedback
    tx_hash: str | None
    vulnerability_pattern: dict  # ciri-ciri kontrak
    primitive_sequence: list[tuple[str, dict]]  # exploit steps
    confirmed_at: str
```

### Alur Data Baru

```
Exploit Berhasil
      │
      ├──► Classifier /confirm endpoint (SUDAH ADA)
      │       └──► PatternLearner.learn_from_exploit() (SUDAH ADA)
      │
      └──► Tulis ke /data/knowledge/confirmed_tp.json (BARU)
              ├── contract_hash
              ├── vulnerability_pattern
              └── primitive_sequence

Human Feedback
      │
      ├──► Classifier /feedback endpoint (SUDAH ADA)
      │       └──► PatternLearner.learn_from_feedback() (SUDAH ADA)
      │
      └──► Tulis ke /data/knowledge/feedback.json (BARU)

Exploit Planner
      │
      ├──► Baca /data/knowledge/confirmed_tp.json
      │       └──► Prioritaskan hypothesis yang cocok dengan pattern
      │
      └──► Baca /data/knowledge/feedback.json
              └──► Hindari attack type yang sering jadi FP

Classifier
      │
      ├──► Baca /data/knowledge/attack_patterns.json
      │       └──► Naikkan confidence untuk finding yang punya exploit match
      │
      └──► Baca /data/knowledge/confirmed_tp.json
              └──► Auto-classify sebagai TP kalo match contract_hash
```

---

## Task List

### Task 1: Shared Volume + Schema

| # | File | Perubahan |
|---|------|-----------|
| 1.1 | `shared/knowledge_base/__init__.py` | **CREATE** — empty init |
| 1.2 | `shared/knowledge_base/models.py` | **CREATE** — ConfirmedFinding, KnowledgeRecord dataclasses |
| 1.3 | `shared/knowledge_base/repository.py` | **CREATE** — KnowledgeRepository class (baca/tulis JSON) |
| 1.4 | `docker-compose.yml` | **MODIFY** — tambah volume `vyper_kb`, mount ke 07-classifier + 08-exploit |

### Task 2: Exploit → Knowledge Base

| # | File | Perubahan |
|---|------|-----------|
| 2.1 | `08-exploit/src/engine.py` | **MODIFY** — setelah exploit berhasil, panggil `KnowledgeRepository.save_confirmed()` |
| 2.2 | `08-exploit/src/planner.py` | **MODIFY** — `create_plan()` prioritaskan hypothesis yang match dengan confirmed patterns dari KB |

### Task 3: Classifier → Knowledge Base

| # | File | Perubahan |
|---|------|-----------|
| 3.1 | `07-classifier/app.py` | **MODIFY** — `/confirm` juga simpan ke KB |
| 3.2 | `07-classifier/app.py` | **MODIFY** — `/feedback` juga simpan ke KB |
| 3.3 | `07-classifier/src/classify.py` | **MODIFY** — `classify()` cek KB untuk auto-TP kalo contract_hash match |

### Task 4: Integration Test

| # | File | Perubahan |
|---|------|-----------|
| 4.1 | `tests/test_integration_pipeline.py` | **CREATE** — end-to-end: scan → classify → exploit → confirm → reclassify → report |
| 4.2 | `tests/conftest.py` | **MODIFY** — fixtures untuk mock services |

---

## Estimasi Dampak

| Metrik | Sebelum | Sesudah |
|--------|---------|---------|
| Akurasi classifier untuk finding yang sudah di-exploit | Sama aja (gak ada feedback) | **↑ 20-30%** (exploit result feed langsung) |
| Exploit planner hypothesis selection | Random berdasarkan heuristic | **Prioritized** berdasarkan pattern yang pernah berhasil |
| False positive rate | Tinggi (classifier gak tahu mana yang sudah di-test) | **Rendah** (exploit-confirmed = ground truth) |
| Jumlah service | 19 | **19 (TETAP)** |
| Shared volume | 0 | **1** (`vyper_kb`) |

---

## File yang Akan Diubah/Dibuat

Total: **8 files**

```
CREATE:  shared/knowledge_base/__init__.py
CREATE:  shared/knowledge_base/models.py
CREATE:  shared/knowledge_base/repository.py
CREATE:  tests/test_integration_pipeline.py
MODIFY:  docker-compose.yml
MODIFY:  08-exploit/src/engine.py
MODIFY:  08-exploit/src/planner.py
MODIFY:  07-classifier/app.py
MODIFY:  07-classifier/src/classify.py
MODIFY:  tests/conftest.py
```

**Tidak ada service yang dihapus atau digabung.** Cuma nambah shared volume + read/write pattern.

---

## Review

Setuju dengan plan ini? Ada yang mau diubah sebelum eksekusi?
