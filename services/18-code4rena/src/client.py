"""GraphQL client for the Code4rena API."""

from __future__ import annotations

from typing import Any

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

GRAPHQL_ENDPOINT = "https://api.code4rena.com/graphql"


class Code4renaClient:
    """Async GraphQL client for Code4rena audit contest platform.

    Uses httpx.AsyncClient to query the public GraphQL endpoint.
    Handles pagination, rate limiting, and error handling.
    Converts Code4rena data to UnifiedBounty format.
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _graphql(self, query: str, variables: dict | None = None) -> dict[str, Any]:
        """Execute a GraphQL query against Code4rena."""
        client = await self._get_client()
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        try:
            resp = await client.post(
                GRAPHQL_ENDPOINT,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if "errors" in data:
                for err in data["errors"]:
                    log.warning("graphql.error", message=err.get("message", str(err)))
            return data.get("data", {})
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                log.warning("graphql.rate_limited", headers=dict(e.response.headers))
            else:
                log.error("graphql.http_error", status=e.response.status_code, body=e.response.text[:200])
            return {}
        except httpx.TimeoutException:
            log.error("graphql.timeout")
            return {}
        except Exception as e:
            log.error("graphql.unexpected", error=str(e))
            return {}

    # ── Contest Queries ─────────────────────────────────────

    CONTESTS_QUERY = """
    query Contests($first: Int, $after: String, $status: String) {
      contests(first: $first, after: $after, status: $status) {
        edges {
          node {
            id
            title
            description
            status
            startDate
            endDate
            totalPool
            platformId
            slug
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    """

    CONTEST_DETAIL_QUERY = """
    query ContestDetail($id: ID!) {
      contest(id: $id) {
        id
        title
        description
        status
        startDate
        endDate
        totalPool
        platformId
        slug
        scope {
          contracts {
            address
            chain
            name
          }
          repos
        }
      }
    }
    """

    async def fetch_contests(self, status: str = "active") -> list[dict[str, Any]]:
        """Fetch contests with pagination. Returns normalized contest dicts."""
        log.info("code4rena.fetch_contests.start", status=status)
        all_contests: list[dict] = []
        cursor: str | None = None
        has_next = True
        page = 0

        while has_next:
            page += 1
            variables: dict[str, Any] = {"first": 50, "status": status}
            if cursor:
                variables["after"] = cursor

            data = await self._graphql(self.CONTESTS_QUERY, variables)
            contests_data = data.get("contests", {})
            edges = contests_data.get("edges", [])

            for edge in edges:
                node = edge.get("node", {})
                if node:
                    all_contests.append(self._normalize_contest(node))

            page_info = contests_data.get("pageInfo", {})
            has_next = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

            log.debug("code4rena.fetch_contests.page", page=page, count=len(edges), has_next=has_next)

            if not edges:
                break

        log.info("code4rena.fetch_contests.done", total=len(all_contests))
        return all_contests

    async def fetch_contest_detail(self, contest_id: str) -> dict[str, Any] | None:
        """Fetch detailed info for a single contest including scope."""
        log.info("code4rena.fetch_contest_detail", contest_id=contest_id)
        data = await self._graphql(self.CONTEST_DETAIL_QUERY, {"id": contest_id})
        contest = data.get("contest")
        if contest is None:
            log.warning("code4rena.contest_not_found", contest_id=contest_id)
            return None
        return self._normalize_contest_detail(contest)

    # ── Normalization ───────────────────────────────────────

    def _normalize_contest(self, node: dict) -> dict[str, Any]:
        """Normalize a contest node from the list query."""
        return {
            "id": str(node.get("id", "")),
            "title": node.get("title", ""),
            "description": node.get("description", ""),
            "status": node.get("status", "upcoming"),
            "start_date": node.get("startDate", ""),
            "end_date": node.get("endDate", ""),
            "total_pool_usd": float(node.get("totalPool") or 0),
            "platform_id": str(node.get("platformId", "")),
            "slug": node.get("slug", ""),
        }

    def _normalize_contest_detail(self, node: dict) -> dict[str, Any]:
        """Normalize a contest detail node including scope."""
        scope = node.get("scope") or {}
        scope_contracts = scope.get("contracts") or []
        scope_repos = scope.get("repos") or []

        return {
            "id": str(node.get("id", "")),
            "title": node.get("title", ""),
            "description": node.get("description", ""),
            "status": node.get("status", "upcoming"),
            "start_date": node.get("startDate", ""),
            "end_date": node.get("endDate", ""),
            "total_pool_usd": float(node.get("totalPool") or 0),
            "platform_id": str(node.get("platformId", "")),
            "slug": node.get("slug", ""),
            "scope": {
                "contracts": [
                    {
                        "address": c.get("address", ""),
                        "chain": c.get("chain", ""),
                        "name": c.get("name", ""),
                    }
                    for c in scope_contracts
                ],
                "repos": scope_repos if isinstance(scope_repos, list) else [],
            },
        }

    # ── Unified Bounty Conversion ───────────────────────────

    def to_unified_bounty(self, contest: dict) -> UnifiedBounty:
        """Convert a normalized contest dict to UnifiedBounty model."""
        scope = contest.get("scope", {})
        scope_contracts = scope.get("contracts", [])
        scope_repos = scope.get("repos", [])

        status_map = {
            "active": BountyStatus.ACTIVE,
            "upcoming": BountyStatus.UPCOMING,
            "closed": BountyStatus.CLOSED,
            "judging": BountyStatus.JUDGING,
            "escalating": BountyStatus.ESCALATING,
            "paid": BountyStatus.PAID,
        }
        bounty_status = status_map.get(
            contest.get("status", "").lower(), BountyStatus.UPCOMING
        )

        return UnifiedBounty(
            id=f"c4_{contest['id']}",
            platform=BountyPlatform.CODE4RENA,
            platform_id=str(contest.get("platform_id", "")),
            title=contest.get("title", ""),
            description=contest.get("description", ""),
            bounty_type=BountyType.AUDIT_CONTEST,
            status=bounty_status,
            scope_contracts=[
                BountyContract(
                    address=c.get("address", ""),
                    chain=c.get("chain", ""),
                    name=c.get("name", ""),
                )
                for c in scope_contracts
            ],
            scope_repos=list(scope_repos),
            max_bounty_usd=float(contest.get("total_pool_usd") or 0),
            total_pool_usd=float(contest.get("total_pool_usd") or 0),
            start_date=contest.get("start_date"),
            end_date=contest.get("end_date"),
            url=f"https://code4rena.com/contests/{contest.get('slug', contest['id'])}",
        )
