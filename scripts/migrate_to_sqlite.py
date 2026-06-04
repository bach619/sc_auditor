#!/usr/bin/env python3
"""Batch migration script — JSON to SQLite for all Vyper services.

Usage:
    python scripts/migrate_to_sqlite.py --service all
    python scripts/migrate_to_sqlite.py --service 01-config --mode dual
    python scripts/migrate_to_sqlite.py --service 07-classifier --mode sqlite
    python scripts/migrate_to_sqlite.py --rollback --service 01-config

Modes:
    sqlite  — SQLite only (production)
    json    — JSON only (legacy / rollback)
    dual    — Write to both during migration (safe transition)
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.shared.storage import SqliteStore, SimpleSQLiteStore, StoreConfig

# ════════════════════════════════════════════════════════════════
# Service registry — maps service name to DB path + schema
# ════════════════════════════════════════════════════════════════

SERVICE_REGISTRY = {
    # P0 — Critical
    "01-config": {
        "db_path": "/data/config/config.db",
        "schema_sql": None,  # Uses ConfigManagerSQLite
        "priority": "P0",
        "status": "ready",
    },
    "07-classifier": {
        "db_path": "/data/classifier/classifier.db",
        "schema_sql": None,  # Uses ClassifierSQLiteStore
        "priority": "P0",
        "status": "ready",
    },
    "08-exploit": {
        "db_path": "/data/exploit/exploit.db",
        "schema_sql": None,  # Uses ExploitSQLiteStore
        "priority": "P0",
        "status": "ready",
    },
    "11-orchestrator": {
        "db_path": "/data/orchestrator/orchestrator.db",
        "schema_sql": None,  # Uses OrchestratorSQLiteStore
        "priority": "P0",
        "status": "ready",
    },
    # P1 — High Impact
    "02-immunefi": {
        "db_path": "/data/immunefi/immunefi.db",
        "schema_sql": "immunefi",
        "priority": "P1",
        "status": "ready",
    },
    "03-source": {
        "db_path": "/data/source/source.db",
        "schema_sql": "source",
        "priority": "P1",
        "status": "ready",
    },
    "06-ai": {
        "db_path": "/data/ai/ai_cache.db",
        "schema_sql": "ai",
        "priority": "P1",
        "status": "ready",
    },
    "14-agent": {
        "db_path": "/data/agent/memory.db",
        "schema_sql": "agent",
        "priority": "P1",
        "status": "ready",
    },
    "04-scanner": {
        "db_path": "/data/scanner/scanner.db",
        "schema_sql": "scanner",
        "priority": "P1",
        "status": "ready",
    },
}

# P2/P3 services — all use SimpleSQLiteStore
SIMPLE_SERVICES = [
    "04a-scanner-slither",
    "04b-scanner-echidna",
    "04c-scanner-forge",
    "04d-scanner-halmos",
    "04e-scanner-manticore",
    "05-scanner-mythril",
    "09-reporter",
    "10-notifier",
    "12-webhook",
    "13-upkeep",
    "15-dashboard",
    "16-submission",
    "18-code4rena",
    "19-sherlock",
    "20-cantina",
    "21-hats",
    "22-source-starknet",
    "23-scanner-cairo",
]

# Add simple services to registry
for svc in SIMPLE_SERVICES:
    safe_name = svc.replace("-", "_").split("-", 1)[-1] if svc[0].isdigit() else svc
    SERVICE_REGISTRY[svc] = {
        "db_path": f"/data/{safe_name}/{safe_name}.db",
        "schema_sql": None,
        "priority": "P2" if svc.startswith(("04", "05", "09", "10")) else "P3",
        "status": "ready",
    }


def get_service(service_name: str) -> dict:
    """Get service config from registry."""
    if service_name not in SERVICE_REGISTRY:
        print(f"Unknown service: {service_name}")
        print(f"Available: {', '.join(sorted(SERVICE_REGISTRY.keys()))}")
        sys.exit(1)
    return SERVICE_REGISTRY[service_name]


def init_sqlite_store(service_name: str) -> SqliteStore | SimpleSQLiteStore:
    """Initialize SQLite store for a service based on its schema."""
    svc = get_service(service_name)
    db_path = svc["db_path"]
    schema_type = svc["schema_sql"]

    if schema_type and schema_type in ("immunefi", "source", "ai", "agent", "scanner"):
        from services.shared.storage.service_schemas import (
            SCHEMA_SQL as IMMUNEFI_SCHEMA,
            SOURCE_SCHEMA_SQL,
            AI_SCHEMA_SQL,
            AGENT_SCHEMA_SQL,
            SCANNER_SCHEMA_SQL,
        )
        schema_map = {
            "immunefi": IMMUNEFI_SCHEMA,
            "source": SOURCE_SCHEMA_SQL,
            "ai": AI_SCHEMA_SQL,
            "agent": AGENT_SCHEMA_SQL,
            "scanner": SCANNER_SCHEMA_SQL,
        }
        return SimpleSQLiteStore(db_path=db_path, schema_sql=schema_map[schema_type])

    # P2/P3 services — generic store
    return SqliteStore(StoreConfig(db_path=db_path, journal_mode="WAL"))


def migrate_json_to_sqlite(service_name: str, json_dir: str) -> int:
    """Migrate JSON files to SQLite for a service."""
    svc = get_service(service_name)
    json_path = Path(json_dir)
    if not json_path.exists():
        print(f"[{service_name}] No JSON data at {json_path} — skipping")
        return 0

    store = init_sqlite_store(service_name)
    json_files = list(json_path.glob("*.json"))
    if not json_files:
        print(f"[{service_name}] No JSON files found — skipping")
        return 0

    migrated = 0
    for jf in json_files:
        try:
            data = json.loads(jf.read_text())
            if isinstance(data, list):
                # List of records → batch insert
                if hasattr(store, "insert_batch"):
                    store.insert_batch(data)
                else:
                    table = jf.stem
                    for row in data:
                        if isinstance(row, dict):
                            store.insert(table, row)
                migrated += len(data) if isinstance(data, list) else 1
            elif isinstance(data, dict):
                store.insert(jf.stem, data)
                migrated += 1
            print(f"  ✓ {jf.name} ({len(data) if isinstance(data, list) else 1} records)")
        except Exception as exc:
            print(f"  ✗ {jf.name}: {exc}")

    print(f"[{service_name}] Migrated {migrated} records from {len(json_files)} files")
    return migrated


def main():
    parser = argparse.ArgumentParser(description="JSON → SQLite migration tool for Vyper")
    parser.add_argument("--service", "-s", default="all", help="Service name or 'all'")
    parser.add_argument("--mode", "-m", default="dual",
                       choices=["sqlite", "json", "dual"],
                       help="Storage mode")
    parser.add_argument("--rollback", action="store_true", help="Rollback to JSON mode")
    parser.add_argument("--json-dir", default="", help="Directory containing JSON files to migrate")
    parser.add_argument("--status", action="store_true", help="Show migration status for all services")
    args = parser.parse_args()

    if args.status:
        print("\n=== Vyper SQLite Migration Status ===\n")
        for name, svc in sorted(SERVICE_REGISTRY.items()):
            mode = os.environ.get("STORAGE_ENGINE", "json")
            db_exists = Path(svc["db_path"]).exists()
            icon = "✅" if db_exists else "⬜"
            print(f"  [{svc['priority']}] {name:25s}  {icon}  mode={mode}  db={'exists' if db_exists else 'pending'}")
        return

    if args.service == "all":
        services = list(SERVICE_REGISTRY.keys())
        print(f"Migrating ALL {len(services)} services...")
    else:
        services = [args.service]

    for svc_name in services:
        svc = get_service(svc_name)
        print(f"\n[{svc['priority']}] {svc_name}...")

        if args.rollback:
            print(f"  Rolling back to JSON mode")
            # Rollback = just remove the .db file (JSON is still there)
            db_file = Path(svc["db_path"])
            if db_file.exists():
                db_file.unlink()
                print(f"  Removed {db_file}")
            continue

        # Initialize store (creates tables)
        store = init_sqlite_store(svc_name)
        print(f"  SQLite store initialized: {svc['db_path']}")

        # Migrate JSON data if path provided
        if args.json_dir:
            migrate_json_to_sqlite(svc_name, args.json_dir)

        # Health check
        if hasattr(store, "health"):
            health = store.health()
            print(f"  Health: status={health.get('status')}, "
                  f"tables={health.get('table_count', 'N/A')}, "
                  f"size={health.get('total_size_mb', 'N/A')}MB")

    print("\n=== Migration complete ===")


if __name__ == "__main__":
    main()
