# Enhancement Plan: Service 02 — Immunefi Bug Bounty Intelligence

> **Service saat ini**: Fetch program dari GitHub mirror Immunefi, deteksi repo GitHub, cache JSON lokal.
> **Port**: 8001  |  **Version**: 0.1.0

---

## Daftar Isi

1. [Arsitektur Saat Ini](#1-arsitektur-saat-ini)
2. [Critical Gaps](#2-critical-gaps)
3. [Enhancement Level 1 — Foundation (Minggu 1)](#3-enhancement-level-1--foundation-minggu-1)
4. [Enhancement Level 2 — Intelligence (Minggu 2)](#4-enhancement-level-2--intelligence-minggu-2)
5. [Enhancement Level 3 — Autonomous (Minggu 3)](#5-enhancement-level-3--autonomous-minggu-3)
6. [Enhancement Level 4 — God-Tier (Minggu 4+)](#6-enhancement-level-4--god-tier-minggu-4)
7. [Repository Forking Capability](#7-repository-forking-capability)
8. [Roadmap & Dependencies](#8-roadmap--dependencies)

---

## 1. Arsitektur Saat Ini

```
┌─────────────────────────────────────────────────────────┐
│                    02-immunefi                           │
│                                                         │
│  GitHub Mirror (raw JSON)  ──►  ImmunefiScraper         │
│       (infosec-us-team)          │                       │
│                                  ▼                       │
│  RepoDetector ──►  SyncManager ──►  programs.json       │
│                                  │          (disk cache) │
│                                  ▼                       │
│  FastAPI Endpoints:                                      │
│    GET  /programs        (list + filter + sort)          │
│    GET  /programs/{slug} (detail)                        │
│    POST /sync            (async background)              │
│    POST /sync/run        (sync blocking)                 │
│    GET  /sync/{id}       (poll status)                   │
│    GET  /sync/status     (last sync info)                │
│    GET  /stats           (aggregated)                    │
└─────────────────────────────────────────────────────────┘
```

### Kelemahan Fundamental Saat Ini:
1. **Hanya satu source**: GitHub mirror unofficial — bisa stale/down
2. **No real-time updates**: Sync manual via POST — tidak ada webhook atau polling otomatis
3. **Tidak ada integrasi langsung dengan Immunefi API**: Hanya mirror data
4. **Repo detection terbatas**: Regex GitHub URL saja — tidak deteksi GitLab, Bitbucket, atau private repo
5. **Tidak ada analisis kontrak**: Contract addresses di-capture tapi tidak pernah di-scan atau di-analyze
6. **No TVL / value data**: Tidak ada info total value locked per program
7. **Tidak ada severity scoring**: Tidak ada mapping antara bug bounty reward dan severity
8. **Caching flat file**: JSON file rawan corruption, tidak ada versioning, tidak ada backup

---

## 2. Critical Gaps

| Gap | Dampak | Priority |
|-----|--------|----------|
| Single source of truth (unofficial mirror) | Data tidak akurat, ketinggalan | 🔴 Critical |
| No automatic sync scheduling | Program baru tidak terdeteksi | 🔴 Critical |
| No Immunefi official API integration | Tidak bisa submit finding auto | 🟡 High |
| No contract-level intelligence | Tidak tahu kontrak apa yang ada | 🟡 High |
| No TVL / financial context | Tidak bisa prioritasi bounty | 🟡 High |
| No historical tracking | Tidak tahu perubahan program | 🟢 Medium |
| No notifications | Tidak alert ketika program baru | 🟢 Medium |

---

## 3. Enhancement Level 1 — Foundation (Minggu 1)

### 3.1 Multi-Source Data Ingestion

Tambahkan **5 source baru** untuk fetching program data:

```python
# src/providers/
PROVIDER_REGISTRY = {
    "immunefi_official": ImmunefiOfficialProvider(),   # API resmi Immunefi
    "immunefi_mirror":  ImmunefiMirrorProvider(),      # GitHub mirror (existing)
    "hackerone":        HackerOneProvider(),           # HackerOne bounties
    "cantina":          CantinaProvider(),             # Cantina (spearbit)
    "code4rena":        Code4renaProvider(),           # C4 contests
    "sherlock":         SherlockProvider(),            # Sherlock audits
}
```

**ImmunefiOfficialProvider** — langsung ke API resmi:
```python
class ImmunefiOfficialProvider:
    """Fetch langsung dari API resmi Immunefi."""
    
    BASE_URL = "https://api.immunefi.com/v1"
    # Endpoints:
    # GET /programs          — list semua program
    # GET /programs/{slug}   — detail program
    # GET /programs/{slug}/contracts — kontrak yang di-audit
    # GET /programs/{slug}/stats     — TVL, reward paid, dll
    
    async def fetch_program_list(self) -> list[Program]:
        # Dengan API key dari 01-config
        api_key = await config_service.get_secret("immunefi_api_key")
        headers = {"Authorization": f"Bearer {api_key}"}
        resp = await self.client.get(f"{BASE_URL}/programs", headers=headers)
        return self._parse(resp.json())
```

### 3.2 Automated Sync Engine

Ganti sync manual dengan **4 mode scheduling**:

```yaml
sync:
  modes:
    - realtime:    # Webhook dari Immunefi (Level 3)
      type: webhook
      endpoint: /webhook/immunefi
    
    - periodic:    # Cron-based auto-sync
      type: cron
      schedule: "*/30 * * * *"   # Every 30 minutes
      max_programs: 500
    
    - incremental: # Hanya fetch yang berubah sejak last sync
      type: diff
      use_commit_hash: true
      batch_size: 50
    
    - on_demand:   # Manual trigger (existing)
      type: manual
      endpoint: /sync
```

**Incremental sync implementation**:
```python
async def sync_incremental(self) -> SyncStatus:
    """Hanya sync program yang berubah sejak last sync."""
    last_commit = self._commit_hash
    
    # 1. Check remote commit hash
    latest_commit = await self._fetch_latest_commit()
    if latest_commit == last_commit:
        return SyncStatus(status="skipped", reason="no_changes")
    
    # 2. Get changed files (GitHub API compare)
    changes = await self._get_changed_files(last_commit, latest_commit)
    changed_slugs = [f["slug"] for f in changes if f["type"] == "program"]
    
    # 3. Only re-sync changed programs
    for slug in changed_slugs:
        try:
            detail = await scraper.fetch_program_detail(slug)
            self._programs[slug] = self._build_program(detail)
        except ProgramNotFoundError:
            self._programs.pop(slug, None)  # Program dihapus
    
    # 4. Update commit hash
    self._commit_hash = latest_commit
    self.save_programs()
```

### 3.3 Database Upgrade: SQLite → PostgreSQL

Ganti JSON file dengan PostgreSQL untuk:

```sql
-- Programs table
CREATE TABLE programs (
    slug            TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT,
    status          TEXT DEFAULT 'unknown',
    max_bounty      NUMERIC(20,2),
    min_bounty      NUMERIC(20,2),
    currency        TEXT DEFAULT 'USD',
    project_url     TEXT,
    logo            TEXT,
    tags            TEXT[],       -- PostgreSQL array
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    last_synced     TIMESTAMPTZ,
    commit_hash     TEXT,
    metadata        JSONB         -- Flexible extra data
);

-- Chains (many-to-many)
CREATE TABLE program_chains (
    program_slug    TEXT REFERENCES programs(slug),
    chain           TEXT,
    PRIMARY KEY (program_slug, chain)
);

-- Contracts
CREATE TABLE program_contracts (
    id              SERIAL PRIMARY KEY,
    program_slug    TEXT REFERENCES programs(slug),
    address         TEXT NOT NULL,
    chain           TEXT NOT NULL,
    name            TEXT,
    UNIQUE(program_slug, address, chain)
);

-- Repos
CREATE TABLE program_repos (
    id              SERIAL PRIMARY KEY,
    program_slug    TEXT REFERENCES programs(slug),
    url             TEXT NOT NULL,
    owner           TEXT,
    repo            TEXT,
    source          TEXT DEFAULT 'unknown',
    UNIQUE(program_slug, url)
);

-- Historical snapshots (track changes over time)
CREATE TABLE program_history (
    id              SERIAL PRIMARY KEY,
    program_slug    TEXT REFERENCES programs(slug),
    snapshot        JSONB,        -- Full program state at that time
    captured_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Sync log
CREATE TABLE sync_log (
    id              SERIAL PRIMARY KEY,
    sync_id         TEXT,
    status          TEXT,
    programs_total  INT DEFAULT 0,
    programs_synced INT DEFAULT 0,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error           TEXT
);
```

### 3.4 New Endpoints Level 1

```python
@router.get("/programs/{slug}/history")
async def get_program_history(slug: str, days: int = 30):
    """Lihat perubahan program dalam N hari terakhir."""
    pass

@router.get("/programs/{slug}/contracts")
async def get_program_contracts(slug: str):
    """List semua kontrak yang terkait dengan program."""
    pass

@router.get("/programs/chains")
async def list_chains():
    """List unique chains dari semua program."""
    pass

@router.get("/sync/schedule")
async def get_sync_schedule():
    """Lihat jadwal sync yang aktif."""
    pass

@router.put("/sync/schedule")
async def update_sync_schedule(schedule: SyncSchedule):
    """Update jadwal sync."""
    pass
```

---

## 4. Enhancement Level 2 — Intelligence (Minggu 2)

### 4.1 Smart Contract Auto-Fetch

Integrasi dengan **Service 03 (Source)** untuk auto-fetch semua kontrak:

```python
class ContractAutoFetcher:
    """Auto-fetch all contracts from all programs."""
    
    async def fetch_all_contracts(self):
        for program in self.active_programs:
            for contract in program.contracts:
                # Panggil Service 03
                source = await self.source_service.fetch(
                    chain=contract.chain,
                    address=contract.address,
                )
                if source:
                    # Cache di database kita
                    await self.save_contract_source(contract, source)
                    
                    # Trigger scan via orchestrator
                    await self.trigger_scan(program.slug, contract)
    
    async def trigger_scan(self, slug: str, contract: Contract):
        """Kirim ke orchestrator untuk full scan pipeline."""
        await self.orchestrator.submit({
            "source": contract.source,
            "chain": contract.chain,
            "address": contract.address,
            "program_slug": slug,
        })
```

### 4.2 Program Intelligence Scoring

Tambahkan scoring system untuk setiap program:

```python
class ProgramIntelligence:
    """Hitungan intelligence score untuk setiap program."""
    
    async def score(self, program: Program) -> ProgramScore:
        return ProgramScore(
            slug=program.slug,
            scores={
                "bounty_attractiveness": self._bounty_score(program),
                "contract_complexity": await self._complexity_score(program),
                "historical_payouts": await self._payout_score(program),
                "competition_level": self._competition_score(program),
                "tech_stack_suitability": self._tech_score(program),
                "total_tvl": await self._tvl_score(program),
            },
            overall_score=self._calculate_overall(),
            recommendation=self._recommend_action(),
        )
    
    def _bounty_score(self, program) -> float:
        """Higher bounty = higher score."""
        max_bounty = program.max_bounty or 0
        if max_bounty >= 1_000_000: return 1.0   # $1M+
        if max_bounty >= 100_000:   return 0.8   # $100k+
        if max_bounty >= 10_000:    return 0.5   # $10k+
        return 0.2
    
    async def _complexity_score(self, program) -> float:
        """Lebih kompleks = lebih menarik (lebih banyak bugs)."""
        contracts = await self.get_contracts(program.slug)
        if not contracts:
            return 0.5  # default
        
        complexity = 0
        for c in contracts:
            if c.lines_of_code > 1000:    complexity += 0.2
            if c.has_delegatecall:         complexity += 0.3
            if c.uses_assembly:            complexity += 0.2
            if len(c.functions) > 20:      complexity += 0.1
            if c.is_defi:                  complexity += 0.2
        
        return min(complexity, 1.0)
```

### 4.3 Trend Analysis & Anomaly Detection

```python
class ProgramTrendAnalyzer:
    """Deteksi tren dan anomali di program bounty."""
    
    async def analyze(self):
        return {
            "new_programs": await self.detect_new(),       # Program baru minggu ini
            "closed_programs": await self.detect_closed(), # Program yang ditutup
            "bounty_increases": await self.detect_bounty_changes(),
            "hot_chains": await self.hot_chains(),         # Chain dengan program terbanyak
            "emerging_categories": await self.emerging_categories(),
            "alert_if_high_value_new": await self.check_high_value_new(),
        }
    
    async def detect_new(self) -> list[Program]:
        """Program yang muncul dalam 7 hari terakhir."""
        return await self.db.query("""
            SELECT * FROM programs 
            WHERE created_at >= NOW() - INTERVAL '7 days'
            ORDER BY max_bounty DESC
        """)
    
    async def check_high_value_new(self) -> list[Alert]:
        """Alert jika program baru dengan bounty > $100k muncul."""
        new_high_value = await self.db.query("""
            SELECT * FROM programs
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            AND max_bounty >= 100000
        """)
        return [Alert(
            type="high_value_program",
            severity="high",
            message=f"New {p.name}: ${p.max_bounty:,.0f} bounty",
            program=p
        ) for p in new_high_value]
```

### 4.4 GitHub Repository Deep Intelligence

```python
class RepoDeepAnalyzer:
    """Analisis mendalam GitHub repository."""
    
    async def analyze(self, repo: Repo) -> RepoIntelligence:
        return RepoIntelligence(
            # Basic
            stars=await self._get_stargazers(repo),
            forks=await self._get_forks(repo),
            last_commit=await self._get_last_commit(repo),
            
            # Security
            open_issues=self._count_issue_labels(repo, ["bug", "security", "critical"]),
            dependabot_alerts=await self._get_dependabot_alerts(repo),
            codeql_findings=await self._get_codeql_findings(repo),
            
            # Development velocity
            commit_frequency=self._commits_per_week(repo, 90),  # 90 days
            contributors=await self._count_contributors(repo),
            test_coverage=self._estimate_test_coverage(repo),
            
            # Audit history
            previous_audits=await self._find_previous_audits(repo),
            audit_findings_count=await self._count_audit_findings(repo),
        )
```

### 4.5 New Endpoints Level 2

```python
@router.get("/programs/{slug}/intelligence")
async def get_program_intelligence(slug: str):
    """Full intelligence score untuk satu program."""
    pass

@router.get("/programs/recommendations")
async def get_program_recommendations(
    min_bounty: float = 10000,
    max_complexity: float = 0.3,
    chain: str = None,
):
    """Rekomendasi program berdasarkan preference."""
    pass

@router.get("/programs/trends")
async def get_trends(days: int = 30):
    """Trend analysis untuk semua program."""
    pass

@router.get("/programs/alerts")
async def get_alerts():
    """Alert untuk high-value programs baru."""
    pass

@router.post("/programs/{slug}/contracts/scan")
async def scan_program_contracts(slug: str):
    """Trigger full scan pipeline untuk semua kontrak di program."""
    pass
```

---

## 5. Enhancement Level 3 — Autonomous (Minggu 3)

### 5.1 Auto-Submission Pipeline

Integrasi dengan **Immunefi Official API** untuk auto-submit finding:

```python
class ImmunefiSubmissionBot:
    """Auto-submit finding ke Immunefi."""
    
    async def submit_finding(
        self,
        program_slug: str,
        finding: ExploitResult,
        poc: str,
    ) -> SubmissionResult:
        # 1. Validate finding
        validation = await self._validate_finding(finding)
        if not validation.passed:
            return SubmissionResult(rejected=True, reason=validation.reason)
        
        # 2. Prepare submission
        submission = {
            "program": program_slug,
            "title": finding.title,
            "description": finding.description,
            "severity": finding.severity,
            "vulnerability_classification": finding.attack_type,
            "proof_of_concept": poc,
            "affected_urls": [f"https://etherscan.io/address/{finding.contract_address}"],
            "assets": [{"type": "contract", "address": finding.contract_address}],
        }
        
        # 3. Submit via API
        api_key = await self.config.get_secret("immunefi_api_key")
        resp = await self.client.post(
            f"https://api.immunefi.com/v1/submissions",
            json=submission,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        
        # 4. Track submission
        await self._record_submission(program_slug, finding, resp)
        
        return SubmissionResult(
            success=resp.status_code == 201,
            submission_id=resp.json().get("id"),
            response=resp.json(),
        )
    
    async def _validate_finding(self, finding) -> Validation:
        """Pastikan finding memenuhi syarat Immunefi."""
        checks = []
        # Harus unique (tidak duplikat)
        checks.append(await self._check_duplicate(finding))
        # Harus reproducible
        checks.append(self._check_reproducible(finding))
        # Harus memiliki PoC yang valid
        checks.append(self._check_poc_valid(finding))
        # Severity minimal Medium
        checks.append(self._check_severity(finding, min="medium"))
        
        return Validation(
            passed=all(c.passed for c in checks),
            checks=checks,
        )
```

### 5.2 Competition Analysis

```python
class CompetitionIntelligence:
    """Analisis kompetisi antar bug hunter."""
    
    async def analyze_program_competition(self, slug: str) -> dict:
        """Lihat seberapa kompetitif suatu program."""
        
        # Metrics
        top_hunters = await self._get_top_hunters(slug, limit=10)
        avg_response_time = await self._get_avg_submission_time(slug)
        total_submissions = await self._count_submissions(slug, days=30)
        avg_payout = await self._get_avg_payout(slug)
        
        # Competition score
        if total_submissions == 0:
            competition = "no_competition"  # First mover advantage!
        elif total_submissions < 10:
            competition = "low"
        elif total_submissions < 50:
            competition = "medium"
        else:
            competition = "high"
        
        # Optimal strategy
        if competition == "high":
            strategy = "focus_on_deep_dive"  # Bugs yang orang lain lewatkan
        elif avg_response_time < 24:
            strategy = "speed_first"  # Cepat submit
        else:
            strategy = "quality_over_speed"  # Quality > speed
        
        return {
            "slug": slug,
            "competition_level": competition,
            "top_hunters": top_hunters,
            "avg_response_time_hours": avg_response_time,
            "submissions_last_30d": total_submissions,
            "recommended_strategy": strategy,
        }
```

### 5.3 Bounty Prediction using ML

```python
class BountyPredictor:
    """Prediksi bounty yang akan naik/turun."""
    
    def __init__(self):
        self.model = self._load_model()  # Trained XGBoost/RandomForest
    
    def _load_model(self):
        """Load trained model from disk."""
        import joblib
        return joblib.load("/models/bounty_predictor.pkl")
    
    def predict_bounty_change(self, program: Program) -> Prediction:
        """Prediksi apakah bounty akan naik dalam 30 hari."""
        features = {
            "current_bounty": program.max_bounty,
            "program_age_days": (datetime.now() - program.created_at).days,
            "total_contracts": len(program.contracts),
            "total_repos": len(program.repos),
            "has_recent_audit": self._has_recent_audit(program),
            "github_stars": self._get_github_stars(program),
            "github_commits_30d": self._get_recent_commits(program),
            "tvl_usd": self._get_tvl(program),
            "chain_popularity": self._get_chain_popularity(program),
            "num_competitors": self._count_competitors(program),
        }
        
        prediction = self.model.predict_proba([features])[0]
        
        return Prediction(
            program_slug=program.slug,
            will_increase=bool(prediction[1] > 0.7),
            probability=float(prediction[1]),
            estimated_new_bounty=program.max_bounty * (1 + prediction[1] * 0.5),
            confidence="high" if max(prediction) > 0.8 else "medium",
        )
    
    def _get_tvl(self, program) -> float:
        """Fetch TVL dari DeFiLlama API."""
        # Implementation with caching
        pass
```

### 5.4 New Endpoints Level 3

```python
@router.post("/programs/{slug}/submit")
async def auto_submit_finding(slug: str, finding_id: str):
    """Auto-submit finding ke Immunefi via API."""
    pass

@router.get("/programs/{slug}/competition")
async def get_program_competition(slug: str):
    """Analisis kompetisi untuk program."""
    pass

@router.get("/programs/{slug}/prediction")
async def predict_bounty(slug: str):
    """Prediksi perubahan bounty."""
    pass

@router.get("/submissions")
async def list_submissions(status: str = None):
    """List semua submission yang sudah dilakukan."""
    pass

@router.get("/submissions/{id}")
async def get_submission_status(id: str):
    """Cek status submission (pending/accepted/rejected)."""
    pass
```

---

## 6. Enhancement Level 4 — God-Tier (Minggu 4+)

### 6.1 Real-Time On-Chain Monitoring

```python
class OnChainBountyMonitor:
    """Monitor on-chain untuk bounty-related events."""
    
    async def start_monitoring(self):
        """Start background task untuk monitor events."""
        
        # 1. Listen ke event Immunefi contract
        immunefi_contracts = {
            "ethereum": "0x...ImmunefiContract",
            "polygon": "0x...ImmunefiContract",
        }
        
        for chain, address in immunefi_contracts.items():
            asyncio.create_task(self._listen_events(chain, address))
        
        # 2. Monitor new contract deployments
        asyncio.create_task(self._monitor_new_contracts())
        
        # 3. Monitor TVL changes via DeFiLlama
        asyncio.create_task(self._monitor_tvl_changes())
    
    async def _listen_events(self, chain: str, address: str):
        """Listen ke event smart contract Immunefi."""
        w3 = await self._get_web3(chain)
        
        event_signatures = [
            "BountyCreated(address,uint256)",
            "BountyClaimed(address,uint256,address)",
            "BountyCancelled(address,uint256)",
            "ProgramUpdated(bytes32)",
        ]
        
        for sig in event_signatures:
            event_filter = w3.eth.contract(
                address=address,
                abi=self._get_abi(sig),
            ).events[sig.split("(")[0]].create_filter(fromBlock="latest")
            
            # Process events in real-time
            async for event in event_filter.get_new_entries():
                await self._process_onchain_event(event)
    
    async def _monitor_tvl_changes(self):
        """Monitor TVL via DeFiLlama API — update setiap jam."""
        while True:
            for program in self.active_programs:
                for chain in program.chains:
                    tvl = await self._fetch_tvl(chain, program.contracts)
                    if tvl != program.tvl:
                        await self._record_tvl_change(program, tvl)
                        # Trigger alert if TVL drop > 10%
                        if program.tvl and abs(tvl - program.tvl) / program.tvl > 0.1:
                            await self._alert_tvl_drop(program, tvl)
            
            await asyncio.sleep(3600)  # Every hour
```

### 6.2 AI-Powered Program Matching

```python
class AISmartMatcher:
    """AI untuk mencocokkan auditor dengan program yang tepat."""
    
    async def find_best_programs(
        self,
        auditor_profile: AuditorProfile,
        limit: int = 10,
    ) -> list[MatchResult]:
        """Cari program terbaik untuk auditor tertentu."""
        
        # 1. Embedding-based similarity
        auditor_embedding = await self._embed(auditor_profile.specialization)
        program_embeddings = await self._get_all_program_embeddings()
        
        # Cosine similarity
        similarities = cosine_similarity(
            [auditor_embedding],
            program_embeddings,
        )[0]
        
        # 2. Weighted scoring
        scored = []
        for idx, program in enumerate(self._programs):
            score = (
                0.3 * similarities[idx] +                    # Match specialization
                0.2 * self._bounty_score(program) +          # Bounty amount
                0.2 * self._success_probability(program) +   # Chance of finding bugs
                0.15 * self._time_to_submission(program) +   # Time pressure
                0.15 * self._learning_value(program)          # What can we learn
            )
            scored.append(MatchResult(
                program=program,
                score=score,
                reasons=self._explain_match(program, score),
            ))
        
        return sorted(scored, key=lambda x: x.score, reverse=True)[:limit]
    
    async def _embed(self, text: str) -> list[float]:
        """Generate embedding via AI service (06-ai)."""
        resp = await self.ai_service.embed(text)
        return resp.embedding
```

### 6.3 Predictive Exploit Planning

Integrasi penuh dengan **Service 08 (Exploit)** dan **Service 11 (Orchestrator)**:

```python
class PredictiveExploitPlanner:
    """Predictive planning: tahu bug apa yang mungkin ada SEBELUM di-scan."""
    
    async def predict_vulnerabilities(self, program: Program) -> list[Prediction]:
        """Prediksi kerentanan berdasarkan data historis."""
        
        predictions = []
        
        for contract in program.contracts:
            # 1. Analisis pattern dari kontrak serupa
            similar_contracts = await self._find_similar(contract)
            common_bugs = self._extract_common_bugs(similar_contracts)
            
            # 2. Prioritas berdasarkan bounty
            for bug in common_bugs:
                if bug.severity == "critical" and program.max_bounty > 100000:
                    # Priority 1: critical bugs in high-value programs
                    predictions.append(Prediction(
                        contract=contract.address,
                        bug_type=bug.type,
                        probability=bug.frequency / len(similar_contracts),
                        estimated_payout=program.max_bounty * 0.3,  # 30% of max
                        action="scan_immediately",
                    ))
            
            # 3. Auto-trigger scan pipeline
            if predictions:
                await self.orchestrator.trigger_full_scan(
                    program_slug=program.slug,
                    contract=contract,
                    priority_bugs=[p.bug_type for p in predictions[:3]],
                )
        
        return predictions
```

### 6.4 God-Tier Dashboard Integration

Integrasi dengan **Service 15 (Dashboard)** untuk real-time visualisasi:

```python
# Endpoints baru untuk dashboard
@router.get("/dashboard/overview")
async def dashboard_overview():
    """Ringkasan untuk dashboard: total bounty, active programs, dll."""
    return {
        "total_active_programs": ...,
        "total_available_bounty": ...,
        "programs_by_chain": ...,
        "top_programs": ...,
        "recent_changes": ...,
        "alerts": ...,
    }

@router.get("/dashboard/map")
async def dashboard_map():
    """Heatmap chain vs bounty."""
    pass

@router.get("/dashboard/timeline")
async def dashboard_timeline(days: int = 90):
    """Timeline bounty changes."""
    pass
```

### 6.5 New Endpoints Level 4

```python
@router.websocket("/ws/programs")
async def websocket_program_updates():
    """Real-time updates via WebSocket."""
    pass

@router.get("/programs/{slug}/onchain/events")
async def get_onchain_events(slug: str, event_type: str = None):
    """On-chain events untuk program."""
    pass

@router.get("/matchmaking")
async def match_auditor_to_program(
    specialization: str = "defi",
    min_bounty: float = 50000,
):
    """AI matchmaking: cari program terbaik untuk auditor."""
    pass

@router.post("/programs/{slug}/predict")
async def predict_program_vulnerabilities(slug: str):
    """Prediksi kerentanan yang mungkin ada."""
    pass
```

---

## 7. Repository Forking Capability

### 7.1 Tujuan

Memungkinkan service 02 untuk **memforking seluruh repositori GitHub** dari program bounty blockchain/smart-contract ke akun GitHub pribadi. Ini bukan sekadar fetch — tapi clone penuh ke ownership kita.

### 7.2 Use Case di Pipeline Audit

```
Sebelum Fork:
  github.com/target/defi-protocol  (read-only, bisa dihapus owner)
  │
  └── Service 03 fetch source ─── rate limited, tergantung owner

Sesudah Fork:
  github.com/target/defi-protocol
       │
       └── github.com/kamu/defi-protocol  (fork — milik kamu)
              │
              ├── Service 03 fetch source  ✅ unlimited, cepat
              ├── Kamu edit source         ✅ testing fix
              ├── Kamu tambah test         ✅ verify patch
              └── Kamu buat PR             ✅ kontribusi whitehat
```

### 7.3 API yang Dibutuhkan

GitHub API endpoint untuk fork:

```
POST /repos/{owner}/{repo}/forks
Authorization: Bearer ghp_xxx

Response (202 Accepted):
{
  "name": "defi-protocol",
  "full_name": "kamu/defi-protocol",
  "fork": true,
  "clone_url": "https://github.com/kamu/defi-protocol.git",
  "default_branch": "main"
}
```

### 7.4 Implementasi

```python
# src/github_fork.py

class GitHubForkClient:
    """Client untuk operasi GitHub: fork, clone info, status."""

    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise RuntimeError(
                "GITHUB_TOKEN diperlukan. Set di environment variable "
                "atau via Service 01 Config."
            )
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.v3+json",
            },
            timeout=30.0,
        )

    async def fork_repo(self, owner: str, repo: str) -> dict:
        """Fork repo {owner}/{repo} ke akun GitHub terautentikasi.
        
        Jika sudah pernah di-fork, GitHub mengembalikan fork yang sudah ada.
        """
        resp = await self.client.post(
            f"https://api.github.com/repos/{owner}/{repo}/forks",
            json={"default_branch_only": True},
        )
        if resp.status_code == 202:
            return resp.json()
        elif resp.status_code == 403:
            raise PermissionError(
                "Rate limit atau token tidak memiliki akses. "
                "Butuh scope: repo / public_repo."
            )
        else:
            raise Exception(f"Fork gagal: {resp.status_code} {resp.text}")

    async def fork_multiple(self, repos: list[dict]) -> list[dict]:
        """Batch fork banyak repo sekaligus."""
        results = []
        for repo in repos:
            try:
                result = await self.fork_repo(repo["owner"], repo["repo"])
                results.append({
                    "original": f"{repo['owner']}/{repo['repo']}",
                    "fork": result["full_name"],
                    "clone_url": result["clone_url"],
                    "status": "success",
                })
            except Exception as e:
                results.append({
                    "original": f"{repo['owner']}/{repo['repo']}",
                    "status": "failed",
                    "error": str(e),
                })
        return results

    async def check_fork_exists(self, owner: str, repo: str) -> bool:
        """Cek apakah repo ini sudah pernah di-fork ke akun kita."""
        username = await self._get_username()
        resp = await self.client.get(
            f"https://api.github.com/repos/{username}/{repo}"
        )
        return resp.status_code == 200

    async def _get_username(self) -> str:
        """Ambil username dari token yang digunakan."""
        resp = await self.client.get("https://api.github.com/user")
        resp.raise_for_status()
        return resp.json()["login"]

    async def close(self):
        await self.client.aclose()
```

### 7.5 Endpoint Baru

```python
@router.post("/programs/{slug}/fork")
async def fork_program_repos(slug: str):
    """Fork semua repositori dari suatu program bounty.
    
    Contoh: fork repo dari program "euler-finance"
    → github.com/kamu/euler-finance
    → github.com/kamu/euler-contracts
    """
    program = sync_manager.programs.get(slug)
    if not program:
        raise HTTPException(404, "Program not found")
    
    github = GitHubForkClient()
    repos_data = [
        {"owner": r.owner, "repo": r.repo}
        for r in program.repos
        if r.owner and r.repo
    ]
    
    if not repos_data:
        raise HTTPException(400, "Program has no detectable GitHub repos")
    
    results = await github.fork_multiple(repos_data)
    await github.close()
    
    return ok({
        "program": slug,
        "program_name": program.name,
        "total_repos": len(repos_data),
        "successful": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "results": results,
    })


@router.get("/programs/{slug}/forks")
async def list_program_forks(slug: str):
    """Lihat status fork dari semua repo program."""
    program = sync_manager.programs.get(slug)
    if not program:
        raise HTTPException(404, "Program not found")
    
    github = GitHubForkClient()
    username = await github._get_username()
    
    forks = []
    for repo in program.repos:
        if not repo.owner or not repo.repo:
            continue
        try:
            resp = await github.client.get(
                f"https://api.github.com/repos/{repo.owner}/{repo.repo}/forks"
            )
            user_forks = [
                f for f in resp.json()
                if f["owner"]["login"] == username
            ]
            forks.append({
                "original": f"{repo.owner}/{repo.repo}",
                "forked": len(user_forks) > 0,
                "fork_url": user_forks[0]["clone_url"] if user_forks else None,
                "fork_owner": username if user_forks else None,
            })
        except Exception as e:
            forks.append({
                "original": f"{repo.owner}/{repo.repo}",
                "forked": False,
                "error": str(e),
            })
    
    await github.close()
    return ok({
        "program": slug,
        "total_repos": len(program.repos),
        "forks": forks,
    })


@router.delete("/programs/{slug}/forks")
async def delete_program_forks(slug: str):
    """Hapus fork repo (via GitHub API — butuh token dengan scope delete_repo)."""
    # Memanggil API DELETE /repos/{owner}/{repo}
    pass
```

### 7.6 Token & Keamanan

| Aspek | Detail |
|-------|--------|
| **Token type** | GitHub Personal Access Token (classic) |
| **Scope minimal** | `public_repo` (untuk fork repo public) |
| **Scope penuh** | `repo` (jika perlu fork private repo) |
| **Penyimpanan** | Via Service 01 Config (`/secrets/github_token`) + fallback env var |
| **Rate limit** | 5,000 request/jam (dengan token) vs 60/jam (anonymous) |
| **Rotasi** | Bisa ganti token kapan saja via Config Service tanpa restart |

### 7.7 Integrasi dengan Service 03 (Source)

Fork memungkinkan Service 03 fetch source **dari repo fork sendiri** — lebih cepat dan tidak kena rate limit:

```python
class ForkAwareSourceProvider:
    """Provider yang cek fork dulu sebelum fetch dari original."""
    
    async def fetch(self, chain: str, address: str) -> SourceResult:
        # 1. Cek di database: apakah kontrak ini punya repo GitHub?
        repo_info = await self._get_repo_for_contract(chain, address)
        
        if repo_info:
            # 2. Apakah repo sudah di-fork?
            fork_url = await self._check_fork(repo_info.owner, repo_info.repo)
            
            if fork_url:
                # 3. Fetch dari fork (cepat, unlimited)
                return await self._fetch_from_github(fork_url)
        
        # 4. Fallback: provider normal (Etherscan, dll)
        return await super().fetch(chain, address)
```

### 7.8 Integrasi dengan Service 08 (Exploit)

Setelah fork, exploit engine bisa push PoC langsung ke repo fork:

```python
class ExploitPusher:
    """Push PoC exploit ke repo fork untuk dokumentasi."""
    
    async def push_poc_to_fork(self, finding_id: str, poc_code: str):
        """Push PoC sebagai file ke repo fork."""
        # 1. Dapatkan info fork dari database
        fork_info = await self.db.get_fork_for_finding(finding_id)
        
        # 2. Buat file PoC di branch baru
        github = GitHubForkClient()
        await github.client.put(
            f"https://api.github.com/repos/{fork_info['fork_full_name']}/"
            f"contents/pocs/{finding_id}.t.sol",
            json={
                "message": f"PoC: {finding_id}",
                "content": base64.b64encode(poc_code.encode()).decode(),
                "branch": f"poc/{finding_id}",
            },
        )
        await github.close()
```

### 7.9 Level Penerapan

| Level | Kemampuan Fork | SP |
|-------|---------------|----|
| **L1 — Basic Fork** | Fork single repo + endpoint `POST /programs/{slug}/fork` | 5 |
| **L2 — Batch Fork** | Fork semua repo semua program + `GET /programs/{slug}/forks` | 8 |
| **L3 — Smart Fork** | Auto-fork program baru + integrasi dengan 03 + 08 | 13 |
| **L4 — Fork Management** | Delete fork, sync fork, branch management, PR creation | 21 |
| **Total** | | **47 SP** |

---

## 8. Roadmap & Dependencies

```
Minggu 1 (Foundation)          Minggu 3 (Autonomous)
┌────────────────┐            ┌────────────────┐
│ Multi-source    │            │ Auto-submission │
│ DB upgrade      │            │ Competition     │
│ Auto sync       │            │ ML prediction   │
│ New endpoints   │            │ WebSocket       │
└────────┬───────┘            └────────┬───────┘
         │                             │
         ▼                             ▼
Minggu 2 (Intelligence)       Minggu 4 (God-Tier)
┌────────────────┐            ┌────────────────┐
│ Contract fetch  │            │ On-chain monitor│
│ Scoring engine  │            │ AI matching     │
│ Trend analysis  │            │ Predictive      │
│ Repo deep dive  │            │ Dashboard       │
└────────────────┘            └────────────────┘
```

### Dependencies Cross-Service

| Enhancement | Dependent On | Service |
|-------------|-------------|---------|
| Contract auto-fetch | Source Service | 03 |
| Scan trigger | Orchestrator | 11 |
| AI matching | AI Service | 06 |
| Auto-submit | Config (API keys) | 01 |
| Dashboard | Dashboard Service | 15 |
| Exploit prediction | Exploit Engine | 08 |
| TVL data | DeFiLlama (external) | — |
| Repository fork | GitHub Token (Config 01) | 01 |
| Fork + Source | GitHub + Source Service | 03 |
| Fork + PoC push | GitHub + Exploit Engine | 08 |

### Effort Estimation

| Level | Story Points | Man-Days | Risk |
|-------|-------------|----------|------|
| Level 1 (Foundation) | 21 SP | 10-12 | Low |
| Level 2 (Intelligence) | 34 SP | 15-18 | Medium |
| Level 3 (Autonomous) | 55 SP | 25-30 | High |
| Level 4 (God-Tier) | 89 SP | 40-50 | Very High |
| Fork L1 (Basic Fork) | 5 SP | 2-3 | Low |
| Fork L2 (Batch Fork) | 8 SP | 3-4 | Low |
| Fork L3 (Smart Fork) | 13 SP | 5-7 | Medium |
| Fork L4 (Fork Mgmt) | 21 SP | 8-12 | Medium |
| **Total** | **~246 SP** | **108-136** | |

---

> **Catatan**: Enhancement ini mengubah service 02 dari **passive data fetcher** menjadi **active intelligence platform** yang tidak hanya menyediakan data, tapi juga menganalisis, memprediksi, dan bahkan mengambil tindakan secara otonom.
