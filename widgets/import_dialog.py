"""
widgets/import_dialog.py — Import Wizard Dialog.

5-step wizard: Select File → Preview → Map Columns → Options → Execute.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QFileDialog, QLineEdit, QTableWidget,
    QTableWidgetItem, QComboBox, QCheckBox, QSpinBox, QProgressBar,
    QTextEdit, QGroupBox, QWidget, QSplitter, QMessageBox,
    QAbstractItemView,
)

from app.logger import get_logger
from core.database.connection import DatabaseConnection
from core.database.introspector import SchemaIntrospector
from services.import_service import ImportService

log = get_logger("import_dialog")


class ImportDialog(QDialog):
    """Step-by-step import wizard."""

    def __init__(self, conn: DatabaseConnection, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._file_path: str = ""
        self._source_headers: list[str] = []
        self._dest_tables: list[str] = []
        self._column_map: dict[str, str] = {}
        self._thread: Optional[QThread] = None

        self.setWindowTitle("Import Data")
        self.setMinimumSize(700, 500)
        self._setup_ui()
        self._load_tables()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Step indicator
        self._step_label = QLabel("Step 1 of 4: Select File")
        self._step_label.setStyleSheet("font-weight:bold; font-size:11pt; padding:6px;")
        layout.addWidget(self._step_label)

        # Stacked pages
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        # Pages
        self._stack.addWidget(self._build_page1())  # 0: Select file
        self._stack.addWidget(self._build_page2())  # 1: Preview
        self._stack.addWidget(self._build_page3())  # 2: Options
        self._stack.addWidget(self._build_page4())  # 3: Progress

        # Navigation buttons
        nav = QHBoxLayout()
        self._btn_back = QPushButton("◀ Back")
        self._btn_back.clicked.connect(self._go_back)
        self._btn_back.setEnabled(False)
        self._btn_next = QPushButton("Next ▶")
        self._btn_next.setProperty("class", "primary")
        self._btn_next.clicked.connect(self._go_next)
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)
        nav.addWidget(self._btn_cancel)
        nav.addStretch()
        nav.addWidget(self._btn_back)
        nav.addWidget(self._btn_next)
        layout.addLayout(nav)

    # ── Pages ─────────────────────────────────────────────────────────────────

    def _build_page1(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        grp = QGroupBox("Source File")
        g_layout = QVBoxLayout(grp)

        file_row = QHBoxLayout()
        self._txt_file = QLineEdit()
        self._txt_file.setPlaceholderText("Select a file to import…")
        self._txt_file.setReadOnly(True)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_file)
        file_row.addWidget(self._txt_file)
        file_row.addWidget(btn_browse)
        g_layout.addLayout(file_row)

        enc_row = QHBoxLayout()
        enc_row.addWidget(QLabel("Encoding:"))
        self._cmb_encoding = QComboBox()
        self._cmb_encoding.addItems(["utf-8", "utf-8-sig", "latin-1", "cp1252", "ascii"])
        self._cmb_encoding.setFixedWidth(130)
        enc_row.addWidget(self._cmb_encoding)
        enc_row.addStretch()
        g_layout.addLayout(enc_row)
        layout.addWidget(grp)

        grp2 = QGroupBox("Destination Table")
        g2_layout = QHBoxLayout(grp2)
        g2_layout.addWidget(QLabel("Import into table:"))
        self._cmb_dest_table = QComboBox()
        self._cmb_dest_table.setMinimumWidth(200)
        g2_layout.addWidget(self._cmb_dest_table)
        g2_layout.addStretch()
        layout.addWidget(grp2)

        layout.addStretch()
        return page

    def _build_page2(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Preview (first 5 rows):"))
        self._preview_table = QTableWidget()
        self._preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self._preview_table)
        return page

    def _build_page3(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        grp_opts = QGroupBox("Import Options")
        opts_layout = QVBoxLayout(grp_opts)
        self._chk_skip_dup = QCheckBox("Skip duplicate rows (INSERT OR IGNORE)")
        self._chk_upsert = QCheckBox("Upsert mode (INSERT OR REPLACE)")
        self._spn_batch = QSpinBox()
        self._spn_batch.setRange(100, 100000)
        self._spn_batch.setValue(1000)
        batch_row = QHBoxLayout()
        batch_row.addWidget(QLabel("Batch size:"))
        batch_row.addWidget(self._spn_batch)
        batch_row.addStretch()
        opts_layout.addWidget(self._chk_skip_dup)
        opts_layout.addWidget(self._chk_upsert)
        opts_layout.addLayout(batch_row)
        layout.addWidget(grp_opts)

        # Column mapping
        grp_map = QGroupBox("Column Mapping (Source → Destination)")
        map_layout = QVBoxLayout(grp_map)
        self._map_table = QTableWidget(0, 2)
        self._map_table.setHorizontalHeaderLabels(["Source Column", "Destination Column"])
        self._map_table.horizontalHeader().setStretchLastSection(True)
        map_layout.addWidget(self._map_table)
        layout.addWidget(grp_map, 1)
        return page

    def _build_page4(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self._progress = QProgressBar()
        self._progress.setTextVisible(True)
        layout.addWidget(self._progress)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        layout.addWidget(self._log)
        return page

    # ── Navigation ────────────────────────────────────────────────────────────

    def _go_next(self) -> None:
        current = self._stack.currentIndex()
        if current == 0:
            if not self._file_path:
                QMessageBox.warning(self, "No file", "Please select a file first.")
                return
            self._load_preview()
            self._stack.setCurrentIndex(1)
            self._step_label.setText("Step 2 of 4: Preview Data")
            self._btn_back.setEnabled(True)
        elif current == 1:
            self._build_column_map()
            self._stack.setCurrentIndex(2)
            self._step_label.setText("Step 3 of 4: Options & Column Mapping")
        elif current == 2:
            self._stack.setCurrentIndex(3)
            self._step_label.setText("Step 4 of 4: Importing…")
            self._btn_next.setEnabled(False)
            self._btn_back.setEnabled(False)
            self._run_import()

    def _go_back(self) -> None:
        current = self._stack.currentIndex()
        if current > 0:
            self._stack.setCurrentIndex(current - 1)
            self._step_label.setText(f"Step {current} of 4")
            if current == 1:
                self._btn_back.setEnabled(False)
            self._btn_next.setEnabled(True)

    # ── Logic ─────────────────────────────────────────────────────────────────

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open File", "",
            "All Supported (*.csv *.xlsx *.xls *.json *.sql *.db);;"
            "CSV (*.csv);;Excel (*.xlsx *.xls);;JSON (*.json);;SQL (*.sql);;SQLite (*.db *.sqlite)"
        )
        if path:
            self._file_path = path
            self._txt_file.setText(path)

    def _load_tables(self) -> None:
        try:
            intro = SchemaIntrospector(self._conn.connection)
            self._dest_tables = intro.get_tables()
            self._cmb_dest_table.addItems(self._dest_tables)
        except Exception as exc:
            log.warning("Could not load tables: %s", exc)

    def _load_preview(self) -> None:
        svc = ImportService(self._conn.connection)
        enc = self._cmb_encoding.currentText()
        headers, rows = svc.preview_file(self._file_path, rows=5, encoding=enc)
        self._source_headers = headers
        self._preview_table.setColumnCount(len(headers))
        self._preview_table.setHorizontalHeaderLabels(headers)
        self._preview_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                self._preview_table.setItem(r, c, QTableWidgetItem(str(val)))

    def _build_column_map(self) -> None:
        self._map_table.setRowCount(len(self._source_headers))
        for i, h in enumerate(self._source_headers):
            self._map_table.setItem(i, 0, QTableWidgetItem(h))
            cmb = QComboBox()
            cmb.addItem("-- skip --", "")
            try:
                from core.database.introspector import SchemaIntrospector
                intro = SchemaIntrospector(self._conn.connection)
                table = self._cmb_dest_table.currentText()
                if table:
                    cols = [c.name for c in intro.get_columns(table)]
                    cmb.addItems(cols)
                    # Auto-match same name
                    idx = cmb.findText(h, Qt.MatchFixedString)
                    if idx >= 0:
                        cmb.setCurrentIndex(idx)
            except Exception:
                pass
            self._map_table.setCellWidget(i, 1, cmb)

    def _run_import(self) -> None:
        from core.workers.import_export_workers import ImportWorker

        table = self._cmb_dest_table.currentText()
        enc = self._cmb_encoding.currentText()
        skip_dup = self._chk_skip_dup.isChecked()
        upsert = self._chk_upsert.isChecked()
        batch_size = self._spn_batch.value()

        # Build column map
        col_map = {}
        for i in range(self._map_table.rowCount()):
            src = self._map_table.item(i, 0).text() if self._map_table.item(i, 0) else ""
            cmb = self._map_table.cellWidget(i, 1)
            dest = cmb.currentText() if cmb else ""
            if src and dest and dest != "-- skip --":
                col_map[src] = dest

        svc = ImportService(self._conn.connection)

        def do_import():
            return svc.import_file(
                self._file_path, table,
                column_map=col_map or None,
                skip_duplicates=skip_dup,
                upsert=upsert,
                batch_size=batch_size,
                encoding=enc,
            )

        self._worker = ImportWorker(do_import)
        self._worker.finished.connect(self._on_import_done)
        self._worker.error.connect(self._on_import_error)
        self._progress.setRange(0, 0)  # indeterminate
        self._worker.start()

    def _on_import_done(self, rows: int) -> None:
        self._progress.setRange(0, 100)
        self._progress.setValue(100)
        self._log.append(f"✔ Import complete. {rows} rows imported.")
        self._btn_next.setText("Close")
        self._btn_next.setEnabled(True)
        self._btn_next.clicked.disconnect()
        self._btn_next.clicked.connect(self.accept)

    def _on_import_error(self, msg: str) -> None:
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._log.append(f"✘ Error: {msg}")
        self._btn_back.setEnabled(True)
