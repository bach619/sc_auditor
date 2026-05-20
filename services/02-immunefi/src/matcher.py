"""AISmartMatcher — AI-powered matching antara auditor dan program.

Menggunakan Service 06 (AI) untuk:
  1. Generate embedding dari auditor specialization
  2. Generate embedding dari program descriptions + tags
  3. Cosine similarity scoring
  4. Weighted recommendation

Fallback ke keyword-based matching kalau AI service unavailable.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

from src.models import Program
from src.scorer import ProgramScorer

log = structlog.get_logger()

AI_SERVICE_URL = os.getenv("AI_URL", "http://06-ai:8000")


class AISmartMatcher:
    """Cocokkan auditor dengan program terbaik menggunakan AI embeddings.

    Usage:
        matcher = AISmartMatcher()
        matches = await matcher.find_best(
            specialization="defi, reentrancy, solidity",
            programs=programs_dict,
            min_bounty=50000,
            limit=10,
        )
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _get_embedding(self, text: str) -> list[float] | None:
        """Generate embedding via AI Service 06.

        POST /embed → { "data": { "embedding": [...] } }
        """
        client = await self._get_client()
        try:
            resp = await client.post(
                f"{AI_SERVICE_URL}/embed",
                json={"text": text},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                if isinstance(data, dict):
                    return data.get("embedding")
                return None
        except Exception as e:
            log.warning("matcher.embedding_error", error=str(e)[:100])
        return None

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _keyword_match_score(
        self,
        specialization: str,
        program: Program,
    ) -> float:
        """Fallback keyword-based matching score."""
        keywords = set(specialization.lower().replace(",", " ").split())
        score = 0.0
        total = len(keywords)
        if total == 0:
            return 0.5

        # Check against tags
        prog_tags = {t.lower() for t in program.tags}
        tag_matches = len(keywords & prog_tags)
        score += tag_matches * 0.3

        # Check against description
        desc = (program.description or "").lower()
        for kw in keywords:
            if kw in desc:
                score += 0.2

        # Check against name
        name = program.name.lower()
        for kw in keywords:
            if kw in name:
                score += 0.3

        return min(score / max(total, 1), 1.0)

    async def find_best(
        self,
        specialization: str,
        programs: dict[str, Program],
        min_bounty: float = 0,
        max_bounty: float | None = None,
        chain: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Cari program terbaik untuk auditor tertentu.

        Args:
            specialization: Keahlian auditor (e.g. "defi, reentrancy, solidity")
            programs: Dict of slug → Program
            min_bounty: Minimum bounty filter
            max_bounty: Maximum bounty filter
            chain: Filter by chain
            limit: Max results

        Returns:
            List of {slug, name, score, reasons, ...} sorted by score desc.
        """
        # Filter programs
        candidates = list(programs.values())
        if min_bounty > 0:
            candidates = [p for p in candidates if (p.max_bounty or 0) >= min_bounty]
        if max_bounty is not None:
            candidates = [p for p in candidates if (p.max_bounty or 0) <= max_bounty]
        if chain:
            chain_lower = chain.lower()
            candidates = [
                p for p in candidates
                if any(c.lower() == chain_lower for c in p.chains)
            ]

        if not candidates:
            return []

        # Try AI embedding matching
        auditor_embedding = await self._get_embedding(specialization)
        use_ai = auditor_embedding is not None

        scorer = ProgramScorer()
        scored = []

        for prog in candidates:
            if use_ai:
                # AI-based matching
                prog_text = f"{prog.name} {' '.join(prog.tags)} {prog.description[:500]}"
                prog_embedding = await self._get_embedding(prog_text)
                ai_score = self._cosine_similarity(
                    auditor_embedding, prog_embedding
                ) if prog_embedding else 0.0
            else:
                # Keyword fallback
                ai_score = self._keyword_match_score(specialization, prog)

            # Blend AI score + bounty score
            bounty_score = scorer._bounty_score(prog) / 100.0  # normalize
            total_score = (
                ai_score * 0.5
                + bounty_score * 0.25
                + (1.0 if prog.status.lower() in ("active", "live") else 0.2) * 0.25
            )

            reasons = []
            if ai_score > 0.6:
                reasons.append("Strong match with specialization")
            if bounty_score > 0.5:
                reasons.append(f"High bounty: ${prog.max_bounty:,.0f}")
            if prog.status.lower() in ("active", "live"):
                reasons.append("Program is active")

            scored.append({
                "slug": prog.slug,
                "name": prog.name,
                "total_score": round(total_score, 3),
                "ai_match_score": round(ai_score, 3),
                "bounty_score": round(bounty_score, 3),
                "max_bounty": prog.max_bounty,
                "chains": prog.chains,
                "tags": prog.tags,
                "status": prog.status,
                "reasons": reasons,
                "ai_matched": use_ai,
            })

        scored.sort(key=lambda x: x["total_score"], reverse=True)
        return scored[:limit]

    async def find_similar_programs(
        self,
        slug: str,
        programs: dict[str, Program],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Cari program yang mirip dengan program tertentu."""
        target = programs.get(slug)
        if not target:
            return []

        target_text = f"{target.name} {' '.join(target.tags)} {target.description[:500]}"
        target_embedding = await self._get_embedding(target_text)

        candidates = [p for s, p in programs.items() if s != slug]
        scored = []

        for prog in candidates:
            if target_embedding:
                prog_text = f"{prog.name} {' '.join(prog.tags)} {prog.description[:500]}"
                prog_emb = await self._get_embedding(prog_text)
                sim = self._cosine_similarity(
                    target_embedding, prog_emb
                ) if prog_emb else 0.0
            else:
                # Tag overlap
                target_tags = {t.lower() for t in target.tags}
                prog_tags = {t.lower() for t in prog.tags}
                overlap = len(target_tags & prog_tags)
                sim = overlap / max(len(target_tags | prog_tags), 1)

            scored.append({
                "slug": prog.slug,
                "name": prog.name,
                "similarity": round(sim, 3),
                "max_bounty": prog.max_bounty,
                "chains": prog.chains,
                "tags": prog.tags,
            })

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:limit]

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
