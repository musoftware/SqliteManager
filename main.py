"""
main.py — SQLite Manager Entry Point.

Production-grade bootstrap with:
  - Splash screen with progress
  - Global crash handler
  - First-run wizard
  - Auto-update check (background)
  - Proper AppData config folder setup
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# ── Bootstrap: ensure config dirs exist before anything else ──────────────────
def _bootstrap_dirs() -> None:
    appdata = os.getenv("APPDATA", str(Path.home() / ".config"))
    base = Path(appdata) / "SQLiteManager"
    for sub in ("", "backups", "exports", "crashes", "logs"):
        (base / sub).mkdir(parents=True, exist_ok=True)

_bootstrap_dirs()

# ── PyInstaller resource path helper ─────────────────────────────────────────
def resource_path(relative: str) -> str:
    """Get absolute path to a resource — works in dev and PyInstaller bundle."""
    base = getattr(sys, "_MEIPASS", Path(__file__).parent)
    return str(Path(base) / relative)


def main() -> int:
    # ── Crash handler (install before Qt so all exceptions are caught) ────────
    from utils.crash_reporter import install_crash_handler
    install_crash_handler()

    # ── Qt Application ────────────────────────────────────────────────────────
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QPixmap, QIcon

    from app.config import DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE
    from app.version import APP_NAME, VERSION

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("SQLiteManager")
    app.setFont(QFont(DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE))

    # Set application icon
    icon_path = resource_path("assets/icons/app.ico")
    if Path(icon_path).exists():
        app.setWindowIcon(QIcon(icon_path))

    # ── Logging ───────────────────────────────────────────────────────────────
    from app.logger import setup_logging
    setup_logging()

    # ── Splash Screen ─────────────────────────────────────────────────────────
    from widgets.splash_screen import SplashScreen

    splash_path = resource_path("assets/splash.png")
    splash_px = QPixmap(splash_path) if Path(splash_path).exists() else QPixmap()
    splash = SplashScreen(splash_px if not splash_px.isNull() else None)
    splash.show()
    app.processEvents()

    # ── Progressive loading with splash feedback ──────────────────────────────
    splash.set_progress(10, "Loading theme")
    from ui.theme_manager import theme_manager
    theme_manager.apply_saved()

    splash.set_progress(25, "Loading database engine")
    from core.database.connection import connection_manager  # noqa — trigger import

    splash.set_progress(40, "Loading UI components")
    from ui.main_window import MainWindow

    splash.set_progress(60, "Loading services")
    from services.backup_service import BackupService  # noqa

    splash.set_progress(75, "Initializing widgets")
    from widgets.schema_explorer import SchemaExplorer  # noqa
    from widgets.data_viewer import DataViewer          # noqa
    from widgets.query_editor import QueryEditor        # noqa

    splash.set_progress(90, "Starting application")
    window = MainWindow()

    # ── Apply theme to window before showing ──────────────────────────────────
    theme_manager.apply_saved()

    splash.set_progress(100, "Ready")
    splash.finish_and_close(window)
    window.show()

    # ── First-Run Wizard ──────────────────────────────────────────────────────
    from widgets.first_run_wizard import FirstRunWizard
    if FirstRunWizard.should_show():
        wizard = FirstRunWizard(window)
        result = wizard.exec()
        if wizard.open_demo:
            window._on_open_demo()

    # ── Background update check ───────────────────────────────────────────────
    from PySide6.QtCore import QSettings
    from app.config import APP_AUTHOR
    settings = QSettings(APP_AUTHOR, APP_NAME)
    if settings.value("app/check_updates", True, type=bool):
        _start_update_check(window)

    return app.exec()


def _start_update_check(window) -> None:
    """Start a silent background update check after 5 seconds."""
    from PySide6.QtCore import QTimer

    def _check():
        try:
            from services.updater_service import UpdaterService
            svc = UpdaterService(window)
            svc.update_available.connect(lambda r: _on_update_found(window, r))
            svc.check(silent=True)
        except Exception:
            pass

    QTimer.singleShot(5000, _check)


def _on_update_found(window, release) -> None:
    """Show a non-intrusive update notification in the status bar."""
    try:
        window._status_bar.show_message(
            f"Update available: v{release.version}  — Help → Check for Updates"
        )
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
