"""SQLite schema for 01-config service.

Replaces: /data/config/config.json
Database:  /data/config/config.db

Tables:
    settings  — key-value configuration store
    api_keys  — API key management (optional, for future use)
"""

SCHEMA_SQL = """
-- Main configuration store (key-value pairs with categories)
CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,            -- JSON-encoded value
    category    TEXT NOT NULL DEFAULT 'general',
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Index for category-based queries
CREATE INDEX IF NOT EXISTS idx_settings_category ON settings(category);

-- API key store (future use)
CREATE TABLE IF NOT EXISTS api_keys (
    provider    TEXT PRIMARY KEY,          -- openai | anthropic | infura | alchemy
    key_hash    TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1
);
"""

# Default settings to insert if table is empty
DEFAULT_SETTINGS = [
    ("immunefi_refresh_interval", "3600", "scheduler"),
    ("openai_model", '"gpt-4o"', "ai"),
    ("anthropic_model", '"claude-3-5-sonnet-20241022"', "ai"),
    ("max_concurrent_scans", "2", "performance"),
    ("max_concurrent_ai", "1", "performance"),
    ("priority_factors", '{"bounty":0.4,"similarity":0.3,"chain":0.15,"freshness":0.1,"tp_history":0.05}', "scoring"),
    ("notification_channels", "[]", "notifications"),
    ("rpc_endpoints", '{"ethereum":"https://eth.llamarpc.com","arbitrum":"https://arb1.arbitrum.io/rpc"}', "chains"),
    ("exploit_timeout_seconds", "300", "performance"),
    ("daemon_interval_minutes", "60", "scheduler"),
]
