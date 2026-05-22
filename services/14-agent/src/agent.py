"""ReAct Agent Loop — the brain of Vyper Agent.

Implements the Reasoning + Acting (ReAct) pattern:
1. THINK: Agent reasons about current state and decides next action
2. ACT: Agent calls a skill with parameters
3. OBSERVE: Agent processes the skill result
4. REPEAT until task is complete

Memory integration:
- VectorStore: Search past sessions for similar patterns
- EpisodicStore: Record every step chronologically
- GraphMemory: Track relationships between contracts, vulns, exploits
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import httpx
import structlog

from src.llm import AgentReasoningClient
from src.memory import AgentMemory
from src.models import (
    AgentResponse,
    AgentSession,
    AgentState,
    AgentStep,
    TaskType,
)
from src.skills.registry import SkillRegistry

log = structlog.get_logger()

MAX_STEPS_DEFAULT = 25
MAX_OBSERVATION_LENGTH = 2000


class AgentLoop:
    """ReAct Agent Loop — orchestrates thinking, acting, and observing.

    Attributes:
        registry: Skill registry with all available skills
        llm: LLM client for reasoning
        memory: Agent memory system (working + vector + episodic + graph)
        http_client: HTTP client for service calls
    """

    def __init__(
        self,
        registry: SkillRegistry,
        llm: AgentReasoningClient,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.registry = registry
        self.llm = llm
        self.memory = AgentMemory()
        self.http_client = http_client
        self._sessions: dict[str, AgentSession] = {}

    # ── Public API ─────────────────────────────────────────

    async def run(
        self,
        task_type: TaskType,
        input_data: dict[str, Any],
        goal: str = "",
        max_steps: int = MAX_STEPS_DEFAULT,
    ) -> AgentSession:
        """Run agent task dengan ReAct loop.

        Args:
            task_type: Jenis task (full_audit, source_scan, dll)
            input_data: Input data untuk task
            goal: Natural language description of the goal
            max_steps: Maximum ReAct steps

        Returns:
            AgentSession with all steps and output
        """
        session_id = f"agent-{uuid.uuid4().hex[:12]}"
        goal = goal or self._default_goal(task_type, input_data)

        session = AgentSession(
            session_id=session_id,
            task_type=task_type,
            goal=goal,
            input_data=input_data,
        )
        self._sessions[session_id] = session

        log.info(
            "agent_session_started",
            session_id=session_id,
            task_type=task_type.value,
            goal=goal[:100],
        )

        # Init working memory dengan input
        self.memory.clear_working()
        self.memory.set_working("task_type", task_type.value)
        self.memory.set_working("goal", goal)
        self.memory.set_working("input_data", input_data)
        self.memory.set_working("findings", [])
        self.memory.set_working("analyzed_findings", [])
        self.memory.set_working("reports", [])

        # Vector store: cari pengalaman serupa dari session sebelumnya
        try:
            similar_past = await self.memory.vector.retrieve(
                f"{task_type.value}: {goal[:100]}",
                limit=3,
            )
            if similar_past:
                self.memory.set_working(
                    "similar_past_sessions", similar_past
                )
                log.info(
                    "found_similar_past",
                    count=len(similar_past),
                )
        except Exception:
            pass  # non-blocking

        # Graph memory: catat session node
        try:
            session_node_id = uuid.uuid4().hex[:8]
            self.memory.graph.add_node(
                node_id=session_node_id,
                node_type="session",
                properties={
                    "label": f"Session {session_id}: {goal[:50]}",
                    "session_id": session_id,
                    "task_type": task_type.value,
                    "goal": goal[:200],
                },
            )
            self.memory.set_working("_graph_session_node", session_node_id)
        except Exception:
            pass

        # Episodic store: record session start
        try:
            await self.memory.episodic_store.store_text(
                "session_started",
                {"session_id": session_id, "task_type": task_type.value, "goal": goal[:200]},
                metadata={"session_id": session_id, "event": "start"},
            )
        except Exception:
            pass

        # ReAct loop
        for step_num in range(1, max_steps + 1):
            session.status = AgentState.THINKING
            session.updated_at = _now()

            # ── THINK ──
            step = AgentStep(step_number=step_num, thought="", action="")

            context = self.memory.build_context()
            skills_desc = self.registry.format_for_prompt()

            log.info("agent_thinking", session_id=session_id, step=step_num)

            decision = await self.llm.reason(
                context=context,
                skills_desc=skills_desc,
            )

            thought = decision.get("thought", "")
            action_name = decision.get("action", "FINAL_ANSWER")
            action_input = decision.get("action_input") or {}
            final_answer = decision.get("final_answer")

            step.thought = thought
            step.action = action_name
            step.action_input = action_input

            # ── FINAL ANSWER? ──
            if action_name == "FINAL_ANSWER":
                step.status = AgentState.COMPLETED
                step.observation = final_answer or "Task completed."
                session.steps.append(step)
                session.status = AgentState.COMPLETED
                session.output_data = {
                    "summary": final_answer or "Audit completed successfully.",
                    "findings": self.memory.get_working("analyzed_findings", []),
                    "reports": self.memory.get_working("reports", []),
                }
                session.updated_at = _now()

                # Catat ke episodic memory
                self.memory.add_episode(
                    "session_completed",
                    {"steps": step_num, "output": session.output_data},
                )

                # Vector store: simpan session summary
                try:
                    summary_text = (
                        f"Session {session_id}: {goal[:100]} | "
                        f"Findings: {len(session.output_data.get('findings', []))} | "
                        f"Steps: {step_num}"
                    )
                    await self.memory.vector.store_text(
                        f"session_{session_id}",
                        summary_text,
                        metadata={
                            "session_id": session_id,
                            "task_type": task_type.value,
                            "steps": step_num,
                            "success": True,
                        },
                    )
                except Exception:
                    pass

                # Graph memory: link session → findings
                try:
                    for finding in session.output_data.get("findings", [])[:5]:
                        finding_label = (
                            finding.get("title") or finding.get("name", "unknown")
                        )[:100]
                        finding_node_id = uuid.uuid4().hex[:8]
                        self.memory.graph.add_node(
                            node_id=finding_node_id,
                            node_type="finding",
                            properties={"label": f"Finding: {finding_label}", **finding},
                        )
                        graph_node = self.memory.get_working("_graph_session_node")
                        if graph_node:
                            self.memory.graph.add_edge(
                                from_id=graph_node,
                                to_id=finding_node_id,
                                relation="found",
                                properties={"weight": 1.0},
                            )
                except Exception:
                    pass

                # Reflection (async — tidak blocking)
                try:
                    reflection = await self.llm.reflect(
                        f"Audit session {session_id}: {step_num} steps. "
                        f"Goal: {goal[:100]}"
                    )
                    self.memory.set_semantic(
                        f"reflection_{session_id}", reflection
                    )
                except Exception:
                    pass

                log.info(
                    "agent_session_completed",
                    session_id=session_id,
                    steps=step_num,
                )
                return session

            # ── ACT: Execute skill ──
            session.status = AgentState.ACTING
            step_start = time.monotonic()

            log.info(
                "agent_acting",
                session_id=session_id,
                step=step_num,
                skill=action_name,
            )

            result = await self.registry.execute(action_name, **action_input)

            step.duration_ms = (time.monotonic() - step_start) * 1000

            # ── OBSERVE ──
            session.status = AgentState.OBSERVING

            observation = self._format_observation(result)
            step.observation = observation[:MAX_OBSERVATION_LENGTH]
            step.action_output = result.output if result.success else {"error": result.error}
            step.status = AgentState.COMPLETED if result.success else AgentState.FAILED

            session.steps.append(step)

            # Simpan hasil ke memory
            self.memory.add_episode(
                f"step_{step_num}_{action_name}",
                {
                    "thought": thought[:200],
                    "action": action_name,
                    "success": result.success,
                    "summary": observation[:300],
                },
            )

            # Episodic store: record each step
            try:
                await self.memory.episodic_store.store_text(
                    f"step_{step_num}_{action_name}",
                    {
                        "thought": thought[:200],
                        "action": action_name,
                        "success": result.success,
                        "duration_ms": step.duration_ms,
                    },
                    metadata={
                        "session_id": session_id,
                        "step": step_num,
                        "skill": action_name,
                        "success": result.success,
                    },
                )
            except Exception:
                pass

            # Update working memory dengan findings jika ada
            if result.success and isinstance(result.output, dict):
                if "findings" in result.output:
                    existing = self.memory.get_working("findings", [])
                    existing.extend(result.output["findings"])
                    self.memory.set_working("findings", existing)

                if "analyzed_findings" in result.output:
                    self.memory.set_working(
                        "analyzed_findings",
                        result.output["analyzed_findings"],
                    )
                    self.memory.set_working(
                        "critical_findings",
                        result.output.get("critical_findings", []),
                    )

                if "summary" in result.output:
                    self.memory.set_working(
                        f"summary_{action_name}",
                        result.output["summary"],
                    )

            session.updated_at = _now()

            if not result.success:
                log.warning(
                    "agent_step_failed",
                    session_id=session_id,
                    step=step_num,
                    skill=action_name,
                    error=result.error,
                )

        # Max steps reached
        session.status = AgentState.STOPPED
        session.error = f"Reached maximum steps ({max_steps})"
        session.updated_at = _now()

        log.warning(
            "agent_session_max_steps",
            session_id=session_id,
            max_steps=max_steps,
        )

        return session

    # ── Helpers ────────────────────────────────────────────

    def _format_observation(self, result: Any) -> str:
        """Format skill result into readable observation string."""
        if not result.success:
            return f"Error: {result.error}"

        output = result.output
        if output is None:
            return "No output."

        if isinstance(output, str):
            return output

        if isinstance(output, dict):
            parts = []
            for key, value in output.items():
                if key.startswith("_"):
                    continue
                if isinstance(value, list):
                    parts.append(f"{key}: {len(value)} item(s)")
                    if value and isinstance(value[0], dict):
                        first = value[0]
                        summary = ", ".join(
                            f"{k}={v}" for k, v in list(first.items())[:4]
                        )
                        parts.append(f"  first: {summary}")
                elif isinstance(value, dict):
                    count = len(value)
                    parts.append(f"{key}: {count} field(s)")
                elif isinstance(value, bool):
                    parts.append(f"{key}: {'yes' if value else 'no'}")
                elif value is not None:
                    str_val = str(value)
                    if len(str_val) > 100:
                        str_val = str_val[:100] + "..."
                    parts.append(f"{key}: {str_val}")
            return " | ".join(parts) if parts else "Success."

        if isinstance(output, list):
            return f"List with {len(output)} item(s)."

        return str(output)[:MAX_OBSERVATION_LENGTH]

    def _default_goal(
        self, task_type: TaskType, input_data: dict[str, Any]
    ) -> str:
        """Generate default goal description based on task type."""
        goals = {
            TaskType.FULL_AUDIT: (
                "Complete smart contract audit: fetch source → scan for vulnerabilities "
                "→ analyze findings with AI → classify TP/FP → exploit critical bugs "
                "→ generate report"
            ),
            TaskType.SOURCE_SCAN: (
                "Fetch source code and run static analysis tools"
            ),
            TaskType.FINDING_ANALYSIS: (
                "Analyze scanner findings with AI to determine TP/FP"
            ),
            TaskType.EXPLOIT_TEST: (
                "Generate and execute proof-of-concept exploit"
            ),
            TaskType.REPORT_GENERATE: (
                "Generate audit report in Immunefi-ready format"
            ),
            TaskType.PROGRAM_SYNC: (
                "Sync Immunefi programs and find high-value targets"
            ),
        }
        return goals.get(task_type, "Execute audit task")

    # ── Session Management ─────────────────────────────────

    def get_session(self, session_id: str) -> AgentSession | None:
        return self._sessions.get(session_id)

    def list_sessions(
        self, limit: int = 20, status: str | None = None
    ) -> list[AgentSession]:
        sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.created_at,
            reverse=True,
        )
        if status:
            sessions = [s for s in sessions if s.status.value == status]
        return sessions[:limit]

    @property
    def active_sessions(self) -> int:
        return sum(
            1 for s in self._sessions.values()
            if s.status in (AgentState.THINKING, AgentState.ACTING, AgentState.OBSERVING)
        )


def _now() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
