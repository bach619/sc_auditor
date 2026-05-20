"""DashboardData — Aggregated data untuk dashboard visualizations.

Menyediakan endpoint data yang siap dikonsumsi oleh frontend dashboard:
  - Overview cards (total bounty, active programs, dll)
  - Chain heatmap
  - Timeline bounty changes
  - Top programs
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.models import Program
from src.scorer import ProgramScorer
from src.storage import EnhancedJSONStorage
from src.trends import TrendAnalyzer


class DashboardData:
    """Generate data payloads for dashboard visualizations."""

    def __init__(self, storage: EnhancedJSONStorage) -> None:
        self.storage = storage
        self.scorer = ProgramScorer()

    def overview(self, programs: dict[str, Program]) -> dict[str, Any]:
        """Ringkasan dashboard: cards + KPIs."""
        total = len(programs)
        active = sum(
            1 for p in programs.values()
            if p.status.lower() in ("active", "live", "open")
        )

        total_bounty = sum(p.max_bounty or 0 for p in programs.values())
        avg_bounty = round(total_bounty / total, 2) if total else 0

        total_contracts = sum(len(p.contracts) for p in programs.values())
        total_repos = sum(len(p.repos) for p in programs.values())

        # Top 5 chains
        chains: dict[str, int] = {}
        for p in programs.values():
            for c in p.chains:
                chains[c or "unknown"] = chains.get(c or "unknown", 0) + 1
        top_chains = sorted(chains.items(), key=lambda x: -x[1])[:5]

        # Top 5 programs by score
        ranked = self.scorer.rank_all(programs)
        top_programs = ranked[:5]

        return {
            "total_programs": total,
            "active_programs": active,
            "inactive_programs": total - active,
            "total_bounty_usd": round(total_bounty, 2),
            "average_bounty_usd": avg_bounty,
            "total_contracts": total_contracts,
            "total_repos": total_repos,
            "top_chains": [
                {"name": name, "program_count": count}
                for name, count in top_chains
            ],
            "top_programs": [
                {
                    "slug": p["slug"],
                    "name": p["name"],
                    "score": p["score"],
                }
                for p in top_programs
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def chain_heatmap(self, programs: dict[str, Program]) -> dict[str, Any]:
        """Chain vs bounty heatmap data."""
        chain_data: dict[str, dict] = {}

        for p in programs.values():
            for chain in p.chains:
                c = chain or "unknown"
                if c not in chain_data:
                    chain_data[c] = {
                        "chain": c,
                        "program_count": 0,
                        "total_bounty": 0.0,
                        "max_bounty": 0.0,
                        "avg_bounty": 0.0,
                        "active_count": 0,
                    }
                chain_data[c]["program_count"] += 1
                bounty = p.max_bounty or 0
                chain_data[c]["total_bounty"] += bounty
                chain_data[c]["max_bounty"] = max(chain_data[c]["max_bounty"], bounty)
                if p.status.lower() in ("active", "live"):
                    chain_data[c]["active_count"] += 1

        for c in chain_data.values():
            c["avg_bounty"] = round(
                c["total_bounty"] / c["program_count"], 2
            ) if c["program_count"] else 0

        return {
            "chains": sorted(chain_data.values(), key=lambda x: -x["total_bounty"]),
            "total_chains": len(chain_data),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def bounty_timeline(self, programs: dict[str, Program]) -> dict[str, Any]:
        """Timeline data: bounty changes over time."""
        analyzer = TrendAnalyzer(self.storage)
        recent = analyzer.recent_changes(hours=720)  # 30 days

        # Aggregate by day
        daily_changes: dict[str, dict] = {}
        for change in recent.get("bounty_changes_detail", []):
            ts = change.get("timestamp", "")[:10]  # YYYY-MM-DD
            if ts not in daily_changes:
                daily_changes[ts] = {
                    "date": ts,
                    "increases": 0,
                    "decreases": 0,
                    "total_bounty_delta": 0.0,
                }
            old = change.get("old_bounty") or 0
            new = change.get("new_bounty") or 0
            delta = new - old
            daily_changes[ts]["total_bounty_delta"] += delta
            if delta > 0:
                daily_changes[ts]["increases"] += 1
            else:
                daily_changes[ts]["decreases"] += 1

        return {
            "timeline": sorted(daily_changes.values(), key=lambda x: x["date"]),
            "total_changes": recent.get("bounty_changes", 0),
            "programs_modified": recent.get("programs_modified", 0),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def full_dashboard(self, programs: dict[str, Program]) -> dict[str, Any]:
        """Complete dashboard data: overview + heatmap + timeline."""
        return {
            "overview": self.overview(programs),
            "chain_heatmap": self.chain_heatmap(programs),
            "bounty_timeline": self.bounty_timeline(programs),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
