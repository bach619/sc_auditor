"""Shared Compilation Cache — compile once, serve to all scanners.

Problem: 6 scanner tools each compile Solidity independently.
         Same contract compiled 6x = 6x wasted CPU + time.

Solution: 03-source compiles once via solc, caches AST + bytecode
          to /data/compiled/. All scanner services read from cache.

Architecture:
    ┌─────────────┐
    │  03-source   │  Compile → /data/compiled/{hash}/
    │  (compiler)  │    ├── combined.json   (solc --combined-json)
    └──────┬───────┘    ├── StandardJson     (solc --standard-json)
           │            ├── ast.json         (AST)
           │            ├── bytecode.bin     (deployed bytecode)
           │            └── sourcemap.json   (source mapping)
           │
    ┌──────┼───────┬──────────┬──────────┬──────────┐
    │      ▼       ▼          ▼          ▼          ▼
    │  Slither   Mythril   Echidna    Halmos   Manticore
    │  (baca     (baca     (baca      (baca     (baca
    │   AST)     bytecode)  bytecode)  AST)      bytecode)
    └──────────────────────────────────────────────────┘

Usage:
    from src.compilation_cache import CompilationCache
    cache = CompilationCache()
    result = cache.compile_or_get(source_code, contract_name, compiler_version)

Performance:
    - First compile: ~5-15 detik (normal solc time)
    - Cache hit: <1ms (read from disk)
    - Re-compile trigger: source code SHA256 changed OR compiler version changed
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger("vyper.compilation_cache")

# Shared volume — all scanner containers mount this
COMPILED_DIR = Path("/data/compiled")


class CompilationCache:
    """Compile Solidity once, cache results for all scanner services.

    Mount /data/compiled as a shared Docker volume across:
    - 03-source (writes)
    - 04a-slither, 04b-echidna, 04c-forge, 04d-halmos,
      04e-manticore, 05-mythril (read)
    """

    def __init__(self, cache_dir: str = "/data/compiled") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0

    # ── Public API ──────────────────────────────────────────

    def compile_or_get(
        self,
        source_code: str,
        contract_name: str = "",
        compiler_version: str = "0.8.19",
        optimize: bool = True,
        optimize_runs: int = 200,
    ) -> dict:
        """Compile Solidity source, return cached result if available.

        Returns:
            {
                "hash": "sha256...",
                "cached": True/False,
                "ast": {...},           # solc --ast-compact-json
                "bytecode": "0x...",    # Deployed bytecode
                "abi": [...],           # Contract ABI
                "sourcemap": "...",     # Source mapping
                "combined": {...},      # Full solc --combined-json output
                "compile_time_ms": 1234,
            }
        """
        source_hash = hashlib.sha256(source_code.encode()).hexdigest()
        cache_key = f"{source_hash}_{compiler_version}_{optimize}_{optimize_runs}"
        cache_path = self.cache_dir / cache_key

        # Cache hit
        if cache_path.exists():
            self.hits += 1
            result = json.loads((cache_path / "compiled.json").read_text())
            result["cached"] = True
            logger.debug("Compilation cache HIT: %s", cache_key[:16])
            return result

        # Cache miss — compile
        self.misses += 1
        logger.info("Compilation cache MISS — compiling: %s", cache_key[:16])
        result = self._compile(source_code, contract_name, compiler_version, optimize, optimize_runs)

        # Store in cache
        cache_path.mkdir(parents=True, exist_ok=True)
        (cache_path / "compiled.json").write_text(json.dumps(result, indent=2))
        (cache_path / "source.sol").write_text(source_code)  # Keep source for debugging
        result["cached"] = False

        return result

    def get_by_hash(self, source_hash: str) -> Optional[dict]:
        """Find cached compilation by source hash (partial match)."""
        for subdir in self.cache_dir.iterdir():
            if subdir.is_dir() and subdir.name.startswith(source_hash):
                compiled = subdir / "compiled.json"
                if compiled.exists():
                    return json.loads(compiled.read_text())
        return None

    def invalidate(self, source_hash: str) -> int:
        """Remove cached compilation entries. Returns count removed."""
        removed = 0
        for subdir in self.cache_dir.iterdir():
            if subdir.is_dir() and subdir.name.startswith(source_hash):
                import shutil
                shutil.rmtree(subdir)
                removed += 1
        return removed

    def clear(self) -> int:
        """Clear entire cache. Returns count removed."""
        import shutil
        count = len(list(self.cache_dir.iterdir()))
        shutil.rmtree(self.cache_dir)
        self.cache_dir.mkdir()
        self.hits = 0
        self.misses = 0
        return count

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def stats(self) -> dict:
        cache_size = sum(
            f.stat().st_size
            for f in self.cache_dir.rglob("*")
            if f.is_file()
        )
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hit_rate, 3),
            "cache_entries": len(list(self.cache_dir.iterdir())),
            "cache_size_mb": round(cache_size / (1024 * 1024), 2),
        }

    # ── Internal — solc compilation ────────────────────────

    def _compile(
        self,
        source_code: str,
        contract_name: str,
        compiler_version: str,
        optimize: bool,
        optimize_runs: int,
    ) -> dict:
        """Run solc and return comprehensive compilation output."""
        import time
        start = time.perf_counter()

        # Determine solc binary
        solc_binary = self._get_solc(compiler_version)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sol_file = tmp / "contract.sol"
            sol_file.write_text(source_code)

            # --combined-json for full output
            combined_cmd = [
                solc_binary,
                str(sol_file),
                "--combined-json", "abi,ast,bin,bin-runtime,srcmap,srcmap-runtime,storage-layout",
                "--pretty-json",
            ]
            if optimize:
                combined_cmd.extend(["--optimize", "--optimize-runs", str(optimize_runs)])

            result = subprocess.run(
                combined_cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                raise RuntimeError(f"solc compilation failed: {result.stderr[:500]}")

            combined = json.loads(result.stdout)

            # Extract per-contract data
            ast = None
            bytecode = None
            abi = None
            sourcemap = None

            for key, data in combined.get("contracts", {}).items():
                if contract_name and contract_name not in key:
                    continue
                ast = combined.get("sourceList", [])
                bytecode = data.get("bin-runtime", "")
                abi = json.loads(data.get("abi", "[]"))
                sourcemap = data.get("srcmap-runtime", "")
                break

            elapsed = (time.perf_counter() - start) * 1000

            return {
                "hash": hashlib.sha256(source_code.encode()).hexdigest(),
                "compiler": compiler_version,
                "bytecode": bytecode,
                "abi": abi,
                "sourcemap": sourcemap,
                "combined": combined,
                "compile_time_ms": round(elapsed, 2),
                "optimized": optimize,
                "optimize_runs": optimize_runs,
            }

    @staticmethod
    def _get_solc(version: str) -> str:
        """Find solc binary — use solc-select if available."""
        # Try solc-select managed binary first
        try:
            result = subprocess.run(
                ["solc-select", "use", version, "--always-install"],
                capture_output=True, timeout=30,
            )
            if result.returncode == 0:
                # solc-select places binary in PATH
                result2 = subprocess.run(["which", "solc"], capture_output=True, text=True)
                if result2.returncode == 0:
                    return result2.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback: try direct solc
        try:
            subprocess.run(["solc", "--version"], capture_output=True, timeout=5)
            return "solc"
        except FileNotFoundError:
            pass

        # Last resort: system solc
        return "solc"


# ── Scanner-side helpers ─────────────────────────────────

def get_compiled_ast(source_hash: str, cache_dir: str = "/data/compiled") -> Optional[dict]:
    """Scanner services call this to get pre-compiled AST.
    
    Usage in 04a-slither Dockerfile:
        compiled = get_compiled_ast(source_hash)
        if compiled:
            # Use compiled["combined"] for slither Slither() init
            pass
    """
    cache_path = Path(cache_dir)
    for subdir in cache_path.iterdir():
        if subdir.is_dir() and subdir.name.startswith(source_hash):
            compiled = subdir / "compiled.json"
            if compiled.exists():
                return json.loads(compiled.read_text())
    return None
