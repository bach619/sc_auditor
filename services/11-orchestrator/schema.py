"""SQLite schema for 11-orchestrator service.

Replaces: /data/orchestrator/audit_log.json, queue.json, daemon_state.json
Database:  /data/orchestrator/orchestrator.db
"""

SCHEMA_SQL = """
-- Main audit records (replaces audit_log.json)
CREATE TABLE IF NOT EXISTS audits (
    audit_id            TEXT PRIMARY KEY,
    chain               TEXT NOT NULL,
    address             TEXT NOT NULL,
    program             TEXT DEFAULT '',
    priority            INTEGER DEFAULT 5,
    use_ai              INTEGER DEFAULT 1,
    state               TEXT NOT NULL,           -- PENDING|FETCHING_PROGRAM|FETCHING_SOURCE|SCANNING|AI_ANALYSIS|CLASSIFYING|EXPLOITING|RECLASSIFYING|REPORTING|NOTIFYING|COMPLETED|FETCH_FAILED|SCAN_FAILED
    error               TEXT,
    report_path         TEXT,
    duration_seconds    REAL,
    metadata_json       TEXT DEFAULT '{}',       -- JSON-encoded dict
    partial_results     TEXT DEFAULT '{}',       -- JSON-encoded dict: step_name → success|skipped|degraded|failed
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at        TEXT
);

-- Pipeline steps per audit
CREATE TABLE IF NOT EXISTS pipeline_steps (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id            TEXT NOT NULL,
    step_name           TEXT NOT NULL,            -- FETCHING_PROGRAM|FETCHING_SOURCE|SCANNING|AI_ANALYSIS|...
    state               TEXT NOT NULL,            -- PENDING|RUNNING|COMPLETED|FAILED|SKIPPED
    started_at          TEXT,
    completed_at        TEXT,
    duration_seconds    REAL,
    retry_count         INTEGER DEFAULT 0,
    error               TEXT,
    result_json         TEXT,                     -- JSON: step result data
    UNIQUE(audit_id, step_name),
    FOREIGN KEY (audit_id) REFERENCES audits(audit_id)
);

-- Audit data (source code, findings, AI analysis, reports)
CREATE TABLE IF NOT EXISTS audit_data (
    audit_id            TEXT PRIMARY KEY,
    source_code         TEXT,                     -- Full Solidity source
    scanner_results     TEXT,                     -- JSON: aggregated scanner output
    ai_analysis         TEXT,                     -- JSON: AI analysis
    exploit_results     TEXT,                     -- JSON: PoC exploit results
    report_md           TEXT,                     -- Markdown report
    report_pdf_path     TEXT,
    findings_count      INTEGER DEFAULT 0,
    FOREIGN KEY (audit_id) REFERENCES audits(audit_id)
);

-- Priority queue (replaces queue.json)
CREATE TABLE IF NOT EXISTS queue (
    contract_id         TEXT PRIMARY KEY,         -- "chain:address"
    chain               TEXT NOT NULL,
    address             TEXT NOT NULL,
    program             TEXT DEFAULT '',
    priority_score      REAL DEFAULT 0.0,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    last_audited_at     TEXT,
    skip_reason         TEXT
);

-- Daemon state (replaces daemon_state.json)
CREATE TABLE IF NOT EXISTS daemon_state (
    id                  INTEGER PRIMARY KEY CHECK (id = 1), -- Single row
    status              TEXT NOT NULL DEFAULT 'stopped',     -- stopped|running|paused|error
    started_at          TEXT,
    stopped_at          TEXT,
    last_run_at         TEXT,
    next_run_at         TEXT,
    total_audited       INTEGER DEFAULT 0,
    total_cycles        INTEGER DEFAULT 0,
    last_error          TEXT
);

-- Scan metrics per tool
CREATE TABLE IF NOT EXISTS scan_metrics (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id            TEXT,
    scanner             TEXT NOT NULL,            -- slither|mythril|echidna|halmos|manticore
    duration_ms         INTEGER NOT NULL,
    findings_count      INTEGER DEFAULT 0,
    success             INTEGER DEFAULT 1,
    scanned_at          TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (audit_id) REFERENCES audits(audit_id)
);

-- Similarity data (replaces similarity.json)
CREATE TABLE IF NOT EXISTS similarity (
    contract_hash       TEXT PRIMARY KEY,
    similar_contract    TEXT NOT NULL,
    similarity_score    REAL NOT NULL,
    matched_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_audits_state ON audits(state);
CREATE INDEX IF NOT EXISTS idx_audits_program ON audits(program);
CREATE INDEX IF NOT EXISTS idx_audits_chain ON audits(chain);
CREATE INDEX IF NOT EXISTS idx_audits_created ON audits(created_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_audit ON pipeline_steps(audit_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_state ON pipeline_steps(state);
CREATE INDEX IF NOT EXISTS idx_queue_score ON queue(priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_scan_metrics_audit ON scan_metrics(audit_id);
CREATE INDEX IF NOT EXISTS idx_scan_metrics_scanner ON scan_metrics(scanner);
"""
