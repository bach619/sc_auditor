from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from src.models import Message, Submission

log = structlog.get_logger()


class SubmissionStorage:
    SCHEMA_VERSION = "1.0"

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        for sub_dir in ["submissions", "messages", "indexes"]:
            (self.data_dir / sub_dir).mkdir(parents=True, exist_ok=True)

    def write_atomic(self, path: str | Path, data: Any) -> bool:
        path = Path(path)
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(
                json.dumps(data, indent=2, default=str, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(path)
            return True
        except (OSError, PermissionError) as e:
            log.error("storage.write_atomic.error", path=str(path), error=str(e))
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            return False

    def read_json(self, path: str | Path, default: Any = None) -> Any:
        path = Path(path)
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            log.warning("storage.read_json.error", path=str(path), error=str(e))
            return default

    def save_submission(self, submission: Submission) -> bool:
        path = self.data_dir / "submissions" / f"{submission.finding_id}.json"
        data = submission.model_dump(mode="json")
        data["created_at"] = submission.created_at.isoformat()
        data["updated_at"] = submission.updated_at.isoformat()
        result = self.write_atomic(path, data)
        if result:
            self.rebuild_indexes()
        return result

    def load_submission(self, finding_id: str) -> Submission | None:
        path = self.data_dir / "submissions" / f"{finding_id}.json"
        data = self.read_json(path)
        if data is None:
            return None
        try:
            return Submission(**data)
        except Exception as e:
            log.warning("storage.load_submission.invalid", finding_id=finding_id, error=str(e))
            return None

    def delete_submission(self, finding_id: str) -> bool:
        path = self.data_dir / "submissions" / f"{finding_id}.json"
        try:
            if path.exists():
                path.unlink()
                self.rebuild_indexes()
                return True
            return False
        except OSError as e:
            log.error("storage.delete_submission.error", finding_id=finding_id, error=str(e))
            return False

    def save_message(self, message: Message) -> bool:
        msg_dir = self.data_dir / "messages" / message.submission_id
        msg_dir.mkdir(parents=True, exist_ok=True)
        path = msg_dir / f"{message.id}.json"
        return self.write_atomic(path, message.model_dump(mode="json"))

    def load_messages(self, submission_id: str) -> list[Message]:
        msg_dir = self.data_dir / "messages" / submission_id
        if not msg_dir.exists():
            return []
        messages: list[Message] = []
        for f in sorted(msg_dir.iterdir()):
            if f.suffix == ".json":
                data = self.read_json(f)
                if data:
                    try:
                        messages.append(Message(**data))
                    except Exception as e:
                        log.warning("storage.load_message.skip", file=f.name, error=str(e))
                        continue
        return sorted(messages, key=lambda m: m.created_at)

    def list_all_submissions(self) -> list[Submission]:
        submissions: list[Submission] = []
        sub_dir = self.data_dir / "submissions"
        if not sub_dir.exists():
            return submissions
        for f in sorted(sub_dir.iterdir()):
            if f.suffix == ".json":
                data = self.read_json(f)
                if data:
                    try:
                        submissions.append(Submission(**data))
                    except Exception as e:
                        log.warning("storage.list_all.skip", file=f.name, error=str(e))
                        continue
        return submissions

    def rebuild_indexes(self) -> bool:
        submissions = self.list_all_submissions()
        by_category: dict[str, list[str]] = {}
        by_status: dict[str, list[str]] = {}
        by_program: dict[str, list[str]] = {}
        by_recent: list[dict[str, str]] = []

        for sub in submissions:
            cat = sub.bug_category.value if hasattr(sub.bug_category, "value") else str(sub.bug_category)
            by_category.setdefault(cat, []).append(sub.finding_id)
            st = sub.status.value if hasattr(sub.status, "value") else str(sub.status)
            by_status.setdefault(st, []).append(sub.finding_id)
            by_program.setdefault(sub.program_slug, []).append(sub.finding_id)
            ts = sub.created_at.isoformat() if isinstance(sub.created_at, datetime) else str(sub.created_at)
            by_recent.append({"finding_id": sub.finding_id, "created_at": ts})

        by_recent.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        index_dir = self.data_dir / "indexes"
        success = True
        success &= self.write_atomic(index_dir / "by_category.json", by_category)
        success &= self.write_atomic(index_dir / "by_status.json", by_status)
        success &= self.write_atomic(index_dir / "by_program.json", by_program)
        success &= self.write_atomic(index_dir / "by_recent.json", [i["finding_id"] for i in by_recent])

        log.info("storage.indexes.rebuilt", submission_count=len(submissions))
        return success

    def get_index(self, name: str) -> Any:
        path = self.data_dir / "indexes" / f"{name}.json"
        return self.read_json(path)

    def list_by_category(self, category: str) -> list[str]:
        index = self.get_index("by_category")
        if isinstance(index, dict):
            return index.get(category, [])
        return []

    def list_by_status(self, status: str) -> list[str]:
        index = self.get_index("by_status")
        if isinstance(index, dict):
            return index.get(status, [])
        return []

    def list_by_program(self, program_slug: str) -> list[str]:
        index = self.get_index("by_program")
        if isinstance(index, dict):
            return index.get(program_slug, [])
        return []

    def read_meta(self) -> dict:
        default = {
            "schema_version": self.SCHEMA_VERSION,
            "submission_count": 0,
            "last_updated": None,
        }
        path = self.data_dir / "_meta.json"
        if not path.exists():
            return default
        meta = self.read_json(path)
        if not isinstance(meta, dict):
            return default
        return {**default, **meta}

    def write_meta(self, **kwargs: Any) -> bool:
        meta = self.read_meta()
        meta.update(kwargs)
        meta["schema_version"] = self.SCHEMA_VERSION
        meta["submission_count"] = len(self.list_all_submissions())
        meta["last_updated"] = datetime.now(UTC).isoformat()
        return self.write_atomic(self.data_dir / "_meta.json", meta)
