"""Planner — creates execution plans before Antonio's ReAct loop.

Antonio uses this to:
1. Analyze the user's request
2. Break it into sub-tasks
3. Determine which skills to use
4. Create an ordered execution plan
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

log = structlog.get_logger()


@dataclass
class PlanStep:
    """Satu langkah dalam execution plan."""
    step_number: int
    goal: str
    required_skill: str  # skill name
    depends_on: list[int] = field(default_factory=list)
    priority: str = "normal"
    context_hint: str = ""


@dataclass
class ExecutionPlan:
    """Full execution plan for a user request."""
    goal: str
    steps: list[PlanStep]
    total_estimated_duration_ms: float = 0.0


class Planner:
    """Creates execution plans from user requests."""

    def __init__(self, llm_client: Any | None = None) -> None:
        self.llm = llm_client

    async def create_plan(
        self,
        goal: str,
        input_data: dict[str, Any],
        available_skills: list[str],
    ) -> ExecutionPlan:
        """Create an execution plan."""
        # Generate default plan based on goal keywords
        return self._default_plan(goal, input_data, available_skills)

    def _default_plan(
        self,
        goal: str,
        input_data: dict[str, Any],
        available_skills: list[str],
    ) -> ExecutionPlan:
        """Generate a default plan for smart contract audit tasks."""
        goal.lower()

        # Determine steps based on goal type
        steps = []

        # Always start with fetch if source isn't provided
        has_fetch_skill = any("fetch" in s for s in available_skills)
        if not input_data.get("source_code") and has_fetch_skill:
            steps.append(PlanStep(
                step_number=1,
                goal="Fetch source code and program information",
                required_skill="fetch_program" if "fetch_program" in available_skills else "fetch_source",
            ))

        # Scan if source is available
        has_source = bool(input_data.get("source_code")) or len(steps) > 0
        if has_source and "scan_contract" in available_skills:
            deps = [s.step_number for s in steps]
            steps.append(PlanStep(
                step_number=len(steps) + 1,
                goal="Run static analysis to find vulnerabilities",
                required_skill="scan_contract",
                depends_on=deps,
            ))

        # AI Analysis
        if "analyze_findings" in available_skills:
            deps = [s.step_number for s in steps]
            steps.append(PlanStep(
                step_number=len(steps) + 1,
                goal="Analyze findings with AI to classify TP/FP",
                required_skill="analyze_findings",
                depends_on=deps,
            ))

        # Classify
        if "classify_finding" in available_skills:
            deps = [s.step_number for s in steps]
            steps.append(PlanStep(
                step_number=len(steps) + 1,
                goal="Classify and validate all findings",
                required_skill="classify_finding",
                depends_on=deps,
            ))

        # Exploit
        if "exploit_test" in available_skills:
            deps = [s.step_number for s in steps]
            steps.append(PlanStep(
                step_number=len(steps) + 1,
                goal="Generate and test proof-of-concept exploits for critical findings",
                required_skill="exploit_test",
                depends_on=deps,
            ))

        # Report
        if "generate_report" in available_skills:
            deps = [s.step_number for s in steps]
            steps.append(PlanStep(
                step_number=len(steps) + 1,
                goal="Generate comprehensive audit report",
                required_skill="generate_report",
                depends_on=deps,
            ))

        # Notify
        if "notify" in available_skills:
            deps = [s.step_number for s in steps]
            steps.append(PlanStep(
                step_number=len(steps) + 1,
                goal="Send notifications about completed audit",
                required_skill="notify",
                depends_on=deps,
            ))

        return ExecutionPlan(
            goal=goal,
            steps=steps,
            total_estimated_duration_ms=len(steps) * 60_000,
        )
