"""
widgets/find_replace.py — Find & Replace Dialog.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QGroupBox, QMessageBox,
)


class FindReplaceDialog(QDialog):
    """Find & Replace dialog. Emits signals for the data viewer to act on."""

    find_requested = Signal(str, bool, bool)        # text, case_sensitive, regex
    replace_requested = Signal(str, str, bool, bool)  # find, replace, case, regex
    replace_all_requested = Signal(str, str, bool, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find & Replace")
        self.setFixedSize(400, 230)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        grp = QGroupBox("Search")
        g_layout = QVBoxLayout(grp)

        find_row = QHBoxLayout()
        find_row.addWidget(QLabel("Find:"))
        self._txt_find = QLineEdit()
        self._txt_find.setPlaceholderText("Search text…")
        find_row.addWidget(self._txt_find)
        g_layout.addLayout(find_row)

        replace_row = QHBoxLayout()
        replace_row.addWidget(QLabel("Replace:"))
        self._txt_replace = QLineEdit()
        self._txt_replace.setPlaceholderText("Replacement text…")
        replace_row.addWidget(self._txt_replace)
        g_layout.addLayout(replace_row)

        opts_row = QHBoxLayout()
        self._chk_case = QCheckBox("Case sensitive")
        self._chk_regex = QCheckBox("Regex")
        opts_row.addWidget(self._chk_case)
        opts_row.addWidget(self._chk_regex)
        opts_row.addStretch()
        g_layout.addLayout(opts_row)
        layout.addWidget(grp)

        btn_row = QHBoxLayout()
        btn_find = QPushButton("Find Next")
        btn_find.clicked.connect(self._on_find)
        btn_replace = QPushButton("Replace")
        btn_replace.clicked.connect(self._on_replace)
        btn_replace_all = QPushButton("Replace All")
        btn_replace_all.setProperty("class", "primary")
        btn_replace_all.clicked.connect(self._on_replace_all)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_find)
        btn_row.addWidget(btn_replace)
        btn_row.addWidget(btn_replace_all)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _on_find(self) -> None:
        self.find_requested.emit(
            self._txt_find.text(),
            self._chk_case.isChecked(),
            self._chk_regex.isChecked(),
        )

    def _on_replace(self) -> None:
        self.replace_requested.emit(
            self._txt_find.text(),
            self._txt_replace.text(),
            self._chk_case.isChecked(),
            self._chk_regex.isChecked(),
        )

    def _on_replace_all(self) -> None:
        self.replace_all_requested.emit(
            self._txt_find.text(),
            self._txt_replace.text(),
            self._chk_case.isChecked(),
            self._chk_regex.isChecked(),
        )
