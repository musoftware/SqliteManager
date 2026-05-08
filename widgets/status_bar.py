"""
widgets/status_bar.py — Custom Application Status Bar.

Shows: DB name, row count, query timer, page info, connection status.
Supports toast-style temporary messages.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QStatusBar, QLabel, QWidget, QHBoxLayout, QProgressBar

from app.config import DARK_ACCENT, DARK_SUCCESS, DARK_ERROR, DARK_WARNING, DARK_TEXT_DIM


class StatusBar(QStatusBar):
    """Enhanced status bar with permanent labels and toast notifications."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizeGripEnabled(True)
        self._setup_widgets()
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._clear_toast)

    def _setup_widgets(self) -> None:
        # Toast/main message (left)
        self._lbl_message = QLabel("")
        self._lbl_message.setMinimumWidth(300)
        self.addWidget(self._lbl_message, 1)

        # Progress bar (hidden by default)
        self._progress = QProgressBar()
        self._progress.setFixedWidth(160)
        self._progress.setFixedHeight(14)
        self._progress.setVisible(False)
        self._progress.setTextVisible(True)
        self.addWidget(self._progress)

        # Separator
        sep1 = QLabel("  |  ")
        sep1.setStyleSheet(f"color:{DARK_TEXT_DIM};")
        self.addPermanentWidget(sep1)

        # Row count
        self._lbl_rows = QLabel("0 rows")
        self._lbl_rows.setStyleSheet(f"color:{DARK_TEXT_DIM}; font-size:9pt;")
        self.addPermanentWidget(self._lbl_rows)

        sep2 = QLabel("  |  ")
        sep2.setStyleSheet(f"color:{DARK_TEXT_DIM};")
        self.addPermanentWidget(sep2)

        # Page info
        self._lbl_page = QLabel("Page 1 / 1")
        self._lbl_page.setStyleSheet(f"color:{DARK_TEXT_DIM}; font-size:9pt;")
        self.addPermanentWidget(self._lbl_page)

        sep3 = QLabel("  |  ")
        sep3.setStyleSheet(f"color:{DARK_TEXT_DIM};")
        self.addPermanentWidget(sep3)

        # Query time
        self._lbl_time = QLabel("")
        self._lbl_time.setStyleSheet(f"color:{DARK_TEXT_DIM}; font-size:9pt;")
        self.addPermanentWidget(self._lbl_time)

        sep4 = QLabel("  |  ")
        sep4.setStyleSheet(f"color:{DARK_TEXT_DIM};")
        self.addPermanentWidget(sep4)

        # Connection indicator
        self._lbl_conn = QLabel("● Not connected")
        self._lbl_conn.setStyleSheet(f"color:{DARK_ERROR}; font-size:9pt; padding-right:8px;")
        self.addPermanentWidget(self._lbl_conn)

    # ── Public API ────────────────────────────────────────────────────────────

    def show_message(self, msg: str, duration_ms: int = 4000) -> None:
        """Show a temporary info message (toast)."""
        self._lbl_message.setText(msg)
        self._lbl_message.setStyleSheet(f"color:{DARK_TEXT_DIM};")
        if duration_ms > 0:
            self._toast_timer.start(duration_ms)

    def show_success(self, msg: str, duration_ms: int = 4000) -> None:
        self._lbl_message.setText(f"✔  {msg}")
        self._lbl_message.setStyleSheet(f"color:{DARK_SUCCESS};")
        if duration_ms > 0:
            self._toast_timer.start(duration_ms)

    def show_error(self, msg: str, duration_ms: int = 6000) -> None:
        self._lbl_message.setText(f"✘  {msg}")
        self._lbl_message.setStyleSheet(f"color:{DARK_ERROR};")
        if duration_ms > 0:
            self._toast_timer.start(duration_ms)

    def show_warning(self, msg: str, duration_ms: int = 5000) -> None:
        self._lbl_message.setText(f"⚠  {msg}")
        self._lbl_message.setStyleSheet(f"color:{DARK_WARNING};")
        if duration_ms > 0:
            self._toast_timer.start(duration_ms)

    def set_row_count(self, count: int) -> None:
        self._lbl_rows.setText(f"{count:,} rows")

    def set_page_info(self, current: int, total: int) -> None:
        self._lbl_page.setText(f"Page {current + 1} / {total}")

    def set_query_time(self, elapsed_ms: float) -> None:
        if elapsed_ms < 1000:
            self._lbl_time.setText(f"⏱ {elapsed_ms:.1f} ms")
        else:
            self._lbl_time.setText(f"⏱ {elapsed_ms/1000:.2f} s")

    def clear_query_time(self) -> None:
        self._lbl_time.setText("")

    def set_connected(self, db_name: str) -> None:
        self._lbl_conn.setText(f"● {db_name}")
        self._lbl_conn.setStyleSheet(f"color:{DARK_SUCCESS}; font-size:9pt; padding-right:8px;")

    def set_disconnected(self) -> None:
        self._lbl_conn.setText("● Not connected")
        self._lbl_conn.setStyleSheet(f"color:{DARK_ERROR}; font-size:9pt; padding-right:8px;")

    def show_progress(self, value: int, maximum: int = 100, text: str = "") -> None:
        self._progress.setVisible(True)
        self._progress.setMaximum(maximum)
        self._progress.setValue(value)
        if text:
            self._progress.setFormat(text)
        else:
            self._progress.setFormat(f"{value}/{maximum}")

    def hide_progress(self) -> None:
        self._progress.setVisible(False)

    def _clear_toast(self) -> None:
        self._lbl_message.setText("")
