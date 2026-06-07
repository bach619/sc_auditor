"""Sub-Agent — specialized team member with limited skills and own ReAct loop.

Each sub-agent has:
- A specific role (Intel, Scanner, Analyst, Exploit, QA, Report)
- Access to only its allowed skills
- Its own memory (working + episodic)
- Its own ReAct loop for reasoning
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import httpx
import structlog

from src.llm import AgentReasoningClient
from src.memory import AgentMemory
from src.models import AgentRole, AgentState, AgentStep, SkillResult
from src.organization import AgentPersona, get_persona
from src.skills.registry import SkillRegistry

log = structlog.get_logger()

MAX_SUB_STEPS = 10
MAX_OBSERVATION_LENGTH = 2000


class SubAgent:
    """A specialized agent that is part of the audit team.

    Each SubAgent has a specific role, limited skills, and
    runs its own ReAct loop to complete delegated tasks.

    Attributes:
        role: Agent role (intel, scanner, analyst, etc.)
        persona: Persona definition (prompts, skills, title)
        registry: Skill registry with only allowed skills
        llm: LLM client for reasoning
        memory: Working + episodic memory
        http_client: HTTP client for skill calls
    """

    def __init__(
        self,
        role: AgentRole,
        llm: AgentReasoningClient,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.role = role
        self.persona: AgentPersona = get_persona(role)
        self.registry = SkillRegistry()
        self.llm = llm
        self.memory = AgentMemory()
        self.http_client = http_client
        self._skills_loaded = False
        log.info("sub_agent_created", role=role.value)

    def register_skill(self, skill: Any) -> None:
        """Register a skill into this sub-agent's limited registry."""
        self.registry.register(skill)
        self._skills_loaded = True

    async def execute_task(
        self,
        task: str,
        context: str = "",
        max_steps: int = MAX_SUB_STEPS,
    ) -> SubTaskResult:
        """Execute a delegated task using ReAct loop.

        Args:
            task: Description of what to do
            context: Context from previous steps
            max_steps: Maximum ReAct steps

        Returns:
            SubTaskResult with all steps and output
        """
        sub_id = f"sub-{self.role.value}-{uuid.uuid4().hex[:8]}"

        log.info(
            "sub_agent_task_started",
            role=self.role.value,
            task=task[:100],
            sub_id=sub_id,
        )

        # Reset memory for this task
        self.memory.clear_working()
        self.memory.set_working("task", task)
        self.memory.set_working("context", context)
        self.memory.set_working("results", [])

        steps: list[AgentStep] = []

        # ── Mini ReAct Loop ──
        for step_num in range(1, max_steps + 1):
            step = AgentStep(step_number=step_num, thought="", action="")

            context_str = self._build_context(context, steps)
            skills_desc = self.registry.format_for_prompt()
            system_prompt = self.persona.system_prompt.replace(
                "{f Skills}", skills_desc
            )

            # THINK
            log.info(
                "sub_agent_thinking",
                role=self.role.value,
                sub_id=sub_id,
                step=step_num,
            )

            decision = await self.llm.reason_custom(
                system_prompt=system_prompt,
                context=context_str,
                skills_desc="",  # Already embedded in system prompt
            )

            thought = decision.get("thought", "")
            action_name = decision.get("action") or "FINAL_ANSWER"
            action_input = decision.get("action_input") or {}
            final_answer = decision.get("final_answer")

            step.thought = thought
            step.action = action_name
            step.action_input = action_input

            # FINAL ANSWER?
            if action_name == "FINAL_ANSWER":
                step.status = AgentState.COMPLETED
                step.observation = final_answer or "Task completed."
                steps.append(step)

                log.info(
                    "sub_agent_task_completed",
                    role=self.role.value,
                    sub_id=sub_id,
                    steps=step_num,
                )

                return SubTaskResult(
                    role=self.role,
                    task=task,
                    status=AgentState.COMPLETED,
                    steps=steps,
                    output=self._synthesize_output(steps, final_answer or ""),
                    summary=final_answer or "Task completed.",
                )

            # ACT — is this a delegation action? (shouldn't happen, but handle)
            if action_name.startswith("delegate_"):
                step.status = AgentState.FAILED
                step.observation = "Sub-agents cannot delegate. Use skills directly."
                steps.append(step)
                continue

            # Execute skill
            step_start = time.monotonic()
            log.info(
                "sub_agent_acting",
                role=self.role.value,
                sub_id=sub_id,
                step=step_num,
                skill=action_name,
            )

            # Check if this skill is allowed
            if not self.registry.get(action_name):
                step.status = AgentState.FAILED
                step.observation = f"Skill '{action_name}' not available for {self.role.value}. Allowed: {', '.join(self.persona.allowed_skills)}"
                steps.append(step)
                continue

            result = await self.registry.execute(action_name, **action_input)
            step.duration_ms = (time.monotonic() - step_start) * 1000

            # OBSERVE
            observation = self._format_observation(result)
            step.observation = observation[:MAX_OBSERVATION_LENGTH]
            step.action_output = (
                result.output if result.success else {"error": result.error}
            )
            step.status = AgentState.COMPLETED if result.success else AgentState.FAILED
            steps.append(step)

            # Update memory
            self.memory.add_episode(
                f"step_{step_num}_{action_name}",
                {
                    "thought": thought[:200],
                    "action": action_name,
                    "success": result.success,
                    "summary": observation[:300],
                },
            )

            if result.success and isinstance(result.output, dict):
                results = self.memory.get_working("results", [])
                results.append({"action": action_name, "output": result.output})
                self.memory.set_working("results", results)

                for key in ("findings", "analyzed_findings", "summary", "report"):
                    if key in result.output:
                        self.memory.set_working(key, result.output[key])

            if not result.success:
                log.warning(
                    "sub_agent_step_failed",
                    role=self.role.value,
                    sub_id=sub_id,
                    step=step_num,
                    skill=action_name,
                    error=result.error,
                )

        # Max steps
        log.warning(
            "sub_agent_max_steps",
            role=self.role.value,
            sub_id=sub_id,
            max_steps=max_steps,
        )

        return SubTaskResult(
            role=self.role,
            task=task,
            status=AgentState.STOPPED,
            steps=steps,
            output=self._synthesize_output(steps, "Reached maximum steps."),
            summary="Reached maximum steps without completing task.",
        )

    # ── Helpers ─────────────────────────────────────────────

    def _build_context(self, task: str, steps: list[AgentStep]) -> str:
        """Build context string for this sub-agent's reasoning."""
        parts = [f"=== TASK ===\n{task}"]
        if steps:
            parts.append("\n=== PREVIOUS STEPS ===")
            for s in steps[-5:]:  # Last 5 steps only
                parts.append(
                    f"  Step {s.step_number}: {s.action} -> "
                    f"{'OK' if s.status == AgentState.COMPLETED else 'FAIL'}"
                )
        # Add working memory
        if self.memory.working:
            parts.append("\n=== WORKING MEMORY ===")
            for key, value in self.memory.working.items():
                val_str = str(value)[:300]
                parts.append(f"  {key}: {val_str}")
        return "\n".join(parts)

    def _format_observation(self, result: SkillResult) -> str:
        """Format skill result into readable observation."""
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
                elif isinstance(value, dict):
                    parts.append(f"{key}: {len(value)} fields")
                elif isinstance(value, bool):
                    parts.append(f"{key}: {'yes' if value else 'no'}")
                elif value is not None:
                    str_val = str(value)[:100]
                    parts.append(f"{key}: {str_val}")
            return " | ".join(parts) if parts else "Success."
        if isinstance(output, list):
            return f"List with {len(output)} item(s)."
        return str(output)[:MAX_OBSERVATION_LENGTH]

    def _synthesize_output(
        self, steps: list[AgentStep], final_summary: str
    ) -> dict[str, Any]:
        """Synthesize all steps into a structured output."""
        output: dict[str, Any] = {
            "summary": final_summary,
            "steps_count": len(steps),
            "successful_steps": sum(
                1 for s in steps if s.status == AgentState.COMPLETED
            ),
            "failed_steps": sum(1 for s in steps if s.status == AgentState.FAILED),
        }

        # Collect results from working memory
        results = self.memory.get_working("results", [])
        for r in results:
            if isinstance(r.get("output"), dict):
                output.update(r["output"])

        return output


class SubTaskResult:
    """Result from a sub-agent task execution."""

    def __init__(
        self,
        role: AgentRole,
        task: str,
        status: AgentState,
        steps: list[AgentStep],
        output: dict[str, Any],
        summary: str = "",
    ) -> None:
        self.role = role
        self.task = task
        self.status = status
        self.steps = steps
        self.output = output
        self.summary = summary
