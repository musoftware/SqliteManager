"""
widgets/create_table_dialog.py — Visual Create Table Dialog.

Allows creating a new table by defining columns interactively,
then generates and executes the CREATE TABLE SQL.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QComboBox, QCheckBox, QHeaderView,
    QPlainTextEdit, QSplitter, QWidget, QMessageBox, QAbstractItemView,
)
from PySide6.QtGui import QFont

from app.logger import get_logger
from core.database.connection import DatabaseConnection

log = get_logger("create_table")

COL_TYPES = ["INTEGER", "TEXT", "REAL", "NUMERIC", "BLOB",
             "VARCHAR(255)", "BOOLEAN", "DATE", "DATETIME", "JSON"]


class CreateTableDialog(QDialog):
    """Interactive CREATE TABLE dialog with live SQL preview."""

    def __init__(self, conn: DatabaseConnection, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("Create New Table")
        self.setMinimumSize(800, 550)
        self._setup_ui()
        self._update_preview()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Table name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Table Name:"))
        self._txt_name = QLineEdit()
        self._txt_name.setPlaceholderText("e.g. users, products, orders…")
        self._txt_name.textChanged.connect(self._update_preview)
        name_row.addWidget(self._txt_name, 1)
        layout.addLayout(name_row)

        splitter = QSplitter(Qt.Horizontal)

        # Columns editor
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("<b>Columns</b>"))

        self._col_table = QTableWidget(0, 6)
        self._col_table.setHorizontalHeaderLabels(["Name", "Type", "PK", "Not Null", "Unique", "Default"])
        self._col_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._col_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        for i in range(2, 5):
            self._col_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._col_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._col_table.itemChanged.connect(self._update_preview)
        left_layout.addWidget(self._col_table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("➕ Add Column")
        btn_add.clicked.connect(self._add_column_row)
        btn_remove = QPushButton("➖ Remove")
        btn_remove.clicked.connect(self._remove_column_row)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        btn_row.addStretch()
        left_layout.addLayout(btn_row)
        splitter.addWidget(left)

        # SQL Preview
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("<b>Generated SQL</b>"))
        self._sql_preview = QPlainTextEdit()
        self._sql_preview.setReadOnly(True)
        self._sql_preview.setFont(QFont("Consolas", 10))
        right_layout.addWidget(self._sql_preview)
        splitter.addWidget(right)
        splitter.setSizes([500, 300])
        layout.addWidget(splitter)

        # Buttons
        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        self._btn_create = QPushButton("✨ Create Table")
        self._btn_create.setProperty("class", "primary")
        self._btn_create.clicked.connect(self._on_create)
        btns.addWidget(btn_cancel)
        btns.addStretch()
        btns.addWidget(self._btn_create)
        layout.addLayout(btns)

        # Start with one default column
        self._add_column_row("id", "INTEGER", pk=True)
        self._add_column_row("name", "TEXT", not_null=True)
        self._add_column_row("created_at", "DATETIME")

    def _add_column_row(self, name: str = "", col_type: str = "TEXT",
                         pk: bool = False, not_null: bool = False,
                         unique: bool = False, default: str = "") -> None:
        row = self._col_table.rowCount()
        self._col_table.insertRow(row)

        # Name
        self._col_table.setItem(row, 0, QTableWidgetItem(name))

        # Type combo
        type_cmb = QComboBox()
        type_cmb.addItems(COL_TYPES)
        if col_type in COL_TYPES:
            type_cmb.setCurrentText(col_type)
        type_cmb.currentTextChanged.connect(self._update_preview)
        self._col_table.setCellWidget(row, 1, type_cmb)

        # Checkboxes
        for col_idx, checked in [(2, pk), (3, not_null), (4, unique)]:
            chk = QCheckBox()
            chk.setChecked(checked)
            chk.setStyleSheet("margin-left:8px;")
            chk.toggled.connect(self._update_preview)
            container = QWidget()
            c_layout = QHBoxLayout(container)
            c_layout.addWidget(chk)
            c_layout.setAlignment(Qt.AlignCenter)
            c_layout.setContentsMargins(0, 0, 0, 0)
            self._col_table.setCellWidget(row, col_idx, container)

        # Default
        self._col_table.setItem(row, 5, QTableWidgetItem(default))
        self._update_preview()

    def _remove_column_row(self) -> None:
        rows = set(idx.row() for idx in self._col_table.selectedIndexes())
        for r in sorted(rows, reverse=True):
            self._col_table.removeRow(r)
        self._update_preview()

    def _get_chk(self, row: int, col: int) -> bool:
        container = self._col_table.cellWidget(row, col)
        if container:
            for child in container.children():
                if isinstance(child, QCheckBox):
                    return child.isChecked()
        return False

    def _build_sql(self) -> str:
        table_name = self._txt_name.text().strip() or "new_table"
        lines = []
        pk_cols = []

        for row in range(self._col_table.rowCount()):
            name_item = self._col_table.item(row, 0)
            col_name = name_item.text().strip() if name_item else f"col{row}"
            if not col_name:
                continue

            type_cmb = self._col_table.cellWidget(row, 1)
            col_type = type_cmb.currentText() if type_cmb else "TEXT"

            is_pk = self._get_chk(row, 2)
            is_nn = self._get_chk(row, 3)
            is_uq = self._get_chk(row, 4)

            default_item = self._col_table.item(row, 5)
            default = default_item.text().strip() if default_item else ""

            col_def = f'    "{col_name}" {col_type}'
            if is_pk and self._col_table.rowCount() > 1:
                pk_cols.append(col_name)
            elif is_pk:
                col_def += " PRIMARY KEY"
                if col_type == "INTEGER":
                    col_def += " AUTOINCREMENT"
            if is_nn and not is_pk:
                col_def += " NOT NULL"
            if is_uq and not is_pk:
                col_def += " UNIQUE"
            if default:
                col_def += f" DEFAULT '{default}'"
            lines.append(col_def)

        if len(pk_cols) > 1:
            pk_str = ", ".join(f'"{c}"' for c in pk_cols)
            lines.append(f"    PRIMARY KEY ({pk_str})")

        body = ",\n".join(lines)
        return f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n{body}\n);'

    def _update_preview(self) -> None:
        self._sql_preview.setPlainText(self._build_sql())

    def _on_create(self) -> None:
        sql = self._build_sql()
        table_name = self._txt_name.text().strip()
        if not table_name:
            QMessageBox.warning(self, "No Name", "Please enter a table name.")
            return
        if self._col_table.rowCount() == 0:
            QMessageBox.warning(self, "No Columns", "Please add at least one column.")
            return
        try:
            self._conn.execute(sql)
            self._conn.commit()
            log.info("Created table: %s", table_name)
            QMessageBox.information(self, "Done", f"Table '{table_name}' created successfully.")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Create Failed", str(exc))
