"""Integration tests for Hybrid Agent Architecture.

Tests the full flow:
1. Agent discovery (registry discovers backend agents)
2. Capability lookup (find agents by what they can do)
3. Delegation (Main Agent sends tasks to backend agents)
4. Negotiation (check if agent can handle a task)
5. Capacity management (agent rejects when busy)
6. Planning (planner creates execution plans)
7. AIAgent strategy (critical vs batch analysis)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client for testing."""
    client = AsyncMock()

    # Mock GET /agent/manifest response
    # Use MagicMock (not AsyncMock) because json() and raise_for_status()
    # are called synchronously in AgentRegistry.discover_all()
    manifest_response = MagicMock()
    manifest_response.status_code = 200
    manifest_response.json.return_value = {
        "data": {
            "service_name": "06-ai",
            "agent_role": "vulnerability_analyst",
            "version": "0.1.0",
            "capabilities": [
                {
                    "name": "classify_findings",
                    "description": "Classify scanner findings",
                    "input_schema": {},
                    "output_schema": {},
                    "estimated_duration_ms": 30000,
                    "estimated_cost_usd": 0.05,
                    "confidence": 0.85,
                }
            ],
            "constraints": {"max_concurrent_tasks": 3, "requires_api_key": False, "max_context_length": 8000},
            "current_load": {"active_tasks": 0, "queue_depth": 0, "status": "idle"},
        }
    }

    # Mock POST /agent/delegate response
    delegate_response = MagicMock()
    delegate_response.status_code = 200
    delegate_response.json.return_value = {
        "data": {
            "task_id": "task-test-123",
            "status": "completed",
            "output": {"result": "ok", "findings": []},
            "error": None,
            "confidence": 0.85,
            "cost_usd": 0.05,
            "duration_ms": 1500.0,
            "steps_taken": 1,
            "reflection": "Test completed successfully.",
        }
    }

    client.get = AsyncMock(return_value=manifest_response)
    client.post = AsyncMock(return_value=delegate_response)
    return client


# ── Test 1: Agent Discovery ──────────────────────────────────


@pytest.mark.asyncio
async def test_agent_discovery(mock_http_client):
    """Test that AgentRegistry can discover backend agents."""
    from services.shared.agent_protocol.registry import AgentRegistry

    registry = AgentRegistry(http_client=mock_http_client)
    registry._known_services = {"06-ai": "http://06-ai:8000"}

    manifests = await registry.discover_all()

    assert len(manifests) == 1
    assert manifests[0].service_name == "06-ai"
    assert manifests[0].agent_role == "vulnerability_analyst"
    assert len(manifests[0].capabilities) == 1

    # Verify HTTP call was made
    mock_http_client.get.assert_called_once_with(
        "http://06-ai:8000/agent/manifest"
    )


# ── Test 2: Capability Lookup ────────────────────────────────


@pytest.mark.asyncio
async def test_capability_lookup():
    """Test finding agents by capability."""
    from services.shared.agent_protocol.models import (
        AgentCapability,
        AgentManifest,
        CapabilityDefinition,
    )
    from services.shared.agent_protocol.registry import AgentRegistry

    registry = AgentRegistry()

    # Manually register an agent
    registry._agents["06-ai"] = AgentManifest(
        service_name="06-ai",
        agent_role="vulnerability_analyst",
        version="0.1.0",
        capabilities=[
            CapabilityDefinition(
                name=AgentCapability.CLASSIFY_FINDINGS,
                description="Classify findings",
                input_schema={},
                output_schema={},
            )
        ],
        current_load={"active_tasks": 0, "queue_depth": 0, "status": "idle"},
    )

    # Find by capability that exists
    results = registry.find_agents_by_capability(AgentCapability.CLASSIFY_FINDINGS)
    assert len(results) == 1
    assert results[0][0] == "06-ai"

    # Find by capability that doesn't exist
    results = registry.find_agents_by_capability(AgentCapability.RUN_FUZZING)
    assert len(results) == 0


# ── Test 3: Delegation Flow ──────────────────────────────────


@pytest.mark.asyncio
async def test_delegation_flow():
    """Test full delegation: Main Agent → Backend Agent."""
    from services.shared.agent_protocol.base_agent import BaseAgent
    from services.shared.agent_protocol.models import (
        AgentCapability,
        CapabilityDefinition,
        DelegationRequest,
        TaskStatus,
        generate_task_id,
    )

    # Create a test agent
    class TestAgent(BaseAgent):
        async def _execute_task(self, request):
            return {"result": f"Processed: {request.goal}", "_steps": 1}

    agent = TestAgent(service_name="test-agent", agent_role="test")
    agent.register_capability(CapabilityDefinition(
        name=AgentCapability.CLASSIFY_FINDINGS,
        description="Test capability",
        input_schema={},
        output_schema={},
    ))

    # Create delegation request
    request = DelegationRequest(
        task_id=generate_task_id(),
        goal="Analyze findings for USDe",
        capability=AgentCapability.CLASSIFY_FINDINGS,
        input_data={"findings": [{"id": "F-001", "severity": "high"}]},
    )

    # Handle delegation
    response = await agent.handle_delegation(request)

    assert response.status == TaskStatus.COMPLETED
    assert response.output["result"] == "Processed: Analyze findings for USDe"
    assert response.duration_ms >= 0
    assert len(response.steps_taken) == 1


# ── Test 4: Negotiation Flow ─────────────────────────────────


@pytest.mark.asyncio
async def test_negotiation_flow():
    """Test negotiation between Main Agent and Backend Agent."""
    from services.shared.agent_protocol.base_agent import BaseAgent
    from services.shared.agent_protocol.models import (
        AgentCapability,
        CapabilityDefinition,
        NegotiationRequest,
    )

    class TestAgent(BaseAgent):
        async def _execute_task(self, request):
            return {"result": "ok"}

    agent = TestAgent(service_name="test", agent_role="test")
    agent.register_capability(CapabilityDefinition(
        name=AgentCapability.CLASSIFY_FINDINGS,
        description="Test",
        input_schema={},
        output_schema={},
        estimated_duration_ms=1000,
    ))

    # Test: agent CAN handle
    req = NegotiationRequest(
        task_description="Classify findings",
        required_capability=AgentCapability.CLASSIFY_FINDINGS,
    )
    resp = await agent.handle_negotiation(req)
    assert resp.can_handle is True
    assert resp.estimated_duration_ms > 0

    # Test: agent CANNOT handle (unknown capability)
    req = NegotiationRequest(
        task_description="Fuzz contract",
        required_capability=AgentCapability.RUN_FUZZING,
    )
    resp = await agent.handle_negotiation(req)
    assert resp.can_handle is False


# ── Test 5: Agent at Capacity ────────────────────────────────


@pytest.mark.asyncio
async def test_agent_at_capacity():
    """Test that agent rejects tasks when at capacity."""
    import asyncio

    from services.shared.agent_protocol.base_agent import BaseAgent
    from services.shared.agent_protocol.models import (
        AgentCapability,
        CapabilityDefinition,
        DelegationRequest,
        TaskStatus,
        generate_task_id,
    )

    class TestAgent(BaseAgent):
        async def _execute_task(self, request):
            await asyncio.sleep(0.1)  # Simulate work
            return {"result": "ok"}

    agent = TestAgent(service_name="test", agent_role="test")
    agent._max_concurrent = 1
    agent.register_capability(CapabilityDefinition(
        name=AgentCapability.CLASSIFY_FINDINGS,
        description="Test",
        input_schema={},
        output_schema={},
    ))

    # Start first task (let it run in background)
    req1 = DelegationRequest(
        task_id=generate_task_id(),
        goal="Task 1",
        capability=AgentCapability.CLASSIFY_FINDINGS,
        input_data={},
    )
    task1 = asyncio.create_task(agent.handle_delegation(req1))
    await asyncio.sleep(0.02)  # Let first task start

    # Second task should be DEFERRED
    req2 = DelegationRequest(
        task_id=generate_task_id(),
        goal="Task 2",
        capability=AgentCapability.CLASSIFY_FINDINGS,
        input_data={},
    )
    response2 = await agent.handle_delegation(req2)
    assert response2.status == TaskStatus.DEFERRED

    # Wait for first task
    await task1


# ── Test 6: Planner ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_planner_creates_execution_plan():
    """Test that Planner creates valid execution plans."""
    import importlib.util
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    _planner_path = project_root / "services/14-agent/src/planner.py"

    # Dynamic load: use unique module name to avoid namespace clashes
    spec = importlib.util.spec_from_file_location(
        "test_vyper_planner", str(_planner_path)
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["test_vyper_planner"] = mod
    spec.loader.exec_module(mod)
    Planner = mod.Planner

    planner = Planner()
    plan = await planner.create_plan(
        goal="Full audit of USDe contract",
        input_data={"address": "0xabc", "chain": "ethereum"},
        available_skills=[
            "fetch_source", "scan_contract", "analyze_findings",
            "classify_finding", "exploit_test", "generate_report",
        ],
    )

    assert plan.goal == "Full audit of USDe contract"
    assert len(plan.steps) > 0
    assert plan.steps[0].step_number == 1
    assert plan.steps[0].required_skill in ("fetch_program", "fetch_source")
    assert plan.total_estimated_duration_ms > 0


# ── Test 7: AIAgent Strategy ─────────────────────────────────


@pytest.mark.asyncio
async def test_ai_agent_strategy_separates_critical_vs_low():
    """Test that AIAgent separates critical/high for deep analysis vs low/medium for batch."""
    from services.shared.agent_protocol.base_agent import BaseAgent
    from services.shared.agent_protocol.models import (
        AgentCapability,
        CapabilityDefinition,
        DelegationRequest,
    )

    # Create a minimal AIAgent-like agent
    class MockAIAgent(BaseAgent):
        def __init__(self):
            super().__init__("06-ai", "vulnerability_analyst")
            self.register_capability(CapabilityDefinition(
                name=AgentCapability.CLASSIFY_FINDINGS,
                description="Classify findings",
                input_schema={},
                output_schema={},
            ))

        async def _execute_task(self, request):
            input_data = request.input_data
            findings = input_data.get("findings", [])

            # This is the key behavior to test: separation logic
            critical = [f for f in findings if f.get("severity") in ("critical", "high")]
            low = [f for f in findings if f.get("severity") in ("low", "informational", "medium")]

            return {
                "findings": findings,
                "summary": {
                    "total": len(findings),
                    "true_positives": len(critical),  # Assume all critical are TP
                    "false_positives": len(low),
                },
                "strategy": "hybrid" if critical and low else ("deep" if critical else "batch"),
                "_steps": (1 if critical else 0) + (1 if low else 0),
            }

    agent = MockAIAgent()

    # Mix of findings
    findings = [
        {"id": "F-001", "severity": "critical", "title": "Reentrancy"},
        {"id": "F-002", "severity": "high", "title": "Oracle manipulation"},
        {"id": "F-003", "severity": "medium", "title": "Unused return"},
        {"id": "F-004", "severity": "low", "title": "Naming convention"},
        {"id": "F-005", "severity": "informational", "title": "Gas optimization"},
    ]

    request = DelegationRequest(
        task_id="test-001",
        goal="Analyze findings",
        capability=AgentCapability.CLASSIFY_FINDINGS,
        input_data={"findings": findings, "source": {"Contract.sol": "contract A {}"}},
    )

    response = await agent.handle_delegation(request)
    assert response.status.value == "completed"
    assert response.output["strategy"] == "hybrid"  # Both critical and low present
    assert response.output["summary"]["true_positives"] == 2  # 2 critical/high
    assert response.output["summary"]["false_positives"] == 3  # 3 low/medium/info
    assert len(response.steps_taken) == 2  # One deep step + one batch step


# ── Test 8: Full Integration Scenario ────────────────────────


@pytest.mark.asyncio
async def test_full_audit_scenario(mock_http_client):
    """Simulate a complete audit flow with discovery + delegation."""
    from services.shared.agent_protocol.models import (
        AgentCapability,
        CapabilityDefinition,
        DelegationRequest,
        generate_task_id,
    )
    from services.shared.agent_protocol.registry import AgentRegistry

    # Setup: Create registry and register an agent
    registry = AgentRegistry(http_client=mock_http_client)
    registry._known_services = {"06-ai": "http://06-ai:8000"}

    # Also manually register for capability lookup
    from services.shared.agent_protocol.models import AgentManifest
    registry._agents["06-ai"] = AgentManifest(
        service_name="06-ai",
        agent_role="vulnerability_analyst",
        version="0.1.0",
        capabilities=[CapabilityDefinition(
            name=AgentCapability.CLASSIFY_FINDINGS,
            description="Classify findings",
            input_schema={},
            output_schema={},
        )],
        current_load={"active_tasks": 0, "queue_depth": 0, "status": "idle"},
    )

    # Step 1: Discover agents
    manifests = await registry.discover_all()
    assert len(manifests) > 0

    # Step 2: Find agent by capability
    agents = registry.find_agents_by_capability(AgentCapability.CLASSIFY_FINDINGS)
    assert len(agents) > 0
    assert agents[0][0] == "06-ai"

    # Step 3: Get best agent
    best = registry.get_best_agent(AgentCapability.CLASSIFY_FINDINGS)
    assert best is not None
    assert best[0] == "06-ai"

    # Step 4: Delegate to best agent
    request = DelegationRequest(
        task_id=generate_task_id(),
        goal="Test analysis",
        capability=AgentCapability.CLASSIFY_FINDINGS,
        input_data={"findings": [], "source": {}},
    )
    response = await registry.delegate_to_best(AgentCapability.CLASSIFY_FINDINGS, request)
    assert response is not None
    assert response.status.value == "completed"


# ── Run instructions ────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
