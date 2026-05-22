"""Vyper Scanner Service — FastAPI microservice for Solidity security analysis.

Runs static analysis and fuzzing tools (Slither, Echidna, Forge) directly,
and proxies Mythril analysis to an isolated sidecar service
(``scanner-mythril``) to avoid dependency conflicts.

Port: 8003
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

import httpx
from shared.cache import CacheLayer
from shared.observability import setup_observability
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.deps import DependencyResolver, create_dependency_resolver
from src.echidna import EchidnaRunner, create_echidna_runner
from src.forge import ForgeRunner, create_forge_runner
from src.models import (
    ApiResponse,
    Finding,
    HealthData,
    InstallResult,
    Meta,
    ScanRequest,
    ScanResponse,
    ToolInfo,
    ToolInstallRequest,
    ToolResult,
)
from src.slither import SlitherRunner, create_slither_runner
from src.slither_config import SlitherConfigBuilder, create_slither_config
from src.solc_manager import SolcManager, create_solc_manager






# ── Constants ──────────────────────────────────────────────

SERVICE_NAME = "scanner"
SERVICE_VERSION = "0.1.0"
DATA_DIR = Path("/data/scanner")
RESULTS_DIR = DATA_DIR / "results"
SOURCES_DIR = DATA_DIR / "sources"
TOOLS_DIR = DATA_DIR / "tools"

# Mythril sidecar URL (set via env, defaults to localhost for testing)
MYTHRIL_URL = os.getenv("MYTHRIL_URL", "http://localhost:8013")

# Halmos sidecar URL (set via env, defaults to Docker compose service name)
HALMOS_URL = os.getenv("HALMOS_URL", "http://04d-scanner-halmos:8017")

# Scanner-Slither sidecar URL (custom detector engine)
SCANNER_SLITHER_URL = os.getenv("SCANNER_SLITHER_URL", "http://04a-scanner-slither:8014")

# ── Cache ───────────────────────────────────────────────────
scan_cache = CacheLayer(cache_dir="/data/cache/scanner")

# ── Global state ───────────────────────────────────────────


class AppState:
    """Shared application state injected via ``request.app.state.vyper``."""

    def __init__(self) -> None:
        self.solc_mgr: SolcManager = create_solc_manager()
        self.slither_runner: SlitherRunner = create_slither_runner()
        self.echidna_runner: EchidnaRunner = create_echidna_runner()
        self.forge_runner: ForgeRunner = create_forge_runner()
        self.dep_resolver: DependencyResolver = create_dependency_resolver()
        self.mythril_available: bool = False
        self.mythril_version: str | None = None
        self.halmos_available: bool = False
        self.halmos_version: str | None = None
        self._shutdown_requested: bool = False

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def request_shutdown(self) -> None:
        self._shutdown_requested = True


def _get_state(request: Request) -> AppState:
    """Get the application state from the request."""
    return request.app.state.vyper  # type: ignore[no-any-return]


# ── Lifespan ───────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: create data dirs, ensure tools are installed.
    Shutdown: clean log.
    """
    state = AppState()
    app.state.vyper = state

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    # Check solc availability
    solc_versions = state.solc_mgr.list_versions()
    log.info(
        "scanner.startup",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        solc_versions=len(solc_versions),
    )

    yield

    log.info("scanner.shutdown", service=SERVICE_NAME)


# ── App Factory ────────────────────────────────────────────

app = FastAPI(
    title="Vyper Scanner Service",
    description=(
        "Runs Slither, Echidna, and Foundry Forge on Solidity "
        "source code. Manages solc versions and resolves dependencies."
    ),
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

# CORS — permissive for local development / Docker compose
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



log = setup_observability(app, "04-scanner", "0.1.0")

# ── Helper ─────────────────────────────────────────────────


def ok(data: object = None) -> ApiResponse:
    """Build a standard Vyper success response."""
    return ApiResponse(data=data, meta=Meta(status="ok"))


def err(detail: str, status_code: int = 400) -> HTTPException:
    """Build a standard Vyper error response."""
    return HTTPException(
        status_code=status_code,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health(request: Request) -> ApiResponse:
    """Health check endpoint.

    Returns service status, version, installed tools, and available
    Solidity compiler versions.
    """
    state = _get_state(request)
    solc_versions = await asyncio.to_thread(state.solc_mgr.list_versions)
    tools = await _detect_tools(state)

    return ok(
        HealthData(
            status="ok",
            service=SERVICE_NAME,
            version=SERVICE_VERSION,
            tools_available=len([t for t in tools if t.available]),
            tools_installed=[t.name for t in tools if t.available],
            solc_versions=solc_versions,
        )
    )


@app.get("/tools")
async def list_tools(request: Request) -> ApiResponse:
    """List available security analysis tools and their versions."""
    state = _get_state(request)
    tools = await _detect_tools(state)
    return ok(tools)


@app.post("/tools/install")
async def install_tools(body: ToolInstallRequest) -> ApiResponse:
    """Install or update security analysis tools.

    Supports: ``slither``, ``echidna``, ``forge``.

    Installation runs via pip for Python tools or binary download for
    Echidna/Foundry. Returns results for each requested tool.
    """
    results: list[InstallResult] = []

    for tool in body.tools:
        result = await _install_tool(tool)
        results.append(result)

    return ok(results)


@app.post("/scan")
async def run_scan(body: ScanRequest, request: Request) -> ApiResponse:
    """Run security analysis tools on Solidity source code.

    Accepts source files, resolves compiler version, optionally installs
    dependencies, then runs the requested analysis tools (Slither,
    Echidna) plus a Forge build verification.

    **Request body**::

        {
            "chain": "ethereum",
            "address": "0x...",
            "sources": {"Contract.sol": "// SPDX-..."},
            "compiler": "0.8.20",
            "tools": ["slither", "echidna"],
            "config_tier": "default",
            "echidna_timeout": 600
        }

    ``tools`` defaults to all available tools if not specified.
    """
    start = time.monotonic()
    state = _get_state(request)

    if not body.sources:
        raise err("At least one source file is required")

    if not body.address or not body.address.startswith("0x"):
        raise err("address must be a 0x-prefixed hex string")

    if not body.chain:
        raise err("chain is required")

    # Resolve tools list
    tools_to_run = body.tools or ["slither", "echidna"]
    audit_id = str(uuid.uuid4())

    # Check cache first
    cache_key = {"contract": body.address, "chain": body.chain, "tools": tools_to_run if isinstance(tools_to_run, list) else ["all"]}
    cached = await scan_cache.get("scan", cache_key)
    if cached is not None:
        log.info("scan.cache_hit", contract=body.address)
        return ok(cached)

    # Create working directory for this audit
    audit_dir = SOURCES_DIR / audit_id
    audit_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Write source files to disk
        for file_path, source_code in body.sources.items():
            target = audit_dir / file_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source_code, encoding="utf-8")

        log.info(
            "scan.start",
            audit_id=audit_id,
            contract=body.address,
            chain=body.chain,
            files=len(body.sources),
            tools=tools_to_run,
            compiler=body.compiler,
        )

        # ── Step 1: Ensure solc version ──────────────────────
        try:
            await asyncio.to_thread(
                state.solc_mgr.ensure_version, body.compiler
            )
        except RuntimeError as exc:
            log.warning("scan.solc_unavailable", error=str(exc))
            # Continue anyway — tools may auto-detect solc

        # ── Step 2: Resolve dependencies ─────────────────────
        try:
            deps = await asyncio.to_thread(
                state.dep_resolver.resolve, audit_dir
            )
            if deps:
                log.info("scan.deps_resolved", count=len(deps))
        except Exception as exc:
            log.warning("scan.deps_failed", error=str(exc))

        # ── Step 3: Forge build verification ─────────────────
        forge_result = None
        try:
            forge_result = await asyncio.to_thread(
                state.forge_runner.run,
                audit_dir,
                compiler_version=body.compiler,
                timeout=120,
            )
        except Exception as exc:
            log.warning("scan.forge_failed", error=str(exc))
            forge_result = None

        # ── Step 4: Run tools ────────────────────────────────
        all_findings: list[Finding] = []
        tool_results: list[ToolResult] = []
        sem = asyncio.Semaphore(2)  # max 2 concurrent tool runs

        async def run_tool(tool: str) -> ToolResult:
            async with sem:
                return await asyncio.to_thread(
                    _run_single_tool,
                    state,
                    tool,
                    audit_dir,
                    body,
                )

        # Run tools concurrently (with semaphore limit)
        # Note: 'forge' is a build step (Step 3), not a scan tool — skip it here
        scan_tools = [t for t in tools_to_run if t in SUPPORTED_TOOLS and t != "forge"]
        tasks = [run_tool(t) for t in scan_tools]
        if tasks:
            completed = await asyncio.gather(*tasks, return_exceptions=True)
            for result in completed:
                if isinstance(result, ToolResult):
                    tool_results.append(result)
                    all_findings.extend(result.findings)
                elif isinstance(result, Exception):
                    log.error("scan.tool_crashed", error=str(result))

        # ── Step 5: Build response ───────────────────────────
        elapsed = time.monotonic() - start
        critical = sum(1 for f in all_findings if f.severity == "critical")
        high = sum(1 for f in all_findings if f.severity == "high")

        # Save results to disk
        scan_response = ScanResponse(
            audit_id=audit_id,
            contract_address=body.address,
            chain=body.chain,
            compiler=body.compiler,
            forge=forge_result,
            tools=tool_results,
            all_findings=all_findings,
            total_findings=len(all_findings),
            critical_count=critical,
            high_count=high,
            duration_seconds=round(elapsed, 2),
        )

        _save_results(audit_id, scan_response)

        log.info(
            "scan.complete",
            audit_id=audit_id,
            findings=len(all_findings),
            critical=critical,
            high=high,
            duration=round(elapsed, 2),
        )

        # Cache results
        await scan_cache.set("scan", cache_key, scan_response.model_dump(mode="json"), ttl_seconds=86400)

        return ok(scan_response)

    except Exception as exc:
        log.exception("scan.failed", audit_id=audit_id, error=str(exc))
        raise err(f"Scan failed: {exc}", status_code=500)

    finally:
        # Cleanup source directory after scan
        try:
            shutil.rmtree(audit_dir, ignore_errors=True)
        except OSError:
            pass


@app.get("/scan/{audit_id}")
async def get_scan_result(audit_id: str) -> ApiResponse:
    """Get the results of a previously completed scan.

    Results are loaded from disk if they exist.
    """
    result_path = RESULTS_DIR / audit_id / "result.json"
    if not result_path.exists():
        raise err(f"Scan result not found: {audit_id}", status_code=404)

    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
        return ok(data)
    except (json.JSONDecodeError, OSError) as exc:
        log.error("scan.result_read_error", audit_id=audit_id, error=str(exc))
        raise err("Failed to read scan result", status_code=500)


# ── Custom Detector Scan (proxy to scanner-slither) ──────────


@app.post("/scan/custom")
async def scan_custom(body: dict[str, Any], request: Request) -> JSONResponse:
    """Run Slither scan with custom detectors — proxied to scanner-slither sidecar.

    Forward body to 04a-scanner-slither:8014/scan/custom.
    Supports ``custom_detectors`` list and ``include_built_in`` flag.
    """
    try:
        async with httpx.AsyncClient(timeout=body.get("timeout", 600) + 30) as client:
            resp = await client.post(
                f"{SCANNER_SLITHER_URL}/scan/custom",
                json=body,
            )
            return JSONResponse(
                content=resp.json(),
                status_code=resp.status_code,
            )
    except httpx.RequestError as exc:
        raise err(f"Scanner-slither sidecar unreachable: {exc}", status_code=502)
    except Exception as exc:
        raise err(f"Custom scan proxy failed: {exc}", status_code=500)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Tools that this service supports natively.
SUPPORTED_TOOLS: dict[str, str] = {
    "slither": "static",
    "mythril": "symbolic",
    "halmos": "symbolic",
    "echidna": "fuzzer",
    "forge": "compiler",
}


async def _detect_tools(state: AppState) -> list[ToolInfo]:
    """Detect which tools are installed and their versions."""

    async def check_tool(name: str, binary: str, version_flag: str) -> ToolInfo:
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [binary, version_flag],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                version = result.stdout.strip() or result.stderr.strip()
                # Truncate to first line/100 chars
                version = version.splitlines()[0][:100] if version else None
                return ToolInfo(
                    name=name,
                    version=version,
                    available=True,
                    type=SUPPORTED_TOOLS.get(name, "static"),
                )
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            pass
        return ToolInfo(
            name=name,
            available=False,
            type=SUPPORTED_TOOLS.get(name, "static"),
        )

    checks = [
        check_tool("slither", "slither", "--version"),
        check_tool("echidna", "echidna", "--version"),
        check_tool("forge", "forge", "--version"),
        check_tool("solc", "solc", "--version"),
    ]

    results = await asyncio.gather(*checks)

    # Check mythril via HTTP (sidecar)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{MYTHRIL_URL}/health")
            if resp.status_code == 200:
                data = resp.json()
                mythril_ok = data.get("data", {}).get("mythril_available", False)
                mythril_ver = data.get("data", {}).get("mythril_version")
                state.mythril_available = mythril_ok
                state.mythril_version = mythril_ver
                results.append(
                    ToolInfo(
                        name="mythril",
                        version=mythril_ver,
                        available=mythril_ok,
                        type="symbolic",
                    )
                )
            else:
                state.mythril_available = False
                results.append(
                    ToolInfo(
                        name="mythril",
                        available=False,
                        type="symbolic",
                    )
                )
    except (httpx.RequestError, httpx.TimeoutException, Exception):
        log.warning("mythril_sidecar_unreachable", url=MYTHRIL_URL)
        state.mythril_available = False
        results.append(
            ToolInfo(
                name="mythril",
                available=False,
                type="symbolic",
            )
        )

    # Check halmos via HTTP (sidecar — 04d-scanner-halmos)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{HALMOS_URL}/health")
            if resp.status_code == 200:
                data = resp.json()
                halmos_ok = data.get("data", {}).get("halmos_available", False)
                halmos_ver = data.get("data", {}).get("halmos_version")
                state.halmos_available = halmos_ok
                state.halmos_version = halmos_ver
                results.append(
                    ToolInfo(
                        name="halmos",
                        version=halmos_ver,
                        available=halmos_ok,
                        type="symbolic",
                    )
                )
            else:
                state.halmos_available = False
                results.append(
                    ToolInfo(
                        name="halmos",
                        available=False,
                        type="symbolic",
                    )
                )
    except (httpx.RequestError, httpx.TimeoutException, Exception):
        log.warning("halmos_sidecar_unreachable", url=HALMOS_URL)
        state.halmos_available = False
        results.append(
            ToolInfo(
                name="halmos",
                available=False,
                type="symbolic",
            )
        )

    return results


async def _install_tool(tool: str) -> InstallResult:
    """Install or update a single analysis tool."""
    try:
        if tool == "slither":
            # pip-installable Python tool (needs setuptools for pkg_resources)
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    sys.executable, "-m", "pip", "install",
                    "--upgrade",
                    "slither-analyzer",
                    "setuptools",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                version = _extract_pip_version(result.stdout, tool)
                return InstallResult(
                    tool=tool, success=True, version=version
                )
            return InstallResult(
                tool=tool,
                success=False,
                error=result.stderr.strip()[:500],
            )

        elif tool == "echidna":
            # Echidna binary — download from GitHub releases
            return await _install_echidna()

        elif tool == "forge":
            # Foundry — install foundryup first if missing, then run it
            async def _install_forge() -> InstallResult:
                # Locate foundryup (common locations)
                foundryup_bin: str | None = None
                for candidate in (
                    "foundryup",
                    "/root/.foundry/bin/foundryup",
                    "/home/appuser/.foundry/bin/foundryup",
                ):
                    which = await asyncio.to_thread(
                        subprocess.run,
                        ["which", candidate],
                        capture_output=True, text=True,
                    )
                    if which.returncode == 0:
                        foundryup_bin = candidate
                        break
                if foundryup_bin is None:
                    # Install foundryup via curl
                    log.info("forge.installing_foundryup")
                    curl = await asyncio.to_thread(
                        subprocess.run,
                        ["curl", "-fsSL", "https://foundry.paradigm.xyz", "-o", "/tmp/foundryup.sh"],
                        capture_output=True, text=True, timeout=60,
                    )
                    if curl.returncode != 0:
                        return InstallResult(
                            tool=tool, success=False,
                            error=f"Failed to download foundryup: {curl.stderr.strip()[:300]}",
                        )
                    # NOTE: sh foundryup.sh may return non-zero (set -e triggered by
                    # "could not detect shell" warning) but the binary IS installed.
                    # We check for binary existence instead of exit code.
                    await asyncio.to_thread(
                        subprocess.run,
                        ["sh", "/tmp/foundryup.sh"],
                        capture_output=True, text=True, timeout=60,
                    )
                    # Check if binary was actually installed
                    import os as _os
                    if _os.path.exists("/root/.foundry/bin/foundryup"):
                        foundryup_bin = "/root/.foundry/bin/foundryup"
                    else:
                        return InstallResult(
                            tool=tool, success=False,
                            error="foundryup binary not found after install",
                        )
                # Run foundryup to install/update forge
                result = await asyncio.to_thread(
                    subprocess.run,
                    [foundryup_bin],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode != 0:
                    return InstallResult(
                        tool=tool,
                        success=False,
                        error=result.stderr.strip()[:500],
                    )
                # Create symlinks in /usr/local/bin for PATH access
                FOUNDRY_BINS = ["forge", "cast", "anvil", "chisel"]
                for bin_name in FOUNDRY_BINS:
                    src = f"/root/.foundry/bin/{bin_name}"
                    dst = f"/usr/local/bin/{bin_name}"
                    await asyncio.to_thread(
                        subprocess.run,
                        ["ln", "-sf", src, dst],
                        capture_output=True, text=True,
                    )
                return InstallResult(tool=tool, success=True, version="latest")
            return await _install_forge()

        elif tool == "mythril":
            # Mythril runs in an isolated sidecar (scanner-mythril).
            # Cannot install from here — the sidecar Docker image must be rebuilt.
            return InstallResult(
                tool=tool,
                success=False,
                error=(
                    "Mythril runs in the 'scanner-mythril' sidecar service. "
                    "Rebuild and restart the scanner-mythril container to update."
                ),
            )

        elif tool == "halmos":
            # Halmos runs in an isolated sidecar (04d-scanner-halmos).
            # Cannot install from here — the sidecar Docker image must be rebuilt.
            return InstallResult(
                tool=tool,
                success=False,
                error=(
                    "Halmos runs in the '04d-scanner-halmos' sidecar service. "
                    "Rebuild and restart the container to update."
                ),
            )

        else:
            return InstallResult(
                tool=tool,
                success=False,
                error=f"Unknown tool: {tool}",
            )

    except subprocess.TimeoutExpired:
        return InstallResult(
            tool=tool,
            success=False,
            error="Installation timed out",
        )
    except (FileNotFoundError, OSError) as exc:
        return InstallResult(
            tool=tool,
            success=False,
            error=str(exc),
        )


def _run_single_tool(
    state: AppState,
    tool: str,
    audit_dir: Path,
    body: ScanRequest,
) -> ToolResult:
    """Run a single analysis tool and return its result."""
    if tool == "slither":
        config = SlitherConfigBuilder().with_tier(body.config_tier).build()
        return state.slither_runner.run(audit_dir, config=config)

    elif tool == "echidna":
        return state.echidna_runner.run(
            audit_dir,
            contract_name=body.contract_name,
            timeout=body.echidna_timeout,
        )

    elif tool == "mythril":
        # Mythril runs in the scanner-mythril sidecar (HTTP proxy)
        try:
            # Build the sources dict from audit directory
            sources: dict[str, str] = {}
            for sol_file in sorted(audit_dir.rglob("*.sol")):
                rel_path = sol_file.relative_to(audit_dir)
                sources[str(rel_path)] = sol_file.read_text(encoding="utf-8")

            with httpx.Client(timeout=body.mythril_timeout or 300) as client:
                resp = client.post(
                    f"{MYTHRIL_URL}/analyze",
                    json={
                        "sources": sources,
                        "compiler_version": body.compiler,
                        "timeout": body.mythril_timeout or 300,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # Check if the sidecar reported success
                    if not data.get("ok", True):
                        return ToolResult(
                            tool="mythril",
                            success=False,
                            error=data.get("error", "Mythril sidecar returned ok=false"),
                        )
                    mythril_data = data.get("data") or {}
                    findings_raw = mythril_data.get("findings", [])
                    errors = mythril_data.get("errors", [])

                    findings = []
                    for f in findings_raw:
                        swc_id = f.get("swc_id")
                        swc_title = f.get("swc_title", "")
                        desc = f.get("description", "")
                        if swc_title and swc_title not in desc:
                            desc = f"[{swc_title}] {desc}" if desc else swc_title
                        findings.append(
                            Finding(
                                title=f.get("title", "Unknown"),
                                description=desc,
                                severity=f.get("severity", "Medium").lower(),
                                tool="mythril",
                                swc_id=swc_id,
                                function=f.get("function"),
                                line=f.get("address"),
                            )
                        )

                    return ToolResult(
                        tool="mythril",
                        success=True,
                        findings=findings,
                        errors=errors,
                    )
                else:
                    return ToolResult(
                        tool="mythril",
                        success=False,
                        error=f"Mythril service returned {resp.status_code}: {resp.text[:500]}",
                    )
        except httpx.RequestError as exc:
            return ToolResult(
                tool="mythril",
                success=False,
                error=f"Mythril sidecar unreachable: {str(exc)[:200]}",
            )
        except Exception as exc:
            return ToolResult(
                tool="mythril",
                success=False,
                error=f"Mythril execution error: {str(exc)[:300]}",
            )

    elif tool == "halmos":
        # Halmos runs in the 04d-scanner-halmos sidecar (HTTP proxy)
        try:
            # Build the sources dict from audit directory
            sources: dict[str, str] = {}
            for sol_file in sorted(audit_dir.rglob("*.sol")):
                rel_path = sol_file.relative_to(audit_dir)
                sources[str(rel_path)] = sol_file.read_text(encoding="utf-8")

            with httpx.Client(timeout=body.halmos_timeout or 600) as client:
                resp = client.post(
                    f"{HALMOS_URL}/analyze",
                    json={
                        "sources": sources,
                        "compiler_version": body.compiler,
                        "timeout": body.halmos_timeout or 600,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # Check if the sidecar reported success
                    if not data.get("ok", True):
                        return ToolResult(
                            tool="halmos",
                            success=False,
                            error=data.get("error", "Halmos sidecar returned ok=false"),
                        )
                    halmos_data = data.get("data") or {}
                    findings_raw = halmos_data.get("findings", [])
                    errors = halmos_data.get("errors", [])

                    findings = []
                    for f in findings_raw:
                        swc_id = f.get("swc_id")
                        swc_title = f.get("swc_title", "")
                        desc = f.get("description", "")
                        if swc_title and swc_title not in desc:
                            desc = f"[{swc_title}] {desc}" if desc else swc_title
                        findings.append(
                            Finding(
                                title=f.get("title", "Unknown"),
                                description=desc,
                                severity=f.get("severity", "Medium").lower(),
                                tool="halmos",
                                swc_id=swc_id,
                                function=f.get("function"),
                                line=f.get("address"),
                            )
                        )

                    return ToolResult(
                        tool="halmos",
                        success=True,
                        findings=findings,
                        errors=errors,
                    )
                else:
                    return ToolResult(
                        tool="halmos",
                        success=False,
                        error=f"Halmos service returned {resp.status_code}: {resp.text[:500]}",
                    )
        except httpx.RequestError as exc:
            return ToolResult(
                tool="halmos",
                success=False,
                error=f"Halmos sidecar unreachable: {str(exc)[:200]}",
            )
        except Exception as exc:
            return ToolResult(
                tool="halmos",
                success=False,
                error=f"Halmos execution error: {str(exc)[:300]}",
            )

    else:
        return ToolResult(
            tool=tool,
            success=False,
            error=f"Unsupported tool: {tool}",
        )


def _save_results(audit_id: str, response: ScanResponse) -> None:
    """Save scan results to disk as JSON."""
    result_dir = RESULTS_DIR / audit_id
    result_dir.mkdir(parents=True, exist_ok=True)

    data = response.model_dump(mode="json")
    result_path = result_dir / "result.json"
    try:
        result_path.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )
    except OSError as exc:
        log.error("scan.save_failed", audit_id=audit_id, error=str(exc))


async def _install_echidna() -> InstallResult:
    """Download and install the Echidna binary from GitHub releases."""
    import platform

    # Map platform to GitHub release asset name
    arch_map = {
        "x86_64": "amd64",
        "aarch64": "arm64",
    }
    os_map = {
        "linux": "linux",
        "darwin": "darwin",
    }
    machine = platform.machine()
    system = platform.system().lower()
    # Map platform to GitHub release asset arch name
    arch_map = {"x86_64": "x86_64", "aarch64": "aarch64"}
    os_map = {"linux": "linux", "darwin": "macos"}
    target_arch = arch_map.get(machine, machine)
    target_os = os_map.get(system, system)

    # Fetch latest release tag
    try:
        req = await asyncio.to_thread(
            subprocess.run,
            [
                "curl", "-fsSL",
                "https://api.github.com/repos/crytic/echidna/releases/latest",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if req.returncode != 0:
            return InstallResult(tool="echidna", success=False,
                                 error=f"GitHub API failed: {req.stderr.strip()[:200]}")
        import json as _json
        release = _json.loads(req.stdout)
        tag = release.get("tag_name", "v2.3.2")
    except Exception as exc:
        tag = "v2.3.2"  # fallback

    version_str = tag.lstrip("v")
    url = f"https://github.com/crytic/echidna/releases/download/{tag}/echidna-{version_str}-{target_arch}-{target_os}.tar.gz"
    log.info("echidna.downloading", url=url)

    try:
        dl = await asyncio.to_thread(
            subprocess.run,
            ["curl", "-fsSL", url, "-o", "/tmp/echidna.tar.gz"],
            capture_output=True, text=True, timeout=120,
        )
        if dl.returncode != 0:
            return InstallResult(tool="echidna", success=False,
                                 error=f"Download failed: {dl.stderr.strip()[:200]}")

        extract = await asyncio.to_thread(
            subprocess.run,
            ["tar", "-xzf", "/tmp/echidna.tar.gz", "-C", "/tmp/"],
            capture_output=True, text=True, timeout=30,
        )
        if extract.returncode != 0:
            return InstallResult(tool="echidna", success=False,
                                 error=f"Extract failed: {extract.stderr.strip()[:200]}")

        install = await asyncio.to_thread(
            subprocess.run,
            ["install", "-m", "755", "/tmp/echidna", "/usr/local/bin/echidna"],
            capture_output=True, text=True, timeout=30,
        )
        if install.returncode != 0:
            return InstallResult(tool="echidna", success=False,
                                 error=f"Install failed: {install.stderr.strip()[:200]}")

        # Verify
        ver = await asyncio.to_thread(
            subprocess.run,
            ["echidna", "--version"],
            capture_output=True, text=True, timeout=30,
        )
        version = ver.stdout.strip() or ver.stderr.strip() or "latest"
        return InstallResult(tool="echidna", success=True, version=version)
    except Exception as exc:
        return InstallResult(tool="echidna", success=False, error=str(exc)[:200])


def _extract_pip_version(pip_output: str, tool: str) -> str | None:
    """Extract the installed version from pip output."""
    for line in pip_output.splitlines():
        if "installed" in line.lower() and tool in line.lower():
            # e.g. "Installing collected packages: slither-analyzer... Successfully installed slither-analyzer-0.10.0"
            import re
            match = re.search(r"(\d+\.\d+\.\d+)", line)
            if match:
                return match.group(1)
    return None


# ── Entry Point ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8003,
        log_level="info",
        reload=False,
    )
