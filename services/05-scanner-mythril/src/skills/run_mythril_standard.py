"""RunMythrilStandardSkill — standard mythril CLI analysis."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class RunMythrilStandardSkill(BaseSkill):
    """Standard Mythril symbolic execution via CLI."""

    @property
    def name(self) -> str:
        return "run_mythril_standard"

    @property
    def description(self) -> str:
        return (
            "Run standard Mythril symbolic analysis on Solidity source code "
            "via the mythril CLI. Returns findings, raw output, and execution metrics."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "object",
                    "description": "Source files keyed by path",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max duration per function in seconds",
                },
                "depth": {
                    "type": "integer",
                    "description": "Mythril analysis depth (default 32)",
                },
            },
            "required": ["sources"],
        }

    @property
    def category(self) -> str:
        return "scanning"

    async def run(
        self,
        sources: dict[str, str],
        timeout: int = 300,
        depth: int = 32,
        **kwargs: Any,
    ) -> dict[str, Any]:
        import asyncio
        import json
        import subprocess
        import tempfile
        import time
        from pathlib import Path

        if not sources:
            raise ValueError("At least one source file is required")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            for file_path, source_code in sources.items():
                target = tmp_path / file_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source_code, encoding="utf-8")

            start = time.monotonic()
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    [
                        "mythril", "analyze",
                        "--solc-json", str(tmp_path / "combined.json"),
                        "--max-depth", str(depth),
                    ],
                    capture_output=True, text=True,
                    timeout=timeout,
                    cwd=str(tmp_path),
                )
                elapsed = time.monotonic() - start
                success = result.returncode == 0

                findings = []
                if success and result.stdout:
                    try:
                        parsed = json.loads(result.stdout)
                        findings = parsed.get("issues", parsed if isinstance(parsed, list) else [])
                    except json.JSONDecodeError:
                        pass

                return {
                    "findings": findings,
                    "total_findings": len(findings),
                    "raw_output": result.stdout[-5000:] if result.stdout else "",
                    "raw_error": result.stderr[-1000:] if result.stderr else "",
                    "success": success,
                    "mythril_available": True,
                    "duration_seconds": round(elapsed, 2),
                }
            except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
                elapsed = time.monotonic() - start
                return {
                    "findings": [],
                    "total_findings": 0,
                    "error": str(exc),
                    "success": False,
                    "mythril_available": isinstance(exc, subprocess.TimeoutExpired),
                    "duration_seconds": round(elapsed, 2),
                }
