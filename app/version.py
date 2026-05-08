"""
app/version.py — Central version management.

Single source of truth for version strings, used by build system,
auto-updater, and about dialogs.
"""
from __future__ import annotations

# ── Version ───────────────────────────────────────────────────────────────────
VERSION_MAJOR = 1
VERSION_MINOR = 0
VERSION_PATCH = 0
VERSION_BUILD = 0          # auto-incremented by build system

VERSION = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"
VERSION_FULL = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}.{VERSION_BUILD}"
VERSION_TUPLE = (VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH, VERSION_BUILD)

# ── Application metadata ──────────────────────────────────────────────────────
APP_NAME        = "SQLite Manager"
APP_ID          = "com.sqlitemanager.app"         # unique app identifier
APP_AUTHOR      = "SQLite Manager Team"
APP_COMPANY     = "Musoftware"
APP_DESCRIPTION = "Professional SQLite Database Management Tool"
APP_COPYRIGHT   = f"Copyright (c) 2025 {APP_COMPANY}"
APP_URL         = "https://github.com/musoftware/SqliteManager"
APP_UPDATE_URL  = f"{APP_URL}/releases/latest"
APP_RELEASES_API = "https://api.github.com/repos/musoftware/SqliteManager/releases/latest"

# ── File association ──────────────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = [".db", ".sqlite", ".sqlite3", ".db3"]

def version_tuple_to_str(t: tuple) -> str:
    return ".".join(str(x) for x in t)

def parse_version(s: str) -> tuple:
    parts = s.lstrip("v").split(".")
    try:
        return tuple(int(p) for p in parts[:4])
    except ValueError:
        return (0, 0, 0, 0)

def is_newer(remote: str, current: str = VERSION) -> bool:
    """Return True if remote version is newer than current."""
    return parse_version(remote) > parse_version(current)
