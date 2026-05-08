"""
widgets/first_run_wizard.py — First-Run Setup Wizard.

Shown when the app is launched for the first time.
Guides the user through: theme selection, default folder config,
file associations, and opening the demo database.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QWidget, QRadioButton, QButtonGroup,
    QCheckBox, QLineEdit, QFileDialog, QGroupBox,
)

from app.config import APP_AUTHOR, APP_NAME, EXPORTS_DIR, BACKUPS_DIR
from app.version import VERSION


class FirstRunWizard(QDialog):
    """
    3-page wizard shown on first launch.
    Page 1: Welcome
    Page 2: Theme + preferences
    Page 3: Done — open demo DB option
    """

    SETTING_FIRST_RUN = "app/first_run_complete"
    SETTING_THEME     = "ui/theme"
    SETTING_EXPORTS   = "paths/exports"
    SETTING_BACKUPS   = "paths/backups"
    SETTING_ASSOC     = "app/file_associations"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = QSettings(APP_AUTHOR, APP_NAME)
        self.open_demo = False

        self.setWindowTitle(f"Welcome to {APP_NAME}")
        self.setMinimumSize(580, 420)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._setup_ui()

    @staticmethod
    def should_show() -> bool:
        s = QSettings(APP_AUTHOR, APP_NAME)
        return not s.value("app/first_run_complete", False, type=bool)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header bar
        header = QWidget()
        header.setFixedHeight(70)
        header.setStyleSheet("background:#1e1e2e; border-bottom:1px solid #313244;")
        h_layout = QHBoxLayout(header)
        title_lbl = QLabel(f"<b style='color:#cba6f7; font-size:16pt;'>{APP_NAME}</b>  "
                           f"<span style='color:#7f849c; font-size:10pt;'>v{VERSION}</span>")
        h_layout.addWidget(title_lbl)
        h_layout.addStretch()
        layout.addWidget(header)

        # Step indicator
        self._step_lbl = QLabel("Step 1 of 3")
        self._step_lbl.setStyleSheet("padding:8px 16px; color:#7f849c; font-size:9pt;")
        layout.addWidget(self._step_lbl)

        # Pages
        self._stack = QStackedWidget()
        self._stack.addWidget(self._page_welcome())
        self._stack.addWidget(self._page_prefs())
        self._stack.addWidget(self._page_done())
        layout.addWidget(self._stack, 1)

        # Navigation
        nav = QHBoxLayout()
        nav.setContentsMargins(16, 8, 16, 12)
        self._btn_back = QPushButton("◀ Back")
        self._btn_back.setEnabled(False)
        self._btn_back.clicked.connect(self._go_back)
        self._btn_next = QPushButton("Next ▶")
        self._btn_next.setProperty("class", "primary")
        self._btn_next.clicked.connect(self._go_next)
        self._btn_skip = QPushButton("Skip Setup")
        self._btn_skip.clicked.connect(self._on_skip)
        nav.addWidget(self._btn_skip)
        nav.addStretch()
        nav.addWidget(self._btn_back)
        nav.addWidget(self._btn_next)
        layout.addLayout(nav)

    # ── Pages ─────────────────────────────────────────────────────────────────

    def _page_welcome(self) -> QWidget:
        p = QWidget()
        layout = QVBoxLayout(p)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(12)

        emoji_lbl = QLabel("🗄")
        emoji_lbl.setFont(QFont("Segoe UI Emoji", 48))
        emoji_lbl.setAlignment(Qt.AlignCenter)

        h = QLabel(f"<h2 style='color:#cdd6f4;'>Welcome to {APP_NAME}!</h2>")
        h.setAlignment(Qt.AlignCenter)

        sub = QLabel(
            "<p style='color:#7f849c; text-align:center;'>"
            "A modern, production-grade SQLite database manager.<br>"
            "This short wizard will help you configure the application."
            "</p>"
        )
        sub.setWordWrap(True)
        sub.setAlignment(Qt.AlignCenter)

        features = QLabel(
            "<ul style='color:#cdd6f4;'>"
            "<li>Open, create, and manage SQLite databases</li>"
            "<li>Visual ERD diagram viewer</li>"
            "<li>Import/Export: CSV, Excel, JSON, PDF</li>"
            "<li>SQL editor with syntax highlighting</li>"
            "<li>Auto-backup scheduler</li>"
            "</ul>"
        )

        layout.addStretch()
        layout.addWidget(emoji_lbl)
        layout.addWidget(h)
        layout.addWidget(sub)
        layout.addWidget(features)
        layout.addStretch()
        return p

    def _page_prefs(self) -> QWidget:
        p = QWidget()
        layout = QVBoxLayout(p)
        layout.setContentsMargins(30, 20, 30, 20)

        # Theme
        grp_theme = QGroupBox("Appearance")
        theme_layout = QHBoxLayout(grp_theme)
        self._rb_dark = QRadioButton("🌙 Dark Theme  (recommended)")
        self._rb_light = QRadioButton("☀ Light Theme")
        self._rb_dark.setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self._rb_dark)
        bg.addButton(self._rb_light)
        theme_layout.addWidget(self._rb_dark)
        theme_layout.addWidget(self._rb_light)
        layout.addWidget(grp_theme)

        # Export folder
        grp_paths = QGroupBox("Default Folders")
        paths_layout = QVBoxLayout(grp_paths)
        exp_row = QHBoxLayout()
        exp_row.addWidget(QLabel("Exports:"))
        self._txt_exports = QLineEdit(str(EXPORTS_DIR))
        btn_exp = QPushButton("Browse")
        btn_exp.clicked.connect(lambda: self._browse(self._txt_exports))
        exp_row.addWidget(self._txt_exports, 1)
        exp_row.addWidget(btn_exp)
        paths_layout.addLayout(exp_row)

        bk_row = QHBoxLayout()
        bk_row.addWidget(QLabel("Backups:"))
        self._txt_backups = QLineEdit(str(BACKUPS_DIR))
        btn_bk = QPushButton("Browse")
        btn_bk.clicked.connect(lambda: self._browse(self._txt_backups))
        bk_row.addWidget(self._txt_backups, 1)
        bk_row.addWidget(btn_bk)
        paths_layout.addLayout(bk_row)
        layout.addWidget(grp_paths)

        # Startup
        grp_start = QGroupBox("Startup")
        start_layout = QVBoxLayout(grp_start)
        self._chk_reopen = QCheckBox("Reopen last database on startup")
        self._chk_reopen.setChecked(True)
        self._chk_updates = QCheckBox("Check for updates automatically")
        self._chk_updates.setChecked(True)
        start_layout.addWidget(self._chk_reopen)
        start_layout.addWidget(self._chk_updates)
        layout.addWidget(grp_start)

        layout.addStretch()
        return p

    def _page_done(self) -> QWidget:
        p = QWidget()
        layout = QVBoxLayout(p)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(14)

        tick = QLabel("✔")
        tick.setFont(QFont("Segoe UI Emoji", 52))
        tick.setAlignment(Qt.AlignCenter)
        tick.setStyleSheet("color:#a6e3a1;")

        h = QLabel("<h2 style='color:#cdd6f4;'>All Set!</h2>")
        h.setAlignment(Qt.AlignCenter)

        sub = QLabel("<p style='color:#7f849c;'>Your preferences have been saved.</p>")
        sub.setAlignment(Qt.AlignCenter)

        self._chk_demo = QCheckBox("Open the demo e-commerce database to explore the features")
        self._chk_demo.setChecked(True)
        self._chk_demo.setStyleSheet("color:#cdd6f4;")

        layout.addStretch()
        layout.addWidget(tick)
        layout.addWidget(h)
        layout.addWidget(sub)
        layout.addWidget(self._chk_demo, alignment=Qt.AlignCenter)
        layout.addStretch()
        return p

    # ── Navigation ────────────────────────────────────────────────────────────

    def _go_next(self) -> None:
        idx = self._stack.currentIndex()
        if idx < self._stack.count() - 1:
            self._stack.setCurrentIndex(idx + 1)
            self._step_lbl.setText(f"Step {idx + 2} of 3")
            self._btn_back.setEnabled(True)
            if idx + 1 == self._stack.count() - 1:
                self._btn_next.setText("Finish")
        else:
            self._save_prefs()
            self.accept()

    def _go_back(self) -> None:
        idx = self._stack.currentIndex()
        if idx > 0:
            self._stack.setCurrentIndex(idx - 1)
            self._step_lbl.setText(f"Step {idx} of 3")
            self._btn_next.setText("Next ▶")
            if idx == 1:
                self._btn_back.setEnabled(False)

    def _on_skip(self) -> None:
        self._save_prefs()
        self.reject()

    # ── Save prefs ────────────────────────────────────────────────────────────

    def _save_prefs(self) -> None:
        from ui.theme_manager import theme_manager, THEME_DARK, THEME_LIGHT
        theme = THEME_DARK if self._rb_dark.isChecked() else THEME_LIGHT
        theme_manager.apply(theme)

        self._settings.setValue("app/first_run_complete", True)
        self._settings.setValue("app/check_updates", self._chk_updates.isChecked())
        self._settings.setValue("app/reopen_last", self._chk_reopen.isChecked())

        try:
            exp_dir = Path(self._txt_exports.text())
            exp_dir.mkdir(parents=True, exist_ok=True)
            bk_dir = Path(self._txt_backups.text())
            bk_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        if hasattr(self, "_chk_demo"):
            self.open_demo = self._chk_demo.isChecked()

    def _browse(self, txt: QLineEdit) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select Folder", txt.text())
        if d:
            txt.setText(d)
