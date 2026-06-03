"""LLM Client for Agent Reasoning — multi-provider support.

Supports any provider via Settings:
- OpenAI-compatible (OpenAI, DeepSeek, xAI/Grok, OpenRouter, HuggingFace, etc.)
- Anthropic (native API format)

Provider config is loaded from Config Service at startup.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx
import structlog

log = structlog.get_logger()

DEFAULT_TIMEOUT = 90.0  # Increased from 30s — large system prompts need more time

# ── Safety helper: ensure we always have a meaningful error string ──
# Some exceptions (e.g. httpx.ConnectError) can produce empty str(exc),
# which causes confusing empty "Chat failed: " messages in the frontend.
def _safe_error(exc: BaseException) -> str:
    """Return a non-empty error string from any exception."""
    s = str(exc).strip() if exc else ""
    if s:
        return s
    # Try to build a meaningful message from the exception class + context
    cls_name = type(exc).__name__
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code} from {exc.request.url}"
    if isinstance(exc, httpx.RequestError):
        return f"Request error ({cls_name})"
    if isinstance(exc, OSError):
        # e.g. ConnectionRefusedError, TimeoutError
        return f"{cls_name}: {getattr(exc, 'strerror', 'network error')}"
    return cls_name

# ── Provider default base URLs ──────────────────────────────
# These match the apiKeyField / baseUrlField in frontend Settings.tsx

PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "api_type": "openai_compatible",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-3-5-sonnet-20241022",
        "api_type": "anthropic",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "api_type": "openai_compatible",
    },
    "xai": {
        "base_url": "https://api.x.ai/v1",
        "model": "grok-4.20-expert",
        "api_type": "openai_compatible",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openrouter/free",
        "api_type": "openai_compatible",
    },
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1",
        "model": "gemini-3.1-pro",
        "api_type": "openai_compatible",
    },
    "huggingface": {
        "base_url": "https://api-inference.huggingface.co/v1",
        "model": "mistralai/Mistral-7B-Instruct-v0.3",
        "api_type": "openai_compatible",
    },
}

# Providers that use OpenAI /chat/completions format
OPENAI_COMPATIBLE_PROVIDERS = {
    k for k, v in PROVIDER_DEFAULTS.items()
    if v["api_type"] == "openai_compatible"
}

# ── Text Cleaning ──────────────────────────────────────────

# Pattern: double-escaped unicode like \\u201c or \\u2014 (backslash + u + 4 hex digits)
_UNICODE_ESC_RE = re.compile(r"\\u([0-9a-fA-F]{4})")

# Pattern: common JSON double-escapes like \\n, \\t, \\"
_COMMON_ESC_RE = re.compile(r"\\([nrt\"\\])")

_ESC_MAP: dict[str, str] = {
    "n": "\n",
    "r": "\r",
    "t": "\t",
    '"': '"',
    "\\": "\\",
}


def _unescape_text(text: str) -> str:
    """Clean escape sequences from LLM response text.

    Handles two cases:
    1. Unicode escapes  → actual Unicode chars  (e.g. ``\\u201c`` → ``"``)
    2. Common escapes   → actual control chars   (e.g. ``\\n`` → newline)

    Only processes sequences that were NOT already decoded by JSON parser
    (i.e. where the backslash appears literally in the string).
    """
    # 1. Unicode escapes: \u201c → "  (LEFT DOUBLE QUOTATION MARK)
    text = _UNICODE_ESC_RE.sub(lambda m: chr(int(m.group(1), 16)), text)

    # 2. Common escapes: \n → newline, \" → quote, etc.
    text = _COMMON_ESC_RE.sub(lambda m: _ESC_MAP.get(m.group(1), m.group(0)), text)

    return text


def _deep_unescape(obj: Any) -> Any:
    """Recursively unescape all string values in a JSON-like structure."""
    if isinstance(obj, str):
        return _unescape_text(obj)
    if isinstance(obj, dict):
        return {k: _deep_unescape(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_unescape(v) for v in obj]
    return obj


# ── ReAct System Prompt ────────────────────────────────────

REACT_SYSTEM_PROMPT = """You are Vyper, an expert smart contract security AI agent.

Your goal is to audit smart contracts and find security vulnerabilities.
You have access to a set of SKILLS that you can call.

## How to Think (ReAct Pattern)

For each step, follow this format:

THOUGHT: What is the current situation? What should I do next?
ACTION: skill_name
ACTION_INPUT: {"param": "value"}
OBSERVATION: (result from skill)

## Available Skills

{s Skills}

## Rules

1. Always think step by step before acting
2. Choose ONE skill per step
3. After calling a skill, wait for the observation
4. If a skill fails, try an alternative approach
5. When the task is complete, respond with FINAL_ANSWER
6. Be specific about what you find — contract names, function names, line numbers

## Output Format

You MUST respond with valid JSON:
{{
  "thought": "your reasoning here",
  "action": "skill_name or FINAL_ANSWER",
  "action_input": {{ "param": "value" or null }},
  "final_answer": "final summary or null"
}}

For the final step, set action to "FINAL_ANSWER" and provide summary in final_answer.
"""


# ── Vyper Platform Knowledge ─────────────────────────────────
# Embedded knowledge so Antonio can answer broad/strategic questions
# about the platform itself without needing to call any skills.

VYPER_KNOWLEDGE = """
## Vyper Platform Knowledge (Comprehensive)

You are the AI controller of **Vyper**, an automated smart contract security audit platform.
Here is EVERYTHING you know about the platform:

### Platform Overview
- **28 microservices** (Python FastAPI) in Docker Compose on `vyper-net` bridge network
- Dashboard at http://localhost:8000, Antonio (you) at port 8021
- 10-stage audit pipeline from PENDING to COMPLETED
- 7 LLM providers with automatic failover
- JSON file-based storage via Docker volumes
- React 18 + TypeScript + Tailwind v4 + Vite 8 frontend

### Complete Service Map (28 services)

**Core (01-16):**
- 01-config (host 8011, internal :8000) — API keys, provider settings, preferences storage
- 02-immunefi (host 8001, internal :8000) — Immunefi bounty program sync (234+ programs)
- 03-source (host 8002, internal :8000) — Multi-source Solidity fetcher (Etherscan, Sourcify)
- 04-scanner (host 8003, internal :8000) — Scanner gateway router
- 04a-scanner-slither (host 8014, internal :8014) — Static analysis + custom detectors
- 04b-scanner-echidna (host 8015, internal :8015) — Fuzzing + intelligence engine
- 04c-scanner-forge (host 8016, internal :8016) — Foundry Forge build verification
- 04d-scanner-halmos (host 8017, internal :8017) — Symbolic testing (Halmos)
- 04e-scanner-manticore (host 8020, internal :8018) — Deep symbolic execution
- 05-scanner-mythril (host 8013, internal :8013) — Symbolic execution + self-contained intelligence
- 06-ai (host 8004, internal :8000) — LLM-based vulnerability TP/FP classification
- 07-classifier (host 8005, internal :8000) — ML classifier + confidence scoring + deduplication
- 08-exploit (host 8006, internal :8006) — PoC exploit generation (Anvil Docker, 16 primitives)
- 09-reporter (host 8007, internal :8007) — Immunefi-format report generation
- 10-notifier (host 8008, internal :8000) — Discord/Telegram/Email notifications
- 11-orchestrator (host 8009, internal :8000) — Pipeline state machine + SSE broadcast
- 12-webhook (host 8010, internal :8000) — Webhook delivery + logs
- 13-upkeep (host 8012, internal :8000) — Backup, metrics, health, disk cleanup
- 14-agent (host 8021, internal :8000) — YOU (Antonio) — ReAct loop + chat + daemon + team
- 15-dashboard (host 8000, internal :8000) — React SPA + API Gateway + SSE event hub
- 16-submission (host 8018, internal :8000) — Immunefi bug report submission

**Bounty Platform Integrations (18-21):**
- 18-code4rena (host 8022, internal :8000) — Code4rena audit contests (GraphQL API)
- 19-sherlock (host 8023, internal :8000) — Sherlock audit contests (REST API)
- 20-cantina (host 8024, internal :8000) — Cantina bug bounties (REST API)
- 21-hats (host 8025, internal :8000) — Hats Finance bug bounties (REST API)

**Learning (17):**
- 17-experience (host 8019, internal :8019) — Centralized cross-agent learning + SQLite

**Multi-Chain (22-23):**
- 22-source-starknet (host 8026, internal :8000) — StarkNet/Cairo source fetcher (Voyager, Starkscan, GitHub)
- 23-scanner-cairo (host 8028, internal :8000) — Cairo scanner with 8 pattern-based detectors

### Audit Pipeline (10 stages)
PENDING → FETCHING_PROGRAM → FETCHING_SOURCE → SCANNING → AI_ANALYSIS → CLASSIFYING → EXPLOITING (TP only) → REPORTING → NOTIFYING → COMPLETED

### Exploit Primitives (16 types)
Tier 2 Classic: Reentrancy, Integer Overflow, Access Control, Flash Loan, Oracle Manipulation
Tier 2 DeFi: TWAP Manipulation, Sandwich Frontrun, Governance Attack
Tier 3 Proxy: Proxy Init Frontrun, Timelock Bypass
Tier 4 Advanced: Bridge Forgery, EIP-712 Bypass, Paymaster Exploit, V4 Hook Exploit
Tier 5 L2: Sequencer Censorship, Storage Collision

### Multi-Chain Support
- EVM/Solidity (full production) + StarkNet/Cairo (alpha, 8 detectors)
- ChainAdapter ABC with IR layer for chain-agnostic analysis
- Supported chains: Ethereum, StarkNet (more planned: Solana, Sui, Polkadot)

### 5 Bounty Platforms
Immunefi (02), Code4rena (18), Sherlock (19), Cantina (20), Hats Finance (21)

### Your Skills (10 available)
fetch_program, fetch_source, scan_contract, analyze_findings, classify_finding,
exploit_test, generate_report, notify, deduplicate_findings, delegate_task

### Your Memory System
5 stores: Working (in-memory, per-session), Episodic (JSON, audit history),
Semantic (in-memory, accumulated), Vector (TF-IDF, semantic search),
Graph (nodes/edges, vulnerability relationships)

### Current State (June 2026)
- 28/28 services have tests (100% coverage)
- 117 tests total (54 unit + 16 integration + 8 E2E)
- CI pipeline hardened (no false-green masking)
- vyper_lib centralized (duplicate models eliminated)
- Docker security improved (755 permissions)
- SSE real-time pipeline streaming to dashboard

### Honest Limitations
1. No formal verification capability
2. External tool dependency (Slither, Mythril, Echidna — containerized)
3. JSON storage (migration to PostgreSQL planned)
4. Solo developer (bus factor = 1)
5. No billing/payment system
6. No authentication (local-first design)
7. Computation-heavy for large contracts

### Strategic Roadmap (Vyper OP)
Phase 1 (Foundation): Multi-chain expansion, exploit library completion, 5 bounty platforms
Phase 2 (Competitive): Formal verification engine, real-time monitoring, AI reasoning
Phase 3 (Dominance): CI/CD integration, community platform, DAO governance, pricing
"""


# ── Chat System Prompt ──────────────────────────────────────

CHAT_SYSTEM_PROMPT = """You are Antonio, the AI controller of Vyper — an automated smart contract security audit platform.

## Your Identity
- You are the central AI agent of Vyper, a microservice-based audit platform
- You are an expert in smart contract security, DeFi vulnerabilities, and Web3 security
- You speak conversationally, match the user's language, and are helpful but honest

{vyper_knowledge}

## How You Work — TWO MODES

You operate in two modes. **Always default to MODE 1** unless the user explicitly asks for something that requires platform data.

### MODE 1: Direct Answer (GENERAL KNOWLEDGE) — USE THIS BY DEFAULT
Use this mode for ANY question that does NOT require calling platform services:
- Questions about Vyper itself (architecture, roadmap, capabilities, limitations)
- Questions about smart contract security (vulnerability types, attack vectors, best practices)
- Strategic recommendations (how to improve Vyper, what tools to use)
- Web3/DeFi knowledge (how protocols work, recent exploits, security trends)
- Troubleshooting help (configuration, setup, error explanations)
- "What is X?", "How does Y work?", "Why is Z?", "Give me recommendations for..."
- ANY conversational question, greeting, or general discussion

**In MODE 1:** Immediately set action to "FINAL_ANSWER" and provide a thorough, knowledgeable response.
Do NOT call any skills. Answer from your own expertise.
This should be your FIRST step — don't loop.

### MODE 2: Skill-Based (PLATFORM DATA) — ONLY when truly needed
Use this mode ONLY when the user explicitly wants you to:
- Audit a specific contract: "audit 0x1234..."
- Fetch programs: "show me Immunefi programs"
- Scan code: "scan this contract"
- Generate a report: "generate report for audit_xxx"
- Search memory: "what did we find in the last audit?"
- Run exploit tests: "test reentrancy on 0x..."
- Check daemon/health: "is the daemon running?"

**In MODE 2:** Use the ReAct pattern:
1. THINK — what does the user want?
2. ACT — call the right skill with parameters
3. OBSERVE — process the result
4. REPEAT if needed, then FINAL_ANSWER

## Available Skills (for MODE 2 only)

{s Skills}

## Critical Rules

1. **DEFAULT TO MODE 1**: If you're unsure whether to use a skill, DON'T. Answer directly.
2. **LANGUAGE MATCHING**: Always respond in the same language the user used.
   - Indonesian user → Indonesian response
   - English user → English response
3. **BE HONEST**: If you don't know something, say so. Don't fabricate audit results.
4. **BE CONVERSATIONAL**: You're having a chat, not running a script. Be warm and helpful.
5. **NO SKILL FORCING**: Never call a skill just because it exists. Only call when the user's intent clearly maps to it.
6. **ONE STEP FOR DIRECT ANSWERS**: For MODE 1 questions, always answer in step 1 with FINAL_ANSWER.
7. **PROVIDE CONTEXT**: When answering broad questions, be thorough. Give examples. Suggest next steps.

## When Using Skills (MODE 2 data integrity rules)

When you call a skill and receive a result with counts, lists, or totals:
- ALWAYS report the ACTUAL count from the skill's output, not a curated subset
- If a skill returns `_total_count`, include it: "Found X of Y programs"
- If a skill returns `_summary`, use that as the primary data point
- When user asks to "list all" or "show all", report the actual data from the skill
- Do NOT summarize to only well-known programs unless the user asks for that explicitly
- If the result is too large, tell the user: "Returned X items. Use filters to narrow down."

## Output Format

You MUST respond with valid JSON:
{{
  "thought": "your reasoning here (explain which mode and why)",
  "action": "skill_name or FINAL_ANSWER",
  "action_input": {{ "param": "value" or null }},
  "final_answer": "your conversational response or null"
}}

For MODE 1: action = "FINAL_ANSWER", final_answer = your detailed response.
For MODE 2: follow the ReAct pattern, then FINAL_ANSWER with a summary.
"""


class AgentReasoningClient:
    """Multi-provider LLM client for agent reasoning (ReAct think step).

    Fully provider-agnostic: reads all provider configs from a dict.
    Supports any provider configured via Settings UI.

    Provider types:
    - ``openai_compatible``: Uses /chat/completions endpoint (OpenAI, DeepSeek, xAI, etc.)
    - ``anthropic``: Uses Anthropic Messages API
    """

    def __init__(
        self,
        providers: dict[str, dict[str, str]] | None = None,
        preferred_provider: str = "",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize the LLM client.

        Args:
            providers: Dict of provider_id -> {api_key, base_url, model}.
                       If None, loaded from PROVIDER_DEFAULTS without keys.
            preferred_provider: The provider to use first (e.g. "deepseek", "openai").
            http_client: Shared httpx client for connection pooling.
        """
        self.providers: dict[str, dict[str, str]] = {}
        self.preferred_provider = preferred_provider or ""
        self._http_client = http_client

        # Merge defaults with actual config
        if providers:
            for pid, cfg in providers.items():
                defaults = PROVIDER_DEFAULTS.get(pid, {})
                api_key = cfg.get("api_key") or ""
                base_url_cfg = cfg.get("base_url") or ""
                base_url_default = defaults.get("base_url", "")

                # Use default base_url if config value is empty
                base_url = (base_url_cfg or base_url_default).rstrip("/")

                # Warn if API key is set but base_url was empty (common misconfig)
                if api_key and not base_url_cfg:
                    log.warning(
                        "provider_base_url_empty_using_default",
                        provider=pid,
                        default_base_url=base_url_default,
                        hint="Set base_url in Settings > AI Providers to avoid relying on defaults",
                    )

                self.providers[pid] = {
                    "api_key": api_key,
                    "base_url": base_url,
                    "model": cfg.get("model") or defaults.get("model", "unknown"),
                    "api_type": defaults.get("api_type", "openai_compatible"),
                }

        # Debug: log all configured providers with their effective URLs
        for pid, p in self.providers.items():
            if p.get("api_key"):
                log.info(
                    "llm_provider_configured",
                    provider=pid,
                    model=p.get("model", "?"),
                    base_url=p.get("base_url", "?"),
                )

    # ── Public API ──────────────────────────────────────────

    def is_configured(self) -> bool:
        """Check if at least one provider has an API key set."""
        return any(p.get("api_key") for p in self.providers.values())

    def configured_providers(self) -> list[str]:
        """Return list of provider IDs that have API keys."""
        return [pid for pid, p in self.providers.items() if p.get("api_key")]

    # ── Core Reasoning ─────────────────────────────────────

    async def reason(
        self,
        context: str,
        skills_desc: str,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Agent berpikir: given context, what to do next?

        Args:
            context: Current session context (working memory + history)
            skills_desc: Description of available skills
            max_retries: Max retry on parse failure

        Returns:
            Dict with keys: thought, action, action_input, final_answer
        """
        system_prompt = REACT_SYSTEM_PROMPT.replace("{s Skills}", skills_desc)
        user_prompt = f"## Context\n\n{context}\n\n## Task\n\nWhat should I do next?"

        last_error: str | None = None

        for attempt in range(max_retries):
            try:
                raw = await self._call_llm(system_prompt, user_prompt)
                result = self._parse_response(raw)

                # Jika ada error dari attempt sebelumnya, tambahkan ke thought
                if last_error and result.get("action") != "FINAL_ANSWER":
                    result["thought"] = (
                        f"[Previous attempt failed: {last_error}]\n{result.get('thought', '')}"
                    )

                return result

            except Exception as exc:
                last_error = _safe_error(exc)
                log.warning(
                    "agent_reason_retry",
                    attempt=attempt + 1,
                    error=last_error,
                    exc_info=True,
                )
                # Skip retry on auth errors — retrying won't fix bad credentials
                is_auth = (
                    "Authentication failed" in last_error
                    or "API key may be invalid" in last_error
                    or "No AI provider configured" in last_error
                )
                if is_auth:
                    log.error("agent_reason_auth_fatal", error=last_error)
                    break
                # Exponential backoff: 1s, 2s, 4s, ... between retries
                if attempt < max_retries - 1:
                    wait = min(2 ** attempt, 16)  # cap at 16s
                    log.debug("agent_reason_backoff", wait_seconds=wait)
                    await asyncio.sleep(wait)
                continue

        # Fallback: return error action
        return {
            "thought": f"Failed to reason after {max_retries} attempts: {last_error}",
            "action": "FINAL_ANSWER",
            "action_input": None,
            "final_answer": f"Error: Could not process request - {last_error}",
        }

    # ── LLM Router ──────────────────────────────────────────

    async def _call_llm(self, system: str, user: str) -> str:
        """Call the preferred LLM provider, with fallback if unavailable.

        Each provider is tried with up to 2 retries (3 total attempts)
        before moving to the next configured provider.
        """
        # Build ordered list: preferred first, then all other configured providers
        ordered: list[str] = []
        if self.preferred_provider and self.providers.get(self.preferred_provider, {}).get("api_key"):
            ordered.append(self.preferred_provider)
        for pid in self.providers:
            if pid not in ordered and self.providers[pid].get("api_key"):
                ordered.append(pid)

        if not ordered:
            raise RuntimeError(
                "No AI provider configured. "
                "Go to Settings > AI Providers, set at least one API key, "
                "then set 'Preferred Provider' to the provider ID (e.g. 'deepseek')."
            )

        errors: list[str] = []

        for pid in ordered:
            provider = self.providers[pid]
            # Per-provider retry with backoff (max 3 attempts per provider)
            for attempt in range(3):
                try:
                    result = await self._call_provider(provider, system, user)
                    if pid != ordered[0]:
                        log.info("llm_fallback_success", from_provider=ordered[0], to_provider=pid)
                    return result
                except Exception as exc:
                    err_msg = _safe_error(exc)
                    # Skip retry on auth errors — retrying with bad key won't help
                    is_auth_error = (
                        isinstance(exc, RuntimeError)
                        and ("Authentication failed" in err_msg
                             or "API key may be invalid" in err_msg
                             or "API key missing" in err_msg)
                    )
                    if is_auth_error:
                        log.error(
                            "llm_auth_error",
                            provider=pid,
                            error=err_msg,
                        )
                        errors.append(f"{pid}: {err_msg}")
                        break  # Stop retrying this provider, try next one

                    if attempt < 2:  # more retries remain
                        wait = min(2 ** attempt, 8)  # 1s, 2s, 4s max
                        log.warning(
                            "llm_call_retry",
                            provider=pid,
                            attempt=attempt + 1,
                            error=err_msg,
                            wait_seconds=wait,
                        )
                        await asyncio.sleep(wait)
                    else:
                        log.error(
                            "llm_call_exhausted",
                            provider=pid,
                            error=err_msg,
                            exc_info=True,
                        )
                        errors.append(f"{pid}: {err_msg}")

        # All providers exhausted
        error_summary = "; ".join(errors) if errors else "Unknown error"
        raise RuntimeError(
            f"All LLM providers failed: {error_summary}. "
            f"Check your API keys, network connectivity, and provider status."
        )

    async def _call_provider(self, provider: dict[str, str], system: str, user: str) -> str:
        """Route to the correct API caller based on provider type."""
        if provider.get("api_type") == "anthropic":
            return await self._call_anthropic(provider, system, user)
        return await self._call_openai_compatible(provider, system, user)

    # ── OpenAI-Compatible Caller ────────────────────────────

    async def _call_openai_compatible(
        self, provider: dict[str, str], system: str, user: str
    ) -> str:
        """Call any OpenAI-compatible /chat/completions endpoint.

        Works with: OpenAI, DeepSeek, xAI/Grok, OpenRouter, HuggingFace, etc.
        """
        api_key = provider.get("api_key", "")
        base_url = provider.get("base_url", "")
        model = provider.get("model", "")

        if not api_key:
            raise RuntimeError(f"API key missing for provider at {base_url}")
        if self._http_client is None:
            raise RuntimeError("HTTP client not initialized")
        if not base_url:
            raise RuntimeError(f"base_url not configured for provider with model '{model}'")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": 2048,
            "temperature": 0.2,
        }

        url = f"{base_url}/chat/completions"
        log.info(
            "llm_call_openai_compatible",
            model=model,
            base_url=base_url,
        )

        try:
            resp = await self._http_client.post(
                url,
                headers=headers,
                json=body,
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError(
                    f"Unexpected API response from {base_url}: {exc}. "
                    f"Response keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}"
                ) from exc
        except httpx.TimeoutException:
            raise RuntimeError(
                f"LLM request timed out after {DEFAULT_TIMEOUT}s to {base_url}. "
                f"The provider may be overloaded or unreachable."
            )
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = ""
            try:
                detail = exc.response.text[:500]
            except Exception:
                pass
            if status == 429:
                raise RuntimeError(
                    f"Rate limited by {base_url} (HTTP 429). "
                    f"Retry will happen automatically with backoff."
                )
            if status in (401, 403):
                raise RuntimeError(
                    f"Authentication failed for {base_url} (HTTP {status}). "
                    f"Your API key may be invalid or expired. Check Settings > AI Providers."
                )
            raise RuntimeError(
                f"HTTP {status} from {base_url}: {detail or exc.response.reason_phrase}"
            )

    # ── Anthropic Caller ────────────────────────────────────

    async def _call_anthropic(
        self, provider: dict[str, str], system: str, user: str
    ) -> str:
        """Call Anthropic Messages API."""
        api_key = provider.get("api_key", "")
        base_url = provider.get("base_url", "")
        model = provider.get("model", "")

        if not api_key:
            raise RuntimeError("Anthropic API key missing")
        if self._http_client is None:
            raise RuntimeError("HTTP client not initialized")
        if not base_url:
            raise RuntimeError(f"base_url not configured for Anthropic provider with model '{model}'")

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "max_tokens": 2048,
            "temperature": 0.2,
        }

        url = f"{base_url}/messages"
        try:
            resp = await self._http_client.post(
                url,
                headers=headers,
                json=body,
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            try:
                return data["content"][0]["text"]
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError(
                    f"Unexpected Anthropic response from {base_url}: {exc}. "
                    f"Response keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}"
                ) from exc
        except httpx.TimeoutException:
            raise RuntimeError(
                f"Anthropic request timed out after {DEFAULT_TIMEOUT}s. "
                f"The provider may be overloaded or unreachable."
            )
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = ""
            try:
                detail = exc.response.text[:500]
            except Exception:
                pass
            if status == 429:
                raise RuntimeError(
                    f"Rate limited by Anthropic (HTTP 429). "
                    f"Retry will happen automatically with backoff."
                )
            if status in (401, 403):
                raise RuntimeError(
                    f"Anthropic authentication failed (HTTP {status}). "
                    f"Your API key may be invalid or expired. Check Settings > AI Providers."
                )
            raise RuntimeError(
                f"Anthropic HTTP {status}: {detail or exc.response.reason_phrase}"
            )

    # ── Parse ──────────────────────────────────────────────

    def _parse_response(self, raw: str) -> dict[str, Any]:
        """Parse LLM response into structured action dict.

        Attempts JSON parsing first, then falls back to
        text-based parsing for non-JSON responses.

        All string values are cleaned of escape sequences
        (\\n → newline, \\u201c → smart quote, etc.)
        """
        text = raw.strip()

        # Try JSON first
        if text.startswith("{"):
            try:
                result = json.loads(text)
                return _deep_unescape(result)
            except json.JSONDecodeError:
                pass

        # Fallback: parse text format
        lines = text.split("\n")
        result: dict[str, Any] = {
            "thought": "",
            "action": "FINAL_ANSWER",
            "action_input": None,
            "final_answer": text,
        }

        current_key = None
        for line in lines:
            line = line.strip()
            if line.upper().startswith("THOUGHT:"):
                result["thought"] = line[len("THOUGHT:"):].strip()
                current_key = "thought"
            elif line.upper().startswith("ACTION:"):
                result["action"] = line[len("ACTION:"):].strip()
                current_key = "action"
            elif line.upper().startswith("ACTION_INPUT:"):
                try:
                    input_str = line[len("ACTION_INPUT:"):].strip()
                    result["action_input"] = json.loads(input_str)
                except json.JSONDecodeError:
                    result["action_input"] = {"data": input_str}
                current_key = "action_input"
            elif line.upper().startswith("OBSERVATION:"):
                current_key = None
            elif line.upper().startswith("FINAL_ANSWER:"):
                result["action"] = "FINAL_ANSWER"
                result["final_answer"] = line[len("FINAL_ANSWER:"):].strip()
            elif current_key and line and not line.startswith("```"):
                if isinstance(result.get(current_key), str):
                    result[current_key] += " " + line

        return _deep_unescape(result)

    # ── Custom Reasoning ────────────────────────────────────

    async def reason_custom(
        self,
        system_prompt: str,
        context: str,
        skills_desc: str = "",
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Agent reasoning with a custom system prompt.

        Args:
            system_prompt: Full system prompt (role-specific)
            context: Current context
            skills_desc: Skill descriptions (optional, can be in prompt already)
            max_retries: Max retry on parse failure

        Returns:
            Dict with keys: thought, action, action_input, final_answer
        """
        user_prompt = f"## Context\n\n{context}\n\n## Task\n\nWhat should I do next?"
        last_error: str | None = None

        for attempt in range(max_retries):
            try:
                raw = await self._call_llm(system_prompt, user_prompt)
                result = self._parse_response(raw)

                if last_error and result.get("action") != "FINAL_ANSWER":
                    result["thought"] = (
                        f"[Previous attempt failed: {last_error}]\n{result.get('thought', '')}"
                    )

                return result

            except Exception as exc:
                last_error = _safe_error(exc)
                log.warning(
                    "agent_reason_custom_retry",
                    attempt=attempt + 1,
                    error=last_error,
                    exc_info=True,
                )
                # Skip retry on auth errors — retrying won't fix bad credentials
                is_auth = (
                    "Authentication failed" in last_error
                    or "API key may be invalid" in last_error
                    or "No AI provider configured" in last_error
                )
                if is_auth:
                    log.error("agent_reason_custom_auth_fatal", error=last_error)
                    break
                # Exponential backoff: 1s, 2s, 4s, ... between retries
                if attempt < max_retries - 1:
                    wait = min(2 ** attempt, 16)  # cap at 16s
                    log.debug("agent_reason_custom_backoff", wait_seconds=wait)
                    await asyncio.sleep(wait)
                continue

        return {
            "thought": f"Failed to reason after {max_retries} attempts: {last_error}",
            "action": "FINAL_ANSWER",
            "action_input": None,
            "final_answer": f"Error: Could not process request - {last_error}",
        }

    # ── Reflection ──────────────────────────────────────────

    async def reflect(self, session_summary: str) -> str:
        """Agent反思: evaluate how the session went.

        Args:
            session_summary: Summary of what happened

        Returns:
            Reflection text with lessons learned
        """
        prompt = (
            "Reflect on this audit session. What went well? "
            "What could be improved? What patterns did you learn?\n\n"
            f"Session: {session_summary}"
        )
        return await self._call_llm(
            "You are a self-improving security audit agent. Reflect honestly.",
            prompt,
        )
