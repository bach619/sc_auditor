"""TestIntelligence — discovers, runs, and analyzes test suites in a repository."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("vyper.orchestrator.test_intel")


@dataclass
class TestAnalysis:
    """Result of a full test intelligence scan."""

    has_tests: bool = False
    test_count: int = 0
    passing: int = 0
    failing: int = 0
    skipped: int = 0
    error_count: int = 0  # test errors (setup failures etc.)
    coverage_percent: float | None = None
    frameworks_used: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    duration_seconds: float | None = None
    output: str = ""
    errors: list[str] = field(default_factory=list)


# ── Framework detection patterns ────────────────────────────────

_FRAMEWORK_PATTERNS: dict[str, list[str]] = {
    "hardhat": ["hardhat.config", "hardhat.config.ts", "hardhat.config.js"],
    "foundry": ["foundry.toml"],
    "truffle": ["truffle-config.js", "truffle-config.ts"],
    "brownie": ["brownie-config.yaml"],
    "forge": [".forge.config"],
    "dapptools": ["dapp.tools", "Makefile"],
    "echidna": ["echidna.yaml", ".echidna"],
    "hevm": [".hevm"],
}


_TEST_DIR_PATTERNS: list[str] = [
    "test",
    "tests",
    "spec",
    "specs",
    "hardhat/test",
    "contracts/test",
    "test/foundry",
    "test/hardhat",
    "test/unit",
    "test/integration",
    "test/fuzz",
]


_TEST_FILE_PATTERNS: list[str] = [
    "*.test.js",
    "*.test.ts",
    "*.spec.js",
    "*.spec.ts",
    "*.t.sol",  # Foundry
    "Test*.sol",
    "*Test.sol",
    "test_*.py",  # Brownie
    "*_test.py",
    "*.test.sol",
]


class TestIntelligence:
    """Discover, run, and analyze tests in a Solidity repository."""

    def __init__(self) -> None:
        self._frameworks: list[str] = []

    # ── Test discovery ──────────────────────────────────────────

    def find_test_frameworks(self, repo_path: Path) -> list[str]:
        """Detect which test framework(s) the repo uses."""
        detected: list[str] = []
        for framework, patterns in _FRAMEWORK_PATTERNS.items():
            for pattern in patterns:
                if list(repo_path.rglob(pattern)):
                    detected.append(framework)
                    break
        # Also check package.json for devDependencies
        pkg_json = repo_path / "package.json"
        if pkg_json.exists():
            try:
                import json
                data = json.loads(pkg_json.read_text("utf-8"))
                deps = {
                    **data.get("devDependencies", {}),
                    **data.get("dependencies", {}),
                }
                if "hardhat" in deps:
                    detected.append("hardhat")
                if "@nomiclabs/hardhat-waffle" in deps:
                    detected.append("hardhat-waffle")
                if "truffle" in deps:
                    detected.append("truffle")
                if "solc" in deps:
                    detected.append("solc")
            except (json.JSONDecodeError, OSError):
                pass
        return list(set(detected))

    def find_tests(self, repo_path: Path) -> TestAnalysis:
        """Discover test files without running them."""
        analysis = TestAnalysis()
        analysis.frameworks_used = self.find_test_frameworks(repo_path)

        test_files: set[Path] = set()
        for dir_pattern in _TEST_DIR_PATTERNS:
            test_dir = repo_path / dir_pattern
            if test_dir.exists() and test_dir.is_dir():
                for file_pattern in _TEST_FILE_PATTERNS:
                    test_files.update(test_dir.rglob(file_pattern))

        if not test_files:
            return analysis

        analysis.has_tests = True
        analysis.test_count = len(test_files)
        analysis.test_files = sorted(str(p.relative_to(repo_path)) for p in test_files)
        return analysis

    # ── Test execution ──────────────────────────────────────────

    def run_tests(self, repo_path: Path, timeout: int = 600) -> TestAnalysis:
        """Run tests and return results. Supports Foundry and Hardhat.

        Detects which framework is available and runs accordingly.
        Returns analysis with pass/fail counts.
        """
        frameworks = self.find_test_frameworks(repo_path)
        analysis = TestAnalysis()
        analysis.frameworks_used = frameworks

        # Prefer Foundry (forge) over Hardhat (npx hardhat) for speed
        if "foundry" in frameworks or "forge" in frameworks:
            return self._run_forge(repo_path, timeout)
        elif "hardhat" in frameworks:
            return self._run_hardhat(repo_path, timeout)
        elif "brownie" in frameworks:
            return self._run_brownie(repo_path, timeout)
        else:
            # Try generic npm test
            return self._run_npm_test(repo_path, timeout)

    def _run_forge(self, repo_path: Path, timeout: int) -> TestAnalysis:
        """Run `forge test` and parse output."""
        analysis = TestAnalysis()
        analysis.frameworks_used = ["foundry"]
        try:
            result = subprocess.run(
                ["forge", "test", "--json"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            analysis.output = result.stdout + result.stderr
            analysis.duration_seconds = timeout
            # Parse forge JSON output
            self._parse_forge_output(analysis, result.stdout, result.stderr, result.returncode)
        except subprocess.TimeoutExpired:
            analysis.errors.append(f"Test run timed out after {timeout}s")
        except FileNotFoundError:
            analysis.errors.append("forge binary not found")
        except Exception as e:
            analysis.errors.append(str(e))
        return analysis

    def _run_hardhat(self, repo_path: Path, timeout: int) -> TestAnalysis:
        """Run `npx hardhat test`."""
        analysis = TestAnalysis()
        analysis.frameworks_used = ["hardhat"]
        try:
            result = subprocess.run(
                ["npx", "hardhat", "test"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            analysis.output = result.stdout + result.stderr
            analysis.duration_seconds = timeout
            analysis.passing = 1 if result.returncode == 0 else 0
            analysis.failing = 0 if result.returncode == 0 else 1
            if result.returncode != 0:
                analysis.errors.append("Hardhat tests failed")
        except subprocess.TimeoutExpired:
            analysis.errors.append(f"Test run timed out after {timeout}s")
        except FileNotFoundError:
            analysis.errors.append("npx/hardhat not found")
        except Exception as e:
            analysis.errors.append(str(e))
        return analysis

    def _run_brownie(self, repo_path: Path, timeout: int) -> TestAnalysis:
        analysis = TestAnalysis()
        analysis.frameworks_used = ["brownie"]
        try:
            result = subprocess.run(
                ["brownie", "test"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            analysis.output = result.stdout + result.stderr
            analysis.duration_seconds = timeout
            analysis.passing = 1 if result.returncode == 0 else 0
            analysis.failing = 0 if result.returncode == 0 else 1
        except subprocess.TimeoutExpired:
            analysis.errors.append(f"Brownie test timed out after {timeout}s")
        except FileNotFoundError:
            analysis.errors.append("brownie not found")
        except Exception as e:
            analysis.errors.append(str(e))
        return analysis

    def _run_npm_test(self, repo_path: Path, timeout: int) -> TestAnalysis:
        analysis = TestAnalysis()
        try:
            result = subprocess.run(
                ["npm", "test", "--", "--json"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            analysis.output = result.stdout + result.stderr
            analysis.duration_seconds = timeout
            analysis.passing = 1 if result.returncode == 0 else 0
        except subprocess.TimeoutExpired:
            analysis.errors.append(f"npm test timed out after {timeout}s")
        except FileNotFoundError:
            analysis.errors.append("npm not found")
        except Exception as e:
            analysis.errors.append(str(e))
        return analysis

    # ── Forge output parser ─────────────────────────────────────

    @staticmethod
    def _parse_forge_output(
        analysis: TestAnalysis, stdout: str, stderr: str, returncode: int
    ) -> None:
        """Parse `forge test --json` output into pass/fail counts."""
        import json as json_mod

        analysis.has_tests = True
        analysis.test_count = 0
        analysis.passing = 0
        analysis.failing = 0

        # Foundry's --json emits NDJSON lines
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json_mod.loads(line)
                analysis.test_count += 1
                kind = record.get("kind", "")
                status = record.get("status", "")
                if status == "success" or kind == "test_success":
                    analysis.passing += 1
                elif status == "failure" or kind == "test_failure":
                    analysis.failing += 1
                elif kind == "test_skipped":
                    analysis.skipped += 1
            except (json_mod.JSONDecodeError, KeyError):
                pass

        # Fallback: if no JSON records, use exit code
        if analysis.test_count == 0:
            analysis.test_count = 1
            if returncode == 0:
                analysis.passing = 1
            else:
                analysis.failing = 1
                analysis.errors.append(stderr[:500])

    # ── Coverage ─────────────────────────────────────────────────

    def analyze_coverage(self, repo_path: Path, timeout: int = 300) -> TestAnalysis:
        """Run code coverage analysis. Tries Foundry first, then Hardhat."""
        frameworks = self.find_test_frameworks(repo_path)

        if "foundry" in frameworks or "forge" in frameworks:
            return self._forge_coverage(repo_path, timeout)
        elif "hardhat" in frameworks:
            return self._hardhat_coverage(repo_path, timeout)

        analysis = TestAnalysis()
        analysis.errors.append("No supported framework found for coverage")
        return analysis

    def _forge_coverage(self, repo_path: Path, timeout: int) -> TestAnalysis:
        analysis = TestAnalysis()
        analysis.frameworks_used = ["foundry"]
        try:
            result = subprocess.run(
                ["forge", "coverage", "--report", "summary"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            analysis.output = result.stdout + result.stderr
            # Parse coverage percentage from " Lines: 45.5%"
            for line in result.stdout.splitlines():
                if "Lines:" in line:
                    try:
                        pct_str = line.split("Lines:")[1].split("%")[0].strip()
                        analysis.coverage_percent = float(pct_str)
                    except (ValueError, IndexError):
                        pass
                    break
            analysis.duration_seconds = timeout
        except subprocess.TimeoutExpired:
            analysis.errors.append(f"Forge coverage timed out after {timeout}s")
        except FileNotFoundError:
            analysis.errors.append("forge binary not found")
        except Exception as e:
            analysis.errors.append(str(e))
        return analysis

    def _hardhat_coverage(self, repo_path: Path, timeout: int) -> TestAnalysis:
        analysis = TestAnalysis()
        analysis.frameworks_used = ["hardhat"]
        try:
            result = subprocess.run(
                ["npx", "hardhat", "coverage"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            analysis.output = result.stdout + result.stderr
            # Parse coverage from lines like "-----------------------|----------|..."
            for line in result.stdout.splitlines():
                if "%" in line and "100.00" not in line:
                    parts = line.split("|")
                    if len(parts) >= 4:
                        for part in parts:
                            pct_str = part.strip().replace("%", "")
                            try:
                                val = float(pct_str)
                                if 0 <= val <= 100:
                                    analysis.coverage_percent = val
                                    break
                            except ValueError:
                                continue
                    if analysis.coverage_percent is not None:
                        break
            analysis.duration_seconds = timeout
        except subprocess.TimeoutExpired:
            analysis.errors.append(f"Hardhat coverage timed out after {timeout}s")
        except FileNotFoundError:
            analysis.errors.append("npx/hardhat not found")
        except Exception as e:
            analysis.errors.append(str(e))
        return analysis


__all__ = ["TestIntelligence", "TestAnalysis"]
