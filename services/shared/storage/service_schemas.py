"""SQLite schema for 02-immunefi service.

Replaces: /data/immunefi/programs/{slug}.json, history/{slug}.jsonl, indexes/
Database:  /data/immunefi/immunefi.db
"""

SCHEMA_SQL = """
-- Bounty programs
CREATE TABLE IF NOT EXISTS programs (
    slug            TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    url             TEXT,
    max_bounty      TEXT,
    platform        TEXT DEFAULT 'immunefi',
    chain           TEXT,
    status          TEXT DEFAULT 'active',
    metadata_json   TEXT DEFAULT '{}',
    last_updated    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Program-to-chain mapping (many-to-many)
CREATE TABLE IF NOT EXISTS program_chains (
    program_slug    TEXT NOT NULL,
    chain           TEXT NOT NULL,
    PRIMARY KEY (program_slug, chain),
    FOREIGN KEY (program_slug) REFERENCES programs(slug)
);

-- Change history (replaces JSONL files)
CREATE TABLE IF NOT EXISTS program_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    program_slug    TEXT NOT NULL,
    change_type     TEXT NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    changed_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (program_slug) REFERENCES programs(slug)
);

CREATE INDEX IF NOT EXISTS idx_programs_chain ON programs(chain);
CREATE INDEX IF NOT EXISTS idx_programs_status ON programs(status);
CREATE INDEX IF NOT EXISTS idx_history_slug ON program_history(program_slug);
"""

# SQLite schema for 03-source
SOURCE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS contracts (
    contract_hash   TEXT PRIMARY KEY,
    chain           TEXT NOT NULL,
    address         TEXT NOT NULL,
    name            TEXT,
    source_code     TEXT,
    abi_json        TEXT,
    compiler_version TEXT,
    license         TEXT,
    verified        INTEGER DEFAULT 0,
    bytecode_hash   TEXT,
    fetched_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(chain, address)
);

CREATE TABLE IF NOT EXISTS fetch_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_hash   TEXT NOT NULL,
    source          TEXT NOT NULL,
    success         INTEGER DEFAULT 1,
    error_message   TEXT,
    fetched_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (contract_hash) REFERENCES contracts(contract_hash)
);

CREATE INDEX IF NOT EXISTS idx_contracts_chain ON contracts(chain);
CREATE INDEX IF NOT EXISTS idx_contracts_addr ON contracts(address);
CREATE INDEX IF NOT EXISTS idx_fetch_history_hash ON fetch_history(contract_hash);
"""

# SQLite schema for 06-ai
AI_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS analysis_cache (
    content_hash    TEXT PRIMARY KEY,
    prompt_template TEXT NOT NULL,
    model           TEXT NOT NULL,
    response        TEXT NOT NULL,
    tokens_used     INTEGER,
    cost_usd        REAL,
    ttl_seconds     INTEGER DEFAULT 604800,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ai_cache_expires ON analysis_cache(
    datetime(created_at, '+' || ttl_seconds || ' seconds')
);
"""

# SQLite schema for 14-agent
AGENT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS episodic_memory (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    content_json    TEXT NOT NULL,
    importance      REAL DEFAULT 0.5,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS semantic_memory (
    id              TEXT PRIMARY KEY,
    concept         TEXT NOT NULL,
    relationship    TEXT,
    related_to      TEXT,
    confidence      REAL DEFAULT 0.5,
    source          TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id      TEXT PRIMARY KEY,
    status          TEXT DEFAULT 'active',
    task_type       TEXT,
    context_json    TEXT DEFAULT '{}',
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_episodic_session ON episodic_memory(session_id);
CREATE INDEX IF NOT EXISTS idx_episodic_type ON episodic_memory(event_type);
CREATE INDEX IF NOT EXISTS idx_semantic_concept ON semantic_memory(concept);
"""

# SQLite schema for 04-scanner
SCANNER_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS scan_jobs (
    job_id          TEXT PRIMARY KEY,
    contract_hash   TEXT NOT NULL,
    chain           TEXT NOT NULL,
    address         TEXT NOT NULL,
    tools_requested TEXT NOT NULL,
    status          TEXT DEFAULT 'PENDING',
    priority        INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS scan_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT NOT NULL,
    tool_name       TEXT NOT NULL,
    findings_count  INTEGER DEFAULT 0,
    duration_ms     INTEGER,
    success         INTEGER DEFAULT 1,
    error_message   TEXT,
    result_json     TEXT,
    scanned_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES scan_jobs(job_id)
);

CREATE INDEX IF NOT EXISTS idx_scan_jobs_status ON scan_jobs(status);
CREATE INDEX IF NOT EXISTS idx_scan_results_job ON scan_results(job_id);
CREATE INDEX IF NOT EXISTS idx_scan_results_tool ON scan_results(tool_name);
"""
