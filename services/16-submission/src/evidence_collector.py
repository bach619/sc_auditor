from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.models import BugCategory

log = structlog.get_logger()

CATEGORY_SERVICE_PRIORITY: dict[str, list[str]] = {
    "reentrancy": ["08-exploit", "04a-scanner-slither"],
    "oracle_manipulation": ["08-exploit", "08-maths"],
    "flash_loan": ["08-exploit", "08-maths"],
    "mev": ["08-exploit", "08-maths"],
    "access_control": ["04a-scanner-slither", "03-source", "08-exploit"],
    "overflow": ["08-exploit", "08-maths"],
    "precision_loss": ["08-exploit", "08-maths"],
    "bridge": ["08-exploit", "03-source"],
    "zero_day": ["08-exploit", "08-maths"],
    "governance": ["08-exploit", "03-source"],
    "signature_replay": ["08-exploit", "08-maths"],
    "storage_collision": ["08-exploit", "08-maths"],
    "donation": ["08-exploit", "08-maths"],
    "other": ["08-exploit", "11-orchestrator"],
}


class EvidenceCollector:
    """Collect evidence from pipeline services for a given finding."""

    def __init__(
        self,
        immunefi_url: str = "http://02-immunefi:8000",
        source_url: str = "http://03-source:8000",
        ai_url: str = "http://06-ai:8000",
        exploit_url: str = "http://08-exploit:8006",
        orchestrator_url: str = "http://11-orchestrator:8000",
    ) -> None:
        self.immunefi_url = immunefi_url
        self.source_url = source_url
        self.ai_url = ai_url
        self.exploit_url = exploit_url
        self.orchestrator_url = orchestrator_url

    async def collect_all_evidence(self, finding_id: str, bug_category: str = "other") -> dict[str, Any]:
        """Collect all evidence from pipeline services."""
        evidence: dict[str, Any] = {
            "source": await self._get_source(finding_id),
            "scan_results": await self._get_scans(finding_id),
            "exploit_poc": await self._get_exploit(finding_id, bug_category),
            "math_params": await self._get_math(finding_id, bug_category),
            "program_info": await self._get_program(finding_id),
        }

        category_data = await self._get_category_specific_evidence(finding_id, bug_category)
        evidence["category_data"] = category_data

        evidence = {k: v for k, v in evidence.items() if v is not None}
        return evidence

    async def _get_source(self, finding_id: str) -> dict | None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.source_url}/source/{finding_id}",
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("data", data)
        except httpx.RequestError as e:
            log.warning("evidence.source_unreachable", finding_id=finding_id, error=str(e))
        return None

    async def _get_scans(self, finding_id: str) -> list[dict] | None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.orchestrator_url}/findings/{finding_id}/scans",
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("data", data)
                    if isinstance(results, dict):
                        return [results]
                    return results if isinstance(results, list) else [results]
        except httpx.RequestError as e:
            log.warning("evidence.scans_unreachable", finding_id=finding_id, error=str(e))
        return None

    async def _get_exploit(self, finding_id: str, bug_category: str = "other") -> dict | None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.exploit_url}/exploit/{finding_id}",
                    params={"category": bug_category},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("data", data)
        except httpx.RequestError as e:
            log.warning("evidence.exploit_unreachable", finding_id=finding_id, error=str(e))
        return None

    async def _get_math(self, finding_id: str, bug_category: str = "other") -> dict | None:
        math_endpoints = {
            "oracle_manipulation": "/math/fixed-point",
            "overflow": "/math/sat-solve",
            "mev": "/math/mev-calc",
            "reentrancy": "/math/sat-solve",
        }
        endpoint = math_endpoints.get(bug_category, "/math/status")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.exploit_url}{endpoint}",
                    params={"finding_id": finding_id},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("data", data)
        except httpx.RequestError as e:
            log.warning("evidence.math_unreachable", finding_id=finding_id, error=str(e))
        return None

    async def _get_program(self, finding_id: str) -> dict | None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.immunefi_url}/programs/{finding_id}",
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("data", data)
        except httpx.RequestError as e:
            log.warning("evidence.program_unreachable", finding_id=finding_id, error=str(e))
        return None

    async def _get_category_specific_evidence(self, finding_id: str, bug_category: str) -> dict[str, Any]:
        collectors = {
            "reentrancy": self._collect_reentrancy_evidence,
            "oracle_manipulation": self._collect_oracle_evidence,
            "overflow": self._collect_overflow_evidence,
            "bridge": self._collect_bridge_evidence,
            "zero_day": self._collect_zeroday_evidence,
            "mev": self._collect_mev_evidence,
            "donation": self._collect_donation_evidence,
        }
        collector = collectors.get(bug_category)
        if collector:
            return await collector(finding_id)
        return {}

    async def _collect_reentrancy_evidence(self, finding_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "call_graph": [],
            "state_diff": {},
            "call_depth": 0,
            "is_read_only": False,
            "is_cross_function": False,
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.exploit_url}/exploit/{finding_id}/call-graph",
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    call_graph = data.get("data", data)
                    result["call_graph"] = call_graph if isinstance(call_graph, list) else []

                resp2 = await client.get(
                    f"{self.exploit_url}/exploit/{finding_id}/state-diff",
                    timeout=10.0,
                )
                if resp2.status_code == 200:
                    data2 = resp2.json()
                    result["state_diff"] = data2.get("data", data2)
        except httpx.RequestError as e:
            log.warning("evidence.reentrancy_collect_error", finding_id=finding_id, error=str(e))
        return result

    async def _collect_oracle_evidence(self, finding_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "manipulation_cost": 0,
            "profit": 0,
            "twap_window": 0,
            "break_even_size": 0,
            "oracle_type": "unknown",
            "pools_affected": [],
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.exploit_url}/math/fixed-point",
                    json={"finding_id": finding_id},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    fp = resp.json().get("data", resp.json())
                    result["manipulation_cost"] = fp.get("manipulation_cost", 0)
                    result["twap_window"] = fp.get("twap_window", 0)
                    result["break_even_size"] = fp.get("break_even", 0)
                    result["oracle_type"] = fp.get("oracle_type", "unknown")

                resp2 = await client.post(
                    f"{self.exploit_url}/math/mev-calc",
                    json={"finding_id": finding_id, "type": "oracle"},
                    timeout=10.0,
                )
                if resp2.status_code == 200:
                    mev = resp2.json().get("data", resp2.json())
                    result["profit"] = mev.get("extractable_value", 0)
                    result["pools_affected"] = mev.get("pools_affected", [])
        except httpx.RequestError as e:
            log.warning("evidence.oracle_collect_error", finding_id=finding_id, error=str(e))
        return result

    async def _collect_overflow_evidence(self, finding_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "exact_values": [],
            "trigger_condition": "",
            "variable": "",
            "var_type": "",
            "max_loss": 0,
            "sat_proof": "",
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.exploit_url}/math/sat-solve",
                    json={"finding_id": finding_id, "type": "overflow"},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    sat = resp.json().get("data", resp.json())
                    result["exact_values"] = sat.get("solutions", [])
                    result["trigger_condition"] = sat.get("condition", "")
                    result["variable"] = sat.get("variable", "")
                    result["var_type"] = sat.get("variable_type", "")
                    result["max_loss"] = sat.get("max_extractable", 0)
                    result["sat_proof"] = sat.get("proof", "")
        except httpx.RequestError as e:
            log.warning("evidence.overflow_collect_error", finding_id=finding_id, error=str(e))
        return result

    async def _collect_zeroday_evidence(self, finding_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "novelty_points": [],
            "prior_art": "none",
            "closest_prior_art": None,
            "difference": "",
            "search_sources": [],
            "math_proof_available": False,
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.exploit_url}/exploit/{finding_id}/novelty",
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    novelty = resp.json().get("data", resp.json())
                    result["novelty_points"] = novelty.get("unique_aspects", [])
                    result["prior_art"] = novelty.get("prior_art_search", "none")
                    result["closest_prior_art"] = novelty.get("closest_match")
                    result["difference"] = novelty.get("difference_from_prior", "")
                    result["search_sources"] = novelty.get("search_sources", [])
                    result["math_proof_available"] = novelty.get("has_math_proof", False)
        except httpx.RequestError as e:
            log.warning("evidence.zeroday_collect_error", finding_id=finding_id, error=str(e))
        return result

    async def _collect_mev_evidence(self, finding_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "mev_score": 0.0,
            "sandwich_profit": 0,
            "frontrun_probability": 0.0,
            "affected_users": 0,
            "user_loss_per_tx": 0,
            "priority_gas_required": 0,
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.exploit_url}/math/mev-calc",
                    json={"finding_id": finding_id, "type": "mev"},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    mev = resp.json().get("data", resp.json())
                    result["mev_score"] = mev.get("mev_score", 0.0)
                    result["sandwich_profit"] = mev.get("sandwich_profit", 0)
                    result["frontrun_probability"] = mev.get("probability", 0.0)
                    result["affected_users"] = mev.get("affected_users", 0)
                    result["user_loss_per_tx"] = mev.get("user_loss", 0)
                    result["priority_gas_required"] = mev.get("priority_gas", 0)
        except httpx.RequestError as e:
            log.warning("evidence.mev_collect_error", finding_id=finding_id, error=str(e))
        return result

    async def _collect_bridge_evidence(self, finding_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "source_chain": "",
            "dest_chain": "",
            "bridge_type": "",
            "validator_count": 0,
            "needed_validators": 0,
            "attack_path": "",
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.exploit_url}/exploit/{finding_id}/bridge",
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", resp.json())
                    result["source_chain"] = data.get("source_chain", "")
                    result["dest_chain"] = data.get("dest_chain", "")
                    result["bridge_type"] = data.get("bridge_type", "")
                    result["validator_count"] = data.get("validator_count", 0)
                    result["needed_validators"] = data.get("needed_validators", 0)
                    result["attack_path"] = data.get("attack_path", "")
        except httpx.RequestError as e:
            log.warning("evidence.bridge_collect_error", finding_id=finding_id, error=str(e))
        return result

    async def _collect_donation_evidence(self, finding_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "exchange_rate_change": "",
            "donation_amount": 0,
            "share_inflation": "",
            "victim_count": 0,
            "profit": 0,
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.exploit_url}/exploit/{finding_id}/donation",
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", resp.json())
                    result["exchange_rate_change"] = data.get("exchange_rate_change", "")
                    result["donation_amount"] = data.get("donation_amount", 0)
                    result["share_inflation"] = data.get("share_inflation", "")
                    result["victim_count"] = data.get("victim_count", 0)
                    result["profit"] = data.get("profit", 0)
        except httpx.RequestError as e:
            log.warning("evidence.donation_collect_error", finding_id=finding_id, error=str(e))
        return result
