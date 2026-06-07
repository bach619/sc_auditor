"""ProgramScorer — Scoring engine for bug bounty programs.

Menghitung intelligence score (0–100) untuk setiap program berdasarkan:
  - Bounty amount (log scale)
  - Chain diversity
  - Activity (recency of updates)
  - Repository presence
  - Contract presence
  - Tags / categories
  - Status

Score disimpan di index agar bisa diquery cepat via /programs?sort=score.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from src.models import Program


class ProgramScorer:
    """Compute intelligence scores for programs.

    Usage:
        scorer = ProgramScorer()
        score = scorer.score(program)
        ranked = scorer.rank_all(programs_dict)
    """

    # ── Weights (total = 1.0) ───────────────────────────────

    WEIGHT_BOUNTY = 0.30
    WEIGHT_CHAINS = 0.10
    WEIGHT_ACTIVITY = 0.10
    WEIGHT_REPOS = 0.15
    WEIGHT_CONTRACTS = 0.10
    WEIGHT_TAGS = 0.10
    WEIGHT_STATUS = 0.05
    WEIGHT_COMPLEXITY = 0.10

    # Tags that indicate higher-quality programs
    BOOST_TAGS: set[str] = {
        "erc20", "defi", "dex", "lending", "bridge",
        "staking", "yield", "oracle", "cross-chain",
        "layer2", "l2", "rollup", "zkevm",
        "infrastructure", "protocol",
    }

    # ── Scoring ─────────────────────────────────────────────

    def score(self, program: Program) -> float:
        """Compute total score (0–100) for a single program."""
        components = self.score_components(program)
        return round(sum(components.values()), 1)

    def score_components(self, program: Program) -> dict[str, float]:
        """Return breakdown of score by factor."""
        return {
            "bounty": self._bounty_score(program) * self.WEIGHT_BOUNTY,
            "chains": self._chains_score(program) * self.WEIGHT_CHAINS,
            "activity": self._activity_score(program) * self.WEIGHT_ACTIVITY,
            "repos": self._repos_score(program) * self.WEIGHT_REPOS,
            "contracts": self._contracts_score(program) * self.WEIGHT_CONTRACTS,
            "tags": self._tags_score(program) * self.WEIGHT_TAGS,
            "status": self._status_score(program) * self.WEIGHT_STATUS,
            "complexity": self._complexity_score(program) * self.WEIGHT_COMPLEXITY,
        }

    def rank_all(self, programs: dict[str, Program]) -> list[dict[str, Any]]:
        """Rank all programs by score descending.

        Returns list of {slug, name, score, components}.
        """
        ranked = []
        for slug, prog in programs.items():
            components = self.score_components(prog)
            total = round(sum(components.values()), 1)
            ranked.append({
                "slug": slug,
                "name": prog.name,
                "score": total,
                "components": {k: round(v, 2) for k, v in components.items()},
            })

        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked

    # ── Sub-scores (each 0–100) ─────────────────────────────

    def _bounty_score(self, program: Program) -> float:
        """Bounty score on log scale.

        0 = no bounty
        <1k  → ~10
        <10k → ~30
        <100k → ~50
        <1M → ~70
        >=10M → ~100
        """
        bounty = program.max_bounty
        if bounty is None or bounty <= 0:
            return 0.0

        # Log scale: log10(bounty) mapped to 0–100
        log_val = math.log10(bounty)
        # log10(1_000) = 3 → ~20; log10(10_000_000) = 7 → ~100
        score = min(100.0, max(0.0, (log_val - 2.0) * 20.0))
        return round(score, 1)

    def _chains_score(self, program: Program) -> float:
        """Chain diversity score.

        0 chains → 0
        1 chain  → 30
        2 chains → 50
        3 chains → 70
        4+       → 100
        """
        count = len(program.chains)
        if count == 0:
            return 0.0
        if count == 1:
            return 30.0
        if count == 2:
            return 50.0
        if count == 3:
            return 70.0
        return 100.0

    def _activity_score(self, program: Program) -> float:
        """Recency score based on updated_at.

        < 1 day ago  → 100
        < 7 days     → 80
        < 30 days    → 60
        < 90 days    → 40
        < 365 days   → 20
        older/never  → 0
        """
        if not program.updated_at:
            return 0.0

        try:
            updated = datetime.fromisoformat(program.updated_at)
        except (ValueError, TypeError):
            return 0.0

        now = datetime.now(UTC)
        # Naive datetime → assume UTC
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=UTC)

        delta = now - updated
        days = delta.days

        if days < 0:
            return 100.0  # future date? treat as very fresh
        if days < 1:
            return 100.0
        if days < 7:
            return 80.0
        if days < 30:
            return 60.0
        if days < 90:
            return 40.0
        if days < 365:
            return 20.0
        return 0.0

    def _repos_score(self, program: Program) -> float:
        """Repository presence score.

        No repos  → 0
        1 repo    → 60
        2+ repos  → 100
        """
        count = len(program.repos)
        if count == 0:
            return 0.0
        if count == 1:
            return 60.0
        return 100.0

    def _contracts_score(self, program: Program) -> float:
        """Contract presence score.

        0 contracts → 0
        1 contract  → 40
        2-5         → 70
        6+          → 100
        """
        count = len(program.contracts)
        if count == 0:
            return 0.0
        if count == 1:
            return 40.0
        if count <= 5:
            return 70.0
        return 100.0

    def _complexity_score(self, program: Program) -> float:
        """Contract complexity score.

        Lebih kompleks = lebih menarik (lebih banyak potensi bugs).
        Berdasarkan jumlah kontrak, jumlah chain, dan jumlah repo.

        0 contracts → 0
        1 contract  → 20
        2-5         → 50
        6+          → 80
        Plus bonus untuk multi-chain: +10, multi-repo: +10
        """
        contract_count = len(program.contracts)
        if contract_count == 0:
            base = 0.0
        elif contract_count == 1:
            base = 20.0
        elif contract_count <= 5:
            base = 50.0
        else:
            base = 80.0

        # Bonus untuk multi-chain
        if len(program.chains) > 1:
            base += 10.0

        # Bonus untuk multi-repo
        if len(program.repos) > 1:
            base += 10.0

        return min(base, 100.0)

    def _tags_score(self, program: Program) -> float:
        """Tag/category score.

        Programs with relevant tags get a boost.
        More boost tags → higher score.
        """
        if not program.tags:
            return 50.0  # neutral: no tags = middle

        tags_lower = {t.lower() for t in program.tags}
        boost_count = len(tags_lower & self.BOOST_TAGS)

        if boost_count >= 3:
            return 100.0
        if boost_count == 2:
            return 80.0
        if boost_count == 1:
            return 65.0
        return 50.0

    def _status_score(self, program: Program) -> float:
        """Status score.

        active/active → 100
        unknown      → 50
        inactive/hold → 20
        others       → 0
        """
        status = (program.status or "").lower()
        if status in ("active", "live", "open"):
            return 100.0
        if status in ("", "unknown"):
            return 50.0
        if status in ("inactive", "hold", "paused", "closed", "completed"):
            return 20.0
        return 0.0

    # ── Bulk helpers ────────────────────────────────────────

    def build_score_index(self, programs: dict[str, Program]) -> dict[str, Any]:
        """Build a compreshensive score index for all programs.

        Returns dict with:
          - scores: {slug: total_score}
          - components: {slug: {factor: score}}
          - ranked: list sorted by score desc
          - top_programs: top 10 slugs
        """
        ranked = self.rank_all(programs)
        scores: dict[str, float] = {}
        components: dict[str, dict] = {}
        for entry in ranked:
            scores[entry["slug"]] = entry["score"]
            components[entry["slug"]] = entry["components"]

        return {
            "scores": scores,
            "components": components,
            "ranked": ranked,
            "top_programs": [r["slug"] for r in ranked[:10]],
            "total_scored": len(ranked),
            "average_score": round(
                sum(scores.values()) / len(scores), 1
            ) if scores else 0.0,
        }
