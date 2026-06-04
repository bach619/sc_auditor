"""SQLite schema for 07-classifier service.

Replaces: /data/classifier/findings.json, patterns.json, metrics.json
          /data/learning/feedback.json, false_negatives.json, false_positives.json
Database:  /data/classifier/classifier.db
"""

SCHEMA_SQL = """
-- Core findings table (replaces findings.json)
CREATE TABLE IF NOT EXISTS findings (
    finding_id          TEXT PRIMARY KEY,
    audit_id            TEXT,
    title               TEXT NOT NULL,
    description         TEXT,
    severity            TEXT NOT NULL,          -- critical|high|medium|low|info
    tool_name           TEXT,                   -- slither|mythril|echidna|halmos|manticore
    tool_version        TEXT,
    file_path           TEXT,
    line_start          INTEGER,
    line_end            INTEGER,
    code_snippet        TEXT,
    swc_id              TEXT,
    cwe_id              TEXT,
    impact              TEXT,
    recommendation      TEXT,
    ai_confidence       REAL,
    ai_verdict          TEXT,                   -- unknown|tp|fp|tn|fn
    classification       TEXT DEFAULT 'unknown', -- Final classification
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Classification layers (one finding can have multiple classification stages)
CREATE TABLE IF NOT EXISTS classification_layers (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id          TEXT NOT NULL,
    stage               TEXT NOT NULL,          -- raw|ai_analyzed|classified|exploit_confirmed|human_reviewed|immunefi_submitted
    classification       TEXT NOT NULL,          -- unknown|true_positive|false_positive|true_negative|false_negative
    source              TEXT NOT NULL,          -- tool_raw|ai_verdict|classifier|exploit|human_review|immunefi_feedback|reclassification
    confidence          REAL NOT NULL DEFAULT 0.0,
    reasoning           TEXT,
    timestamp           TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (finding_id) REFERENCES findings(finding_id)
);

-- Patterns (replaces patterns.json)
CREATE TABLE IF NOT EXISTS patterns (
    pattern_id          TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    pattern_type        TEXT NOT NULL,          -- code_pattern|keyword_pattern|severity_pattern|tool_pattern
    classification       TEXT NOT NULL,
    description         TEXT,
    rules_json          TEXT NOT NULL,          -- JSON-encoded rules dict
    effectiveness_score REAL DEFAULT 0.0,
    match_count         INTEGER DEFAULT 0,
    correct_count       INTEGER DEFAULT 0,
    source_feedback_id  TEXT,
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Feedback (replaces /data/learning/feedback.json)
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id         TEXT PRIMARY KEY,
    finding_id          TEXT NOT NULL,
    audit_id            TEXT,
    correct_classification TEXT NOT NULL,
    original_classification TEXT,
    notes               TEXT,
    status              TEXT DEFAULT 'initial', -- initial|reviewed|finalized
    reviewed_by         TEXT,
    source              TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- False negatives / positives tracking
CREATE TABLE IF NOT EXISTS false_records (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    record_type         TEXT NOT NULL,          -- false_negative|false_positive
    finding_id          TEXT NOT NULL,
    audit_id            TEXT,
    reason              TEXT,
    recorded_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Metrics (replaces metrics.json)
CREATE TABLE IF NOT EXISTS metrics (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    date                TEXT NOT NULL,          -- YYYY-MM-DD
    tool_name           TEXT,                   -- NULL = aggregate
    tp                  INTEGER DEFAULT 0,
    fp                  INTEGER DEFAULT 0,
    tn                  INTEGER DEFAULT 0,
    fn                  INTEGER DEFAULT 0,
    precision           REAL DEFAULT 0.0,
    recall              REAL DEFAULT 0.0,
    f1_score            REAL DEFAULT 0.0,
    accuracy            REAL DEFAULT 0.0,
    overall_score       REAL DEFAULT 0.0,
    calculated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(date, tool_name)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
CREATE INDEX IF NOT EXISTS idx_findings_audit ON findings(audit_id);
CREATE INDEX IF NOT EXISTS idx_findings_classification ON findings(classification);
CREATE INDEX IF NOT EXISTS idx_findings_tool ON findings(tool_name);
CREATE INDEX IF NOT EXISTS idx_layers_finding ON classification_layers(finding_id);
CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_patterns_active ON patterns(is_active);
CREATE INDEX IF NOT EXISTS idx_feedback_finding ON feedback(finding_id);
CREATE INDEX IF NOT EXISTS idx_metrics_date ON metrics(date);
"""
