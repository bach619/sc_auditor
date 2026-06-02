"""CreateBackupSkill — backup system data."""

from __future__ import annotations

from typing import Any

from shared.skills.base_skill import BaseSkill


class CreateBackupSkill(BaseSkill):
    """Create a backup of platform system data."""

    @property
    def name(self) -> str:
        return "create_backup"

    @property
    def description(self) -> str:
        return (
            "Create a comprehensive backup of platform system data including "
            "configuration, findings database, user preferences, and "
            "service state. Supports full and incremental backup modes."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "backup_type": {
                    "type": "string",
                    "enum": ["full", "incremental"],
                    "description": "Type of backup to create (default: full)",
                },
                "include_logs": {
                    "type": "boolean",
                    "description": "Include log files in backup (default: false)",
                },
                "destination": {
                    "type": "string",
                    "description": "Backup destination path (optional, uses default)",
                },
            },
        }

    @property
    def category(self) -> str:
        return "maintenance"

    async def run(
        self,
        backup_type: str = "full",
        include_logs: bool = False,
        destination: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        from ..backup import BackupManager

        backup_mgr = BackupManager()
        result = await backup_mgr.create_backup(
            backup_type=backup_type,
            include_logs=include_logs,
            destination=destination,
        )

        return {
            "skill": "create_backup",
            "backup_type": backup_type,
            "backup_id": result.get("backup_id", result.get("id", "unknown")),
            "size_bytes": result.get("size_bytes", result.get("size", 0)),
            "path": result.get("path", result.get("destination", "")),
            "duration_seconds": result.get("duration_seconds", result.get("duration", 0)),
            "success": result.get("success", True),
            "files_included": result.get("files_count", result.get("file_count", 0)),
        }
