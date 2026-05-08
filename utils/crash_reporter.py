"""
utils/crash_reporter.py — Global Exception Handler & Crash Reporter.

Installs a sys.excepthook that:
1. Logs the full traceback
2. Shows a friendly crash dialog with copy-to-clipboard
3. Optionally saves a crash dump file
"""
from __future__ import annotations

import sys
import traceback
import platform
import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from app.logger import get_logger
from app.version import VERSION, APP_NAME

log = get_logger("crash")


def _format_crash_report(exc_type, exc_value, exc_tb) -> str:
    """Build a structured crash report string."""
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    tb_str = "".join(tb_lines)

    report = (
        f"{'=' * 60}\n"
        f"CRASH REPORT — {APP_NAME} v{VERSION}\n"
        f"{'=' * 60}\n"
        f"Time      : {datetime.datetime.now().isoformat()}\n"
        f"Python    : {sys.version}\n"
        f"Platform  : {platform.platform()}\n"
        f"{'=' * 60}\n"
        f"{tb_str}"
        f"{'=' * 60}\n"
    )
    return report


def _save_crash_dump(report: str) -> str:
    """Save crash report to AppData and return the path."""
    try:
        from app.config import APP_DATA_DIR
        crash_dir = APP_DATA_DIR / "crashes"
        crash_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = crash_dir / f"crash_{ts}.txt"
        path.write_text(report, encoding="utf-8")
        return str(path)
    except Exception:
        return ""


def _show_crash_dialog(report: str, crash_path: str) -> None:
    """Show a Qt crash dialog (only if QApplication is alive)."""
    try:
        from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QPushButton, QHBoxLayout
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QClipboard

        if not QApplication.instance():
            return

        dlg = QDialog()
        dlg.setWindowTitle(f"{APP_NAME} — Unexpected Error")
        dlg.setMinimumSize(700, 450)
        dlg.setWindowFlag(Qt.WindowStaysOnTopHint)

        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(
            "<b style='color:#f38ba8; font-size:13pt;'>An unexpected error occurred.</b><br>"
            "<span style='color:#7f849c;'>The application encountered an unhandled exception.<br>"
            "Please copy the report below and report this issue.</span>"
        ))

        txt = QPlainTextEdit(report)
        txt.setReadOnly(True)
        txt.setFont(__import__("PySide6.QtGui", fromlist=["QFont"]).QFont("Consolas", 9))
        layout.addWidget(txt)

        if crash_path:
            layout.addWidget(QLabel(f"<small>Crash dump saved to: <code>{crash_path}</code></small>"))

        btns = QHBoxLayout()
        btn_copy = QPushButton("Copy Report")
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(report))
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dlg.accept)
        btn_close.setProperty("class", "primary")
        btns.addWidget(btn_copy)
        btns.addStretch()
        btns.addWidget(btn_close)
        layout.addLayout(btns)

        dlg.exec()
    except Exception:
        pass  # If Qt is dead, we can't show a dialog


def install_crash_handler() -> None:
    """
    Install a global exception handler.
    Call once at startup in main.py.
    """

    def handler(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        report = _format_crash_report(exc_type, exc_value, exc_tb)
        log.critical("UNHANDLED EXCEPTION:\n%s", report)

        crash_path = _save_crash_dump(report)
        _show_crash_dialog(report, crash_path)

    sys.excepthook = handler
    log.info("Crash handler installed.")
