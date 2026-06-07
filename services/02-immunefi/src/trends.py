"""TrendAnalyzer — Analyze program trends over time.

Menggunakan history data (JSON Lines) dari EnhancedJSONStorage
untuk mendeteksi:
  - Program baru vs dihapus
  - Perubahan bounty (naik/turun)
  - Perubahan chain
  - Perubahan status
  - Aktivitas per chain
  - Aktivitas per tag
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from src.models import Program
from src.storage import EnhancedJSONStorage


class TrendAnalyzer:
    """Analyze program trends from history data."""

    def __init__(self, storage: EnhancedJSONStorage) -> None:
        self.storage = storage

    # ── Recent Changes ──────────────────────────────────────

    def recent_changes(
        self,
        hours: int = 24,
        min_programs: int = 5,
    ) -> dict[str, Any]:
        """Get changes in the last N hours across all programs.

        Returns summary of what changed recently.
        """
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        recent_programs: set[str] = set()
        bounty_changes: list[dict] = []
        status_changes: list[dict] = []

        # Get history for all programs (slugs from index)
        all_slugs = self.storage.get_index("all_slugs")
        if not isinstance(all_slugs, list):
            all_slugs = []

        for slug in all_slugs:
            history = self.storage.get_history(slug)
            for entry in history:
                ts = entry.get("timestamp", "")
                if not ts:
                    continue
                try:
                    entry_time = datetime.fromisoformat(ts)
                    if entry_time.tzinfo is None:
                        entry_time = entry_time.replace(tzinfo=UTC)
                except (ValueError, TypeError):
                    continue

                if entry_time < cutoff:
                    continue  # skip old entries

                recent_programs.add(slug)

                # Track bounty changes
                old = entry.get("old_value", {}) or {}
                new = entry.get("new_value", {}) or {}
                if old.get("max_bounty") != new.get("max_bounty"):
                    bounty_changes.append({
                        "slug": slug,
                        "old_bounty": old.get("max_bounty"),
                        "new_bounty": new.get("max_bounty"),
                        "timestamp": ts,
                    })
                if old.get("status") != new.get("status"):
                    status_changes.append({
                        "slug": slug,
                        "old_status": old.get("status"),
                        "new_status": new.get("status"),
                        "timestamp": ts,
                    })

        return {
            "period_hours": hours,
            "programs_modified": len(recent_programs),
            "bounty_changes": len(bounty_changes),
            "status_changes": len(status_changes),
            "bounty_changes_detail": bounty_changes[:20],
            "status_changes_detail": status_changes[:20],
        }

    # ── Chain Trends ────────────────────────────────────────

    def chain_trends(self, programs: dict[str, Program]) -> dict[str, Any]:
        """Analyze chain distribution trends."""
        chain_counts: Counter = Counter()
        for prog in programs.values():
            for chain in prog.chains:
                chain_counts[chain or "unknown"] += 1

        total = sum(chain_counts.values())
        return {
            "total_programs_with_chains": sum(
                1 for p in programs.values() if p.chains
            ),
            "total_chain_assignments": total,
            "chains": [
                {
                    "name": name,
                    "count": count,
                    "percentage": round(count / total * 100, 1) if total else 0,
                }
                for name, count in chain_counts.most_common()
            ],
        }

    # ── Bounty Distribution ─────────────────────────────────

    def bounty_trends(self, programs: dict[str, Program]) -> dict[str, Any]:
        """Analyze bounty distribution."""
        ranges = {
            "under_1k": 0,
            "1k_to_10k": 0,
            "10k_to_100k": 0,
            "100k_to_1M": 0,
            "over_1M": 0,
            "unknown": 0,
        }

        bounty_values: list[float] = []
        for prog in programs.values():
            b = prog.max_bounty
            if b is None:
                ranges["unknown"] += 1
            elif b < 1000:
                ranges["under_1k"] += 1
                bounty_values.append(b)
            elif b < 10_000:
                ranges["1k_to_10k"] += 1
                bounty_values.append(b)
            elif b < 100_000:
                ranges["10k_to_100k"] += 1
                bounty_values.append(b)
            elif b < 1_000_000:
                ranges["100k_to_1M"] += 1
                bounty_values.append(b)
            else:
                ranges["over_1M"] += 1
                bounty_values.append(b)

        avg_bounty = round(sum(bounty_values) / len(bounty_values), 2) if bounty_values else 0
        max_bounty = max(bounty_values) if bounty_values else 0

        return {
            "total_programs": len(programs),
            "programs_with_bounty": len(bounty_values),
            "average_bounty": avg_bounty,
            "max_bounty": max_bounty,
            "ranges": ranges,
        }

    # ── Status Distribution ─────────────────────────────────

    def status_trends(self, programs: dict[str, Program]) -> dict[str, Any]:
        """Analyze status distribution."""
        status_counts: Counter = Counter()
        for prog in programs.values():
            s = prog.status or "unknown"
            status_counts[s] += 1

        total = len(programs)
        return {
            "statuses": [
                {
                    "status": status,
                    "count": count,
                    "percentage": round(count / total * 100, 1) if total else 0,
                }
                for status, count in status_counts.most_common()
            ],
            "active_count": status_counts.get("active", 0)
                           + status_counts.get("live", 0)
                           + status_counts.get("open", 0),
        }

    # ── Tag / Category Trends ───────────────────────────────

    def tag_trends(self, programs: dict[str, Program]) -> dict[str, Any]:
        """Analyze tag/category distribution."""
        tag_counts: Counter = Counter()
        for prog in programs.values():
            for tag in prog.tags:
                tag_counts[tag] += 1

        total = sum(tag_counts.values())
        return {
            "total_tags": len(tag_counts),
            "tags": [
                {
                    "tag": tag,
                    "count": count,
                    "percentage": round(count / total * 100, 1) if total else 0,
                }
                for tag, count in tag_counts.most_common(20)
            ],
        }

    # ── Full Trend Report ──────────────────────────────────

    def full_report(self, programs: dict[str, Program]) -> dict[str, Any]:
        """Generate a complete trend report."""
        return {
            "recent_changes": self.recent_changes(hours=24),
            "chain_trends": self.chain_trends(programs),
            "bounty_trends": self.bounty_trends(programs),
            "status_trends": self.status_trends(programs),
            "tag_trends": self.tag_trends(programs),
            "total_programs": len(programs),
            "generated_at": datetime.now(UTC).isoformat(),
        }
