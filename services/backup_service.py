"""
services/backup_service.py — Database Backup Service.

Provides manual and scheduled automatic backups.
"""
from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, QObject, Signal

from app.config import BACKUPS_DIR, DEFAULT_BACKUP_INTERVAL_MIN
from app.logger import get_logger

log = get_logger("backup")


class BackupService(QObject):
    """Manages database backups with optional auto-scheduling."""

    backup_created = Signal(str)   # path to backup
    backup_failed = Signal(str)    # error message

    def __init__(self, parent=None):
        super().__init__(parent)
        self._db_path: Optional[str] = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._auto_backup)
        self._interval_min: int = DEFAULT_BACKUP_INTERVAL_MIN

    def set_database(self, path: str) -> None:
        self._db_path = path

    def backup(self, label: str = "") -> Optional[str]:
        """Create a timestamped backup. Returns backup path or None on error."""
        if not self._db_path or not Path(self._db_path).exists():
            log.warning("Backup skipped — no valid database path.")
            return None
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = Path(self._db_path).stem
            suffix = f"_{label}" if label else ""
            dest = BACKUPS_DIR / f"{stem}{suffix}_{ts}.db"
            shutil.copy2(self._db_path, dest)
            log.info("Backup created: %s", dest)
            self.backup_created.emit(str(dest))
            return str(dest)
        except Exception as exc:
            log.error("Backup failed: %s", exc)
            self.backup_failed.emit(str(exc))
            return None

    def backup_before_operation(self, operation: str) -> Optional[str]:
        """Create a safety backup before a destructive operation."""
        return self.backup(label=operation)

    def start_auto_backup(self, interval_min: int = DEFAULT_BACKUP_INTERVAL_MIN) -> None:
        self._interval_min = interval_min
        self._timer.start(interval_min * 60 * 1000)
        log.info("Auto-backup started: every %d minutes.", interval_min)

    def stop_auto_backup(self) -> None:
        self._timer.stop()
        log.info("Auto-backup stopped.")

    def _auto_backup(self) -> None:
        self.backup(label="auto")

    def list_backups(self) -> list[Path]:
        return sorted(BACKUPS_DIR.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)

    def delete_old_backups(self, keep_last: int = 10) -> None:
        backups = self.list_backups()
        for old in backups[keep_last:]:
            try:
                old.unlink()
                log.info("Deleted old backup: %s", old)
            except Exception as exc:
                log.warning("Could not delete %s: %s", old, exc)
