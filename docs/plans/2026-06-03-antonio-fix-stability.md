# Antonio Stability Fix — Implementation Plan ✅ COMPLETED 2026-06-03

> **Status: 7/9 task selesai, 2 di-skip (non-critical).** Semua Docker image sudah rebuild.

> **For Opencode:** Use the task tool to dispatch each task to a subagent for implementation.

**Goal:** Fix 4 critical failures that prevent Antonio from completing user audit requests reliably.

**Root Causes (from lore-master analysis):**
1. LLM provider misconfiguration (DeepSeek + Anthropic URL mix)
2. Circuit breaker blocks source fetch after few failures
3. Antonio only shows 4 of 234+ Immunefi programs
4. Antonio doesn't validate user-provided address against Immunefi program contracts

**Architecture:** All fixes are in `services/14-agent/` (Antonio service) except Task 1 (Config Service) and Task 8 (Immunefi service). Each fix is independent.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2

---

## 🐳 ATURAN DOCKER IMAGE — WAJIB SETIAP PERUBAHAN

> **Setiap kali selesai implementasi 1 task (atau batch task yang modify service yang sama), WAJIB rebuild Docker image dan restart service.**

### Perintah Dasar

```bash
# 1. Build ulang image service yang berubah
docker compose build <service-name>

# 2. Restart service dengan image baru
docker compose up -d <service-name>

# 3. Cek log untuk verifikasi
docker compose logs -f <service-name> --tail 50
```

### Mapping Service Name ↔ Directory

| Directory | docker-compose Service Name |
|-----------|---------------------------|
| `services/14-agent/` | `agent` (or `14-agent`) |
| `services/01-config/` | `config` (or `01-config`) |
| `services/02-immunefi/` | `immunefi` (or `02-immunefi`) |
| `services/03-source/` | `source` (or `03-source`) |
| `services/15-dashboard/` | `dashboard` (or `15-dashboard`) |

> Cek nama service yang tepat di `docker-compose.yml`.

### Contoh Rebuild + Restart

```bash
# Setelah mengubah file di services/14-agent/
docker compose build 14-agent
docker compose up -d 14-agent
docker compose logs -f 14-agent --tail 50
```

### Rules
1. **1 task → 1 build** — Jangan tumpuk perubahan tanpa rebuild
2. **Cek log setelah restart** — Pastikan service started dengan sukses
3. **Jika multi-service berubah** — Rebuild semua service yang berubah dalam 1 batch
4. **Gunakan `--no-cache` jika perlu** — `docker compose build --no-cache <service>` untuk fresh build

---

## Task List (Ordered by Priority)

### 🔴 TASK 1: Validate Provider Config at Antonio Startup

**Objective:** Prevent Antonio from starting with a clearly wrong provider URL (e.g., `api.deepseek.com/anthropic`).

**Files:**
- Modify: `services/14-agent/app.py` around line 120-162 (`_load_providers` function)
- Create: `services/14-agent/tests/test_provider_validation.py`

**Step 1: Write failing test**

Create file `services/14-agent/tests/test_provider_validation.py`:

```python
"""Tests for provider config validation logic."""

import pytest
from app import _validate_provider_urls  # we'll create this


def test_detect_cross_provider_url_mix():
    """Detect when a provider's base_url uses another provider's domain."""
    providers = {
        "anthropic": {
            "api_key": "sk-test",
            "base_url": "https://api.deepseek.com/anthropic",  # BUG: DeepSeek domain for Anthropic
            "model": "claude-3-5-sonnet-20241022",
            "api_type": "openai_compatible",
        }
    }
    errors = _validate_provider_urls(providers)
    assert len(errors) >= 1
    assert "deepseek" in errors[0].lower() or "anthropic" in errors[0].lower()


def test_valid_openai_passes():
    """Valid OpenAI config should pass validation."""
    providers = {
        "openai": {
            "api_key": "sk-test",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
            "api_type": "openai_compatible",
        }
    }
    errors = _validate_provider_urls(providers)
    assert len(errors) == 0


def test_valid_anthropic_passes():
    """Valid Anthropic config should pass validation."""
    providers = {
        "anthropic": {
            "api_key": "sk-test",
            "base_url": "https://api.anthropic.com/v1",
            "model": "claude-3-5-sonnet-20241022",
            "api_type": "anthropic",
        }
    }
    errors = _validate_provider_urls(providers)
    assert len(errors) == 0


def test_detect_wrong_api_type():
    """Detect when anthropic provider uses openai_compatible api_type."""
    providers = {
        "anthropic": {
            "api_key": "sk-test",
            "base_url": "https://api.anthropic.com/v1",
            "model": "claude-3-5-sonnet-20241022",
            "api_type": "openai_compatible",  # BUG: should be "anthropic"
        }
    }
    errors = _validate_provider_urls(providers)
    assert len(errors) >= 1
```

**Step 2: Run test to verify failure**

```bash
cd services/14-agent
pip install pytest pytest-asyncio
pytest tests/test_provider_validation.py -v
```
Expected: ModuleNotFoundError or ImportError (function doesn't exist yet)

**Step 3: Add validation function to `app.py`**

Add BEFORE the `_load_providers` function (around line 119):

```python
# ── Provider URL Validation ──────────────────────────────────

# Known domain-to-provider mapping for validation
KNOWN_PROVIDER_DOMAINS: dict[str, str] = {
    "api.openai.com": "openai",
    "api.anthropic.com": "anthropic",
    "api.deepseek.com": "deepseek",
    "api.x.ai": "xai",
    "openrouter.ai": "openrouter",
    "generativelanguage.googleapis.com": "google",
    "api-inference.huggingface.co": "huggingface",
}


def _validate_provider_urls(providers: dict[str, dict[str, str]]) -> list[str]:
    """Validate provider configurations for common mistakes.

    Checks:
    1. Anthropic provider must use api_type="anthropic"
    2. Provider's base_url domain should match its provider id
    3. No two providers should have the same base_url (unless intentional)

    Returns:
        List of validation error messages (empty = all good)
    """
    errors: list[str] = []

    for pid, cfg in providers.items():
        base_url = cfg.get("base_url", "")
        api_type = cfg.get("api_type", "openai_compatible")
        api_key = cfg.get("api_key", "")

        if not api_key:
            continue  # Skip unconfigured providers

        # Check 1: Anthropic api_type mismatch
        if pid == "anthropic" and api_type != "anthropic":
            errors.append(
                f"Provider '{pid}': api_type should be 'anthropic' not '{api_type}'. "
                f"Set api_type='anthropic' in PROVIDER_DEFAULTS."
            )

        # Check 2: Domain-provider mismatch
        if base_url:
            for domain, expected_provider in KNOWN_PROVIDER_DOMAINS.items():
                if domain in base_url and pid != expected_provider:
                    errors.append(
                        f"Provider '{pid}': base_url contains '{domain}' "
                        f"which belongs to '{expected_provider}'. "
                        f"Did you mean to use provider '{expected_provider}'?"
                    )

        # Check 3: Non-OpenAI base URL with openai_compatible type
        if api_type == "openai_compatible" and base_url:
            is_openai_domain = any(d in base_url for d in KNOWN_PROVIDER_DOMAINS)
            if not is_openai_domain and not base_url.startswith("http://localhost"):
                errors.append(
                    f"Provider '{pid}': base_url '{base_url}' is not a recognized domain. "
                    f"If this is a custom endpoint, ignore this warning."
                )

    return errors
```

**Step 4: Integrate into `_load_providers`**

Modify `_load_providers` function (line 120-162). After collecting all provider configs, add validation:

Find the end of `_load_providers` function (line ~162, the `return providers`):

```python
    # ── ADD THIS BLOCK ──
    # Validate provider configs
    validation_errors = _validate_provider_urls(providers)
    if validation_errors:
        log.warning(
            "provider_config_issues",
            errors=validation_errors,
            action="Agent may fail to connect to LLM. Check Settings > AI Providers.",
        )
        for err in validation_errors:
            log.warning("provider_config_error", detail=err)
    # ── END ADD ──

    return providers
```

**Step 5: Run tests to verify pass**

```bash
cd services/14-agent
pytest tests/test_provider_validation.py -v
```
Expected: 4 passed

**Step 6: Rebuild Docker image & restart**

```bash
# Rebuild agent service dengan kode baru
docker compose build 14-agent

# Restart service
docker compose up -d 14-agent

# Verifikasi startup log
docker compose logs -f 14-agent --tail 30
```
Expected: Log menunjukkan `provider_config_issues` hanya jika ada misconfig, tidak ada error startup.

**Step 7: Commit**

```bash
git add services/14-agent/app.py services/14-agent/tests/test_provider_validation.py
git commit -m "fix(antonio): add provider config validation to detect URL misconfiguration"
```

---

### 🔴 TASK 2: Reset Provider Config via API Endpoint

**Objective:** Add an endpoint to reset provider config to safe defaults so user can recover from misconfiguration without editing files.

**Files:**
- Modify: `services/14-agent/app.py` (add new endpoint)
- Modify: `services/01-config/app.py` (add reset endpoint)

**Step 1: Add GET /agent/provider-defaults endpoint in 14-agent**

Add this endpoint AFTER the `/agent/manifest` endpoint (after line 379):

```python
@app.get("/agent/provider-defaults")
async def provider_defaults() -> ApiResponse:
    """Get the default provider configuration values.

    Returns the PROVIDER_DEFAULTS dict so the frontend can
    reset misconfigured providers to known-good values.
    """
    from src.llm import PROVIDER_DEFAULTS

    return _ok({
        "defaults": PROVIDER_DEFAULTS,
        "note": "Set base_url and api_type to these defaults to fix misconfiguration",
    })
```

**Step 2: Add POST /config/reset-providers endpoint in 01-config**

Read `services/01-config/app.py` and find the right location to add:

```python
@app.post("/config/reset-providers")
async def reset_providers() -> ApiResponse:
    """Reset all provider configs to factory defaults.

    This clears provider_openai_*, provider_anthropic_*, etc.
    User will need to re-enter API keys.
    """
    from src.manager import ConfigManager  # adjust import as needed

    provider_keys = [
        "provider_openai_api_key", "provider_openai_base_url", "provider_openai_model",
        "provider_anthropic_api_key", "provider_anthropic_base_url", "provider_anthropic_model",
        "provider_deepseek_api_key", "provider_deepseek_base_url", "provider_deepseek_model",
        "provider_xai_api_key", "provider_xai_base_url", "provider_xai_model",
        "provider_openrouter_api_key", "provider_openrouter_base_url", "provider_openrouter_model",
        "provider_google_api_key", "provider_google_base_url", "provider_google_model",
        "provider_huggingface_api_key", "provider_huggingface_base_url", "provider_huggingface_model",
    ]

    cleared = 0
    for key in provider_keys:
        try:
            # Adjust this call to match how ConfigManager deletes keys
            # e.g., config_manager.delete(key)
            cleared += 1
        except Exception:
            pass

    return ok({
        "message": f"Cleared {cleared} provider config keys. Re-enter API keys in Settings.",
        "cleared_keys": cleared,
    })
```

**Note:** Adjust the ConfigManager call to match the actual API of `services/01-config/src/manager.py`.

**Step 3: Rebuild Docker & restart (14-agent + 01-config)**

```bash
# Rebuild kedua service yang berubah
docker compose build 14-agent 01-config

# Restart
docker compose up -d 14-agent 01-config

# Verifikasi
docker compose logs -f 14-agent --tail 20
```

**Step 4: Commit**

```bash
git add services/14-agent/app.py services/01-config/app.py
git commit -m "feat(antonio): add provider reset endpoint for recovering from misconfiguration"
```

---

### 🟡 TASK 3: Tune Circuit Breaker Parameters

**Objective:** Make circuit breaker more resilient — increase failure threshold and add smart retry.

**Files:**
- Modify: `services/14-agent/src/skills/base.py`

**Step 1: Increase failure threshold and recovery timeout**

Modify the `execute` method in `base.py` (around line 125-181). Find the circuit breaker check at line 145:

```python
# ── Circuit breaker check ──
cb = circuit_breaker(f"skill:{self.name}")
```

Replace the circuit breaker section (lines 145-154) with:

```python
# ── Circuit breaker check ──
# Use different thresholds based on skill type
skill_name = self.name
if skill_name in ("fetch_source", "fetch_program"):
    # External API calls need higher tolerance
    cb = circuit_breaker(
        f"skill:{skill_name}",
        failure_threshold=10,      # default was 5
        recovery_timeout=60.0,     # default was 30s
        half_open_max_calls=3,
    )
else:
    cb = circuit_breaker(
        f"skill:{skill_name}",
        failure_threshold=5,
        recovery_timeout=30.0,
        half_open_max_calls=3,
    )

if cb.state == "OPEN":
    if time.time() - cb.last_failure_time > cb.recovery_timeout:
        cb.state = "HALF_OPEN"
    else:
        remaining = int(cb.recovery_timeout - (time.time() - cb.last_failure_time))
        # Log warning but don't throw — let it try anyway for fetch_source
        # If it's a network issue, retry might work
        if skill_name in ("fetch_source", "fetch_program"):
            log.warning(
                "circuit_breaker_open_but_retrying",
                skill=skill_name,
                remaining_s=remaining,
            )
            # Force HALF_OPEN to allow retry
            cb.state = "HALF_OPEN"
            cb._half_open_calls = 0
        else:
            raise Exception(
                f"Circuit breaker OPEN for {self.name} "
                f"(retry in {remaining}s)"
            )
```

**Step 2: Rebuild Docker & restart**

```bash
docker compose build 14-agent
docker compose up -d 14-agent
docker compose logs -f 14-agent --tail 30
```
Expected: Log menunjukkan circuit breaker initialized dengan threshold baru.

**Step 3: Commit**

```bash
git add services/14-agent/src/skills/base.py
git commit -m "fix(antonio): tune circuit breaker for fetch_source (threshold=10, timeout=60s)"
```

---

### 🟡 TASK 4: Add Retry Logic to FetchSourceSkill

**Objective:** Add exponential backoff retry when source fetch fails due to transient errors.

**Files:**
- Modify: `services/14-agent/src/skills/fetch_source.py`

**Step 1: Modify `FetchSourceSkill.run()` to add retry**

Replace the `run` method (lines 60-97) with:

```python
async def run(self, **kwargs: Any) -> Any:
    body: dict[str, Any] = {}

    if kwargs.get("address") and kwargs.get("chain"):
        body["address"] = kwargs["address"]
        body["chain"] = kwargs["chain"]
    elif kwargs.get("url"):
        body["url"] = kwargs["url"]
    elif kwargs.get("program_slug"):
        body["program_slug"] = kwargs["program_slug"]
    else:
        return {"error": "Provide address+chain, url, or program_slug"}

    if kwargs.get("contract_name"):
        body["contract_name"] = kwargs["contract_name"]

    # ── Retry with exponential backoff ──
    max_retries = 3
    last_error: str | None = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = await self._client.post(f"{SOURCE_URL}/fetch", json=body)
            resp.raise_for_status()
            data = resp.json()

            result: dict[str, Any] = {
                "files": {},
                "compiler": None,
                "contract_name": None,
            }

            source_data = data.get("data", {})
            if isinstance(source_data, dict):
                result["files"] = source_data.get("files", {})
                result["compiler"] = source_data.get("compiler_version")
                result["contract_name"] = source_data.get("contract_name")
                result["source_path"] = source_data.get("source_path")

            file_count = len(result["files"])
            file_names = list(result["files"].keys())
            result["_summary"] = f"Found {file_count} file(s): {', '.join(file_names[:5])}"

            return result

        except httpx.HTTPStatusError as exc:
            last_error = str(exc)
            if exc.response.status_code == 404:
                # Not found — no point retrying
                return {"error": f"Contract not found: {exc}"}
            if exc.response.status_code == 429:
                # Rate limited — wait longer
                retry_after = int(exc.response.headers.get("Retry-After", str(2 ** attempt)))
                log.warning(
                    "fetch_source_rate_limited",
                    attempt=attempt,
                    retry_after=retry_after,
                )
                if attempt < max_retries:
                    await asyncio.sleep(retry_after)
                continue
            # Other HTTP errors — retry
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)  # 2s, 4s, 8s
                continue
            raise

        except (httpx.RequestError, httpx.TimeoutException) as exc:
            last_error = str(exc)
            log.warning(
                "fetch_source_connection_error",
                attempt=attempt,
                error=str(exc),
            )
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)  # 2s, 4s, 8s
                continue
            raise

    return {"error": f"Failed after {max_retries} retries: {last_error}"}
```

Add import at top of file:

```python
import asyncio
import httpx
```

**Step 2: Rebuild Docker & restart**

```bash
docker compose build 14-agent
docker compose up -d 14-agent
docker compose logs -f 14-agent --tail 30
```
Expected: Log menunjukkan agent started dengan fetch_source skill terdaftar.

**Step 3: Commit**

```bash
git add services/14-agent/src/skills/fetch_source.py
git commit -m "fix(antonio): add exponential backoff retry to FetchSourceSkill"
```

---

### 🟡 TASK 5: Fix System Prompt — Always Show Total Program Count

**Objective:** When user asks to list programs, Antonio must show the actual total count from the skill result.

**Files:**
- Modify: `services/14-agent/src/llm.py`

**Step 1: Add instruction to CHAT_SYSTEM_PROMPT**

Find `CHAT_SYSTEM_PROMPT` (line 162). After the Guidelines section (around line 199), add:

```python
## Data Integrity Rules

7. When listing programs, contracts, or findings from a skill result:
   - ALWAYS report the ACTUAL count from the skill's output, not a curated subset
   - Format: "Found X of Y programs: [list first N]"
   - If the user says "list all", list the actual data from the skill
   - Do NOT summarize to only well-known programs unless the user asks
```

**Step 2: Add instruction to REACT_SYSTEM_PROMPT**

Find `REACT_SYSTEM_PROMPT` (line 119). Add to the Rules section (after line 145):

```python
7. Always report actual counts from skill output, not curated summaries
8. When user asks to list data, return the complete skill result, not a subset
```

**Step 3: Add `_total_count` field to FetchProgramSkill output**

Modify `services/14-agent/src/skills/fetch_program.py` line 71:

Change:
```python
return {"programs": data.get("data", []), "count": len(data.get("data", []))}
```

To:
```python
programs_list = data.get("data", [])
total = data.get("total", len(programs_list))
return {
    "programs": programs_list,
    "count": len(programs_list),
    "_total_count": total,
    "_summary": f"Returned {len(programs_list)} of {total} programs. Use search or filter to narrow down."
}
```

**Step 4: Rebuild Docker & restart**

```bash
docker compose build 14-agent
docker compose up -d 14-agent
docker compose logs -f 14-agent --tail 30
```

**Step 5: Commit**

```bash
git add services/14-agent/src/llm.py services/14-agent/src/skills/fetch_program.py
git commit -m "fix(antonio): enforce data integrity — show actual total count from skills"
```

---

### 🟡 TASK 6: Address Cross-Validation in FetchSourceSkill

**Objective:** Before fetching source code, verify that the user-provided address matches the Immunefi program's registered contracts.

**Files:**
- Modify: `services/14-agent/src/skills/fetch_source.py`
- Modify: `services/14-agent/src/skills/fetch_program.py`

**Step 1: Add `verify_address` method to FetchSourceSkill**

Add to `services/14-agent/src/skills/fetch_source.py`, inside the class, before `run()`:

```python
async def _verify_address_for_program(
    self, address: str, program_slug: str | None
) -> dict[str, Any] | None:
    """Verify that an address belongs to a known Immunefi program.

    If program_slug is provided, checks against that program's contracts.
    If no program_slug, searches across all programs.

    Returns:
        Dict with match info if found, None if not found,
        dict with error if verification failed.
    """
    if not program_slug:
        return None  # No program to verify against

    try:
        resp = await self._client.get(
            f"{IMMUNEFI_URL}/programs/{program_slug}/contracts"
        )
        if resp.status_code != 200:
            return None

        data = resp.json().get("data", {})
        contracts = data.get("contracts", [])

        address_lower = address.lower()
        for contract in contracts:
            if contract.get("address", "").lower() == address_lower:
                return {
                    "match": True,
                    "program_slug": program_slug,
                    "contract_name": contract.get("name", ""),
                    "chain": contract.get("chain", ""),
                }

        # No match found
        valid_addresses = [c.get("address", "") for c in contracts[:5]]
        return {
            "match": False,
            "program_slug": program_slug,
            "message": f"Address {address} is NOT a registered contract for {program_slug}. "
                       f"Valid contracts include: {', '.join(valid_addresses)}",
        }
    except Exception as exc:
        log.warning("address_verification_failed", error=str(exc))
        return None  # Non-blocking — proceed with fetch anyway
```

Add import at top of file:

```python
IMMUNEFI_URL = "http://02-immunefi:8000"
```

(Already have `SOURCE_URL = "http://03-source:8002"` — add the immunefi URL)

**Step 2: Call verification in `run()` method**

At the beginning of `run()`, add:

```python
async def run(self, **kwargs: Any) -> Any:
    address = kwargs.get("address", "")
    chain = kwargs.get("chain", "")
    program_slug = kwargs.get("program_slug", "")

    # ── Address verification ──
    if address and program_slug:
        verification = await self._verify_address_for_program(address, program_slug)
        if verification and not verification.get("match"):
            return {
                "warning": verification["message"],
                "_verification": verification,
                "suggestion": "Use fetch_program to get the correct contract addresses",
            }
        if verification and verification.get("match"):
            log.info(
                "address_verified",
                address=address,
                program=program_slug,
                contract=verification.get("contract_name"),
            )

    body: dict[str, Any] = {}
    # ... rest of method unchanged
```

**Step 3: Add program_slug parameter to fetch_program detail response**

Modify `services/14-agent/src/skills/fetch_program.py` `run()` method, in the `action == "detail"` section (lines 82-89):

```python
elif action == "detail":
    slug = kwargs.get("slug", "")
    if not slug:
        return {"error": "slug required for detail"}
    resp = await self._client.get(f"{IMMUNEFI_URL}/programs/{slug}")
    resp.raise_for_status()
    data = resp.json()
    program = data.get("data", {})
    # Ensure contracts list is always present
    if isinstance(program, dict) and "contracts" not in program:
        program["contracts"] = []
    return {"program": program}
```

**Step 4: Rebuild Docker & restart**

```bash
docker compose build 14-agent
docker compose up -d 14-agent
docker compose logs -f 14-agent --tail 30
```

**Step 5: Commit**

```bash
git add services/14-agent/src/skills/fetch_source.py services/14-agent/src/skills/fetch_program.py
git commit -m "fix(antonio): add address cross-validation against Immunefi program contracts"
```

---

### 🟢 TASK 7: Add Provider Status Endpoint to Dashboard Proxy

**Objective:** Allow user to see provider config status from the Dashboard without needing to read logs.

**Files:**
- Modify: `services/15-dashboard/src/proxy.py`

**Step 1: Add provider status route**

Find the right location in `proxy.py` and add:

```python
@router.get("/api/agent/provider-status")
async def agent_provider_status(request: Request):
    """Get Antonio's LLM provider configuration status.

    Returns which providers have API keys, their base URLs (truncated),
    and validation warnings.
    """
    async with httpx.AsyncClient() as client:
        # Get health info from Antonio
        health_resp = await client.get("http://14-agent:8000/health")
        health = health_resp.json()

        # Get provider defaults
        defaults_resp = await client.get("http://14-agent:8000/agent/provider-defaults")
        defaults = defaults_resp.json()

        # Get circuit breaker status
        cb_resp = await client.get("http://14-agent:8000/circuit-breakers")
        breakers = cb_resp.json()

    return {
        "health": health.get("data", {}),
        "defaults": defaults.get("data", {}),
        "circuit_breakers": breakers.get("data", {}),
    }
```

**Step 2: Rebuild Docker & restart (dashboard)**

```bash
docker compose build 15-dashboard
docker compose up -d 15-dashboard
docker compose logs -f 15-dashboard --tail 20
```

**Step 3: Commit**

```bash
git add services/15-dashboard/src/proxy.py
git commit -m "feat(dashboard): add provider status endpoint for monitoring LLM config"
```

---

### 🟢 TASK 8: Add Test Suite for All Fixes

**Objective:** Ensure all fixes have test coverage.

**Files:**
- Create: `services/14-agent/tests/test_circuit_breaker.py`
- Create: `services/14-agent/tests/test_fetch_source.py`

**Step 1: Test circuit breaker tuning**

Create `services/14-agent/tests/test_circuit_breaker.py`:

```python
"""Tests for circuit breaker behavior with different skill types."""

import time
from src.utils.circuit_breaker import CircuitBreaker


def test_default_threshold():
    """Default circuit breaker should have threshold=5."""
    cb = CircuitBreaker("test_default")
    assert cb.failure_threshold == 5
    assert cb.recovery_timeout == 30.0


def test_custom_threshold():
    """Custom parameters should be used when provided."""
    cb = CircuitBreaker("test_custom", failure_threshold=10, recovery_timeout=60.0)
    assert cb.failure_threshold == 10
    assert cb.recovery_timeout == 60.0


def test_open_after_threshold():
    """Circuit breaker opens after failure_threshold failures."""
    cb = CircuitBreaker("test_open", failure_threshold=3)
    assert cb.state == "CLOSED"

    for _ in range(3):
        cb.record_failure()

    assert cb.state == "OPEN"
    assert cb.can_call() is False


def test_half_open_after_timeout():
    """Circuit breaker transitions to HALF_OPEN after recovery_timeout."""
    cb = CircuitBreaker("test_half", failure_threshold=2, recovery_timeout=0.1)

    for _ in range(2):
        cb.record_failure()

    assert cb.state == "OPEN"
    assert cb.can_call() is False

    time.sleep(0.15)  # Wait for recovery timeout

    assert cb.can_call() is True
    assert cb.state == "HALF_OPEN"


def test_reset():
    """Reset should return to CLOSED state."""
    cb = CircuitBreaker("test_reset", failure_threshold=2)

    for _ in range(2):
        cb.record_failure()

    assert cb.state == "OPEN"

    cb.reset()
    assert cb.state == "CLOSED"
    assert cb.failure_count == 0
```

**Step 2: Run tests**

```bash
cd services/14-agent
pytest tests/test_circuit_breaker.py -v
```
Expected: 5 passed

**Step 3: (Test-only — no Docker rebuild needed)**

```bash
# Test files don't affect runtime — no rebuild required
# Tapi jalankan test dulu untuk memastikan pass
pytest services/14-agent/tests/test_circuit_breaker.py -v
```

**Step 4: Commit**

```bash
git add services/14-agent/tests/test_circuit_breaker.py
git commit -m "test(antonio): add circuit breaker unit tests"
```

---

### 🟢 TASK 9: Verify Provider Config in Settings UI (Frontend)

**Objective:** Add visual indicator in the Dashboard Settings page when provider config is invalid.

**Files:**
- Modify: `services/15-dashboard/frontend/src/pages/Settings.tsx` (approximate path)

**Step 1: Add validation warning**

Find the provider settings section in `Settings.tsx` and add a validation check:

```tsx
// After loading provider configs from the API
const [providerStatus, setProviderStatus] = useState<Record<string, {valid: boolean; warning?: string}>>({});

// On mount, check provider config validity
useEffect(() => {
    fetch('/api/agent/provider-defaults')
        .then(r => r.json())
        .then(data => {
            const defaults = data.data?.defaults || {};
            const status: Record<string, {valid: boolean; warning?: string}> = {};
            
            // Check each configured provider
            for (const [providerId, config] of Object.entries(providerConfigs)) {
                const def = defaults[providerId];
                if (def) {
                    const baseUrl = (config as any).base_url || '';
                    const expectedDomain = new URL(def.base_url).hostname;
                    
                    if (baseUrl && !baseUrl.includes(expectedDomain)) {
                        status[providerId] = {
                            valid: false,
                            warning: `Base URL doesn't match expected domain for ${providerId}. Expected: ${def.base_url}`
                        };
                    } else {
                        status[providerId] = { valid: true };
                    }
                }
            }
            
            setProviderStatus(status);
        })
        .catch(() => {});
}, [providerConfigs]);
```

Add a warning badge in the provider card:

```tsx
{providerStatus[providerId]?.valid === false && (
    <div className="rounded-md bg-red-50 p-3 mt-2">
        <div className="flex">
            <span className="text-red-400 mr-2">⚠️</span>
            <p className="text-sm text-red-700">{providerStatus[providerId].warning}</p>
        </div>
    </div>
)}
```

**Step 2: Rebuild Docker & restart (dashboard)**

```bash
# Frontend change — perlu rebuild image karena include node_modules
docker compose build 15-dashboard
docker compose up -d 15-dashboard
docker compose logs -f 15-dashboard --tail 30
```

**Step 3: Commit**

```bash
git add services/15-dashboard/frontend/src/pages/Settings.tsx
git commit -m "feat(dashboard): add provider config validation warning in Settings UI"
```

---

## Verification Plan

After all tasks are implemented, verify the fix end-to-end:

### Step 0: Rebuild semua service yang berubah

```bash
# Build ulang semua service yang dimodifikasi dalam plan ini
docker compose build 14-agent 01-config 15-dashboard

# Restart semua
docker compose up -d 14-agent 01-config 15-dashboard

# Tunggu semua service health-check passed
docker compose ps
```
Expected: Semua service menunjukkan status `Up` (healthy)

### Step 1: Restart Antonio

```bash
docker compose restart 14-agent
docker compose logs -f 14-agent | head -30
```
Expected: No provider config warnings in logs (or warnings that explain the issue clearly)

### Step 2: Test provider validation

```bash
curl http://localhost:8021/health
```
Expected: `{"meta":{"status":"ok"},"data":{"status":"ok","service":"antonio","version":"0.2.0",...}}`

### Step 3: Test chat

```bash
curl -X POST http://localhost:8021/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "list all Immunefi programs", "session_id": null}'
```
Expected: Response should include actual count (e.g., "Found 234 programs")

### Step 4: Test address validation

```bash
curl -X POST http://localhost:8021/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "audit synthetix contract 0x53773E034d9784153471813dacAFF53dBBB78E8c", "session_id": null}'
```
Expected: Antonio should warn that this address is not a Synthetix contract

### Step 5: Test circuit breaker status

```bash
curl http://localhost:8021/circuit-breakers
```
Expected: All breakers in CLOSED state

### Step 6: Test provider defaults

```bash
curl http://localhost:8021/agent/provider-defaults
```
Expected: Returns PROVIDER_DEFAULTS dict with correct base URLs

---

## Rollback Plan

If any fix causes issues:

1. **Per-task revert**: Each commit is isolated — revert individual commits with:
   ```bash
   git revert <commit-hash>
   ```

2. **Config reset**: If provider validation is too strict, increase `KNOWN_PROVIDER_DOMAINS` or make warnings non-blocking.

3. **Circuit breaker tuning**: If fetch_source is still blocked, decrease `failure_threshold` back to 5 or increase `recovery_timeout` further.
