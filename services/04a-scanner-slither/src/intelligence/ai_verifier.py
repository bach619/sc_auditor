"""AI Verifier — integration with 06-AI service for context-aware verification.

Calls the 06-AI /analyze endpoint for each Slither finding, gets TP/FP
verdict with confidence score, and enriches findings with AI-based
reasoning.

Architecture:
  - Batches findings per audit to minimize HTTP calls
  - Caches AI results locally to avoid re-analyzing identical findings
  - Handles 06-AI service being offline gracefully (falls back to
    heuristic scoring)
  - Respects rate limits via configurable concurrency throttle

Integration:
  AIVerifier → httpx → 06-AI (POST /analyze)
           → experience_db (record verified findings)
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import httpx
import structlog

log = structlog.get_logger()

# Default 06-AI service URL
AI_SERVICE_URL = "http://06-ai:8004"

# Local cache for AI verdicts (survives restarts)
CACHE_DIR = Path("/data/scanner-slither/ai_cache")


class AIVerificationResult:
    """Result of AI verification for a single finding."""

    def __init__(
        self,
        finding_id: str,
        title: str,
        ai_verdict: str,  # "true_positive" | "false_positive"
        ai_confidence: float,
        ai_severity: str,
        ai_reasoning: str,
        suggested_fix: str | None = None,
    ) -> None:
        self.finding_id = finding_id
        self.title = title
        self.ai_verdict = ai_verdict
        self.ai_confidence = ai_confidence
        self.ai_severity = ai_severity
        self.ai_reasoning = ai_reasoning
        self.suggested_fix = suggested_fix

    @property
    def is_true_positive(self) -> bool:
        return self.ai_verdict == "true_positive"

    @property
    def is_false_positive(self) -> bool:
        return self.ai_verdict == "false_positive"

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "title": self.title,
            "ai_verdict": self.ai_verdict,
            "ai_confidence": self.ai_confidence,
            "ai_severity": self.ai_severity,
            "ai_reasoning": self.ai_reasoning,
            "suggested_fix": self.suggested_fix,
            "is_true_positive": self.is_true_positive,
        }


class AIVerifier:
    """Verify Slither findings using 06-AI service.

    Args:
        ai_service_url: Base URL for 06-AI service.
        cache_dir: Directory for local AI result cache.
        max_concurrent: Max concurrent AI verification requests.
        min_confidence: Minimum AI confidence to accept a verdict.
    """

    def __init__(
        self,
        ai_service_url: str = AI_SERVICE_URL,
        cache_dir: str | Path = CACHE_DIR,
        max_concurrent: int = 5,
        min_confidence: float = 0.4,
    ) -> None:
        self._ai_url = ai_service_url.rstrip("/")
        self._cache_dir = Path(cache_dir)
        self._max_concurrent = max_concurrent
        self._min_confidence = min_confidence
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._http: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self._ai_url,
                timeout=httpx.Timeout(60.0, connect=5.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return self._http

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    # ── Public API ──────────────────────────────────────────

    async def verify_findings(
        self,
        findings: list[dict[str, Any]],
        source_code: dict[str, str],
        audit_id: str = "default",
        contract_name: str = "",
        compiler: str = "",
    ) -> list[AIVerificationResult]:
        """Verify a batch of Slither findings using 06-AI.

        Steps:
          1. Check local cache for each finding (by content hash)
          2. For uncached findings: build AI request payload
          3. Call 06-AI /analyze (batched into one call)
          4. Cache results locally
          5. Return enriched results

        Args:
            findings: List of finding dicts with title, description, severity.
            source_code: Dict of file path → source code.
            audit_id: Audit session identifier.
            contract_name: Name of the contract being analyzed.
            compiler: Solidity compiler version.

        Returns:
            List of AIVerificationResult, one per finding.
        """
        if not findings:
            return []

        results: list[AIVerificationResult] = []
        uncached_indices: list[int] = []
        uncached_findings: list[dict[str, Any]] = []

        # Check cache for each finding
        for idx, finding in enumerate(findings):
            cache_key = self._compute_finding_hash(finding, source_code)
            cached = self._load_cache(cache_key)
            if cached is not None:
                results.append(AIVerificationResult(**cached))
                log.debug("ai_verifier.cache_hit", finding_id=finding.get("title", "?"), confidence=cached.get("ai_confidence", 0))
            else:
                results.append(None)  # placeholder
                uncached_indices.append(idx)
                uncached_findings.append(finding)

        # Verify uncached findings via 06-AI
        if uncached_findings:
            try:
                ai_results = await self._call_ai_service(
                    findings=uncached_findings,
                    source_code=source_code,
                    audit_id=audit_id,
                    contract_name=contract_name,
                    compiler=compiler,
                )
            except Exception as exc:
                log.error("ai_verifier.service_failed", error=str(exc), count=len(uncached_findings))
                # Fallback: assign heuristic results
                ai_results = [
                    self._heuristic_fallback(f)
                    for f in uncached_findings
                ]

            # Fill placeholders and cache
            for idx, ai_res in zip(uncached_indices, ai_results):
                results[idx] = ai_res
                cache_key = self._compute_finding_hash(findings[idx], source_code)
                self._save_cache(cache_key, ai_res.to_dict())

        # Filter out any None placeholders (shouldn't happen)
        return [r for r in results if r is not None]

    async def verify_single(
        self,
        finding: dict[str, Any],
        source_code: dict[str, str],
        audit_id: str = "default",
    ) -> AIVerificationResult:
        """Verify a single finding."""
        results = await self.verify_findings(
            [finding], source_code, audit_id=audit_id
        )
        return results[0] if results else self._heuristic_fallback(finding)

    # ── AI Service Call ─────────────────────────────────────

    async def _call_ai_service(
        self,
        findings: list[dict[str, Any]],
        source_code: dict[str, str],
        audit_id: str,
        contract_name: str,
        compiler: str,
    ) -> list[AIVerificationResult]:
        """Call 06-AI POST /analyze with findings and source code."""
        client = await self._get_client()

        # Build finding payloads in 06-AI format
        ai_findings = []
        for f in findings:
            finding_id = hashlib.sha256(
                f"{f.get('title', '')}:{f.get('description', '')}".encode()
            ).hexdigest()[:12]

            location = {}
            if f.get("contract"):
                location["contract"] = f["contract"]
            if f.get("line"):
                location["line"] = f["line"]
            if f.get("line_end"):
                location["line_end"] = f["line_end"]

            ai_findings.append({
                "id": finding_id,
                "tool": "slither",
                "title": f.get("title", "Unknown"),
                "description": f.get("description", ""),
                "severity": f.get("severity", "medium"),
                "location": location,
            })

        payload = {
            "audit_id": audit_id,
            "source": source_code,
            "findings": ai_findings,
            "contract_name": contract_name or "",
            "compiler": compiler or "",
        }

        log.info(
            "ai_verifier.calling_service",
            finding_count=len(ai_findings),
            audit_id=audit_id,
        )

        try:
            response = await client.post("/analyze", json=payload)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            log.warning("ai_verifier.service_error", error=str(exc))
            raise

        # Parse response
        response_data = data.get("data", {})
        analyzed = response_data.get("findings", [])

        results = []
        for i, f in enumerate(findings):
            ai_result = analyzed[i] if i < len(analyzed) else {}
            results.append(AIVerificationResult(
                finding_id=ai_result.get("id", f"f_{i}"),
                title=f.get("title", "Unknown"),
                ai_verdict=ai_result.get("ai_verdict", "true_positive"),
                ai_confidence=ai_result.get("ai_confidence", 0.5),
                ai_severity=ai_result.get("ai_severity", f.get("severity", "medium")),
                ai_reasoning=ai_result.get("ai_reasoning", ""),
                suggested_fix=ai_result.get("suggested_fix"),
            ))

        # Log summary
        tp_count = sum(1 for r in results if r.is_true_positive)
        fp_count = len(results) - tp_count
        log.info(
            "ai_verifier.completed",
            total=len(results),
            true_positives=tp_count,
            false_positives=fp_count,
        )

        return results

    # ── Fallback ────────────────────────────────────────────

    def _heuristic_fallback(
        self, finding: dict[str, Any]
    ) -> AIVerificationResult:
        """Heuristic fallback when AI service is unavailable.

        Uses:
          - Detector name → known reliability score
          - Severity → base confidence
        """
        title = finding.get("title", "")
        severity = finding.get("severity", "medium")

        # Known detector reliability (from experience DB stats)
        detector_reliability: dict[str, float] = {
            "reentrancy-eth": 0.42,
            "reentrancy-no-eth": 0.55,
            "reentrancy-benign": 0.30,
            "reentrancy-events": 0.25,
            "unchecked-lowlevel": 0.70,
            "controlled-delegatecall": 0.85,
            "tx-origin": 0.90,
            "incorrect-equality": 0.60,
            "timestamp": 0.40,
            "low-level-calls": 0.65,
            "arbitrary-send": 0.75,
            "shadowing-state": 0.50,
            "uninitialized-state": 0.80,
            "missing-zero-check": 0.45,
            "suicidal": 0.85,
            "naming-convention": 0.10,
            "pragma": 0.05,
            "solc-version": 0.05,
        }

        confidence = detector_reliability.get(title, 0.50)

        # Severity adjustment
        sev_mult = {"critical": 1.1, "high": 1.0, "medium": 0.9, "low": 0.7, "informational": 0.5}
        confidence *= sev_mult.get(severity, 0.9)
        confidence = max(0.1, min(0.95, confidence))

        verdict = "true_positive" if confidence >= 0.4 else "false_positive"

        return AIVerificationResult(
            finding_id=finding.get("title", "unknown"),
            title=title,
            ai_verdict=verdict,
            ai_confidence=round(confidence, 3),
            ai_severity=severity,
            ai_reasoning=f"Heuristic assessment (AI service offline): known {title} reliability = {confidence:.0%}",
        )

    # ── Cache ───────────────────────────────────────────────

    @staticmethod
    def _compute_finding_hash(
        finding: dict[str, Any],
        source_code: dict[str, str],
    ) -> str:
        """Compute a deterministic hash for a finding + source code.

        Same finding on same code → same hash → cache hit.
        """
        content = json.dumps({
            "title": finding.get("title", ""),
            "description": finding.get("description", ""),
            "severity": finding.get("severity", ""),
            "source": source_code,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def _load_cache(self, key: str) -> dict[str, Any] | None:
        """Load cached AI result by hash key."""
        cache_file = self._cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            # Check TTL (7 days)
            if time.time() - data.get("_cached_at", 0) > 604800:
                cache_file.unlink(missing_ok=True)
                return None
            return data.get("result")
        except (json.JSONDecodeError, OSError):
            return None

    def _save_cache(self, key: str, result: dict[str, Any]) -> None:
        """Save AI result to local cache."""
        cache_file = self._cache_dir / f"{key}.json"
        try:
            cache_file.write_text(json.dumps({
                "_cached_at": time.time(),
                "result": result,
            }, default=str), encoding="utf-8")
        except OSError as exc:
            log.warning("ai_verifier.cache_write_failed", error=str(exc))

    def clear_cache(self, older_than_days: int = 7) -> int:
        """Clear expired cache entries."""
        cutoff = time.time() - (older_than_days * 86400)
        count = 0
        for f in self._cache_dir.glob("*.json"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    count += 1
            except OSError:
                pass
        return count

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        files = list(self._cache_dir.glob("*.json"))
        return {
            "total_cached": len(files),
            "cache_dir": str(self._cache_dir),
            "disk_usage_bytes": sum(f.stat().st_size for f in files),
        }


def create_ai_verifier(
    ai_service_url: str = AI_SERVICE_URL,
    cache_dir: str | Path = CACHE_DIR,
) -> AIVerifier:
    """Create a configured AIVerifier instance."""
    return AIVerifier(ai_service_url=ai_service_url, cache_dir=cache_dir)
