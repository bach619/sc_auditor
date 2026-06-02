"""Enhanced NLP — AI-powered natural language analysis.

Menggabungkan rule-based NLP (existing) dengan LLM dari 06-ai untuk:
  1. Penjelasan natural language tentang findings
  2. Generate human-readable audit report sections
  3. Tanya-jawab tentang kontrak dan temuannya
  4. Auto-generate PoC description in plain English
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

from src._rule_based_nlp import _RuleBasedNLP

log = structlog.get_logger()


class EnhancedNLP:
    """AI-enhanced NLP layer using 06-ai LLM backend.

    Falls back to rule-based NLP if AI is unavailable.
    """

    def __init__(self, ai_url: str | None = None) -> None:
        self._ai_url = ai_url
        self._rule_engine = _RuleBasedNLP()

    async def explain_finding(self, finding: dict[str, Any]) -> str:
        """Generate human-readable explanation for a finding.

        Uses AI if available, falls back to rule-based.
        """
        if self._ai_url:
            try:
                return await self._ai_explain(finding)
            except Exception as e:
                log.warning("ai_explain_failed", error=str(e))

        return self._rule_engine.explain_finding(finding)

    async def generate_report_section(
        self,
        findings: list[dict[str, Any]],
        section: str = "summary",
    ) -> str:
        """Generate an audit report section from findings."""
        if self._ai_url and section in ("summary", "detailed", "recommendations"):
            try:
                return await self._ai_report_section(findings, section)
            except Exception as e:
                log.warning("ai_report_failed", error=str(e))

        return self._rule_engine.generate_report_section(findings, section)

    async def ask_question(self, question: str, context: dict[str, Any]) -> str:
        """Answer a natural language question about findings/contract."""
        if self._ai_url:
            try:
                return await self._ai_ask(question, context)
            except Exception as e:
                log.warning("ai_ask_failed", error=str(e))

        return self._rule_engine.ask_question(question, context)

    async def generate_poc_description(
        self, finding: dict[str, Any]
    ) -> str:
        """Generate a plain-English PoC description with attack steps."""
        if self._ai_url:
            try:
                return await self._ai_poc_description(finding)
            except Exception:
                pass

        return self._rule_engine.generate_poc_description(finding)

    async def summarize_findings(
        self, findings: list[dict[str, Any]]
    ) -> str:
        """Generate a one-paragraph summary of all findings."""
        if self._ai_url:
            try:
                return await self._ai_summarize(findings)
            except Exception:
                pass

        return self._rule_engine.summarize_findings(findings)

    # ── AI-powered methods ─────────────────────────────

    async def _ai_explain(self, finding: dict[str, Any]) -> str:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._ai_url}/v1/chat/completions",
                json={
                    "model": "default",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a smart contract security expert. "
                                "Explain the following vulnerability in simple terms "
                                "that a developer can understand. Include: "
                                "1) What the vulnerability is, "
                                "2) Why it's dangerous, "
                                "3) How an attacker would exploit it."
                            ),
                        },
                        {
                            "role": "user",
                            "content": json.dumps(finding),
                        },
                    ],
                    "max_tokens": 500,
                    "temperature": 0.3,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return ""

    async def _ai_report_section(
        self, findings: list[dict[str, Any]], section: str
    ) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._ai_url}/v1/chat/completions",
                json={
                    "model": "default",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a smart contract audit report writer. "
                                f"Generate the '{section}' section of an audit report "
                                "based on the findings provided."
                            ),
                        },
                        {
                            "role": "user",
                            "content": json.dumps(findings, default=str),
                        },
                    ],
                    "max_tokens": 1000,
                    "temperature": 0.3,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return ""

    async def _ai_ask(self, question: str, context: dict[str, Any]) -> str:
        async with httpx.AsyncClient(timeout=15.0) as client:
            prompt = f"Context (findings): {json.dumps(context.get('findings', []), default=str)}\n\nQuestion: {question}"
            resp = await client.post(
                f"{self._ai_url}/v1/chat/completions",
                json={
                    "model": "default",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a smart contract security expert assistant. "
                                "Answer questions about audit findings accurately "
                                "and concisely."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 500,
                    "temperature": 0.3,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return ""

    async def _ai_poc_description(self, finding: dict[str, Any]) -> str:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._ai_url}/v1/chat/completions",
                json={
                    "model": "default",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a security researcher writing a Proof of Concept. "
                                "Describe step-by-step how to exploit this vulnerability. "
                                "Be specific about function calls, parameters, and expected results."
                            ),
                        },
                        {
                            "role": "user",
                            "content": json.dumps(finding, default=str),
                        },
                    ],
                    "max_tokens": 500,
                    "temperature": 0.4,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return ""

    async def _ai_summarize(self, findings: list[dict[str, Any]]) -> str:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._ai_url}/v1/chat/completions",
                json={
                    "model": "default",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Summarize the following smart contract audit findings "
                                "in one paragraph. Include total findings, severity "
                                "distribution, and the most critical issues."
                            ),
                        },
                        {
                            "role": "user",
                            "content": json.dumps(findings, default=str),
                        },
                    ],
                    "max_tokens": 300,
                    "temperature": 0.3,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return ""
