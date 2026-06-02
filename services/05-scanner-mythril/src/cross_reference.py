"""Cross-Reference Engine — membandingkan temuan antar scanner tools.

Membantu menentukan:
  - Apakah temuan Mythril juga terdeteksi oleh Slither?
  - Apakah temuan Mythril sudah dikonfirmasi oleh Manticore?
  - Berapa false positive rate per tool?
  - Finding mana yang unique ke Mythril?
"""

from __future__ import annotations

from typing import Any


class CrossReferenceEngine:
    """Cross-references findings across Slither, Mythril, Manticore, and Echidna."""

    # SWC-to-check mapping: tool check names -> SWC ID
    TOOL_MAPPING: dict[str, dict[str, set[str]]] = {
        "slither": {
            "reentrancy": {"SWC-107"},
            "unchecked-calls": {"SWC-104"},
            "access-control": {"SWC-105"},
            "arbitrary-delegatecall": {"SWC-112"},
            "tx-origin": {"SWC-115"},
            "incorrect-equality": {"SWC-116"},
            "pragma": {"SWC-103"},
        },
    }

    def __init__(self) -> None:
        self._stats: dict[str, Any] = {
            "total_cross_refs": 0,
            "confirmed": 0,
            "conflicting": 0,
            "unique": 0,
        }

    def cross_reference(
        self,
        mythril_findings: list[dict[str, Any]],
        slither_findings: list[dict[str, Any]] | None = None,
        manticore_findings: list[dict[str, Any]] | None = None,
        echidna_findings: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Cross-reference Mythril findings against other tools.

        Returns enriched findings with cross-reference metadata.
        """
        enriched: list[dict[str, Any]] = []
        stats = {"total": 0, "confirmed": 0, "conflicting": 0, "unique": 0}

        for finding in mythril_findings:
            ref = self._ref_single_finding(
                finding, slither_findings, manticore_findings, echidna_findings
            )
            finding["cross_reference"] = ref
            enriched.append(finding)

            if ref.get("status") == "confirmed":
                stats["confirmed"] += 1
            elif ref.get("status") == "conflicting":
                stats["conflicting"] += 1
            else:
                stats["unique"] += 1
            stats["total"] += 1

        self._stats = stats
        return {
            "enriched_findings": enriched,
            "statistics": stats,
            "summary": self._build_summary(stats),
        }

    def _ref_single_finding(
        self,
        finding: dict[str, Any],
        slither: list[dict[str, Any]] | None,
        manticore: list[dict[str, Any]] | None,
        echidna: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Cross-reference a single finding against all tools."""
        swc_id = finding.get("swc_id", "")
        bug_type = finding.get("bug_type", "")
        title = finding.get("title", "")

        ref: dict[str, Any] = {
            "swc_id": swc_id,
            "bug_type": bug_type,
            "slither": self._match_slither(swc_id, bug_type, title, slither),
            "manticore": self._match_manticore(swc_id, bug_type, title, manticore),
            "echidna": self._match_echidna(swc_id, bug_type, title, echidna),
        }

        # Determine overall status
        confirmations = sum(
            1 for v in [ref["slither"], ref["manticore"], ref["echidna"]] if v.get("confirmed")
        )
        total_available = sum(
            1 for v in [ref["slither"], ref["manticore"], ref["echidna"]] if v.get("checked")
        )

        if confirmations >= 2:
            ref["status"] = "confirmed"
            ref["confidence_boost"] = 0.2
        elif confirmations == 1:
            ref["status"] = "partial"
            ref["confidence_boost"] = 0.1
        elif total_available == 0:
            ref["status"] = "unknown"
            ref["confidence_boost"] = 0.0
        else:
            ref["status"] = "unique_to_mythril"
            ref["confidence_boost"] = 0.0

        return ref

    def _match_slither(
        self, swc_id: str, bug_type: str, title: str, slither: list[dict[str, Any]] | None
    ) -> dict[str, Any]:
        """Check if Slither found the same bug."""
        result: dict[str, Any] = {"checked": False, "confirmed": False, "finding": None}
        if not slither:
            return result
        result["checked"] = True

        for sf in slither:
            sf_swc = sf.get("swc_id", "")
            sf_check = sf.get("check", "")

            if swc_id and sf_swc and swc_id == sf_swc:
                result["confirmed"] = True
                result["finding"] = sf
                result["match_type"] = "swc_id_exact"
                break

            # Fuzzy match by bug type
            if bug_type and sf_check and (
                bug_type.lower() in sf_check.lower()
                or sf_check.lower() in bug_type.lower()
            ):
                result["confirmed"] = True
                result["finding"] = sf
                result["match_type"] = "bug_type_fuzzy"
                break

        return result

    def _match_manticore(
        self, swc_id: str, bug_type: str, title: str, manticore: list[dict[str, Any]] | None
    ) -> dict[str, Any]:
        """Check if Manticore confirmed this finding."""
        result: dict[str, Any] = {"checked": False, "confirmed": False}
        if not manticore:
            return result
        result["checked"] = True

        for mf in manticore:
            mf_bug = mf.get("bug_type", "")
            if bug_type and mf_bug and bug_type == mf_bug:
                result["confirmed"] = True
                result["confidence"] = mf.get("confidence", 0.8)
                break

            mf_title = mf.get("title", "")
            if title and mf_title and (
                title.lower() in mf_title.lower()
                or mf_title.lower() in title.lower()
            ):
                result["confirmed"] = True
                break

        return result

    def _match_echidna(
        self, swc_id: str, bug_type: str, title: str, echidna: list[dict[str, Any]] | None
    ) -> dict[str, Any]:
        """Check if Echidna fuzzing found related bugs."""
        result: dict[str, Any] = {"checked": False, "confirmed": False}
        if not echidna:
            return result
        result["checked"] = True

        for ef in echidna:
            ef_cat = (ef.get("category", "") or ef.get("classification", "") or "").lower()
            if bug_type and ef_cat and bug_type.lower() in ef_cat:
                result["confirmed"] = True
                break

        return result

    def _build_summary(self, stats: dict[str, Any]) -> str:
        total = stats.get("total", 0)
        if total == 0:
            return "No findings to cross-reference."

        confirmed = stats.get("confirmed", 0)
        conflicting = stats.get("conflicting", 0)
        unique = stats.get("unique", 0)

        parts: list[str] = []
        if confirmed:
            parts.append(f"{confirmed}/{total} findings confirmed by other tools")
        if unique:
            parts.append(f"{unique}/{total} findings unique to Mythril")
        if conflicting:
            parts.append(f"{conflicting}/{total} findings have conflicting results")

        return "; ".join(parts) if parts else "Cross-reference incomplete."
