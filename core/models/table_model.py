"""
core/models/table_model.py — Virtual Paginated Qt Table Model.

Uses QAbstractTableModel with LIMIT/OFFSET paging so millions of rows
never load into memory. Supports editing, sorting, filtering, undo/redo.
"""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
    Signal,
)
from PySide6.QtGui import QUndoStack, QUndoCommand
from PySide6.QtGui import QColor, QFont

from app.config import DEFAULT_PAGE_SIZE, EDITOR_FONT_FAMILY
from app.logger import get_logger
from core.database.connection import DatabaseConnection
from core.database.executor import SqlExecutor
from core.database.introspector import ColumnInfo, SchemaIntrospector

log = get_logger("table_model")


# ── Undo/Redo command ─────────────────────────────────────────────────────────

class EditCellCommand(QUndoCommand):
    def __init__(self, model: "TableDataModel", index: QModelIndex, old_val, new_val):
        super().__init__(f"Edit [{index.row()},{index.column()}]")
        self._model = model
        self._row = index.row()
        self._col = index.column()
        self._old = old_val
        self._new = new_val

    def redo(self):
        self._model._set_cell(self._row, self._col, self._new)

    def undo(self):
        self._model._set_cell(self._row, self._col, self._old)


# ── Main model ────────────────────────────────────────────────────────────────

class TableDataModel(QAbstractTableModel):
    """
    Virtual model for a single SQLite table.

    Features
    --------
    - Pages through data with LIMIT/OFFSET
    - Dirty-cell tracking for commit/revert
    - Undo stack for cell edits
    - Sort delegation to SQL ORDER BY
    - Column filter delegation to SQL WHERE … LIKE
    """

    page_changed = Signal(int, int)      # current_page, total_pages
    total_rows_changed = Signal(int)
    dirty_changed = Signal(bool)

    def __init__(
        self,
        conn: DatabaseConnection,
        table_name: str,
        page_size: int = DEFAULT_PAGE_SIZE,
        parent=None,
    ):
        super().__init__(parent)
        self._conn = conn
        self._executor = SqlExecutor(conn)
        self._introspector = SchemaIntrospector(conn.connection)
        self._table = table_name

        self._page_size = page_size
        self._current_page = 0
        self._total_rows = 0
        self._total_pages = 0

        self._columns: list[ColumnInfo] = []
        self._col_names: list[str] = []
        self._pk_col: Optional[str] = None

        self._rows: list[list[Any]] = []     # current page data (mutable)
        self._dirty: dict[tuple, Any] = {}   # (row_in_page, col_idx) → new_val
        self._new_rows: list[list[Any]] = [] # rows pending insert

        self._sort_col: Optional[str] = None
        self._sort_asc: bool = True
        self._filters: dict[str, str] = {}

        self._undo_stack = QUndoStack(self)
        self._read_only = conn.read_only

        self._load_schema()
        self.refresh()

    # ── Schema ────────────────────────────────────────────────────────────────

    def _load_schema(self) -> None:
        self._columns = self._introspector.get_columns(self._table)
        self._col_names = [c.name for c in self._columns]
        pk_cols = [c for c in self._columns if c.pk > 0]
        self._pk_col = pk_cols[0].name if pk_cols else None

    # ── Data loading ──────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload current page from DB."""
        self.beginResetModel()
        try:
            self._total_rows = self._executor.count_rows(self._table, self._filters)
            self._total_pages = max(
                1,
                (self._total_rows + self._page_size - 1) // self._page_size,
            )
            result = self._executor.fetch_page(
                self._table,
                page=self._current_page,
                page_size=self._page_size,
                order_col=self._sort_col,
                order_asc=self._sort_asc,
                filters=self._filters,
            )
            self._rows = [list(row) for row in result.rows]
            self._dirty.clear()
        except Exception as exc:
            log.error("Error loading page: %s", exc)
            self._rows = []
        self.endResetModel()
        self.total_rows_changed.emit(self._total_rows)
        self.page_changed.emit(self._current_page, self._total_pages)
        self.dirty_changed.emit(False)

    def set_page(self, page: int) -> None:
        if 0 <= page < self._total_pages:
            self._current_page = page
            self.refresh()

    def next_page(self) -> None:
        self.set_page(self._current_page + 1)

    def prev_page(self) -> None:
        self.set_page(self._current_page - 1)

    def first_page(self) -> None:
        self.set_page(0)

    def last_page(self) -> None:
        self.set_page(self._total_pages - 1)

    # ── QAbstractTableModel interface ─────────────────────────────────────────

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._col_names)

    def data(self, index: QModelIndex, role=Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        r, c = index.row(), index.column()

        if role in (Qt.DisplayRole, Qt.EditRole):
            key = (r, c)
            val = self._dirty.get(key, self._rows[r][c])
            return "" if val is None else str(val)

        if role == Qt.BackgroundRole:
            key = (r, c)
            if key in self._dirty:
                return QColor("#3d3a1f")  # yellowish tint for modified
            if r % 2 == 0:
                return QColor("#1e1e2e")
            return QColor("#181825")

        if role == Qt.ForegroundRole:
            key = (r, c)
            if self._rows[r][c] is None:
                return QColor("#7f849c")  # dim NULL values
            return QColor("#cdd6f4")

        if role == Qt.FontRole:
            f = QFont(EDITOR_FONT_FAMILY, 10)
            return f

        if role == Qt.ToolTipRole:
            key = (r, c)
            val = self._dirty.get(key, self._rows[r][c])
            return f"NULL" if val is None else str(val)

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                name = self._col_names[section] if section < len(self._col_names) else ""
                col_info = self._columns[section] if section < len(self._columns) else None
                if col_info and col_info.pk:
                    return f"🔑 {name}"
                return name
            return str(section + 1 + self._current_page * self._page_size)
        if role == Qt.ToolTipRole and orientation == Qt.Horizontal:
            if section < len(self._columns):
                c = self._columns[section]
                return (
                    f"Name: {c.name}\n"
                    f"Type: {c.type}\n"
                    f"Nullable: {not c.notnull}\n"
                    f"Default: {c.default_value}\n"
                    f"PK: {bool(c.pk)}"
                )
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if not self._read_only:
            base |= Qt.ItemIsEditable
        return base

    def setData(self, index: QModelIndex, value: Any, role=Qt.EditRole) -> bool:
        if not index.isValid() or role != Qt.EditRole or self._read_only:
            return False
        r, c = index.row(), index.column()
        old_val = self._dirty.get((r, c), self._rows[r][c])
        if str(old_val) == str(value):
            return False
        cmd = EditCellCommand(self, index, old_val, value)
        self._undo_stack.push(cmd)
        return True

    def _set_cell(self, row: int, col: int, value: Any) -> None:
        """Internal — called by undo/redo commands."""
        self._dirty[(row, col)] = value
        idx = self.index(row, col)
        self.dataChanged.emit(idx, idx, [Qt.DisplayRole, Qt.BackgroundRole])
        self.dirty_changed.emit(bool(self._dirty))

    # ── Sorting & Filtering ───────────────────────────────────────────────────

    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder) -> None:
        if column < len(self._col_names):
            self._sort_col = self._col_names[column]
            self._sort_asc = order == Qt.AscendingOrder
            self._current_page = 0
            self.refresh()

    def set_filter(self, col_name: str, value: str) -> None:
        if value:
            self._filters[col_name] = value
        else:
            self._filters.pop(col_name, None)
        self._current_page = 0
        self.refresh()

    def clear_filters(self) -> None:
        self._filters.clear()
        self._current_page = 0
        self.refresh()

    # ── Write operations ──────────────────────────────────────────────────────

    def commit_changes(self) -> tuple[int, list[str]]:
        """
        Persist all dirty cells to the database.
        Returns (affected_rows, [error_messages]).
        """
        if not self._dirty or self._read_only:
            return 0, []

        errors = []
        affected = 0

        # Group dirty cells by row
        rows_to_update: dict[int, dict[str, Any]] = {}
        for (row_idx, col_idx), new_val in self._dirty.items():
            if row_idx >= len(self._rows):
                continue
            rows_to_update.setdefault(row_idx, {})[self._col_names[col_idx]] = new_val

        for row_idx, updates in rows_to_update.items():
            if self._pk_col and self._pk_col not in updates:
                pk_val = self._rows[row_idx][self._col_names.index(self._pk_col)]
                try:
                    self._executor.update_row(self._table, self._pk_col, pk_val, updates)
                    # Apply to in-memory cache
                    for col_name, val in updates.items():
                        col_idx = self._col_names.index(col_name)
                        self._rows[row_idx][col_idx] = val
                    affected += 1
                except Exception as exc:
                    errors.append(f"Row {row_idx}: {exc}")
            else:
                errors.append(f"Row {row_idx}: No primary key to update by.")

        self._dirty.clear()
        self.dirty_changed.emit(False)
        return affected, errors

    def revert_changes(self) -> None:
        self._dirty.clear()
        self._undo_stack.clear()
        self.beginResetModel()
        self.endResetModel()
        self.dirty_changed.emit(False)

    def add_empty_row(self) -> None:
        """Append an empty row for the user to fill in."""
        if self._read_only:
            return
        empty = [None] * len(self._col_names)
        self.beginInsertRows(QModelIndex(), len(self._rows), len(self._rows))
        self._rows.append(empty)
        self.endInsertRows()

    def delete_rows(self, row_indices: list[int]) -> tuple[int, list[str]]:
        """Delete selected rows by primary key."""
        if self._read_only or not self._pk_col:
            return 0, ["Cannot delete: no primary key or read-only mode."]
        pk_col_idx = self._col_names.index(self._pk_col)
        pk_vals = [self._rows[r][pk_col_idx] for r in row_indices if r < len(self._rows)]
        try:
            count = self._executor.delete_rows(self._table, self._pk_col, pk_vals)
            self.refresh()
            return count, []
        except Exception as exc:
            return 0, [str(exc)]

    # ── Accessors ─────────────────────────────────────────────────────────────

    @property
    def is_dirty(self) -> bool:
        return bool(self._dirty)

    @property
    def undo_stack(self) -> QUndoStack:
        return self._undo_stack

    @property
    def current_page(self) -> int:
        return self._current_page

    @property
    def total_pages(self) -> int:
        return self._total_pages

    @property
    def total_rows(self) -> int:
        return self._total_rows

    @property
    def column_names(self) -> list[str]:
        return self._col_names

    @property
    def columns_info(self) -> list[ColumnInfo]:
        return self._columns

    def get_row_data(self, row_idx: int) -> dict[str, Any]:
        if row_idx >= len(self._rows):
            return {}
        return {
            self._col_names[c]: self._dirty.get((row_idx, c), self._rows[row_idx][c])
            for c in range(len(self._col_names))
        }
