"""Backup Manager for Vyper Upkeep Service.

Creates, lists, and restores compressed backups of the entire
``/data/`` directory tree. Backups are ``tar.gz`` archives stored
under ``/data/upkeep/backups/``.
"""

from __future__ import annotations

import asyncio
import os
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import structlog

from src.models import BackupInfo, BackupResult, RestoreResult

log = structlog.get_logger()

# ── Constants ───────────────────────────────────────────────

BACKUP_DIR = Path("/data/upkeep/backups")
BACKUP_SOURCE = Path("/data")
BACKUP_PREFIX = "vyper-backup"

# Directories to exclude from backup (relative to BACKUP_SOURCE)
EXCLUDE_DIRS: set[str] = {
    "upkeep/backups",  # Don't nest backups inside backups
}

# Maximum bytes to track for progress reporting (100 MB chunks)
PROGRESS_CHUNK_BYTES = 100 * 1024 * 1024


# ── BackupManager ────────────────────────────────────────────


class BackupManager:
    """Manages Vyper data backup and restore lifecycle.

    Responsibilities:
        - Create compressed (``tar.gz``) backups of ``/data/``.
        - List available backups with metadata.
        - Restore from a selected backup.
        - Auto-create pre-restore snapshots.
    """

    def __init__(
        self,
        backup_dir: Path = BACKUP_DIR,
        source_dir: Path = BACKUP_SOURCE,
    ) -> None:
        self.backup_dir = backup_dir
        self.source_dir = source_dir

        backup_dir.mkdir(parents=True, exist_ok=True)

    # ── Create Backup ────────────────────────────────────────

    async def create_backup(self) -> BackupResult:
        """Create a compressed backup of the data directory.

        The backup is created as a ``tar.gz`` file with a timestamp
        name. Large backups report progress in chunks.

        Returns:
            BackupResult with path, size, and success status.
        """
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        name = f"{BACKUP_PREFIX}-{timestamp}"
        backup_path = self.backup_dir / f"{name}.tar.gz"

        log.info("backup.starting", name=name, path=str(backup_path))

        try:
            # Collect files to back up
            files_to_backup = _collect_files(
                self.source_dir, exclude_dirs=EXCLUDE_DIRS
            )

            if not files_to_backup:
                log.warning("backup.no_files", source=str(self.source_dir))
                return BackupResult(
                    success=False,
                    error="No files found to back up in /data/",
                )

            # Run tar in executor to avoid blocking event loop
            await asyncio.to_thread(
                _create_tar_archive,
                archive_path=backup_path,
                source_dir=self.source_dir,
                files=files_to_backup,
            )

            size_bytes = backup_path.stat().st_size
            log.info(
                "backup.complete",
                name=name,
                size_bytes=size_bytes,
                files=len(files_to_backup),
            )

            return BackupResult(
                success=True,
                name=name,
                path=str(backup_path),
                size_bytes=size_bytes,
            )

        except (OSError, tarfile.TarError) as exc:
            log.exception("backup.failed", error=str(exc))
            # Clean up partial archive
            if backup_path.exists():
                try:
                    backup_path.unlink()
                except OSError:
                    pass
            return BackupResult(
                success=False,
                error=str(exc),
            )

    # ── List Backups ─────────────────────────────────────────

    async def list_backups(self) -> list[BackupInfo]:
        """List all available backup archives with metadata.

        Returns:
            List of BackupInfo sorted by creation date descending.
        """
        backups: list[BackupInfo] = []
        now = datetime.now(UTC)

        try:
            for entry in sorted(
                self.backup_dir.iterdir(),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            ):
                if not entry.is_file() or not entry.name.endswith(".tar.gz"):
                    continue

                stat = entry.stat()
                # Extract a human-readable name from the file stem
                name = entry.stem

                created_ts = datetime.fromtimestamp(
                    stat.st_mtime, tz=UTC
                )
                age_days = round((now - created_ts).total_seconds() / 86400, 1)

                backups.append(
                    BackupInfo(
                        name=name,
                        size_bytes=stat.st_size,
                        created_at=created_ts.isoformat(),
                        age_days=age_days,
                        path=str(entry),
                    )
                )
        except OSError as exc:
            log.error("backup.list_failed", error=str(exc))

        return backups

    # ── Restore Backup ───────────────────────────────────────

    async def restore_backup(self, backup_name: str) -> RestoreResult:
        """Restore data directory from a backup archive.

        Before restoring, creates an automatic pre-restore backup
        so the operation is reversible.

        Args:
            backup_name: Backup name (with or without ``.tar.gz``).

        Returns:
            RestoreResult with success/failure and pre-restore info.
        """
        # Normalise: add .tar.gz if missing
        if not backup_name.endswith(".tar.gz"):
            backup_name += ".tar.gz"

        backup_path = self.backup_dir / backup_name
        if not backup_path.exists():
            return RestoreResult(
                success=False,
                backup_name=backup_name,
                backup_path=str(backup_path),
                error=f"Backup not found: {backup_name}",
            )

        log.info(
            "restore.starting",
            backup=backup_name,
            source=str(self.source_dir),
        )

        try:
            # ── Step 1: Create pre-restore snapshot ──────────
            pre_restore = await self.create_backup()
            pre_name = pre_restore.name if pre_restore.success else None

            if pre_restore.success:
                log.info("restore.pre_backup_created", name=pre_name)

            # ── Step 2: Verify archive integrity ─────────────
            is_valid = await asyncio.to_thread(
                _verify_tar_archive, archive_path=backup_path
            )
            if not is_valid:
                return RestoreResult(
                    success=False,
                    backup_name=backup_name,
                    backup_path=str(backup_path),
                    pre_restore_backup=pre_name,
                    error="Backup archive is corrupted or invalid",
                )

            # ── Step 3: Extract backup ───────────────────────
            await asyncio.to_thread(
                _extract_tar_archive,
                archive_path=backup_path,
                target_dir=self.source_dir,
            )

            log.info(
                "restore.complete",
                backup=backup_name,
                pre_restore=pre_name,
            )

            return RestoreResult(
                success=True,
                backup_name=backup_name,
                backup_path=str(backup_path),
                pre_restore_backup=pre_name,
            )

        except (OSError, tarfile.TarError, RuntimeError) as exc:
            log.exception("restore.failed", error=str(exc))
            return RestoreResult(
                success=False,
                backup_name=backup_name,
                backup_path=str(backup_path),
                error=str(exc),
            )

    # ── Prune Old Backups ────────────────────────────────────

    async def prune_backups(
        self, max_age_days: int = 30, min_keep: int = 5
    ) -> int:
        """Remove backups older than ``max_age_days``, keeping at least
        ``min_keep`` most recent backups.

        Returns:
            Number of backups removed.
        """
        backups = await self.list_backups()
        if len(backups) <= min_keep:
            return 0

        removed = 0
        # Keep the most recent N regardless of age
        keep = set(b.name for b in backups[:min_keep])

        for backup in backups:
            if backup.name in keep:
                continue
            if backup.age_days > max_age_days:
                try:
                    Path(backup.path).unlink()
                    removed += 1
                    log.info("backup.pruned", name=backup.name)
                except OSError as exc:
                    log.warning(
                        "backup.prune_failed",
                        name=backup.name,
                        error=str(exc),
                    )

        if removed:
            log.info(
                "backup.prune_complete",
                removed=removed,
                max_age_days=max_age_days,
            )

        return removed


# ── Factory ──────────────────────────────────────────────────


def create_backup_manager() -> BackupManager:
    """Create a BackupManager instance."""
    return BackupManager()


# ═══════════════════════════════════════════════════════════════
# BackupScheduler — scheduled full backups
# ═══════════════════════════════════════════════════════════════

import asyncio
import shutil
import time as _time

FULL_BACKUP_DIR = Path("/data/backups")
FULL_BACKUP_INTERVAL = 6 * 3600  # 6 hours
FULL_BACKUP_MAX_AGE_DAYS = 30


class BackupScheduler:
    """Periodic full-backup scheduler.

    Backs up all data directories to ``/data/backups/full_backup_YYYYMMDD_HHMMSS.tar.gz``
    every 6 hours and cleans up backups older than 30 days.
    """

    def __init__(
        self,
        backup_dir: Path = FULL_BACKUP_DIR,
        source_dir: Path = BACKUP_SOURCE,
        interval: int = FULL_BACKUP_INTERVAL,
        max_age_days: int = FULL_BACKUP_MAX_AGE_DAYS,
    ) -> None:
        self.backup_dir = backup_dir
        self.source_dir = source_dir
        self.interval = interval
        self.max_age_days = max_age_days
        self._task: asyncio.Task | None = None

        backup_dir.mkdir(parents=True, exist_ok=True)

    async def backup_all(self) -> dict:
        """Create a full backup of all data directories.

        Returns:
            dict with path, size_bytes, and success status.
        """
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        name = f"full_backup_{timestamp}"
        backup_path = self.backup_dir / f"{name}.tar.gz"

        log.info("backup_scheduler.starting", name=name)

        try:
            files_to_backup = _collect_files(
                self.source_dir, exclude_dirs=EXCLUDE_DIRS
            )

            if not files_to_backup:
                log.warning("backup_scheduler.no_files")
                return {"success": False, "error": "No files found to back up"}

            await asyncio.to_thread(
                _create_tar_archive,
                archive_path=backup_path,
                source_dir=self.source_dir,
                files=files_to_backup,
            )

            size_bytes = backup_path.stat().st_size
            log.info(
                "backup_scheduler.complete",
                name=name,
                size_bytes=size_bytes,
            )

            return {
                "success": True,
                "name": name,
                "path": str(backup_path),
                "size_bytes": size_bytes,
            }

        except (OSError, tarfile.TarError) as exc:
            log.exception("backup_scheduler.failed", error=str(exc))
            if backup_path.exists():
                try:
                    backup_path.unlink()
                except OSError:
                    pass
            return {"success": False, "error": str(exc)}

    async def cleanup_old_backups(self) -> dict:
        """Remove full backups older than ``max_age_days``.

        Returns:
            dict with removed count and freed bytes.
        """
        now = datetime.now(UTC)
        removed = 0
        freed_bytes = 0

        try:
            for entry in sorted(
                self.backup_dir.iterdir(),
                key=lambda p: p.stat().st_mtime,
            ):
                if not entry.is_file() or not entry.name.endswith(".tar.gz"):
                    continue
                if not entry.name.startswith("full_backup_"):
                    continue

                stat = entry.stat()
                age_days = (now.timestamp() - stat.st_mtime) / 86400

                if age_days > self.max_age_days:
                    size = stat.st_size
                    try:
                        entry.unlink()
                        removed += 1
                        freed_bytes += size
                        log.info(
                            "backup_scheduler.pruned",
                            name=entry.name,
                            age_days=round(age_days, 1),
                        )
                    except OSError as exc:
                        log.warning(
                            "backup_scheduler.prune_failed",
                            name=entry.name,
                            error=str(exc),
                        )
        except OSError as exc:
            log.error("backup_scheduler.cleanup_failed", error=str(exc))

        if removed:
            log.info(
                "backup_scheduler.cleanup_complete",
                removed=removed,
                freed_bytes=freed_bytes,
            )

        return {"removed": removed, "freed_bytes": freed_bytes}

    async def start(self) -> None:
        """Start the periodic backup loop (non-blocking)."""
        if self._task is not None:
            log.warning("backup_scheduler.already_running")
            return

        self._task = asyncio.create_task(self._run_loop())
        log.info(
            "backup_scheduler.started",
            interval_hours=self.interval / 3600,
            max_age_days=self.max_age_days,
        )

    async def stop(self) -> None:
        """Stop the periodic backup loop."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            log.info("backup_scheduler.stopped")

    async def _run_loop(self) -> None:
        """Internal loop: backup + cleanup, then sleep."""
        while True:
            try:
                await asyncio.sleep(self.interval)
                await self.backup_all()
                await self.cleanup_old_backups()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("backup_scheduler.loop_error", error=str(exc))
                await asyncio.sleep(60)  # back-off on error


def create_backup_scheduler() -> BackupScheduler:
    """Create a BackupScheduler instance."""
    return BackupScheduler()


# ── Internal Functions ───────────────────────────────────────


def _collect_files(
    source_dir: Path, exclude_dirs: set[str]
) -> list[Path]:
    """Recursively collect files to back up, excluding certain dirs."""
    files: list[Path] = []
    source_str = str(source_dir)

    try:
        for root, dirs, file_names in os.walk(source_dir):
            rel_root = os.path.relpath(root, source_str)

            # Prune excluded directories from walk
            dirs[:] = [
                d
                for d in dirs
                if os.path.join(rel_root, d) not in exclude_dirs
                and d not in exclude_dirs
            ]

            for name in file_names:
                full_path = Path(root) / name
                rel_path = os.path.relpath(str(full_path), source_str)
                # Exclude specific paths
                if rel_path in exclude_dirs or any(
                    rel_path.startswith(e + os.sep) for e in exclude_dirs
                ):
                    continue
                files.append(full_path)
    except OSError as exc:
        log.warning("backup.collect_files_failed", error=str(exc))

    return files


def _create_tar_archive(
    archive_path: Path,
    source_dir: Path,
    files: list[Path],
) -> None:
    """Create a tar.gz archive from the given file list.

    Runs in a thread executor — blocking I/O.
    """
    with tarfile.open(archive_path, "w:gz", compresslevel=6) as tar:
        for file_path in files:
            try:
                # Store relative to source_dir
                arcname = str(file_path.relative_to(source_dir))
                tar.add(str(file_path), arcname=arcname)
            except (OSError, tarfile.TarError) as exc:
                log.warning(
                    "backup.skip_file",
                    path=str(file_path),
                    error=str(exc),
                )
                continue


def _verify_tar_archive(archive_path: Path) -> bool:
    """Verify that a tar.gz archive is not corrupted."""
    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            members = tar.getmembers()
            return len(members) > 0
    except (tarfile.TarError, OSError):
        return False


def _extract_tar_archive(
    archive_path: Path,
    target_dir: Path,
) -> None:
    """Extract a tar.gz archive into the target directory.

    Runs in a thread executor — blocking I/O.
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive_path, "r:gz") as tar:
        # Security: forbid absolute paths and path traversal
        for member in tar.getmembers():
            if member.name.startswith("/") or ".." in member.name:
                raise RuntimeError(
                    f"Unsafe path in archive: {member.name}"
                )
        tar.extractall(path=str(target_dir))
