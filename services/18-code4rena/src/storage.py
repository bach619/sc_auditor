"""Simple JSON file storage for Code4rena data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger()

DATA_DIR = Path("/data/code4rena")


def _ensure_dir() -> None:
    """Create the data directory if it does not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, data: Any) -> bool:
    """Atomically write JSON to a file (tmp → rename)."""
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(data, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(path)
        return True
    except OSError as e:
        log.error("storage.write_json.error", path=str(path), error=str(e))
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        return False


def _read_json(path: Path) -> Any:
    """Read and parse a JSON file. Returns None if missing or corrupt."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.warning("storage.read_json.error", path=str(path), error=str(e))
        return None


def save_contests(contests: list[dict]) -> bool:
    """Save contest list to /data/code4rena/contests.json."""
    _ensure_dir()
    path = DATA_DIR / "contests.json"
    ok = _write_json(path, {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(contests),
        "contests": contests,
    })
    log.info("storage.contests_saved", count=len(contests))
    return ok


def load_contests() -> list[dict]:
    """Load contest list from /data/code4rena/contests.json."""
    path = DATA_DIR / "contests.json"
    data = _read_json(path)
    if data is None:
        return []
    return data.get("contests", []) if isinstance(data, dict) else []


def save_contest_detail(contest_id: str, detail: dict) -> bool:
    """Save contest detail to /data/code4rena/contest_{id}.json."""
    _ensure_dir()
    path = DATA_DIR / f"contest_{contest_id}.json"
    detail["saved_at"] = datetime.now(timezone.utc).isoformat()
    ok = _write_json(path, detail)
    log.info("storage.contest_detail_saved", contest_id=contest_id)
    return ok


def load_contest_detail(contest_id: str) -> dict | None:
    """Load contest detail from /data/code4rena/contest_{id}.json."""
    path = DATA_DIR / f"contest_{contest_id}.json"
    return _read_json(path)
