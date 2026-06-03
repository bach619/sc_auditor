# Architecture Vision: Vyper OP — Web3 Security Dominator

> **Dokumen**: Visi arsitektur Vyper versi OP (Overpowered)
> **Sumber**: Brainstorming Antonio + Ekspansi (lihat `01_brainstorming.md`)
> **Target**: 12 bulan, 3 fase

---

## Daftar Isi

1. [High-Level Architecture](#1-high-level-architecture)
2. [Service Architecture (Vyper v2 → v4)](#2-service-architecture)
3. [Multi-Chain Abstraction Layer](#3-multi-chain-abstraction-layer)
4. [Data Architecture](#4-data-architecture)
5. [Integration Architecture](#5-integration-architecture)
6. [Security Architecture](#6-security-architecture)
7. [Deployment Architecture](#7-deployment-architecture)

---

## 1. High-Level Architecture

### Vyper v1 (Current) → Vyper v4 (OP Target)

```
┌───────────────────────────────────────────────────────────────────────┐
│                    VYPER v4 — WEB3 SECURITY DOMINATOR                    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    INTERFACE LAYER                                │   │
│  │                                                                  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────────┐   │   │
│  │  │ Antonio  │ │ CLI Tool │ │ VSCode    │ │ Dashboard (Web)  │   │   │
│  │  │ AI Agent │ │ vyper    │ │ Extension │ │                  │   │   │
│  │  └──────────┘ └──────────┘ └───────────┘ └──────────────────┘   │   │
│  │                                                                  │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │              API Gateway (Unified)                        │   │   │
│  │  │  • REST + WebSocket + gRPC                                │   │   │
│  │  │  • Rate limiting, Auth (API Key + JWT), Versioning       │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│                                    ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    ORCHESTRATION LAYER                            │   │
│  │                                                                  │   │
│  │  ┌──────────────────────┐  ┌──────────────────────┐             │   │
│  │  │ Workflow Orchestrator│  │ Event Bus (NATS/Kafka)│             │   │
│  │  │ (State Machine)      │  │ Cross-service comm    │             │   │
│  │  └──────────────────────┘  └──────────────────────┘             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│                                    ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    CORE ENGINE LAYER                              │   │
│  │                                                                  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │   │
│  │  │ Multi-   │ │ Analysis │ │ Exploit  │ │ AI Reasoning     │   │   │
│  │  │ Chain    │─▶│ Engine   │─▶│ Engine   │─▶│ Engine           │   │   │
│  │  │ Adapter  │ │ (Hybrid) │ │ (Fork)   │ │ (LLM + Logic)    │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │   │
│  │                                                                  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │   │
│  │  │ Formal   │ │ Real-Time│ │ Auto-Fix │ │ Report           │   │   │
│  │  │ Verifier │ │ Monitor  │ │ Generator│ │ Generator        │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│                                    ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    DATA & INTELLIGENCE LAYER                      │   │
│  │                                                                  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │   │
│  │  │ PostgreSQL│ │ Vector DB│ │ Knowledge│ │ Experience       │   │   │
│  │  │ (Primary) │ │ (Qdrant) │ │ Graph    │ │ Store (SQLite)   │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│                                    ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    EXTERNAL INTEGRATIONS                          │   │
│  │                                                                  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │   │
│  │  │ Immunefi │ │ Code4rena│ │ Sherlock │ │ GitHub/GitLab    │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │   │
│  │                                                                  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │   │
│  │  │ Etherscan│ │ Alchemy  │ │ Anvil    │ │ Chain RPC Nodes  │   │   │
│  │  │ (Source) │ │ (Mempool)│ │ (Fork)   │ │ (Multi-chain)    │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 2. Service Architecture (Vyper v2 → v4)

### Service Map: 20 → 30+ Services

```
┌─────────────────────────────────────────────────────────────────┐
│              VYPER v4 SERVICE ARCHITECTURE                       │
│                                                                 │
│  LAYER 1: INTERFACE (5 services)                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 14-agent (Antonio)     — AI Agent Controller              │  │
│  │ 15-dashboard           — Web Dashboard (React)            │  │
│  │ 18-cli                 — Vyper CLI Tool [NEW]             │  │
│  │ 19-vscode              — VSCode Extension Backend [NEW]   │  │
│  │ 20-api-gateway         — Unified API Gateway [NEW]        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  LAYER 2: BOUNTY INGESTION (5 services)                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 02-immunefi            — Immunefi integration (existing)  │  │
│  │ 21-code4rena           — Code4rena integration [NEW]      │  │
│  │ 22-sherlock            — Sherlock integration [NEW]       │  │
│  │ 23-cantina             — Cantina integration [NEW]        │  │
│  │ 24-hats                — Hats Finance integration [NEW]   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  LAYER 3: SOURCE ACQUISITION (3 services)                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 03-source              — EVM source fetcher (existing)    │  │
│  │ 25-source-starknet     — StarkNet/Cairo source [NEW]      │  │
│  │ 26-source-solana       — Solana/Rust source [NEW]         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  LAYER 4: ANALYSIS ENGINE (10 services)                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 04-scanner             — Scanner router (existing)        │  │
│  │ 04a-scanner-slither    — Slither (existing)               │  │
│  │ 04b-scanner-echidna    — Echidna (existing)               │  │
│  │ 04c-scanner-forge      — Forge (existing)                 │  │
│  │ 04d-scanner-halmos     — Halmos (existing)                │  │
│  │ 04e-scanner-manticore  — Manticore (existing)             │  │
│  │ 05-scanner-mythril     — Mythril (existing)               │  │
│  │ 27-scanner-cairo       — Cairo analyzer [NEW]             │  │
│  │ 28-scanner-move        — Move Prover [NEW]                │  │
│  │ 29-formal-verifier     — SMT-based Verifier [NEW]         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  LAYER 5: INTELLIGENCE (5 services)                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 06-ai                  — LLM Analysis (existing)          │  │
│  │ 07-classifier          — TP/FP classifier (existing)     │  │
│  │ 30-reasoning-engine    — AI Reasoning Engine [NEW]        │  │
│  │ 31-threat-intel        — Threat Intelligence Feed [NEW]   │  │
│  │ 32-auto-fix            — Auto-Fix Generator [NEW]         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  LAYER 6: EXPLOIT & VALIDATION (3 services)                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 08-exploit             — PoC Generator (existing)         │  │
│  │ 33-anvil-farm          — Anvil Fork Farm [NEW]            │  │
│  │ 34-simulation-engine   — Multi-chain sim engine [NEW]     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  LAYER 7: OUTPUT & DELIVERY (4 services)                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 09-reporter            — Report generator (existing)      │  │
│  │ 10-notifier            — Notification (existing)          │  │
│  │ 16-submission          — Bounty submission (existing)     │  │
│  │ 35-github-integration  — GitHub PR/Comment [NEW]          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  LAYER 8: MONITORING (3 services)                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 36-mempool-watcher     — Mempool monitor [NEW]            │  │
│  │ 37-contract-watcher    — Contract state monitor [NEW]     │  │
│  │ 38-alert-engine        — Alert & escalation [NEW]         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  LAYER 9: PLATFORM (4 services)                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 01-config              — Configuration (existing)         │  │
│  │ 11-orchestrator        — Pipeline coordinator (existing)  │  │
│  │ 13-upkeep              — Maintenance (existing)           │  │
│  │ 17-experience          — Experience/KB (existing)         │  │
│  │ 39-community           — Community platform [NEW]         │  │
│  │ 40-analytics           — Analytics & metrics [NEW]        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Service Communication Matrix

```
                ┌──────────┬──────┬──────┬──────┬──────┬──────┐
                │ REST API │ gRPC │ WS   │ NATS │ Redis│ File │
┌───────────────┼──────────┼──────┼──────┼──────┼──────┼──────┤
│ Interface→Core│    ✅    │  ✅  │  ✅  │  ❌  │  ❌  │  ❌  │
│ Core Internal │    ✅    │  ✅  │  ❌  │  ✅  │  ✅  │  ❌  │
│ Core→Data     │    ✅    │  ✅  │  ❌  │  ❌  │  ✅  │  ✅  │
│ Monitoring    │    ❌    │  ❌  │  ✅  │  ✅  │  ✅  │  ❌  │
│ External API  │    ✅    │  ❌  │  ✅  │  ❌  │  ❌  │  ❌  │
└───────────────┴──────────┴──────┴──────┴──────┴──────┴──────┘
```

---

## 3. Multi-Chain Abstraction Layer

### Design: Chain-Agnostic Intermediate Representation (IR)

```
┌─────────────────────────────────────────────────────────────────┐
│              MULTI-CHAIN IR ARCHITECTURE                          │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   CHAIN ADAPTERS                           │  │
│  │                                                           │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │  │
│  │  │ EVM      │ │ Cairo    │ │ Move     │ │ Rust     │    │  │
│  │  │ Adapter  │ │ Adapter  │ │ Adapter  │ │ Adapter  │    │  │
│  │  │          │ │          │ │          │ │          │    │  │
│  │  │ Solidity │ │ .cairo   │ │ .move    │ │ .rs      │    │  │
│  │  │ .yul     │ │ StarkNet │ │ Sui/Aptos│ │ Solana   │    │  │
│  │  │ EVM byte │ │ CairoVM  │ │ MoveVM   │ │ BPF/SVM  │    │  │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘    │  │
│  │       │            │            │            │           │  │
│  └───────┼────────────┼────────────┼────────────┼───────────┘  │
│          │            │            │            │               │
│          └────────────┴────────────┴────────────┘               │
│                            │                                     │
│                            ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            UNIFIED INTERMEDIATE REPRESENTATION             │  │
│  │                                                            │  │
│  │  ┌──────────────────────────────────────────────────────┐ │  │
│  │  │ Control Flow Graph (CFG)                              │ │  │
│  │  │ • Basic blocks                                        │ │  │
│  │  │ • Branch conditions                                   │ │  │
│  │  │ • Loop structures                                     │ │  │
│  │  └──────────────────────────────────────────────────────┘ │  │
│  │                                                            │  │
│  │  ┌──────────────────────────────────────────────────────┐ │  │
│  │  │ Data Flow Graph (DFG)                                 │ │  │
│  │  │ • Variable definitions & uses                         │ │  │
│  │  │ • Storage/memory access patterns                      │ │  │
│  │  │ • Cross-contract data flow                            │ │  │
│  │  └──────────────────────────────────────────────────────┘ │  │
│  │                                                            │  │
│  │  ┌──────────────────────────────────────────────────────┐ │  │
│  │  │ Call Graph                                            │ │  │
│  │  │ • Internal function calls                             │ │  │
│  │  │ • External contract calls                             │ │  │
│  │  │ • Delegate/proxy relationships                        │ │  │
│  │  └──────────────────────────────────────────────────────┘ │  │
│  │                                                            │  │
│  │  ┌──────────────────────────────────────────────────────┐ │  │
│  │  │ Semantic Model                                        │ │  │
│  │  │ • Token operations (transfer, mint, burn)             │ │  │
│  │  │ • AMM operations (swap, add/remove liquidity)         │ │  │
│  │  │ • Lending operations (deposit, borrow, liquidate)     │ │  │
│  │  │ • Governance operations (propose, vote, execute)      │ │  │
│  │  └──────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                     │
│                            ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            UNIFIED ANALYSIS ENGINE                        │  │
│  │                                                            │  │
│  │  • Pattern-based detectors (chain-agnostic)               │  │
│  │  • Data flow analysis (chain-agnostic)                    │  │
│  │  • Symbolic execution (chain-agnostic, custom VM per IR)  │  │
│  │  • Formal verification (SMT on IR)                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### IR Specification (Simplified)

```python
# vyper_lib/models/ir.py (NEW)

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set

class IROpCode(str, Enum):
    """Chain-agnostic IR operations"""
    # Storage
    SLOAD = "sload"
    SSTORE = "sstore"
    # Memory
    MLOAD = "mload"
    MSTORE = "mstore"
    # Control flow
    JUMP = "jump"
    JUMPI = "jumpi"
    CALL = "call"
    DELEGATECALL = "delegatecall"
    STATICCALL = "staticcall"
    RETURN = "return"
    REVERT = "revert"
    # Arithmetic
    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"
    # Comparison
    LT = "lt"
    GT = "gt"
    EQ = "eq"
    # Token operations (semantic)
    TRANSFER = "transfer"
    MINT = "mint"
    BURN = "burn"
    APPROVE = "approve"
    # DeFi operations (semantic)
    SWAP = "swap"
    ADD_LIQUIDITY = "add_liquidity"
    REMOVE_LIQUIDITY = "remove_liquidity"
    DEPOSIT = "deposit"
    BORROW = "borrow"
    REPAY = "repay"
    LIQUIDATE = "liquidate"

@dataclass
class IRInstruction:
    opcode: IROpCode
    operands: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

@dataclass
class IRBasicBlock:
    id: str
    instructions: List[IRInstruction]
    predecessors: Set[str] = field(default_factory=set)
    successors: Set[str] = field(default_factory=set)

@dataclass
class IRContract:
    name: str
    chain: str
    language: str
    address: Optional[str]
    functions: Dict[str, List[IRBasicBlock]]
    storage_layout: Dict[str, str]  # slot → variable name
    external_calls: List[str]  # target contracts
    semantic_model: Dict  # protocol-specific semantic model
```

---

## 4. Data Architecture

### Storage Evolution: JSON → PostgreSQL + ClickHouse + Qdrant

```
┌─────────────────────────────────────────────────────────────────┐
│              DATA ARCHITECTURE                                    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              POSTGRESQL (Primary Store)                    │  │
│  │                                                           │  │
│  │  Tables:                                                  │  │
│  │  • audits (id, program_id, status, timestamps)            │  │
│  │  • findings (id, audit_id, severity, confidence, type)    │  │
│  │  • contracts (id, address, chain, source, abi)            │  │
│  │  • programs (id, platform, title, max_bounty, status)     │  │
│  │  • users (id, tier, api_key, created_at)                  │  │
│  │  • submissions (id, finding_id, platform, bounty_usd)     │  │
│  │  • detectors (id, name, type, author, version)            │  │
│  │  • community (id, user_id, reputation, badges)            │  │
│  │                                                           │  │
│  │  Indexes:                                                 │  │
│  │  • findings(audit_id), findings(severity), audits(status) │  │
│  │  • contracts(address, chain), programs(platform)          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              CLICKHOUSE (Analytics & Time-Series)          │  │
│  │                                                           │  │
│  │  Tables:                                                  │  │
│  │  • audit_events (timestamp, service, event_type, data)    │  │
│  │  • monitoring_events (timestamp, contract, tx_hash, ...)  │  │
│  │  • performance_metrics (timestamp, service, metric, val)  │  │
│  │  • user_actions (timestamp, user_id, action, data)        │  │
│  │                                                           │  │
│  │  Use cases:                                               │  │
│  │  • Real-time dashboards                                   │  │
│  │  • Usage analytics                                        │  │
│  │  • Billing/usage tracking                                 │  │
│  │  • Threat intelligence aggregation                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              QDRANT (Vector Store)                         │  │
│  │                                                           │  │
│  │  Collections:                                             │  │
│  │  • finding_embeddings (512-dim)                           │  │
│  │  • contract_embeddings (512-dim)                          │  │
│  │  • exploit_embeddings (512-dim)                           │  │
│  │  • detector_embeddings (512-dim)                          │  │
│  │                                                           │  │
│  │  Use cases:                                               │  │
│  │  • "Bug ini mirip dengan CASE-012"                        │  │
│  │  • Pattern recognition untuk novel vulnerabilities       │  │
│  │  • Similarity search untuk threat intelligence            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              REDIS (Cache & Pub/Sub)                       │  │
│  │                                                           │  │
│  │  Use cases:                                               │  │
│  │  • Audit result caching                                   │  │
│  │  • Rate limiting                                          │  │
│  │  • Real-time alert pub/sub                                │  │
│  │  • Job queue for async audit tasks                        │  │
│  │  • Mempool event stream buffer                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              FILE STORAGE (Legacy → Deprecated)            │  │
│  │                                                           │  │
│  │  ~/.vyper/                                                │  │
│  │  ├── reports/       (still file-based, .md/.pdf)          │  │
│  │  ├── exploits/      (PoC scripts)                         │  │
│  │  ├── sources/       (cached contract sources)             │  │
│  │  └── backups/       (database dumps)                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Migration Strategy: JSON → PostgreSQL

```
Phase 1: Dual-write (week 1-2)
  • Semua write ke JSON + PostgreSQL
  • Read dari JSON dulu (PostgreSQL sebagai backup)

Phase 2: PostgreSQL read-primary (week 3-4)
  • Read dari PostgreSQL, JSON sebagai fallback
  • Background sync JSON → PostgreSQL untuk historical data

Phase 3: JSON deprecated (week 5+)
  • JSON hanya untuk reports/exploits (binary)
  • Semua structured data di PostgreSQL
  • Migration complete
```

---

## 5. Integration Architecture

### External Service Integration Map

```
┌─────────────────────────────────────────────────────────────────┐
│              EXTERNAL INTEGRATIONS                                │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            BLOCKCHAIN DATA PROVIDERS                       │  │
│  │                                                           │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │  │
│  │  │ Alchemy  │  │ Infura   │  │ QuickNode│  │ Helius   │ │  │
│  │  │ (EVM)    │  │ (EVM)    │  │ (Multi)  │  │ (Solana) │ │  │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │  │
│  │       └──────────────┴────────────┴──────────────┘       │  │
│  │                         │                                  │  │
│  │               ┌─────────▼──────────┐                      │  │
│  │               │  RPC Router        │                      │  │
│  │               │  (Load balance +   │                      │  │
│  │               │   failover)        │                      │  │
│  │               └────────────────────┘                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            SOURCE CODE PROVIDERS                           │  │
│  │                                                           │  │
│  │  EVM: Etherscan, Sourcify, Blockscout, GitHub            │  │
│  │  StarkNet: Voyager, Starkscan, GitHub                     │  │
│  │  Solana: Solana Explorer, Anchor Registry, GitHub         │  │
│  │  Sui/Aptos: Sui Explorer, Aptos Explorer, GitHub          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            BOUNTY & CONTEST PLATFORMS                      │  │
│  │                                                           │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │  │
│  │  │Immunefi  │ │Code4rena │ │Sherlock  │ │Cantina   │    │  │
│  │  │REST API  │ │GraphQL   │ │REST API  │ │REST API  │    │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            THREAT INTELLIGENCE FEEDS                       │  │
│  │                                                           │  │
│  │  • Rekt Database (exploit history)                        │  │
│  │  • DeFiLlama (protocol data)                              │  │
│  │  • BlockSec / Phalcon (attack detection)                  │  │
│  │  • SlowMist Hacked Archive                                │  │
│  │  • Twitter/X (security researcher feeds)                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            DEVELOPER TOOLS                                  │  │
│  │                                                           │  │
│  │  • GitHub API (PR creation, inline comments)              │  │
│  │  • GitLab API (MR creation)                               │  │
│  │  • npm (Hardhat plugin distribution)                      │  │
│  │  • VS Code Marketplace (extension distribution)           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Security Architecture

### Multi-Tenant Security Model

```
┌─────────────────────────────────────────────────────────────────┐
│              SECURITY ARCHITECTURE                                │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ AUTHENTICATION                                            │  │
│  │                                                           │  │
│  │  • API Key (per user/team)                                │  │
│  │  • JWT (Dashboard sessions)                               │  │
│  │  • OAuth2 (GitHub, Google — optional)                     │  │
│  │  • API Key rotation support                               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ AUTHORIZATION (RBAC)                                      │  │
│  │                                                           │  │
│  │  Roles:                                                   │  │
│  │  • admin — full access                                    │  │
│  │  • team_admin — manage team, billing                     │  │
│  │  • auditor — run audits, view results                    │  │
│  │  • viewer — read-only access                             │  │
│  │                                                           │  │
│  │  Resource-level:                                          │  │
│  │  • User → Team → Audits → Findings                        │  │
│  │  • Audit results visible to team members only             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ SERVICE-TO-SERVICE AUTH                                   │  │
│  │                                                           │  │
│  │  • mTLS for gRPC communication                            │  │
│  │  • HMAC-signed internal API calls                         │  │
│  │  • Service-level API keys (internal only)                 │  │
│  │  • Network isolation via Docker network                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ DATA SECURITY                                             │  │
│  │                                                           │  │
│  │  • Contract source code: encrypted at rest                │  │
│  │  • API keys: encrypted at rest (AES-256-GCM)              │  │
│  │  • Audit findings: encrypted at rest                      │  │
│  │  • Secrets: never in logs, never in error messages        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ CODE EXECUTION SANDBOX                                    │  │
│  │                                                           │  │
│  │  • Community detectors: gVisor sandbox                    │  │
│  │  • PoC execution: isolated Docker containers              │  │
│  │  • Anvil forks: ephemeral, auto-destroyed                 │  │
│  │  • Timeouts: 5min for analysis, 1min for PoC, 30s for    │  │
│  │    monitoring alerts                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Deployment Architecture

### Production Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│              DEPLOYMENT ARCHITECTURE                              │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            LOCAL (Developer / Open Source)                 │  │
│  │                                                           │  │
│  │  • Docker Compose (current)                               │  │
│  │  • All services on localhost                               │  │
│  │  • JSON storage                                            │  │
│  │  • No auth (local-only)                                    │  │
│  │  • Free + Open Source                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            CLOUD (SaaS — Vyper Cloud)                     │  │
│  │                                                           │  │
│  │  • Kubernetes (GKE/EKS/AKS)                               │  │
│  │  • PostgreSQL (Cloud SQL / RDS)                           │  │
│  │  • ClickHouse (Altinity Cloud / self-hosted)              │  │
│  │  • Qdrant Cloud (vector DB)                               │  │
│  │  • Redis (ElastiCache / Memorystore)                      │  │
│  │  • NATS (self-hosted or Synadia Cloud)                    │  │
│  │  • Prometheus + Grafana (or Datadog)                      │  │
│  │  • Auth0 / Clerk (auth provider)                          │  │
│  │  • Stripe (billing)                                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            ENTERPRISE (On-Premise)                         │  │
│  │                                                           │  │
│  │  • Helm chart for Kubernetes                              │  │
│  │  • Air-gapped deployment support                          │  │
│  │  • SSO integration (SAML/OIDC)                             │  │
│  │  • Audit logging to SIEM                                   │  │
│  │  • Custom detector deployment                             │  │
│  │  • SLA: 99.5% uptime                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            CI/CD PIPELINE                                  │  │
│  │                                                           │  │
│  │  • GitHub Actions:                                        │  │
│  │    - Build & test Docker images                           │  │
│  │    - Push to GHCR / Docker Hub                            │  │
│  │    - Deploy to staging                                    │  │
│  │    - Integration tests                                     │  │
│  │    - Deploy to production (manual approval)               │  │
│  │                                                           │  │
│  │  • ArgoCD (GitOps for K8s):                               │  │
│  │    - Auto-sync from Git repo                              │  │
│  │    - Rollback support                                      │  │
│  │    - Progressive delivery (canary/blue-green)             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | Python 3.12+ / FastAPI | API & microservices |
| **Frontend** | React 18 / Vite / Tailwind v4 | Dashboard |
| **AI/ML** | OpenAI / Anthropic / DeepSeek APIs | LLM analysis & reasoning |
| **AI/ML (Local)** | Sentence Transformers / scikit-learn | Classification, embeddings |
| **Primary DB** | PostgreSQL 16 | Structured data |
| **Analytics** | ClickHouse | Time-series, analytics |
| **Vector DB** | Qdrant | Semantic search |
| **Cache** | Redis 7 | Caching, pub/sub, queues |
| **Message Bus** | NATS / Kafka | Inter-service events |
| **Formal Verification** | Z3 / CVC5 | SMT solving |
| **Symbolic Execution** | Halmos / Manticore | Symbolic analysis |
| **Fuzzing** | Echidna / Foundry | Property-based testing |
| **Fork Engine** | Anvil (Foundry) | Mainnet fork simulation |
| **Container** | Docker / Kubernetes | Deployment |
| **CI/CD** | GitHub Actions / ArgoCD | Pipeline |
| **Monitoring** | Prometheus / Grafana / OpenTelemetry | Observability |
| **Auth** | Auth0 / Clerk | Authentication |
| **Billing** | Stripe | Payment processing |

---

*Arsitektur Vision: 2026-06-03 | Target: Vyper v4 (12 bulan)*
