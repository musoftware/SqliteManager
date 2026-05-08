"""
widgets/pragma_editor.py — Visual SQLite PRAGMA Editor.

Shows all PRAGMAs in a table with current values and editable controls.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QLineEdit, QCheckBox, QSpinBox,
    QHeaderView, QMessageBox, QGroupBox, QTextEdit,
)

from app.logger import get_logger
from core.database.connection import DatabaseConnection
from core.database.pragma_manager import PragmaManager, PRAGMA_DEFINITIONS

log = get_logger("pragma_editor")


class PragmaEditorDialog(QDialog):
    """Visual editor for SQLite PRAGMAs."""

    def __init__(self, conn: DatabaseConnection, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._pragma_mgr = PragmaManager(conn.connection)
        self.setWindowTitle("SQLite PRAGMA Editor")
        self.setMinimumSize(700, 500)
        self._setup_ui()
        self._load_values()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Table
        self._table = QTableWidget(len(PRAGMA_DEFINITIONS), 4)
        self._table.setHorizontalHeaderLabels(["PRAGMA", "Category", "Current Value", "Description"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.AllEditTriggers)
        layout.addWidget(self._table)

        # Maintenance buttons
        grp = QGroupBox("Maintenance")
        grp_layout = QHBoxLayout(grp)
        btn_vacuum = QPushButton("🗜 VACUUM")
        btn_vacuum.clicked.connect(self._run_vacuum)
        btn_analyze = QPushButton("📊 ANALYZE")
        btn_analyze.clicked.connect(self._run_analyze)
        btn_integrity = QPushButton("✔ Integrity Check")
        btn_integrity.clicked.connect(self._run_integrity)
        grp_layout.addWidget(btn_vacuum)
        grp_layout.addWidget(btn_analyze)
        grp_layout.addWidget(btn_integrity)
        grp_layout.addStretch()
        layout.addWidget(grp)

        # Results
        self._result_label = QLabel("")
        self._result_label.setStyleSheet("color: #a6e3a1; font-size:9pt;")
        layout.addWidget(self._result_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        btn_apply = QPushButton("Apply Changes")
        btn_apply.setProperty("class", "primary")
        btn_apply.clicked.connect(self._apply_changes)
        btn_row.addWidget(btn_close)
        btn_row.addStretch()
        btn_row.addWidget(btn_apply)
        layout.addLayout(btn_row)

    def _load_values(self) -> None:
        values = self._pragma_mgr.read_all()
        for row, defn in enumerate(PRAGMA_DEFINITIONS):
            name_item = QTableWidgetItem(defn["name"])
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            cat_item = QTableWidgetItem(defn["category"])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsEditable)
            val = str(values.get(defn["name"], ""))
            val_item = QTableWidgetItem(val)
            if not defn.get("writable", True):
                val_item.setFlags(val_item.flags() & ~Qt.ItemIsEditable)
                val_item.setForeground(Qt.gray)
            desc_item = QTableWidgetItem(defn["description"])
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemIsEditable)

            self._table.setItem(row, 0, name_item)
            self._table.setItem(row, 1, cat_item)
            self._table.setItem(row, 2, val_item)
            self._table.setItem(row, 3, desc_item)

    def _apply_changes(self) -> None:
        if self._conn.read_only:
            QMessageBox.warning(self, "Read-Only", "Database is in read-only mode.")
            return
        changed = 0
        for row, defn in enumerate(PRAGMA_DEFINITIONS):
            if not defn.get("writable", True):
                continue
            val = self._table.item(row, 2).text().strip() if self._table.item(row, 2) else ""
            if self._pragma_mgr.write(defn["name"], val):
                changed += 1
        self._result_label.setText(f"✔ Applied {changed} PRAGMA changes.")
        log.info("Applied %d PRAGMA changes.", changed)

    def _run_vacuum(self) -> None:
        try:
            self._pragma_mgr.run_vacuum()
            self._result_label.setText("✔ VACUUM completed.")
        except Exception as exc:
            QMessageBox.critical(self, "VACUUM Error", str(exc))

    def _run_analyze(self) -> None:
        try:
            self._pragma_mgr.run_analyze()
            self._result_label.setText("✔ ANALYZE completed.")
        except Exception as exc:
            QMessageBox.critical(self, "ANALYZE Error", str(exc))

    def _run_integrity(self) -> None:
        try:
            results = self._pragma_mgr.run_integrity_check()
            if results == ["ok"]:
                self._result_label.setText("✔ Integrity check passed.")
            else:
                QMessageBox.warning(self, "Integrity Issues", "\n".join(results))
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
