"""SyncManager — Orchestrates full sync of all bounty providers.

Menggunakan EnhancedJSONStorage untuk persistence.
Mengiterasi semua registered provider (Immunefi, HackerOne, dll).
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import structlog

from src.models import Contract, Program, Repo, SyncStatus
from src.providers import get_available_providers, get_provider_statuses
from src.repo_detector import RepoDetector
from src.scraper import ImmunefiScraper, ProgramNotFoundError
from src.storage import EnhancedJSONStorage

log = structlog.get_logger()

# ── Constants ──────────────────────────────────────────────

COMMIT_HASH_URL = (
    "https://api.github.com/repos/"
    "infosec-us-team/Immunefi-Bug-Bounty-Programs-Unofficial/commits/main"
)

# Read GITHUB_TOKEN once from environment
_GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")


def _github_auth_headers() -> dict[str, str]:
    """Return Authorization header if GITHUB_TOKEN is set."""
    if _GITHUB_TOKEN:
        return {"Authorization": f"Bearer {_GITHUB_TOKEN}"}
    return {}


# ── SyncManager ────────────────────────────────────────────

class SyncManager:
    """Manages program data sync from Immunefi GitHub mirror.

    Data is stored via EnhancedJSONStorage:
      /data/immunefi/
      ├── programs/{slug}.json       # Per-program files
      ├── history/{slug}.jsonl       # Change log
      ├── indexes/                    # Fast lookup indexes
      ├── sync_log.jsonl              # Sync operation log
      └── _meta.json                  # Schema version, last_synced, commit_hash

    Usage:
        mgr = SyncManager(Path("/data/immunefi"))
        mgr.load_programs()

        # Full sync
        async with httpx.AsyncClient() as client:
            status = await mgr.sync_all(client)
    """

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Enhanced JSON Storage
        self.storage = EnhancedJSONStorage(self.data_dir)

        # In-memory program cache
        self._programs: dict[str, Program] = {}

        # Sync tracking (in-memory, for polling /sync/{id})
        self._syncs: dict[str, SyncStatus] = {}

        # Sync schedule config (persisted in meta)
        self.interval_minutes: int = self._load_interval_from_meta()
        self.next_sync_at: str | None = None
        self._sync_task: asyncio.Task | None = None  # set by start_background_sync()

    # ── Load / Save ─────────────────────────────────────────

    def load_programs(self) -> dict[str, Program]:
        """Load programs from disk into memory.

        Delegates to EnhancedJSONStorage which handles:
        - Multi-file format (programs/{slug}.json)
        - Legacy migration (programs.json → new format)
        """
        self._programs = self.storage.load_all_programs()

        meta = self.storage.read_meta()
        log.info(
            "sync.load.complete",
            count=len(self._programs),
            schema_version=meta.get("schema_version"),
            last_synced=meta.get("last_synced"),
        )

        return self._programs

    def save_programs(self, programs: dict[str, Program] | None = None) -> bool:
        """Save all programs via EnhancedJSONStorage. Returns True on success."""
        if programs is not None:
            self._programs = programs

        # Save all programs to individual files
        all_ok = self.storage.save_all(self._programs)

        # Rebuild indexes
        self.storage.rebuild_indexes(self._programs)

        # Update metadata
        self.storage.write_meta(
            last_synced=datetime.now(timezone.utc).isoformat(),
        )

        if all_ok:
            log.info("sync.save.complete", count=len(self._programs))
        else:
            log.warning("sync.save.partial", count=len(self._programs))

        return all_ok

    # ── Background Sync Scheduler ──────────────────────────

    def _load_interval_from_meta(self) -> int:
        """Load interval from stored meta, default 30 min."""
        try:
            meta = self.storage.read_meta()
            return int(meta.get("sync_interval_minutes", 30))
        except Exception:
            return 30

    def _save_interval_to_meta(self) -> None:
        """Persist current interval to meta."""
        self.storage.write_meta(sync_interval_minutes=self.interval_minutes)

    def set_interval(self, minutes: int) -> None:
        """Update sync interval (min 1, max 1440)."""
        self.interval_minutes = max(1, min(1440, minutes))
        self._save_interval_to_meta()
        log.info("sync.interval_updated", minutes=self.interval_minutes)

    def start_background_sync(self) -> None:
        """Start background periodic sync task.

        Runs in an asyncio.Task that sleeps interval_minutes
        between each sync. Safe to call only inside a running event loop
        (e.g., FastAPI lifespan). No-op if already running.
        """
        if self._sync_task is not None and not self._sync_task.done():
            log.warning("sync.background.already_running")
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            log.warning("sync.background.no_event_loop", action="skipped")
            return

        async def _loop() -> None:
            log.info(
                "sync.background.started",
                interval_minutes=self.interval_minutes,
            )
            while True:
                try:
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        # Check for updates first (quick)
                        if await self.has_updates(client):
                            log.info("sync.background.updates_found")
                            await self.sync_all(client=client)
                        else:
                            log.debug("sync.background.no_updates")
                except asyncio.CancelledError:
                    log.info("sync.background.cancelled")
                    break
                except Exception as e:
                    log.error("sync.background.error", error=str(e)[:200])

                # Update next_sync_at and sleep
                self.next_sync_at = datetime.now(timezone.utc).isoformat()
                await asyncio.sleep(self.interval_minutes * 60)

        self._sync_task = asyncio.create_task(_loop())

    def stop_background_sync(self) -> None:
        """Stop the background sync task."""
        if self._sync_task is not None and not self._sync_task.done():
            self._sync_task.cancel()
            log.info("sync.background.stopped")
        self._sync_task = None

    @property
    def background_sync_running(self) -> bool:
        """Check if background sync task is active."""
        return (self._sync_task is not None and not self._sync_task.done())

    # ── Sync Operations ────────────────────────────────────

    async def sync_all(
        self,
        client: httpx.AsyncClient | None = None,
    ) -> SyncStatus:
        """Run a full sync: iterate all providers → merge → save.

        Workflow:
          1. Get all available providers from registry
          2. Each provider's .fetch_program_list() → raw list
          3. Merge + deduplicate (by slug) across providers
          4. Fetch detail for each program from best available provider
          5. Save per-program via EnhancedJSONStorage

        Returns a SyncStatus that can be polled via get_sync_status().
        """
        sync_id = uuid.uuid4().hex[:12]
        started_at = datetime.now(timezone.utc).isoformat()

        status = SyncStatus(
            sync_id=sync_id,
            status="running",
            started_at=started_at,
        )
        self._syncs[sync_id] = status

        log.info("sync.all.start", sync_id=sync_id)

        try:
            # Step 1: Fetch from all providers
            raw_by_provider = await self._fetch_from_all_providers(client)
            all_raw = []
            for provider_name, items in raw_by_provider.items():
                all_raw.extend(items)
                log.info(
                    "sync.all.provider_list",
                    provider=provider_name,
                    count=len(items),
                )

            if not all_raw:
                log.warning("sync.all.no_data_from_any_provider")
                status.status = "completed"
                status.completed_at = datetime.now(timezone.utc).isoformat()
                status.total = 0
                return status

            # Step 2: Merge & deduplicate (last provider wins for each slug)
            merged: dict[str, dict] = {}
            for item in all_raw:
                slug = item.get("slug", "")
                if slug:
                    merged[slug] = item

            status.total = len(merged)
            log.info("sync.all.merged", total=status.total)

            # Step 3: Build program models + save
            programs: dict[str, Program] = {}
            repo_detector = RepoDetector()

            for i, (slug, list_item) in enumerate(merged.items()):
                detail = await self._fetch_best_detail(slug, list_item, client)
                program = self._build_program(list_item, detail, repo_detector)
                programs[slug] = program
                self.storage.save_program(program)
                status.programs_synced = i + 1

            # Step 4: Update commit hash (only for Immunefi mirror)
            await self._update_commit_hash(client)

            # Step 5: Update in-memory state + indexes
            self._programs = programs
            self.storage.rebuild_indexes(programs)

            # Step 6: Update metadata
            now = datetime.now(timezone.utc).isoformat()
            self.storage.write_meta(last_synced=now)

            # Step 7: Record sync log
            self.storage.append_sync_log({
                "sync_id": sync_id,
                "status": "completed",
                "programs_synced": status.programs_synced,
                "total": status.total,
                "providers": list(raw_by_provider.keys()),
                "started_at": started_at,
                "completed_at": now,
            })

            status.status = "completed"
            status.completed_at = now
            log.info(
                "sync.all.complete",
                sync_id=sync_id,
                total=status.total,
                synced=status.programs_synced,
            )

        except Exception as e:
            status.status = "failed"
            status.completed_at = datetime.now(timezone.utc).isoformat()
            status.error = str(e)
            log.error("sync.all.failed", sync_id=sync_id, error=str(e))

            self.storage.append_sync_log({
                "sync_id": sync_id,
                "status": "failed",
                "error": str(e)[:200],
                "started_at": started_at,
                "completed_at": status.completed_at,
            })

        self._syncs[sync_id] = status
        return status

    async def sync_incremental(self, client: httpx.AsyncClient) -> SyncStatus:
        """Incremental sync: only fetch programs that changed since last sync.

        Uses GitHub API compare to detect changed files, then only fetches
        detail for those programs. Fallback to full sync if commit hash unknown.
        """
        meta = self.storage.read_meta()
        last_commit = meta.get("commit_hash")

        if not last_commit:
            log.info("sync.incremental.no_commit_hash", action="fallback_to_full")
            return await self.sync_all(client)

        # Check latest remote commit
        latest_commit = await self._fetch_latest_commit(client)
        if not latest_commit:
            log.warning("sync.incremental.cannot_fetch_commit")
            return await self.sync_all(client)

        if latest_commit == last_commit:
            log.info("sync.incremental.no_changes")
            return SyncStatus(
                sync_id="incremental",
                status="skipped",
                reason="no_changes",
                total=len(self._programs),
                programs_synced=0,
                started_at=datetime.now(timezone.utc).isoformat(),
            )

        # Get changed files between commits
        changes = await self._get_changed_files(client, last_commit, latest_commit)
        changed_slugs = [c["slug"] for c in changes if c["status"] != "removed"]
        removed_slugs = [c["slug"] for c in changes if c["status"] == "removed"]

        log.info(
            "sync.incremental.changes",
            changed=len(changed_slugs),
            removed=len(removed_slugs),
        )

        synced = 0
        repo_detector = RepoDetector()
        # Use multi-provider detail fetching
        for slug in changed_slugs:
            try:
                list_item = {"slug": slug}
                detail = await self._fetch_best_detail(slug, list_item, client)
                if not detail or detail == list_item:
                    # Could not fetch detail — treat as removed
                    self._programs.pop(slug, None)
                    prog_file = self.storage.data_dir / "programs" / f"{slug}.json"
                    if prog_file.exists():
                        prog_file.unlink()
                    continue

                program = self._build_program(list_item, detail, repo_detector)
                self._programs[slug] = program
                self.storage.save_program(program)
                synced += 1
            except Exception as e:
                log.warning("sync.incremental.slug_error", slug=slug, error=str(e)[:80])

        # Remove deleted programs
        for slug in removed_slugs:
            self._programs.pop(slug, None)
            prog_file = self.storage.data_dir / "programs" / f"{slug}.json"
            if prog_file.exists():
                prog_file.unlink()

        # Update commit hash + indexes
        self.storage.write_meta(commit_hash=latest_commit)
        self.storage.rebuild_indexes(self._programs)

        now = datetime.now(timezone.utc).isoformat()
        self.storage.append_sync_log({
            "sync_id": "incremental",
            "status": "completed",
            "programs_synced": synced,
            "programs_removed": len(removed_slugs),
            "total": len(self._programs),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": now,
        })

        log.info("sync.incremental.complete", synced=synced, removed=len(removed_slugs))
        return SyncStatus(
            sync_id="incremental",
            status="completed",
            total=len(self._programs),
            programs_synced=synced,
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=now,
        )

    async def has_updates(self, client: httpx.AsyncClient | None = None) -> bool:
        """Quick check if the remote repo has new commits."""
        meta = self.storage.read_meta()
        stored_hash = meta.get("commit_hash")

        if not stored_hash:
            return True  # never synced

        try:
            close_client = client is None
            if close_client:
                client = httpx.AsyncClient(timeout=10.0)

            try:
                resp = await client.get(COMMIT_HASH_URL, headers=_github_auth_headers())
                resp.raise_for_status()
                latest_sha = resp.json().get("sha", "")
                has_updates = latest_sha != stored_hash
                log.info(
                    "sync.has_updates",
                    has_updates=has_updates,
                    stored=stored_hash[:8],
                    remote=latest_sha[:8],
                    authenticated=bool(_GITHUB_TOKEN),
                )
                return has_updates
            finally:
                if close_client:
                    await client.aclose()
        except Exception as e:
            log.warning("sync.has_updates.error", error=str(e))
            return True  # assume updates on error

    # ── Fork Index ──────────────────────────────────────────

    def save_fork_index(self, fork_data: dict) -> bool:
        """Save fork index (tracks which repos have been forked)."""
        return self.storage.write_atomic(
            self.storage.data_dir / "indexes" / "forks.json",
            fork_data,
        )

    def load_fork_index(self) -> dict:
        """Load fork index. Returns empty dict if none."""
        data = self.storage.get_index("forks")
        return data if isinstance(data, dict) else {}

    # ── Sync Status ─────────────────────────────────────────

    def get_sync_status(self, sync_id: str) -> SyncStatus | None:
        """Get the status of a specific sync operation."""
        return self._syncs.get(sync_id)

    def get_providers_status(self) -> list[dict]:
        """Get status info for all registered providers."""
        return get_provider_statuses()

    # ── Intelligence ─────────────────────────────────────────

    def get_scores(self) -> dict[str, Any]:
        """Compute program intelligence scores."""
        from src.scorer import ProgramScorer  # noqa: PLC0415 — lazy import
        scorer = ProgramScorer()
        index = scorer.build_score_index(self._programs)
        return index

    def get_score_for(self, slug: str) -> dict[str, Any] | None:
        """Get score for a single program."""
        from src.scorer import ProgramScorer  # noqa: PLC0415
        prog = self._programs.get(slug)
        if not prog:
            return None
        scorer = ProgramScorer()
        components = scorer.score_components(prog)
        return {
            "slug": slug,
            "name": prog.name,
            "score": round(sum(components.values()), 1),
            "components": {k: round(v, 2) for k, v in components.items()},
        }

    def get_trends(self) -> dict[str, Any]:
        """Generate full trend report."""
        from src.trends import TrendAnalyzer  # noqa: PLC0415
        analyzer = TrendAnalyzer(self.storage)
        return analyzer.full_report(self._programs)

    def get_trends_recent(self, hours: int = 24) -> dict[str, Any]:
        """Get recent changes summary."""
        from src.trends import TrendAnalyzer  # noqa: PLC0415
        analyzer = TrendAnalyzer(self.storage)
        return analyzer.recent_changes(hours=hours)

    def get_anomalies(self) -> dict[str, Any]:
        """Detect anomalies across all programs."""
        from src.anomaly import AnomalyDetector  # noqa: PLC0415
        detector = AnomalyDetector(self.storage)
        return detector.summary(self._programs)

    async def get_repo_intel(self, max_programs: int = 20) -> list[dict[str, Any]]:
        """Fetch repo intelligence for programs with repos."""
        from src.repo_intel import RepoIntel  # noqa: PLC0415
        async with httpx.AsyncClient(timeout=30.0) as client:
            intel = RepoIntel(self.storage, client)
            return await intel.bulk_enrich(self._programs, max_programs=max_programs)

    # ── Level 3: Autonomous ──────────────────────────────────

    async def submit_finding(
        self,
        program_slug: str,
        title: str,
        description: str,
        severity: str,
        vulnerability_classification: str,
        proof_of_concept: str,
        contract_address: str,
    ) -> dict[str, Any]:
        """Submit finding ke Immunefi via API."""
        from src.submission import ImmunefiSubmissionBot  # noqa: PLC0415
        async with httpx.AsyncClient(timeout=60.0) as client:
            bot = ImmunefiSubmissionBot(self.storage, client)
            return await bot.submit(
                program_slug=program_slug,
                title=title,
                description=description,
                severity=severity,
                vulnerability_classification=vulnerability_classification,
                proof_of_concept=proof_of_concept,
                contract_address=contract_address,
            )

    def list_submissions(self, status: str | None = None) -> list[dict]:
        from src.submission import ImmunefiSubmissionBot  # noqa: PLC0415
        bot = ImmunefiSubmissionBot(self.storage)
        return bot.list_submissions(status=status)

    def get_submission(self, submission_id: str) -> dict[str, Any] | None:
        from src.submission import ImmunefiSubmissionBot  # noqa: PLC0415
        bot = ImmunefiSubmissionBot(self.storage)
        return bot.get_submission(submission_id)

    def get_submission_stats(self) -> dict[str, Any]:
        from src.submission import ImmunefiSubmissionBot  # noqa: PLC0415
        bot = ImmunefiSubmissionBot(self.storage)
        return bot.get_stats()

    async def analyze_competition(self, slug: str) -> dict[str, Any]:
        from src.competition import CompetitionIntelligence  # noqa: PLC0415
        prog = self._programs.get(slug)
        if not prog:
            return {"error": f"Program '{slug}' not found"}
        analyzer = CompetitionIntelligence(self.storage)
        return await analyzer.analyze_program(prog)

    async def predict_bounty(self, slug: str) -> dict[str, Any]:
        from src.predictor import BountyPredictor  # noqa: PLC0415
        prog = self._programs.get(slug)
        if not prog:
            return {"error": f"Program '{slug}' not found"}
        predictor = BountyPredictor(self.storage)
        return await predictor.predict(prog)

    # ── Level 4: God-Tier ─────────────────────────────────────

    async def fetch_tvl(self, protocol_slug: str) -> dict[str, Any]:
        """Fetch TVL data untuk protocol dari DeFiLlama."""
        from src.onchain import OnChainMonitor  # noqa: PLC0415
        async with httpx.AsyncClient(timeout=30.0) as client:
            monitor = OnChainMonitor(self.storage, client)
            return await monitor.fetch_tvl(protocol_slug)

    async def fetch_all_tvl(self, max_programs: int = 20) -> list[dict]:
        from src.onchain import OnChainMonitor  # noqa: PLC0415
        async with httpx.AsyncClient(timeout=30.0) as client:
            monitor = OnChainMonitor(self.storage, client)
            return await monitor.fetch_all_tvl(self._programs, max_programs=max_programs)

    def get_tvl_stats(self) -> dict[str, Any]:
        from src.onchain import OnChainMonitor  # noqa: PLC0415
        monitor = OnChainMonitor(self.storage)
        return monitor.get_tvl_stats()

    async def poll_events(self) -> list[dict]:
        from src.onchain import OnChainMonitor  # noqa: PLC0415
        async with httpx.AsyncClient(timeout=30.0) as client:
            monitor = OnChainMonitor(self.storage, client)
            return await monitor.poll_events()

    def get_onchain_events(
        self,
        program_slug: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        from src.onchain import OnChainMonitor  # noqa: PLC0415
        monitor = OnChainMonitor(self.storage)
        return monitor.get_events(
            program_slug=program_slug,
            event_type=event_type,
            limit=limit,
        )

    def get_web3_status(self) -> dict[str, Any]:
        from src.onchain import OnChainMonitor  # noqa: PLC0415
        monitor = OnChainMonitor(self.storage)
        return {
            "web3_available": monitor.is_web3_available(),
            "rpc_url": os.getenv("WEB3_RPC_URL", "(not set)")[:50],
        }

    @property
    def onchain_monitor(self) -> "OnChainMonitor":
        from src.onchain import OnChainMonitor  # noqa: PLC0415
        return OnChainMonitor(self.storage)

    async def match_programs(
        self,
        specialization: str,
        min_bounty: float = 0,
        chain: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """AI-powered program matching."""
        from src.matcher import AISmartMatcher  # noqa: PLC0415
        async with httpx.AsyncClient(timeout=60.0) as client:
            matcher = AISmartMatcher(client)
            return await matcher.find_best(
                specialization=specialization,
                programs=self._programs,
                min_bounty=min_bounty,
                chain=chain,
                limit=limit,
            )

    async def find_similar_programs(self, slug: str, limit: int = 5) -> list[dict]:
        from src.matcher import AISmartMatcher  # noqa: PLC0415
        async with httpx.AsyncClient(timeout=60.0) as client:
            matcher = AISmartMatcher(client)
            return await matcher.find_similar_programs(
                slug=slug, programs=self._programs, limit=limit,
            )

    async def predict_vulnerabilities(self, slug: str) -> dict[str, Any]:
        """Predict vulnerabilities for a program."""
        from src.exploit_planner import PredictiveExploitPlanner  # noqa: PLC0415
        prog = self._programs.get(slug)
        if not prog:
            return {"error": f"Program '{slug}' not found"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            planner = PredictiveExploitPlanner(self.storage, client)
            return await planner.predict_for_program(slug, prog)

    async def trigger_priority_scans(self, max_scans: int = 5) -> list[dict]:
        """Auto-trigger scans for high-priority programs."""
        from src.exploit_planner import PredictiveExploitPlanner  # noqa: PLC0415
        async with httpx.AsyncClient(timeout=120.0) as client:
            planner = PredictiveExploitPlanner(self.storage, client)
            return await planner.trigger_priority_scans(
                self._programs, max_scans=max_scans,
            )

    def get_dashboard(self) -> dict[str, Any]:
        """Full dashboard data."""
        from src.dashboard import DashboardData  # noqa: PLC0415
        dash = DashboardData(self.storage)
        return dash.full_dashboard(self._programs)

    # ── Contract Fetching + Scan Trigger ─────────────────────

    async def fetch_contracts(
        self,
        max_programs: int = 50,
        trigger_scan: bool = True,
    ) -> dict[str, Any]:
        """Fetch contract source code from Service 03 for all programs.

        Optionally triggers orchestrator scan pipeline per contract.
        """
        from src.contract_fetcher import ContractAutoFetcher  # noqa: PLC0415
        async with httpx.AsyncClient(timeout=120.0) as client:
            fetcher = ContractAutoFetcher(self.storage, client)
            return await fetcher.fetch_all(
                self._programs,
                trigger_scan=trigger_scan,
                max_programs=max_programs,
            )

    async def fetch_program_contracts(
        self,
        slug: str,
        trigger_scan: bool = True,
    ) -> list[dict[str, Any]]:
        """Fetch contracts for a single program."""
        from src.contract_fetcher import ContractAutoFetcher  # noqa: PLC0415
        prog = self._programs.get(slug)
        if not prog:
            return [{"error": f"Program '{slug}' not found"}]
        async with httpx.AsyncClient(timeout=120.0) as client:
            fetcher = ContractAutoFetcher(self.storage, client)
            return await fetcher.fetch_for_program(slug, prog, trigger_scan=trigger_scan)

    def get_contract_fetch_stats(self) -> dict[str, Any]:
        """Get contract fetch cache stats."""
        from src.contract_fetcher import ContractAutoFetcher  # noqa: PLC0415
        fetcher = ContractAutoFetcher(self.storage)
        return fetcher.get_fetch_stats()

    # ── Forking ──────────────────────────────────────────────

    async def fork_all_unforked(self, max_forks: int = 10) -> list[dict]:
        """Fork all repos that haven't been forked yet."""
        from src.fork_engine import ForkEngine  # noqa: PLC0415
        async with httpx.AsyncClient(timeout=60.0) as client:
            engine = ForkEngine(self.storage, client)
            return await engine.fork_all_unforked(self._programs, max_forks=max_forks)

    async def fork_program(self, slug: str) -> list[dict]:
        """Fork all unforked repos for a specific program."""
        from src.fork_engine import ForkEngine  # noqa: PLC0415
        prog = self._programs.get(slug)
        if not prog:
            return [{"error": f"Program '{slug}' not found"}]
        async with httpx.AsyncClient(timeout=60.0) as client:
            engine = ForkEngine(self.storage, client)
            return await engine.fork_for_program(slug, prog)

    def get_fork_info(self) -> dict[str, Any]:
        """Get fork stats and unforked repos list."""
        from src.fork_engine import ForkEngine  # noqa: PLC0415
        engine = ForkEngine(self.storage)
        stats = engine.get_fork_stats(self._programs)
        unforked = engine.find_unforked_repos(self._programs)
        return {
            **stats,
            "unforked_repos": unforked,
            "token_available": engine.is_available(),
        }

    # ── Accessors ───────────────────────────────────────────

    @property
    def programs(self) -> dict[str, Program]:
        return self._programs

    @property
    def last_synced(self) -> str | None:
        meta = self.storage.read_meta()
        return meta.get("last_synced")

    @property
    def commit_hash(self) -> str | None:
        meta = self.storage.read_meta()
        return meta.get("commit_hash")

    @property
    def fork_engine(self) -> "ForkEngine":
        """Lazy-initialized ForkEngine instance (no client — for read ops)."""
        from src.fork_engine import ForkEngine  # noqa: PLC0415
        return ForkEngine(self.storage)

    # ── Internal Helpers ────────────────────────────────────

    async def _fetch_from_all_providers(
        self,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, list[dict]]:
        """Iterate all available providers and fetch program lists.

        Returns dict mapping provider_name → list[dict] of raw programs.
        Falls back to ImmunefiScraper if no BountyProvider registered.

        Semua provider HTTP clients di-close setelah selesai untuk
        mencegah connection leak.
        """
        providers = get_available_providers()

        if not providers:
            # Fallback: old-school ImmunefiScraper
            log.info("sync.all.no_bounty_providers", action="fallback_scraper")
            async with ImmunefiScraper(client) as scraper:
                raw = await scraper.fetch_program_list()
                return {"immunefi_scraper": raw}

        PROVIDER_TIMEOUT = 60  # seconds max per provider

        results: dict[str, list[dict]] = {}
        try:
            for provider in providers:
                name = getattr(provider, "name", provider.__class__.__name__)
                try:
                    raw = await asyncio.wait_for(
                        provider.fetch_program_list(),
                        timeout=PROVIDER_TIMEOUT,
                    )
                    results[name] = raw
                    log.info(
                        "sync.all.provider_success",
                        provider=name,
                        count=len(raw),
                    )
                except asyncio.TimeoutError:
                    log.warning(
                        "sync.all.provider_timeout",
                        provider=name,
                        timeout=PROVIDER_TIMEOUT,
                    )
                    results[name] = []
                except Exception as e:
                    log.warning(
                        "sync.all.provider_failed",
                        provider=name,
                        error=str(e)[:100],
                    )
                    results[name] = []
        finally:
            # Cleanup: close all provider HTTP clients
            for provider in providers:
                if hasattr(provider, "close") and callable(provider.close):
                    try:
                        await provider.close()
                    except Exception:
                        pass

        return results

    async def _fetch_best_detail(
        self,
        slug: str,
        list_item: dict,
        client: httpx.AsyncClient | None = None,
    ) -> dict:
        """Fetch detail dari provider terbaik yang available.

        Priority:
          1. BountyProvider (sorted by priority)
          2. Fallback to ImmunefiScraper
          3. Fallback to list_item (no detail)

        Semua provider HTTP clients di-close setelah selesai.
        """
        providers = get_available_providers()
        providers.sort(key=lambda p: getattr(p, "priority", 99))

        try:
            for provider in providers:
                try:
                    detail = await provider.fetch_program_detail(slug)
                    if detail:
                        return detail
                except Exception as e:
                    log.warning(
                        "sync.all.detail_failed",
                        provider=getattr(provider, "name", "?"),
                        slug=slug,
                        error=str(e)[:80],
                    )
        finally:
            # Cleanup: close all provider HTTP clients
            for provider in providers:
                if hasattr(provider, "close") and callable(provider.close):
                    try:
                        await provider.close()
                    except Exception:
                        pass

        # Fallback: ImmunefiScraper
        try:
            async with ImmunefiScraper(client) as scraper:
                detail = await scraper.fetch_program_detail(slug)
                if detail:
                    return detail
        except ProgramNotFoundError:
            pass
        except Exception as e:
            log.warning("sync.all.detail_scraper_failed", slug=slug, error=str(e)[:80])

        return list_item

    async def _update_commit_hash(self, client: httpx.AsyncClient | None) -> None:
        """Fetch and persist the latest commit SHA from the mirror repo."""
        if client is None:
            return

        sha = await self._fetch_latest_commit(client)
        if sha:
            self.storage.write_meta(commit_hash=sha)
            log.info("sync.commit_hash_updated", sha=sha[:8])

    async def _fetch_latest_commit(self, client: httpx.AsyncClient) -> str | None:
        """Get latest commit SHA from GitHub API (with GITHUB_TOKEN if available)."""
        try:
            resp = await client.get(COMMIT_HASH_URL, headers=_github_auth_headers())
            resp.raise_for_status()
            return resp.json().get("sha", "")
        except Exception as e:
            log.warning("sync.fetch_commit.error", error=str(e))
            return None

    async def _get_changed_files(
        self,
        client: httpx.AsyncClient,
        base_sha: str,
        head_sha: str,
    ) -> list[dict]:
        """GitHub API compare: get changed program files between two commits."""
        url = (
            "https://api.github.com/repos/"
            "infosec-us-team/Immunefi-Bug-Bounty-Programs-Unofficial/"
            f"compare/{base_sha}...{head_sha}"
        )
        try:
            resp = await client.get(url, headers=_github_auth_headers())
            resp.raise_for_status()
            files = resp.json().get("files", [])
        except Exception as e:
            log.warning("sync.get_changed_files.error", error=str(e))
            return []

        changes = []
        for f in files:
            # Parse slug from filename: "project/{slug}.json"
            if f["filename"].startswith("project/") and f["filename"].endswith(".json"):
                slug = f["filename"][8:-5]
                changes.append({
                    "slug": slug,
                    "status": f["status"],  # added, modified, removed
                    "filename": f["filename"],
                })
        return changes

    @staticmethod
    def _build_program(
        list_item: dict[str, Any],
        detail: dict[str, Any],
        repo_detector: RepoDetector,
    ) -> Program:
        """Build a Program model from list + detail data."""
        max_bounty = detail.get("maxBounty") or list_item.get("maxBounty")
        min_bounty = detail.get("minBounty") or list_item.get("minBounty")

        if max_bounty is not None:
            try:
                max_bounty = float(max_bounty)
            except (ValueError, TypeError):
                max_bounty = None
        if min_bounty is not None:
            try:
                min_bounty = float(min_bounty)
            except (ValueError, TypeError):
                min_bounty = None

        raw_contracts = ImmunefiScraper.parse_contracts(detail)
        contracts = [Contract(**c) for c in raw_contracts]
        repos = repo_detector.detect(detail)
        chains = detail.get("chains") or list_item.get("chains") or []

        return Program(
            slug=str(detail.get("slug") or list_item.get("slug", "")),
            name=str(detail.get("name") or list_item.get("name", "")),
            chains=list(chains) if isinstance(chains, list) else [str(chains)],
            max_bounty=max_bounty,
            min_bounty=min_bounty,
            currency=str(detail.get("currency", "USD") or "USD"),
            status=str(detail.get("status") or list_item.get("status", "unknown")),
            repos=repos,
            contracts=contracts,
            project_url=str(detail.get("project_url") or detail.get("url", "")),
            logo=str(detail.get("logo", "") or ""),
            description=str(detail.get("description", "") or ""),
            tags=detail.get("tags", []) or list_item.get("tags", []),
            updated_at=str(detail.get("updatedAt") or detail.get("updated_at", "")),
        )
