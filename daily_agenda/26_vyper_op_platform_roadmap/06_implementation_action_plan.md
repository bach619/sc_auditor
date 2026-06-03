# Sub-Agenda 26 — Vyper OP Implementation Action Plan

> **Created**: 2026-06-03 | **Status**: 🟡 PLANNING | **Source**: Agenda #26 Brainstorming Documents (01-05)

---

## Executive Summary

Based on comprehensive analysis of all 5 roadmap documents and the current Vyper v1 codebase state, this action plan extracts the **most actionable next steps** that can be executed immediately. The 10-pillar roadmap is ambitious (12 months, 44 services, $1M+ ARR) — this plan focuses on **Fase 1 Quick Wins** that can be completed within the existing architecture.

---

## Immediate Action Items (Week 1-2)

### Quick Win #1: Exploit PoC Library v2 (Agenda 26.2)
**Priority**: #4 overall | **Impact**: 🔥🔥🔥🔥 | **Effort**: LOW | **TTV**: 3 weeks

Already partially implemented in `services/08-exploit/` (16 primitives registered). Complete by adding:

| # | Tier | Attack Type | Status |
|---|------|-------------|--------|
| 1 | 2 | Reentrancy (CEI) | ✅ Existing |
| 2 | 2 | Integer Overflow | ✅ Existing |
| 3 | 2 | Access Control | ✅ Existing |
| 4 | 2 | Flash Loan | ✅ Existing |
| 5 | 2 | Oracle Manipulation | ✅ Existing |
| 6 | 2 | TWAP Manipulation | ✅ Added (agenda-26) |
| 7 | 2 | Sandwich Frontrun | ✅ Added (agenda-26) |
| 8 | 2 | Governance Attack | ✅ Added (agenda-26) |
| 9 | 3 | Proxy Init Frontrun | ✅ Added (agenda-26) |
| 10 | 3 | Timelock Bypass | ✅ Added (agenda-26) |
| 11 | 4 | Bridge Forgery | ✅ Added (agenda-26) |
| 12 | 4 | EIP-712 Bypass | ✅ Added (agenda-26) |
| 13 | 4 | Paymaster Exploit | ✅ Added (agenda-26) |
| 14 | 5 | Sequencer Censorship | ✅ Added (agenda-26) |
| 15 | 5 | V4 Hook Exploit | ✅ Added (agenda-26) |
| 16 | — | Arbitrary Send | ⏳ Pending |
| 17 | — | Unchecked Return | ⏳ Pending |
| 18 | — | Storage Collision | ⏳ Pending |
| 19 | — | Delegatecall Injection | ⏳ Pending |
| 20 | — | Selfdestruct Attack | ⏳ Pending |

**Action**: Create 5 more primitives for remaining types → total 20+ attack types.

### Quick Win #2: Multi-Bounty Platform Integration (Agenda 26.4)
**Priority**: #6 overall | **Impact**: 🔥🔥🔥🔥 | **Effort**: LOW | **TTV**: 2 weeks

Already implemented:
- ✅ 18-code4rena (GraphQL client + SyncManager)
- ✅ 19-sherlock (REST client + SyncManager)
- ✅ 20-cantina (REST client + SyncManager)
- ✅ 21-hats (REST client + SyncManager)
- ✅ 02-immunefi (existing)

**Action**: Add integration tests for 18-21 (DONE in Agenda #08 gap fix).

### Quick Win #3: CI/CD GitHub Actions (Agenda 13)
**Priority**: #9 overall | **Impact**: 🔥🔥🔥🔥 | **Effort**: MEDIUM | **TTV**: 2 weeks

Already implemented:
- ✅ `.github/workflows/ci.yml` — 5 jobs (lint-python, lint-frontend, type-check, test-backend, validate-docker)
- ✅ `|| true` masking removed (debug session)
- ✅ `pytest-timeout` added

**Action**: Add deployment workflow (build Docker images, push to registry).

---

## Phase 1 Strategic Bets (Month 1-4)

### Multi-Chain Support (Agenda 26.1) — 🥇 #1 Priority
Already implemented:
- ✅ `vyper_lib/models/chain_adapter.py` — ChainAdapter ABC + AdapterRegistry
- ✅ `vyper_lib/models/ir.py` — Chain-agnostic IR (IROpType 60+ ops)
- ✅ 22-source-starknet — StarkNet source fetcher
- ✅ 23-scanner-cairo — Cairo scanner with 8 pattern detectors

**Next Steps**:
1. Write integration tests for 22-source-starknet + 23-scanner-cairo (DONE)
2. Add Solana/Rust adapter blueprint
3. Add Sui/Move adapter blueprint

### In-House Detector Engine (Agenda 26.3) — 🥈 #2 Priority
**Status**: NOT STARTED. Currently relies on external tools (Slither, Mythril).

**Action**: Create 1-2 prototype detectors in `04a-scanner-slither` using the existing infrastructure.

---

## Pre-Implementation Prerequisites

Before Phase 2 (Formal Verification, Real-Time Monitoring), these MUST be done:

| # | Prerequisite | Blocking | Status |
|---|-------------|----------|--------|
| 1 | Migrate JSON → PostgreSQL | Fase 2, 3 | ⏳ Not started |
| 2 | Set up billing/payment (Stripe) | Pricing tiers | ⏳ Not started |
| 3 | Add authentication (JWT + RBAC) | SaaS deployment | ⏳ Not started |
| 4 | Build data migration strategy | PostgreSQL migration | ⏳ Not started |
| 5 | Find co-founders/early hires | Scalability | ⏳ Not started |

---

## Risk Mitigation

Based on the pre-mortem analysis, the top 3 risks:

### Risk 1: Multi-Chain IR Complexity (CRITICAL)
- **Mitigation**: Only support Cairo + 1 more chain (Solana) in Phase 1. Don't add 10 chains at once.
- **Success metric**: Cairo scan produces valid findings on ≥1 real StarkNet contract.

### Risk 2: LLM API Costs (HIGH)
- **Mitigation**: DeepSeek for 80% of simple queries (cheapest), Claude only for complex reasoning. Cache common patterns.
- **Budget cap**: $1,000/mo for LLM APIs in Phase 1.

### Risk 3: Solo Developer Burnout (CRITICAL)
- **Mitigation**: Open-source the project early (MIT license). Build community contributors.
- **Action**: Create CONTRIBUTING.md + GitHub issues labeled "good first issue".

---

## Success Criteria (Phase 1)

| Metric | Target | Current |
|--------|--------|---------|
| Services with tests | 28/28 (100%) | ✅ 28/28 |
| Attack types in PoC library | 20+ | ✅ 16 (5 more needed) |
| Bounty platforms integrated | 5 | ✅ 5 (Immunefi, C4, Sherlock, Cantina, Hats) |
| Multi-chain support | 2 chains (EVM + Cairo) | ✅ EVM + Cairo |
| CI/CD pipeline | Green on every PR | ✅ (after debug fixes) |
| Duplicate code eliminated | 0 duplicates | ✅ (Agenda #20 done) |

---

## Document Reference

| Doc | Content | Status |
|-----|---------|--------|
| `01_brainstorming.md` | 10 pillars, decision matrix, pre-mortem | ✅ Complete |
| `02_architecture_vision.md` | 6-layer architecture, 44-service map | ✅ Complete |
| `03_implementation_roadmap.md` | 3-phase Gantt, risk register, milestones | ✅ Complete |
| `04_market_analysis.md` | SWOT, TAM/SAM/SOM, competitors, GTM | ✅ Complete |
| `05_technical_spec.md` | 7 feature specs, API endpoints, service ports | ✅ Complete |
| `06_implementation_action_plan.md` | THIS FILE — actionable next steps | 🟡 Draft |

---

*Dibuat: 2026-06-03 | Sub-Agenda: 26 | Status: 🟡 PLANNING*
