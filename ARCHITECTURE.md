# SC Auditor Platform — Detailed Architecture

> **Status**: Brainstorming (Belum Eksekusi)
> **Dokumen Ini**: API Contracts, Event Schema, Database Schema per Service
> **Tanggal**: 17 Mei 2026

---

## Table of Contents

1. [API Contracts (gRPC Protobuf)](#1-api-contracts-grpc-protobuf)
2. [Event Schema (Message Queue)](#2-event-schema-message-queue)
3. [Database Schema per Service](#3-database-schema-per-service)
4. [End-to-End Pipeline Flow](#4-end-to-end-pipeline-flow)
5. [Immunefi Data Model](#5-immunefi-data-model)
6. [Proto File Structure](#6-proto-file-structure)
7. [Bug Classification System](#7-bug-classification-system)
8. [Matured Decisions](#8-matured-decisions)

---

## 1. API Contracts (gRPC Protobuf)

Setiap service mengekspos gRPC endpoint. REST gateway juga bisa di-generate dari proto yang sama.

### 1.1 Auth Service

```protobuf
syntax = "proto3";
package scauditor.auth.v1;

service AuthService {
  // User Management
  rpc CreateUser(CreateUserRequest) returns (CreateUserResponse);
  rpc GetUser(GetUserRequest) returns (User);
  rpc UpdateUser(UpdateUserRequest) returns (User);
  rpc DeleteUser(DeleteUserRequest) returns (Empty);

  // Authentication
  rpc Authenticate(AuthRequest) returns (AuthResponse);
  rpc ValidateToken(ValidateTokenRequest) returns (ValidateTokenResponse);
  rpc RefreshToken(RefreshTokenRequest) returns (AuthResponse);
  rpc RevokeToken(RevokeTokenRequest) returns (Empty);

  // API Keys
  rpc CreateApiKey(CreateApiKeyRequest) returns (ApiKey);
  rpc ListApiKeys(ListApiKeysRequest) returns (ListApiKeysResponse);
  rpc RevokeApiKey(RevokeApiKeyRequest) returns (Empty);

  // RBAC
  rpc AssignRole(AssignRoleRequest) returns (Empty);
  rpc CheckPermission(CheckPermissionRequest) returns (CheckPermissionResponse);
  rpc ListRoles(ListRolesRequest) returns (ListRolesResponse);
}

message User {
  string id = 1;
  string email = 2;
  string display_name = 3;
  repeated string roles = 4;
  bool email_verified = 5;
  int64 created_at = 6;
  int64 updated_at = 7;
}

message AuthRequest {
  string email = 1;
  string password_hash = 2;
  optional string mfa_code = 3;
}

message AuthResponse {
  string access_token = 1;
  string refresh_token = 2;
  int64 expires_at = 3;
  User user = 4;
}

message ValidateTokenRequest {
  string access_token = 1;
}

message ValidateTokenResponse {
  bool valid = 1;
  string user_id = 2;
  repeated string roles = 3;
  optional string error = 4;
}

message CheckPermissionRequest {
  string user_id = 1;
  string permission = 2;    // e.g., "project:create", "audit:start"
  optional string resource_id = 3;
}

message CheckPermissionResponse {
  bool allowed = 1;
}
```

### 1.2 Immunefi Scraper Service

```protobuf
syntax = "proto3";
package scauditor.immunefi.v1;

service ImmunefiScraperService {
  // Sync
  rpc TriggerSync(SyncTrigger) returns (SyncStatus);
  rpc GetSyncStatus(Empty) returns (SyncStatus);

  // Programs
  rpc ListPrograms(ListProgramsRequest) returns (ListProgramsResponse);
  rpc GetProgram(GetProgramRequest) returns (ImmunefiProgram);
  rpc SearchPrograms(SearchProgramsRequest) returns (ListProgramsResponse);

  // Contracts
  rpc ListContracts(ListContractsRequest) returns (ListContractsResponse);
  rpc GetContract(GetContractRequest) returns (ContractInfo);

  // Stats
  rpc GetStats(Empty) returns (ImmunefiStats);

  // Contracts pending audit
  rpc GetPendingContracts(PendingContractsRequest) returns (PendingContractsResponse);
}

service ImmunefiContractService {
  // Source code fetching
  rpc FetchSourceCode(FetchSourceRequest) returns (FetchSourceResponse);
  rpc GetCachedSource(GetSourceRequest) returns (SourceCode);
}

message ImmunefiProgram {
  string id = 1;
  string slug = 2;
  string name = 3;
  string logo_url = 4;
  string website = 5;
  // Bounty
  double max_bounty_usd = 6;
  string reward_type = 7;       // USDC, ETH, etc.
  bool kyc_required = 8;
  repeated string poc_required_for = 9;  // ["critical", "high", "medium"]
  // Scope
  repeated ContractAsset assets = 10;
  repeated string chains = 11;
  // Features
  repeated string features = 12;  // Managed Triage, Arbitration, etc.
  // Status
  string status = 13;           // active, paused, closed
  int64 added_at = 14;
  int64 last_updated = 15;
  // References
  repeated string previous_audits = 16;
  repeated string known_issues = 17;
  string safe_harbor = 18;
}

message ContractAsset {
  string address = 1;
  string chain = 2;
  string name = 3;
  string description = 4;
  string asset_type = 5;       // smart_contract, etc.
  string etherscan_url = 6;
  string source_type = 7;      // verified, unverified, proxy
  bool is_verified = 8;
}

message ImmunefiStats {
  int32 total_programs = 1;
  int32 active_programs = 2;
  int32 total_contracts = 3;
  double total_max_bounty = 4;
  // per chain
  map<string, int32> contracts_per_chain = 5;
  // top 10 by bounty
  repeated ImmunefiProgram top_programs = 6;
  int32 last_sync_at = 7;
}

message ListProgramsRequest {
  int32 page = 1;
  int32 page_size = 2;
  optional string sort_by = 3;     // bounty, name, updated
  optional string chain_filter = 4;
  optional string status_filter = 5;
  optional bool poc_required = 6;
}

message PendingContractsRequest {
  repeated string vulnerabilities = 1;  // prefer contracts with known vuln patterns
  double min_bounty = 2;
  repeated string chains = 3;
}
```

### 1.3 Orchestrator Service

```protobuf
syntax = "proto3";
package scauditor.orchestrator.v1;

service OrchestratorService {
  // Pipeline lifecycle
  rpc StartAudit(StartAuditRequest) returns (AuditSession);
  rpc GetAuditStatus(GetAuditRequest) returns (AuditSession);
  rpc CancelAudit(CancelAuditRequest) returns (Empty);
  rpc ListAudits(ListAuditsRequest) returns (ListAuditsResponse);

  // Pipeline management
  rpc GetPipelineDefinition(Empty) returns (PipelineDefinition);
  rpc UpdatePipelineConfig(UpdatePipelineConfigRequest) returns (PipelineDefinition);

  // Real-time progress
  rpc StreamAuditProgress(GetAuditRequest) returns (stream AuditEvent);
}

service SkillDispatchService {
  rpc DispatchSkills(DispatchRequest) returns (DispatchResponse);
  rpc GetSkillResult(GetSkillResultRequest) returns (SkillResult);
}

message StartAuditRequest {
  string project_id = 1;
  repeated string contract_ids = 2;    // contract addresses to audit
  string immunefi_program_id = 3;
  optional PipelineConfig config = 4;
}

message AuditSession {
  string session_id = 1;
  string project_id = 2;
  string immunefi_program_id = 3;
  AuditStatus status = 4;
  repeated PipelineStep steps = 5;
  int64 started_at = 6;
  optional int64 completed_at = 7;
  optional string error = 8;
}

message PipelineStep {
  string name = 1;           // static-analysis, exploit, ai-analysis, etc.
  StepStatus status = 2;     // pending, running, completed, failed, skipped
  optional int64 started_at = 3;
  optional int64 completed_at = 4;
  optional string result_ref = 5;   // reference to result data
  optional string error = 6;
}

message AuditEvent {
  string session_id = 1;
  string step = 2;
  string event_type = 3;     // started, progress, completed, failed
  string message = 4;
  int32 progress_pct = 5;
  optional string payload_json = 6;
}

message PipelineDefinition {
  repeated Stage stages = 1;
  int32 max_concurrent_scans = 2;
  bool auto_exploit = 3;
  bool auto_gas_analysis = 4;
  repeated string required_skills = 5;
}

message Stage {
  string name = 1;
  string service = 2;           // service to call
  repeated string depends_on = 3;  // stage names this depends on
  string timeout_seconds = 4;
  bool optional = 5;
}

enum AuditStatus {
  AUDIT_STATUS_UNSPECIFIED = 0;
  AUDIT_STATUS_PENDING = 1;
  AUDIT_STATUS_RUNNING = 2;
  AUDIT_STATUS_COMPLETED = 3;
  AUDIT_STATUS_FAILED = 4;
  AUDIT_STATUS_CANCELLED = 5;
}

enum StepStatus {
  STEP_STATUS_UNSPECIFIED = 0;
  STEP_STATUS_PENDING = 1;
  STEP_STATUS_RUNNING = 2;
  STEP_STATUS_COMPLETED = 3;
  STEP_STATUS_FAILED = 4;
  STEP_STATUS_SKIPPED = 5;
}
```

### 1.4 Static Analysis Service

```protobuf
syntax = "proto3";
package scauditor.static_analysis.v1;

service StaticAnalysisService {
  rpc RunScan(RunScanRequest) returns (ScanSession);
  rpc GetScanResult(GetScanRequest) returns (ScanResult);
  rpc ListScans(ListScansRequest) returns (ListScansResponse);
  rpc GetSupportedTools(Empty) returns (SupportedTools);
  rpc RunCustomTool(RunCustomToolRequest) returns (ScanSession);
}

message RunScanRequest {
  string source_url = 1;         // URL ke Storage Service
  string contract_address = 2;
  string chain = 3;
  repeated string tools = 4;     // ["slither", "mythril", "echidna"]
  optional string compiler_version = 5;
  optional map<string, string> tool_config = 6;
}

message ScanSession {
  string scan_id = 1;
  string status = 2;
  repeated string tools_running = 3;
  int64 started_at = 4;
}

message ScanResult {
  string scan_id = 1;
  string contract_address = 2;
  repeated Finding findings = 3;
  map<string, ToolOutput> tool_outputs = 4;
  int64 completed_at = 5;
  int32 duration_seconds = 6;
}

message Finding {
  string id = 1;
  string tool = 2;              // slither, mythril, echidna
  string title = 3;
  string description = 4;
  string severity = 5;          // critical, high, medium, low, informational
  double confidence = 6;        // 0.0 - 1.0
  string file = 7;
  int32 line_start = 8;
  int32 line_end = 9;
  string code_snippet = 10;
  string impact = 11;
  string recommendation = 12;
  repeated string references = 13;
  string swc_id = 14;           // SWC Registry ID
  string cwe_id = 15;           // CWE ID
}

message ToolOutput {
  string raw_output = 1;
  bool success = 2;
  optional string error = 3;
  int32 duration_seconds = 4;
}
```

### 1.5 Exploit Engine Service

```protobuf
syntax = "proto3";
package scauditor.exploit.v1;

service ExploitEngineService {
  rpc StartExploitSession(StartExploitRequest) returns (ExploitSession);
  rpc GetSessionStatus(GetExploitRequest) returns (ExploitSession);
  rpc ExecuteExploit(ExecuteExploitRequest) returns (ExploitResult);
  rpc StopExploit(StopExploitRequest) returns (Empty);
  rpc GetPoolStatus(Empty) returns (PoolStatus);
  rpc ListSessions(ListSessionsRequest) returns (ListSessionsResponse);
}

message StartExploitRequest {
  string contract_address = 1;
  string chain = 2;
  int32 fork_block = 3;          // block number to fork at
  string source_code_url = 4;
  repeated Vulnerability findings = 5;  // findings to test
  optional string rpc_endpoint = 6;     // archived node RPC
}

message ExploitSession {
  string session_id = 1;
  string status = 2;             // pending, forking, ready, executing, completed, failed
  string anvil_endpoint = 3;     // internal: http://anvil:8545
  int32 block_forked = 4;
  string chain_id = 5;
  int64 started_at = 6;
  PoolInstanceInfo instance = 7;
}

message ExecuteExploitRequest {
  string session_id = 1;
  string exploit_code = 2;       // Solidity/ethers.js exploit script
  repeated string accounts_to_impersonate = 3;
  optional uint64 eth_balance = 4;  // ETH to give impersonated account
  optional int32 gas_limit = 5;
}

message ExploitResult {
  string session_id = 1;
  bool exploit_successful = 2;
  string tx_hash = 3;
  string transaction_trace = 4;  // detailed trace
  int64 gas_used = 5;
  string state_diff = 6;         // state changes
  optional string error = 7;
  repeated ExploitAttempt attempts = 8;
}

message ExploitAttempt {
  int32 attempt_number = 1;
  string technique = 2;          // reentrancy, flash-loan, etc.
  bool success = 3;
  string result_summary = 4;
  int64 gas_used = 5;
}

message PoolInstanceInfo {
  string instance_id = 1;
  string container_id = 2;
  PoolStatus status = 3;
  int32 uptime_seconds = 4;
  int64 memory_used_mb = 5;
}
```

### 1.6 AI Analysis Service

```protobuf
syntax = "proto3";
package scauditor.ai.v1;

service AIAnalysisService {
  rpc AnalyzeVulnerabilities(AnalyzeRequest) returns (AnalyzeResponse);
  rpc GetAnalysisResult(GetAnalysisRequest) returns (AnalysisResult);
  rpc ReAnalyze(ReAnalyzeRequest) returns (AnalyzeResponse);
  rpc GenerateFixRecommendation(FixRequest) returns (FixResponse);
}

message AnalyzeRequest {
  string scan_id = 1;
  repeated StaticFinding scan_findings = 2;
  string source_code = 3;
  repeated PatternMatch pattern_matches = 4;
  optional AnalysisConfig config = 5;
}

message AnalysisResult {
  string analysis_id = 1;
  repeated AIVerdict verdicts = 2;
  string overall_assessment = 3;
  double risk_score = 4;        // 0-100
  string summary = 5;
  int64 processed_at = 6;
  string model_used = 7;
}

message AIVerdict {
  string finding_id = 1;
  bool confirmed = 2;
  double confidence = 3;        // 0.0 - 1.0
  string severity_reassessment = 4;  // up/down/same
  string reasoning = 5;
  optional string exploit_scenario = 6;
  optional string fix_recommendation = 7;
  double estimated_financial_impact = 8;  // USD if exploited
}

message FixRequest {
  string source_code = 1;
  string vulnerability_description = 2;
}

message FixResponse {
  string fixed_code = 1;
  string diff = 2;
  string explanation = 3;
  bool verified = 4;
}
```

### 1.7 Report Service

```protobuf
syntax = "proto3";
package scauditor.report.v1;

service ReportService {
  rpc GenerateReport(GenerateReportRequest) returns (Report);
  rpc GetReport(GetReportRequest) returns (Report);
  rpc ListReports(ReportsListRequest) returns (ListReportsResponse);
  rpc ExportReport(ExportReportRequest) returns (ExportResponse);
  rpc GetReportTemplate(GetTemplateRequest) returns (ReportTemplate);
  rpc ListTemplates(Empty) returns (ListTemplatesResponse);
}

message GenerateReportRequest {
  string audit_session_id = 1;
  string project_id = 2;
  string format = 3;              // pdf, html, md, json
  optional string template_id = 4;
  repeated string sections = 5;   // include only specific sections
}

message Report {
  string report_id = 1;
  string project_id = 2;
  string audit_session_id = 3;
  string title = 4;
  string format = 5;
  string immunefi_program_id = 6;
  // Sections
  string executive_summary = 7;
  repeated FindingReport findings = 8;
  double overall_score = 9;
  string risk_assessment = 10;
  string recommendations = 11;
  // Metadata
  int64 generated_at = 12;
  int32 total_findings = 13;
  int32 critical_count = 14;
  int32 high_count = 15;
  int32 medium_count = 16;
  int32 low_count = 17;
  optional string exported_url = 18;
}

message FindingReport {
  string id = 1;
  string title = 2;
  string severity = 3;
  string status = 4;           // confirmed, false_positive, unconfirmed
  string description = 5;
  string impact = 6;
  string exploit_scenario = 7;
  string proof_of_concept = 8;
  string recommendation = 9;
  string code_location = 10;
  string cwe_id = 11;
  double cvss_score = 12;
}

message ExportReportRequest {
  string report_id = 1;
  string format = 2;
}

message ExportResponse {
  string download_url = 1;
  int64 file_size_bytes = 2;
  string content_type = 3;
}
```

---

## 2. Event Schema (Message Queue)

Menggunakan **NATS** (JetStream) karena ringan dan persistent. Topics menggunakan format: `scauditor.{domain}.{event}`

### 2.1 Event Topics

```
┌─────────────────────────────────────────────────────────────────────┐
│                    NATS JETSTREAM TOPICS                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  IMMUNEFI DOMAIN:                                                  │
│  ───────────────                                                   │
│  scauditor.immunefi.program.synced      → Program baru/update      │
│  scauditor.immunefi.contract.detected   → Contract baru in-scope   │
│  scauditor.immunefi.program.closed      → Program ditutup          │
│                                                                    │
│  PROJECT DOMAIN:                                                   │
│  ───────────────                                                   │
│  scauditor.project.created              → Project auto-created     │
│  scauditor.project.contracts_ready      → All contracts fetched    │
│  scauditor.project.updated              → Project status change    │
│                                                                    │
│  AUDIT DOMAIN:                                                     │
│  ────────────                                                      │
│  scauditor.audit.requested              → New audit requested      │
│  scauditor.audit.started                → Orchestrator mulai       │
│  scauditor.audit.step.completed         → Satu stage selesai       │
│  scauditor.audit.progress               → Progress update (N%)     │
│  scauditor.audit.completed              → Audit selesai            │
│  scauditor.audit.failed                 → Audit gagal              │
│  scauditor.audit.cancelled              → Audit dibatalkan         │
│                                                                    │
│  ANALYSIS DOMAIN:                                                  │
│  ───────────────                                                   │
│  scauditor.scan.completed               → Static scan selesai      │
│  scauditor.patterns.matched             → Vuln DB match selesai    │
│  scauditor.ai.analyzed                  → AI analysis selesai      │
│  scauditor.exploit.completed            → Exploit test selesai     │
│  scauditor.gas.analyzed                 → Gas analysis selesai     │
│  scauditor.skills.evaluated             → Skill eval selesai       │
│                                                                    │
│  REPORT DOMAIN:                                                    │
│  ─────────────                                                      │
│  scauditor.report.generated             → Report siap              │
│  scauditor.report.exported              → PDF/HTML exported        │
│                                                                    │
│  NOTIFICATION DOMAIN:                                              │
│  ──────────────────                                                │
│  scauditor.notification.sent            → Notif terkirim           │
│  scauditor.notification.failed          → Notif gagal              │
│                                                                    │
│  ERROR DOMAIN:                                                     │
│  ────────────                                                      │
│  scauditor.error.service_unavailable    → Service down             │
│  scauditor.error.pipeline_timeout       → Stage timeout            │
│  scauditor.error.dead_letter            → Unprocessable message    │
│                                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Event Message Format

Semua event menggunakan envelope format yang sama:

```json
{
  "id": "evt_abc123",
  "type": "scauditor.audit.step.completed",
  "source": "orchestrator-service",
  "correlation_id": "audit_sess_xyz789",
  "timestamp": 1717890123,
  "version": 1,
  "data": { /* per-event payload */ },
  "metadata": {
    "trace_id": "trace_xxx",
    "user_id": "user_abc",
    "project_id": "proj_123",
    "session_id": "audit_sess_xyz789",
    "service_version": "1.2.0"
  }
}
```

### 2.3 Key Event Payloads

**audit.requested** — Trigger pipeline dimulai
```json
{
  "type": "scauditor.audit.requested",
  "data": {
    "session_id": "audit_sess_xyz789",
    "project_id": "proj_123",
    "immunefi_program_id": "ethena",
    "contract_addresses": [
      "0x4c9edd5852cd905f086c759e8383e09bff1e68b3",
      "0x2b1d5c8b3e3d9f0a1c2b3d4e5f6a7b8c9d0e1f2a"
    ],
    "chain": "ethereum",
    "config": {
      "auto_exploit": true,
      "auto_gas_analysis": true,
      "include_skills": ["owasp", "reentrancy", "flash-loan"]
    },
    "max_bounty_usd": 3000000
  }
}
```

**scan.completed** — Static analysis selesai
```json
{
  "type": "scauditor.scan.completed",
  "data": {
    "scan_id": "scan_456",
    "session_id": "audit_sess_xyz789",
    "contract_address": "0x4c9edd5852cd905f086c759e8383e09bff1e68b3",
    "tools_run": ["slither", "mythril"],
    "findings_count": 5,
    "critical_count": 1,
    "high_count": 2,
    "medium_count": 1,
    "low_count": 1,
    "result_ref": "storage://scans/scan_456/result.json",
    "duration_seconds": 127
  }
}
```

**exploit.completed** — Exploit test selesai
```json
{
  "type": "scauditor.exploit.completed",
  "data": {
    "session_id": "exploit_sess_321",
    "audit_session_id": "audit_sess_xyz789",
    "vulnerability_tested": "Reentrancy in withdraw()",
    "exploit_successful": true,
    "tx_hash": "0xabcd...1234",
    "gas_used": 89432,
    "value_at_risk_usd": 1250000,
    "poC_available": true,
    "result_ref": "storage://exploits/exploit_321/result.json"
  }
}
```

### 2.4 Pipeline Orchestration Flow

```
NATS STREAMS: scauditor_audit_pipeline

[audit.requested] ────▶ Orchestrator memproses
       │
       ▼
[audit.started] ──────▶ Notifikasi ke WS/SSE
       │
       ▼  Dispatch ke Static Analysis Service
[scan.completed] ──────▶ Orchestrator mengecek
       │
       ├──▶ [patterns.matched] ──▶ Vuln DB matching
       │         │
       │         ▼
       │    [ai.analyzed] ──────▶ AI verdict
       │         │
       │         ▼
       │    [exploit.completed] ──▶ Jika confirm+berbahaya
       │         │
       │         ▼
       │    [gas.analyzed] ──────▶ Gas optimization
       │
       ▼
[report.generated] ────▶ Report Service kompilasi
       │
       ▼
[audit.completed] ──────▶ Delivery + notify user
```

---

## 3. Database Schema per Service

### 3.1 Auth Service — JSON Storage

> Sesuai VYPER.md §3a — 100% JSON file-based, zero SQL.

```json
/data/auth/
├── users/{user_id}.json              # Per-user data
│       { "id": "uuid", "email": "...", "display_name": "...",
│         "password_hash": "...", "email_verified": true,
│         "mfa_enabled": false, "avatar_url": null,
│         "created_at": "...", "updated_at": "...", "deleted_at": null }
├── roles.json                        # All roles in one file
├── api_keys/{user_id}/{key_id}.json  # Per-API key
├── sessions/{token_hash}.json        # Per-session
├── audit_log/{date}.jsonl            # JSON Lines append-only
├── indexes/
│   ├── by_email.json                 # email → user_id mapping
│   ├── by_role.json                  # role → [user_id, ...]
│   └── by_user.json                  # user_id → [role_id, ...]
└── _meta.json                        # Schema version, stats
```

### 3.2 Immunefi Scraper Service — JSON Storage

```json
/data/immunefi/
├── programs/{slug}.json              # Per-program
│       { "slug": "...", "name": "...", "max_bounty_usd": 1000000,
│         "reward_type": "USDC", "status": "active",
│         "features": [...], "safe_harbor": "...",
│         "added_at": "...", "last_updated": "..." }
├── contracts/{chain}_{address}.json  # Per-contract
├── history/{slug}.jsonl              # JSON Lines append-only
├── sync_log.jsonl                    # Sync history (JSON Lines)
├── indexes/
│   ├── by_chain.json                 # chain → [slug, ...]
│   ├── by_status.json                # status → [slug, ...]
│   ├── by_bounty.json                # range → [slug, ...]
│   └── by_recent.json                # ordered by last_updated
└── _meta.json                        # Schema version, last synced
```

### 3.3 Project Service — JSON Storage

```json
/data/project/
├── projects/{project_id}.json            # Per-project
│       { "id": "uuid", "name": "...", "chain": "ethereum",
│         "status": "active", "total_contracts": 5,
│         "scanned_contracts": 3, "overall_score": 7.5,
│         "created_at": "...", "updated_at": "..." }
├── contracts/{project_id}/{contract_id}.json  # Per-contract in project
├── tags/{project_id}/{tag_name}.json     # Per-tag
├── indexes/
│   ├── by_owner.json                     # owner_id → [project_id, ...]
│   ├── by_status.json                    # status → [project_id, ...]
│   └── by_immunefi.json                  # program_id → project_id
└── _meta.json
```

### 3.4 Static Analysis Service — JSON Storage

```json
/data/scanner/
├── scans/{scan_id}.json                    # Per-scan
│       { "id": "uuid", "session_id": "...", "contract_address": "0x...",
│         "chain": "ethereum", "tools_used": ["slither", "mythril"],
│         "status": "completed", "total_findings": 5,
│         "critical_count": 1, "high_count": 2,
│         "started_at": "...", "completed_at": "..." }
├── findings/{scan_id}/{finding_id}.json    # Per-finding
├── outputs/{scan_id}/{tool}.json           # Raw tool output
├── indexes/
│   ├── by_session.json                     # session_id → [scan_id, ...]
│   ├── by_contract.json                    # contract_address → [scan_id, ...]
│   └── by_severity.json                    # severity → [scan_id, ...]
└── _meta.json
```

### 3.5 Exploit Engine — No Persistent DB

Exploit Engine **tidak memiliki database persisten**. Semua state bersifat ephemeral.

Data yang perlu disimpan (oleh service lain):
- Exploit result → disimpan oleh **Storage Service** sebagai blob
- Exploit metadata → disimpan oleh **Report Service**
- Logs → stdout container, dikumpulkan oleh **Observability Stack**

### 3.6 AI Analysis Service — JSON Storage

```json
/data/ai/
├── analyses/{analysis_id}.json              # Per-analysis
│       { "id": "uuid", "scan_id": "...", "contract_address": "0x...",
│         "model_used": "gpt-4o", "risk_score": 85.5,
│         "overall_assessment": "...", "summary": "...",
│         "tokens_used": 15000, "duration_ms": 3200,
│         "status": "completed", "created_at": "..." }
├── verdicts/{analysis_id}/{finding_id}.json  # Per-verdict
├── fixes/{analysis_id}/{finding_id}.json     # Per-fix recommendation
├── indexes/
│   ├── by_session.json                      # session_id → [analysis_id, ...]
│   └── by_contract.json                     # address → [analysis_id, ...]
└── _meta.json
```

### 3.7 Vulnerability DB Service — JSON Storage

```json
/data/vulndb/
├── patterns/{pattern_id}.json               # Per-vulnerability pattern
│       { "id": "uuid", "name": "Reentrancy", "category": "reentrancy",
│         "severity": "high", "swc_id": "SWC-107",
│         "description": "...", "detection_rules": {...},
│         "code_example_bad": "...", "code_example_good": "...",
│         "remediation": "...", "is_active": true }
├── cve/{cve_id}.json                        # Per-CVE entry
├── indexes/
│   ├── by_category.json                    # category → [pattern_id, ...]
│   └── by_severity.json                    # severity → [pattern_id, ...]
```

### 3.8 Report Service — JSON Storage

```json
/data/report/
├── reports/{report_id}.json               # Per-report
│       { "id": "uuid", "session_id": "...", "project_id": "...",
│         "title": "...", "format": "md", "status": "draft",
│         "executive_summary": "...", "overall_score": 7.5,
│         "total_findings": 5, "critical_count": 1,
│         "generated_at": "...", "exported_at": "..." }
├── findings/{report_id}/{finding_id}.json  # Per-finding in report
├── templates/{template_id}.json            # Report templates
├── indexes/
│   ├── by_session.json                    # session_id → [report_id, ...]
│   ├── by_project.json                    # project_id → [report_id, ...]
│   └── by_status.json                     # status → [report_id, ...]
└── _meta.json
```

### 3.9 Notification Service — JSON Storage

```json
/data/notifier/
├── templates/{event_type}_{channel}.json   # Per-template
├── queue/{notification_id}.json           # Per-queued notification
├── webhooks/{webhook_id}.json             # Per-webhook config
├── delivery_logs/{date}.jsonl             # JSON Lines append-only
├── indexes/
│   ├── by_event.json                     # event_type → [notification_id, ...]
│   ├── by_status.json                    # status → [notification_id, ...]
│   └── by_webhook_user.json             # user_id → [webhook_id, ...]
└── _meta.json
```



---

## 4. End-to-End Pipeline Flow

### 4.1 Complete Audit Lifecycle

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                    FULL AUDIT PIPELINE — 8 Phases                              │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  PHASE 0: DISCOVERY (Immunefi Scraper)                                        │
│  ─────────────────────────────────────────                                     │
│  1. Cron trigger sync setiap 6 jam                                             │
│  2. Fetch projects.json dari GitHub (234+ programs)                            │
│  3. Diff dengan data existing → deteksi baru/update/closed                     │
│  4. Untuk program baru: fetch detail per program                              │
│  5. Simpan/update immunefi_programs + immunefi_contracts                      │
│  6. Emit: immunefi.program.synced                                             │
│                                                                                │
│  PHASE 1: AUTO-CREATE PROJECT (Project Service)                                │
│  ───────────────────────────────────────────────                               │
│  7. Project Service listens to immunefi.program.synced                        │
│  8. Untuk contract baru/terupdate: create project entry                        │
│  9. Fetch source code dari Etherscan (jika verified)                          │
│  10. Upload source ke Storage Service                                         │
│  11. Emit: project.contracts_ready                                            │
│                                                                                │
│  PHASE 2: AUDIT INITIATION (Orchestrator)                                      │
│  ──────────────────────────────────────────                                    │
│  12. Orchestrator listens to project.contracts_ready                          │
│  13. Prioritize berdasarkan: max_bounty, chain, new contracts                  │
│  14. Create AuditSession dengan pipeline config                               │
│  15. Emit: audit.requested → audit.started                                    │
│                                                                                │
│  PHASE 3: STATIC ANALYSIS                                                      │
│  ─────────────────────────                                                      │
│  16. Orchestrator dispatch ke Static Analysis Service                          │
│  17. Service pull source dari Storage Service                                  │
│  18. Run tools sesuai konfigurasi:                                             │
│      ├── Slither: control flow, inheritance, reentrancy                        │
│      ├── Mythril: symbolic execution, deeper paths                             │
│      └── Echidna: fuzzing, property testing                                   │
│  19. Parse semua output → unified finding format                               │
│  20. Simpan: scans + scan_findings + scan_tool_outputs                        │
│  21. Emit: scan.completed                                                     │
│                                                                                │
│  PHASE 4: PATTERN MATCHING (Vuln DB)                                           │
│  ──────────────────────────────────────                                        │
│  22. Vuln DB Service listens to scan.completed                                │
│  23. Match findings against vuln_patterns                                     │
│  24. Cross-reference dengan CVE entries                                       │
│  25. Hitung match_confidence                                                  │
│  26. Simpan: pattern_matches                                                  │
│  27. Emit: patterns.matched                                                   │
│                                                                                │
│  PHASE 5: AI ANALYSIS                                                          │
│  ────────────────────                                                          │
│  28. AI Analysis Service listens to patterns.matched                          │
│  29. Kirim findings + source code + pattern matches ke LLM                     │
│  30. Dapatkan:                                                                 │
│      ├── AI Verdict: confirmed/rejected tiap finding                          │
│      ├── Severity Reassessment: up/down/same                                  │
│      ├── Exploit Scenario: bagaimana exploit dilakukan                        │
│      ├── Fix Recommendation: kode perbaikan                                   │
│      └── Risk Score: 0-100                                                   │
│  31. Store: ai_analyses + ai_verdicts + fix_recommendations                   │
│  32. Generate embedding untuk future learning                                  │
│  33. Emit: ai.analyzed                                                        │
│                                                                                │
│  PHASE 6: EXPLOIT TESTING (Exploit Engine)                                     │
│  ──────────────────────────────────────────                                    │
│  34. Exploit Engine listens to ai.analyzed                                    │
│  35. Skip jika tidak ada finding critical/high yang confirmed                  │
│  36. Pool Manager: check available Anvil instance                              │
│  37. Spin up Anvil container:                                                  │
│      ├── --network=none                                                       │
│      ├── --load-mode=fork                                                     │
│      ├── --fork-url=<archived_rpc>                                           │
│      └── --fork-block-number=<block>                                         │
│  38. Execute exploit berdasarkan AI scenario:                                  │
│      ├── Impersonate accounts (owner, whale)                                  │
│      ├── Manipulate state (balance, storage, timestamp)                      │
│      └── Call vulnerable functions                                           │
│  39. Record: tx_hash, gas_used, state_diff, trace                             │
│  40. Jika berhasil: generate PoC script (Hardhat/Foundry format)             │
│  41. Simpan result → Storage Service                                          │
│  42. Destroy Anvil instance                                                   │
│  43. Emit: exploit.completed                                                  │
│                                                                                │
│  PHASE 7: GAS ANALYSIS (Gas Optimizer)                                        │
│  ────────────────────────────────────────                                     │
│  44. Gas Optimizer listens to ai.analyzed                                     │
│  45. Opcode-level profiling dari source code                                   │
│  46. Identifikasi gas-heavy patterns:                                          │
│      ├── Storage loops (SLOAD/GSSLOAD)                                       │
│      ├── Unbounded iterations                                                │
│      └── Inefficient data structures                                         │
│  47. Generate optimization suggestions                                         │
│  48. Simpan: gas_reports                                                      │
│  49. Emit: gas.analyzed (opsional, can be skipped)                            │
│                                                                                │
│  PHASE 8: REPORT GENERATION (Report Service)                                   │
│  ────────────────────────────────────────────                                 │
│  50. Report Service collects all events:                                       │
│      ├── scan.completed → findings                                           │
│      ├── patterns.matched → CVE refs                                        │
│      ├── ai.analyzed → verdicts + fixes                                     │
│      ├── exploit.completed → PoC                                            │
│      └── gas.analyzed → optimizations                                       │
│  51. Render sesuai template (Immunefi Standard)                               │
│  52. Generate PDF + HTML + Markdown                                           │
│  53. Hitung overall_score berdasarkan:                                        │
│      ├── (critical*10 + high*5 + medium*2) / total_contracts                │
│      ├── dikurangi jika exploit berhasil                                    │
│      └── ditambah jika AI confidence tinggi                                 │
│  54. Upload ke Storage Service                                                │
│  55. Emit: report.generated → audit.completed                                │
│                                                                                │
│  PHASE 9: DELIVERY (Notification Service)                                      │
│  ────────────────────────────────────────                                     │
│  56. Notification Service listens to audit.completed                          │
│  57. Send alerts sesuai konfigurasi:                                           │
│      ├── Email: ringkasan eksekutif + link report                            │
│      ├── Slack/Discord: critical findings summary                            │
│      └── Webhook: JSON payload untuk integrasi                              │
│  58. Update UI via WebSocket (real-time dari Phase 2-8)                       │
│  59. Log delivery ke delivery_logs                                            │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Time Estimation per Audit

```
TIME BREAKDOWN (target per contract):
───────────────────────────────────

  Discovery & Project Creation:     ~30 detik   (auto, no human)
  Source Code Fetch:               ~10 detik   (Etherscan API)
  Static Analysis (Slither):       ~60 detik   (quick pass)
  Static Analysis (Mythril):       ~5-30 menit (symbolic = heavy)
  Static Analysis (Echidna):       ~5-15 menit (fuzzing = time)
  Pattern Matching:                 ~5 detik   (DB lookup)
  AI Analysis:                     ~30 detik   (LLM inference)
  Exploit Testing:                 ~2-10 menit (Anvil + execution)
  Gas Analysis:                     ~20 detik   (opcode profiling)
  Report Generation:                ~10 detik   (template render)

  ─────────────────────────────────────────────────────
  TOTAL (1 contract, all tools):  ~15-60 menit
  TOTAL (1 contract, Slither only): ~3-5 menit

  SCALING:
  ├── 1 program (avg 5 contracts): ~1-5 jam
  ├── 10 programs:                 ~10-50 jam
  └── All 234+ programs:           ~1000+ jam (parallelize!)
```

---

## 5. Immunefi Data Model

### 5.1 GitHub Data Source

```
Source: https://raw.githubusercontent.com/infosec-us-team/
        Immunefi-Bug-Bounty-Programs-Unofficial/main/

├── projects.json           → Array program summaries
└── project/{slug}.json    → Detail per program (234+ files)
```

**projects.json structure:**
```json
{
  "id": "ethena",
  "name": "Ethena",
  "addedAt": 1717171200,
  "lastUpdated": 1717761375,
  "maxBounty": 3000000,
  "logoUrl": "https://..."
}
```

**project/{slug}.json structure (real example — Ethena):**
```json
{
  "project": "Ethena",
  "maxBounty": 3000000,
  "rewardType": "USDC",
  "kycRequired": true,
  "pocPerTypeAndSeverity": [
    "smart_contract - critical",
    "smart_contract - high",
    "smart_contract - medium"
  ],
  "assets": [
    {
      "url": "https://etherscan.io/address/0x4c9edd5852cd905f086c759e8383e09bff1e68b3",
      "type": "smart_contract",
      "description": "USDe.sol"
    }
  ],
  "features": ["Managed Triage", "Arbitration"],
  "safeHarbor": true,
  "previousAudits": [],
  "knownIssues": []
}
```

### 5.2 Sync Strategy

```
IMMUNEFI SCRAPER — SYNC STRATEGY
═══════════════════════════════════

 SCHEDULE:
  ├── Full sync: setiap 6 jam (cron)
  ├── Quick check: setiap 30 menit (HEAD request ke projects.json)
  └── On-demand: trigger manual dari UI/API

 PROCESS:
  1. GET projects.json → parse JSON
  2. Compare dengan immunefi_programs yang ada di DB
  3. Deteksi perubahan:
     ├── NEW: id tidak ada di DB → tambah
     ├── UPDATED: lastUpdated berbeda → fetch ulang
     └── REMOVED: ada di DB tapi tidak di remote → tandai closed
  4. Untuk setiap program baru/update:
     ├── GET project/{slug}.json
     ├── Parse assets → simpan contract addresses
     ├── Simpan metadata (bounty, KYC, PoC requirements)
     └── Emit event: immunefi.program.synced

 EDGE CASES:
  ├── Rate limiting: exponential backoff + jitter
  ├── Partial failure: simpan progress, retry yang gagal
  ├── Validation: skip entry tanpa contract address
  └── Dedup: address yang sama di multiple chains = contract berbeda
```

---

## 6. Proto File Structure

```
proto/
├── scauditor/
│   ├── auth/
│   │   └── v1/
│   │       └── auth.proto
│   ├── immunefi/
│   │   └── v1/
│   │       ├── immunefi.proto
│   │       └── source.proto
│   ├── orchestrator/
│   │   └── v1/
│   │       └── orchestrator.proto
│   ├── static_analysis/
│   │   └── v1/
│   │       └── analysis.proto
│   ├── exploit/
│   │   └── v1/
│   │       └── exploit.proto
│   ├── ai/
│   │   └── v1/
│   │       └── ai.proto
│   ├── vulndb/
│   │   └── v1/
│   │       └── vulndb.proto
│   ├── report/
│   │   └── v1/
│   │       └── report.proto
│   ├── storage/
│   │   └── v1/
│   │       └── storage.proto
│   ├── skill/
│   │   └── v1/
│   │       └── skill.proto
│   ├── gas/
│   │   └── v1/
│   │       └── gas.proto
│   └── notification/
│       └── v1/
│           └── notification.proto
├── common/
│   ├── v1/
│   │   ├── types.proto          # Shared types: Address, Chain, Finding, etc.
│   │   ├── events.proto         # Event envelope
│   │   └── pagination.proto     # Page/PageSize/PageToken
├── buf.yaml                     # Buf config for linting/breaking
├── buf.gen.yaml                 # Code generation config
└── README.md
```

---

## 7. Bug Classification System

### 7.1 The 4-Quadrant Detection Matrix

Setiap finding yang dihasilkan pipeline diklasifikasikan ke dalam 4 kategori untuk mengukur akurasi dan mendorong pembelajaran:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DETECTION MATRIX                                  │
│                     (Confusion Matrix)                               │
├─────────────────────────────┬───────────────────────────────────────┤
│                             │  ACTUAL VULNERABILITY                 │
│                             ├──────────────┬────────────────────────┤
│                             │  YES (Bug)   │  NO (No Bug)           │
├────────────┬────────────────┼──────────────┼────────────────────────┤
│ DETECTED   │ POSITIVE (P)   │  TRUE POS    │  FALSE POS             │
│ (Alat/     │                │  (TP)        │  (FP)                  │
│ AI bilang  │                │  ✅ Real bug │  ❌ False alarm        │
│ ada bug)   │                │  → Submit    │  → Catat, adjust       │
│            │                │  ke Immunefi │  → Kurangi confidence  │
│            ├────────────────┼──────────────┼────────────────────────┤
│            │ NEGATIVE (N)   │  FALSE NEG   │  TRUE NEG              │
│            │                │  (FN)        │  (TN)                  │
│            │                │  ⚠️ Missed!  │  ✅ Correctly safe     │
│            │                │  → Pelajaran  │  → Catat, naikkan      │
│            │                │    PALING     │    confidence pattern  │
│            │                │    PENTING    │                        │
└────────────┴────────────────┴──────────────┴────────────────────────┘
```

**Definisi untuk SC Auditor:**

| Klasifikasi | Definisi | Contoh | Action |
|-------------|----------|--------|--------|
| **True Positive (TP)** | Bug nyata, terkonfirmasi exploit atau AI + human | Reentrancy di withdraw(), terbukti bisa hack | ✅ Masuk laporan Immunefi |
| **False Positive (FP)** | Alat bilang ada bug, tapi setelah dicek aman | Slither detect "unused return" tapi safe | ❌ Dicatat, update pattern matching |
| **True Negative (TN)** | Alat bilang aman, dan memang aman | Function tanpa reentrancy path | ✅ Dicatat, confidence pattern naik |
| **False Negative (FN)** | Ada bug nyata tapi alat tidak detect | Oracle manipulation yang terlewat | ⚠️ PALING PENTING — trigger improvement cycle |

### 7.2 Finding Lifecycle & Reclassification

Setiap finding melewati stages yang bisa mengubah klasifikasinya:

```
FINDING LIFECYCLE:
═══════════════════════════════════════════════════════════════

STAGE 0: RAW (from Static Analysis)
  └── classification: unknown
  └── tool_severity: critical | high | medium | low | info
  └── confidence: 0.3 - 0.7 (tool-dependent)
       │
       ▼
STAGE 1: AI VERDICT (from AI Analysis Service)
  ├── AI classification: TP (confirmed) | FP (rejected)
  ├── AI confidence: 0.0 - 1.0
  └── Jika AI sangat yakin (confidence > 0.9) → langsung TP
       │
       ▼
STAGE 2: EXPLOIT TEST (from Exploit Engine) — only for critical/high TP
  ├── Exploit berhasil → classification = TP ✅ (confirmed)
  ├── Exploit gagal   → classification = FP ❌ (rejected)
  └── Jika gagal tapi AI high confidence → ⚠️ human review needed
       │
       ▼
STAGE 3: HUMAN REVIEW (from UI)
  ├── Human setujui AI → classification final
  └── Human koreksi    → classification berubah, update learning
       │
       ▼
STAGE 4: IMMUNEFI SUBMISSION (External Validation)
  ├── Immunefi accepted → ✅ TP confirmed final
  ├── Immunefi rejected → ❌ Ternyata FP, trigger reclassification
  └── Immunefi found additional bug → ⚠️ New FN, trigger improvement
       │
       ▼
STAGE 5: LEARNING LOOP (Feedback ke sistem)
  ├── TP → reinforce pattern, naikkan weight
  ├── FP → update filter, turunkan tool confidence
  ├── TN → naikkan confidence untuk pattern serupa
  └── FN → 🔴 KRITIS: buat pattern baru, update AI training
```

### 7.3 Finding Classification Storage (JSON)

```json
/data/scanner/
├── findings/{scan_id}/{finding_id}.json   # Per-finding dengan field classification
│       { "id": "uuid", "scan_id": "...", "title": "...",
│         "classification": "true_positive",
│         "classification_confidence": 0.92,
│         "classification_source": "ai_verdict",
│         "final_classification": true,
│         "reclassifications": [
│           { "previous": "unknown", "new": "true_positive",
│             "source": "exploit", "reasoning": "..." }
│         ] }
├── metrics/{date}.json                     # Per-day platform metrics
│       { "metric_date": "2026-05-20",
│         "tp_count": 42, "fp_count": 8, "fn_count": 3,
│         "precision": 0.84, "recall": 0.93, "f1_score": 0.88,
│         "tool_performance": {"slither": {"tp": 20, "fp": 5}, ...} }
├── learning/{opp_id}.json                 # Per-learning opportunity
│       { "id": "uuid", "type": "fn", "finding_id": "...",
│         "description": "...", "root_cause": "...",
│         "status": "open", "priority": 10 }
└── _meta.json
```

### 7.4 Reporting Strategy — Dua Level Laporan

```
REPORT STRATEGY:
═══════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────┐
│ LAPORAN LEVEL 1: IMMUNEFI SUBMISSION                                │
│ ─────────────────────────────────────────────                       │
│ Tujuan: Submit bug bounty ke Immunefi                               │
│ Format: Markdown (template Immunefi Standard)                       │
│ Isi:    ✅ HANYA True Positives (confirmed)                         │
│         ✅ Exploit PoC (wajib untuk critical/high)                  │
│         ✅ Severity sesuai klasifikasi Immunefi                     │
│         ❌ TIDAK ada FP/TN/FN                                       │
│         ❌ TIDAK ada internal notes                                 │
│                                                                     │
│ Sections dalam Immunefi Report:                                     │
│ 1. Vulnerability Title                                              │
│ 2. Contract & Chain                                                 │
│ 3. Severity Classification                                          │
│ 4. Description & Impact                                             │
│ 5. Proof of Concept (Hardhat script)                                │
│ 6. Recommended Fix                                                  │
│ 7. References                                                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ LAPORAN LEVEL 2: INTERNAL AUDIT REPORT                              │
│ ───────────────────────────────────────                             │
│ Tujuan: Learning & improvement                                      │
│ Format: HTML/PDF/MD (detailed)                                      │
│ Isi:    ✅ Semua findings: TP + FP + TN + FN                        │
│         ✅ Classification confidence matrix                         │
│         ✅ Scoring & metrics (precision, recall, F1)                │
│         ✅ Per-tool performance breakdown                           │
│         ✅ Learning opportunities (FN analysis)                     │
│         ✅ Reclassification history                                 │
│                                                                     │
│ Sections dalam Internal Report:                                     │
│ 1. Executive Summary + Score                                        │
│ 2. Detection Matrix (4-quadrant chart)                              │
│ 3. True Positives (yang akan di-submit)                             │
│ 4. False Positives (yang ditolak AI/exploit)                        │
│ 5. False Negatives (⚠️ critical learning)                           │
│ 6. True Negatives (confirmed safe patterns)                         │
│ 7. Per-Tool Performance Analysis                                    │
│ 8. Learning Recommendations                                         │
│ 9. Full Finding Details (all classifications)                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.5 False Negative — Mekanisme Paling Kritis

FN adalah sinyal pembelajaran paling berharga. Platform harus proaktif mengejar FN:

```
FN DETECTION & RESPONSE:
═══════════════════════════════════════════════════════════════

 CARA FN TERDETEKSI:
  ├── 1. Immunefi Rejection dengan bug tambahan
  │    → Tim kami submit bug A (TP), Immunefi bilang "ada juga bug B"
  │    → Bug B adalah FN kami → catat, buat pattern
  │
  ├── 2. Known Issues dari Immunefi project page
  │    → Beberapa program punya known issues list
  │    → Cek apakah tool kami detect known issues = no? → FN
  │
  ├── 3. Cross-tool validation
  │    → Slither detect, Mythril tidak → Mythril mungkin FN
  │    → Evaluasi kenapa Mythril miss
  │
  ├── 4. Human peninjauan periodik
  │    → Sample audit: human audit manual sebagai benchmark
  │    → Bandingkan hasil → hitung FN rate
  │
  └── 5. Similar contract analysis
      → Contract A punya bug X, Contract B mirip
      → Apakah tool detect bug X di Contract B?
      → Jika tidak → FN pattern untuk contract serupa

 RESPONSE TERHADAP FN:
  ├── Priority: 10/10 (tertinggi)
  ├── Buat learning_opportunities entry dengan type='fn'
  ├── Analisis root cause: kenapa miss?
  │   ├── Tool limitation (Slither tidak check oracle)
  │   ├── Pattern tidak ada di Vuln DB
  │   ├── AI tidak trained untuk pattern ini
  │   └── Source code tidak ter-fetch (unverified contract)
  ├── Action:
  │   ├── Tambah pattern ke Vuln DB
  │   ├── Update AI prompt dengan contoh serupa
  │   └── Adjust tool configuration
  └── Verifikasi: re-run audit setelah improvement
```

### 7.6 Scoring System — Berbasis Confusion Matrix

Overall score menggunakan weighted formula yang mempertimbangkan TP, FP, dan FN:

```
SCORING FORMULA:
═══════════════════════════════════════════════════════════════

FINDING SCORE (per finding):
  base = severity_weight (critical=10, high=5, medium=2, low=1)
  
  IF classification = TP:
    IF exploit_successful → score = base × 1.5 (bonus exploit)
    ELSE → score = base × 1.0
  
  IF classification = FP:
    score = -(base × 0.3)  (penalty false alarm)
  
  IF classification = FN:
    score = -(base × 0.5)  (penalty missed bug — larger)
  
  IF classification = TN:
    score = +0.1            (small reward for correct safety)

OVERALL PROJECT SCORE:
  raw = SUM(all finding scores)
  max_possible = SUM(all severity_weights) × 1.5
  
  normalisasi: score = (raw / max_possible) × 10
  clamp: 0.0 - 10.0
  
  Grade:
  ├── 9.0 - 10.0 → S (Superior) — semua TP, exploit confirmed
  ├── 7.5 - 8.9  → A (Excellent) — TP dominan, sedikit FP
  ├── 5.0 - 7.4  → B (Good) — reasonable TP, beberapa FP
  ├── 3.0 - 4.9  → C (Fair) — terlalu banyak FP
  └── 0.0 - 2.9  → D (Poor) — dominan FP/FN, perlu review

PER-TOOL PRECISION (untuk evaluasi tool):
  precision = tool_TP / (tool_TP + tool_FP)
  
  Jika precision < 0.3 → tool perlu rekonfigurasi
  Jika precision > 0.9 → tool reliable, naikkan priority
```

---

## 8. Matured Decisions — 6 Item Final

### 8.1 Target Blockchain Pertama: EVM (Ethereum + EVM L2s)

**Keputusan**: EVM **wajib**, multi-chain **nanti**.

| Faktor | EVM | Solana | Other |
|--------|-----|--------|-------|
| Immunefi Coverage | ~90% program | ~5% | ~5% |
| Tool Maturity | Slither/Mythril/Echidna mature | Sedikit tools | Minimal |
| Anvil Support | ✅ Native fork | ❌ Tidak ada | ❌ |
| Skill Availability | Hermes EVM skills + Opencode SC Auditor | Limited | None |
| Complexity | Known | New paradigm (BPF) | Varied |

```
ROADMAP CHAIN SUPPORT:
═══════════════════════════════════════════════════════════════

Fase 1 (Launch):    Ethereum + Arbitrum + Optimism + Base + Polygon
                    → Semua EVM, reuse Slither/Mythril/Echidna

Fase 2 (Q3 2026):   BNB Chain + Avalanche + Fantom + Mantle
                    → Masih EVM, tambah RPC endpoints

Fase 3 (Q4 2026):   Solana + Near
                    → Butuh tool baru (Not right now)
```

### 8.2 Exploit Engine Stack: TypeScript (utama) + Python (Hermes Scripts)

**Keputusan**: **TypeScript** untuk 95% Exploit Engine, **Python** hanya untuk Hermes skill scripting.

| Komponen | Stack | Alasan |
|----------|-------|--------|
| API Layer (gRPC/REST) | TypeScript | Satu ekosistem dengan service lain, proto shared |
| Pool Manager | TypeScript (Dockerode) | Cukup untuk initial, worker_threads untuk concurrency |
| Anvil Lifecycle | TypeScript (child_process) | Spawn/kill Anvil process |
| Exploit Execution | TypeScript (ethers.js v6) | Hardhat-native, ethers.js mature |
| PoC Generation | TypeScript (Handlebars) | Template-based PoC script generation |
| Hermes Exploit Scripts | Python | Panggil Hermes via subprocess/gRPC untuk pattern tertentu |

```
type ExploitEngine struct {
  api: Express/Fastify        → TypeScript
  pool: ContainerManager      → TypeScript (Dockerode)
  executor: TransactionEngine → TypeScript (ethers.js)
  hermes: HermesBridge        → Python (subprocess)
}
```

**Tidak pakai Go** — alasan: menambah bahasa = menambah kompleksitas build system, CI/CD, debugging. Go bisa ditambahkan nanti jika pool management butuh performa ribuan container concurrent.

### 8.3 Deduplikasi Skill: 109 → ~20 Core Skills

**Keputusan**: Adaptasi **15-20 skills** dari 109 total. Sisanya tidak relevan untuk audit platform.

```
SKILL DEDUP STRATEGY:
═══════════════════════════════════════════════════════════════

 SUMBER: 109 skills
  ├── Hermes: 43 primary + 18 optional = 61
  ├── Paperclip: 8
  └── Opencode: 58 (32 built-in + 26 custom)
       │
       ▼
 FILTER 1: RELEVANSI
  └── Hanya skill yang relevan untuk smart contract audit
       │
       ▼
 FILTER 2: DEDUP
  └── Skill serupa dari multiple framework → merge, pilih terbaik
       │
       ▼
 HASIL: ~20 Core Skills

 # | Skill | Sumber | Kegunaan dalam Platform
---|-------|--------|------------------------|
 1 | smartcontract-auditor | Opencode | Main audit framework |
 2 | blockchain-evm | Hermes | EVM analysis patterns |
 3 | red-teaming-godmode | Hermes | Exploit generation patterns |
 4 | security-sherlock | Hermes | DeFi security patterns |
 5 | security-oss-forensics | Hermes | On-chain forensics |
 6 | database-security | Opencode | Secure data handling |
 7 | reentrancy-detector | (custom) | Reentrancy-specific analysis |
 8 | oracle-manipulation | (custom) | Oracle manipulation patterns |
 9 | access-control | (custom) | Access control analysis |
10 | flash-loan-attacks | (custom) | Flash loan attack vectors |
11 | systematic-debugging | Hermes | Debugging methodology |
12 | test-driven-development | Hermes | Test writing |
13 | implementation-planning | Hermes | Task planning |
14 | agent-driven-development | Hermes | Sub-agent patterns |
15 | understanding | Opencode | Context analysis |
16 | workflow-general | Opencode | Pipeline workflow |
17 | app-quality | Opencode | Quality scoring |
18 | prompt-engineering | Opencode | AI prompt optimization |
19 | self-improving-skills | Opencode | Continuous learning |
20 | plugin-sdk | Paperclip | Extension system |

CATATAN: 
- Skill Hermes dan Opencode adalah MARKDOWN — bisa di-parse oleh service manapun
- Tidak perlu adaptasi kode, cukup format ulang untuk Skill Service
- Skills baru akan ditambahkan seiring pembelajaran dari FN
```

### 8.4 Build Priority: 4 Waves, Parallel dalam Wave

**Keputusan**: 4 waves, service dalam wave yang sama dikerjakan PARALEL.

```
BUILD WAVES:
═══════════════════════════════════════════════════════════════

WAVE 1 — FOUNDATION (Minggu 1-2)
  Tujuan: Data masuk, user bisa login, project tercreate
  Parallel: ✅ Semua service di wave 1 independen
  
  ├── Immunefi Scraper    → sync 234+ programs, contract addresses
  ├── Auth Service        → users, JWT, RBAC, API keys
  ├── Storage Service     → MinIO, source code storage
  └── Project Service     → auto-create dari Immunefi data
       │
       ▼ Dependency for next wave: project with contracts + source code
       ▼

WAVE 2 — CORE AUDIT (Minggu 3-5)
  Tujuan: Pipeline audit dasar berfungsi
  Sequential: Orchestrator → Static → VulnDB → AI (dependent chain)
  
  ├── Orchestrator Service    → pipeline engine, event-driven
  ├── Static Analysis Service → Slither/Mythril/Echidna
  ├── Vuln DB Service         → pattern matching
  └── AI Analysis Service     → LLM verdict, severity scoring
       │
       ▼ Dependency: AI verdict + pattern match → Exploit Engine
       ▼

WAVE 3 — ADVANCED (Minggu 6-8)
  Tujuan: Exploit, gas, skill integration
  Parallel: Exploit & Gas independen, Skill tergantung hasil
  
  ├── Exploit Engine        → Anvil fork, PoC generation
  ├── Gas Optimizer Service → opcode-level gas analysis
  └── Skill Service         → Hermes/Opencode skill integration
       │
       ▼ Dependency: all results → Report Service
       ▼

WAVE 4 — DELIVERY (Minggu 9-10)
  Tujuan: Report, notification, UI, gateway
  Parallel: ✅ Semua independen
  
  ├── Report Service        → TP/FP/TN/FN report generation
  ├── Notification Service  → webhook, email, Slack
  ├── API Gateway           → Kong/Envoy routing
  └── UI                    → React dashboard (dari Paperclip)
```

### 8.5 Deployment Model: Hybrid (VPS + Local Dev)

**Keputusan**: **Hybrid** — VPS untuk services, local untuk Exploit Engine development.

```
DEPLOYMENT ARCHITECTURE:
═══════════════════════════════════════════════════════════════

                    ┌──────────────────────┐
                    │    DEVELOPMENT        │
                    │  (Local Machine)     │
                    │                      │
                    │  • Docker Compose    │
                    │  • Semua service     │
                    │  • Anvil testnet     │
                    │  • Hot reload        │
                    └──────────────────────┘
                            │
                            ▼ (deploy via CI/CD)
                    ┌──────────────────────┐
                    │    PRODUCTION         │
                    │  (VPS: Hetzner CX22)  │
                    │  ≈ €8-12 / bulan      │
                    │                      │
                    │  • Docker Compose    │
                    │  • 14 containers     │
                    │  • NATS JetStream    │
                    │  • MinIO storage     │
                    │                      │
                    │  SPECS:              │
                    │  ├── 2 vCPU          │
                    │  ├── 4 GB RAM        │
                    │  ├── 80 GB SSD       │
                    │  └── 1 Gbpsネット    │
                    └──────────────────────┘
                            │
                            ▼ (on-demand)
                    ┌──────────────────────┐
                    │    EXPLOIT ENGINE     │
                    │  (Scale to Zero)      │
                    │                      │
                    │  • Anvil containers  │
                    │  • --network=none    │
                    │  • tmpfs RAM disk    │
                    │  • Spin up only saat │
                    │    exploit dibutuhkan │
                    │  • Auto-destroy      │
                    └──────────────────────┘

 WHY VPS BUKAN FULL CLOUD:
  ├── Biaya: VPS €8-12 vs Cloud $50-100/bulan
  ├── Anvil butuh akses Docker socket → VPS lebih mudah
  └── Kompleksitas: Kubernetes overkill untuk personal platform

 WHY VPS BUKAN LOCAL ONLY:
  ├── Immunefi scraper harus jalan 24/7
  ├── Cron sync tidak bisa di laptop mati
  └── API endpoint harus selalu available
```

### 8.6 Nama Platform — Options & Rekomendasi

**Keputusan**: Belum final — 5 opsi diajukan, user pilih:

```
CANDIDATE NAMES:
═══════════════════════════════════════════════════════════════

1. ⭐ VYPER              → "Vyper" = cepat + "VIPER" = ular berbisa
                          → Cepat mendeteksi, berbisa ke bug
                          → branding: "Vyper - Smart Contract Hunter"
                          → Domain: vyper.dev ✅ available

2.   SENTRY              → Penjaga, pengawas
                          → branding: "Sentry - Immunefi Bug Hunter"
                          → Domain: sentry.dev ❌ taken

3.   FORGE               → Tempa, forge (cocok dengan Foundry)
                          → branding: "Forge - Automated Audit Platform"
                          → Domain: forge.dev ❌ probably taken

4.   ECHIDNA             → Nama tool fuzzing, tapi bisa ambigu
                          → branding: "Echidna - Smart Contract Security"
                          → Domain: echidna.dev ❌ taken

5.   CRAWLER             → Crawl (merayap) mencari bug
                          → branding: "Crawler - Bug Bounty Automator"
                          → Domain: crawler.dev ✅ available

REKOMENDASI: VYPER
  ├── Short (5 huruf) — mudah diingat
  ├── Unik — tidak bentrok dengan tool terkenal
  ├── Metafora kuat: ular berbisa → bisa mendeteksi + menyerang bug
  ├── .dev domain available
  └── Bisa dikembangkan: "VyperScan", "VyperAudit", "VyperChain"
```

---

## 9. Antonio Supremacy — The Absolute AI Agent Controller

> **Keputusan Arsitektural Final**: Antonio adalah **satu-satunya AI Agent pengendali absolut** secara internal.
> Semua service, semua agent, semua pipeline — semuanya berada di bawah komando Antonio.

### 9.1 The Chain of Command

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CHAIN OF COMMAND — VYPER PLATFORM                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  LEVEL 0: USER (Human Operator)                                         │
│  ────────────────────────────────────                                   │
│  │ Hanya berkomunikasi dengan ANTONIO                                   │
│  │ TIDAK memiliki akses langsung ke service agents                      │
│  │ TIDAK bisa memerintah Orchestrator, scanner, atau agent lain         │
│  │ Input: "Antonio, audit contract 0x..."                               │
│                                                                         │
│         │ ONLY TALKS TO ANTONIO                                         │
│         ▼                                                               │
│  LEVEL 1: ANTONIO (14-agent) — ABSOLUTE CONTROLLER                      │
│  ─────────────────────────────────────────────────────                  │
│  │ Satu-satunya AI Agent dengan ReAct loop penuh                        │
│  │ Pemilik tunggal AgentRegistry                                        │
│  │ Pengendali semua delegasi (DelegateTaskSkill)                        │
│  │ Memori terpusat (vector + episodic + semantic + graph)               │
│  │ Pusat learning (FeedbackLearner)                                     │
│  │ Satu-satunya yang bisa intervensi agent lain                         │
│                                                                         │
│         │ COMMANDS / DELEGATES                                           │
│         ▼                                                               │
│  LEVEL 2: ORCHESTRATOR AGENT (11-orchestrator)                          │
│  ─────────────────────────────────────────────────────                  │
│  │ Bawahan Antonio — menjalankan pipeline atas perintah Antonio         │
│  │ Pipeline deterministik (state machine) — TIDAK punya AI otonom       │
│  │ Daemon hanya aktif jika Antonio/Dashboard mengaktifkannya            │
│  │ TIDAK bisa memulai pipeline tanpa perintah Antonio                   │
│                                                                         │
│         │ CALLS SERVICES DIRECTLY VIA HTTP                               │
│         ▼                                                               │
│  LEVEL 3: SERVICE AGENTS (02-16, excluding 14)                          │
│  ─────────────────────────────────────────────────────                  │
│  │ Semua adalah BaseAgent — menerima delegasi, tidak berinisiatif       │
│  │ Tidak punya akses ke AgentRegistry milik Antonio                     │
│  │ Tidak bisa saling delegasi — hanya Antonio yang bisa delegasi        │
│  │ Tidak punya AI ReAct loop — hanya eksekutor tugas                    │
│  │ Laporan kembali ke Antonio, bukan ke user                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Aturan Antonio Supremacy (Tidak Bisa Dilanggar)

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                    ATURAN ANTONIO SUPREMACY                              ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  R1. ANTONIO ADALAH SATU-SATUNYA AI                                      ║
║     └── Tidak ada AI / LLM / ReAct loop lain selain Antonio              ║
║     └── Service agents TIDAK punya akses ke LLM — hanya Antonio          ║
║     └── Orchestrator TIDAK punya ReAct loop — hanya state machine        ║
║                                                                          ║
║  R2. AGENT REGISTRY MILIK ANTONIO                                        ║
║     └── Hanya Antonio yang menginisialisasi AgentRegistry                 ║
║     └── Hanya Antonio yang bisa discover agents                           ║
║     └── Service agents tidak tahu keberadaan agent lain                   ║
║     └── AgentRegistry.start_background_refresh() hanya dipanggil Antonio ║
║                                                                          ║
║  R3. SEMUA DELEGASI MELALUI ANTONIO                                      ║
║     └── Tidak ada service yang boleh delegasi ke service lain             ║
║     └── Orchestrator boleh HTTP-call service (eksekusi teknis)            ║
║         tapi TIDAK melalui AgentProtocol (hanya Antonio yang pakai itu)  ║
║     └── DelegateTaskSkill adalah SATU-SATUNYA gerbang delegasi           ║
║                                                                          ║
║  R4. TIDAK ADA AUTONOMI TANPA IZIN ANTONIO                               ║
║     └── Orchestrator daemon: auto-start = FALSE (harus via API Antonio)  ║
║     └── Antonio daemon: bisa autonomous, tapi start/stop via user        ║
║     └── Service agents: zero autonomy — pure task executor               ║
║                                                                          ║
║  R5. USER HANYA BICARA KE ANTONIO                                        ║
║     └── Dashboard hanya punya 1 AI interface: chat dengan Antonio        ║
║     └── Tidak ada "Direct Agents" page di dashboard                       ║
║     └── Service health & monitoring tetap visible, tapi read-only        ║
║                                                                          ║
║  R6. MEMORY & LEARNING TERPUSAT DI ANTONIO                               ║
║     └── Hanya Antonio yang punya vector memory + episodic memory         ║
║     └── Hanya Antonio yang punya FeedbackLearner                         ║
║     └── Service agents tidak punya memori — stateless task executors     ║
║                                                                          ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

### 9.3 Implementasi — Sudah & Belum

| Aturan | Status | Bukti / Catatan |
|--------|--------|------------------|
| R1: Antonio satu-satunya AI | ✅ **FIXED** | ✅ 14-agent punya `AgentReasoningClient` + ReAct loop. ✅ 06-ai sudah di-strip: `SkillRegistry` + autonomous routing dihapus. `LLMClient` tetap sebagai technical execution layer (bukan AI agency). Lihat §9.5 |
| R2: AgentRegistry milik Antonio | ✅ | `AgentRegistry()` di-init di `14-agent/app.py:171`. Tidak ada service lain yang import/instantiate registry |
| R3: Semua delegasi via Antonio | ✅ | `DelegateTaskSkill` di `14-agent/src/skills/delegate_task.py`. Orchestrator HTTP-call service untuk eksekusi teknis — bukan delegasi agent protocol |
| R4: Tidak ada autonomi tanpa izin | ✅ | Orchestrator daemon tidak auto-start. Antonio daemon bisa autonomous tapi start/stop via user |
| R5: User hanya bicara ke Antonio | ✅ | Dashboard → hanya halaman Antonio untuk AI chat |
| R6: Memory terpusat | ✅ | `AgentMemory` hanya di 14-agent. Tidak ada service lain yang punya persistent memory |

### 9.4 Diagram Visual — Siapa Ngontrol Apa

```
                    ╔═══════════════════════════════════╗
                    ║         ANTONIO (14-agent)        ║
                    ║                                   ║
                    ║  ┌──────────────┐                 ║
                    ║  │ AgentRegistry│── Daftar semua  ║
                    ║  └──────────────┘   agent known   ║
                    ║                                   ║
                    ║  ┌──────────────┐                 ║
                    ║  │ DelegateTask │── Kirim task    ║
                    ║  │ Skill        │   ke agent      ║
                    ║  └──────────────┘                 ║
                    ║                                   ║
                    ║  ┌──────────────┐                 ║
                    ║  │ AgentMemory  │── Simpan semua  ║
                    ║  └──────────────┘   pembelajaran  ║
                    ║                                   ║
                    ║  ┌──────────────┐                 ║
                    ║  │ ReAct Loop   │── Otak AI yang  ║
                    ║  │ (LLM)        │   memutuskan    ║
                    ║  └──────────────┘                 ║
                    ╚═══════════════════════════════════╝
                           │     │     │
              ┌────────────┘     │     └────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
   ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐
   │ ORCHESTRATOR     │  │ SERVICE      │  │ DAEMON       │
   │ (11)             │  │ AGENTS       │  │ (Antonio's)  │
   │                  │  │ (02-16,      │  │              │
   │ Pipeline state   │  │  except 14)  │  │ Self-improve │
   │ machine.         │  │              │  │ loop. Auto   │
   │ TIDAK punya AI.  │  │ Task exec.   │  │ hanya jika   │
   │ Bawahan Antonio. │  │ Stateless.   │  │ di-start.    │
   └──────────────────┘  └──────────────┘  └──────────────┘
           │                    │
           │ HTTP call langsung │ (bukan agent protocol)
           ▼                    ▼
   ┌──────────────────────────────────────────────┐
   │   INFRASTRUCTURE (scanner, database, etc.)   │
   │   BUKAN AI — pure execution layer            │
   └──────────────────────────────────────────────┘
```

### 9.5 Fix: 06-ai Stripped — Autonomous Routing Dihapus

> **Perbaikan (2 Juni 2026)**: Service `06-ai` telah di-"strip" — semua autonomous routing,
> SkillRegistry, dan severity-based strategy selection dihapus. Sekarang 06-ai adalah
> **pure delegation receiver** yang hanya execute perintah Antonio.

#### Detail Perbaikan

```
06-ai STRIP RESULTS:
═══════════════════════════════════════════════════════════════

 SEBELUM (Violation):
   AIAgent:
   ├── SkillRegistry dengan 4 registered skills
   │   ├── classify_single   (deep analysis untuk critical/high)
   │   ├── classify_batch    (batch analysis untuk low/medium)
   │   ├── deep_analysis     (full exploit path verification)
   │   └── generate_fix      (code fix generation)
   ├── _execute_classify() — severity-based autonomous routing
   │   ├── critical/high → classify_single (one-by-one)
   │   └── low/medium → classify_batch (all at once)
   ├── _generate_reflection() — post-execution summary
   ├── Capabilities: CLASSIFY_FINDINGS, GENERATE_FIX, DEEP_ANALYSIS
   └── LLMClient: direct API calls ke OpenAI/Anthropic

 SESUDAH (Compliant):
   AIAgent:
   ├── NO SkillRegistry
   ├── NO skills (semua file di-deprecate)
   ├── NO severity-based routing
   ├── NO strategy selection
   ├── _execute_task() langsung ke analyzer.analyze_all()
   │   atau fixer.suggest_fix() — sesuai perintah Antonio
   ├── Capabilities: CLASSIFY_FINDINGS, GENERATE_FIX (DEEP_ANALYSIS dihapus)
   ├── REST endpoints tetap ada untuk backward compatibility
   │   → Tapi Antonio yang kontrol kapan dan bagaimana dipanggil
   └── LLMClient tetap ada sebagai technical execution layer
       → Ini TIDAK melanggar karena 06-ai TIDAK punya AI agency
       → Hanya execute LLM call saat diperintah Antonio

 FILE YANG DIUBAH:
   ├── services/06-ai/src/agent_loop.py   → REWRITE: pure delegation receiver
   ├── services/06-ai/src/skills/*.py      → ALL DEPRECATED (5 files)
   ├── services/06-ai/app.py              → AIAgent init: analyzer + fixer (bukan llm_client)
   └── ARCHITECTURE.md                    → Status table diperbaiki

 KEPUTUSAN: Opsi A (Stripped Agent) — 2 Juni 2026
```

---

> **Dokumen ini adalah arsitektur detail dari SC Auditor Platform.**
> API contracts, event schema, database schema, bug classification, dan matured decisions siap untuk implementasi.
> Semua service wajib dibangun — tidak ada yang opsional.
>
> *Generated by lore-master — 17 Mei 2026*
