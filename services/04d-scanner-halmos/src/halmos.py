"""Halmos runner — executes halmos CLI on Foundry test files.

Halmos (a16z) performs symbolic execution on Foundry tests.
Input: Foundry test file (.t.sol) or project directory.
Output: Test results (pass/fail) with counter-examples.

Reference: https://github.com/a16z/halmos
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger()


class HalmosFinding:
    """A symbolic execution finding from Halmos."""

    def __init__(
        self,
        test_name: str,
        status: str,
        calldata: str | None = None,
        error_message: str | None = None,
        duration: float = 0.0,
    ) -> None:
        self.title = f"Halmos: {test_name}"
        self.description = self._build_description(status, calldata, error_message)
        self.severity = "high" if status == "fail" else ("medium" if status == "error" else "info")
        self.test_name = test_name
        self.status = status
        self.calldata = calldata or ""
        self.error_message = error_message or ""
        self.duration = duration
        self.swc_id = None
        self.category = "symbolic_execution"
        self.confidence = 0.9 if status == "fail" else 0.5

    @staticmethod
    def _build_description(status: str, calldata: str | None, error: str | None) -> str:
        if status == "fail":
            return (
                f"Symbolic execution found a counter-example.\n"
                f"Test: {status}\n"
                f"Calldata: {calldata or 'N/A'}"
            )
        elif status == "error":
            return f"Symbolic execution error: {error or 'Unknown error'}"
        return "Test passed symbolic execution."

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "test_name": self.test_name,
            "status": self.status,
            "calldata": self.calldata,
            "error_message": self.error_message,
            "duration": self.duration,
            "swc_id": self.swc_id,
            "category": self.category,
            "confidence": self.confidence,
        }


class HalmosResult:
    """Result of a Halmos symbolic execution run."""

    def __init__(
        self,
        success: bool,
        findings: list[HalmosFinding],
        errors: list[str],
        statistics: dict[str, Any] | None = None,
    ) -> None:
        self.success = success
        self.findings = findings
        self.errors = errors
        self.statistics = statistics or {}
        self.passed = statistics.get("num_passed", 0) if statistics else 0
        self.failed = statistics.get("num_failed", 0) if statistics else 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "findings": [f.to_dict() for f in self.findings],
            "errors": self.errors,
            "statistics": self.statistics,
            "passed": self.passed,
            "failed": self.failed,
        }


class HalmosRunner:
    """Run Halmos symbolic execution on Foundry test files."""

    def __init__(self, halmos_bin: str = "halmos", forge_bin: str = "forge") -> None:
        self._halmos_bin = halmos_bin
        self._forge_bin = forge_bin
        self._work_dir = Path("/data/scanner-halmos")
        self._work_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        sources: dict[str, str],
        timeout: int = 300,
        function: str | None = None,
    ) -> HalmosResult:
        """Run Halmos on provided Solidity sources.

        Args:
            sources: Dict of {filepath: source_code}.
            timeout: Total timeout in seconds.
            function: Specific test function to run (optional).

        Returns:
            HalmosResult with findings and statistics.
        """
        audit_id = str(uuid.uuid4())
        project_dir = self._work_dir / audit_id
        findings: list[HalmosFinding] = []
        errors: list[str] = []
        effective_timeout = timeout

        try:
            # Write sources to temp project directory
            self._write_sources(project_dir, sources)

            # ── Large contract detection ───────────────────────
            timeout_multiplier, size_error = self._check_contract_size(project_dir)
            if size_error:
                log.warning("halmos.contract_too_large", error=size_error)
                return HalmosResult(success=False, findings=findings, errors=[size_error])

            effective_timeout = int(timeout * timeout_multiplier)
            if timeout_multiplier > 1:
                log.info(
                    "halmos.timeout_adjusted",
                    original=timeout,
                    effective=effective_timeout,
                    multiplier=timeout_multiplier,
                )

            # Step 1: forge build
            log.info("halmos.forge_build.start", project=str(project_dir))
            build_ok = self._run_forge_build(project_dir, effective_timeout)
            if not build_ok:
                errors.append("Forge build failed — check source code for compilation errors")
                return HalmosResult(success=False, findings=findings, errors=errors)

            # Step 2: halmos
            log.info("halmos.run.start", project=str(project_dir), function=function)
            halmos_output = self._run_halmos(project_dir, effective_timeout // 2, function)

            # Step 3: Parse output
            parsed = self._parse_output(halmos_output)
            findings = parsed["findings"]
            errors.extend(parsed["errors"])
            stats = parsed["statistics"]

            success = parsed["statistics"].get("num_failed", 0) == 0

            log.info(
                "halmos.run.complete",
                passed=parsed["statistics"].get("num_passed", 0),
                failed=parsed["statistics"].get("num_failed", 0),
                errors=len(errors),
            )

            return HalmosResult(
                success=success,
                findings=findings,
                errors=errors,
                statistics=stats,
            )

        except subprocess.TimeoutExpired:
            log.warning("halmos.timeout", timeout=effective_timeout)
            return HalmosResult(
                success=False,
                findings=findings,
                errors=[f"Halmos timeout after {effective_timeout}s"],
                statistics={"total_tests": 0, "num_passed": 0, "num_failed": 0, "total_time": effective_timeout},
            )
        except Exception as exc:
            log.exception("halmos.run.failed", error=str(exc))
            return HalmosResult(
                success=False,
                findings=findings,
                errors=[f"Halmos execution error: {str(exc)[:500]}"],
            )

        finally:
            # Cleanup
            try:
                shutil.rmtree(project_dir, ignore_errors=True)
            except OSError:
                pass

    def _write_sources(self, project_dir: Path, sources: dict[str, str]) -> None:
        """Write Solidity sources to project directory."""
        for filepath, content in sources.items():
            target = project_dir / filepath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        # Ensure foundry.toml exists
        foundry_toml = project_dir / "foundry.toml"
        if not foundry_toml.exists():
            foundry_toml.write_text(
                "[profile.default]\nsolc_version = \"0.8.20\"\n"
                "src = \"src\"\ntest = \"test\"\n",
                encoding="utf-8",
            )

    def _run_forge_build(self, project_dir: Path, timeout: int) -> bool:
        """Run forge build, return True if successful."""
        try:
            result = subprocess.run(
                [self._forge_bin, "build"],
                capture_output=True, text=True,
                timeout=timeout, cwd=str(project_dir),
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            log.warning("halmos.forge_build_failed", error=str(exc))
            return False

    def _run_halmos(
        self,
        project_dir: Path,
        timeout: int,
        function: str | None = None,
    ) -> str:
        """Run halmos and return stdout."""
        cmd = [self._halmos_bin, "--json"]
        if function:
            cmd.extend(["--function", function])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True,
                timeout=timeout, cwd=str(project_dir),
            )
            return result.stdout or result.stderr
        except subprocess.TimeoutExpired:
            return json.dumps({
                "tests": [],
                "statistics": {
                    "total_tests": 0,
                    "num_passed": 0,
                    "num_failed": 0,
                    "total_time": 0,
                },
            })
        except FileNotFoundError:
            return json.dumps({
                "error": "Halmos CLI not found",
                "tests": [],
                "statistics": {"total_tests": 0, "num_passed": 0, "num_failed": 0, "total_time": 0},
            })

    def _parse_output(self, output: str) -> dict[str, Any]:
        """Parse Halmos JSON output.

        Expected format:
        {
          "tests": [
            {"name": "test_foo", "status": "fail", "num_models": 1,
             "models": [{"name": "model_0", "calldata": "0x..."}], "time": 1.23}
          ],
          "statistics": {"total_tests": 10, "num_passed": 8, "num_failed": 2, "total_time": 12.34}
        }
        """
        findings: list[HalmosFinding] = []
        errors: list[str] = []
        stats: dict[str, Any] = {
            "total_tests": 0, "num_passed": 0,
            "num_failed": 0, "total_time": 0,
        }

        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            # Try to find JSON object in output
            match = re.search(r'\{.*\}', output, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    errors.append("Could not parse Halmos output as JSON")
                    return {"findings": findings, "errors": errors, "statistics": stats}
            else:
                errors.append(f"No JSON found in Halmos output: {output[:500]}")
                return {"findings": findings, "errors": errors, "statistics": stats}

        # Handle error response
        if "error" in data:
            errors.append(data["error"])
            return {"findings": findings, "errors": errors, "statistics": stats}

        # Parse tests
        tests = data.get("tests", [])
        for test in tests:
            name = test.get("name", "unknown")
            status = test.get("status", "pass")
            duration = test.get("time", 0.0)

            calldata = None
            error_msg = None

            if status == "fail":
                models = test.get("models", [])
                if models:
                    calldata = models[0].get("calldata", "")
            elif status == "error":
                error_msg = test.get("error", test.get("message", "Unknown error"))

            finding = HalmosFinding(
                test_name=name,
                status=status,
                calldata=calldata,
                error_message=error_msg,
                duration=duration,
            )
            findings.append(finding)

        # Parse statistics
        stats = data.get("statistics", stats)
        if not stats:
            stats = {"total_tests": len(tests)}
            stats["num_passed"] = sum(1 for t in tests if t.get("status") == "pass")
            stats["num_failed"] = sum(1 for t in tests if t.get("status") == "fail")
            stats["total_time"] = sum(t.get("time", 0) for t in tests)

        return {"findings": findings, "errors": errors, "statistics": stats}

    def _check_contract_size(self, project_dir: Path) -> tuple[float, str | None]:
        """Check total size of Solidity files in project directory.

        Returns:
            Tuple of (timeout_multiplier, error_message).
            If error_message is not None, execution should abort:
            - > 10 MB → warning, timeout doubled
            - > 50 MB → abort with error
        """
        total_size = 0
        try:
            for fpath in project_dir.rglob("*.sol"):
                try:
                    total_size += fpath.stat().st_size
                except OSError:
                    continue
        except OSError:
            return 1.0, None

        total_mb = total_size / (1024 * 1024)

        if total_mb > 50:
            return 1.0, (
                f"Contract too large for symbolic execution "
                f"({total_mb:.1f} MB > 50 MB limit)"
            )

        if total_mb > 10:
            log.warning(
                "halmos.large_contract",
                size_mb=round(total_mb, 1),
                timeout_multiplier=2.0,
            )
            return 2.0, None

        return 1.0, None

    def check_available(self) -> tuple[bool, str | None]:
        """Check if halmos is available and return version."""
        try:
            result = subprocess.run(
                [self._halmos_bin, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            version = (result.stdout.strip() or result.stderr.strip())[:100]
            if result.returncode == 0:
                return True, version or "installed"
            return True, version or "installed (unknown version)"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False, None

    def check_forge(self) -> tuple[bool, str | None]:
        """Check if forge is available."""
        try:
            result = subprocess.run(
                [self._forge_bin, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            version = (result.stdout.strip() or result.stderr.strip())[:100]
            return result.returncode == 0, version or "installed"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False, None


def create_halmos_runner() -> HalmosRunner:
    return HalmosRunner()
