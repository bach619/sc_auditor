"""Utility functions for Vyper — JSON helpers, standard-input parser."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("vyper_lib.utils")


def read_json(path: Path) -> Any:
    """Read JSON file, return None if not exists or invalid."""
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, PermissionError, OSError) as e:
        logger.error("json_read_error", path=str(path), error=str(e))
        return None


def write_json(path: Path, data: Any) -> bool:
    """Write JSON file atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, default=str)
        tmp.replace(path)
        return True
    except (OSError, TypeError) as e:
        logger.error("json_write_error", path=str(path), error=str(e))
        if tmp.exists():
            tmp.unlink()
        return False


def parse_standard_input_json(raw: str) -> dict[str, str] | None:
    """Parse Etherscan/Blockscout standard JSON input format.

    Handles both {{...}} (double-braced) and {...} (single) wrapping.
    Returns dict of source path → source code, or None if not parseable.
    """
    if not raw.startswith("{"):
        return None
    cleaned = raw
    if cleaned.startswith("{{") and cleaned.endswith("}}"):
        cleaned = cleaned[1:-1]
    try:
        parsed = json.loads(cleaned)
        std_sources = parsed.get("sources", {})
        if not std_sources:
            return None
        sources: dict[str, str] = {}
        for path, info in std_sources.items():
            content = ""
            if isinstance(info, str):
                content = info
            elif isinstance(info, dict):
                content = info.get("content", "")
            if content:
                sources[path] = content
        return sources
    except (json.JSONDecodeError, TypeError):
        return None
