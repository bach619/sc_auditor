"""JSON storage for Cairo scan results under /data/scanner-cairo/."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import structlog

from src.models import CairoScanResponse

log = structlog.get_logger()


class CairoScanStorage:

    def __init__(self, data_dir: str | Path | None = None) -> None:
        if data_dir is None:
            data_dir = os.getenv("DATA_DIR", "/tmp/sc_auditor_data")
        self._base = Path(data_dir) / "scanner-cairo"
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, request_id: str) -> Path:
        return self._base / f"{request_id}.json"

    def save_scan_result(self, request_id: str, result: CairoScanResponse) -> bool:
        path = self._path(request_id)
        data = {
            "findings": [f.model_dump() for f in result.findings],
            "detector_results": {
                k: [f.model_dump() for f in v]
                for k, v in result.detector_results.items()
            },
            "duration_seconds": result.duration_seconds,
        }
        return self._write_json(path, data)

    def load_scan_result(self, request_id: str) -> CairoScanResponse | None:
        path = self._path(request_id)
        data = self._read_json(path)
        if not data:
            return None
        from src.models import Finding
        return CairoScanResponse(
            findings=[Finding(**f) for f in data.get("findings", [])],
            detector_results={
                k: [Finding(**f) for f in v]
                for k, v in data.get("detector_results", {}).items()
            },
            duration_seconds=data.get("duration_seconds", 0.0),
        )

    @staticmethod
    def _write_json(path: Path, data: Any) -> bool:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            tmp.replace(path)
            return True
        except OSError as exc:
            log.error("storage.write_failed", path=str(path), error=str(exc))
            if tmp.exists():
                tmp.unlink()
            return False

    @staticmethod
    def _read_json(path: Path) -> Any:
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("storage.read_failed", path=str(path), error=str(exc))
            return None
