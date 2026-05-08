"""
widgets/mass_update_dialog.py — Mass Update Tool.

Allows updating all rows matching a condition in bulk.
Generates and previews the UPDATE SQL before executing.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QLineEdit, QPlainTextEdit, QGroupBox,
    QMessageBox, QWidget, QFormLayout,
)
from PySide6.QtGui import QFont

from app.logger import get_logger
from core.database.connection import DatabaseConnection
from core.database.introspector import SchemaIntrospector

log = get_logger("mass_update")


class MassUpdateDialog(QDialog):
    """
    Mass update tool.
    Lets user pick: SET column = value WHERE condition.
    Shows preview SQL and affected row count before executing.
    """

    def __init__(self, conn: DatabaseConnection, table: str = "", parent=None):
        super().__init__(parent)
        self._conn = conn
        self._intro = SchemaIntrospector(conn.connection)
        self.setWindowTitle("Mass Update Tool")
        self.setMinimumSize(600, 480)
        self._setup_ui(table)

    def _setup_ui(self, default_table: str = "") -> None:
        layout = QVBoxLayout(self)

        # Table selector
        tbl_row = QHBoxLayout()
        tbl_row.addWidget(QLabel("Table:"))
        self._cmb_table = QComboBox()
        tables = self._intro.get_tables()
        self._cmb_table.addItems(tables)
        if default_table in tables:
            self._cmb_table.setCurrentText(default_table)
        self._cmb_table.currentTextChanged.connect(self._on_table_changed)
        tbl_row.addWidget(self._cmb_table, 1)
        layout.addLayout(tbl_row)

        # SET clause
        grp_set = QGroupBox("SET — Column to Update")
        set_layout = QHBoxLayout(grp_set)
        set_layout.addWidget(QLabel("Column:"))
        self._cmb_col = QComboBox()
        self._cmb_col.setMinimumWidth(180)
        self._cmb_col.currentTextChanged.connect(self._update_preview)
        set_layout.addWidget(self._cmb_col)
        set_layout.addWidget(QLabel("="))
        self._txt_value = QLineEdit()
        self._txt_value.setPlaceholderText("New value (use NULL for null)")
        self._txt_value.textChanged.connect(self._update_preview)
        set_layout.addWidget(self._txt_value, 1)
        layout.addWidget(grp_set)

        # WHERE clause
        grp_where = QGroupBox("WHERE — Filter (leave empty to update ALL rows)")
        where_layout = QVBoxLayout(grp_where)
        self._txt_where = QLineEdit()
        self._txt_where.setPlaceholderText("e.g.  status = 'inactive'  OR  age > 18")
        self._txt_where.textChanged.connect(self._update_preview)
        where_layout.addWidget(self._txt_where)
        layout.addWidget(grp_where)

        # SQL Preview
        layout.addWidget(QLabel("<b>Generated SQL:</b>"))
        self._sql_preview = QPlainTextEdit()
        self._sql_preview.setReadOnly(True)
        self._sql_preview.setFont(QFont("Consolas", 10))
        self._sql_preview.setMaximumHeight(100)
        layout.addWidget(self._sql_preview)

        # Affected rows preview
        self._lbl_affected = QLabel("Affected rows: —")
        self._lbl_affected.setStyleSheet("color:#89b4fa; font-weight:600;")
        layout.addWidget(self._lbl_affected)
        btn_preview = QPushButton("🔍 Preview Affected Rows")
        btn_preview.clicked.connect(self._on_preview)
        layout.addWidget(btn_preview)

        layout.addStretch()

        # Buttons
        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        self._btn_execute = QPushButton("⚡ Execute Update")
        self._btn_execute.setProperty("class", "danger")
        self._btn_execute.clicked.connect(self._on_execute)
        btns.addWidget(btn_cancel)
        btns.addStretch()
        btns.addWidget(self._btn_execute)
        layout.addLayout(btns)

        # Init columns
        if tables:
            self._on_table_changed(self._cmb_table.currentText())

    def _on_table_changed(self, table: str) -> None:
        self._cmb_col.clear()
        if table:
            cols = self._intro.get_columns(table)
            self._cmb_col.addItems([c.name for c in cols])
        self._update_preview()

    def _build_sql(self) -> str:
        table = self._cmb_table.currentText()
        col = self._cmb_col.currentText()
        val = self._txt_value.text().strip()
        where = self._txt_where.text().strip()

        if not table or not col:
            return ""

        val_sql = "NULL" if val.upper() == "NULL" else f"'{val}'"
        where_sql = f" WHERE {where}" if where else ""
        return f'UPDATE "{table}" SET "{col}" = {val_sql}{where_sql};'

    def _update_preview(self) -> None:
        self._sql_preview.setPlainText(self._build_sql())

    def _on_preview(self) -> None:
        table = self._cmb_table.currentText()
        where = self._txt_where.text().strip()
        if not table:
            return
        try:
            where_sql = f"WHERE {where}" if where else ""
            count = self._conn.execute(
                f'SELECT COUNT(*) FROM "{table}" {where_sql};'
            ).fetchone()[0]
            self._lbl_affected.setText(f"Affected rows: <b style='color:#f38ba8'>{count:,}</b>")
        except Exception as exc:
            self._lbl_affected.setText(f"Error: {exc}")

    def _on_execute(self) -> None:
        sql = self._build_sql()
        if not sql:
            QMessageBox.warning(self, "Incomplete", "Please fill in all required fields.")
            return

        # Count first
        self._on_preview()

        reply = QMessageBox.question(
            self, "Confirm Mass Update",
            f"This will execute:\n\n{sql}\n\nAre you sure? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            cursor = self._conn.execute(sql)
            self._conn.commit()
            QMessageBox.information(self, "Done", f"Updated {cursor.rowcount} rows.")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Update Failed", str(exc))
