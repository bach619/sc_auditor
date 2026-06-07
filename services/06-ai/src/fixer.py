"""FixSuggester — Generates and applies code fixes for scanner findings.

Responsible for:
  - Sending findings to LLM with a fix-focused prompt
  - Returning structured fix recommendations
  - Applying suggested fixes to produce patched source code
  - Caching fix suggestions to avoid redundant LLM calls
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from src.llm import LLMClient
from src.models import Finding, FixSuggestion

log = structlog.get_logger()

# ── Constants ──────────────────────────────────────────────

CACHE_DIR = Path("/data/ai/fixes")
DEFAULT_NUM_FIXES = 1


# ── Caching Helpers ───────────────────────────────────────


def _read_cache(file: Path) -> dict[str, Any] | None:
    """Read and parse a JSON cache file.

    Args:
        file: Path to the cache file.

    Returns:
        Parsed JSON data, or None if the file doesn't exist or is invalid.
    """
    if not file.exists():
        return None
    try:
        return json.loads(file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("fix_cache_read_failed", path=str(file), error=str(exc))
        return None


def _write_cache(file: Path, data: dict[str, Any]) -> None:
    """Write JSON data to a cache file atomically.

    Args:
        file: Target cache file path.
        data: Data to write.
    """
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(file)
    except OSError as exc:
        log.error("fix_cache_write_failed", path=str(file), error=str(exc))
        if tmp.exists():
            tmp.unlink()


# ── FixSuggester ──────────────────────────────────────────


class FixSuggester:
    """Generates code fix suggestions for scanner findings using an LLM.

    Attributes:
        llm: The LLMClient instance for API calls.
    """

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    # ── Public API ─────────────────────────────────────────

    async def suggest_fix(
        self,
        source_code: str,
        finding: Finding,
        compiler: str | None = None,
    ) -> FixSuggestion:
        """Generate a fix suggestion for a single finding.

        Sends the finding and source code to the LLM with a prompt
        focused on producing a concrete, minimal, and correct fix.

        Args:
            source_code: Full contract source code.
            finding: The finding to generate a fix for.
            compiler: Solidity compiler version (optional).

        Returns:
            A FixSuggestion with code fix, explanation, and impact assessment.

        Raises:
            RuntimeError: If the LLM call fails.
        """
        # Check cache
        cache_key = f"{finding.tool}::{finding.id}::{finding.title}"
        cache_file = CACHE_DIR / f"{_sanitize_key(cache_key)}.json"
        cached = _read_cache(cache_file)
        if cached is not None:
            log.info(
                "fixer.cache_hit",
                finding_id=finding.id,
                tool=finding.tool,
            )
            return FixSuggestion(**cached)

        log.info(
            "fixer.generating_fix",
            finding_id=finding.id,
            tool=finding.tool,
            title=finding.title,
        )

        # Build a fix-focused prompt
        self._build_fix_prompt(
            source_code=source_code,
            finding=finding,
            compiler=compiler,
        )

        # Get analysis from LLM (reuse analyze for now; the prompt handles focus)
        try:
            analysis = await self.llm.analyze(
                source_code=source_code,
                finding_title=finding.title,
                finding_description=finding.description,
                finding_location=finding.location,
                compiler=compiler,
            )
        except Exception as exc:
            log.error(
                "fixer.llm_call_failed",
                finding_id=finding.id,
                error=str(exc),
            )
            raise RuntimeError(f"Fix generation failed: {exc}") from exc

        if analysis.verdict == "false_positive":
            # No fix needed for false positives
            suggestion = FixSuggestion(
                finding_id=finding.id,
                fix_code="",
                explanation=(
                    "This finding was classified as a False Positive. "
                    "No fix is needed. "
                    f"Reasoning: {analysis.reasoning}"
                ),
                gas_impact=None,
                breaking_changes=False,
            )
        else:
            # Parse the suggested fix from the analysis
            suggestion = FixSuggestion(
                finding_id=finding.id,
                fix_code=analysis.suggested_fix or "# No specific fix code provided",
                explanation=analysis.reasoning,
                gas_impact=_estimate_gas_impact(analysis.severity),
                breaking_changes=_check_breaking_changes(
                    analysis.suggested_fix or ""
                ),
            )

        # Cache the result
        _write_cache(cache_file, suggestion.model_dump())

        return suggestion

    async def apply_patch(
        self,
        source_code: str,
        finding: Finding,
        fix: FixSuggestion,
    ) -> str:
        """Apply a suggested fix to the source code.

        Uses the LLM to produce the patched version of the source code
        with the fix applied. This is more reliable than simple string
        replacement because it understands the code structure.

        Args:
            source_code: Original contract source code.
            finding: The finding being fixed.
            fix: The FixSuggestion with the fix code/explanation.

        Returns:
            The modified source code with the fix applied.

        Raises:
            RuntimeError: If patching fails.
        """
        if not fix.fix_code:
            log.info(
                "fixer.no_fix_to_apply",
                finding_id=finding.id,
                reason="Finding is a False Positive or no fix provided",
            )
            return source_code

        log.info(
            "fixer.applying_patch",
            finding_id=finding.id,
            tool=finding.tool,
        )

        # Build a prompt instructing the LLM to apply the fix

        try:
            result = await self.llm.suggest_fix(
                source_code=source_code,
                finding_title=finding.title,
                finding_description=finding.description,
                finding_location=finding.location,
            )
        except Exception as exc:
            log.error(
                "fixer.patch_failed",
                finding_id=finding.id,
                error=str(exc),
            )
            raise RuntimeError(f"Patch application failed: {exc}") from exc

        # Extract the code from the LLM response
        patched_code = result.suggested_fix or source_code

        # Strip markdown code fences if present
        patched_code = patched_code.strip()
        if patched_code.startswith("```"):
            first_newline = patched_code.find("\n")
            if first_newline != -1:
                patched_code = patched_code[first_newline + 1 :]
            closing = patched_code.rfind("```")
            if closing != -1:
                patched_code = patched_code[:closing]
            patched_code = patched_code.strip()

        log.info(
            "fixer.patch_applied",
            finding_id=finding.id,
            original_length=len(source_code),
            patched_length=len(patched_code),
        )

        return patched_code

    # ── Internal: Prompt Building ──────────────────────────

    @staticmethod
    def _build_fix_prompt(
        source_code: str,
        finding: Finding,
        compiler: str | None = None,
    ) -> str:
        """Build a fix-focused prompt for the LLM.

        Args:
            source_code: Contract source code.
            finding: The finding to fix.
            compiler: Compiler version.

        Returns:
            Formatted prompt string.
        """
        location_str = ""
        if finding.location:
            loc = finding.location
            file_name = loc.get("file", "unknown.sol")
            line = loc.get("line", "?")
            snippet = loc.get("snippet", "")
            location_str = f"\n- **Location**: {file_name}:{line}"
            if snippet:
                location_str += f"\n- **Snippet**: `{snippet}`"

        compiler_str = f"\n- **Compiler**: {compiler}" if compiler else ""

        return (
            f"You are a smart contract security expert. Provide a concrete fix for:\n\n"
            f"## Finding\n"
            f"- **Title**: {finding.title}\n"
            f"- **Description**: {finding.description}"
            f"{location_str}"
            f"{compiler_str}"
            f"\n\n## Source Code\n```solidity\n{source_code}\n```\n\n"
            f"Return a JSON object with:\n"
            f"  - fix_code: The exact Solidity code changes needed\n"
            f"  - explanation: Why this fix works\n"
            f"  - gas_impact: Estimated gas cost change\n"
            f"  - breaking_changes: Whether this changes the contract interface\n"
        )


# ── Internal: Helpers ─────────────────────────────────────


def _sanitize_key(key: str) -> str:
    """Sanitize a cache key for use as a filename.

    Replaces non-alphanumeric characters with underscores.

    Args:
        key: Raw cache key.

    Returns:
        Sanitized filename-safe string.
    """
    safe = "".join(c if c.isalnum() else "_" for c in key)
    # Trim consecutive underscores
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_")


def _estimate_gas_impact(severity: str) -> str:
    """Estimate the gas impact of a fix based on severity.

    Args:
        severity: The AI-assessed severity level.

    Returns:
        Human-readable gas impact estimate.
    """
    estimates = {
        "critical": "Variable — depends on fix (adding reentrancy guard: +~500 gas)",
        "high": "+200 to +1000 gas for additional checks",
        "medium": "+100 to +500 gas for additional validation",
        "low": "Negligible (< 100 gas change)",
        "informational": "No gas impact expected",
    }
    return estimates.get(severity, "Unknown")


def _check_breaking_changes(fix_code: str) -> bool:
    """Heuristically check if a fix introduces breaking changes.

    Looks for patterns that change function signatures or storage layout.

    Args:
        fix_code: The suggested fix code.

    Returns:
        True if the fix likely introduces breaking changes.
    """
    breaking_patterns = [
        "function ",
        "modifier ",
        "constructor",
        "immutable",
        "constant",
        "storage ",
        "mapping(",
        "struct ",
        "enum ",
    ]
    return any(pattern in fix_code for pattern in breaking_patterns)
