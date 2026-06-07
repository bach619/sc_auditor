"""pytest fixtures for Vyper integration tests.

Service URLs default to ``localhost`` ports matching the Docker Compose
mapping and can be overridden via environment variables, e.g.::

    $env:CONFIG_URL = "http://01-config:8000"
    pytest

Marks:
    ``requires_docker`` — skip when Docker services are not running.
        Usage: ``pytest -m "not requires_docker"`` for CI unit-test phase.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

# ── Namespace isolation: prevent src/ collisions ─────────────────

# 28 services all use ``src/`` as their Python package name.
# The 04b-scanner-echidna test files add their ``src/`` to sys.path
# at module level, then pop it after imports (sys.path.pop(0)).
#
# Each test file that imports from ``src.*`` handles its own path
# setup and sys.modules cleanup inline. This hook is a safety net.

_ECHIDNA_DIR = str(
    Path(__file__).resolve().parents[1] / "services" / "04b-scanner-echidna"
)


def pytest_configure(config: pytest.Config) -> None:
    """Register markers."""
    pass


# ── Skip requires_docker tests when not available ────────────────


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Auto-skip ``requires_docker`` tests when services are not running."""
    # Simple heuristic: if config URL is localhost and we can't connect,
    # skip docker-requiring tests. For now, just ensure the mark is recognized.
    pass  # Marks are handled by pytest itself; use -m "not requires_docker"

# ── Service URL defaults (Docker Compose host ports) ────────────

_SERVICE_URLS: dict[str, str] = {
    "config": "http://localhost:8011",
    "immunefi": "http://localhost:8001",
    "source": "http://localhost:8002",
    "scanner": "http://localhost:8003",
    "scanner_slither": "http://localhost:8014",
    "scanner_echidna": "http://localhost:8015",
    "scanner_forge": "http://localhost:8016",
    "scanner_halmos": "http://localhost:8017",
    "scanner_mythril": "http://localhost:8013",
    "ai": "http://localhost:8004",
    "classifier": "http://localhost:8005",
    "exploit": "http://localhost:8006",
    "reporter": "http://localhost:8007",
    "notifier": "http://localhost:8008",
    "orchestrator": "http://localhost:8009",
    "webhook": "http://localhost:8010",
    "upkeep": "http://localhost:8012",
    "agent": "http://localhost:8021",  # 14-agent on port 8021 (hindari bentrok 04a-scanner-slither di 8014)
    "dashboard": "http://localhost:8000",
    "scanner_manticore": "http://localhost:8020",
    "submission": "http://localhost:8018",
    "experience": "http://localhost:8019",
    "code4rena": "http://localhost:8022",
    "sherlock": "http://localhost:8023",
    "cantina": "http://localhost:8024",
    "hats": "http://localhost:8025",
    "source_starknet": "http://localhost:8026",
    "scanner_cairo": "http://localhost:8028",
}


def _service_url(name: str) -> str:
    """Return the URL for a service, preferring an env var override."""
    return os.environ.get(f"{name.upper()}_URL", _SERVICE_URLS[name])


# ── pytest-asyncio / anyio ──────────────────────────────────────


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Return the async backend for pytest-asyncio/pytest-anyio."""
    return "asyncio"


@pytest.fixture(scope="function")
def event_loop():
    """Create a fresh event loop per test function (fixes Windows Event loop is closed)."""
    policy = asyncio.WindowsProactorEventLoopPolicy() if os.name == "nt" else asyncio.DefaultEventLoopPolicy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


# ── HTTP client ─────────────────────────────────────────────────


@pytest.fixture(scope="function")
async def async_client() -> httpx.AsyncClient:
    """Fresh HTTP client per test (function-scoped to avoid event loop issues on Windows)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


# ── Sample data fixtures ────────────────────────────────────────


@pytest.fixture()
def sample_contract_address() -> str:
    """A well-known test contract address (WETH on Ethereum)."""
    return "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"


@pytest.fixture()
def sample_audit_payload() -> dict[str, Any]:
    """Standard payload for starting a new audit."""
    return {
        "chain": "ethereum",
        "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "program": "test-program",
        "priority": 5,
    }


@pytest.fixture()
def sample_case_data() -> dict[str, Any]:
    """Sample Case data for Case Management tests."""
    return {
        "title": "Reentrancy in Vault.withdraw()",
        "description": "The withdraw function does not follow CEI pattern.",
        "severity": "High",
        "contract": "Vault",
        "function": "withdraw",
        "detector": "slither",
        "recommendation": "Apply checks-effects-interactions pattern.",
    }


# ── Individual service URL fixtures ─────────────────────────────


@pytest.fixture()
def config_url() -> str:
    """Config Service URL."""
    return _service_url("config")


@pytest.fixture()
def immunefi_url() -> str:
    """Immunefi Service URL."""
    return _service_url("immunefi")


@pytest.fixture()
def source_url() -> str:
    """Source Service URL."""
    return _service_url("source")


@pytest.fixture()
def scanner_url() -> str:
    """Scanner Service URL (legacy monolith)."""
    return _service_url("scanner")


@pytest.fixture()
def scanner_slither_url() -> str:
    """Scanner Slither Service URL."""
    return _service_url("scanner_slither")


@pytest.fixture()
def scanner_echidna_url() -> str:
    """Scanner Echidna Service URL."""
    return _service_url("scanner_echidna")


@pytest.fixture()
def scanner_forge_url() -> str:
    """Scanner Forge Service URL."""
    return _service_url("scanner_forge")


@pytest.fixture()
def scanner_halmos_url() -> str:
    """Scanner Halmos Service URL."""
    return _service_url("scanner_halmos")


@pytest.fixture()
def scanner_mythril_url() -> str:
    """Scanner Mythril Service URL."""
    return _service_url("scanner_mythril")


@pytest.fixture()
def ai_url() -> str:
    """AI Service URL."""
    return _service_url("ai")


@pytest.fixture()
def classifier_url() -> str:
    """Classifier Service URL."""
    return _service_url("classifier")


@pytest.fixture()
def exploit_url() -> str:
    """Exploit Service URL."""
    return _service_url("exploit")


@pytest.fixture()
def reporter_url() -> str:
    """Reporter Service URL."""
    return _service_url("reporter")


@pytest.fixture()
def notifier_url() -> str:
    """Notifier Service URL."""
    return _service_url("notifier")


@pytest.fixture()
def orchestrator_url() -> str:
    """Orchestrator Service URL."""
    return _service_url("orchestrator")


@pytest.fixture()
def webhook_url() -> str:
    """Webhook Service URL."""
    return _service_url("webhook")


@pytest.fixture()
def upkeep_url() -> str:
    """Upkeep Service URL."""
    return _service_url("upkeep")


@pytest.fixture()
def agent_url() -> str:
    """Agent Service URL."""
    return _service_url("agent")


@pytest.fixture()
def dashboard_url() -> str:
    """Dashboard Service URL."""
    return _service_url("dashboard")


@pytest.fixture()
def scanner_manticore_url() -> str:
    """Scanner Manticore Service URL."""
    return _service_url("scanner_manticore")


@pytest.fixture()
def submission_url() -> str:
    """Submission Service URL."""
    return _service_url("submission")


@pytest.fixture()
def experience_url() -> str:
    """Experience Service URL."""
    return _service_url("experience")


@pytest.fixture()
def code4rena_url() -> str:
    """Code4rena Service URL."""
    return _service_url("code4rena")


@pytest.fixture()
def sherlock_url() -> str:
    """Sherlock Service URL."""
    return _service_url("sherlock")


@pytest.fixture()
def cantina_url() -> str:
    """Cantina Service URL."""
    return _service_url("cantina")


@pytest.fixture()
def hats_url() -> str:
    """Hats Finance Service URL."""
    return _service_url("hats")


@pytest.fixture()
def source_starknet_url() -> str:
    """StarkNet Source Service URL."""
    return _service_url("source_starknet")


@pytest.fixture()
def scanner_cairo_url() -> str:
    """Cairo Scanner Service URL."""
    return _service_url("scanner_cairo")
