"""
core/database/connection.py — SQLite Connection Manager.

Manages opening, closing, and caching database connections.
Supports read-only mode, lock detection, and recent DB history.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings

from app.config import (
    MAX_RECENT_DBS,
    SETTINGS_RECENT_DBS,
    SETTINGS_LAST_DB,
    APP_NAME,
    APP_AUTHOR,
)
from app.logger import get_logger

log = get_logger("connection")


class DatabaseConnection:
    """Represents one open SQLite database connection."""

    def __init__(self, path: str, read_only: bool = False):
        self.path = path
        self.name = Path(path).name
        self.read_only = read_only
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._open()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _open(self) -> None:
        try:
            if self.read_only:
                uri = f"file:{self.path}?mode=ro"
                self._conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
            else:
                self._conn = sqlite3.connect(self.path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            # Performance optimisations
            self._conn.execute("PRAGMA journal_mode = WAL;")
            self._conn.execute("PRAGMA synchronous = NORMAL;")
            self._conn.execute("PRAGMA foreign_keys = ON;")
            self._conn.execute("PRAGMA cache_size = -64000;")  # 64 MB
            log.info("Opened database: %s (read_only=%s)", self.path, self.read_only)
        except sqlite3.OperationalError as exc:
            log.error("Failed to open %s: %s", self.path, exc)
            raise

    # ── Public API ────────────────────────────────────────────────────────────

    def execute(
        self,
        sql: str,
        params: tuple = (),
        *,
        timeout: float = 30.0,
    ) -> sqlite3.Cursor:
        """Execute SQL with thread-safety and optional timeout."""
        with self._lock:
            try:
                self._conn.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)};")
                cursor = self._conn.execute(sql, params)
                return cursor
            except sqlite3.Error as exc:
                log.error("Query error on %s: %s\nSQL: %s", self.name, exc, sql)
                raise

    def executemany(self, sql: str, data) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.executemany(sql, data)

    def executescript(self, script: str) -> None:
        with self._lock:
            self._conn.executescript(script)

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    def rollback(self) -> None:
        with self._lock:
            self._conn.rollback()

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
                log.info("Closed database: %s", self.path)

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def is_locked(self) -> bool:
        """Try a harmless write to detect lock state."""
        if self.read_only:
            return False
        try:
            self._conn.execute("BEGIN IMMEDIATE;")
            self._conn.execute("ROLLBACK;")
            return False
        except sqlite3.OperationalError:
            return True

    def file_size_mb(self) -> float:
        try:
            return os.path.getsize(self.path) / (1024 * 1024)
        except OSError:
            return 0.0

    def __repr__(self) -> str:
        return f"<DatabaseConnection path={self.path!r} ro={self.read_only}>"


class ConnectionManager:
    """
    Singleton-style manager that tracks all open connections and persists
    the recent-databases list via QSettings.
    """

    def __init__(self):
        self._connections: dict[str, DatabaseConnection] = {}  # path → conn
        self._settings = QSettings(APP_AUTHOR, APP_NAME)

    # ── Open / Close ──────────────────────────────────────────────────────────

    def open(self, path: str, read_only: bool = False) -> DatabaseConnection:
        path = str(Path(path).resolve())
        if path in self._connections:
            log.debug("Returning cached connection: %s", path)
            return self._connections[path]
        conn = DatabaseConnection(path, read_only=read_only)
        self._connections[path] = conn
        self._add_recent(path)
        self._settings.setValue(SETTINGS_LAST_DB, path)
        return conn

    def close(self, path: str) -> None:
        path = str(Path(path).resolve())
        conn = self._connections.pop(path, None)
        if conn:
            conn.close()

    def close_all(self) -> None:
        for conn in list(self._connections.values()):
            conn.close()
        self._connections.clear()

    def get(self, path: str) -> Optional[DatabaseConnection]:
        return self._connections.get(str(Path(path).resolve()))

    def all_connections(self) -> list[DatabaseConnection]:
        return list(self._connections.values())

    # ── Recent databases ──────────────────────────────────────────────────────

    def _add_recent(self, path: str) -> None:
        recent = self.recent_databases()
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        recent = recent[:MAX_RECENT_DBS]
        self._settings.setValue(SETTINGS_RECENT_DBS, recent)

    def recent_databases(self) -> list[str]:
        val = self._settings.value(SETTINGS_RECENT_DBS, [])
        if isinstance(val, str):
            val = [val]
        # Filter out files that no longer exist
        return [p for p in (val or []) if os.path.isfile(p)]

    def remove_recent(self, path: str) -> None:
        recent = self.recent_databases()
        if path in recent:
            recent.remove(path)
            self._settings.setValue(SETTINGS_RECENT_DBS, recent)

    def last_database(self) -> Optional[str]:
        path = self._settings.value(SETTINGS_LAST_DB)
        if path and os.path.isfile(path):
            return path
        return None


# ── Module-level singleton ─────────────────────────────────────────────────────
connection_manager = ConnectionManager()
