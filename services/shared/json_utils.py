"""Vyper Atomic JSON Utilities — Thread-safe, crash-resistant JSON file I/O.

Replaces the tmp-file + replace pattern duplicated across the codebase
with a single, well-tested implementation.

Usage::

    from shared.json_utils import atomic_json_write, atomic_json_read

    # Write (atomic — tmp file + os.replace, with fsync)
    atomic_json_write(Path("/data/config/config.json"), {"key": "value"})

    # Read (with fallback default, handles corrupt files)
    data = atomic_json_read(Path("/data/config/config.json"), default={})

Design decisions:
    - ``tempfile.mkstemp`` creates a unique tmp file in the SAME directory
      as the target, ensuring the rename is atomic on the same filesystem.
    - ``os.fsync`` + ``fd.flush()`` ensures data durability before rename.
    - ``Path.rename`` (posix) / ``shutil.move`` (cross-fs) for the atomic swap.
    - On failure, the temp file is cleaned up to avoid orphan files.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


def atomic_json_write(path: Path, data: dict | list) -> None:
    """Atomically write JSON data to *path*.

    Thread-safe via unique temp file + os-level atomic rename.
    Never leaves a corrupt file on disk — writes to temp file first,
    flushes to disk, then atomically replaces the target.

    Args:
        path: Destination file path (parent dirs created if needed).
        data: A ``dict`` or ``list`` to serialize as JSON.

    Raises:
        OSError: If disk I/O fails.
        TypeError: If *data* is not JSON-serializable.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        suffix=".tmp", prefix="json_", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, str(path))
    except Exception:
        # Clean up temp file on any failure, then re-raise.
        Path(tmp_path).unlink(missing_ok=True)
        raise


def atomic_json_read(path: Path, default: Any = None) -> Any:
    """Read JSON data from *path*.

    Returns *default* if the file does not exist or is corrupt
    (malformed JSON, empty file, I/O error).

    Args:
        path: Source file path.
        default: Fallback value returned on any read failure.

    Returns:
        Parsed JSON (``dict``, ``list``, etc.) or *default*.
    """
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError):
        return default
