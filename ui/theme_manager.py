"""
ui/theme_manager.py — Dark / Light QSS Stylesheet Manager.
"""
from __future__ import annotations

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings

from app.config import (
    APP_NAME, APP_AUTHOR, SETTINGS_THEME, THEME_DARK, THEME_LIGHT,
    DARK_BG_PRIMARY, DARK_BG_SECONDARY, DARK_BG_PANEL, DARK_BG_HOVER,
    DARK_ACCENT, DARK_ACCENT2, DARK_SUCCESS, DARK_WARNING, DARK_ERROR,
    DARK_TEXT, DARK_TEXT_DIM, DARK_BORDER,
    LIGHT_BG_PRIMARY, LIGHT_BG_SECONDARY, LIGHT_BG_PANEL, LIGHT_BG_HOVER,
    LIGHT_ACCENT, LIGHT_ACCENT2, LIGHT_TEXT, LIGHT_TEXT_DIM, LIGHT_BORDER,
)


DARK_QSS = f"""
* {{ font-family:'Segoe UI','Inter',sans-serif; font-size:10pt; color:{DARK_TEXT}; outline:none; }}
QMainWindow,QDialog,QWidget {{ background-color:{DARK_BG_PRIMARY}; }}
QMenuBar {{ background-color:{DARK_BG_SECONDARY}; border-bottom:1px solid {DARK_BORDER}; padding:2px; }}
QMenuBar::item {{ padding:4px 10px; border-radius:4px; }}
QMenuBar::item:selected {{ background-color:{DARK_BG_HOVER}; }}
QMenu {{ background-color:{DARK_BG_PANEL}; border:1px solid {DARK_BORDER}; border-radius:6px; padding:4px; }}
QMenu::item {{ padding:6px 24px 6px 10px; border-radius:4px; }}
QMenu::item:selected {{ background-color:{DARK_BG_HOVER}; color:{DARK_ACCENT}; }}
QMenu::separator {{ height:1px; background:{DARK_BORDER}; margin:4px 0; }}
QToolBar {{ background-color:{DARK_BG_SECONDARY}; border-bottom:1px solid {DARK_BORDER}; spacing:4px; padding:3px 6px; }}
QToolBar QToolButton {{ background:transparent; border:none; border-radius:5px; padding:5px 8px; }}
QToolBar QToolButton:hover {{ background-color:{DARK_BG_HOVER}; }}
QToolBar QToolButton:pressed {{ background-color:{DARK_BORDER}; }}
QSplitter::handle {{ background-color:{DARK_BORDER}; }}
QTabWidget::pane {{ border:1px solid {DARK_BORDER}; background-color:{DARK_BG_PRIMARY}; }}
QTabBar::tab {{ background-color:{DARK_BG_SECONDARY}; color:{DARK_TEXT_DIM}; padding:6px 16px; border:1px solid {DARK_BORDER}; border-bottom:none; border-top-left-radius:6px; border-top-right-radius:6px; margin-right:2px; }}
QTabBar::tab:selected {{ background-color:{DARK_BG_PRIMARY}; color:{DARK_ACCENT}; border-bottom:2px solid {DARK_ACCENT}; }}
QTabBar::tab:hover:!selected {{ background-color:{DARK_BG_HOVER}; color:{DARK_TEXT}; }}
QTreeView,QListView {{ background-color:{DARK_BG_PANEL}; border:none; alternate-background-color:{DARK_BG_SECONDARY}; show-decoration-selected:1; }}
QTreeView::item,QListView::item {{ padding:3px 4px; border-radius:3px; }}
QTreeView::item:selected,QListView::item:selected {{ background-color:{DARK_ACCENT}; color:{DARK_BG_SECONDARY}; }}
QTreeView::item:hover:!selected,QListView::item:hover:!selected {{ background-color:{DARK_BG_HOVER}; }}
QTableView {{ background-color:{DARK_BG_PRIMARY}; gridline-color:{DARK_BORDER}; border:none; selection-background-color:{DARK_ACCENT2}; selection-color:{DARK_BG_SECONDARY}; alternate-background-color:{DARK_BG_PANEL}; }}
QTableView::item {{ padding:2px 6px; border:none; }}
QHeaderView::section {{ background-color:{DARK_BG_SECONDARY}; color:{DARK_TEXT}; border:none; border-right:1px solid {DARK_BORDER}; border-bottom:1px solid {DARK_BORDER}; padding:4px 8px; font-weight:600; }}
QHeaderView::section:hover {{ background-color:{DARK_BG_HOVER}; color:{DARK_ACCENT}; }}
QTextEdit,QPlainTextEdit {{ background-color:{DARK_BG_SECONDARY}; border:1px solid {DARK_BORDER}; border-radius:5px; padding:6px; selection-background-color:{DARK_ACCENT2}; font-family:'Consolas','Courier New',monospace; font-size:11pt; }}
QLineEdit {{ background-color:{DARK_BG_PANEL}; border:1px solid {DARK_BORDER}; border-radius:5px; padding:5px 10px; selection-background-color:{DARK_ACCENT2}; }}
QLineEdit:focus {{ border:1px solid {DARK_ACCENT}; }}
QLineEdit:disabled {{ background-color:{DARK_BG_SECONDARY}; color:{DARK_TEXT_DIM}; }}
QComboBox {{ background-color:{DARK_BG_PANEL}; border:1px solid {DARK_BORDER}; border-radius:5px; padding:5px 10px; min-width:80px; }}
QComboBox:focus {{ border:1px solid {DARK_ACCENT}; }}
QComboBox::drop-down {{ border:none; width:24px; }}
QComboBox QAbstractItemView {{ background-color:{DARK_BG_PANEL}; border:1px solid {DARK_BORDER}; selection-background-color:{DARK_ACCENT}; selection-color:{DARK_BG_SECONDARY}; }}
QSpinBox,QDoubleSpinBox {{ background-color:{DARK_BG_PANEL}; border:1px solid {DARK_BORDER}; border-radius:5px; padding:4px 8px; }}
QSpinBox:focus,QDoubleSpinBox:focus {{ border:1px solid {DARK_ACCENT}; }}
QPushButton {{ background-color:{DARK_BG_PANEL}; color:{DARK_TEXT}; border:1px solid {DARK_BORDER}; border-radius:6px; padding:6px 16px; font-weight:500; }}
QPushButton:hover {{ background-color:{DARK_BG_HOVER}; border:1px solid {DARK_ACCENT}; color:{DARK_ACCENT}; }}
QPushButton:pressed {{ background-color:{DARK_BORDER}; }}
QPushButton:disabled {{ background-color:{DARK_BG_SECONDARY}; color:{DARK_TEXT_DIM}; border-color:{DARK_BORDER}; }}
QPushButton[class="primary"] {{ background-color:{DARK_ACCENT}; color:{DARK_BG_SECONDARY}; border:none; font-weight:600; }}
QPushButton[class="primary"]:hover {{ background-color:#d4b3ff; color:{DARK_BG_SECONDARY}; }}
QPushButton[class="danger"] {{ background-color:transparent; color:{DARK_ERROR}; border:1px solid {DARK_ERROR}; }}
QPushButton[class="danger"]:hover {{ background-color:{DARK_ERROR}; color:{DARK_BG_SECONDARY}; }}
QPushButton[class="success"] {{ background-color:transparent; color:{DARK_SUCCESS}; border:1px solid {DARK_SUCCESS}; }}
QPushButton[class="success"]:hover {{ background-color:{DARK_SUCCESS}; color:{DARK_BG_SECONDARY}; }}
QStatusBar {{ background-color:{DARK_BG_SECONDARY}; border-top:1px solid {DARK_BORDER}; color:{DARK_TEXT_DIM}; padding:0 8px; }}
QStatusBar::item {{ border:none; }}
QScrollBar:vertical {{ background:{DARK_BG_SECONDARY}; width:10px; border-radius:5px; }}
QScrollBar::handle:vertical {{ background:{DARK_BORDER}; border-radius:5px; min-height:30px; }}
QScrollBar::handle:vertical:hover {{ background:{DARK_TEXT_DIM}; }}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{ height:0px; }}
QScrollBar:horizontal {{ background:{DARK_BG_SECONDARY}; height:10px; border-radius:5px; }}
QScrollBar::handle:horizontal {{ background:{DARK_BORDER}; border-radius:5px; min-width:30px; }}
QScrollBar::handle:horizontal:hover {{ background:{DARK_TEXT_DIM}; }}
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {{ width:0px; }}
QProgressBar {{ background-color:{DARK_BG_PANEL}; border:1px solid {DARK_BORDER}; border-radius:5px; text-align:center; height:18px; }}
QProgressBar::chunk {{ background-color:{DARK_ACCENT}; border-radius:4px; }}
QDockWidget::title {{ background-color:{DARK_BG_PANEL}; border-bottom:1px solid {DARK_BORDER}; padding:6px 10px; font-weight:600; }}
QGroupBox {{ border:1px solid {DARK_BORDER}; border-radius:6px; margin-top:14px; padding-top:6px; }}
QGroupBox::title {{ subcontrol-origin:margin; subcontrol-position:top left; padding:0 6px; color:{DARK_ACCENT}; font-weight:600; }}
QToolTip {{ background-color:{DARK_BG_PANEL}; color:{DARK_TEXT}; border:1px solid {DARK_BORDER}; border-radius:4px; padding:4px 8px; font-size:9pt; }}
QCheckBox {{ spacing:6px; }}
QCheckBox::indicator {{ width:16px; height:16px; border-radius:4px; border:2px solid {DARK_BORDER}; background-color:{DARK_BG_PANEL}; }}
QCheckBox::indicator:checked {{ background-color:{DARK_ACCENT}; border-color:{DARK_ACCENT}; }}
QRadioButton::indicator {{ width:16px; height:16px; border-radius:8px; border:2px solid {DARK_BORDER}; background-color:{DARK_BG_PANEL}; }}
QRadioButton::indicator:checked {{ background-color:{DARK_ACCENT}; border-color:{DARK_ACCENT}; }}
QSlider::groove:horizontal {{ background:{DARK_BORDER}; height:4px; border-radius:2px; }}
QSlider::handle:horizontal {{ background:{DARK_ACCENT}; width:14px; height:14px; border-radius:7px; margin:-5px 0; }}
QSlider::sub-page:horizontal {{ background:{DARK_ACCENT}; border-radius:2px; }}
"""

LIGHT_QSS = f"""
* {{ font-family:'Segoe UI','Inter',sans-serif; font-size:10pt; color:{LIGHT_TEXT}; }}
QMainWindow,QDialog,QWidget {{ background-color:{LIGHT_BG_PRIMARY}; }}
QMenuBar {{ background-color:{LIGHT_BG_SECONDARY}; border-bottom:1px solid {LIGHT_BORDER}; }}
QMenuBar::item:selected {{ background-color:{LIGHT_BG_HOVER}; }}
QMenu {{ background-color:{LIGHT_BG_SECONDARY}; border:1px solid {LIGHT_BORDER}; border-radius:6px; padding:4px; }}
QMenu::item {{ padding:6px 24px 6px 10px; border-radius:4px; }}
QMenu::item:selected {{ background-color:{LIGHT_BG_HOVER}; color:{LIGHT_ACCENT}; }}
QToolBar {{ background-color:{LIGHT_BG_SECONDARY}; border-bottom:1px solid {LIGHT_BORDER}; padding:3px 6px; spacing:4px; }}
QToolBar QToolButton:hover {{ background-color:{LIGHT_BG_HOVER}; border-radius:5px; }}
QTabBar::tab {{ background-color:{LIGHT_BG_PANEL}; border:1px solid {LIGHT_BORDER}; border-bottom:none; padding:6px 16px; border-top-left-radius:6px; border-top-right-radius:6px; margin-right:2px; }}
QTabBar::tab:selected {{ background-color:{LIGHT_BG_SECONDARY}; color:{LIGHT_ACCENT}; border-bottom:2px solid {LIGHT_ACCENT}; }}
QTreeView,QListView {{ background-color:{LIGHT_BG_PANEL}; border:none; alternate-background-color:{LIGHT_BG_SECONDARY}; }}
QTreeView::item:selected,QListView::item:selected {{ background-color:{LIGHT_ACCENT}; color:white; }}
QTableView {{ background-color:{LIGHT_BG_SECONDARY}; gridline-color:{LIGHT_BORDER}; selection-background-color:{LIGHT_ACCENT2}; selection-color:white; alternate-background-color:{LIGHT_BG_PANEL}; }}
QHeaderView::section {{ background-color:{LIGHT_BG_PANEL}; border-right:1px solid {LIGHT_BORDER}; border-bottom:1px solid {LIGHT_BORDER}; padding:4px 8px; font-weight:600; }}
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox {{ background-color:{LIGHT_BG_SECONDARY}; border:1px solid {LIGHT_BORDER}; border-radius:5px; padding:5px 10px; }}
QLineEdit:focus,QComboBox:focus {{ border:1px solid {LIGHT_ACCENT}; }}
QPushButton {{ background-color:{LIGHT_BG_PANEL}; border:1px solid {LIGHT_BORDER}; border-radius:6px; padding:6px 16px; }}
QPushButton:hover {{ background-color:{LIGHT_BG_HOVER}; border:1px solid {LIGHT_ACCENT}; }}
QPushButton[class="primary"] {{ background-color:{LIGHT_ACCENT}; color:white; border:none; font-weight:600; }}
QPushButton[class="danger"] {{ color:#d20f39; border:1px solid #d20f39; background:transparent; }}
QPushButton[class="danger"]:hover {{ background:#d20f39; color:white; }}
QTextEdit,QPlainTextEdit {{ background-color:{LIGHT_BG_SECONDARY}; border:1px solid {LIGHT_BORDER}; border-radius:5px; font-family:'Consolas','Courier New',monospace; font-size:11pt; padding:6px; }}
QStatusBar {{ background-color:{LIGHT_BG_SECONDARY}; border-top:1px solid {LIGHT_BORDER}; color:{LIGHT_TEXT_DIM}; }}
QScrollBar:vertical {{ background:{LIGHT_BG_PANEL}; width:10px; }}
QScrollBar::handle:vertical {{ background:{LIGHT_BORDER}; border-radius:5px; min-height:30px; }}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{ height:0px; }}
QScrollBar:horizontal {{ background:{LIGHT_BG_PANEL}; height:10px; }}
QScrollBar::handle:horizontal {{ background:{LIGHT_BORDER}; border-radius:5px; min-width:30px; }}
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {{ width:0px; }}
QProgressBar {{ background-color:{LIGHT_BG_PANEL}; border:1px solid {LIGHT_BORDER}; border-radius:5px; text-align:center; }}
QProgressBar::chunk {{ background-color:{LIGHT_ACCENT}; border-radius:4px; }}
QToolTip {{ background-color:{LIGHT_BG_SECONDARY}; color:{LIGHT_TEXT}; border:1px solid {LIGHT_BORDER}; border-radius:4px; padding:4px 8px; }}
QGroupBox {{ border:1px solid {LIGHT_BORDER}; border-radius:6px; margin-top:14px; }}
QGroupBox::title {{ color:{LIGHT_ACCENT}; font-weight:600; padding:0 6px; subcontrol-origin:margin; }}
QCheckBox::indicator {{ width:16px; height:16px; border-radius:4px; border:2px solid {LIGHT_BORDER}; background:{LIGHT_BG_SECONDARY}; }}
QCheckBox::indicator:checked {{ background:{LIGHT_ACCENT}; border-color:{LIGHT_ACCENT}; }}
"""


class ThemeManager:
    """Manages dark/light theme switching for the application."""

    def __init__(self):
        self._settings = QSettings(APP_AUTHOR, APP_NAME)
        self._current = self._settings.value(SETTINGS_THEME, THEME_DARK)

    @property
    def current_theme(self) -> str:
        return self._current

    def apply(self, theme: str) -> None:
        app = QApplication.instance()
        if not app:
            return
        self._current = theme
        self._settings.setValue(SETTINGS_THEME, theme)
        app.setStyleSheet(DARK_QSS if theme == THEME_DARK else LIGHT_QSS)

    def toggle(self) -> str:
        new = THEME_LIGHT if self._current == THEME_DARK else THEME_DARK
        self.apply(new)
        return new

    def apply_saved(self) -> None:
        self.apply(self._current)


# Module-level singleton
theme_manager = ThemeManager()
