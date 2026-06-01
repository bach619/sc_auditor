"""Local utility functions for 03-source service.

Duplicated from vyper_lib.utils to avoid dependency on vyper_lib
package which is not installed in the Docker container.
"""

from __future__ import annotations

import json
from typing import Any


def parse_standard_input_json(raw: str) -> dict[str, str] | None:
    """Parse Etherscan/Blockscout standard JSON input format.

    Handles both ``{{...}}`` (double-braced) and ``{...}`` (single) wrapping.
    Returns dict of source path → source code, or None if not parseable.
    """
    if not raw.startswith("{"):
        return None
    cleaned = raw
    if cleaned.startswith("{{") and cleaned.endswith("}}"):
        cleaned = cleaned[1:-1]
    try:
        parsed: dict[str, Any] = json.loads(cleaned)
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
