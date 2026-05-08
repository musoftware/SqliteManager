"""
widgets/data_viewer.py — Spreadsheet-like Table Data Viewer/Editor.

Features: pagination, inline editing, add/delete rows, copy/paste,
column sort/filter/resize, undo/redo, auto-save toggle.
"""
from __future__ import annotations

import csv
import io
from typing import Optional

from PySide6.QtCore import Qt, Signal, QModelIndex, QPoint
from PySide6.QtGui import QAction, QKeySequence, QShortcut, QClipboard
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QPushButton,
    QLabel, QLineEdit, QSpinBox, QComboBox, QToolBar, QMenu,
    QMessageBox, QApplication, QHeaderView, QFrame, QSizePolicy,
    QAbstractItemView,
)

from app.config import DEFAULT_PAGE_SIZE, DARK_ACCENT, DARK_ERROR, DARK_SUCCESS, DARK_TEXT_DIM
from app.logger import get_logger
from core.database.connection import DatabaseConnection
from core.models.table_model import TableDataModel

log = get_logger("data_viewer")


class FilterHeaderWidget(QWidget):
    """A row of QLineEdit filters shown below the table header."""

    filter_changed = Signal(str, str)   # column_name, filter_text

    def __init__(self, col_names: list[str], parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        self._edits: list[QLineEdit] = []
        for name in col_names:
            edit = QLineEdit()
            edit.setPlaceholderText(f"filter…")
            edit.setFixedHeight(22)
            edit.setStyleSheet("font-size:8pt; border-radius:0px;")
            col = name
            edit.textChanged.connect(lambda text, c=col: self.filter_changed.emit(c, text))
            layout.addWidget(edit)
            self._edits.append(edit)

    def clear_all(self) -> None:
        for e in self._edits:
            e.blockSignals(True)
            e.clear()
            e.blockSignals(False)


class DataViewer(QWidget):
    """
    Full spreadsheet-like data viewer for one SQLite table.

    Signals
    -------
    status_message(str)  — informational message for the status bar
    row_count_changed(int)
    dirty_changed(bool)
    """

    status_message = Signal(str)
    row_count_changed = Signal(int)
    dirty_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model: Optional[TableDataModel] = None
        self._conn: Optional[DatabaseConnection] = None
        self._table_name: str = ""
        self._auto_save: bool = False
        self._setup_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        self._toolbar = QToolBar()
        self._toolbar.setMovable(False)
        self._toolbar.setFloatable(False)

        self._btn_add_row = self._toolbar.addAction("➕ Add Row")
        self._btn_add_row.triggered.connect(self._on_add_row)
        self._btn_delete_row = self._toolbar.addAction("➖ Delete Row")
        self._btn_delete_row.triggered.connect(self._on_delete_rows)
        self._toolbar.addSeparator()
        self._btn_commit = self._toolbar.addAction("💾 Commit")
        self._btn_commit.triggered.connect(self._on_commit)
        self._btn_revert = self._toolbar.addAction("↩ Revert")
        self._btn_revert.triggered.connect(self._on_revert)
        self._toolbar.addSeparator()

        # Undo/Redo
        self._btn_undo = self._toolbar.addAction("⬅ Undo")
        self._btn_undo.triggered.connect(self._on_undo)
        self._btn_redo = self._toolbar.addAction("➡ Redo")
        self._btn_redo.triggered.connect(self._on_redo)
        self._toolbar.addSeparator()

        # Auto-save toggle
        self._btn_autosave = self._toolbar.addAction("🔄 Auto-Save: OFF")
        self._btn_autosave.setCheckable(True)
        self._btn_autosave.toggled.connect(self._on_autosave_toggle)
        self._toolbar.addSeparator()

        # Filter toggle
        self._btn_filter = self._toolbar.addAction("🔍 Filter")
        self._btn_filter.setCheckable(True)
        self._btn_filter.toggled.connect(self._on_filter_toggle)

        self._btn_clear_filter = self._toolbar.addAction("✖ Clear Filters")
        self._btn_clear_filter.triggered.connect(self._on_clear_filters)
        self._toolbar.addSeparator()

        # Refresh
        self._btn_refresh = self._toolbar.addAction("↺ Refresh")
        self._btn_refresh.triggered.connect(self._on_refresh)

        layout.addWidget(self._toolbar)

        # Table view
        self._table = QTableView()
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().sectionClicked.connect(self._on_header_click)
        self._table.verticalHeader().setDefaultSectionSize(24)
        self._table.verticalHeader().setMinimumWidth(50)
        layout.addWidget(self._table)

        # Filter row (hidden by default)
        self._filter_container = QWidget()
        self._filter_container.setVisible(False)
        self._filter_layout = QHBoxLayout(self._filter_container)
        self._filter_layout.setContentsMargins(0, 0, 0, 0)
        self._filter_widget: Optional[FilterHeaderWidget] = None
        layout.addWidget(self._filter_container)

        # Pagination bar
        self._pag_bar = self._build_pagination_bar()
        layout.addWidget(self._pag_bar)

        # Keyboard shortcuts
        QShortcut(QKeySequence.Copy, self, activated=self._on_copy)
        QShortcut(QKeySequence.Paste, self, activated=self._on_paste)
        QShortcut(QKeySequence("Delete"), self, activated=self._on_delete_cell)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self._on_undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self._on_redo)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._on_commit)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._on_refresh)

    def _build_pagination_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet("background: #181825; border-top: 1px solid #313244;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 0, 8, 0)

        self._btn_first = QPushButton("|◀")
        self._btn_first.setFixedWidth(32)
        self._btn_first.clicked.connect(self._go_first)
        self._btn_prev = QPushButton("◀")
        self._btn_prev.setFixedWidth(32)
        self._btn_prev.clicked.connect(self._go_prev)
        self._lbl_page = QLabel("Page 1 / 1")
        self._lbl_page.setAlignment(Qt.AlignCenter)
        self._lbl_page.setMinimumWidth(100)
        self._lbl_page.setStyleSheet(f"color:{DARK_TEXT_DIM}; font-size:9pt;")
        self._btn_next = QPushButton("▶")
        self._btn_next.setFixedWidth(32)
        self._btn_next.clicked.connect(self._go_next)
        self._btn_last = QPushButton("▶|")
        self._btn_last.setFixedWidth(32)
        self._btn_last.clicked.connect(self._go_last)

        self._spn_page_size = QSpinBox()
        self._spn_page_size.setRange(10, 10000)
        self._spn_page_size.setValue(DEFAULT_PAGE_SIZE)
        self._spn_page_size.setFixedWidth(70)
        self._spn_page_size.setToolTip("Rows per page")
        self._spn_page_size.valueChanged.connect(self._on_page_size_changed)

        lbl_ps = QLabel("Rows/page:")
        lbl_ps.setStyleSheet(f"color:{DARK_TEXT_DIM}; font-size:9pt;")

        self._lbl_total = QLabel("0 total rows")
        self._lbl_total.setStyleSheet(f"color:{DARK_TEXT_DIM}; font-size:9pt;")

        layout.addWidget(self._btn_first)
        layout.addWidget(self._btn_prev)
        layout.addWidget(self._lbl_page)
        layout.addWidget(self._btn_next)
        layout.addWidget(self._btn_last)
        layout.addStretch()
        layout.addWidget(self._lbl_total)
        layout.addWidget(lbl_ps)
        layout.addWidget(self._spn_page_size)
        return bar

    # ── Public API ────────────────────────────────────────────────────────────

    def load_table(self, conn: DatabaseConnection, table_name: str) -> None:
        """Load a table into the viewer."""
        self._conn = conn
        self._table_name = table_name
        self._model = TableDataModel(conn, table_name, self._spn_page_size.value())
        self._model.page_changed.connect(self._on_page_changed)
        self._model.total_rows_changed.connect(self._on_total_rows_changed)
        self._model.dirty_changed.connect(self._on_dirty_changed)
        self._table.setModel(self._model)
        self._table.sortByColumn(-1, Qt.AscendingOrder)
        self._rebuild_filter_widget()
        self._update_pagination_buttons()
        log.info("Loaded table: %s", table_name)

    def clear(self) -> None:
        self._table.setModel(None)
        self._model = None

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_add_row(self) -> None:
        if self._model:
            self._model.add_empty_row()

    def _on_delete_rows(self) -> None:
        if not self._model:
            return
        rows = sorted(set(idx.row() for idx in self._table.selectedIndexes()), reverse=True)
        if not rows:
            return
        reply = QMessageBox.question(
            self, "Delete Rows",
            f"Delete {len(rows)} selected row(s)? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            count, errors = self._model.delete_rows(rows)
            if errors:
                self.status_message.emit(f"Errors: {'; '.join(errors)}")
            else:
                self.status_message.emit(f"Deleted {count} row(s).")

    def _on_commit(self) -> None:
        if not self._model or not self._model.is_dirty:
            return
        affected, errors = self._model.commit_changes()
        if errors:
            QMessageBox.warning(self, "Commit Errors", "\n".join(errors))
        else:
            self.status_message.emit(f"✔ Saved {affected} row(s).")

    def _on_revert(self) -> None:
        if self._model:
            self._model.revert_changes()
            self.status_message.emit("Changes reverted.")

    def _on_refresh(self) -> None:
        if self._model:
            self._model.refresh()

    def _on_undo(self) -> None:
        if self._model and self._model.undo_stack.canUndo():
            self._model.undo_stack.undo()

    def _on_redo(self) -> None:
        if self._model and self._model.undo_stack.canRedo():
            self._model.undo_stack.redo()

    def _on_autosave_toggle(self, checked: bool) -> None:
        self._auto_save = checked
        label = "Auto-Save: ON" if checked else "Auto-Save: OFF"
        self._btn_autosave.setText(f"🔄 {label}")

    def _on_filter_toggle(self, checked: bool) -> None:
        self._filter_container.setVisible(checked)
        if not checked and self._model:
            self._model.clear_filters()
            if self._filter_widget:
                self._filter_widget.clear_all()

    def _on_clear_filters(self) -> None:
        if self._model:
            self._model.clear_filters()
        if self._filter_widget:
            self._filter_widget.clear_all()

    def _on_header_click(self, section: int) -> None:
        pass  # Sorting is handled by the model via setSortingEnabled

    def _on_page_changed(self, current: int, total: int) -> None:
        self._lbl_page.setText(f"Page {current + 1} / {total}")
        self._update_pagination_buttons()

    def _on_total_rows_changed(self, count: int) -> None:
        self._lbl_total.setText(f"{count:,} total rows")
        self.row_count_changed.emit(count)

    def _on_dirty_changed(self, dirty: bool) -> None:
        self.dirty_changed.emit(dirty)
        if dirty and self._auto_save:
            self._on_commit()

    def _on_page_size_changed(self, value: int) -> None:
        if self._model:
            self._model._page_size = value
            self._model.refresh()

    def _on_filter_changed(self, col_name: str, text: str) -> None:
        if self._model:
            self._model.set_filter(col_name, text)

    # ── Pagination ────────────────────────────────────────────────────────────

    def _go_first(self): self._model and self._model.first_page()
    def _go_prev(self):  self._model and self._model.prev_page()
    def _go_next(self):  self._model and self._model.next_page()
    def _go_last(self):  self._model and self._model.last_page()

    def _update_pagination_buttons(self) -> None:
        if not self._model:
            return
        self._btn_first.setEnabled(self._model.current_page > 0)
        self._btn_prev.setEnabled(self._model.current_page > 0)
        self._btn_next.setEnabled(self._model.current_page < self._model.total_pages - 1)
        self._btn_last.setEnabled(self._model.current_page < self._model.total_pages - 1)

    # ── Copy / Paste ──────────────────────────────────────────────────────────

    def _on_copy(self) -> None:
        indexes = self._table.selectedIndexes()
        if not indexes:
            return
        rows = sorted(set(i.row() for i in indexes))
        cols = sorted(set(i.column() for i in indexes))
        data: list[list[str]] = []
        for r in rows:
            row_data = []
            for c in cols:
                idx = self._model.index(r, c)
                row_data.append(self._model.data(idx, Qt.DisplayRole) or "")
            data.append(row_data)
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter="\t")
        writer.writerows(data)
        QApplication.clipboard().setText(buf.getvalue().rstrip("\n"))

    def _on_paste(self) -> None:
        if not self._model or self._conn.read_only:
            return
        text = QApplication.clipboard().text()
        if not text:
            return
        reader = csv.reader(io.StringIO(text), delimiter="\t")
        rows_data = list(reader)
        current_idx = self._table.currentIndex()
        if not current_idx.isValid():
            return
        start_row = current_idx.row()
        start_col = current_idx.column()
        for r_off, row_vals in enumerate(rows_data):
            for c_off, val in enumerate(row_vals):
                idx = self._model.index(start_row + r_off, start_col + c_off)
                if idx.isValid():
                    self._model.setData(idx, val, Qt.EditRole)

    def _on_delete_cell(self) -> None:
        if not self._model or self._conn.read_only:
            return
        for idx in self._table.selectedIndexes():
            self._model.setData(idx, "", Qt.EditRole)

    # ── Context menu ──────────────────────────────────────────────────────────

    def _on_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        menu.addAction("📋 Copy", self._on_copy, QKeySequence.Copy)
        menu.addAction("📋 Paste", self._on_paste, QKeySequence.Paste)
        menu.addSeparator()
        menu.addAction("➕ Add Row", self._on_add_row)
        menu.addAction("➖ Delete Selected Rows", self._on_delete_rows)
        menu.addSeparator()
        menu.addAction("💾 Commit Changes", self._on_commit)
        menu.addAction("↩ Revert Changes", self._on_revert)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _rebuild_filter_widget(self) -> None:
        # Clear existing
        for i in reversed(range(self._filter_layout.count())):
            w = self._filter_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        if not self._model:
            return
        self._filter_widget = FilterHeaderWidget(self._model.column_names)
        self._filter_widget.filter_changed.connect(self._on_filter_changed)
        self._filter_layout.addWidget(self._filter_widget)
