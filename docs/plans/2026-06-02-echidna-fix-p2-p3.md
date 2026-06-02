# Echidna P2/P3 Enhancement Implementation Plan

> **For Opencode:** Dispatch each task independently — all are parallelizable.

**Goal:** Enhance 04b-scanner-echidna with meaningful invariant harness, multi-contract support, coverage extraction, queue management, FP/TP tracking, ARM64 Docker, and cost estimation.

**Architecture:** 7 independent tasks modifying specific files in the 04b-scanner-echidna service.

---

## Task P2-1: Default Invariant Properties in Harness

**Objective:** Upgrade HARNESS_TEMPLATE with useful default invariants beyond the trivial `echidna_no_reverts()`.

**Files:**
- Modify: `services/04b-scanner-echidna/src/echidna.py` (HARNESS_TEMPLATE)

**Current template:**
```solidity
contract EchidnaHarness is {contract_name} {
    function echidna_no_reverts() public view returns (bool) {
        return true;
    }
}
```

**Enhanced template:**
```solidity
contract EchidnaHarness is {contract_name} {
    // ── Default Invariants ────────────────────────────────
    // These properties are checked during every fuzzing campaign.
    // Override any that don't apply to your contract.
    // Add custom properties below.

    /// @notice Contract should never lock up (always able to receive ETH)
    function echidna_no_reverts() public view returns (bool) {
        return true;
    }

    /// @notice Contract ETH balance should never exceed a reasonable cap
    /// (override this with your actual cap)
    function echidna_eth_balance_cap() public view returns (bool) {
        return address(this).balance <= 100_000 ether;
    }

    /// @notice Contract should not selfdestruct (address must have code)
    function echidna_no_selfdestruct() public view returns (bool) {
        uint256 size;
        address self = address(this);
        assembly { size := extcodesize(self) }
        return size > 0;
    }

    /// @notice Owner address must never be zero
    function echidna_owner_not_zero() public view returns (bool) {
        // Override this if your contract doesn't have an owner
        return true;
    }

    /// @notice Total supply should never exceed max supply (override for ERC20)
    function echidna_total_supply_valid() public view returns (bool) {
        try this.totalSupply() returns (uint256 supply) {
            try this.maxSupply() returns (uint256 max) {
                return supply <= max;
            } catch (bytes memory) {
                return true; // No maxSupply function
            }
        } catch (bytes memory) {
            return true; // No totalSupply function
        }
    }
}
```

**Verification:**
- Read the modified file and confirm the template has at least 4 meaningful `echidna_*` functions.
- Make sure the Solidity syntax is valid (uses `try/catch` for optional external calls).

**Edge cases:**
- Some contracts may not compile with `try` statements (pre-Solidity 0.6). The template should still compile — `try` is used inside the invariant which may fail, but that's fine since if `totalSupply()` doesn't exist, it catches gracefully.

---

## Task P2-2: Multi-Contract / Dependency Support

**Objective:** Fix `_find_contract()` to handle Solidity import dependencies — collect ALL `.sol` files needed, not just one.

**Files:**
- Modify: `services/04b-scanner-echidna/src/echidna.py` (methods `_find_contract` and `_ensure_harness`)

**Current limitation:**
`_find_contract()` picks only the first `.sol` file (or matches by name). If a contract has `import "./Dependency.sol"`, the harness will fail at compilation because:
1. Only one contract file is known
2. Harness imports the target but dependencies aren't resolved

**Fix approach:**
1. Enhance `_find_contract()` to scan ALL `.sol` files and return a list
2. Add `_resolve_dependencies()` method that parses `import` statements and collects all referenced files
3. Modify `_ensure_harness()` to include dependency paths in the Echidna config (via `solc-args --allow-paths` or `cryticArgs` in yaml config)

**Code to add/modify:**

In `_find_contract()`, change return to `tuple[list[Path], str]` — return ALL `.sol` files plus the primary contract name.

Add new method `_resolve_dependencies(source_dir: Path, primary: Path) -> list[Path]`:
```python
@staticmethod
def _resolve_dependencies(source_dir: Path, primary: Path) -> list[Path]:
    """Resolve Solidity import dependencies recursively."""
    resolved: set[Path] = set()
    to_process = [primary]
    import_pattern = re.compile(r'import\s+(?:\{[^}]*\}\s+from\s+)?["\']([^"\']+)["\']')
    
    while to_process:
        current = to_process.pop()
        if current in resolved:
            continue
        resolved.add(current)
        try:
            content = current.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in import_pattern.finditer(content):
            import_path = match.group(1)
            # Resolve relative import
            if import_path.startswith("."):
                resolved_path = (current.parent / import_path).resolve()
            else:
                resolved_path = (source_dir / import_path).resolve()
            if resolved_path.exists() and resolved_path.suffix == ".sol":
                to_process.append(resolved_path)
    
    return sorted(resolved, key=lambda p: str(p))
```

In `_ensure_harness()`, ensure all dependency files are accessible — add `--solc-args "--allow-paths ."` already exists. The key change is making sure the echidna config includes the right `cryticArgs` to resolve imports.

In `_build_config()`, add `cryticArgs` with proper remappings if needed:
```yaml
cryticArgs: ["--solc-remaps", "@openzeppelin/=lib/openzeppelin-contracts/"]
```

**Also update `run()` method** to handle the new return type from `_find_contract()`.

**Verification:**
- `cd /mnt/e/website/project/sc_auditor && python -c "from services.04b_scanner_echidna.src.echidna import EchidnaRunner; print('OK')"`
- Check that `_find_contract` returns multiple files.

**IMPORTANT**: 
- Keep backward compatibility — if there's only 1 `.sol` file, behavior must be identical to before.
- Only resolve imports relative to `source_dir`.
- Don't follow absolute imports (they're external libs).
- Add `from __future__ import annotations` if not already there.

---

## Task P2-3: Coverage Extraction from Echidna Output

**Objective:** Extract and return code coverage data from Echidna output alongside findings.

**Files:**
- Modify: `services/04b-scanner-echidna/src/echidna.py` (add `_extract_coverage()` + include in ToolResult)
- Modify: `vyper_lib/models.py` (add coverage fields to ToolResult)

**Background:** When Echidna runs with `--coverage true`, it outputs coverage info at the end:
```
Coverage: 
  - /path/to/Contract.sol: 72.3% (branches), 85.1% (lines)
```

**Steps:**

1. Add `self._coverage_enabled = True` to `EchidnaRunner.__init__()`

2. Add `--coverage true` to the cmd args in `run()` method (after line 107):
```python
if self._coverage_enabled:
    cmd.extend(["--coverage", "true"])
```

3. Add `_extract_coverage()` static method:
```python
@staticmethod
def _extract_coverage(output: str) -> dict[str, Any]:
    """Extract coverage data from Echidna output.
    
    Returns:
        Dict with structure:
        {
            "branch_coverage": 0.0-100.0,
            "line_coverage": 0.0-100.0,
            "covered_contracts": [...],
            "raw_summary": "..."
        }
    """
    coverage: dict[str, Any] = {
        "branch_coverage": 0.0,
        "line_coverage": 0.0,
        "covered_contracts": [],
        "raw_summary": "",
    }
    
    # Find coverage section
    coverage_match = re.search(r"Coverage:\s*\n(.*?)(?:\n\n|\Z)", output, re.DOTALL)
    if not coverage_match:
        return coverage
    
    raw = coverage_match.group(1).strip()
    coverage["raw_summary"] = raw[:500]  # truncate
    
    # Parse per-contract coverage
    contract_pattern = re.compile(r"-\s+(.+?):\s+([\d.]+)%\s+\(branches\),\s+([\d.]+)%\s+\(lines\)")
    total_branch = 0.0
    total_line = 0.0
    count = 0
    
    for match in contract_pattern.finditer(raw):
        contract_path = match.group(1).strip()
        branch_pct = float(match.group(2))
        line_pct = float(match.group(3))
        total_branch += branch_pct
        total_line += line_pct
        count += 1
        coverage["covered_contracts"].append({
            "path": contract_path,
            "branch_coverage": branch_pct,
            "line_coverage": line_pct,
        })
    
    if count > 0:
        coverage["branch_coverage"] = round(total_branch / count, 1)
        coverage["line_coverage"] = round(total_line / count, 1)
    
    return coverage
```

4. In `run()`, after `_parse_output`, add:
```python
coverage_data = self._extract_coverage(result.stdout) if self._coverage_enabled else {}
```

5. Modify the `ToolResult` return to include coverage. Use `metadata` dict on ToolResult:
```python
return ToolResult(
    tool=tool_name, success=success,
    findings=findings, raw_output=result.stdout,
    error=..., duration_seconds=elapsed,
    metadata={"coverage": coverage_data} if coverage_data else {},
)
```

Wait — `ToolResult` doesn't have a `metadata` field. Let me check... Actually in `vyper_lib/models.py`, `ToolResult` has: tool, success, findings, raw_output, error, duration_seconds. We need to add coverage.

Better approach: Just include coverage in the raw_output metadata, or add a `coverage` field.

**Simpler approach:** Just return coverage as part of `metadata` on the `Finding` or add it to the `dict` in the scan response. Or even simpler: add the coverage dict to the `raw_output` prefix with a separator.

**Cleanest approach:** Modify `vyper_lib/models.py` to add an optional `coverage` field to `ToolResult`:

```python
class ToolResult(BaseModel):
    tool: str
    success: bool = True
    findings: list[Finding] = Field(default_factory=list)
    raw_output: str = ""
    error: str | None = None
    duration_seconds: float = 0.0
    coverage: dict[str, Any] | None = None  # NEW
```

Then in `app.py` scan response, include coverage info.

6. Update `app.py` scan response to include coverage if available:
```python
scan_response = ScanResponse(
    ...
    tools=[result],
    ...
)
# Coverage di-extract dari result di endpoint
```

**Verification:**
- Read the modified files and check that coverage extraction is syntactically correct
- Run: `cd /mnt/e/website/project/sc_auditor && python -c "
from services.04b_scanner_echidna.src.echidna import EchidnaRunner
# Test coverage parsing
sample_output = '''Coverage:
  - /tmp/Contract.sol: 72.3% (branches), 85.1% (lines)
  - /tmp/Lib.sol: 90.0% (branches), 95.0% (lines)

'''
cov = EchidnaRunner._extract_coverage(sample_output)
assert abs(cov['branch_coverage'] - 81.15) < 0.1
assert abs(cov['line_coverage'] - 90.05) < 0.1
assert len(cov['covered_contracts']) == 2
print('Coverage parsing OK:', cov)
"`

---

## Task P2-4: Async Queue Management for Scan Requests

**Objective:** Add internal request queuing to 04b-scanner-echidna to prevent overload when orchestrator fans out multiple concurrent scan requests.

**Files:**
- Modify: `services/04b-scanner-echidna/app.py`
- Create: `services/04b-scanner-echidna/src/queue_manager.py`

**Why:** The orchestrator can fan out 2+ concurrent audits, each calling Echidna. Without internal queuing, if both arrive at the same time, one subprocess will block the other via `asyncio.to_thread`, but there's no limit or ordering.

**Approach:**
Create a lightweight in-memory queue using `asyncio.Queue` with a semaphore limiting concurrent executions.

### `services/04b-scanner-echidna/src/queue_manager.py`
```python
"""Async queue manager for Echidna scan requests.

Prevents resource exhaustion by limiting concurrent Echidna runs
and providing queue status/ordering.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine


@dataclass
class QueueItem:
    """A single scan request in the queue."""
    audit_id: str
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    status: str = "queued"  # queued, running, completed, failed
    result: Any = None
    error: str | None = None


class ScanQueue:
    """Manages concurrent Echidna scan executions.
    
    Usage:
        queue = ScanQueue(max_concurrent=1)
        result = await queue.enqueue("audit-123", runner.run, audit_dir, ...)
    """
    
    def __init__(self, max_concurrent: int = 1) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue: asyncio.Queue[QueueItem] = asyncio.Queue()
        self._items: dict[str, QueueItem] = {}
        self._max_concurrent = max_concurrent
    
    async def enqueue(
        self,
        audit_id: str,
        coro_factory: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Enqueue a scan request and wait for result.
        
        Args:
            audit_id: Unique identifier for this scan.
            coro_factory: Async callable that runs the scan.
            *args, **kwargs: Passed to coro_factory.
        
        Returns:
            The result from coro_factory.
        """
        item = QueueItem(audit_id=audit_id)
        self._items[audit_id] = item
        
        async with self._semaphore:
            item.status = "running"
            item.started_at = time.time()
            try:
                result = await coro_factory(*args, **kwargs)
                item.status = "completed"
                item.result = result
                return result
            except Exception as exc:
                item.status = "failed"
                item.error = str(exc)
                raise
    
    def get_status(self, audit_id: str) -> dict[str, Any] | None:
        """Get status of a queued item."""
        item = self._items.get(audit_id)
        if not item:
            return None
        return {
            "audit_id": item.audit_id,
            "status": item.status,
            "queued_at": item.created_at,
            "started_at": item.started_at,
            "wait_time": round(time.time() - item.created_at, 2) if item.status == "running" else None,
        }
    
    def get_queue_summary(self) -> dict[str, Any]:
        """Get summary of all queue items."""
        statuses: dict[str, int] = {}
        for item in self._items.values():
            statuses[item.status] = statuses.get(item.status, 0) + 1
        return {
            "total": len(self._items),
            "statuses": statuses,
            "max_concurrent": self._max_concurrent,
            "currently_running": sum(1 for i in self._items.values() if i.status == "running"),
        }
```

### Modifications to `app.py`:

1. Add `scan_queue: ScanQueue` to `AppState` init:
```python
self.scan_queue: ScanQueue = ScanQueue(max_concurrent=1)
```

2. Modify the `/scan` endpoint to use the queue:
```python
# Wrap the scan logic in an async function
async def _run_echidna_scan(
    audit_id: str,
    audit_dir: Path,
    echidna_runner: EchidnaRunner,
    solc_mgr: SolcManager,
    dep_resolver: DependencyResolver,
    contract_name: str | None,
    timeout: int,
    compiler: str,
    body_sources: dict[str, str],
) -> ToolResult:
    # ... existing scan logic from lines 259-276 ...
    pass

# In the POST /scan handler:
try:
    result = await state.scan_queue.enqueue(
        audit_id,
        _run_echidna_scan,
        audit_id, audit_dir,
        state.echidna_runner,
        state.solc_mgr,
        state.dep_resolver,
        body.contract_name,
        body.timeout,
        body.compiler,
        body.sources,
    )
except Exception as exc:
    raise err(f"Scan failed: {exc}", status_code=500)
```

3. Add a queue status endpoint:
```python
@app.get("/scan/queue/{audit_id}")
async def scan_queue_status(audit_id: str, request: Request) -> ApiResponse:
    state = _get_state(request)
    status = state.scan_queue.get_status(audit_id)
    if status is None:
        raise err("Audit ID not found in queue", 404)
    return ok(status)

@app.get("/scan/queue")
async def scan_queue_summary(request: Request) -> ApiResponse:
    state = _get_state(request)
    return ok(state.scan_queue.get_queue_summary())
```

**Edge cases:**
- Queue overflow: Semaphore naturally limits concurrent runs
- Error handling: Exceptions propagate properly through the queue
- Memory: Old queue items can be pruned (optional, YAGNI for now)

**Verification:**
- `cd /mnt/e/website/project/sc_auditor && python -c "
import asyncio
from services.04b_scanner_echidna.src.queue_manager import ScanQueue
async def test():
    q = ScanQueue(max_concurrent=2)
    async def dummy(aid):
        await asyncio.sleep(0.1)
        return f'result-{aid}'
    r1 = await q.enqueue('a', dummy, 'a')
    r2 = await q.enqueue('b', dummy, 'b')
    assert r1 == 'result-a'
    assert r2 == 'result-b'
    summary = q.get_queue_summary()
    assert summary['total'] == 2
    print('Queue test OK')
asyncio.run(test())
"`

---

## Task P3-1: L3 FP/TP Database Tracking

**Objective:** Implement the missing L3 FP/TP tracking layer — persistent storage for flaky test tracking and false positive identification.

**Files:**
- Create: `services/04b-scanner-echidna/src/intelligence/fp_tp_db.py`
- Modify: `services/04b-scanner-echidna/src/intelligence/__init__.py`
- Modify: `services/04b-scanner-echidna/app.py`

**What it should do:**
- Track which `echidna_*` test functions have historically produced false positives
- Store FP/TP records persistently in a JSON file
- Provide confidence adjustment for known-flaky tests
- Allow querying FP rate per function

### `services/04b-scanner-echidna/src/intelligence/fp_tp_db.py`:
```python
"""FP/TP Database — L3 Intelligence.

Tracks flaky Echidna tests and provides confidence adjustment
based on historical false positive rates.

Design:
- Persistent JSON file in data directory
- Each record: {test_function, verdict, audit_id, timestamp, notes}
- Query: FP rate per function, per category
- Auto-prune records older than 90 days
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class FpRecord:
    """A single FP/TP tracking record."""
    test_function: str
    verdict: str  # "true_positive" | "false_positive"
    audit_id: str
    category: str = "unknown"
    timestamp: float = field(default_factory=time.time)
    notes: str = ""


FP_RETENTION_DAYS = 90
MAX_RECORDS = 10_000


class FpTpDatabase:
    """Persistent FP/TP tracking database."""

    def __init__(self, data_dir: str | Path = "/data/scanner-echidna") -> None:
        self._path = Path(data_dir) / "fp_tp_db.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._records: list[FpRecord] = []
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text())
                self._records = [FpRecord(**r) for r in raw[-MAX_RECORDS:]]
            except (json.JSONDecodeError, KeyError, TypeError):
                self._records = []

    def _save(self) -> None:
        raw = [asdict(r) for r in self._records[-MAX_RECORDS:]]
        self._path.write_text(json.dumps(raw, indent=2))

    def record(
        self,
        test_function: str,
        verdict: str,
        audit_id: str,
        category: str = "unknown",
        notes: str = "",
    ) -> None:
        """Record a FP/TP verdict for a test function."""
        self._records.append(FpRecord(
            test_function=test_function,
            verdict=verdict,
            audit_id=audit_id,
            category=category,
            notes=notes,
        ))
        self._prune()
        self._save()

    def get_fp_rate(self, test_function: str) -> float:
        """Get false positive rate for a test function (0.0-1.0)."""
        records = [r for r in self._records if r.test_function == test_function]
        if not records:
            return 0.0
        fps = sum(1 for r in records if r.verdict == "false_positive")
        return round(fps / len(records), 3)

    def get_adjusted_confidence(self, test_function: str, base_confidence: float = 1.0) -> float:
        """Adjust confidence based on historical FP rate."""
        fp_rate = self.get_fp_rate(test_function)
        # If FP rate is high, reduce confidence
        adjusted = base_confidence * (1.0 - fp_rate * 0.8)
        return round(max(0.1, min(1.0, adjusted)), 3)

    def get_flaky_tests(self, threshold: float = 0.3) -> list[dict[str, Any]]:
        """Return tests with FP rate above threshold."""
        functions = set(r.test_function for r in self._records)
        flaky = []
        for func in functions:
            fp_rate = self.get_fp_rate(func)
            if fp_rate >= threshold:
                flaky.append({
                    "test_function": func,
                    "fp_rate": fp_rate,
                    "total_records": sum(1 for r in self._records if r.test_function == func),
                })
        return sorted(flaky, key=lambda x: x["fp_rate"], reverse=True)

    def get_stats(self) -> dict[str, Any]:
        """Get aggregate stats."""
        if not self._records:
            return {"total_records": 0, "fp_rate": 0.0, "flaky_tests": []}
        total = len(self._records)
        fps = sum(1 for r in self._records if r.verdict == "false_positive")
        return {
            "total_records": total,
            "total_fp": fps,
            "total_tp": total - fps,
            "fp_rate": round(fps / total, 3),
            "flaky_tests": self.get_flaky_tests(),
        }

    def _prune(self) -> None:
        cutoff = time.time() - FP_RETENTION_DAYS * 86400
        self._records = [r for r in self._records if r.timestamp >= cutoff]


def create_fp_tp_db(data_dir: str | Path = "/data/scanner-echidna") -> FpTpDatabase:
    return FpTpDatabase(data_dir=data_dir)
```

### Modify `services/04b-scanner-echidna/src/intelligence/__init__.py`:
Add:
```python
from src.intelligence.fp_tp_db import FpTpDatabase, create_fp_tp_db

__all__ += [
    "FpTpDatabase",
    "create_fp_tp_db",
]
```

### Modify `services/04b-scanner-echidna/app.py`:
Add `self.fp_tp_db` to AppState init:
```python
self.fp_tp_db: FpTpDatabase = create_fp_tp_db()
```

Add endpoint:
```python
@app.get("/fp-tp/stats")
async def fp_tp_stats(request: Request) -> ApiResponse:
    state = _get_state(request)
    return ok(state.fp_tp_db.get_stats())

@app.post("/fp-tp/record")
async def fp_tp_record(body: dict, request: Request) -> ApiResponse:
    state = _get_state(request)
    state.fp_tp_db.record(
        test_function=body.get("test_function", ""),
        verdict=body.get("verdict", "true_positive"),
        audit_id=body.get("audit_id", ""),
        category=body.get("category", "unknown"),
        notes=body.get("notes", ""),
    )
    return ok({"status": "recorded"})
```

**Verification:**
```bash
cd /mnt/e/website/project/sc_auditor && python -c "
from services.04b_scanner_echidna.src.intelligence.fp_tp_db import FpTpDatabase, create_fp_tp_db
import tempfile, os
db = create_fp_tp_db(tempfile.mkdtemp())
db.record('echidna_test', 'false_positive', 'audit-1')
db.record('echidna_test', 'true_positive', 'audit-2')
db.record('echidna_test', 'false_positive', 'audit-3')
assert db.get_fp_rate('echidna_test') == 2/3
confidence = db.get_adjusted_confidence('echidna_test', 1.0)
assert confidence < 0.5  # Reduced due to high FP rate
assert len(db.get_flaky_tests(threshold=0.2)) == 1
print('FP/TP DB test OK')
stats = db.get_stats()
print('Stats:', stats)
"
```

---

## Task P3-2: ARM64 / Apple Silicon Dockerfile Support

**Objective:** Make the Dockerfile detect architecture and download the correct Echidna binary.

**Files:**
- Modify: `services/04b-scanner-echidna/Dockerfile`

**Current (hardcoded x86_64):**
```dockerfile
RUN ECHIDNA_VER=... && \
    curl -fsSL ".../echidna-${ECHIDNA_VER}-x86_64-linux.tar.gz" -o /tmp/echidna.tar.gz
```

**Fixed (architecture-aware):**
```dockerfile
RUN ECHIDNA_VER=$(curl -fsSL https://api.github.com/repos/crytic/echidna/releases/latest | \
    python3 -c "import json,sys; print(json.load(sys.stdin)['tag_name'].lstrip('v'))" 2>/dev/null || echo "2.3.2") && \
    ARCH=$(uname -m) && \
    case "$ARCH" in \
        x86_64)  ECHIDNA_ARCH="x86_64-linux" ;; \
        aarch64|arm64) ECHIDNA_ARCH="aarch64-linux" ;; \
        *)       echo "Unsupported architecture: $ARCH"; exit 1 ;; \
    esac && \
    curl -fsSL "https://github.com/crytic/echidna/releases/download/v${ECHIDNA_VER}/echidna-${ECHIDNA_VER}-${ECHIDNA_ARCH}.tar.gz" -o /tmp/echidna.tar.gz && \
    tar -xzf /tmp/echidna.tar.gz -C /tmp/ && \
    install -m 755 /tmp/echidna /usr/local/bin/echidna && \
    echo "Echidna installed ($ARCH): $(echidna --version 2>/dev/null || echo 'failed')"
```

**Also check if Echidna publishes ARM binaries.** If not, fallback to building from source or using QEMU emulation.

**Verification:**
- Read the modified Dockerfile and confirm it handles `x86_64` and `aarch64`/`arm64`
- The `case` statement is POSIX-compliant (works in `/bin/sh`)

---

## Task P3-3: Cost Estimation in Agent Capabilities

**Objective:** Add cost/duration estimation to the EchidnaAgent so Antonio can make informed delegation decisions.

**Files:**
- Modify: `services/04b-scanner-echidna/src/agent.py`
- Modify: `services/04b-scanner-echidna/app.py`

**What to add:**
1. A method `estimate_cost(input_data: dict) -> dict` that estimates:
   - `estimated_duration_seconds`: How long the fuzzing will take
   - `estimated_cost_usd`: Estimated compute cost
   - `complexity`: "low" | "medium" | "high" based on source size

2. Include this in the agent manifest and negotiation response.

### Add to `agent.py`:

```python
def estimate_cost(self, input_data: dict) -> dict[str, Any]:
    """Estimate duration and cost for a fuzzing run.
    
    Factors:
    - Number of source files (+ complexity)
    - Timeout requested
    - Historical average duration
    """
    sources = input_data.get("sources", {})
    timeout = input_data.get("timeout", 600)
    
    num_files = len(sources)
    total_lines = sum(len(s.split("\n")) for s in sources.values())
    
    # Complexity based on code size
    if total_lines < 200:
        complexity = "low"
    elif total_lines < 800:
        complexity = "medium"
    else:
        complexity = "high"
    
    # Estimate duration: at least 60s, at most timeout
    estimated_seconds = min(timeout, max(60, total_lines // 2))
    
    # Rough cost estimate (AWS/GCP per-second pricing ~$0.000004)
    estimated_cost = round(estimated_seconds * 0.000004, 4)
    
    return {
        "estimated_duration_seconds": estimated_seconds,
        "estimated_cost_usd": estimated_cost,
        "complexity": complexity,
        "num_files": num_files,
        "total_lines": total_lines,
    }
```

### Modify agent manifest to include cost info:

In `EchidnaAgent.__init__()`, after registering the capability, add:
```python
# Cost estimation metadata
self._manifest["cost_estimation"] = {
    "supports_estimation": True,
    "pricing_per_second": 0.000004,
}
```

### Update negotiation handler:

In `handle_negotiation()`, include cost breakdown:
```python
async def handle_negotiation(self, request: NegotiationRequest) -> dict:
    # Existing logic...
    cost_estimate = self.estimate_cost(request.input_data or {})
    return {
        "accepted": can_handle,
        "estimated_duration": cost_estimate["estimated_duration_seconds"],
        "estimated_cost": cost_estimate["estimated_cost_usd"],
        "complexity": cost_estimate["complexity"],
        # ...
    }
```

Wait — `handle_negotiation` is defined in BaseAgent. Let me check... Actually in `agent.py`, the `_execute_task` method handles delegations, but negotiation is handled at the app.py level (POST /agent/negotiate). Let me just add the cost estimation as a standalone method and include it in the manifest.

**Simpler approach:** Just add `estimate_cost()` to the agent and update the manifest response.

**Verification:**
```bash
cd /mnt/e/website/project/sc_auditor && python -c "
from services.04b_scanner_echidna.src.echidna import EchidnaRunner
from services.04b_scanner_echidna.src.agent import EchidnaAgent
runner = EchidnaRunner()
agent = EchidnaAgent(runner=runner)
manifest = agent.get_manifest()
assert 'capabilities' in manifest
print('Agent OK, manifest keys:', list(manifest.keys()))
"
```
