"""
app/config.py — Application-wide configuration and constants.
"""
from __future__ import annotations

import os
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
APP_NAME = "SQLite Manager"
APP_VERSION = "1.0.0"
APP_AUTHOR = "SQLite Manager Team"

# User data directory (roaming appdata on Windows, ~/.local on Linux/macOS)
APP_DATA_DIR = Path(os.getenv("APPDATA", Path.home() / ".config")) / "SQLiteManager"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = APP_DATA_DIR / "sqlite_manager.log"
QUERY_HISTORY_FILE = APP_DATA_DIR / "query_history.json"
SAVED_QUERIES_FILE = APP_DATA_DIR / "saved_queries.json"
SNIPPETS_FILE = APP_DATA_DIR / "snippets.json"
CONNECTIONS_FILE = APP_DATA_DIR / "connections.enc"
BACKUPS_DIR = APP_DATA_DIR / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR = APP_DATA_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Defaults ─────────────────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE = 500          # rows per page in data viewer
MAX_QUERY_HISTORY = 200          # max query history entries
DEFAULT_QUERY_TIMEOUT = 30       # seconds
MAX_RECENT_DBS = 15              # max recent database files
DEFAULT_BACKUP_INTERVAL_MIN = 30 # minutes between auto-backups
DEFAULT_BATCH_SIZE = 1000        # rows per batch during import

# ── Theme ─────────────────────────────────────────────────────────────────────
THEME_DARK = "dark"
THEME_LIGHT = "light"
DEFAULT_THEME = THEME_DARK

# ── Font ──────────────────────────────────────────────────────────────────────
DEFAULT_FONT_FAMILY = "Segoe UI"
DEFAULT_FONT_SIZE = 10
EDITOR_FONT_FAMILY = "Consolas"
EDITOR_FONT_SIZE = 11

# ── Colors (dark theme palette) ───────────────────────────────────────────────
DARK_BG_PRIMARY   = "#1e1e2e"
DARK_BG_SECONDARY = "#181825"
DARK_BG_PANEL     = "#242438"
DARK_BG_HOVER     = "#313145"
DARK_ACCENT       = "#cba6f7"  # purple
DARK_ACCENT2      = "#89b4fa"  # blue
DARK_SUCCESS      = "#a6e3a1"  # green
DARK_WARNING      = "#f9e2af"  # yellow
DARK_ERROR        = "#f38ba8"  # red
DARK_TEXT         = "#cdd6f4"
DARK_TEXT_DIM     = "#7f849c"
DARK_BORDER       = "#313244"

LIGHT_BG_PRIMARY   = "#eff1f5"
LIGHT_BG_SECONDARY = "#ffffff"
LIGHT_BG_PANEL     = "#e6e9ef"
LIGHT_BG_HOVER     = "#dce0e8"
LIGHT_ACCENT       = "#7287fd"
LIGHT_ACCENT2      = "#209fb5"
LIGHT_SUCCESS      = "#40a02b"
LIGHT_WARNING      = "#df8e1d"
LIGHT_ERROR        = "#d20f39"
LIGHT_TEXT         = "#4c4f69"
LIGHT_TEXT_DIM     = "#8c8fa1"
LIGHT_BORDER       = "#ccd0da"

# ── Settings keys (QSettings) ─────────────────────────────────────────────────
SETTINGS_THEME         = "ui/theme"
SETTINGS_FONT_SIZE     = "ui/font_size"
SETTINGS_PAGE_SIZE     = "data/page_size"
SETTINGS_RECENT_DBS    = "db/recent"
SETTINGS_LAST_DB       = "db/last"
SETTINGS_AUTOSAVE      = "data/autosave"
SETTINGS_AUTOBACKUP    = "backup/auto_enabled"
SETTINGS_BACKUP_INTERVAL = "backup/interval_min"
SETTINGS_QUERY_TIMEOUT = "query/timeout"
SETTINGS_WINDOW_STATE  = "window/state"
SETTINGS_WINDOW_GEOM   = "window/geometry"
