"""Simple JSON file storage for Hats Finance vaults data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger()

DATA_DIR = Path("/data/hats")


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_vaults(vaults: list[dict[str, Any]]) -> bool:
    """Write all vaults to /data/hats/vaults.json."""
    _ensure_dir()
    path = DATA_DIR / "vaults.json"
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(vaults, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(path)
        log.info("storage.save_vaults.ok", count=len(vaults))
        return True
    except (OSError, PermissionError) as e:
        log.error("storage.save_vaults.error", error=str(e))
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        return False


def load_vaults() -> list[dict[str, Any]]:
    """Read all vaults from /data/hats/vaults.json."""
    _ensure_dir()
    path = DATA_DIR / "vaults.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as e:
        log.warning("storage.load_vaults.error", error=str(e))
        return []


def save_vault_detail(vault_id: str, detail: dict[str, Any]) -> bool:
    """Write vault detail to /data/hats/vault_{id}.json."""
    _ensure_dir()
    path = DATA_DIR / f"vault_{vault_id}.json"
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(detail, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(path)
        return True
    except (OSError, PermissionError) as e:
        log.error("storage.save_vault_detail.error", vault_id=vault_id, error=str(e))
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        return False


def load_vault_detail(vault_id: str) -> dict[str, Any] | None:
    """Read vault detail from /data/hats/vault_{id}.json."""
    _ensure_dir()
    path = DATA_DIR / f"vault_{vault_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.warning("storage.load_vault_detail.error", vault_id=vault_id, error=str(e))
        return None
