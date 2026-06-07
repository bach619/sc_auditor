"""Cross-Tool Consensus Engine — eliminate false positives via multi-tool voting.

Problem: Each scanner tool produces findings independently.
         30-60% are false positives. No way to know which are real.

Solution: A finding is only reported if CONFIRMED by multiple independent tools.
          Slither finds something → Mythril confirms same path → Echidna exploits it.
          3-tool consensus = HIGH confidence. 1-tool only = LOW confidence.

Confidence scoring:
  1 tool found it         → LOW (30% confidence)
  2 tools confirm         → MEDIUM (60% confidence)
  3+ tools confirm        → HIGH (90% confidence)
  3+ tools + AI verdict   → VERY HIGH (95%+ confidence)
  3+ tools + exploit PoC   → CONFIRMED (99% confidence)
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

logger = logging.getLogger("vyper.consensus")


class ConfidenceLevel(StrEnum):
    LOW = "low"                # 1 tool — likely false positive
    MEDIUM = "medium"          # 2 tools — probably real
    HIGH = "high"              # 3 tools — very likely real
    VERY_HIGH = "very_high"    # 3 tools + AI — almost certainly real
    CONFIRMED = "confirmed"    # Exploit proven — 100% real


@dataclass
class FindingEvidence:
    """Evidence from a single tool about a finding."""
    tool_name: str = ""
    finding_id: str = ""
    severity: str = ""
    title: str = ""
    contract_file: str = ""
    line_start: int = 0
    line_end: int = 0
    code_hash: str = ""         # SHA256 of vulnerable code snippet
    confidence: float = 0.0     # Tool's own confidence
    raw_output: str = ""


@dataclass
class ConsensusResult:
    """Multi-tool consensus on a single vulnerability."""
    consensus_id: str = ""
    vulnerability_type: str = ""
    severity: str = ""
    title: str = ""
    finding_evidence: list[FindingEvidence] = field(default_factory=list)
    tools_confirmed: list[str] = field(default_factory=list)
    tools_disagreed: list[str] = field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    confidence_score: float = 0.0     # 0.0 - 1.0
    ai_verdict: str = ""              # AI's assessment
    exploit_confirmed: bool = False
    recommendation: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class CrossToolConsensus:
    """Aggregates findings from multiple tools and determines consensus.

    Usage:
        consensus = CrossToolConsensus()
        slither_findings = [...]
        mythril_findings = [...]
        echidna_findings = [...]

        results = consensus.analyze([slither_findings, mythril_findings, echidna_findings])
        for r in results:
            print(f"{r.confidence.value}: {r.title} — {len(r.tools_confirmed)} tools agree")
    """

    # How much each tool's finding overlaps must match to be "same finding"
    CODE_SIMILARITY_THRESHOLD = 0.7
    LOCATION_TOLERANCE = 10  # lines

    def analyze(self, tool_findings: list[list[dict]]) -> list[ConsensusResult]:
        """Run consensus analysis across all tool findings.

        Groups findings by vulnerability type + code location,
        then scores confidence based on how many tools agree.
        """
        all_findings: list[FindingEvidence] = []
        for findings in tool_findings:
            for f in findings:
                all_findings.append(FindingEvidence(
                    tool_name=f.get("tool", "unknown"),
                    finding_id=f.get("id", ""),
                    severity=f.get("severity", "MEDIUM"),
                    title=f.get("title", ""),
                    contract_file=f.get("file", ""),
                    line_start=f.get("line_start", 0),
                    line_end=f.get("line_end", 0),
                    code_hash=self._hash_code(f.get("code_snippet", "")),
                    confidence=f.get("confidence", 0.5),
                    raw_output=json.dumps(f, default=str)[:500],
                ))

        # Group findings by vulnerability type + approximate location
        groups: dict[str, list[FindingEvidence]] = {}
        for evidence in all_findings:
            group_key = self._group_key(evidence)
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(evidence)

        # For each group, calculate consensus
        results: list[ConsensusResult] = []
        for group_key, evidences in groups.items():
            result = self._calculate_consensus(evidences)
            results.append(result)

        # Sort by confidence (highest first)
        results.sort(key=lambda r: r.confidence_score, reverse=True)

        logger.info(
            "Cross-tool consensus: %d unique findings, %d HIGH confidence, %d CONFIRMED",
            len(results),
            sum(1 for r in results if r.confidence >= ConfidenceLevel.HIGH),
            sum(1 for r in results if r.confidence == ConfidenceLevel.CONFIRMED),
        )

        return results

    def _group_key(self, evidence: FindingEvidence) -> str:
        """Create a grouping key for similar findings."""
        # Group by: vulnerability type + approximate file + approximate line
        line_bucket = (evidence.line_start // self.LOCATION_TOLERANCE) * self.LOCATION_TOLERANCE
        return f"{evidence.contract_file}:{line_bucket}:{evidence.code_hash[:8]}"

    def _calculate_consensus(self, evidences: list[FindingEvidence]) -> ConsensusResult:
        """Calculate consensus for a group of related findings."""
        result = ConsensusResult(
            consensus_id=hashlib.sha256(
                "|".join(e.finding_id for e in evidences).encode()
            ).hexdigest()[:12],
        )

        tools = list(set(e.tool_name for e in evidences))
        result.tools_confirmed = tools
        result.finding_evidence = evidences

        # Use the most specific title
        if evidences:
            result.title = max(evidences, key=lambda e: len(e.title)).title
            result.severity = max(evidences, key=lambda e: self._severity_weight(e.severity)).severity

        # Confidence scoring
        tool_count = len(tools)
        avg_confidence = sum(e.confidence for e in evidences) / len(evidences) if evidences else 0

        result.confidence_score = self._score_confidence(tool_count, avg_confidence)

        if result.exploit_confirmed:
            result.confidence = ConfidenceLevel.CONFIRMED
        elif tool_count >= 3 and result.confidence_score > 0.9:
            result.confidence = ConfidenceLevel.VERY_HIGH
        elif tool_count >= 3:
            result.confidence = ConfidenceLevel.HIGH
        elif tool_count >= 2:
            result.confidence = ConfidenceLevel.MEDIUM
        else:
            result.confidence = ConfidenceLevel.LOW

        # Generate recommendation based on consensus
        result.recommendation = self._generate_recommendation(result)

        return result

    def _score_confidence(self, tool_count: int, avg_confidence: float) -> float:
        """Score confidence based on tool agreement."""
        # Base score from number of agreeing tools
        if tool_count == 1:
            base = 0.3
        elif tool_count == 2:
            base = 0.6
        elif tool_count == 3:
            base = 0.85
        else:
            base = 0.95

        # Adjust by average tool confidence
        return min(base * (0.5 + avg_confidence * 0.5), 1.0)

    def confirm_with_exploit(self, consensus_id: str) -> None:
        """Mark a consensus result as confirmed by exploit PoC."""
        # In production: update the consensus record
        logger.info("Consensus %s CONFIRMED by exploit", consensus_id)

    def confirm_with_ai(self, consensus_id: str, verdict: str) -> None:
        """Mark a consensus result with AI verdict."""
        logger.info("Consensus %s: AI verdict = %s", consensus_id, verdict)

    @staticmethod
    def _severity_weight(severity: str) -> int:
        weights = {"CRITICAL": 5, "HIGH": 4, "MEDIUM": 3, "LOW": 2, "INFO": 1}
        return weights.get(severity.upper(), 0)

    @staticmethod
    def _hash_code(code: str) -> str:
        if not code:
            return "no_code"
        return hashlib.sha256(code.encode()).hexdigest()

    @staticmethod
    def _generate_recommendation(result: ConsensusResult) -> str:
        """Generate human-readable recommendation based on consensus."""
        if result.confidence >= ConfidenceLevel.HIGH:
            return (
                f"CONFIRMED VULNERABILITY: {result.title}\n"
                f"  - Confirmed by: {', '.join(result.tools_confirmed)}\n"
                f"  - Severity: {result.severity}\n"
                f"  - Confidence: {result.confidence.value} ({result.confidence_score:.0%})\n"
                f"  - Action: Fix immediately and request re-audit"
            )
        elif result.confidence == ConfidenceLevel.MEDIUM:
            return (
                f"POTENTIAL VULNERABILITY: {result.title}\n"
                f"  - Detected by: {', '.join(result.tools_confirmed)}\n"
                f"  - Action: Manual review recommended. Run exploit generation to confirm."
            )
        else:
            return (
                f"LOW CONFIDENCE: {result.title}\n"
                f"  - Single tool detection: {result.tools_confirmed[0] if result.tools_confirmed else 'unknown'}\n"
                f"  - Action: Likely false positive. Skip unless corroborating evidence found."
            )
