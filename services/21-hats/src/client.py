"""REST API client for Hats Finance bug bounty platform."""

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

BASE_URL = "https://api.hats.finance/v1"


class HatsFinanceClient:
    """Async REST client for the Hats Finance public API.

    Usage:
        async with HatsFinanceClient() as client:
            vaults = await client.fetch_vaults()
            detail = await client.fetch_vault_detail("abc123")
    """

    def __init__(self, base_url: str = BASE_URL, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> HatsFinanceClient:
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
            raise RuntimeError("HatsFinanceClient must be used as async context manager")
        return self._client

    async def fetch_vaults(self) -> list[UnifiedBounty]:
        """Fetch all Hats Finance vaults and normalize to UnifiedBounty."""
        try:
            resp = await self.client.get("/vaults")
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.error("hats.fetch_vaults.error", error=str(e))
            return []

        items = data if isinstance(data, list) else data.get("data", data.get("vaults", []))
        normalized = []
        for item in items:
            try:
                normalized.append(self._normalize_vault(item))
            except Exception as e:
                log.warning("hats.normalize_vault.error", id=item.get("id"), error=str(e))
        return normalized

    async def fetch_vault_detail(self, vault_id: str) -> UnifiedBounty | None:
        """Fetch full vault detail including scope contracts."""
        try:
            resp = await self.client.get(f"/vaults/{vault_id}")
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.error("hats.fetch_vault_detail.error", vault_id=vault_id, error=str(e))
            return None

        try:
            return self._normalize_vault(data)
        except Exception as e:
            log.warning("hats.normalize_detail.error", vault_id=vault_id, error=str(e))
            return None

    def _normalize_vault(self, raw: dict) -> UnifiedBounty:
        vault_id = str(raw.get("id", ""))
        return UnifiedBounty(
            id=f"hats-{vault_id}",
            platform=BountyPlatform.HATS_FINANCE,
            platform_id=vault_id,
            title=str(raw.get("title", raw.get("name", raw.get("description", "")))),
            description=str(raw.get("description", "")),
            bounty_type=BountyType.BUG_BOUNTY,
            status=self._map_status(raw.get("status", "")),
            scope_contracts=self._extract_contracts(raw),
            scope_repos=self._extract_repos(raw),
            chains=[raw.get("chain", "")] if raw.get("chain") else [],
            languages=raw.get("languages", ["Solidity"]),
            max_bounty_usd=float(raw.get("max_bounty_usd", raw.get("max_reward_usd", 0))),
            total_pool_usd=float(raw.get("total_deposited_usd", raw.get("total_pool_usd", 0))),
            rewards=[],
            rewards_token=raw.get("rewards_token"),
            start_date=raw.get("start_date"),
            end_date=raw.get("end_date"),
            url=raw.get("url", f"https://app.hats.finance/vault/{vault_id}"),
            repo_url=raw.get("repo_url"),
        )

    @staticmethod
    def _map_status(raw_status: str) -> BountyStatus:
        status_map = {
            "active": BountyStatus.ACTIVE,
            "live": BountyStatus.ACTIVE,
            "open": BountyStatus.ACTIVE,
            "upcoming": BountyStatus.UPCOMING,
            "created": BountyStatus.UPCOMING,
            "paused": BountyStatus.CLOSED,
            "closed": BountyStatus.CLOSED,
            "terminated": BountyStatus.CLOSED,
            "completed": BountyStatus.CLOSED,
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
