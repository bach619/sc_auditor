"""JSON file storage for StarkNet source results under /data/starknet-source/."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import structlog

from src.models import FetchResult

log = structlog.get_logger()


class StarkNetSourceStorage:

    def __init__(self, data_dir: str | Path | None = None) -> None:
        if data_dir is None:
            data_dir = os.getenv("DATA_DIR", "/tmp/sc_auditor_data")
        self._base = Path(data_dir) / "starknet-source"
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, address: str) -> Path:
        return self._base / f"{address.lower()}.json"

    def save_source(self, address: str, result: FetchResult) -> bool:
        path = self._path(address)
        data = {
            "address": address.lower(),
            "contract_name": result.contract_name,
            "source_files": result.source_files,
            "compiler_version": result.compiler_version,
            "abi": result.abi,
        }
        return self._write_json(path, data)

    def load_source(self, address: str) -> FetchResult | None:
        path = self._path(address)
        data = self._read_json(path)
        if not data:
            return None
        return FetchResult(
            success=True,
            contract_name=data.get("contract_name", ""),
            source_files=data.get("source_files", {}),
            compiler_version=data.get("compiler_version", ""),
            abi=data.get("abi"),
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
