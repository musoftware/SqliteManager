"""
core/database/pragma_manager.py — SQLite PRAGMA Editor.

Provides structured read/write access to SQLite PRAGMA settings,
categorised for use in the visual PRAGMA editor dialog.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Optional

from app.logger import get_logger

log = get_logger("pragma")

PRAGMA_DEFINITIONS: list[dict] = [
    # Performance
    {
        "name": "journal_mode",
        "category": "Performance",
        "description": "Controls the journal mode (DELETE, TRUNCATE, PERSIST, MEMORY, WAL, OFF).",
        "type": "choice",
        "choices": ["DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"],
        "writable": True,
    },
    {
        "name": "synchronous",
        "category": "Performance",
        "description": "Synchronisation level: 0=OFF, 1=NORMAL, 2=FULL, 3=EXTRA.",
        "type": "choice",
        "choices": ["0", "1", "2", "3"],
        "writable": True,
    },
    {
        "name": "cache_size",
        "category": "Performance",
        "description": "Page cache size (negative = KB, positive = pages).",
        "type": "int",
        "writable": True,
    },
    {
        "name": "mmap_size",
        "category": "Performance",
        "description": "Memory-mapped I/O size in bytes. 0 = disabled.",
        "type": "int",
        "writable": True,
    },
    {
        "name": "temp_store",
        "category": "Performance",
        "description": "Temp storage: 0=DEFAULT, 1=FILE, 2=MEMORY.",
        "type": "choice",
        "choices": ["0", "1", "2"],
        "writable": True,
    },
    {
        "name": "wal_autocheckpoint",
        "category": "Performance",
        "description": "WAL auto-checkpoint threshold (frames). 0=disabled.",
        "type": "int",
        "writable": True,
    },
    # Safety
    {
        "name": "foreign_keys",
        "category": "Safety",
        "description": "Enable foreign key enforcement.",
        "type": "bool",
        "writable": True,
    },
    {
        "name": "auto_vacuum",
        "category": "Safety",
        "description": "Auto-vacuum mode: 0=NONE, 1=FULL, 2=INCREMENTAL.",
        "type": "choice",
        "choices": ["0", "1", "2"],
        "writable": True,
    },
    {
        "name": "busy_timeout",
        "category": "Safety",
        "description": "Timeout (ms) before SQLITE_BUSY is returned.",
        "type": "int",
        "writable": True,
    },
    {
        "name": "locking_mode",
        "category": "Safety",
        "description": "NORMAL or EXCLUSIVE locking.",
        "type": "choice",
        "choices": ["NORMAL", "EXCLUSIVE"],
        "writable": True,
    },
    # Info (read-only)
    {
        "name": "page_size",
        "category": "Info",
        "description": "Database page size in bytes.",
        "type": "int",
        "writable": False,
    },
    {
        "name": "page_count",
        "category": "Info",
        "description": "Total number of pages in the database.",
        "type": "int",
        "writable": False,
    },
    {
        "name": "freelist_count",
        "category": "Info",
        "description": "Number of free pages (fragmentation indicator).",
        "type": "int",
        "writable": False,
    },
    {
        "name": "encoding",
        "category": "Info",
        "description": "Text encoding (UTF-8, UTF-16, etc.).",
        "type": "str",
        "writable": False,
    },
    {
        "name": "user_version",
        "category": "Info",
        "description": "User-defined integer version number.",
        "type": "int",
        "writable": True,
    },
]


class PragmaManager:
    """Read and write SQLite PRAGMAs via an open sqlite3 connection."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def read(self, name: str) -> Any:
        try:
            row = self._conn.execute(f"PRAGMA {name};").fetchone()
            return row[0] if row else None
        except Exception as exc:
            log.warning("Cannot read PRAGMA %s: %s", name, exc)
            return None

    def write(self, name: str, value: Any) -> bool:
        try:
            self._conn.execute(f"PRAGMA {name} = {value};")
            log.info("Set PRAGMA %s = %s", name, value)
            return True
        except Exception as exc:
            log.error("Cannot set PRAGMA %s = %s: %s", name, value, exc)
            return False

    def read_all(self) -> dict[str, Any]:
        """Read all defined PRAGMAs at once."""
        return {p["name"]: self.read(p["name"]) for p in PRAGMA_DEFINITIONS}

    def run_vacuum(self) -> None:
        self._conn.execute("VACUUM;")
        log.info("VACUUM executed.")

    def run_analyze(self) -> None:
        self._conn.execute("ANALYZE;")
        log.info("ANALYZE executed.")

    def run_integrity_check(self) -> list[str]:
        rows = self._conn.execute("PRAGMA integrity_check;").fetchall()
        return [r[0] for r in rows]

    def run_quick_check(self) -> list[str]:
        rows = self._conn.execute("PRAGMA quick_check;").fetchall()
        return [r[0] for r in rows]

    @staticmethod
    def definitions() -> list[dict]:
        return PRAGMA_DEFINITIONS
