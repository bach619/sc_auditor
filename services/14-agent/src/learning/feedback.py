"""Feedback-based learning system.

Menganalisis hasil session agent dan mengekstrak pola:
- Skill apa yang paling efektif untuk tipe task tertentu?
- Error apa yang sering muncul?
- Contract type apa yang paling riskan?
- Approach apa yang menghasilkan TP (True Positive) tertinggi?

Pola-pola ini disimpan di VectorMemory dan GraphMemory
untuk digunakan di session selanjutnya.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

import structlog

from src.memory import AgentMemory
from src.models import AgentSession, AgentState, TaskType

log = structlog.get_logger()


class LearningStats:
    """Statistik pembelajaran dari session-session sebelumnya."""

    def __init__(self) -> None:
        self.total_sessions_analyzed: int = 0
        self.patterns_found: int = 0
        self.last_analysis: float = 0.0
        self.task_type_performance: dict[str, dict[str, float]] = {}
        self.error_patterns: dict[str, int] = {}
        self.skill_effectiveness: dict[str, dict[str, float]] = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_sessions_analyzed": self.total_sessions_analyzed,
            "patterns_found": self.patterns_found,
            "last_analysis": self.last_analysis,
            "task_type_performance": self.task_type_performance,
            "top_error_patterns": dict(
                sorted(
                    self.error_patterns.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:10]
            ),
            "skill_effectiveness": self.skill_effectiveness,
        }


class FeedbackLearner:
    """Menganalisis session outcomes dan mengekstrak pembelajaran.

    Attributes:
        memory: Agent memory system (untuk menyimpan pola)
        stats: Learning statistics
    """

    def __init__(self, memory: AgentMemory) -> None:
        self.memory = memory
        self.stats = LearningStats()

    async def analyze_session(self, session: AgentSession) -> dict[str, Any]:
        """Analisis satu session setelah selesai.

        Args:
            session: Completed AgentSession

        Returns:
            Dict dengan hasil analisis (patterns, insights)
        """
        patterns: list[dict[str, Any]] = []
        insights: list[str] = []

        # 1. Task type effectiveness
        tt_key = session.task_type.value
        if tt_key not in self.stats.task_type_performance:
            self.stats.task_type_performance[tt_key] = {
                "total": 0, "success": 0, "failed": 0, "avg_steps": 0.0
            }

        perf = self.stats.task_type_performance[tt_key]
        perf["total"] += 1
        if session.status == AgentState.COMPLETED:
            perf["success"] += 1
        else:
            perf["failed"] += 1

        total = perf["total"]
        steps = len(session.steps)
        perf["avg_steps"] = (
            (perf["avg_steps"] * (total - 1) + steps) / total
        )

        # 2. Skill effectiveness per step
        skill_counts: dict[str, int] = defaultdict(int)
        skill_success: dict[str, int] = defaultdict(int)
        for step in session.steps:
            skill_counts[step.action] += 1
            if step.status == AgentState.COMPLETED:
                skill_success[step.action] += 1

        for skill_name, count in skill_counts.items():
            if skill_name not in self.stats.skill_effectiveness:
                self.stats.skill_effectiveness[skill_name] = {
                    "total": 0, "success": 0
                }
            se = self.stats.skill_effectiveness[skill_name]
            se["total"] += count
            se["success"] += skill_success.get(skill_name, 0)

        # 3. Error pattern detection
        for step in session.steps:
            if step.status == AgentState.FAILED and step.error:
                error_key = step.error.split(":")[0][:80]
                self.stats.error_patterns[error_key] = (
                    self.stats.error_patterns.get(error_key, 0) + 1
                )
                if self.stats.error_patterns[error_key] >= 3:
                    patterns.append({
                        "type": "recurring_error",
                        "pattern": error_key,
                        "count": self.stats.error_patterns[error_key],
                        "skill": step.action,
                    })

        # 4. Step count outlier
        if steps > 20:
            patterns.append({
                "type": "long_session",
                "steps": steps,
                "task_type": session.task_type.value,
                "suggestion": "Consider breaking into sub-tasks",
            })

        # 5. Success insight
        if session.status == AgentState.COMPLETED:
            insight = (
                f"Session {session.session_id[:8]}: {session.task_type.value} "
                f"berhasil dalam {steps} langkah"
            )
            insights.append(insight)

            # Store successful pattern in vector memory
            try:
                await self.memory.vector.store_text(
                    f"success_pattern_{session.session_id[:8]}",
                    insight,
                    metadata={
                        "type": "success_pattern",
                        "task_type": session.task_type.value,
                        "steps": steps,
                    },
                )
            except Exception:
                pass

        # 6. Store analysis results in episodic memory
        if patterns or insights:
            try:
                await self.memory.episodic_store.store_text(
                    f"learning_analysis_{session.session_id[:8]}",
                    {
                        "patterns": patterns,
                        "insights": insights[:3],
                    },
                    metadata={
                        "session_id": session.session_id,
                        "event": "learning_analysis",
                    },
                )
            except Exception:
                pass

        self.stats.total_sessions_analyzed += 1
        self.stats.patterns_found += len(patterns)
        self.stats.last_analysis = time.time()

        return {
            "session_id": session.session_id,
            "patterns_found": patterns,
            "insights": insights,
            "skill_usage": dict(skill_counts),
        }

    async def get_recommendations(
        self, task_type: str | None = None
    ) -> dict[str, Any]:
        """Dapatkan rekomendasi berdasarkan pembelajaran sebelumnya.

        Args:
            task_type: Optional filter by task type

        Returns:
            Dict dengan rekomendasi skill, error warnings, dll
        """
        recommendations = {
            "recommended_skills": [],
            "error_warnings": [],
            "success_rate": {},
            "patterns": [],
        }

        # Recommended skills for task type
        if task_type and task_type in self.stats.task_type_performance:
            perf = self.stats.task_type_performance[task_type]
            success_rate = (
                perf["success"] / perf["total"] * 100 if perf["total"] > 0 else 0
            )
            recommendations["success_rate"][task_type] = round(success_rate, 1)

            # Skills sorted by usage
            sorted_skills = sorted(
                self.stats.skill_effectiveness.items(),
                key=lambda x: x[1]["total"],
                reverse=True,
            )
            recommendations["recommended_skills"] = [
                {"name": name, "calls": data["total"], "success": data["success"]}
                for name, data in sorted_skills[:5]
            ]

        # Error warnings (patterns with >5 occurrences)
        for error_pattern, count in sorted(
            self.stats.error_patterns.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            if count >= 3:
                recommendations["error_warnings"].append({
                    "pattern": error_pattern,
                    "occurrences": count,
                })

        return recommendations

    def get_stats(self) -> dict[str, Any]:
        return self.stats.to_dict()
