"""
widgets/export_dialog.py — Export Dialog.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QLineEdit, QFileDialog, QPlainTextEdit,
    QGroupBox, QProgressBar, QRadioButton, QButtonGroup, QWidget,
    QMessageBox,
)
from PySide6.QtCore import Qt

from app.logger import get_logger
from core.database.connection import DatabaseConnection
from core.database.introspector import SchemaIntrospector

log = get_logger("export_dialog")

EXPORT_FORMATS = [
    ("CSV (.csv)", ".csv"),
    ("Excel (.xlsx)", ".xlsx"),
    ("JSON (.json)", ".json"),
    ("SQL Dump (.sql)", ".sql"),
    ("PDF Report (.pdf)", ".pdf"),
    ("SQLite DB (.db)", ".db"),
]


class ExportDialog(QDialog):
    def __init__(self, conn: DatabaseConnection, table: str = "", parent=None):
        super().__init__(parent)
        self._conn = conn
        self._default_table = table
        self.setWindowTitle("Export Data")
        self.setMinimumSize(560, 480)
        self._setup_ui()
        self._load_tables()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Source
        grp_src = QGroupBox("Data Source")
        src_layout = QVBoxLayout(grp_src)

        self._rb_table = QRadioButton("Export entire table:")
        self._rb_query = QRadioButton("Export by SQL query:")
        self._rb_group = QButtonGroup()
        self._rb_group.addButton(self._rb_table)
        self._rb_group.addButton(self._rb_query)
        self._rb_table.setChecked(True)

        tbl_row = QHBoxLayout()
        self._cmb_table = QComboBox()
        self._cmb_table.setMinimumWidth(200)
        tbl_row.addWidget(self._rb_table)
        tbl_row.addWidget(self._cmb_table)
        tbl_row.addStretch()
        src_layout.addLayout(tbl_row)

        src_layout.addWidget(self._rb_query)
        self._txt_query = QPlainTextEdit()
        self._txt_query.setPlaceholderText("SELECT * FROM my_table WHERE condition = 'value'")
        self._txt_query.setFixedHeight(90)
        self._txt_query.setEnabled(False)
        src_layout.addWidget(self._txt_query)

        self._rb_table.toggled.connect(lambda c: self._txt_query.setEnabled(not c))
        self._rb_table.toggled.connect(lambda c: self._cmb_table.setEnabled(c))
        layout.addWidget(grp_src)

        # Format
        grp_fmt = QGroupBox("Export Format")
        fmt_layout = QHBoxLayout(grp_fmt)
        fmt_layout.addWidget(QLabel("Format:"))
        self._cmb_format = QComboBox()
        for label, ext in EXPORT_FORMATS:
            self._cmb_format.addItem(label, ext)
        fmt_layout.addWidget(self._cmb_format)
        fmt_layout.addStretch()
        layout.addWidget(grp_fmt)

        # Output path
        grp_out = QGroupBox("Output")
        out_layout = QHBoxLayout(grp_out)
        self._txt_output = QLineEdit()
        self._txt_output.setPlaceholderText("Select output path…")
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_output)
        out_layout.addWidget(self._txt_output)
        out_layout.addWidget(btn_browse)
        layout.addWidget(grp_out)

        # Options
        grp_opts = QGroupBox("Options")
        opts_layout = QVBoxLayout(grp_opts)
        self._chk_compress = QCheckBox("Compress output as ZIP")
        opts_layout.addWidget(self._chk_compress)
        layout.addWidget(grp_opts)

        # Progress
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # Buttons
        btn_row = QHBoxLayout()
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_export = QPushButton("Export")
        self._btn_export.setProperty("class", "primary")
        self._btn_export.clicked.connect(self._run_export)
        btn_row.addWidget(self._btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_export)
        layout.addLayout(btn_row)

    def _load_tables(self) -> None:
        try:
            intro = SchemaIntrospector(self._conn.connection)
            tables = intro.get_tables() + intro.get_views()
            self._cmb_table.addItems(tables)
            if self._default_table in tables:
                self._cmb_table.setCurrentText(self._default_table)
        except Exception:
            pass

    def _browse_output(self) -> None:
        ext = self._cmb_format.currentData() or ".csv"
        fmt_filter = {
            ".csv": "CSV (*.csv)",
            ".xlsx": "Excel (*.xlsx)",
            ".json": "JSON (*.json)",
            ".sql": "SQL (*.sql)",
            ".pdf": "PDF (*.pdf)",
            ".db": "SQLite (*.db)",
        }.get(ext, "All Files (*.*)")
        path, _ = QFileDialog.getSaveFileName(self, "Save Export", "", fmt_filter)
        if path:
            if not path.endswith(ext):
                path += ext
            self._txt_output.setText(path)

    def _run_export(self) -> None:
        from core.workers.import_export_workers import ExportWorker
        from services.export_service import ExportService

        output = self._txt_output.text().strip()
        if not output:
            QMessageBox.warning(self, "No output path", "Please select an output path.")
            return

        svc = ExportService(self._conn.connection)

        if self._rb_table.isChecked():
            table = self._cmb_table.currentText()
            sql = None
        else:
            sql = self._txt_query.toPlainText().strip()
            table = None
            if not sql:
                QMessageBox.warning(self, "No query", "Please enter an SQL query.")
                return

        compress = self._chk_compress.isChecked()

        def do_export():
            return svc.export(output, table=table, sql=sql, compress=compress)

        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._btn_export.setEnabled(False)

        self._worker = ExportWorker(do_export)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_done(self, path: str) -> None:
        self._progress.setRange(0, 100)
        self._progress.setValue(100)
        self._btn_export.setEnabled(True)
        QMessageBox.information(self, "Export Complete", f"Exported to:\n{path}")
        self.accept()

    def _on_error(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._btn_export.setEnabled(True)
        QMessageBox.critical(self, "Export Error", msg)
