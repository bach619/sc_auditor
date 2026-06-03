# Technical Specifications: Vyper OP Features

> **Dokumen**: Spesifikasi teknis detail untuk fitur-fitur utama Vyper OP
> **Sumber**: `01_brainstorming.md` + `02_architecture_vision.md`
> **Penggunaan**: Acuan implementasi untuk sub-agenda

---

## Daftar Isi

1. [Multi-Chain IR Specification](#1-multi-chain-ir-specification)
2. [Formal Verification Engine Spec](#2-formal-verification-engine-spec)
3. [Real-Time Monitoring Spec](#3-real-time-monitoring-spec)
4. [AI Reasoning Engine Spec](#4-ai-reasoning-engine-spec)
5. [Exploit PoC Engine v2 Spec](#5-exploit-poc-engine-v2-spec)
6. [GitHub Actions Integration Spec](#6-github-actions-integration-spec)
7. [Community Platform Spec](#7-community-platform-spec)

---

## 1. Multi-Chain IR Specification

### 1.1 Design Goals

| Goal | Description |
|------|-------------|
| **Chain-Agnostic** | IR harus cukup ekspresif untuk semua smart contract language |
| **Bidirectional** | Bisa convert dari chain-specific → IR dan sebaliknya |
| **Analysis-Friendly** | Memudahkan static analysis, data flow, dan formal verification |
| **Extensible** | Mudah tambah chain baru tanpa modifikasi core IR |

### 1.2 Supported Chains & Languages

| Chain | Language | Adapter | Compiler Integration | Priority |
|-------|----------|---------|---------------------|----------|
| Ethereum/EVM | Solidity | `EVMAdapter` | solc, foundry | ✅ Done |
| StarkNet | Cairo | `CairoAdapter` | cairo-compile | P1 |
| Sui/Aptos | Move | `MoveAdapter` | move-compiler | P1 |
| Solana | Rust | `SolanaAdapter` | anchor, solana-sdk | P2 |
| Polkadot | Rust/ink! | `InkAdapter` | cargo-contract | P2 |
| NEAR | Rust/JS | `NearAdapter` | near-sdk | P3 |
| Fuel | Sway | `SwayAdapter` | forc | P2 |

### 1.3 IR Layer Architecture

```
Chain Source Code (Solidity/Cairo/Move/Rust/etc.)
       │
       ▼
┌──────────────────┐
│ Chain Adapter     │  ← Chain-specific parser & compiler
│ (per language)    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Unified IR        │  ← Chain-agnostic representation
│                   │
│ • Control Flow    │
│ • Data Flow       │
│ • Call Graph      │
│ • Semantic Model  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Analysis Engine   │  ← Works on IR only
│                   │
│ • Static Analysis │
│ • Symbolic Exec   │
│ • Formal Verif    │
│ • AI Reasoning    │
└──────────────────┘
```

### 1.4 Key IR Models

**Location**: `vyper_lib/models/ir.py`

Core dataclasses (full code in `02_architecture_vision.md` Section 3):
- `IRType` — enum: 40+ operation types (storage, memory, arithmetic, control flow, semantic)
- `IROperation` — single IR instruction with operands
- `IRBasicBlock` — control flow graph node
- `IRFunction` — function representation with blocks + natspec
- `IRContract` — full contract IR with storage layout, events, external calls
- `IRProtocol` — multi-contract protocol for cross-contract analysis

### 1.5 Chain Adapter Interface

```python
class ChainAdapter(ABC):
    chain: Chain
    language: Language

    async def parse(self, source: ContractSource) -> AST
    async def compile(self, source: ContractSource) -> Bytecode
    async def to_ir(self, ast_or_bytecode, source) -> IRContract
    async def get_detectors(self) -> List[str]
    async def analyze(self, ir, detectors) -> AnalysisResult
```

### 1.6 Cairo Adapter — Reference Implementation

**Service**: `services/27-scanner-cairo/`

**Dependencies**:
- `cairo-lang` (Cairo compiler)
- `cairo-analyzer` (static analysis)
- `amarna` (community detectors)

**Key Challenges**:
1. Cairo's memory model berbeda dengan EVM storage model → mapping ke IR storage ops
2. Cairo's builtins (Pedersen, range check, etc.) → mapping ke IR external ops
3. StarkNet-specific system calls → mapping ke IR semantic ops

---

## 2. Formal Verification Engine Spec

### 2.1 Architecture

**Service**: `services/29-formal-verifier/`

```
┌─────────────────────────────────────────────────────────────┐
│            FORMAL VERIFICATION PIPELINE                      │
│                                                             │
│  INPUT: IRContract + Invariants                             │
│                                                             │
│  LAYER 1: IR Encoder                                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ IR operations → SMT-LIB formulas                      │  │
│  │ State variables → SMT variables                       │  │
│  │ Function transitions → SMT constraints                │  │
│  └──────────────────────────────────────────────────────┘  │
│                       │                                     │
│                       ▼                                     │
│  LAYER 2: SMT Solver                                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Primary: Z3 (Microsoft Research)                      │  │
│  │ Secondary: CVC5 (Stanford/UIowa)                      │  │
│  │ Strategy:                                             │  │
│  │   For each invariant I:                               │  │
│  │     assert(not I) in encoded system                   │  │
│  │     if SAT   → counterexample found = BUG            │  │
│  │     if UNSAT → invariant proven = SAFE               │  │
│  └──────────────────────────────────────────────────────┘  │
│                       │                                     │
│                       ▼                                     │
│  LAYER 3: Counterexample Generator                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ SMT model → transaction sequence                      │  │
│  │ Transaction sequence → Solidity/Cairo/... PoC         │  │
│  │ PoC → executable exploit script                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/verify` | Verify invariants on contract IR |
| GET | `/verify/{id}` | Get verification result |
| POST | `/invariants/generate` | Auto-generate invariants from contract |
| GET | `/invariants/templates` | List available invariant templates |
| POST | `/invariants/validate` | Validate custom invariant formula |

### 2.3 Invariant Template Library

50+ protocol-specific invariants organized by category:

| Category | Count | Examples |
|----------|-------|----------|
| **Token (ERC-20)** | 5 | totalSupply conservation, balance consistency, allowance atomicity |
| **Token (ERC-721)** | 4 | ownerOf uniqueness, safeTransfer checks, approval clearance |
| **AMM** | 8 | constant product, no free lunch, fee consistency, liquidity tracking |
| **Lending** | 7 | over-collateralization, liquidation incentive, interest accrual |
| **Bridge** | 5 | token conservation, message uniqueness, validator threshold |
| **Staking** | 6 | reward distribution, slashing conditions, unstaking delay |
| **Governance** | 5 | quorum requirements, timelock enforcement, proposal execution |
| **Proxy** | 4 | storage layout preservation, initialization guard, admin upgrade path |
| **General** | 6 | reentrancy guard, overflow safety, access control, events emission |

### 2.4 Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Verification time (simple) | <5s | Single invariant, small contract |
| Verification time (complex) | <5min | Multiple invariants, 1000+ line contract |
| Solver timeout | 30min | Per invariant |
| Parallel verification | 4 invariants simultaneously | Multi-core |
| Accuracy | >95% | Measured against known vulnerable contracts |

---

## 3. Real-Time Monitoring Spec

### 3.1 Service Architecture

```
┌──────────────────────────────────────────────────────────────┐
│              REAL-TIME MONITORING ARCHITECTURE                │
│                                                              │
│  ┌──────────────────┐    ┌──────────────────┐               │
│  │ MEMPOOL WATCHER   │    │ CONTRACT WATCHER  │               │
│  │ (36)              │    │ (37)              │               │
│  │                   │    │                   │               │
│  │ • WebSocket subs  │    │ • State polling   │               │
│  │ • Tx filtering    │    │ • Upgrade detect  │               │
│  │ • Sig matching    │    │ • Re-audit trigger│               │
│  └────────┬─────────┘    └────────┬──────────┘               │
│           │                       │                           │
│           └───────────┬───────────┘                           │
│                       │                                       │
│                       ▼                                       │
│  ┌──────────────────────────────────────┐                    │
│  │ SIMULATION ENGINE (34)               │                    │
│  │                                      │                    │
│  │ • Anvil fork per suspicious tx       │                    │
│  │ • Multi-chain simulation             │                    │
│  │ • State diff analysis                │                    │
│  └──────────────────┬───────────────────┘                    │
│                     │                                         │
│                     ▼                                         │
│  ┌──────────────────────────────────────┐                    │
│  │ ALERT ENGINE (38)                    │                    │
│  │                                      │                    │
│  │ • Severity scoring                   │                    │
│  │ • Multi-channel alert                │                    │
│  │ • Incident report generation         │                    │
│  └──────────────────────────────────────┘                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Exploit Signatures (Initial Set — 15 patterns)

| ID | Name | Severity | Detection Method |
|----|------|----------|-----------------|
| sig-reentrancy-001 | Reentrancy: State change after external call | CRITICAL | Call sequence analysis |
| sig-flashloan-001 | Flash loan attack pattern | CRITICAL | Multi-hop call pattern |
| sig-oracle-001 | Oracle price manipulation | HIGH | Large swap + dependent protocol interaction |
| sig-ownership-001 | Ownership transfer to unknown | CRITICAL | Event signature + address reputation |
| sig-drain-001 | Large token drain to EOA | CRITICAL | Transfer value vs contract balance ratio |
| sig-sandwich-001 | Sandwich attack pattern | HIGH | Swap ordering + profitability analysis |
| sig-liquidation-001 | Liquidation manipulation | HIGH | Collateral ratio anomaly |
| sig-proxy-001 | Suspicious proxy upgrade | CRITICAL | Upgrade event + new implementation check |
| sig-bridge-001 | Bridge message forgery | CRITICAL | Cross-chain message validation |
| sig-governance-001 | Governance attack pattern | HIGH | Proposal timing + voting power anomaly |
| sig-erc20-approval-001 | Approval frontrunning | MEDIUM | approve() race condition |
| sig-permit-001 | Permit signature replay | HIGH | EIP-2612 nonce check |
| sig-fee-on-transfer-001 | Fee-on-transfer exploitation | MEDIUM | Balance inconsistency check |
| sig-inflation-001 | Token inflation attack | CRITICAL | Total supply anomaly |
| sig-rugpull-001 | Liquidity removal pattern | HIGH | LP token burn + token dump |

### 3.3 Alert Severity Matrix

| Score Range | Action | Response Time | Channels |
|-------------|--------|---------------|----------|
| 0.0–0.3 | Log only | — | Internal log |
| 0.3–0.5 | Low alert | <15 min | Dashboard notification |
| 0.5–0.7 | Medium alert | <5 min | Discord + Dashboard |
| 0.7–0.9 | High alert | <1 min | Discord + Telegram + Email |
| 0.9–1.0 | Critical alert | Immediate | All channels + SMS + Auto-action |

---

## 4. AI Reasoning Engine Spec

### 4.1 Architecture

**Service**: `services/30-reasoning-engine/`

```
┌──────────────────────────────────────────────────────────────┐
│              AI REASONING PIPELINE                            │
│                                                              │
│  INPUT: IRProtocol + Threat Intel                            │
│                                                              │
│  STEP 1: DECOMPOSE                                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Break protocol into security components:               │ │
│  │ - Entry points (user-facing)                           │ │
│  │ - State-modifying functions                            │ │
│  │ - Admin/privileged functions                           │ │
│  │ - External integrations                                │ │
│  └────────────────────────────────────────────────────────┘ │
│                       │                                      │
│  STEP 2: ANALYZE FLOW                                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Cross-contract data & control flow analysis:           │ │
│  │ - Circular dependencies → reentrancy risk              │ │
│  │ - Untrusted external calls                             │ │
│  │ - Value flows across trust boundaries                  │ │
│  │ - Missing access controls                              │ │
│  └────────────────────────────────────────────────────────┘ │
│                       │                                      │
│  STEP 3: CHALLENGE ASSUMPTIONS                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ "Oracle always correct?" "ERC-20 always compliant?"    │ │
│  │ "Function always atomic?" "No one will frontrun?"      │ │
│  └────────────────────────────────────────────────────────┘ │
│                       │                                      │
│  STEP 4: THREAT INTEL BOOST                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Match against recent exploits from Rekt/DeFiLlama:     │ │
│  │ "Similar pattern exploited in Protocol X last week"    │ │
│  │ → Priority boost to HIGH/CRITICAL                      │ │
│  └────────────────────────────────────────────────────────┘ │
│                       │                                      │
│  STEP 5: GENERATE FINDING + FIX                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ • Vulnerability description + attack scenario           │ │
│  │ • Confidence score                                      │ │
│  │ • Fix suggestion with code                              │ │
│  │ • Similar historical exploits for reference             │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 Key Components

| Component | Service | Description |
|-----------|---------|-------------|
| Context Builder | 30-reasoning | Build full protocol context from IR |
| Cross-Contract Analyzer | 30-reasoning | Call graph + data flow analysis |
| Logic Extractor | 30-reasoning | Extract business logic intent |
| Multi-Step Reasoner | 30-reasoning | Chain-of-thought vulnerability reasoning |
| Threat Intel Feed | 31-threat-intel | Aggregate exploit data from Rekt, DeFiLlama, BlockSec |
| Pattern Matcher | 31-threat-intel | Match latest exploits to current contracts |
| Fix Generator | 32-auto-fix | LLM-based fix code generation |
| Fix Validator | 32-auto-fix | Run tests + formal verification on proposed fix |
| PR Creator | 32-auto-fix | Auto-create GitHub PR with fix |

### 4.3 LLM Provider Strategy

| Case | Provider | Model | Reason |
|------|----------|-------|--------|
| Simple pattern analysis | DeepSeek | deepseek-chat | Low cost, good accuracy |
| Complex reasoning | Claude | claude-sonnet-4-20250514 | Best reasoning capability |
| Code generation (fix) | Claude | claude-sonnet-4-20250514 | Best code generation |
| Cross-contract analysis | GPT | gpt-4.1 | Good with large context |
| Threat intel summarization | DeepSeek | deepseek-chat | Cost-effective for summarization |
| Cached/common patterns | Local | Sentence Transformer | Zero API cost |

---

## 5. Exploit PoC Engine v2 Spec

### 5.1 Attack Type Expansion

| Tier | Category | Count | New Types |
|------|----------|-------|-----------|
| **Tier 1** | Classic (Existing) | 5 | Already implemented |
| **Tier 2** | DeFi Exploits | 8 | Sandwich, Frontrunning, Liquidation manipulation, Bad debt, TWAP manipulation, Slippage, Impermanent loss, Vault inflation |
| **Tier 3** | Governance & Proxy | 6 | Timelock bypass, Proposal manipulation, Vote delegation, Storage collision, Initialization attack, Implementation bricking |
| **Tier 4** | Cross-Chain & Advanced | 8 | Bridge forgery, Validator collusion, Signature replay, EIP-712 bypass, Multi-hop flash loan, MEV bundle, AA paymaster, Staking depeg |
| **Tier 5** | L2 & Emerging | 4 | Sequencer censorship, Fraud proof manipulation, V4 hook exploits, Cross-rollup message exploits |
| **TOTAL** | | **31** | |

### 5.2 PoC Generator Interface

```python
class PoCGenerator:
    async def generate(self, finding: Finding, chain: Chain) -> PoC:
        """Generate executable PoC for a finding"""
    
    async def simulate(self, poc: PoC) -> SimulationResult:
        """Simulate PoC on Anvil fork, return profit/loss"""
    
    async def to_immunefi(self, poc: PoC, finding: Finding) -> str:
        """Format PoC for Immunefi submission"""
```

### 5.3 Anvil Fork Farm

**Service**: `services/33-anvil-farm/`

Multi-chain fork management:
- **EVM**: Anvil (Foundry) — mainnet, Arbitrum, Optimism, Base forks
- **StarkNet**: Katana (Dojo) — StarkNet fork
- **Solana**: Solana Test Validator — Solana fork
- **Sui**: Sui Local Network — Sui fork

Pool of pre-forked chains for instant simulation.

---

## 6. GitHub Actions Integration Spec

### 6.1 Action Definition

```yaml
# action/action.yml
name: Vyper Smart Contract Audit
description: Automated smart contract security audit for every PR

inputs:
  api-key:
    description: Vyper API Key
    required: true
  chain:
    description: Target blockchain (ethereum, starknet, solana, etc.)
    default: ethereum
  tools:
    description: Analysis tools to run (slither, mythril, echidna, halmos, manticore)
    default: slither,mythril,echidna
  severity-fail:
    description: Minimum severity to fail the check
    default: critical
  mode:
    description: Output mode (comment, annotation, check)
    default: comment

runs:
  using: docker
  image: Dockerfile
```

### 6.2 Developer Tooling Suite

| Tool | Package | Distribution |
|------|---------|-------------|
| **Hardhat Plugin** | `@vyper-audit/hardhat` | npm |
| **Foundry Plugin** | Built into Vyper CLI | crates.io / pip |
| **VSCode Extension** | `vyper-audit` | VSCode Marketplace |
| **Pre-Commit Hook** | `.pre-commit-hooks.yaml` | pip / brew |
| **CLI Tool** | `vyper` | pip / brew / docker |

### 6.3 GitHub App Features

| Feature | Description |
|---------|-------------|
| **PR Comment** | Summary of findings with severity badges |
| **Inline Annotation** | Per-line vulnerability highlighting |
| **Status Check** | Pass/fail based on severity threshold |
| **Auto-Fix PR** | Vyper creates PR with fix for auto-fixable issues |
| **Dashboard Link** | Link to full Vyper dashboard report |

---

## 7. Community Platform Spec

### 7.1 Architecture

**Service**: `services/39-community/`

```
services/39-community/
├── app.py
├── Dockerfile
└── src/
    ├── profiles.py          # User profiles, reputation
    ├── leaderboard.py       # Global ranking system
    ├── guilds.py            # Guild creation & management
    ├── detector_market.py   # Community detector marketplace
    ├── intel_feed.py        # Shared threat intelligence
    ├── governance.py        # DAO voting & proposals
    └── models.py            # Pydantic models
```

### 7.2 Reputation System

| Action | Points | Badge |
|--------|--------|-------|
| True positive finding confirmed | +100 | Bug Hunter |
| $10K+ bounty claimed | +500 | Bounty Master |
| $100K+ bounty claimed | +2000 | Legendary Hunter |
| Detector approved by community | +300 | Detector Smith |
| 10 detectors approved | +1000 | Master Smith |
| Guild created | +200 | Guild Leader |
| Mentoring (help new auditor) | +50/task | Mentor |
| 7-day streak | +10/day bonus | Consistent |
| 30-day streak | +25/day bonus | Dedicated |
| 365-day streak | +50/day bonus | Unstoppable |

### 7.3 DAO Governance Model

| Parameter | Initial Value | Governed By |
|-----------|--------------|-------------|
| Free tier audit limit | 3/month | DAO vote |
| Pro tier price | $49/mo | Core team → DAO |
| Bounty share percentage | 10% | DAO vote |
| Detector approval threshold | 70% community vote | DAO |
| Feature priority | Community voting | DAO |
| Treasury allocation | % for dev, community, reserve | DAO |

### 7.4 Guild System

```
GUILD STRUCTURE:
├── Guild Master (creator)
├── Senior Auditors (invite-only)
├── Auditors (members)
└── Apprentices (learning)

GUILD FEATURES:
├── Collaborative audit (multiple members on one audit)
├── Guild leaderboard (compete with other guilds)
├── Guild treasury (% of bounty share → guild pool)
├── Internal knowledge base (shared findings, patterns)
└── Guild quests (weekly challenges with rewards)
```

---

## Appendix: Service Registration

### New Services Summary

| # | Service Name | Port | Phase | Description |
|---|-------------|------|-------|-------------|
| 18 | `18-cli` | — | F3 | Vyper CLI Tool |
| 19 | `19-vscode` | — | F3 | VSCode Extension Backend |
| 20 | `20-api-gateway` | 8021 | F1 | Unified API Gateway |
| 21 | `21-code4rena` | 8022 | F1 | Code4rena Integration |
| 22 | `22-sherlock` | 8023 | F1 | Sherlock Integration |
| 23 | `23-cantina` | 8024 | F1 | Cantina Integration |
| 24 | `24-hats` | 8025 | F1 | Hats Finance Integration |
| 25 | `25-source-starknet` | 8026 | F1 | StarkNet Source Fetcher |
| 26 | `26-source-solana` | 8027 | F2 | Solana Source Fetcher |
| 27 | `27-scanner-cairo` | 8028 | F1 | Cairo Analyzer |
| 28 | `28-scanner-move` | 8029 | F2 | Move Analyzer |
| 29 | `29-formal-verifier` | 8030 | F2 | Formal Verification Engine |
| 30 | `30-reasoning-engine` | 8031 | F2 | AI Reasoning Engine |
| 31 | `31-threat-intel` | 8032 | F2 | Threat Intelligence Feed |
| 32 | `32-auto-fix` | 8033 | F2 | Auto-Fix Generator |
| 33 | `33-anvil-farm` | 8034 | F1 | Anvil Fork Farm (Multi-chain) |
| 34 | `34-simulation-engine` | 8035 | F2 | Multi-Chain Simulation Engine |
| 35 | `35-github-integration` | 8036 | F3 | GitHub/GitLab Integration |
| 36 | `36-mempool-watcher` | 8037 | F2 | Mempool Monitor |
| 37 | `37-contract-watcher` | 8038 | F2 | Contract State Monitor |
| 38 | `38-alert-engine` | 8039 | F2 | Alert & Escalation Engine |
| 39 | `39-community` | 8040 | F3 | Community Platform |
| 40 | `40-analytics` | 8041 | F1 | Analytics & Billing |

### Port Allocation Summary

```
Existing: 8000–8020 (21 ports used)
New Phase 1: 8021–8028, 8034, 8041 (10 new ports)
New Phase 2: 8029–8033, 8035, 8037–8039 (9 new ports)
New Phase 3: 8036, 8040, + CLI/VSCode (no port) (4 new)
Total: 21 + 10 + 9 + 4 = 44 services at full scale
```

---

*Technical Specifications: 2026-06-03 | Ready for implementation planning*
