"""Lead Auditor — team manager with planning + delegation loop.

The Lead Auditor:
1. Plans the audit strategy based on the request
2. Delegates tasks to specialized sub-agents (Intel, Scanner, etc.)
3. Reviews results from each sub-agent
4. Decides next steps adaptively based on findings
5. Synthesizes the final audit report
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import structlog

from src.llm import AgentReasoningClient
from src.memory import AgentMemory
from src.models import (
    AgentRole,
    AgentState,
    AgentStep,
    SubAgentState,
    TeamSession,
    to_serializable,
)
from src.organization import (
    delegation_skills_for_prompt,
    get_persona,
    team_descriptions_for_prompt,
)
from src.skills.registry import SkillRegistry
from src.sub_agent import SubAgent

log = structlog.get_logger()

MAX_DELEGATIONS = 15
MAX_DELEGATION_OBSERVATION = 2500


class LeadAuditor:
    """Lead Auditor — manages team of sub-agents for audit tasks.

    Attributes:
        llm: LLM client for reasoning
        memory: Working + episodic memory for team context
        http_client: HTTP client for sub-agent skills
        sub_agents: Registry of available sub-agents by role
        _sessions: Active team sessions
    """

    def __init__(
        self,
        llm: AgentReasoningClient,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.llm = llm
        self.memory = AgentMemory()
        self.http_client = http_client
        self.sub_agents: dict[AgentRole, SubAgent] = {}
        self._sessions: dict[str, TeamSession] = {}
        self._global_registry: SkillRegistry | None = None

        # ── Session persistence ──
        self._session_db_path = Path("/data/agent/sessions.db")
        self._session_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._session_conn = sqlite3.connect(str(self._session_db_path))
        self._session_conn.execute("PRAGMA journal_mode=WAL")
        self._session_conn.execute("PRAGMA synchronous=NORMAL")
        self._init_session_table()
        self._load_persisted_sessions()

        log.info("lead_auditor_created")

    def set_global_registry(self, registry: SkillRegistry) -> None:
        """Set the global skill registry for sub-agent skill registration."""
        self._global_registry = registry

    def register_sub_agent(self, role: AgentRole) -> SubAgent:
        """Create and register a sub-agent for a given role.

        Registers only the skills allowed for that role from the global registry.
        """
        if role == AgentRole.LEAD_AUDITOR:
            raise ValueError("Cannot register Lead Auditor as sub-agent")

        agent = SubAgent(role=role, llm=self.llm, http_client=self.http_client)

        # Register allowed skills from global registry
        if self._global_registry:
            persona = get_persona(role)
            for skill_name in persona.allowed_skills:
                skill = self._global_registry.get(skill_name)
                if skill:
                    agent.register_skill(skill)
                    log.info(
                        "sub_agent_skill_registered",
                        role=role.value,
                        skill=skill_name,
                    )

        self.sub_agents[role] = agent
        log.info("sub_agent_registered", role=role.value)
        return agent

    def get_sub_agent(self, role: AgentRole) -> SubAgent | None:
        """Get a registered sub-agent by role."""
        return self.sub_agents.get(role)

    # ── Public API ─────────────────────────────────────────

    def create_session(
        self,
        task_type: str,
        input_data: dict[str, Any],
        goal: str,
    ) -> tuple[str, TeamSession]:
        """Create a new team session and return immediately.

        Does NOT run the audit — call run_session() to execute.

        Returns:
            Tuple of (session_id, TeamSession)
        """
        session_id = f"team-{uuid.uuid4().hex[:12]}"

        session = TeamSession(
            team_session_id=session_id,
            task_type=task_type,
            goal=goal,
            input_data=input_data,
        )
        self._sessions[session_id] = session
        self._persist_session(session)

        log.info(
            "team_audit_created",
            session_id=session_id,
            task_type=task_type,
            goal=goal[:100] if goal else "auto",
        )

        return session_id, session

    async def run_session(
        self,
        session_id: str,
        max_delegations: int = MAX_DELEGATIONS,
    ) -> TeamSession:
        """Execute a previously created team session.

        Args:
            session_id: The session ID from create_session()
            max_delegations: Max delegation cycles

        Returns:
            TeamSession with all delegation steps and results
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        goal = session.goal
        input_data = session.input_data
        task_type = session.task_type

        log.info(
            "team_audit_started",
            session_id=session_id,
            task_type=task_type,
            goal=goal[:100] if goal else "auto",
        )

        # Init memory
        self.memory.clear_working()
        self.memory.set_working("task_type", task_type)
        self.memory.set_working("goal", goal)
        self.memory.set_working("input_data", input_data)
        self.memory.set_working("all_findings", [])
        self.memory.set_working("analyzed_findings", [])
        self.memory.set_working("reports", [])
        self.memory.set_working("exploit_results", [])

        # ── Lead Auditor Delegation Loop ──
        for delegation_num in range(1, max_delegations + 1):
            session.status = AgentState.THINKING
            session.updated_at = _now()

            step = AgentStep(
                step_number=delegation_num, thought="", action=""
            )

            # Build context
            context = self._build_lead_context(session)
            delegation_skills = delegation_skills_for_prompt()
            team_desc = team_descriptions_for_prompt()
            lead_prompt = get_persona(AgentRole.LEAD_AUDITOR).system_prompt.format(
                team_size=len(self.sub_agents),
                team_descriptions=team_desc,
                delegation_skills=delegation_skills,
            )

            log.info(
                "lead_auditor_planning",
                session_id=session_id,
                delegation=delegation_num,
            )

            decision = await self.llm.reason_custom(
                system_prompt=lead_prompt,
                context=context,
                skills_desc="",
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
                step.observation = final_answer or "Audit completed."
                session.lead_steps.append(step)
                session.status = AgentState.COMPLETED
                session.output_data = self._synthesize_final_output(
                    final_answer or ""
                )
                session.updated_at = _now()
                self._persist_session(session)  # persist terminal state

                log.info(
                    "team_audit_completed",
                    session_id=session_id,
                    delegations=delegation_num,
                )
                return session

            # DELEGATE to sub-agent
            if action_name.startswith("delegate_"):
                role_str = action_name.replace("delegate_", "")
                try:
                    target_role = AgentRole(role_str)
                except ValueError:
                    step.status = AgentState.FAILED
                    step.observation = f"Unknown role: {role_str}"
                    session.lead_steps.append(step)
                    session.updated_at = _now()
                    continue

                # Check sub-agent exists
                sub = self.sub_agents.get(target_role)
                if sub is None:
                    step.status = AgentState.FAILED
                    step.observation = (
                        f"Sub-agent '{role_str}' not registered. "
                        f"Available: {', '.join(r.value for r in self.sub_agents)}"
                    )
                    session.lead_steps.append(step)
                    session.updated_at = _now()
                    continue

                task = action_input.get("task", "")
                if not task:
                    step.status = AgentState.FAILED
                    step.observation = "No task description provided."
                    session.lead_steps.append(step)
                    session.updated_at = _now()
                    continue

                # EXECUTE sub-agent
                session.status = AgentState.ACTING
                step_start = time.monotonic()

                # Create context from previous delegation results
                prev_context = self._build_delegation_context(session)

                # Track sub-agent state
                sub_state = SubAgentState(
                    role=target_role,
                    status=AgentState.PENDING,
                    task=task,
                )
                session.sub_agents[target_role.value] = sub_state

                log.info(
                    "lead_auditor_delegating",
                    session_id=session_id,
                    delegation=delegation_num,
                    role=target_role.value,
                    task=task[:100],
                )

                try:
                    result = await sub.execute_task(
                        task=task,
                        context=prev_context,
                    )

                    step.duration_ms = (
                        time.monotonic() - step_start
                    ) * 1000

                    # Update sub-agent state in session
                    sub_state.status = result.status
                    sub_state.output = result.output
                    sub_state.summary = result.summary
                    sub_state.steps = result.steps

                    # Format observation
                    observation = self._format_delegation_result(result)
                    step.observation = observation[:MAX_DELEGATION_OBSERVATION]
                    step.action_output = result.output
                    step.status = AgentState.COMPLETED

                    # Merge findings into memory
                    if isinstance(result.output, dict):
                        for key in (
                            "findings",
                            "analyzed_findings",
                            "critical_findings",
                            "report",
                            "summary",
                        ):
                            if key in result.output:
                                existing = self.memory.get_working(
                                    f"all_{key}",
                                    [],
                                ) if key != "summary" else ""
                                if isinstance(existing, list):
                                    vals = result.output[key]
                                    if isinstance(vals, list):
                                        existing.extend(vals)
                                    else:
                                        existing.append(vals)
                                    self.memory.set_working(
                                        f"all_{key}", existing
                                    )
                                else:
                                    self.memory.set_working(
                                        f"last_{key}",
                                        result.output[key],
                                    )

                    # Record which roles completed
                    completed = self.memory.get_working("completed_roles", [])
                    if target_role.value not in completed:
                        completed.append(target_role.value)
                        self.memory.set_working("completed_roles", completed)

                except Exception as exc:
                    step.duration_ms = (
                        time.monotonic() - step_start
                    ) * 1000
                    step.status = AgentState.FAILED
                    step.observation = f"Sub-agent execution failed: {exc}"
                    step.action_output = {"error": str(exc)}
                    sub_state.status = AgentState.FAILED
                    sub_state.output = {"error": str(exc)}

                    log.error(
                        "lead_auditor_delegation_failed",
                        session_id=session_id,
                        role=target_role.value,
                        error=str(exc),
                    )

                session.lead_steps.append(step)
                session.updated_at = _now()

                # If sub-agent failed 3 times in a row, wrap up
                recent_failures = sum(
                    1
                    for s in session.lead_steps[-5:]
                    if s.status == AgentState.FAILED
                )
                if recent_failures >= 3:
                    log.warning(
                        "team_audit_too_many_failures",
                        session_id=session_id,
                        recent_failures=recent_failures,
                    )
                    session.status = AgentState.STOPPED
                    session.error = "Too many delegation failures"
                    session.output_data = self._synthesize_final_output(
                        "Audit stopped due to repeated failures."
                    )
                    session.updated_at = _now()
                    self._persist_session(session)  # persist terminal state
                    return session

        # Max delegations reached
        session.status = AgentState.STOPPED
        session.error = f"Reached maximum delegations ({max_delegations})"
        session.updated_at = _now()
        self._persist_session(session)  # persist terminal state

        log.warning(
            "team_audit_max_delegations",
            session_id=session_id,
            max_delegations=max_delegations,
        )

        return session

    # ── Context Builders ────────────────────────────────────

    def _build_lead_context(self, session: TeamSession) -> str:
        """Build context for Lead Auditor's reasoning."""
        parts = [
            "=== AUDIT REQUEST ===",
            f"Type: {session.task_type}",
            f"Goal: {session.goal}",
            f"Input: {_truncate_dict(session.input_data)}",
        ]

        completed = self.memory.get_working("completed_roles", [])
        if completed:
            parts.append("\n=== COMPLETED DELEGATIONS ===")
            for role in completed:
                sub_state = session.sub_agents.get(role)
                if sub_state:
                    status = "✓" if sub_state.status == AgentState.COMPLETED else "✗"
                    parts.append(f"  {status} {role}: {_truncate_str(sub_state.summary, 200)}")

        all_findings = self.memory.get_working("all_findings", [])
        if all_findings:
            parts.append(f"\n=== FINDINGS SO FAR ({len(all_findings)} total) ===")
            for i, f in enumerate(all_findings[:5]):
                title = f.get("title", f.get("description", "?"))[:80]
                sev = f.get("severity", "?")
                parts.append(f"  {i+1}. [{sev}] {title}")
            if len(all_findings) > 5:
                parts.append(f"  ... and {len(all_findings) - 5} more")

        analyzed = self.memory.get_working("all_analyzed_findings", [])
        if analyzed:
            parts.append(f"\n=== ANALYZED FINDINGS ({len(analyzed)} total) ===")
            for i, f in enumerate(analyzed[:5]):
                title = f.get("title", f.get("finding", "?"))[:80]
                is_tp = f.get("is_true_positive", f.get("is_tp", "?"))
                parts.append(f"  {i+1}. TP={is_tp} | {title}")

        last_report = self.memory.get_working("last_report")
        if last_report:
            parts.append("\n=== LAST REPORT ===")
            parts.append(f"  {_truncate_str(str(last_report), 200)}")

        return "\n".join(parts)

    def _build_delegation_context(self, session: TeamSession) -> str:
        """Build context to pass to sub-agent from previous steps."""
        parts = []
        completed = self.memory.get_working("completed_roles", [])
        if completed:
            parts.append("=== PREVIOUS RESULTS ===")
            for role in completed:
                sub_state = session.sub_agents.get(role)
                if sub_state and sub_state.output:
                    parts.append(f"[{role}] {_truncate_str(sub_state.summary, 300)}")

        all_findings = self.memory.get_working("all_findings", [])
        if all_findings:
            parts.append(f"\n=== ACCUMULATED FINDINGS ({len(all_findings)}) ===")
            parts.append(f"{to_serializable(all_findings[-10:])}")  # Last 10

        analyzed = self.memory.get_working("all_analyzed_findings", [])
        if analyzed:
            parts.append(f"\n=== ANALYZED ({len(analyzed)} items) ===")
            parts.append(f"{to_serializable(analyzed[-5:])}")

        input_data = self.memory.get_working("input_data", {})
        parts.append("\n=== INPUT ===")
        parts.append(f"{to_serializable(input_data)}")

        return "\n".join(parts)

    def _format_delegation_result(self, result: Any) -> str:
        """Format delegation result into readable observation."""
        lines = [
            f"Role: {result.role.value}",
            f"Status: {result.status.value}",
            f"Steps: {len(result.steps)}",
            f"Summary: {_truncate_str(result.summary, 500)}",
        ]

        # Add key data points
        output = result.output
        if isinstance(output, dict):
            for key in ("findings", "analyzed_findings", "report", "critical_findings"):
                val = output.get(key)
                if val:
                    count = len(val) if isinstance(val, list) else 1
                    lines.append(f"{key}: {count} item(s)")

        return " | ".join(lines)

    def _synthesize_final_output(self, final_summary: str) -> dict[str, Any]:
        """Synthesize all team results into final output."""
        return {
            "summary": final_summary,
            "all_findings": self.memory.get_working("all_findings", []),
            "analyzed_findings": self.memory.get_working("all_analyzed_findings", []),
            "critical_findings": self.memory.get_working(
                "all_critical_findings", []
            ),
            "report": self.memory.get_working("last_report"),
            "exploit_results": self.memory.get_working("all_exploit_results", []),
            "completed_roles": self.memory.get_working("completed_roles", []),
        }

    # ── Session Management ─────────────────────────────────

    def _init_session_table(self) -> None:
        """Ensure the sessions table exists."""
        self._session_conn.executescript("""
            CREATE TABLE IF NOT EXISTS agent_sessions (
                session_id      TEXT PRIMARY KEY,
                status          TEXT DEFAULT 'active',
                task_type       TEXT,
                goal            TEXT DEFAULT '',
                context_json    TEXT DEFAULT '{}',
                started_at      TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at    TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_status ON agent_sessions(status);
            CREATE INDEX IF NOT EXISTS idx_sessions_started ON agent_sessions(started_at);
        """)
        self._session_conn.commit()

    def _load_persisted_sessions(self) -> None:
        """Load completed/failed sessions from SQLite into memory."""
        try:
            rows = self._session_conn.execute(
                "SELECT session_id, status, task_type, goal, context_json, started_at, completed_at "
                "FROM agent_sessions ORDER BY started_at DESC"
            ).fetchall()
            loaded = 0
            for row in rows:
                sid = row["session_id"]
                if sid not in self._sessions:
                    ctx = json.loads(row["context_json"] or "{}")
                    self._sessions[sid] = TeamSession(
                        team_session_id=sid,
                        task_type=row["task_type"] or "",
                        goal=row["goal"] or "",
                        input_data=ctx.get("input_data", {}),
                        status=AgentState(row["status"]) if row["status"] else AgentState.COMPLETED,
                        created_at=row["started_at"] or "",
                        error=ctx.get("error"),
                    )
                    loaded += 1
            if loaded > 0:
                log.info("lead_auditor_sessions_loaded", count=loaded)
        except Exception:
            pass  # Fresh DB or corrupt — no problem

    def _persist_session(self, session: TeamSession) -> None:
        """Persist a team session to SQLite (upsert)."""
        try:
            ctx = json.dumps({
                "input_data": session.input_data,
                "error": session.error,
                "output_summary": str(session.output_data)[:500] if session.output_data else "",
                "sub_agents": list(session.sub_agents.keys()),
            })
            self._session_conn.execute(
                """INSERT OR REPLACE INTO agent_sessions
                   (session_id, status, task_type, goal, context_json, started_at, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    session.team_session_id,
                    session.status.value,
                    session.task_type,
                    session.goal[:200],
                    ctx,
                    session.created_at,
                    session.updated_at if session.status in (
                        AgentState.COMPLETED, AgentState.FAILED, AgentState.STOPPED
                    ) else None,
                ),
            )
            self._session_conn.commit()
        except Exception as exc:
            log.warning("session_persist_failed", session_id=session.team_session_id, error=str(exc))

    def get_session(self, session_id: str) -> TeamSession | None:
        return self._sessions.get(session_id)

    def list_sessions(
        self, limit: int = 20, status: str | None = None
    ) -> list[TeamSession]:
        # ── Merge in-memory sessions with persisted sessions ──
        # In-memory sessions take precedence (more recent state)
        merged: dict[str, TeamSession] = {}

        # Load from persistent DB
        try:
            query = "SELECT session_id, status, task_type, goal, context_json, started_at, completed_at FROM agent_sessions"
            params: list[Any] = []
            if status:
                query += " WHERE status = ?"
                params.append(status)
            query += " ORDER BY started_at DESC LIMIT ?"
            params.append(limit)

            rows = self._session_conn.execute(query, params).fetchall()
            for row in rows:
                sid = row["session_id"]
                ctx = json.loads(row["context_json"] or "{}")
                merged[sid] = TeamSession(
                    team_session_id=sid,
                    task_type=row["task_type"] or "",
                    goal=row["goal"] or "",
                    input_data=ctx.get("input_data", {}),
                    status=AgentState(row["status"]) if row["status"] else AgentState.COMPLETED,
                    created_at=row["started_at"] or "",
                    error=ctx.get("error"),
                )
        except Exception:
            pass  # Fall through to in-memory only

        # In-memory sessions override (more up-to-date)
        for sid, s in self._sessions.items():
            merged[sid] = s

        sessions = sorted(
            merged.values(),
            key=lambda s: s.created_at,
            reverse=True,
        )
        return sessions[:limit]

    @property
    def active_sessions(self) -> int:
        return sum(
            1
            for s in self._sessions.values()
            if s.status
            in (AgentState.THINKING, AgentState.ACTING, AgentState.OBSERVING)
        )


# ── Helpers ──────────────────────────────────────────────────


def _now() -> str:
    import datetime
    return datetime.datetime.now(datetime.UTC).isoformat()


def _truncate_str(s: str, max_len: int = 200) -> str:
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def _truncate_dict(d: dict[str, Any], max_len: int = 200) -> str:
    parts = []
    for k, v in d.items():
        s = str(v)
        if len(s) > max_len:
            s = s[:max_len] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)
