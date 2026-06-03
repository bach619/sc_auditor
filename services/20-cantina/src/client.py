"""REST API client for Cantina audit contest platform."""

from __future__ import annotations

import httpx
import structlog

from vyper_lib.models.bounty import (
    BountyContract,
    BountyPlatform,
    BountyStatus,
    BountyType,
    UnifiedBounty,
)

log = structlog.get_logger()

BASE_URL = "https://cantina.xyz/api"


class CantinaClient:
    """Async REST client for the Cantina public API.

    Usage:
        async with CantinaClient() as client:
            contests = await client.fetch_contests()
            detail = await client.fetch_contest_detail("abc123")
    """

    def __init__(self, base_url: str = BASE_URL, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "CantinaClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("CantinaClient must be used as async context manager")
        return self._client

    async def fetch_contests(self) -> list[UnifiedBounty]:
        """Fetch all Cantina contests and normalize to UnifiedBounty."""
        try:
            resp = await self.client.get("/contests")
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.error("cantina.fetch_contests.error", error=str(e))
            return []

        items = data if isinstance(data, list) else data.get("data", data.get("contests", []))
        normalized = []
        for item in items:
            try:
                normalized.append(self._normalize_contest(item))
            except Exception as e:
                log.warning("cantina.normalize_contest.error", id=item.get("id"), error=str(e))
        return normalized

    async def fetch_contest_detail(self, contest_id: str) -> UnifiedBounty | None:
        """Fetch full contest detail including scope contracts."""
        try:
            resp = await self.client.get(f"/contests/{contest_id}")
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.error("cantina.fetch_contest_detail.error", contest_id=contest_id, error=str(e))
            return None

        try:
            return self._normalize_contest(data)
        except Exception as e:
            log.warning("cantina.normalize_detail.error", contest_id=contest_id, error=str(e))
            return None

    def _normalize_contest(self, raw: dict) -> UnifiedBounty:
        contest_id = str(raw.get("id", ""))
        return UnifiedBounty(
            id=f"cantina-{contest_id}",
            platform=BountyPlatform.CANTINA,
            platform_id=contest_id,
            title=str(raw.get("title", raw.get("name", ""))),
            description=str(raw.get("description", "")),
            bounty_type=BountyType.AUDIT_CONTEST,
            status=self._map_status(raw.get("status", "")),
            scope_contracts=self._extract_contracts(raw),
            scope_repos=self._extract_repos(raw),
            chains=raw.get("chains", []),
            languages=raw.get("languages", ["Vyper", "Solidity"]),
            max_bounty_usd=float(raw.get("max_bounty_usd", 0)),
            total_pool_usd=float(raw.get("total_reward_usd", raw.get("total_pool_usd", 0))),
            rewards=[],
            rewards_token=raw.get("rewards_token"),
            start_date=raw.get("starts_at") or raw.get("start_date"),
            end_date=raw.get("ends_at") or raw.get("end_date"),
            url=f"https://cantina.xyz/contests/{contest_id}",
            repo_url=raw.get("repo_url"),
        )

    @staticmethod
    def _map_status(raw_status: str) -> BountyStatus:
        status_map = {
            "upcoming": BountyStatus.UPCOMING,
            "live": BountyStatus.ACTIVE,
            "active": BountyStatus.ACTIVE,
            "judging": BountyStatus.JUDGING,
            "escalating": BountyStatus.ESCALATING,
            "completed": BountyStatus.CLOSED,
            "finished": BountyStatus.CLOSED,
            "paid": BountyStatus.PAID,
        }
        return status_map.get(raw_status.lower(), BountyStatus.CLOSED)

    @staticmethod
    def _extract_contracts(raw: dict) -> list[BountyContract]:
        contracts = []
        scope = raw.get("scope", raw.get("contracts", []))
        if not isinstance(scope, list):
            scope = []
        for item in scope:
            contracts.append(BountyContract(
                address=str(item.get("address", "")),
                chain=str(item.get("chain", item.get("network", ""))),
                name=str(item.get("name", item.get("contract_name", ""))),
                source_type=str(item.get("source_type", "")),
                repo_url=item.get("repo_url"),
                commit_hash=item.get("commit_hash"),
            ))
        return contracts

    @staticmethod
    def _extract_repos(raw: dict) -> list[str]:
        repos = raw.get("repos", raw.get("scope_repos", raw.get("repositories", [])))
        if not isinstance(repos, list):
            repos = []
        return [str(r) for r in repos if r]
