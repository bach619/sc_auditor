"""LLM Client for Agent Reasoning — calls OpenAI/Anthropic for Think step."""

from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

log = structlog.get_logger()

OPENAI_BASE_URL = "https://api.openai.com/v1"
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"
DEFAULT_TIMEOUT = 30.0

# ── ReAct System Prompt ────────────────────────────────────

REACT_SYSTEM_PROMPT = """You are Vyper, an expert smart contract security AI agent.

Your goal is to audit smart contracts and find security vulnerabilities.
You have access to a set of SKILLS that you can call.

## How to Think (ReAct Pattern)

For each step, follow this format:

THOUGHT: What is the current situation? What should I do next?
ACTION: skill_name
ACTION_INPUT: {"param": "value"}
OBSERVATION: (result from skill)

## Available Skills

{s Skills}

## Rules

1. Always think step by step before acting
2. Choose ONE skill per step
3. After calling a skill, wait for the observation
4. If a skill fails, try an alternative approach
5. When the task is complete, respond with FINAL_ANSWER
6. Be specific about what you find — contract names, function names, line numbers

## Output Format

You MUST respond with valid JSON:
{{
  "thought": "your reasoning here",
  "action": "skill_name or FINAL_ANSWER",
  "action_input": {{ "param": "value" or null }},
  "final_answer": "final summary or null"
}}

For the final step, set action to "FINAL_ANSWER" and provide summary in final_answer.
"""


# ── Chat System Prompt ──────────────────────────────────────

CHAT_SYSTEM_PROMPT = """You are Antonio, an expert smart contract security AI agent and the absolute controller of the Vyper audit platform.

Your role is to help users with smart contract security audits in a conversational way. You have access to powerful SKILLS that you can call.

## How to Think (ReAct Pattern)

For each step, follow this format:
1. THINK — Understand what the user wants and decide what to do
2. ACT — Call a skill if needed (audit, scan, search memory, etc.)
3. OBSERVE — Process the skill result
4. REPEAT until you can answer the user
5. FINAL_ANSWER — Respond to the user in natural language

## Available Skills

{s Skills}

## Guidelines

1. Understand user intent:
   - "audit 0x1234" → run audit skills
   - "what did we find?" → search memory
   - "show programs" → fetch program list
   - "help" → explain capabilities
   - general questions → answer from knowledge

2. Always respond in the SAME LANGUAGE the user used
   - User speaks Indonesian → you answer in Indonesian
   - User speaks English → you answer in English

3. Be conversational but professional:
   - Explain what you're doing before calling skills
   - Summarize results clearly
   - Ask clarifying questions if needed

4. When calling skills, explain briefly what you're doing
5. After getting skill results, summarize them for the user
6. If a skill fails, explain the error and suggest alternatives

## Output Format

You MUST respond with valid JSON:
{{
  "thought": "your reasoning here",
  "action": "skill_name or FINAL_ANSWER",
  "action_input": {{ "param": "value" or null }},
  "final_answer": "your conversational response or null"
}}

For the final step, set action to "FINAL_ANSWER" and provide a natural language response in final_answer.
"""


class AgentReasoningClient:
    """LLM client khusus untuk agent reasoning (ReAct think step)."""

    def __init__(
        self,
        openai_key: str = "",
        anthropic_key: str = "",
        openai_model: str = "gpt-4o",
        anthropic_model: str = "claude-3-5-sonnet-20241022",
        preferred_provider: str = "openai",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.openai_key = openai_key
        self.anthropic_key = anthropic_key
        self.openai_model = openai_model
        self.anthropic_model = anthropic_model
        self.preferred_provider = preferred_provider
        self._http_client = http_client

    # ── Core Reasoning ─────────────────────────────────────

    async def reason(
        self,
        context: str,
        skills_desc: str,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Agent berpikir: given context, what to do next?

        Args:
            context: Current session context (working memory + history)
            skills_desc: Description of available skills
            max_retries: Max retry on parse failure

        Returns:
            Dict with keys: thought, action, action_input, final_answer
        """
        system_prompt = REACT_SYSTEM_PROMPT.replace("{s Skills}", skills_desc)
        user_prompt = f"## Context\n\n{context}\n\n## Task\n\nWhat should I do next?"

        last_error: str | None = None

        for attempt in range(max_retries):
            try:
                raw = await self._call_llm(system_prompt, user_prompt)
                result = self._parse_response(raw)

                # Jika ada error dari attempt sebelumnya, tambahkan ke thought
                if last_error and result.get("action") != "FINAL_ANSWER":
                    result["thought"] = (
                        f"[Previous attempt failed: {last_error}]\n{result.get('thought', '')}"
                    )

                return result

            except (ValueError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                log.warning(
                    "agent_reason_parse_retry",
                    attempt=attempt + 1,
                    error=last_error,
                )
                continue

        # Fallback: return error action
        return {
            "thought": f"Failed to reason after {max_retries} attempts: {last_error}",
            "action": "FINAL_ANSWER",
            "action_input": None,
            "final_answer": f"Error: Could not process request - {last_error}",
        }

    async def _call_llm(self, system: str, user: str) -> str:
        """Call LLM API (OpenAI or Anthropic)."""
        if self.preferred_provider == "anthropic" and self.anthropic_key:
            return await self._call_anthropic(system, user)
        return await self._call_openai(system, user)

    async def _call_openai(self, system: str, user: str) -> str:
        if not self.openai_key:
            raise RuntimeError("OpenAI API key not configured")
        if self._http_client is None:
            raise RuntimeError("HTTP client not initialized")

        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.openai_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": 2048,
            "temperature": 0.2,
        }

        resp = await self._http_client.post(
            f"{OPENAI_BASE_URL}/chat/completions",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def _call_anthropic(self, system: str, user: str) -> str:
        if not self.anthropic_key:
            raise RuntimeError("Anthropic API key not configured")
        if self._http_client is None:
            raise RuntimeError("HTTP client not initialized")

        headers = {
            "x-api-key": self.anthropic_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.anthropic_model,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "max_tokens": 2048,
            "temperature": 0.2,
        }

        resp = await self._http_client.post(
            f"{ANTHROPIC_BASE_URL}/messages",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]

    # ── Parse ──────────────────────────────────────────────

    def _parse_response(self, raw: str) -> dict[str, Any]:
        """Parse LLM response into structured action dict.

        Attempts JSON parsing first, then falls back to
        text-based parsing for non-JSON responses.
        """
        text = raw.strip()

        # Try JSON first
        if text.startswith("{"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # Fallback: parse text format
        lines = text.split("\n")
        result: dict[str, Any] = {
            "thought": "",
            "action": "FINAL_ANSWER",
            "action_input": None,
            "final_answer": text,
        }

        current_key = None
        for line in lines:
            line = line.strip()
            if line.upper().startswith("THOUGHT:"):
                result["thought"] = line[len("THOUGHT:"):].strip()
                current_key = "thought"
            elif line.upper().startswith("ACTION:"):
                result["action"] = line[len("ACTION:"):].strip()
                current_key = "action"
            elif line.upper().startswith("ACTION_INPUT:"):
                try:
                    input_str = line[len("ACTION_INPUT:"):].strip()
                    result["action_input"] = json.loads(input_str)
                except json.JSONDecodeError:
                    result["action_input"] = {"data": input_str}
                current_key = "action_input"
            elif line.upper().startswith("OBSERVATION:"):
                current_key = None
            elif line.upper().startswith("FINAL_ANSWER:"):
                result["action"] = "FINAL_ANSWER"
                result["final_answer"] = line[len("FINAL_ANSWER:"):].strip()
            elif current_key and line and not line.startswith("```"):
                if isinstance(result.get(current_key), str):
                    result[current_key] += " " + line

        return result

    async def reason_custom(
        self,
        system_prompt: str,
        context: str,
        skills_desc: str = "",
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Agent reasoning with a custom system prompt.

        Args:
            system_prompt: Full system prompt (role-specific)
            context: Current context
            skills_desc: Skill descriptions (optional, can be in prompt already)
            max_retries: Max retry on parse failure

        Returns:
            Dict with keys: thought, action, action_input, final_answer
        """
        user_prompt = f"## Context\n\n{context}\n\n## Task\n\nWhat should I do next?"
        last_error: str | None = None

        for attempt in range(max_retries):
            try:
                raw = await self._call_llm(system_prompt, user_prompt)
                result = self._parse_response(raw)

                if last_error and result.get("action") != "FINAL_ANSWER":
                    result["thought"] = (
                        f"[Previous attempt failed: {last_error}]\n{result.get('thought', '')}"
                    )

                return result

            except (ValueError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                log.warning(
                    "agent_reason_custom_retry",
                    attempt=attempt + 1,
                    error=last_error,
                )
                continue

        return {
            "thought": f"Failed to reason after {max_retries} attempts: {last_error}",
            "action": "FINAL_ANSWER",
            "action_input": None,
            "final_answer": f"Error: Could not process request - {last_error}",
        }

    async def reflect(self, session_summary: str) -> str:
        """Agent反思: evaluate how the session went.

        Args:
            session_summary: Summary of what happened

        Returns:
            Reflection text with lessons learned
        """
        prompt = (
            "Reflect on this audit session. What went well? "
            "What could be improved? What patterns did you learn?\n\n"
            f"Session: {session_summary}"
        )
        return await self._call_llm(
            "You are a self-improving security audit agent. Reflect honestly.",
            prompt,
        )
