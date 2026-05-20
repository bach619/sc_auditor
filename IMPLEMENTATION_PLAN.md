# VYPER Implementation Plan — Opencode 5-Phase Build

> **Acuan**: VYPER.md (arsitektur), AGENTS.md (opencode rules)
> **Target**: 12 microservice smart contract bug hunter via Docker Compose
> **Filosofi**: Bite-sized tasks (2-5 min), TDD-style, quality gate per fase

---

## Fase 1 — Foundation (8 tasks, ~40 min)

**Goal**: Infrastructure + Config + Immunefi + Source services

| Task | Service | Files | Output |
|------|---------|-------|--------|
| T1 | infrastructure | `docker-compose.yml`, `Dockerfile.base`, `.env.example` | Docker skeleton |
| T2 | infrastructure | `services/*/Dockerfile` | 12 Dockerfiles |
| T3 | Config | `services/01-config/app.py`, `src/manager.py`, `models.py` | Config CRUD API |
| T4 | Config | `services/01-config/requirements.txt` | Dependencies |
| T5 | Immunefi | `services/02-immunefi/app.py`, `src/scraper.py`, `src/sync.py` | Sync Immunefi data |
| T6 | Immunefi | `services/02-immunefi/src/repo_detector.py`, `models.py` | GitHub repo detection |
| T7 | Source | `services/03-source/app.py`, `src/detector.py` | Multi-source fetch skeleton |
| T8 | Source | `services/03-source/src/providers/*.py` | 5 providers |

### Dependency Graph
```
Dockerfile.base → docker-compose.yml
Config → Immunefi → Source → ...
All services → Dockerfile (copy from pattern)
```

---

## Fase 2 — Core Pipeline (10 tasks, ~60 min)

**Goal**: Scanner + AI + Classifier + Orchestrator services

| Task | Service | Key Files | Output |
|------|---------|-----------|--------|
| T9 | Scanner | `app.py`, `src/slither.py`, `src/mythril.py`, `src/echidna.py` | 3 scanner tools |
| T10 | Scanner | `src/forge.py`, `src/solc_manager.py`, `src/deps.py` | Dependency solver |
| T11 | Scanner | `src/slither_config.py` | Slither tuning |
| T12 | AI | `app.py`, `src/llm.py`, `src/analyzer.py` | LLM analysis |
| T13 | AI | `src/fixer.py` | AI fix suggestion |
| T14 | Classifier | `app.py`, `src/classify.py`, `src/metrics.py` | TP/FP classification |
| T15 | Classifier | `src/improver.py` | Pattern learning |
| T16 | Orchestrator | `app.py`, `src/pipeline.py` | State machine |
| T17 | Orchestrator | `src/priority.py`, `src/similarity.py` | Priority + similarity |
| T18 | Orchestrator | `src/batch.py`, `src/daemon.py` | Batch + daemon |

---

## Fase 3 — Value (8 tasks, ~40 min)

**Goal**: Exploit + Reporter + Notifier + Dashboard services

| Task | Service | Key Files | Output |
|------|---------|-----------|--------|
| T19 | Exploit | `app.py`, `src/engine.py`, `src/anvil.py` | Anvil engine |
| T20 | Exploit | `src/executor.py`, `src/poc_generator.py` | PoC generation |
| T21 | Reporter | `app.py`, `src/immunefi.py`, `src/full.py` | Report generation |
| T22 | Reporter | `src/templates/*` | Jinja2 templates |
| T23 | Notifier | `app.py`, `src/discord.py`, `src/telegram.py` | Notifications |
| T24 | Dashboard | `app.py`, `templates/` | UI pages |
| T25 | Dashboard | SSE + daemon control | Live updates |
| T26 | Dashboard | Feedback + submission tracker | User interaction |

---

## Fase 4 — Autonomous (6 tasks, ~30 min)

**Goal**: Webhook + Upkeep + Integration + Polish

| Task | Service | Key Files | Output |
|------|---------|-----------|--------|
| T27 | Webhook | `app.py`, `src/dispatcher.py` | Webhook delivery |
| T28 | Upkeep | `app.py`, `src/update.py` | Self-update |
| T29 | Upkeep | `src/backup.py`, `src/metrics.py` | Backup + metrics |
| T30 | Integration | `tests/test_pipeline.py` | End-to-end test |
| T31 | Integration | `tests/test_services.py` | Service integration |
| T32 | Polish | CLI completion, rate limiter | Final polish |

---

## Dispatch Strategy

```
FASE 1: Sequential (dependencies)
  T1 → T2 → T3+T4 (parallel) → T5+T6 (parallel) → T7+T8 (parallel)

FASE 2: Sequential (pipeline order)
  T9+T10+T11 (parallel) → T12+T13 (parallel) → T14+T15 (parallel) → T16+T17+T18 (parallel)

FASE 3: Sequential + Parallel
  T19+T20 (parallel) → T21+T22 (parallel) → T23 → T24+T25+T26 (parallel)

FASE 4: Mostly Parallel
  T27 → T28+T29 (parallel) → T30+T31 (parallel) → T32
```

## Quality Gate

Setelah SETIAP fase → dispatch @code-reviewer untuk 6-dimension scoring.
Score < 80 di dimensi mana pun → fix sebelum lanjut fase berikutnya.

---

## Immunefi Enhancement Plan (daily_agenda 01)

Untuk implementasi detail enhancement Service 02 (Immunefi Bug Bounty Intelligence),
lihat dokumen terpisah:

📄 **`daily_agenda/01_IMPLEMENTATION_PLAN.md`**

Meliputi:
- **Phase 1** — Enhanced JSON Storage (5 tasks, ~30 min)
- **Phase 2** — Multi-Source Providers (4 tasks, ~25 min)
- **Phase 3** — Automated Sync Engine (4 tasks, ~20 min)
- **Phase 4** — Intelligence Layer (5 tasks, ~35 min)
- **Phase 5** — Cross-Service Integration (3 tasks, ~15 min)
- **Phase 6** — Repository Forking (4 tasks, ~25 min)
- **Total**: 25 tasks, ~146 menit kerja efektif
