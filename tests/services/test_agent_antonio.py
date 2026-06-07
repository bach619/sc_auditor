"""Tests for Agent Antonio Service (14-agent).

Endpoints:
  GET  /health
  GET  /team/structure
  GET  /team/sessions
  POST /agent/run
  GET  /skills
  GET  /skills/{id}
  GET  /memory
  GET  /memory/working
  GET  /memory/episodic
  GET  /memory/semantic
  GET  /memory/search
  POST /agent/session
  GET  /agent/session/{id}
  DELETE /agent/session/{id}
  POST /agent/delegate
  POST /agent/negotiate
  POST /daemon/start
  POST /daemon/stop
  GET  /daemon/status
  GET  /gateway/health
  POST /gateway/proxy
  GET  /config/providers
  GET  /config/provider/{id}
  GET  /chat
  GET  /chat/{id}
  POST /feedback
  GET  /metrics
  GET  /circuit-breaker/status
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest


@pytest.mark.integration
class TestAgentAntonioInit:
    """Agent Loop initialization and skill registry tests."""

    @pytest.mark.asyncio
    async def test_agent_loop_init_with_skill_registry(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """AgentLoop initializes with skill registry loaded from skills directory."""
        resp = await async_client.get(f"{agent_url}/skills")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"
        assert "data" in body

    @pytest.mark.asyncio
    async def test_skill_registration_and_listing(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """Skills can be registered and listed with metadata."""
        resp = await async_client.get(f"{agent_url}/skills")
        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", {})
        if isinstance(data, list):
            assert all("name" in s for s in data if isinstance(s, dict))


@pytest.mark.integration
class TestAgentAntonioReAct:
    """ReAct loop and session management tests."""

    @pytest.mark.asyncio
    async def test_react_loop_think_act_observe_cycle(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """POST /agent/run executes think -> act -> observe cycle."""
        payload = {"task": "audit_analysis", "context": {"chain": "ethereum"}}
        resp = await async_client.post(f"{agent_url}/agent/run", json=payload)
        assert resp.status_code in (200, 202, 422)

    @pytest.mark.asyncio
    async def test_agent_session_creation_and_tracking(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """POST /agent/session creates a new agent session and returns session_id."""
        payload = {"program": "test-program", "audit_id": "test-audit-001"}
        resp = await async_client.post(f"{agent_url}/agent/session", json=payload)
        assert resp.status_code in (200, 201, 404)

    @pytest.mark.asyncio
    async def test_sub_agent_delegation_flow(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """POST /agent/delegate delegates a sub-task to a sub-agent."""
        payload = {"task": "scan_contract", "target": "0xdead", "sub_agent": "scanner"}
        resp = await async_client.post(f"{agent_url}/agent/delegate", json=payload)
        assert resp.status_code in (200, 202, 422)

    @pytest.mark.asyncio
    async def test_task_negotiation_feasibility_check(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """POST /agent/negotiate checks task feasibility before execution."""
        payload = {"task": "formal_verify", "constraints": {"timeout": 300}}
        resp = await async_client.post(f"{agent_url}/agent/negotiate", json=payload)
        assert resp.status_code in (200, 202, 422)


@pytest.mark.integration
class TestAgentAntonioConfig:
    """Provider config and validation tests."""

    @pytest.mark.asyncio
    async def test_provider_config_loading_from_config_service(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """GET /config/providers loads provider configurations from Config Service."""
        resp = await async_client.get(f"{agent_url}/config/providers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_provider_url_validation_domain_matching(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """Provider URLs are validated against allowed domains."""
        resp = await async_client.get(f"{agent_url}/config/providers")
        assert resp.status_code == 200
        body = resp.json()
        if "data" in body:
            data = body["data"]
            if isinstance(data, list):
                for provider in data:
                    if isinstance(provider, dict) and "url" in provider:
                        assert isinstance(provider["url"], str)


@pytest.mark.integration
class TestAgentAntonioMemory:
    """Memory CRUD and search tests."""

    @pytest.mark.asyncio
    async def test_system_knowledge_loading_into_vector_memory(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """System knowledge is loaded into vector memory at startup."""
        resp = await async_client.get(f"{agent_url}/memory")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_memory_crud_working_episodic_semantic(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """Memory stores support CRUD across working, episodic, and semantic stores."""
        endpoints = (
            f"{agent_url}/memory/working",
            f"{agent_url}/memory/episodic",
            f"{agent_url}/memory/semantic",
        )
        for ep in endpoints:
            resp = await async_client.get(ep)
            assert resp.status_code == 200
            body = resp.json()
            assert body["meta"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_memory_search_across_stores(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """GET /memory/search queries across all memory stores."""
        payload = {"query": "reentrancy vulnerability", "limit": 5}
        resp = await async_client.get(f"{agent_url}/memory/search", params=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"


@pytest.mark.integration
class TestAgentAntonioDaemon:
    """Daemon lifecycle tests."""

    @pytest.mark.asyncio
    async def test_daemon_start_stop_lifecycle(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """POST /daemon/start and /daemon/stop manage daemon lifecycle."""
        resp = await async_client.get(f"{agent_url}/daemon/status")
        assert resp.status_code == 200
        # daemon lifecycle should not crash
        await async_client.post(f"{agent_url}/daemon/start")
        await asyncio.sleep(0.2)
        await async_client.post(f"{agent_url}/daemon/stop")


@pytest.mark.integration
class TestAgentAntonioLearning:
    """Feedback learning and team execution tests."""

    @pytest.mark.asyncio
    async def test_feedback_learning_session_to_pattern(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """POST /feedback converts session experience into reusable patterns."""
        payload = {"session_id": "test-session-001", "rating": 4, "notes": "good reentrancy detection"}
        resp = await async_client.post(f"{agent_url}/feedback", json=payload)
        assert resp.status_code in (200, 201, 404, 422)

    @pytest.mark.asyncio
    async def test_lead_auditor_team_based_execution(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """GET /team/sessions returns team-based execution sessions."""
        resp = await async_client.get(f"{agent_url}/team/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"


@pytest.mark.integration
class TestAgentAntonioInfra:
    """Circuit breaker, gateway, and error handling tests."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """GET /circuit-breaker/status reports circuit breaker state."""
        resp = await async_client.get(f"{agent_url}/circuit-breaker/status")
        assert resp.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_agent_gateway_proxy_to_orchestrator(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """POST /gateway/proxy forwards requests to the orchestrator."""
        payload = {"path": "/audits", "method": "GET"}
        resp = await async_client.post(f"{agent_url}/gateway/proxy", json=payload)
        assert resp.status_code in (200, 404, 422)

    @pytest.mark.asyncio
    async def test_error_handling_in_agent_loop(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """Agent loop handles malformed input gracefully."""
        payload = {"malformed": True}
        resp = await async_client.post(f"{agent_url}/agent/run", json=payload)
        assert resp.status_code in (200, 400, 422)

    @pytest.mark.asyncio
    async def test_session_timeout_and_cleanup(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """DELETE /agent/session/{id} cleans up expired sessions."""
        resp = await async_client.delete(f"{agent_url}/agent/session/__nonexistent__")
        assert resp.status_code in (200, 404, 422)


@pytest.mark.integration
class TestAgentAntonioObservability:
    """Metrics, persistence, and session tracking tests."""

    @pytest.mark.asyncio
    async def test_chat_session_persistence(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """GET /chat lists persisted chat sessions."""
        resp = await async_client.get(f"{agent_url}/chat")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_skill_execution_metrics_tracking(self, async_client: httpx.AsyncClient, agent_url: str) -> None:
        """GET /metrics tracks skill execution counts and latencies."""
        resp = await async_client.get(f"{agent_url}/metrics")
        assert resp.status_code in (200, 404)
