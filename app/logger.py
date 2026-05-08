"""
app/logger.py — Logging configuration with file + console output and rotation.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from app.config import LOG_FILE, APP_NAME


def setup_logging(level: int = logging.DEBUG) -> logging.Logger:
    """Configure and return the root application logger."""
    logger = logging.getLogger(APP_NAME)
    logger.setLevel(level)

    if logger.handlers:
        return logger  # Already configured

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── File handler (rotates at 5 MB, keeps 3 backups) ──────────────────────
    try:
        fh = RotatingFileHandler(
            LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception as exc:
        print(f"[Logger] Could not create log file: {exc}", file=sys.stderr)

    # ── Console handler ───────────────────────────────────────────────────────
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the app namespace."""
    return logging.getLogger(f"{APP_NAME}.{name}")
