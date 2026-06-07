"""Integration tests for Halmos formal verification pipeline.

Tests cover:
  1. **Direct Halmos scan** — POST /analyze on 04d-scanner-halmos
  2. **Scanner router dispatch** — POST /scan with ``tools: ["halmos"]``
  3. **Counterexample parsing** — parse Halmos JSON output → Findings
  4. **Large contract timeout** — graceful error, not a crash
"""

from __future__ import annotations

import json
import socket
from typing import Any

import httpx
import pytest

# ═══════════════════════════════════════════════════════════════════
# Dummy Solidity contracts
# ═══════════════════════════════════════════════════════════════════

SIMPLE_COUNTER = """\
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;
contract Counter {
    uint256 public count;
    function increment() public { count++; }
    function decrement() public { count--; }
    function getCount() public view returns (uint256) { return count; }
}
"""

LARGE_DUMMY_CONTRACT = """\
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;
contract LargeDummy {
""" + "\n".join(f"    uint256 public var_{i};" for i in range(500)) + """
    function setAll() public {
""" + "\n".join(f"        var_{i} = {i};" for i in range(500)) + """
    }
}
"""


# ═══════════════════════════════════════════════════════════════════
# Service reachability guards  (module-level, evaluated once)
# ═══════════════════════════════════════════════════════════════════


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check whether a TCP port is accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (TimeoutError, OSError):
        return False


halmos_reachable = _port_open("localhost", 8017)
scanner_reachable = _port_open("localhost", 8003)


# ═══════════════════════════════════════════════════════════════════
# Halmos output parser  (pure function, no HTTP, can be tested
# independently)
# ═══════════════════════════════════════════════════════════════════


def parse_halmos_json_output(raw: str) -> list[dict[str, Any]]:
    """Parse Halmos ``--json`` output into a list of Finding-like dicts.

    Halmos JSON structure::

        {
          "numTests": 2,
          "tests": [
            {"name": "prove_X", "result": "PASS", "time": 0.123},
            {"name": "prove_Y", "result": "FAIL", "time": 0.456,
             "counterexample": "count: 0"}
          ]
        }

    Returns one dict per test with keys:
    ``title``, ``severity``, ``description``, ``detector``,
    and optionally ``counterexample``.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    tests = data.get("tests", []) if isinstance(data, dict) else []
    findings: list[dict[str, Any]] = []

    for t in tests:
        name: str = t.get("name", "unknown")
        result: str = t.get("result", "UNKNOWN")

        if result == "FAIL":
            findings.append({
                "title": f"Halmos: {name}",
                "severity": "High",
                "description": (
                    f"Property {name} failed under Halmos symbolic execution."
                ),
                "detector": "halmos",
                "counterexample": t.get("counterexample"),
            })
        elif result == "PASS":
            findings.append({
                "title": f"Halmos: {name}",
                "severity": "Info",
                "description": (
                    f"Property {name} passed under Halmos symbolic execution."
                ),
                "detector": "halmos",
            })

    return findings


# ═══════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════


class TestHalmosPipeline:
    """Halmos formal verification integration tests."""

    # ── 1. Direct Halmos scan ────────────────────────────────────

    @pytest.mark.skipif(not halmos_reachable, reason="Halmos service not reachable")
    @pytest.mark.asyncio
    async def test_halmos_direct_scan(
        self, async_client: httpx.AsyncClient, scanner_halmos_url: str
    ) -> None:
        """POST /analyze on the Halmos service directly.

        Sends a simple ``Counter`` contract and asserts the response
        contains a ``data.findings`` key.
        """
        resp = await async_client.post(
            f"{scanner_halmos_url}/analyze",
            json={
                "sources": {"Counter.sol": SIMPLE_COUNTER},
                "timeout": 60,
            },
            timeout=10.0,
        )
        assert resp.status_code == 200, (
            f"Halmos direct scan failed: {resp.status_code} {resp.text[:300]}"
        )
        body = resp.json()
        meta = body.get("meta", {})
        assert meta.get("status") == "ok", f"Meta status not ok: {meta}"
        data = body.get("data", {})
        assert "findings" in data, (
            f"Response missing 'findings' key in data: {list(data.keys())}"
        )

    # ── 2. Halmos via scanner router ─────────────────────────────

    @pytest.mark.skipif(not scanner_reachable, reason="Scanner service not reachable")
    @pytest.mark.asyncio
    async def test_halmos_via_scanner_router(
        self, async_client: httpx.AsyncClient, scanner_url: str
    ) -> None:
        """POST /scan on the scanner router with ``tools: ["halmos"]``.

        The scanner should dispatch the request to the Halmos sidecar
        and return aggregated results.
        """
        resp = await async_client.post(
            f"{scanner_url}/scan",
            json={
                "sources": {"Counter.sol": SIMPLE_COUNTER},
                "tools": ["halmos"],
                "timeout": 60,
            },
            timeout=15.0,
        )
        assert resp.status_code == 200, (
            f"Scanner routed Halmos scan failed: "
            f"{resp.status_code} {resp.text[:300]}"
        )
        body = resp.json()
        meta = body.get("meta", {})
        assert meta.get("status") == "ok", f"Meta status not ok: {meta}"

    # ── 3. Counterexample parsing (pure, no HTTP) ────────────────

    @pytest.mark.asyncio
    async def test_counterexample_parsing(self) -> None:
        """Parse a mock Halmos JSON output and verify Finding objects.

        This test does **not** require a running service — it tests
        the local ``parse_halmos_json_output`` function in isolation.
        """
        mock_output = json.dumps({
            "numTests": 2,
            "tests": [
                {
                    "name": "prove_Counter_increment",
                    "result": "PASS",
                    "time": 0.123,
                },
                {
                    "name": "prove_Counter_decrement",
                    "result": "FAIL",
                    "time": 0.456,
                    "counterexample": "count: 0",
                },
            ],
        })

        findings = parse_halmos_json_output(mock_output)

        assert len(findings) == 2, f"Expected 2 findings, got {len(findings)}"

        # PASS finding
        assert findings[0]["title"] == "Halmos: prove_Counter_increment"
        assert findings[0]["severity"] == "Info"
        assert findings[0]["detector"] == "halmos"

        # FAIL finding
        assert findings[1]["title"] == "Halmos: prove_Counter_decrement"
        assert findings[1]["severity"] == "High"
        assert findings[1]["detector"] == "halmos"
        assert findings[1]["counterexample"] == "count: 0"

    # ── 4. Large contract timeout ────────────────────────────────

    @pytest.mark.skipif(not halmos_reachable, reason="Halmos service not reachable")
    @pytest.mark.asyncio
    async def test_halmos_large_contract_timeout(
        self, async_client: httpx.AsyncClient, scanner_halmos_url: str
    ) -> None:
        """POST a large dummy contract with a 1-second timeout.

        Verifies the service returns a graceful error (not a crash):
        either a well-formed JSON error with descriptive message or
        a successful response if analysis completes in time.
        """
        resp = await async_client.post(
            f"{scanner_halmos_url}/analyze",
            json={
                "sources": {"LargeDummy.sol": LARGE_DUMMY_CONTRACT},
                "timeout": 1,  # very short — guaranteed timeout
            },
            timeout=10.0,
        )

        body = resp.json()
        meta = body.get("meta", {})

        if meta.get("status") == "ok":
            # Analysis finished before timeout — that is also fine
            return

        # Error response: must have a descriptive message
        error_info = (
            meta.get("error")
            or body.get("error")
            or body.get("detail")
            or ""
        )
        assert error_info, (
            f"Error response missing descriptive message: {resp.text[:300]}"
        )
