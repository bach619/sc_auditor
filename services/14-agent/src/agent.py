"""Antonio — Main AI Agent with ReAct loop + Planning + Delegation.

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

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import structlog

from src.llm import CHAT_SYSTEM_PROMPT, VYPER_KNOWLEDGE, AgentReasoningClient, _unescape_text
from src.memory import AgentMemory
from src.models import (
    AgentSession,
    AgentState,
    AgentStep,
    ChatResponse,
    TaskType,
)
from src.planner import Planner
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
        self.planner = Planner()
        self.http_client = http_client
        self._sessions: dict[str, AgentSession] = {}
        # Chat sessions: persistent (file) + in-memory cache
        chat_path_env = os.environ.get("CHAT_SESSIONS_PATH", "")
        if chat_path_env:
            self._chat_storage_path = Path(chat_path_env)
        else:
            # Docker: use /data/agent/ volume; local dev: use ~/.sc_auditor/learning/
            docker_path = Path("/data/agent/chat_sessions.json")
            self._chat_storage_path = docker_path if docker_path.parent.exists() else Path.home() / ".sc_auditor" / "learning" / "chat_sessions.json"
        self._chat_storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._chat_sessions: dict[str, list[dict[str, str]]] = {}
        self._load_chat_sessions()

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

        # ── PLANNING PHASE ──
        # Before executing, create an execution plan
        try:
            available = list(self.registry._skills.keys()) if hasattr(self.registry, '_skills') else []
            plan = await self.planner.create_plan(
                goal=goal,
                input_data=input_data,
                available_skills=available,
            )
            self.memory.set_working("execution_plan", {
                "goal": plan.goal,
                "steps": [
                    {"step": s.step_number, "goal": s.goal, "skill": s.required_skill,
                     "depends_on": s.depends_on}
                    for s in plan.steps
                ],
            })
            log.info(
                "plan_created",
                session_id=session_id,
                steps=len(plan.steps),
                goal=goal[:100],
            )
        except Exception as exc:
            log.warning("plan_creation_failed", error=str(exc))
            # Non-blocking — continue with ReAct loop without plan

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
                cleaned_final = _unescape_text(final_answer or "Task completed.")
                step.status = AgentState.COMPLETED
                step.observation = cleaned_final
                session.steps.append(step)
                session.status = AgentState.COMPLETED
                session.output_data = {
                    "summary": cleaned_final,
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

    # ── Chat ───────────────────────────────────────────────

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
        max_steps: int = MAX_STEPS_DEFAULT,
    ) -> ChatResponse:
        """Handle a natural language chat message.

        Runs the ReAct loop with the CHAT system prompt so Antonio
        can understand user intent, call skills, and respond conversationally.
        Maintains message history per session in working memory.

        Args:
            message: User's natural language message.
            session_id: If provided, resume an existing chat session.
            max_steps: Maximum ReAct steps.

        Returns:
            ChatResponse with Antonio's natural language response.
        """
        # Create or resume session
        sid = session_id or f"chat-{uuid.uuid4().hex[:12]}"

        if session_id and session_id in self._chat_sessions:
            # Load existing history
            history = self._chat_sessions[session_id]
            self.memory.set_working("chat_history", history)
            goal = f"Continue conversation. User says: {message}"
        else:
            # New session
            history: list[dict[str, str]] = []
            self._chat_sessions[sid] = history
            self._save_chat_sessions()
            goal = message

        # Add user message to history
        history.append({"role": "user", "content": message})
        self._save_chat_sessions()
        self.memory.set_working("chat_history", history)

        # Init working memory for this chat turn
        self.memory.set_working("task_type", TaskType.CHAT.value)
        self.memory.set_working("goal", goal)
        self.memory.set_working("findings", [])
        self.memory.set_working("analyzed_findings", [])

        log.info(
            "chat_session",
            session_id=sid,
            message=message[:100],
            history_len=len(history),
        )

        # Build context: recent history + working memory
        context_parts = [f"User message: {message}"]
        if len(history) > 1:
            context_parts.append("\nRecent conversation:")
            for msg in history[-6:-1]:  # Last 5 exchanges (exclude current)
                role = "User" if msg["role"] == "user" else "Antonio"
                content_preview = msg["content"][:200]
                context_parts.append(f"  {role}: {content_preview}")
        context_parts.append(f"\nWorking memory contents:\n{self.memory.build_context()}")
        context = "\n".join(context_parts)

        # ReAct loop with chat prompt
        step_count = 0

        for step_num in range(1, max_steps + 1):
            step_count = step_num
            skills_desc = self.registry.format_for_prompt()

            # ── Build system prompt ──
            # Full prompt includes VYPER_KNOWLEDGE for broad question answering.
            # If step > 1 or we already tried MODE 1 and failed, skip knowledge
            # to keep prompt lean for skill-calling mode.
            if step_num == 1:
                full_prompt = CHAT_SYSTEM_PROMPT.replace("{s Skills}", skills_desc).replace("{vyper_knowledge}", VYPER_KNOWLEDGE)
                prompt_label = "full"
            else:
                # Subsequent steps: lean prompt without platform knowledge
                # (we already tried MODE 1 direct answer if appropriate)
                lean_prompt = CHAT_SYSTEM_PROMPT.replace("{s Skills}", skills_desc).replace("{vyper_knowledge}", "")
                full_prompt = lean_prompt
                prompt_label = "lean"

            # Log prompt size for debugging
            prompt_len = len(full_prompt)
            log.debug("chat_prompt_size", step=step_num, label=prompt_label, chars=prompt_len)

            # Use chat-specific system prompt
            decision = await self.llm.reason_custom(
                system_prompt=full_prompt,
                context=context,
                skills_desc="",  # Already in system prompt
            )

            action_name = decision.get("action", "FINAL_ANSWER")
            action_input = decision.get("action_input") or {}
            final_answer = decision.get("final_answer")
            thought = decision.get("thought", "")

            # FINAL ANSWER
            if action_name == "FINAL_ANSWER":
                # ── Detect error fallback from exhausted LLM retries ──
                # If reason_custom exhausted all retries, it returns a
                # fallback with "Error: Could not process request" prefix.
                is_error_fallback = (
                    final_answer
                    and final_answer.startswith("Error: Could not process request")
                )
                if is_error_fallback:
                    # ── Smart retry: full prompt may have timed out ──
                    # Try once more with a LEAN prompt (no VYPER_KNOWLEDGE)
                    if prompt_label == "full":
                        log.warning(
                            "chat_full_prompt_failed_retrying_lean",
                            session_id=sid,
                            error=final_answer[:100],
                        )
                        lean_prompt = CHAT_SYSTEM_PROMPT.replace("{s Skills}", skills_desc).replace("{vyper_knowledge}", "")
                        try:
                            decision = await self.llm.reason_custom(
                                system_prompt=lean_prompt,
                                context=context,
                                skills_desc="",
                            )
                            action_name = decision.get("action", "FINAL_ANSWER")
                            final_answer = decision.get("final_answer")
                            # If lean prompt succeeded, use its response
                            if action_name == "FINAL_ANSWER" and final_answer and not final_answer.startswith("Error: Could not process request"):
                                response_text = _unescape_text(final_answer)
                                history.append({"role": "assistant", "content": response_text})
                                self._chat_sessions[sid] = history
                                self._save_chat_sessions()
                                log.info("chat_completed_lean_fallback", session_id=sid, response_length=len(response_text))
                                return ChatResponse(
                                    session_id=sid,
                                    response=response_text,
                                    steps_taken=step_count,
                                    status=AgentState.COMPLETED,
                                )
                        except Exception:
                            pass  # Both attempts failed, fall through to friendly message

                    log.error(
                        "chat_llm_exhausted",
                        session_id=sid,
                        steps=step_count,
                        error=final_answer,
                    )
                    # Build graceful Indonesian response (or English for English users)
                    # Check if conversation is in Indonesian
                    is_indonesian = any(
                        word in message.lower()
                        for word in ("apa", "ini", "bagaimana", "saya", "kamu", "anda",
                                     "adalah", "yang", "dengan", "untuk", "tolong")
                    )
                    if is_indonesian:
                        friendly = (
                            "Maaf, saya sedang mengalami kendala teknis saat menghubungi "
                            "layanan AI. Beberapa penyebab umum:\n\n"
                            "1. **API key belum dikonfigurasi** — Buka Settings > AI Providers\n"
                            "2. **Provider sedang sibuk** — Coba lagi dalam beberapa detik\n"
                            "3. **Koneksi jaringan bermasalah** — Periksa koneksi internet\n\n"
                            "Silakan coba lagi, atau periksa konfigurasi AI Provider di Settings."
                        )
                    else:
                        friendly = (
                            "Sorry, I'm experiencing technical difficulties connecting to "
                            "the AI service. Common causes:\n\n"
                            "1. **API key not configured** — Check Settings > AI Providers\n"
                            "2. **Provider is busy** — Try again in a few seconds\n"
                            "3. **Network issues** — Check your internet connection\n\n"
                            "Please try again, or verify your AI Provider settings."
                        )
                    response_text = friendly
                else:
                    response_text = _unescape_text(final_answer or "Done.")
                # Add to history
                history.append({"role": "assistant", "content": response_text})
                self._chat_sessions[sid] = history
                self._save_chat_sessions()

                log.info(
                    "chat_completed",
                    session_id=sid,
                    steps=step_count,
                    response_length=len(response_text),
                )
                return ChatResponse(
                    session_id=sid,
                    response=response_text,
                    steps_taken=step_count,
                    status=AgentState.COMPLETED,
                )

            # Execute skill
            log.info(
                "chat_acting",
                session_id=sid,
                step=step_num,
                skill=action_name,
                thought=thought[:100],
            )

            result = await self.registry.execute(action_name, **action_input)

            # Update context with observation
            observation = self._format_observation(result)
            context += f"\n\nStep {step_num}: Called {action_name}\nObservation: {observation[:500]}"

            # Update working memory with findings if any
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

            if not result.success:
                log.warning(
                    "chat_step_failed",
                    session_id=sid,
                    step=step_num,
                    skill=action_name,
                    error=result.error,
                )

        # Max steps
        fallback = (
            "Maaf, saya butuh langkah lebih banyak untuk menyelesaikan ini. "
            "Bisa coba pertanyaan yang lebih spesifik?"
        )
        history.append({"role": "assistant", "content": fallback})
        self._chat_sessions[sid] = history
        self._save_chat_sessions()

        return ChatResponse(
            session_id=sid,
            response=fallback,
            steps_taken=step_count,
            status=AgentState.STOPPED,
            error=f"Reached maximum steps ({max_steps})",
        )

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
            TaskType.CHAT: "Chat with user — answer questions, run audits, provide info",
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

    # ── Chat Session Persistence ─────────────────────────────

    def _load_chat_sessions(self) -> None:
        """Load chat sessions from local JSON file into in-memory cache."""
        if self._chat_storage_path.exists():
            try:
                data: dict = json.loads(self._chat_storage_path.read_text())
                # Validate structure: {session_id: [{role, content}, ...]}
                if isinstance(data, dict):
                    for sid, msgs in data.items():
                        if isinstance(msgs, list) and all(
                            isinstance(m, dict) and "role" in m and "content" in m
                            for m in msgs
                        ):
                            self._chat_sessions[sid] = msgs
                    log.info(
                        "chat_sessions.loaded",
                        path=str(self._chat_storage_path),
                        count=len(self._chat_sessions),
                    )
                else:
                    log.warning("chat_sessions.invalid_format", path=str(self._chat_storage_path))
            except (json.JSONDecodeError, OSError) as e:
                log.warning("chat_sessions.load_failed", error=str(e))
        else:
            log.info("chat_sessions.no_file", path=str(self._chat_storage_path))

    def _save_chat_sessions(self) -> None:
        """Save all chat sessions from in-memory cache to local JSON file."""
        try:
            self._chat_storage_path.write_text(
                json.dumps(self._chat_sessions, indent=2, ensure_ascii=False)
            )
            log.debug("chat_sessions.saved", path=str(self._chat_storage_path))
        except OSError as e:
            log.error("chat_sessions.save_failed", error=str(e))

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

    def list_chat_sessions(self) -> list[dict[str, Any]]:
        """Return all chat sessions as a list of {id, messages, message_count}."""
        return [
            {
                "session_id": sid,
                "messages": msgs,
                "message_count": len(msgs),
            }
            for sid, msgs in self._chat_sessions.items()
        ]

    @property
    def active_sessions(self) -> int:
        return sum(
            1 for s in self._sessions.values()
            if s.status in (AgentState.THINKING, AgentState.ACTING, AgentState.OBSERVING)
        )


def _now() -> str:
    import datetime
    return datetime.datetime.now(datetime.UTC).isoformat()
