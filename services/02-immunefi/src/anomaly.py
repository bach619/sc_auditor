"""AnomalyDetector — Detect unusual changes in bounty programs.

Anomalies terdeteksi dari history data:
  - Bounty spike/drop > 50% dalam 24 jam
  - Program tiba-tiba inactive setelah lama active
  - Chain berubah drastis
  - Banyak program berubah dalam waktu singkat (batch change)
  - Program hilang (deleted tanpa history)

Setiap anomaly punya severity: info, warning, critical.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from src.models import Program
from src.storage import EnhancedJSONStorage


class AnomalyDetector:
    """Detect anomalies from program history and current state."""

    def __init__(self, storage: EnhancedJSONStorage) -> None:
        self.storage = storage

    # ── Detection Methods ──────────────────────────────────

    def detect(self, programs: dict[str, Program]) -> list[dict[str, Any]]:
        """Run all anomaly detectors and return sorted results."""
        anomalies: list[dict[str, Any]] = []

        anomalies.extend(self._detect_bounty_spikes(programs))
        anomalies.extend(self._detect_sudden_inactive(programs))
        anomalies.extend(self._detect_batch_changes(programs))
        anomalies.extend(self._detect_missing_programs(programs))
        anomalies.extend(self._detect_fork_opportunities(programs))

        # Sort by severity: critical > warning > info
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        anomalies.sort(key=lambda a: severity_order.get(a.get("severity", "info"), 99))

        return anomalies

    # ── Bounty Spikes / Drops ──────────────────────────────

    def _detect_bounty_spikes(
        self,
        programs: dict[str, Program],
    ) -> list[dict]:
        """Detect bounty changes >50% in recent history."""
        anomalies: list[dict] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

        for slug, prog in programs.items():
            history = self.storage.get_history(slug, limit=3)
            if len(history) < 2:
                continue

            # Check most recent two entries
            latest = history[-1] if len(history) >= 1 else None
            if not latest:
                continue

            ts = latest.get("timestamp", "")
            if ts:
                try:
                    entry_time = datetime.fromisoformat(ts)
                    if entry_time.tzinfo is None:
                        entry_time = entry_time.replace(tzinfo=timezone.utc)
                    if entry_time < cutoff:
                        continue
                except (ValueError, TypeError):
                    continue

            old_val = (latest.get("old_value") or {}) if latest else {}
            new_val = (latest.get("new_value") or {}) if latest else {}

            old_bounty = old_val.get("max_bounty")
            new_bounty = new_val.get("max_bounty")

            if old_bounty and new_bounty and old_bounty > 0:
                change_pct = abs(new_bounty - old_bounty) / old_bounty * 100
                if change_pct >= 50:
                    severity = "critical" if change_pct >= 200 else "warning"
                    anomalies.append({
                        "id": uuid.uuid4().hex[:12],
                        "type": "bounty_change",
                        "severity": severity,
                        "slug": slug,
                        "program_name": prog.name,
                        "detail": (
                            f"Bounty changed {change_pct:.0f}%: "
                            f"${old_bounty:,.0f} → ${new_bounty:,.0f}"
                        ),
                        "old_bounty": old_bounty,
                        "new_bounty": new_bounty,
                        "change_percentage": round(change_pct, 1),
                        "timestamp": ts,
                    })

        return anomalies

    # ── Sudden Inactive ────────────────────────────────────

    def _detect_sudden_inactive(
        self,
        programs: dict[str, Program],
    ) -> list[dict]:
        """Detect programs that went inactive after being active."""
        anomalies: list[dict] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=72)

        for slug, prog in programs.items():
            if prog.status.lower() in ("inactive", "closed", "completed", "hold"):
                # Check if it was active before
                history = self.storage.get_history(slug, limit=3)
                for entry in history:
                    old_val = entry.get("old_value") or {}
                    new_val = entry.get("new_value") or {}
                    old_status = (old_val.get("status") or "").lower()
                    new_status = (new_val.get("status") or "").lower()

                    if old_status in ("active", "live") and new_status in (
                        "inactive", "closed", "completed", "hold"
                    ):
                        ts = entry.get("timestamp", "")
                        if ts:
                            try:
                                entry_time = datetime.fromisoformat(ts)
                                if entry_time.tzinfo is None:
                                    entry_time = entry_time.replace(tzinfo=timezone.utc)
                                if entry_time < cutoff:
                                    continue
                            except (ValueError, TypeError):
                                continue

                        anomalies.append({
                            "id": uuid.uuid4().hex[:12],
                            "type": "status_change",
                            "severity": "warning",
                            "slug": slug,
                            "program_name": prog.name,
                            "detail": f"Program changed from '{old_status}' to '{new_status}'",
                            "old_status": old_status,
                            "new_status": new_status,
                            "timestamp": ts,
                        })
                        break  # one alert per program

        return anomalies

    # ── Batch Changes ──────────────────────────────────────

    def _detect_batch_changes(
        self,
        programs: dict[str, Program],
    ) -> list[dict]:
        """Detect if many programs changed in a short window."""
        anomalies: list[dict] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=6)

        # Count changes per slug in the last 6 hours
        changed_slugs: set[str] = set()
        for slug in programs:
            history = self.storage.get_history(slug, limit=1)
            if not history:
                continue
            ts = history[0].get("timestamp", "")
            if ts:
                try:
                    entry_time = datetime.fromisoformat(ts)
                    if entry_time.tzinfo is None:
                        entry_time = entry_time.replace(tzinfo=timezone.utc)
                    if entry_time >= cutoff:
                        changed_slugs.add(slug)
                except (ValueError, TypeError):
                    continue

        if len(changed_slugs) >= 10:
            anomalies.append({
                "id": uuid.uuid4().hex[:12],
                "type": "batch_change",
                "severity": "info",
                "slug": "N/A",
                "program_name": "Multiple Programs",
                "detail": f"{len(changed_slugs)} programs changed in the last 6 hours",
                "count": len(changed_slugs),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return anomalies

    # ── Missing Programs ───────────────────────────────────

    def _detect_missing_programs(
        self,
        programs: dict[str, Program],
    ) -> list[dict]:
        """Detect programs that exist in index but not on disk."""
        anomalies: list[dict] = []
        all_slugs = self.storage.get_index("all_slugs")

        if not isinstance(all_slugs, list):
            return []

        for slug in all_slugs:
            if slug not in programs:
                anomalies.append({
                    "id": uuid.uuid4().hex[:12],
                    "type": "missing_program",
                    "severity": "warning",
                    "slug": slug,
                    "program_name": slug,
                    "detail": f"Program '{slug}' in index but not loaded in memory",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        return anomalies

    # ── Fork Opportunities ─────────────────────────────────

    def _detect_fork_opportunities(
        self,
        programs: dict[str, Program],
    ) -> list[dict]:
        """Detect programs with repos that might need forking.

        A fork opportunity = program has repos but fork index
        says they haven't been forked yet.
        """
        anomalies: list[dict] = []
        fork_index = self.storage.get_index("forks")

        if not isinstance(fork_index, dict):
            return []

        for slug, prog in programs.items():
            for repo in prog.repos:
                repo_key = f"{repo.owner}/{repo.repo}"
                if repo_key not in fork_index:
                    anomalies.append({
                        "id": uuid.uuid4().hex[:12],
                        "type": "fork_opportunity",
                        "severity": "info",
                        "slug": slug,
                        "program_name": prog.name,
                        "detail": f"Repo {repo_key} not yet forked",
                        "repo_owner": repo.owner,
                        "repo_name": repo.repo,
                        "repo_url": repo.url,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

        return anomalies

    # ── Summary ────────────────────────────────────────────

    def summary(self, programs: dict[str, Program]) -> dict[str, Any]:
        """Return anomaly summary with counts by type and severity."""
        all_anomalies = self.detect(programs)

        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for a in all_anomalies:
            by_type[a["type"]] = by_type.get(a["type"], 0) + 1
            by_severity[a["severity"]] = by_severity.get(a["severity"], 0) + 1

        return {
            "total_anomalies": len(all_anomalies),
            "by_type": by_type,
            "by_severity": by_severity,
            "critical_count": by_severity.get("critical", 0),
            "warning_count": by_severity.get("warning", 0),
            "anomalies": all_anomalies[:50],  # limit to 50
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
