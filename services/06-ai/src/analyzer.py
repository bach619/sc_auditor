"""Analyzer — Orchestrates LLM-based vulnerability analysis for scanner findings.

Responsible for:
  - Sending findings to LLMClient for TP/FP classification
  - Batching multiple findings into single LLM prompts for efficiency
  - Enriching raw findings with AI analysis results
  - Caching analysis results to avoid reprocessing
  - Rate limiting LLM API calls
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import structlog

from src.llm import LLMClient, CircuitBreakerOpenError
from src.models import AnalyzedFinding, Finding, LlmAnalysis, Verdict

log = structlog.get_logger()

# ── Constants ──────────────────────────────────────────────

CACHE_DIR = Path("/data/ai/cache")
CACHE_LOCK: asyncio.Lock = asyncio.Lock()
DEFAULT_MAX_CONCURRENT = 3  # Max concurrent LLM calls


# ── Helpers ────────────────────────────────────────────────


def _compute_finding_hash(
    tool: str,
    source_code: str,
    finding_title: str,
    finding_description: str,
) -> str:
    """Compute a deterministic hash for a finding + source combination.

    Uses SHA-256 over the concatenation of tool, source code,
    finding title, and description. The result is a hex string
    suitable for use as a cache key.

    Args:
        tool: The scanner tool name (e.g. "slither").
        source_code: The contract source code.
        finding_title: The finding title.
        finding_description: The finding description.

    Returns:
        A 64-character hex string (SHA-256 hash).
    """
    raw = f"{tool}||{source_code}||{finding_title}||{finding_description}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_cache(finding_hash: str) -> LlmAnalysis | None:
    """Load a cached analysis result from disk.

    Args:
        finding_hash: The cache key (SHA-256 hex string).

    Returns:
        Cached LlmAnalysis if found and valid, None otherwise.
    """
    cache_file = CACHE_DIR / f"{finding_hash}.json"
    if not cache_file.exists():
        return None

    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        return LlmAnalysis(**data)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        log.warning("cache_read_failed", hash=finding_hash[:16], error=str(exc))
        return None


def _save_cache(finding_hash: str, analysis: LlmAnalysis) -> None:
    """Save an analysis result to disk cache atomically.

    Writes to a temporary file first, then atomically renames
    to the final path to prevent partial writes.

    Args:
        finding_hash: The cache key (SHA-256 hex string).
        analysis: The analysis result to cache.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{finding_hash}.json"
    tmp_file = cache_file.with_suffix(".tmp")

    try:
        data = analysis.model_dump()
        tmp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp_file.replace(cache_file)
    except OSError as exc:
        log.error("cache_write_failed", hash=finding_hash[:16], error=str(exc))
        if tmp_file.exists():
            tmp_file.unlink()


def _clear_cache(finding_hash: str) -> bool:
    """Remove a cached analysis result.

    Args:
        finding_hash: The cache key to remove.

    Returns:
        True if the cache entry existed and was removed, False otherwise.
    """
    cache_file = CACHE_DIR / f"{finding_hash}.json"
    if not cache_file.exists():
        return False
    cache_file.unlink()
    return True


def count_cache_entries() -> int:
    """Count the number of cached analysis results.

    Returns:
        Number of .json files in the cache directory.
    """
    if not CACHE_DIR.exists():
        return 0
    return len(list(CACHE_DIR.glob("*.json")))


# ── Error Types ────────────────────────────────────────────


class AnalyzerError(Exception):
    """Base exception for analyzer errors."""


class AnalysisFailedError(AnalyzerError):
    """Raised when LLM analysis fails for a finding."""


class RateLimitError(AnalyzerError):
    """Raised when API rate limits are exceeded."""


# ── Analyzer ───────────────────────────────────────────────


class Analyzer:
    """Orchestrates LLM analysis for scanner findings.

    Manages batching, caching, rate limiting, and enrichment
    of scanner findings with AI analysis results.

    Attributes:
        llm: The LLMClient instance for API calls.
        max_concurrent: Maximum number of concurrent LLM API calls.
        semaphore: Asyncio semaphore for rate limiting.
    """

    def __init__(
        self,
        llm: LLMClient,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    ) -> None:
        self.llm = llm
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    # ── Public API ─────────────────────────────────────────

    async def analyze_all(
        self,
        source: dict[str, str],
        findings: list[Finding],
        compiler: str | None = None,
        contract_name: str | None = None,
    ) -> list[AnalyzedFinding]:
        """Analyze a batch of findings against source code.

        Each finding is analyzed independently (concurrently within
        the rate limit). Results are cached on disk.

        Args:
            source: Dictionary mapping file names to source code.
            findings: List of scanner findings to analyze.
            compiler: Solidity compiler version (optional).
            contract_name: Contract name (optional, used for logging).

        Returns:
            List of AnalyzedFinding objects, one per input finding,
            in the same order as the input.

        Raises:
            AnalyzerError: If analysis fails for a significant number
                           of findings.
        """
        if not findings:
            return []

        # Combine all source files into one string for context
        full_source = self._combine_source(source)
        contract_label = contract_name or "unknown"

        log.info(
            "analyzer.starting",
            contract=contract_label,
            finding_count=len(findings),
            compiler=compiler,
        )

        # ── Early exit: no LLM keys configured ──────────────
        # If no API keys are set, skip LLM calls entirely and
        # return scanner findings as trusted true_positives.
        if not self.llm.has_keys:
            log.info(
                "analyzer.no_llm_keys",
                count=len(findings),
                message="No LLM API keys configured. Trusting scanner findings.",
            )
            trusted: list[AnalyzedFinding] = []
            for f in findings:
                scanner_sev: str = f.severity or "informational"
                trusted.append(AnalyzedFinding(
                    id=f.id,
                    tool=f.tool,
                    title=f.title,
                    description=f.description,
                    ai_verdict="true_positive",
                    ai_confidence=0.5,
                    ai_severity=scanner_sev,  # type: ignore[arg-type]
                    ai_reasoning="LLM analysis unavailable (no API keys). Finding trusted based on scanner assessment.",
                    suggested_fix=None,
                    scanner_severity=scanner_sev,
                    location=f.location,
                ))
            return trusted

        # Create tasks for each finding, with concurrent limit
        sem = self._semaphore

        async def _analyze_one(finding: Finding) -> AnalyzedFinding:
            async with sem:
                return await self._analyze_single(
                    source_code=full_source,
                    finding=finding,
                    compiler=compiler,
                )

        tasks = [_analyze_one(f) for f in findings]
        results: list[AnalyzedFinding | None] = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        # Process results, handling exceptions
        enriched: list[AnalyzedFinding] = []
        errors = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors += 1
                log.error(
                    "analyzer.finding_failed",
                    finding_id=findings[i].id,
                    error=str(result),
                )
                # Return a degraded result instead of failing the whole batch
                enriched.append(
                    self._degraded_result(findings[i], error=str(result))
                )
            else:
                enriched.append(result)

        if errors:
            log.warning(
                "analyzer.completed_with_errors",
                total=len(findings),
                errors=errors,
            )
        else:
            log.info("analyzer.completed", total=len(findings))

        return enriched

    async def analyze_single(
        self,
        source: dict[str, str],
        finding: Finding,
        compiler: str | None = None,
    ) -> AnalyzedFinding:
        """Analyze a single finding (cached or fresh).

        Checks the on-disk cache first. If a cached result exists,
        returns it directly. Otherwise, calls the LLM.

        Args:
            source: Dictionary mapping file names to source code.
            finding: The finding to analyze.
            compiler: Solidity compiler version (optional).

        Returns:
            Enriched AnalyzedFinding with AI verdict.
        """
        full_source = self._combine_source(source)
        return await self._analyze_single(
            source_code=full_source,
            finding=finding,
            compiler=compiler,
        )

    async def clear_cache(self, finding_hash: str) -> bool:
        """Clear a single cached analysis result.

        Args:
            finding_hash: The cache key to clear.

        Returns:
            True if the cache entry was removed, False if not found.
        """
        return _clear_cache(finding_hash)

    def get_cached(self, finding_hash: str) -> LlmAnalysis | None:
        """Retrieve a cached analysis result without calling the LLM.

        Args:
            finding_hash: The cache key to look up.

        Returns:
            Cached LlmAnalysis if found, None otherwise.
        """
        return _load_cache(finding_hash)

    # ── Internal: Single Finding Analysis ──────────────────

    async def _analyze_single(
        self,
        source_code: str,
        finding: Finding,
        compiler: str | None = None,
    ) -> AnalyzedFinding:
        """Analyze a single finding with caching.

        Checks the on-disk cache first. If cached, returns immediately.
        Otherwise, calls the LLM and caches the result.

        Args:
            source_code: Full contract source code.
            finding: The finding to analyze.
            compiler: Compiler version.

        Returns:
            AnalyzedFinding with AI analysis.
        """
        finding_hash = _compute_finding_hash(
            tool=finding.tool,
            source_code=source_code,
            finding_title=finding.title,
            finding_description=finding.description,
        )

        # Check cache
        cached = _load_cache(finding_hash)
        if cached is not None:
            log.info(
                "analyzer.cache_hit",
                finding_id=finding.id,
                tool=finding.tool,
                hash_prefix=finding_hash[:16],
                verdict=cached.verdict,
            )
            return self._enrich_finding(finding, cached)

        log.info(
            "analyzer.cache_miss",
            finding_id=finding.id,
            tool=finding.tool,
            hash_prefix=finding_hash[:16],
        )

        # Call LLM
        try:
            analysis = await self.llm.analyze(
                source_code=source_code,
                finding_title=finding.title,
                finding_description=finding.description,
                finding_location=finding.location,
                compiler=compiler,
            )
        except CircuitBreakerOpenError:
            log.error(
                "analyzer.circuit_breaker_open",
                finding_id=finding.id,
            )
            raise AnalysisFailedError(
                "LLM circuit breaker is open. API calls temporarily blocked."
            )
        except Exception as exc:
            log.error(
                "analyzer.llm_call_failed",
                finding_id=finding.id,
                error=str(exc),
            )
            raise AnalysisFailedError(f"LLM analysis failed: {exc}") from exc

        # Cache the result
        _save_cache(finding_hash, analysis)

        return self._enrich_finding(finding, analysis)

    # ── Internal: Enrichment ───────────────────────────────

    def _enrich_finding(
        self,
        finding: Finding,
        analysis: LlmAnalysis,
    ) -> AnalyzedFinding:
        """Merge LLM analysis into a finding to produce an AnalyzedFinding.

        Args:
            finding: The original scanner finding.
            analysis: The LLM analysis result.

        Returns:
            Enriched finding with AI verdict and metadata.
        """
        return AnalyzedFinding(
            id=finding.id,
            tool=finding.tool,
            title=finding.title,
            description=finding.description,
            ai_verdict=analysis.verdict,
            ai_confidence=analysis.confidence,
            ai_severity=analysis.severity,
            ai_reasoning=analysis.reasoning,
            suggested_fix=analysis.suggested_fix,
            scanner_severity=finding.severity,
            location=finding.location,
        )

    def _degraded_result(
        self,
        finding: Finding,
        error: str,
    ) -> AnalyzedFinding:
        """Produce a fallback result when LLM analysis fails.

        Returns a True Positive verdict with low confidence and
        the error message as reasoning. Scanner findings from
        tools like Slither have high baseline accuracy, so we
        trust the scanner result when LLM is unavailable rather
        than silently discarding potential vulnerabilities.

        Args:
            finding: The original finding.
            error: The error message from the failure.

        Returns:
            A degraded AnalyzedFinding that trusts the scanner verdict.
        """
        return AnalyzedFinding(
            id=finding.id,
            tool=finding.tool,
            title=finding.title,
            description=finding.description,
            ai_verdict="true_positive",  # Trust scanner when LLM unavailable
            ai_confidence=0.3,
            ai_severity=finding.severity,
            ai_reasoning=f"AI analysis unavailable: {error}. Finding retained based on scanner ({finding.tool}) assessment.",
            suggested_fix=None,
            scanner_severity=finding.severity,
            location=finding.location,
        )

    # ── Internal: Helpers ──────────────────────────────────

    @staticmethod
    def _combine_source(source: dict[str, str]) -> str:
        """Combine multiple source files into a single string.

        Each file is prefixed with a comment indicating its path.

        Args:
            source: Dictionary of file_name → source_code.

        Returns:
            Combined source string with file markers.
        """
        if len(source) == 1:
            return next(iter(source.values()))

        parts: list[str] = []
        for file_name, content in source.items():
            parts.append(f"// File: {file_name}")
            parts.append(content)
            parts.append("")  # blank line separator
        return "\n".join(parts)
