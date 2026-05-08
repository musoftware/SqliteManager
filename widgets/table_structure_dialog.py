"""
widgets/table_structure_dialog.py — Visual Table Structure Viewer.

Shows column details, foreign keys, and indexes in a readable format.
Also allows adding/dropping columns and indexes.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QHeaderView, QWidget,
    QInputDialog, QMessageBox, QLineEdit, QComboBox, QCheckBox,
    QGroupBox, QFormLayout,
)
from PySide6.QtGui import QColor, QFont

from app.logger import get_logger
from core.database.connection import DatabaseConnection
from core.database.introspector import SchemaIntrospector, ColumnInfo

log = get_logger("table_structure")

TYPE_CHOICES = ["INTEGER", "TEXT", "REAL", "NUMERIC", "BLOB", "BOOLEAN", "DATE", "DATETIME", "VARCHAR(255)"]


class TableStructureDialog(QDialog):
    """
    Shows the full structure of a table:
    - Columns tab: name, type, nullable, default, PK
    - Foreign Keys tab
    - Indexes tab
    - DDL tab: raw CREATE TABLE SQL
    - Stats tab: row count, size estimates
    """

    def __init__(self, conn: DatabaseConnection, table_name: str, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._table = table_name
        self._intro = SchemaIntrospector(conn.connection)
        self._info = self._intro.get_table_info(table_name)

        self.setWindowTitle(f"Table Structure — {table_name}")
        self.setMinimumSize(750, 500)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Title row
        title_row = QHBoxLayout()
        title = QLabel(f"<b style='color:#cba6f7; font-size:13pt;'>📋 {self._table}</b>")
        row_count = QLabel(f"<span style='color:#7f849c;'>{self._info.row_count:,} rows</span>")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(row_count)
        layout.addLayout(title_row)

        tabs = QTabWidget()

        # ── Columns tab ───────────────────────────────────────────────────────
        cols_tab = QWidget()
        cols_layout = QVBoxLayout(cols_tab)

        self._cols_table = QTableWidget(len(self._info.columns), 7)
        self._cols_table.setHorizontalHeaderLabels([
            "#", "Column Name", "Type", "Not Null", "Default", "PK", "FK"
        ])
        self._cols_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._cols_table.setAlternatingRowColors(True)
        self._cols_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._cols_table.setSelectionBehavior(QTableWidget.SelectRows)

        fk_map = {fk.from_col: f"{fk.table}.{fk.to_col}" for fk in self._info.foreign_keys}

        for i, col in enumerate(self._info.columns):
            items = [
                str(col.cid),
                col.name,
                col.type or "TEXT",
                "✓" if col.notnull else "",
                str(col.default_value) if col.default_value is not None else "",
                "🔑" if col.pk else "",
                fk_map.get(col.name, ""),
            ]
            for j, val in enumerate(items):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter if j != 1 else Qt.AlignLeft | Qt.AlignVCenter)
                if col.pk:
                    item.setForeground(QColor("#f9e2af"))
                elif col.name in fk_map:
                    item.setForeground(QColor("#89b4fa"))
                self._cols_table.setItem(i, j, item)

        cols_layout.addWidget(self._cols_table)

        # Add/Drop column buttons (only if not read-only)
        if not self._conn.read_only:
            btn_row = QHBoxLayout()
            btn_add_col = QPushButton("➕ Add Column")
            btn_add_col.clicked.connect(self._on_add_column)
            btn_row.addWidget(btn_add_col)
            btn_row.addStretch()
            cols_layout.addLayout(btn_row)

        tabs.addTab(cols_tab, f"Columns ({len(self._info.columns)})")

        # ── Foreign Keys tab ──────────────────────────────────────────────────
        fk_tab = QWidget()
        fk_layout = QVBoxLayout(fk_tab)
        fk_tbl = QTableWidget(len(self._info.foreign_keys), 5)
        fk_tbl.setHorizontalHeaderLabels(["ID", "From Column", "→ Table", "→ Column", "On Delete"])
        fk_tbl.horizontalHeader().setStretchLastSection(True)
        fk_tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        fk_tbl.setAlternatingRowColors(True)
        for i, fk in enumerate(self._info.foreign_keys):
            for j, val in enumerate([str(fk.id), fk.from_col, fk.table, fk.to_col, fk.on_delete]):
                fk_tbl.setItem(i, j, QTableWidgetItem(val))
        fk_layout.addWidget(fk_tbl)
        tabs.addTab(fk_tab, f"Foreign Keys ({len(self._info.foreign_keys)})")

        # ── Indexes tab ───────────────────────────────────────────────────────
        idx_tab = QWidget()
        idx_layout = QVBoxLayout(idx_tab)
        idx_tbl = QTableWidget(len(self._info.indexes), 4)
        idx_tbl.setHorizontalHeaderLabels(["Name", "Unique", "Columns", "Origin"])
        idx_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        idx_tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        idx_tbl.setAlternatingRowColors(True)
        for i, idx in enumerate(self._info.indexes):
            for j, val in enumerate([idx.name, "✓" if idx.unique else "", ", ".join(idx.columns), idx.origin]):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter if j != 0 else Qt.AlignLeft | Qt.AlignVCenter)
                idx_tbl.setItem(i, j, item)
        idx_layout.addWidget(idx_tbl)

        if not self._conn.read_only:
            btn_row2 = QHBoxLayout()
            btn_add_idx = QPushButton("➕ Add Index")
            btn_add_idx.clicked.connect(self._on_add_index)
            btn_row2.addWidget(btn_add_idx)
            btn_row2.addStretch()
            idx_layout.addLayout(btn_row2)

        tabs.addTab(idx_tab, f"Indexes ({len(self._info.indexes)})")

        # ── DDL tab ───────────────────────────────────────────────────────────
        from PySide6.QtWidgets import QPlainTextEdit
        ddl_tab = QPlainTextEdit()
        ddl_tab.setReadOnly(True)
        ddl_tab.setFont(QFont("Consolas", 10))
        sql = self._info.sql or ""
        try:
            from services.formatter_service import SqlFormatterService
            sql = SqlFormatterService.format(sql)
        except Exception:
            pass
        ddl_tab.setPlainText(sql)
        tabs.addTab(ddl_tab, "DDL")

        # ── Stats tab ─────────────────────────────────────────────────────────
        stats_tab = QWidget()
        stats_layout = QFormLayout(stats_tab)
        try:
            page_size = self._conn.execute("PRAGMA page_size;").fetchone()[0]
            page_count = self._conn.execute("PRAGMA page_count;").fetchone()[0]
            db_size_mb = round(page_size * page_count / (1024 * 1024), 3)
            stats_layout.addRow("Table Name:", QLabel(f"<b>{self._table}</b>"))
            stats_layout.addRow("Row Count:", QLabel(f"<b>{self._info.row_count:,}</b>"))
            stats_layout.addRow("Column Count:", QLabel(str(len(self._info.columns))))
            stats_layout.addRow("Index Count:", QLabel(str(len(self._info.indexes))))
            stats_layout.addRow("FK Count:", QLabel(str(len(self._info.foreign_keys))))
            stats_layout.addRow("DB Page Size:", QLabel(f"{page_size} bytes"))
            stats_layout.addRow("DB Size:", QLabel(f"{db_size_mb} MB"))
        except Exception as e:
            stats_layout.addRow("Error:", QLabel(str(e)))
        tabs.addTab(stats_tab, "Statistics")

        layout.addWidget(tabs)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)

    # ── Add Column ────────────────────────────────────────────────────────────

    def _on_add_column(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Column")
        dlg.setMinimumWidth(350)
        layout = QVBoxLayout(dlg)

        form = QFormLayout()
        name_edit = QLineEdit()
        type_combo = QComboBox()
        type_combo.addItems(TYPE_CHOICES)
        not_null_chk = QCheckBox("NOT NULL")
        default_edit = QLineEdit()
        default_edit.setPlaceholderText("optional default value")

        form.addRow("Column Name:", name_edit)
        form.addRow("Type:", type_combo)
        form.addRow("Constraint:", not_null_chk)
        form.addRow("Default:", default_edit)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Add")
        btn_ok.setProperty("class", "primary")
        btn_cancel = QPushButton("Cancel")
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel.clicked.connect(dlg.reject)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

        if dlg.exec() != QDialog.Accepted:
            return

        col_name = name_edit.text().strip()
        col_type = type_combo.currentText()
        not_null = not_null_chk.isChecked()
        default = default_edit.text().strip()

        if not col_name:
            QMessageBox.warning(self, "Invalid", "Column name is required.")
            return

        sql = f'ALTER TABLE "{self._table}" ADD COLUMN "{col_name}" {col_type}'
        if not_null and default:
            sql += f" NOT NULL DEFAULT '{default}'"
        elif default:
            sql += f" DEFAULT '{default}'"
        sql += ";"

        try:
            self._conn.execute(sql)
            self._conn.commit()
            QMessageBox.information(self, "Done", f"Column '{col_name}' added.")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    # ── Add Index ─────────────────────────────────────────────────────────────

    def _on_add_index(self) -> None:
        col_names = [c.name for c in self._info.columns]
        col, ok = QInputDialog.getItem(self, "Add Index", "Column to index:", col_names, 0, False)
        if not ok:
            return
        idx_name = f"idx_{self._table}_{col}"
        unique, ok2 = QInputDialog.getItem(self, "Add Index", "Index type:", ["Regular", "Unique"], 0, False)
        if not ok2:
            return
        unique_kw = "UNIQUE " if unique == "Unique" else ""
        sql = f'CREATE {unique_kw}INDEX IF NOT EXISTS "{idx_name}" ON "{self._table}" ("{col}");'
        try:
            self._conn.execute(sql)
            self._conn.commit()
            QMessageBox.information(self, "Done", f"Index '{idx_name}' created.")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
