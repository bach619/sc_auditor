# Vyper System Knowledge — Complete Application Reference for Antonio

> **Purpose**: This document is Antonio's complete knowledge base about the Vyper platform.
> It is loaded into vector memory at startup and can be referenced via semantic search.
> **Last Updated**: 2026-06-03

---

## 1. Platform Overview

**Vyper** is an automated smart contract security audit platform running as 28 FastAPI microservices
on Docker Compose. It scans contracts from 5 bug bounty platforms, analyzes them with 6+ tools,
generates exploit PoCs from 16 attack types, and produces Immunefi-ready submission reports.

- **Language**: Python 3.11+ (backend), TypeScript + React + Tailwind v4 + Vite 8 (frontend)
- **Storage**: JSON file-based (Docker volumes at `/data/`)
- **Network**: `vyper-net` bridge network (Docker internal)
- **Port Range**: 8000–8028 (host-mapped)
- **LLM Providers**: 7 (OpenAI, Anthropic, DeepSeek, xAI Grok, OpenRouter, Google Gemini, HuggingFace)

---

## 2. Complete Service Map (28 services)

**CRITICAL — Port Convention:**
- **Host ports** (e.g., `8001`, `8014`) are for accessing services from OUTSIDE Docker (localhost)
- **Internal ports** (usually `:8000`) are what services use INSIDE the Docker network
- **Antonio always uses INTERNAL ports** since it runs inside Docker
- Exception: scanner services (04a-04e, 05, 08, 09, 17) use matching internal/host ports

### Core Services (01–16)

| Service | Host Port | Internal Port | Role |
|---------|-----------|---------------|------|
| 01-config | 8011 | 8000 | Global config store — API keys, provider settings, preferences |
| 02-immunefi | 8001 | 8000 | Immunefi bounty program sync (234+ programs) |
| 03-source | 8002 | 8000 | Multi-source contract fetcher (Etherscan, Sourcify, Blockscout) |
| 04-scanner | 8003 | 8000 | Legacy scanner gateway — coordinates sub-scanners |
| 04a-scanner-slither | 8014 | 8014 | Static analysis (Slither + custom detectors) |
| 04b-scanner-echidna | 8015 | 8015 | Fuzzing (Echidna) + intelligence engine |
| 04c-scanner-forge | 8016 | 8016 | Build verification (Foundry Forge) |
| 04d-scanner-halmos | 8017 | 8017 | Symbolic testing (Halmos) |
| 04e-scanner-manticore | 8020 | 8018 | Symbolic execution (HIGH/CRITICAL focus) |
| 05-scanner-mythril | 8013 | 8013 | Deep symbolic execution (Mythril) |
| 06-ai | 8004 | 8000 | LLM-based vulnerability analysis |
| 07-classifier | 8005 | 8000 | ML-based TP/FP finding classification + metrics |
| 08-exploit | 8006 | 8006 | Anvil Docker engine + PoC exploit generation |
| 09-reporter | 8007 | 8007 | Immunefi-format audit report generation |
| 10-notifier | 8008 | 8000 | Discord/Telegram/Email notifications |
| 11-orchestrator | 8009 | 8000 | Pipeline state machine (10 stages) + SSE broadcast |
| 12-webhook | 8010 | 8000 | Webhook delivery + logs |
| 13-upkeep | 8012 | 8000 | Backup, metrics, health, disk cleanup |
| 14-agent (Antonio) | 8021 | 8000 | Central AI controller — ReAct loop + chat + daemon |
| 15-dashboard | 8000 | 8000 | React SPA + API Gateway + SSE event hub |
| 16-submission | 8018 | 8000 | Immunefi bug bounty submission agent |

### Bounty Platform Integrations (18–21)

| Service | Host Port | Internal Port | Platform |
|---------|-----------|---------------|----------|
| 18-code4rena | 8022 | 8000 | Code4rena audit contests (GraphQL) |
| 19-sherlock | 8023 | 8000 | Sherlock audit contests (REST) |
| 20-cantina | 8024 | 8000 | Cantina bug bounties (REST) |
| 21-hats | 8025 | 8000 | Hats Finance bug bounties (REST) |

### Learning & Experience (17)

| Service | Host Port | Internal Port | Role |
|---------|-----------|---------------|------|
| 17-experience | 8019 | 8019 | Centralized experience system — cross-agent learning, SQLite |

### Multi-Chain Expansion (22–23)

| Service | Host Port | Internal Port | Role |
|---------|-----------|---------------|------|
| 22-source-starknet | 8026 | 8000 | StarkNet/Cairo source fetcher (Voyager, Starkscan, GitHub) |
| 23-scanner-cairo | 8028 | 8000 | Cairo scanner — 8 pattern-based detectors + ChainAdapter ABC |

---

## 3. Service Communication Map

```
                    ┌──────────────┐
                    │  15-dashboard│◄──── SSE (real-time)
                    │  (port 8000) │
                    └──────┬───────┘
                           │ HTTP
                    ┌──────▼───────┐
                    │  14-agent    │◄── Antonio (ReAct + Chat)
                    │  (port 8021) │
                    └──────┬───────┘
                           │ HTTP
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                  ▼
┌─────────────┐   ┌──────────────┐   ┌──────────────┐
│11-orchestr. │   │02-immunefi   │   │03-source      │
│(pipeline)   │   │(bounty sync) │   │(contract src) │
└──────┬──────┘   └──────────────┘   └──────────────┘
       │
       ▼
┌──────────────────────────────────────────────────┐
│              SCANNER CLUSTER                      │
│  04a-slither → 04b-echidna → 04c-forge           │
│  04d-halmos  → 04e-manticore → 05-mythril        │
└──────────────────────┬───────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│06-ai     │  │07-class. │  │08-exploit│
│(LLM TP/FP)│  │(ML class.)│  │(PoC gen) │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │
     └─────────────┼─────────────┘
                   ▼
         ┌──────────────────┐
         │09-reporter       │
         │10-notifier       │
         │16-submission     │
         └──────────────────┘
```

---

## 4. Audit Pipeline (10 Stages)

```
PENDING → FETCHING_PROGRAM → FETCHING_SOURCE → SCANNING
→ AI_ANALYSIS → CLASSIFYING → EXPLOITING (TP only) → REPORTING
→ NOTIFYING → COMPLETED
```

### Stage Details

| Stage | What Happens | Services Involved |
|-------|-------------|-------------------|
| PENDING | Audit request received, queued | 11-orchestrator |
| FETCHING_PROGRAM | Fetch bounty program details | 02-immunefi, 18-code4rena, 19-sherlock, 20-cantina, 21-hats |
| FETCHING_SOURCE | Download contract source code | 03-source, 22-source-starknet |
| SCANNING | Run 6 analysis tools in parallel | 04a-slither, 04b-echidna, 04c-forge, 04d-halmos, 04e-manticore, 05-mythril |
| AI_ANALYSIS | LLM triage + TP/FP assessment | 06-ai |
| CLASSIFYING | ML confidence scoring + deduplication | 07-classifier |
| EXPLOITING | Generate PoC exploits (TP findings only) | 08-exploit |
| REPORTING | Generate Immunefi-format report | 09-reporter |
| NOTIFYING | Send alerts via Discord/Telegram/Email | 10-notifier |
| COMPLETED | Audit finished, results stored | 11-orchestrator, 17-experience |

---

## 5. All Exploit Types (16 Primitives)

### Tier 2 — Classic Exploits (5)
1. Reentrancy (CEI pattern violation)
2. Integer Overflow/Underflow
3. Access Control Bypass
4. Flash Loan Attack
5. Oracle Price Manipulation

### Tier 2 — DeFi Exploits (3)
6. TWAP Manipulation
7. Sandwich Frontrun
8. Governance Attack (flash loan voting, proposal flooding)

### Tier 3 — Proxy/Upgrade (2)
9. Proxy Initialization Frontrun
10. Timelock Bypass

### Tier 4 — Cross-chain/Advanced (4)
11. Bridge Forgery (cross-chain message manipulation)
12. EIP-712 Bypass (typed data signature replay)
13. Paymaster Exploit (ERC-4337 validation bypass)
14. Uniswap V4 Hook Exploit (fee manipulation)

### Tier 5 — L2/Emerging (2)
15. Sequencer Censorship (L2 forced liquidation)
16. Storage Collision (proxy delegatecall)

---

## 6. Multi-Chain Support

### Supported Chains
| Chain | Language | Service | Status |
|-------|----------|---------|--------|
| Ethereum/EVM | Solidity | 03-source, 04-scanner | ✅ Production |
| StarkNet | Cairo | 22-source-starknet, 23-scanner-cairo | ✅ Alpha |

### Cairo Scanner Detectors (8 patterns)
1. Access Control (`ownable_check`)
2. Storage Collision
3. Arithmetic Overflow (`u256_safe_add`)
4. Reentrancy (`no_reentrancy`)
5. Unchecked Return (`syscall_result`)
6. Oracle Manipulation
7. Event Emission
8. Upgrade Safety

### ChainAdapter Interface
```python
# vyper_lib/models/chain_adapter.py
class ChainAdapter(ABC):
    def parse(source: str) -> ContractSource
    def compile(source: ContractSource) -> CompileResult
    def to_ir(compiled: CompileResult) -> IRContract
    def get_detectors() -> list[Callable]
    def analyze(ir: IRContract, detectors: list) -> list[Finding]
```

---

## 7. LLM Provider Configuration

| Provider | Model | Base URL | API Type |
|----------|-------|----------|----------|
| OpenAI | gpt-4o | https://api.openai.com/v1 | OpenAI-compatible |
| Anthropic | claude-3-5-sonnet-20241022 | https://api.anthropic.com/v1 | Anthropic |
| DeepSeek | deepseek-chat | https://api.deepseek.com | OpenAI-compatible |
| xAI Grok | grok-4.20-expert | https://api.x.ai/v1 | OpenAI-compatible |
| OpenRouter | openrouter/free | https://openrouter.ai/api/v1 | OpenAI-compatible |
| Google Gemini | gemini-3.1-pro | https://generativelanguage.googleapis.com/v1 | OpenAI-compatible |
| HuggingFace | Mistral-7B-Instruct-v0.3 | https://api-inference.huggingface.co/v1 | OpenAI-compatible |

**Failover**: 3 retries per provider → next provider. Timeout: 90 seconds per call.

---

## 8. Antonio's Own Architecture

### ReAct Agent Loop
```
1. THINK  → LLM reasons about context, decides next action
2. ACT    → Execute skill via HTTP to backend service
3. OBSERVE→ Store result in working memory + episodic store
4. REPEAT → Until FINAL_ANSWER or max_steps (25)
```

### Chat Mode
- **MODE 1 (Direct)**: For general questions — answers from system knowledge
- **MODE 2 (Skill-Based)**: For audit commands — calls skills to backend services

### Team Audit
- Lead Auditor delegates to 6 sub-agents: Intel, Scanner, Analyst, Exploit, QA, Report
- Each sub-agent runs its own mini ReAct loop with role-specific prompts

### Memory System
| Store | Type | Persistence | Purpose |
|-------|------|-------------|---------|
| Working | dict | In-memory | Current session context |
| Episodic | list | JSON file | Audit history + outcomes |
| Semantic | dict | In-memory | Accumulated knowledge |
| Vector | TF-IDF | JSON file | Semantic search of past sessions |
| Graph | nodes/edges | JSON file | Vulnerability relationships |

### Skills (10 available)
| Skill | Target Service | Method |
|-------|---------------|--------|
| fetch_program | 02-immunefi | GET /programs |
| fetch_source | 03-source | POST /fetch |
| scan_contract | 04-scanner | POST /scan |
| analyze_findings | 06-ai | POST /analyze |
| classify_finding | 07-classifier | GET/POST |
| exploit_test | 08-exploit | POST /exploit |
| generate_report | 09-reporter | POST /generate |
| notify | 10-notifier | POST /notify |
| deduplicate_findings | (local) | Pattern matching |
| delegate_task | (agent registry) | Agent-to-agent |

---

## 9. Configuration Management

All config stored in 01-config service at `http://01-config:8000`:

### Key Configuration Keys
- `providers.openai` — OpenAI API key
- `providers.anthropic` — Anthropic API key
- `providers.deepseek` — DeepSeek API key
- `providers.xai` — xAI API key
- `providers.openrouter` — OpenRouter API key
- `providers.google` — Google API key
- `provider_configs` — Per-provider model/base_url overrides
- `agent_max_steps` — Max ReAct loop iterations (default: 25)
- `agent_preferred_provider` — Preferred LLM provider name
- `immunefi_api_key` — Immunefi API key
- `etherscan_api_key` — Etherscan API key

---

## 10. Data Directories

| Path | Service | Contents |
|------|---------|----------|
| `/data/config/` | 01-config | API keys, provider settings |
| `/data/scanner/solc/` | 04-scanner | Installed solc versions |
| `/data/scanner/results/` | 04-scanner | Scan results (JSON) |
| `/data/source/` | 03-source | Downloaded source code |
| `/data/reporter/reports/` | 09-reporter | Generated audit reports |
| `/data/exploit/pocs/` | 08-exploit | PoC exploit scripts |
| `/data/classifier/` | 07-classifier | Classification results |
| `/data/orchestrator/` | 11-orchestrator | Pipeline state |
| `/data/immunefi/` | 02-immunefi | Synced bounty programs |
| `/data/learning/` | 14-agent, 17-exp | Learning data, vector index |
| `~/.sc_auditor/learning/` | 14-agent | Antonio's memory stores |

---

## 11. Health Check Dependencies

Each service exposes `GET /health` returning `{"data": {...}, "meta": {"status": "ok"}}`.

### Antonio's Health Check
Antonio's `/health` reports: active sessions, skills loaded, memory entries (working/episodic/semantic/vector/graph), daemon status.

### Common Issues
1. **9090 port conflict**: 08-exploit binds port 9090 for Anvil — check `docker compose ps`
2. **Dashboard shows "offline"**: Check REPORTER_URL, WEBHOOK_URL, UPKEEP_URL env vars in docker-compose
3. **DeepSeek empty base_url**: Fixed with explicit default + better logging
4. **LLM timeout**: 90s timeout — large contracts may need more time
5. **Docker socket permission**: 08-exploit needs Docker socket for Anvil

---

## 12. Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| CONFIG_URL | http://01-config:8000 | Config service URL |
| IMMUNEFI_URL | http://02-immunefi:8000 | Immunefi service URL |
| SOURCE_URL | http://03-source:8000 | Source fetcher URL |
| SCANNER_URL | http://04-scanner:8000 | Scanner gateway URL |
| AI_URL | http://06-ai:8000 | AI analysis service URL |
| CLASSIFIER_URL | http://07-classifier:8000 | Classifier service URL |
| EXPLOIT_URL | http://08-exploit:8000 | Exploit service URL |
| REPORTER_URL | http://09-reporter:8000 | Reporter service URL |
| NOTIFIER_URL | http://10-notifier:8000 | Notifier service URL |
| ORCHESTRATOR_URL | http://11-orchestrator:8000 | Orchestrator URL |
| DASHBOARD_URL | http://15-dashboard:8000 | Dashboard URL |
| EXPERIENCE_URL | http://17-experience:8019 | Experience service URL |
| SCANNER_SLITHER_URL | http://04a-scanner-slither:8014 | Slither service |
| SCANNER_ECHIDNA_URL | http://04b-scanner-echidna:8015 | Echidna service |
| SCANNER_FORGE_URL | http://04c-scanner-forge:8016 | Forge service |
| SCANNER_HALMOS_URL | http://04d-scanner-halmos:8017 | Halmos service |
| SCANNER_MANTICORE_URL | http://04e-scanner-manticore:8018 | Manticore service |
| SCANNER_MYTHRIL_URL | http://05-scanner-mythril:8013 | Mythril service |
| SOURCE_STARKNET_URL | http://22-source-starknet:8000 | StarkNet source |
| SCANNER_CAIRO_URL | http://23-scanner-cairo:8000 | Cairo scanner |

---

## 13. Testing

- **Test directory**: `tests/`
- **28/28 services** have ≥1 integration test
- **117 tests total**: 54 unit + 16 integration (need Docker) + 8 E2E
- **Run unit tests**: `pytest tests/ -v -m "not integration and not e2e"`
- **Run all**: `pytest tests/ -v` (requires `docker compose up`)

---

## 14. Recent Changes (2026-06-03)

1. **8 new services added** (18–23): Code4rena, Sherlock, Cantina, Hats, Experience, StarkNet source, Cairo scanner
2. **16 exploit primitives** — expanded from 5 to 16 attack types
3. **Setup.py fix** — vyper_lib now properly packaged in find_packages
4. **CI hardening** — removed `|| true` masking, all steps now fail on error
5. **Docker security** — chmod 777 → 755, duplicate pip install removed
6. **Duplicate models eliminated** — 04-scanner now re-exports from vyper_lib (~1270 lines removed)
7. **28/28 services tested** — all 8 gaps filled with integration tests
8. **SSE broadcast** — orchestrator streams pipeline progress to dashboard in real-time
