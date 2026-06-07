"""PriorityScorer — calculates scan priority (0–100) for contracts.

Factors:
  - 40% Bounty size (from Immunefi program data)
  - 30% Contract similarity to known true-positive contracts
  - 15% Chain (Ethereum first, then L2s, then others)
  - 10% Freshness (newly listed programs get a boost)
  -  5% TP history (programs with prior valid findings rank higher)
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config import config


class PriorityScorer:
    """Calculates and manages priority scores for queued contracts."""

    # Chain ranking: Ethereum gets highest priority, then L2s
    CHAIN_RANKS: dict[str, int] = {
        "ethereum": 100,
        "arbitrum": 90,
        "optimism": 85,
        "base": 80,
        "polygon": 75,
        "avalanche": 70,
        "bnb": 65,
        "bnbchain": 65,
        "solana": 60,  # non-EVM, still high value
        "fantom": 55,
        "cronos": 50,
        "linea": 50,
        "scroll": 50,
        "zksync": 50,
        "zkevm": 50,
        "blast": 45,
        "mantle": 45,
        "others": 30,
    }

    def __init__(self) -> None:
        self._tp_history: dict[str, int] = {}  # program_slug -> count of TP findings
        self._load_tp_history()

    # ── Persistence ─────────────────────────────────────────────

    def _load_tp_history(self) -> None:
        tp_file = Path(config.data_dir) / "tp_history.json"
        if tp_file.exists():
            try:
                self._tp_history = json.loads(tp_file.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                self._tp_history = {}

    def _save_tp_history(self) -> None:
        tp_file = Path(config.data_dir) / "tp_history.json"
        tp_file.parent.mkdir(parents=True, exist_ok=True)
        tp_file.write_text(json.dumps(self._tp_history, indent=2), "utf-8")

    def record_tp_finding(self, program_slug: str) -> None:
        """Increment the TP count for a program."""
        self._tp_history[program_slug] = self._tp_history.get(program_slug, 0) + 1
        self._save_tp_history()

    # ── Scoring ──────────────────────────────────────────────────

    def score(
        self,
        program: dict[str, Any] | None = None,
        similarity_data: list[tuple[str, float]] | None = None,
        chain: str = "ethereum",
        created_at: datetime | None = None,
        program_slug: str = "",
    ) -> float:
        """Compute priority score 0–100.

        Args:
            program: Immunefi program dict with keys like 'maxBounty', 'payoutRange', etc.
            similarity_data: List of (contract_id, score) from ContractSimilarity.find_similar()
            chain: Blockchain name.
            created_at: When the contract/program was added (for freshness).
            program_slug: Program identifier for TP history lookup.
        """
        score = 0.0

        # 1. Bounty component (40%)
        bounty_score = self._score_bounty(program)
        score += config.priority_weight_bounty * bounty_score

        # 2. Similarity component (30%)
        similarity_score = self._score_similarity(similarity_data)
        score += config.priority_weight_similarity * similarity_score

        # 3. Chain component (15%)
        chain_score = self._score_chain(chain)
        score += config.priority_weight_chain * chain_score

        # 4. Freshness (10%)
        freshness_score = self._score_freshness(created_at)
        score += config.priority_weight_freshness * freshness_score

        # 5. TP history (5%)
        tp_score = self._score_tp_history(program_slug)
        score += config.priority_weight_tp_history * tp_score

        return min(max(score, 0.0), 100.0)

    # ── Sub-scores ───────────────────────────────────────────────

    def _score_bounty(self, program: dict[str, Any] | None) -> float:
        """Score 0–100 based on bounty size."""
        if not program:
            return 50.0  # neutral default

        # Try multiple possible keys that Immunefi API returns
        max_bounty = (
            program.get("maxBounty")
            or program.get("max_bounty")
            or program.get("payoutRange", {}).get("max")
            or 0
        )
        if isinstance(max_bounty, str):
            try:
                max_bounty = float(max_bounty.replace("$", "").replace(",", ""))
            except (ValueError, AttributeError):
                max_bounty = 0

        if max_bounty <= 0:
            return 50.0

        # Logarithmic scale: $0 → 0, $100k → 50, $1M → 80, $10M+ → 100
        log_score = 100.0 * math.log10(1 + max_bounty / 1_000) / math.log10(1 + 10_000_000 / 1_000)
        return min(max(log_score, 0.0), 100.0)

    def _score_similarity(
        self, similarity_data: list[tuple[str, float]] | None
    ) -> float:
        """Score 0–100. Higher if similar to TP-prone contracts."""
        if not similarity_data:
            return 0.0
        # Take the highest similarity score
        best = max(s[1] for s in similarity_data)
        return best * 100.0  # similarity is 0–1

    def _score_chain(self, chain: str) -> float:
        """Score 0–100 based on chain priority."""
        return float(self.CHAIN_RANKS.get(chain.lower(), self.CHAIN_RANKS["others"]))

    def _score_freshness(self, created_at: datetime | None) -> float:
        """Score 0–100. Newly added items score higher; decays over 30 days."""
        if created_at is None:
            return 50.0
        now = datetime.now(UTC)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        age_days = (now - created_at).days
        if age_days < 0:
            return 100.0  # future date = max freshness
        decay = max(0.0, 1.0 - age_days / 30.0)
        return 100.0 * decay

    def _score_tp_history(self, program_slug: str) -> float:
        """Score 0–100 based on historical TP findings for the program."""
        count = self._tp_history.get(program_slug, 0)
        if count == 0:
            return 0.0
        # 1 finding → 50, 2 → 75, 3+ → 100
        return min(100.0, 50.0 * math.log2(1 + count))

    # ── Queue management ────────────────────────────────────────

    def sort_queue(self, queue: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Re-sort a list of queue items by priority_score descending."""
        return sorted(queue, key=lambda item: item.get("priority_score", 0), reverse=True)


__all__ = ["PriorityScorer"]
