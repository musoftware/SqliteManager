"""
main.py — SQLite Manager Entry Point.
"""
from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.config import APP_NAME, DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE
from app.logger import setup_logging


def main() -> int:
    # ── Logging ───────────────────────────────────────────────────────────────
    setup_logging()

    # ── Qt Application ────────────────────────────────────────────────────────
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("SQLiteManager")
    app.setApplicationVersion("1.0.0")

    # High-DPI support
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Default font
    font = QFont(DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE)
    app.setFont(font)

    # ── Main Window ───────────────────────────────────────────────────────────
    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
