# Agenda 28 — Scanner Overpower: Cangkul → Excavator

> **Project**: sc_auditor (Vyper — Smart Contract Bug Hunter)
> **Status**: ✅ CLOSED
> **Severity**: CRITICAL
> **Labels**: `scanner` `overpower` `custom-detectors` `optimization` `differentiation`
> **Dependensi**: Agenda 27 (SQLite Storage) ✅
> **Target**: 3 bulan — dari tool standar ke scanner yang tidak dimiliki auditor lain

---

## Visi

> Semua auditor pakai cangkul dari pabrik yang sama. VYPER ubah cangkul jadi excavator.

Standard tools = `pip install slither-analyzer` → semua dapat yang sama.
VYPER tools = custom fork + enhancement yang tidak ada di tool manapun.

---

## Roadmap

```
BULAN 1: FOUNDATION (Quick Wins)
├── M1W1-2: Shared Compilation Cache + Smart Scan Router
│   Service: 03-source + 04-scanner
│   Impact: Pipeline 3-6x faster untuk semua kontrak
│
├── M1W3-4: Custom Slither Detectors
│   Service: 04a-scanner-slither
│   Impact: 2 detector baru (cross-contract taint, oracle deviation)
│
BULAN 2: DEEP ENHANCEMENT
├── M2W5-6: AI-Generated Invariants + Coverage-Guided Fuzz
│   Service: 04b-scanner-echidna
│   Impact: Otomatisasi invariant writing + 3x deeper fuzzing
│
├── M2W7-8: Multi-TX Attack Synthesis + Concrete-Symbolic Hybrid
│   Service: 05-scanner-mythril + 04e-scanner-manticore
│   Impact: Flash loan detection + 10x faster symbolic exec
│
BULAN 3: OVERKILL MODE
├── M3W9-10: Cross-Tool Consensus + Self-Improving Detector Factory
│   Service: 04-scanner + 14-agent (Antonio)
│   Impact: FP elimination + autonomous learning
│
├── M3W11-12: Economic Exploit Calculator + Mainnet State Import
│   Service: 08-exploit + 04b-echidna
│   Impact: "Bug ini profit $4.2M" dalam 1 klik
```

---

## Service Map

| Service | Enhancement | File |
|---------|------------|------|
| **03-source** | Shared Compilation Cache | `src/compilation_cache.py` |
| **04-scanner** | Smart Scan Router | `src/smart_router.py` |
| **04a-slither** | Cross-Contract Taint + Oracle Detector | `detectors/` |
| **04b-echidna** | AI Invariants + Coverage Fuzz | `src/ai_invariants.py` |
| **04e-manticore** | Concrete-Symbolic Hybrid | `src/hybrid_executor.py` |
| **05-mythril** | Multi-TX Attack Synthesis | `src/multi_tx.py` |
| **14-agent** | Detector Factory | `src/detector_factory.py` |

---

*Dibuat: 2026-06-04 | Agenda: 28*
