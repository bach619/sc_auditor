# Agenda 29 — Quality Improvement: Roadmap B- → A-

> **Project**: sc_auditor (Vyper)
> **Status**: 🔴 OPEN
> **Severity**: CRITICAL
> **Labels**: `quality` `testing` `security` `performance` `roadmap`
> **Dependensi**: Agenda 27 (SQLite) ✅, Agenda 28 (Scanner Overpower) ✅
> **Sumber**: Comprehensive project review — 12-dimension quality assessment
> **Target**: 71/100 (B-) → 88/100 (A-) dalam 3 bulan

---

## Executive Summary

Project review 12-dimensi menemukan:
- ⭐ **Architecture 9.0** + **Documentation 9.5** = foundation kelas dunia
- ⚠️ **Testing 5.0** = critical gap (314 tests / 100,720 lines = 0.3%)
- ⚠️ **11 services restarting** = tidak bisa production
- ⚠️ **28 files > 500 lines** = technical debt

Roadmap 3 bulan untuk menutup semua gap.

---

## Roadmap

```
BULAN 1: FOUNDATIONS          Target: 75/100 (Grade B)
├── Fix 11 crashed services   → 28/28 Up
├── 50+ unit tests            → 25% coverage
└── CI coverage gate           → block merge if <25%

BULAN 2: HARDENING             Target: 82/100 (Grade B+)
├── Split 5 largest files     → 0 files > 500 lines
├── Security hardening        → rate limit + auth + audit
└── Observability upgrade      → structured logs + tracing

BULAN 3: OPTIMIZATION          Target: 88/100 (Grade A-)
├── Pipeline parallelization  → 6x faster
├── Response caching           → 10x re-scan
└── 200+ additional tests      → 70% coverage
```

---

## Dokumen

| # | Dokumen | Fokus | Timeline |
|---|---------|-------|:--------:|
| 1 | `doc_prioritas-1.md` | Fix crashed services + Testing + CI Gate + Integration Tests + Error Standardization + DRY Pattern | Bulan 1 |
| 2 | `doc_prioritas-2.md` | File splitting + Security + Observability + Circuit Breaker + Distributed Tracing + Alerting + Shared Volumes Removal + Backup Automation | Bulan 2 |
| 3 | `doc_prioritas-3.md` | Performance + Caching + Stress Tests + Production Deploy Guide + Disaster Recovery + Final Polish | Bulan 3 |

---

---

## Gap Coverage

Setelah review, **10 gap** yang sebelumnya terlewat sudah ditambahkan:

| # | Gap | Dimana | Prioritas |
|---|-----|--------|:--------:|
| A | Integration Tests (E2E cross-service) | doc-1 | 1 |
| B | Standardized Error Response Format | doc-1 | 1 |
| C | DRY — JSON pattern 109x → 1 utility | doc-1 | 1 |
| D | Circuit Breaker (anti cascade failure) | doc-2 | 2 |
| E | Distributed Tracing (OpenTelemetry) | doc-2 | 2 |
| F | Alerting Rules (proactive monitoring) | doc-2 | 2 |
| G | Shared Volumes Complete Removal | doc-2 | 2 |
| H | Backup/Restore Automation | doc-2 | 2 |
| I | Stress/Load Testing | doc-3 | 3 |
| J | Production Deployment Guide | doc-3 | 3 |
| K | Disaster Recovery Plan | doc-3 | 3 |

---

*Dibuat: 2026-06-04 | Agenda: 29*
