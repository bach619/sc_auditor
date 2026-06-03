"""Simple JSON file storage for Sherlock contests data."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger()

DATA_DIR = Path("/data/sherlock")


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_contests(contests: list[dict[str, Any]]) -> bool:
    """Write all contests to /data/sherlock/contests.json."""
    _ensure_dir()
    path = DATA_DIR / "contests.json"
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(contests, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(path)
        log.info("storage.save_contests.ok", count=len(contests))
        return True
    except (OSError, PermissionError) as e:
        log.error("storage.save_contests.error", error=str(e))
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        return False


def load_contests() -> list[dict[str, Any]]:
    """Read all contests from /data/sherlock/contests.json."""
    _ensure_dir()
    path = DATA_DIR / "contests.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as e:
        log.warning("storage.load_contests.error", error=str(e))
        return []


def save_contest_detail(contest_id: str, detail: dict[str, Any]) -> bool:
    """Write contest detail to /data/sherlock/contest_{id}.json."""
    _ensure_dir()
    path = DATA_DIR / f"contest_{contest_id}.json"
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(detail, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(path)
        return True
    except (OSError, PermissionError) as e:
        log.error("storage.save_contest_detail.error", contest_id=contest_id, error=str(e))
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        return False


def load_contest_detail(contest_id: str) -> dict[str, Any] | None:
    """Read contest detail from /data/sherlock/contest_{id}.json."""
    _ensure_dir()
    path = DATA_DIR / f"contest_{contest_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.warning("storage.load_contest_detail.error", contest_id=contest_id, error=str(e))
        return None
