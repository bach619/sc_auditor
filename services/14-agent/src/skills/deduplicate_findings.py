"""DeduplicateFindingsSkill — Merges duplicate findings from multiple scanner tools.

Scanner tools (Slither, Mythril, Echidna) often report the same vulnerability
with different wording. This skill deduplicates by:
1. Grouping by (contract, function, vulnerability_type)
2. Keeping the highest severity
3. Merging descriptions from all tools
4. Removing tool-specific noise

Usage (called by agent):
    {
        "findings": [...],
        "strategy": "conservative" | "aggressive" (default: conservative)
    }
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

import structlog

from src.skills.base import BaseSkill

log = structlog.get_logger()

# ── Vulnerability type normalization ───────────────────────

VULN_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"re-entrancy|reentrancy", re.I), "reentrancy"),
    (re.compile(r"access.control|unprotected|onlyowner|owner.?check", re.I), "access_control"),
    (re.compile(r"flash.?loan", re.I), "flash_loan"),
    (re.compile(r"oracle", re.I), "oracle_manipulation"),
    (re.compile(r"overflow|underflow|arithmetic", re.I), "arithmetic"),
    (re.compile(r"bad.?cast|type.?confus", re.I), "type_confusion"),
    (re.compile(r"delegate.?call|delegatecall", re.I), "delegate_call"),
    (re.compile(r"front.?run|frontrunning", re.I), "frontrunning"),
    (re.compile(r"tx.?origin", re.I), "tx_origin"),
    (re.compile(r"timestamp|block.timestamp", re.I), "timestamp_dependency"),
    (re.compile(r"denial.?of.?service|dos|grief", re.I), "dos"),
    (re.compile(r"logic.?error|business.?logic", re.I), "business_logic"),
    (re.compile(r"centrali?z[ea]tion|single.?point", re.I), "centralization_risk"),
    (re.compile(r"uninitialized|uninit", re.I), "uninitialized"),
    (re.compile(r"lock|locking|lock.contrac", re.I), "locking"),
    (re.compile(r"race.?condition", re.I), "race_condition"),
    (re.compile(r"gas|inefficient", re.I), "gas_optimization"),
    (re.compile(r"compliance|kyc|aml", re.I), "compliance"),
    (re.compile(r"pricing|price.?manipul", re.I), "pricing"),
    (re.compile(r".*", re.I), "other"),  # catch-all
]


def _normalize_vuln_type(title: str, description: str, finding_type: str = "") -> str:
    """Normalize a vulnerability description to a canonical type."""
    text = f"{title} {description} {finding_type}"
    for pattern, vuln_type in VULN_PATTERNS:
        if pattern.search(text):
            return vuln_type
    return "other"


SEVERITY_RANK = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "informational": 1,
    "unknown": 0,
}


def _normalize_severity(sev: str | None) -> str:
    """Normalize severity string."""
    if not sev:
        return "unknown"
    sev = sev.lower().strip()
    for key in SEVERITY_RANK:
        if key in sev:
            return key
    return "unknown"


def _best_severity(sev_a: str, sev_b: str) -> str:
    """Choose the higher severity."""
    return sev_a if SEVERITY_RANK.get(sev_a, 0) >= SEVERITY_RANK.get(sev_b, 0) else sev_b


# ── Skill Implementation ───────────────────────────────────


class DeduplicateFindingsSkill(BaseSkill):
    """Deduplicates scanner findings — merges duplicates, keeps highest severity."""

    cache_ttl: int = 3600  # 1 hour — dedup patterns don't change often

    @property
    def name(self) -> str:
        return "deduplicate_findings"

    @property
    def description(self) -> str:
        return (
            "Deduplicates findings from multiple scanner tools "
            "(Slither, Mythril, Echidna). Groups duplicates by vulnerability type, "
            "keeps highest severity, and merges descriptions from all tools. "
            "Use this BEFORE classify_finding to reduce AI analysis cost."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "findings": {
                "type": "array",
                "description": "List of finding objects from scanner tools",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "severity": {"type": "string"},
                        "tool": {"type": "string"},
                        "contract": {"type": "string"},
                        "function": {"type": "string"},
                        "file": {"type": "string"},
                        "line": {"type": "integer"},
                    },
                },
            },
            "strategy": {
                "type": "string",
                "description": "Deduplication strategy",
                "enum": ["conservative", "aggressive"],
                "default": "conservative",
            },
        }

    async def run(self, findings: list[dict], strategy: str = "conservative", **kwargs: Any) -> dict:
        """Deduplicate findings.

        Args:
            findings: List of finding dicts from scanner
            strategy: 'conservative' (merge only exact matches) or
                     'aggressive' (merge by vulnerability class)

        Returns:
            dict with:
            - unique_findings: deduplicated list
            - removed_count: how many were merged
            - groups: how many unique groups formed
            - stats: per-tool contribution
        """
        if not findings:
            return {
                "unique_findings": [],
                "removed_count": 0,
                "groups": 0,
                "stats": {},
            }

        # Group findings by key
        groups: dict[str, list[dict]] = defaultdict(list)
        tool_counts: dict[str, int] = defaultdict(int)

        for finding in findings:
            title = finding.get("title", "")
            desc = finding.get("description", "")
            ftype = finding.get("type", "")
            contract = finding.get("contract", finding.get("file", ""))
            func = finding.get("function", "")
            tool = finding.get("tool", "unknown")

            tool_counts[tool] += 1

            if strategy == "aggressive":
                vuln_type = _normalize_vuln_type(title, desc, ftype)
                key = f"{contract}:{func}:{vuln_type}"
            else:
                # Conservative: group by normalized title + location
                norm_title = re.sub(r"\s+", " ", title.lower().strip())[:80]
                key = f"{contract}:{func}:{norm_title}"

            groups[key].append(finding)

        # Merge each group
        unique_findings: list[dict] = []
        for key, group in groups.items():
            if len(group) == 1:
                unique_findings.append(group[0])
                continue

            merged = self._merge_group(group)
            unique_findings.append(merged)

        removed = len(findings) - len(unique_findings)

        log.info(
            "deduplication_complete",
            input_count=len(findings),
            unique_count=len(unique_findings),
            removed=removed,
            groups=len(groups),
            strategy=strategy,
        )

        return {
            "unique_findings": unique_findings,
            "removed_count": removed,
            "groups": len(groups),
            "stats": dict(tool_counts),
        }

    def _merge_group(self, group: list[dict]) -> dict:
        """Merge a group of duplicate findings into one."""
        best = group[0].copy()

        # Collect unique tools
        tools_seen: set[str] = set()
        all_descriptions: list[str] = []
        all_lines: list[int] = []

        for f in group:
            tool = f.get("tool", "unknown")
            tools_seen.add(tool)

            desc = f.get("description", "").strip()
            if desc and desc not in all_descriptions:
                all_descriptions.append(desc)

            line = f.get("line")
            if line is not None:
                all_lines.append(line)

            # Pick highest severity
            best["severity"] = _best_severity(
                best.get("severity", "unknown"),
                f.get("severity", "unknown"),
            )

        best["tool"] = sorted(tools_seen)
        best["tools_count"] = len(tools_seen)
        best["merged_from"] = len(group)

        if all_descriptions:
            # Keep the longest/most detailed description
            best["description"] = max(all_descriptions, key=len)
            best["_all_descriptions"] = all_descriptions

        if all_lines:
            best["line"] = min(all_lines)
            best["lines"] = sorted(set(all_lines))

        return best
