"""
widgets/query_editor.py — SQL Query Editor with Syntax Highlighting,
Autocomplete, History, Multiple Tabs, and Result Viewer.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer, QStringListModel
from PySide6.QtGui import (
    QKeySequence, QShortcut, QFont, QSyntaxHighlighter,
    QTextCharFormat, QColor, QAction,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget,
    QPushButton, QPlainTextEdit, QTableView, QLabel, QComboBox,
    QCompleter, QToolBar, QMessageBox, QMenu, QFileDialog, QTextEdit,
)

from app.config import (
    QUERY_HISTORY_FILE, SAVED_QUERIES_FILE,
    MAX_QUERY_HISTORY, DARK_ACCENT, DARK_ERROR, DARK_SUCCESS,
    DARK_TEXT_DIM, DARK_BG_SECONDARY, DARK_BG_PANEL,
    DEFAULT_QUERY_TIMEOUT, EDITOR_FONT_FAMILY, EDITOR_FONT_SIZE,
)
from app.logger import get_logger
from core.database.connection import DatabaseConnection
from core.database.executor import QueryResult
from core.models.table_model import TableDataModel
from core.workers.query_worker import QueryWorker

log = get_logger("query_editor")


# ── SQL Syntax Highlighter ────────────────────────────────────────────────────

class SqlHighlighter(QSyntaxHighlighter):
    """Pygments-powered SQL syntax highlighting."""

    SQL_KEYWORDS = {
        "SELECT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "OUTER",
        "ON", "AND", "OR", "NOT", "IN", "IS", "NULL", "AS", "DISTINCT",
        "GROUP", "BY", "ORDER", "HAVING", "LIMIT", "OFFSET", "UNION", "ALL",
        "INSERT", "INTO", "VALUES", "UPDATE", "SET", "DELETE", "CREATE",
        "TABLE", "VIEW", "INDEX", "DROP", "ALTER", "ADD", "COLUMN",
        "PRIMARY", "KEY", "FOREIGN", "REFERENCES", "UNIQUE", "DEFAULT",
        "CONSTRAINT", "CHECK", "AUTOINCREMENT", "INTEGER", "TEXT", "REAL",
        "BLOB", "NUMERIC", "BEGIN", "COMMIT", "ROLLBACK", "TRANSACTION",
        "EXPLAIN", "PRAGMA", "VACUUM", "ANALYZE", "TRIGGER", "WHEN",
        "THEN", "ELSE", "END", "CASE", "IF", "EXISTS", "WITH", "RECURSIVE",
        "ASC", "DESC", "LIKE", "GLOB", "BETWEEN", "CROSS", "NATURAL",
        "USING", "REPLACE", "IGNORE", "ABORT", "FAIL", "REPLACE",
    }

    def __init__(self, document):
        super().__init__(document)
        self._keyword_fmt = QTextCharFormat()
        self._keyword_fmt.setForeground(QColor("#cba6f7"))  # purple
        self._keyword_fmt.setFontWeight(700)

        self._string_fmt = QTextCharFormat()
        self._string_fmt.setForeground(QColor("#a6e3a1"))   # green

        self._number_fmt = QTextCharFormat()
        self._number_fmt.setForeground(QColor("#fab387"))   # orange

        self._comment_fmt = QTextCharFormat()
        self._comment_fmt.setForeground(QColor("#7f849c"))   # dim
        self._comment_fmt.setFontItalic(True)

        self._func_fmt = QTextCharFormat()
        self._func_fmt.setForeground(QColor("#89b4fa"))      # blue

        SQL_FUNCTIONS = {
            "COUNT", "SUM", "AVG", "MAX", "MIN", "COALESCE", "IFNULL",
            "LENGTH", "SUBSTR", "UPPER", "LOWER", "TRIM", "LTRIM", "RTRIM",
            "REPLACE", "INSTR", "PRINTF", "CAST", "TYPEOF", "DATE", "TIME",
            "DATETIME", "STRFTIME", "JULIANDAY", "ABS", "ROUND", "RANDOM",
            "ROWID", "OID", "LAST_INSERT_ROWID", "CHANGES", "TOTAL_CHANGES",
            "NULLIF", "IIF", "HEX", "QUOTE", "GROUP_CONCAT",
        }
        self._keywords = self.SQL_KEYWORDS
        self._functions = SQL_FUNCTIONS

    def highlightBlock(self, text: str) -> None:
        import re
        # Comments
        for m in re.finditer(r"--[^\n]*|/\*.*?\*/", text, re.DOTALL):
            self.setFormat(m.start(), m.end() - m.start(), self._comment_fmt)
            return  # if in comment, skip rest

        # Strings
        for m in re.finditer(r"'[^']*'|\"[^\"]*\"", text):
            self.setFormat(m.start(), m.end() - m.start(), self._string_fmt)

        # Numbers
        for m in re.finditer(r"\b\d+(\.\d+)?\b", text):
            self.setFormat(m.start(), m.end() - m.start(), self._number_fmt)

        # Keywords and functions
        for m in re.finditer(r"\b([A-Za-z_][A-Za-z_0-9]*)\b", text):
            word = m.group(1).upper()
            if word in self._keywords:
                self.setFormat(m.start(), m.end() - m.start(), self._keyword_fmt)
            elif word in self._functions:
                self.setFormat(m.start(), m.end() - m.start(), self._func_fmt)


# ── Line-number area ──────────────────────────────────────────────────────────

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(self._editor._line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor._paint_line_numbers(event)


class SqlEditor(QPlainTextEdit):
    """Enhanced SQL editor with line numbers and autocomplete."""

    execute_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont(EDITOR_FONT_FAMILY, EDITOR_FONT_SIZE)
        font.setFixedPitch(True)
        self.setFont(font)
        self.setTabStopDistance(28)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

        self._highlighter = SqlHighlighter(self.document())
        self._line_number_area = LineNumberArea(self)

        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)

        self._update_line_number_area_width(0)
        self._highlight_current_line()

        # Autocomplete
        self._completer: Optional[QCompleter] = None
        self._setup_completer([])

    def _setup_completer(self, words: list[str]) -> None:
        self._completer = QCompleter(words, self)
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.activated.connect(self._insert_completion)

    def update_completions(self, words: list[str]) -> None:
        sql_kw = [
            "SELECT", "FROM", "WHERE", "JOIN", "ON", "AND", "OR", "NOT", "IN",
            "IS", "NULL", "AS", "GROUP BY", "ORDER BY", "LIMIT", "OFFSET",
            "INSERT INTO", "VALUES", "UPDATE", "SET", "DELETE FROM",
            "CREATE TABLE", "DROP TABLE", "ALTER TABLE", "ADD COLUMN",
            "PRAGMA", "VACUUM", "ANALYZE", "EXPLAIN", "BEGIN", "COMMIT", "ROLLBACK",
        ]
        all_words = sorted(set(sql_kw + words))
        model = QStringListModel(all_words, self._completer)
        self._completer.setModel(model)

    def _insert_completion(self, completion: str) -> None:
        tc = self.textCursor()
        extra = len(completion) - len(self._completer.completionPrefix())
        tc.movePosition(tc.MoveOperation.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)

    def keyPressEvent(self, event) -> None:
        if self._completer and self._completer.popup().isVisible():
            if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape,
                                Qt.Key_Tab, Qt.Key_Backtab):
                event.ignore()
                return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() & Qt.ControlModifier:
            self.execute_requested.emit(self.toPlainText())
            return
        super().keyPressEvent(event)
        self._trigger_autocomplete(event)

    def _trigger_autocomplete(self, event) -> None:
        if not self._completer:
            return
        if event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier):
            return
        tc = self.textCursor()
        tc.select(tc.SelectionType.WordUnderCursor)
        prefix = tc.selectedText()
        if len(prefix) < 2:
            self._completer.popup().hide()
            return
        if prefix != self._completer.completionPrefix():
            self._completer.setCompletionPrefix(prefix)
            self._completer.popup().setCurrentIndex(
                self._completer.completionModel().index(0, 0)
            )
        cr = self.cursorRect()
        cr.setWidth(
            self._completer.popup().sizeHintForColumn(0)
            + self._completer.popup().verticalScrollBar().sizeHint().width()
        )
        self._completer.complete(cr)

    # ── Line numbers ──────────────────────────────────────────────────────────

    def _line_number_area_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_number_area_width(self, _) -> None:
        self.setViewportMargins(self._line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy) -> None:
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        from PySide6.QtCore import QRect
        self._line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self._line_number_area_width(), cr.height())
        )

    def _paint_line_numbers(self, event) -> None:
        from PySide6.QtGui import QPainter
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor("#181825"))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor("#7f849c"))
                painter.drawText(
                    0, top,
                    self._line_number_area.width() - 4,
                    self.fontMetrics().height(),
                    Qt.AlignRight,
                    str(block_number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def _highlight_current_line(self) -> None:
        from PySide6.QtWidgets import QTextEdit
        extra: list[QTextEdit.ExtraSelection] = []
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor("#2a2a3e"))
            sel.format.setProperty(130, True)  # FullWidthSelection
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            extra.append(sel)
        self.setExtraSelections(extra)


# ── Result Table (read-only) ──────────────────────────────────────────────────

class ResultTableModel:
    """Minimal inline model to display query results without DB connection."""

    pass  # We'll use a simple QStandardItemModel inline below


# ── Query Tab ─────────────────────────────────────────────────────────────────

class QueryTab(QWidget):
    """One query editor tab with editor + results panel."""

    status_message = Signal(str)
    query_finished = Signal(float)  # elapsed_ms

    def __init__(self, conn: DatabaseConnection, tab_name: str = "Query", parent=None):
        super().__init__(parent)
        self._conn = conn
        self._tab_name = tab_name
        self._worker: Optional[QueryWorker] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)

        self._btn_run = toolbar.addAction("▶ Run (Ctrl+Enter)")
        self._btn_run.triggered.connect(self._on_run)
        self._btn_run_explain = toolbar.addAction("🔍 Explain")
        self._btn_run_explain.triggered.connect(self._on_run_explain)
        self._btn_cancel = toolbar.addAction("⏹ Cancel")
        self._btn_cancel.triggered.connect(self._on_cancel)
        self._btn_cancel.setEnabled(False)
        toolbar.addSeparator()
        self._btn_format = toolbar.addAction("✨ Format SQL")
        self._btn_format.triggered.connect(self._on_format)
        self._btn_save = toolbar.addAction("💾 Save Query")
        self._btn_save.triggered.connect(self._on_save_query)
        toolbar.addSeparator()
        self._btn_export = toolbar.addAction("📤 Export Results")
        self._btn_export.triggered.connect(self._on_export)
        layout.addWidget(toolbar)

        # Splitter: editor on top, results below
        splitter = QSplitter(Qt.Vertical)

        # Editor area
        editor_container = QWidget()
        ec_layout = QVBoxLayout(editor_container)
        ec_layout.setContentsMargins(0, 0, 0, 0)
        self._editor = SqlEditor()
        self._editor.execute_requested.connect(self._on_run_from_editor)
        self._editor.setPlaceholderText(
            "-- Write your SQL here\n-- Ctrl+Enter to execute\n-- Ctrl+Space for autocomplete\n"
        )
        ec_layout.addWidget(self._editor)
        splitter.addWidget(editor_container)

        # Results area
        results_container = QWidget()
        rc_layout = QVBoxLayout(results_container)
        rc_layout.setContentsMargins(0, 0, 0, 0)
        rc_layout.setSpacing(0)

        # Result tabs (Results / Messages)
        self._result_tabs = QTabWidget()

        # Results table
        self._result_table = QTableView()
        self._result_table.setAlternatingRowColors(True)
        self._result_table.horizontalHeader().setStretchLastSection(True)
        self._result_tabs.addTab(self._result_table, "Results")

        # Messages / errors
        self._messages = QPlainTextEdit()
        self._messages.setReadOnly(True)
        self._messages.setFont(QFont(EDITOR_FONT_FAMILY, 9))
        self._result_tabs.addTab(self._messages, "Messages")

        rc_layout.addWidget(self._result_tabs)

        # Results info bar
        self._result_info = QLabel("Ready")
        self._result_info.setStyleSheet(f"color:{DARK_TEXT_DIM}; font-size:9pt; padding:2px 8px;")
        rc_layout.addWidget(self._result_info)

        splitter.addWidget(results_container)
        splitter.setSizes([300, 200])
        layout.addWidget(splitter)

    # ── Execution ─────────────────────────────────────────────────────────────

    def _on_run(self) -> None:
        self._execute(explain=False)

    def _on_run_explain(self) -> None:
        self._execute(explain=True)

    def _on_run_from_editor(self, sql: str) -> None:
        self._execute(explain=False)

    def _execute(self, explain: bool = False) -> None:
        sql = self._editor.toPlainText().strip()
        if not sql:
            return
        self._add_to_history(sql)
        self._btn_run.setEnabled(False)
        self._btn_cancel.setEnabled(True)
        self._result_info.setText("⏳ Running…")
        self._messages.clear()

        self._worker = QueryWorker(self._conn, sql, explain=explain)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.message.connect(self._on_message)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()

    def _on_result(self, result: QueryResult) -> None:
        from PySide6.QtGui import QStandardItemModel, QStandardItem
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(result.columns)
        for row in result.rows:
            items = [QStandardItem("" if v is None else str(v)) for v in row]
            for item in items:
                item.setEditable(False)
            model.appendRow(items)
        self._result_table.setModel(model)
        self._result_table.resizeColumnsToContents()
        info = f"✔  {result.row_count:,} rows  |  {result.elapsed_ms:.1f} ms"
        if result.rowcount >= 0 and result.row_count == 0:
            info = f"✔  {result.rowcount} rows affected  |  {result.elapsed_ms:.1f} ms"
        self._result_info.setText(info)
        self._result_tabs.setCurrentIndex(0)

    def _on_error(self, msg: str) -> None:
        self._messages.setPlainText(msg)
        self._result_tabs.setCurrentIndex(1)
        self._result_info.setText(f"✘ Error")
        self._btn_run.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        self.status_message.emit(f"Query error: {msg[:80]}")

    def _on_message(self, msg: str) -> None:
        self._messages.appendPlainText(msg)

    def _on_finished(self, elapsed_ms: float) -> None:
        self._btn_run.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        self.query_finished.emit(elapsed_ms)

    # ── Format ────────────────────────────────────────────────────────────────

    def _on_format(self) -> None:
        try:
            import sqlparse
            sql = self._editor.toPlainText()
            formatted = sqlparse.format(
                sql, reindent=True, keyword_case="upper", identifier_case="lower"
            )
            self._editor.setPlainText(formatted)
        except ImportError:
            self.status_message.emit("sqlparse not installed.")

    # ── Save / Export ─────────────────────────────────────────────────────────

    def _on_save_query(self) -> None:
        sql = self._editor.toPlainText().strip()
        if not sql:
            return
        try:
            saved: list = []
            if SAVED_QUERIES_FILE.exists():
                saved = json.loads(SAVED_QUERIES_FILE.read_text("utf-8"))
            saved.append({"sql": sql, "ts": time.time()})
            SAVED_QUERIES_FILE.write_text(json.dumps(saved, indent=2), "utf-8")
            self.status_message.emit("Query saved.")
        except Exception as exc:
            self.status_message.emit(f"Save failed: {exc}")

    def _on_export(self) -> None:
        model = self._result_table.model()
        if not model or model.rowCount() == 0:
            QMessageBox.information(self, "No results", "Run a query first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "", "CSV (*.csv);;Excel (*.xlsx);;JSON (*.json)"
        )
        if not path:
            return
        try:
            rows = []
            headers = [model.headerData(c, Qt.Horizontal) for c in range(model.columnCount())]
            for r in range(model.rowCount()):
                row = [model.data(model.index(r, c)) or "" for c in range(model.columnCount())]
                rows.append(row)
            if path.endswith(".csv"):
                import csv as _csv
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = _csv.writer(f)
                    w.writerow(headers)
                    w.writerows(rows)
            elif path.endswith(".xlsx"):
                import pandas as pd
                pd.DataFrame(rows, columns=headers).to_excel(path, index=False)
            elif path.endswith(".json"):
                import json
                data = [dict(zip(headers, r)) for r in rows]
                Path(path).write_text(json.dumps(data, indent=2, default=str), "utf-8")
            self.status_message.emit(f"Exported to {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    # ── History ───────────────────────────────────────────────────────────────

    def _add_to_history(self, sql: str) -> None:
        try:
            history: list = []
            if QUERY_HISTORY_FILE.exists():
                history = json.loads(QUERY_HISTORY_FILE.read_text("utf-8"))
            history.insert(0, {"sql": sql, "ts": time.time()})
            history = history[:MAX_QUERY_HISTORY]
            QUERY_HISTORY_FILE.write_text(json.dumps(history, indent=2), "utf-8")
        except Exception:
            pass

    # ── Public ────────────────────────────────────────────────────────────────

    def set_sql(self, sql: str) -> None:
        self._editor.setPlainText(sql)

    def update_completions(self, words: list[str]) -> None:
        self._editor.update_completions(words)

    @property
    def tab_name(self) -> str:
        return self._tab_name


# ── Query Editor Container (multi-tab) ───────────────────────────────────────

class QueryEditor(QWidget):
    """Multi-tab query editor container."""

    status_message = Signal(str)
    query_finished = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._conn: Optional[DatabaseConnection] = None
        self._tab_counter = 1
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tab bar with add/close
        header = QHBoxLayout()
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._on_close_tab)
        header.addWidget(self._tabs)

        btn_new = QPushButton("+")
        btn_new.setFixedSize(28, 28)
        btn_new.setToolTip("New query tab")
        btn_new.clicked.connect(self._on_new_tab)
        header.addWidget(btn_new, alignment=Qt.AlignTop)

        layout.addLayout(header)

        # History panel button
        self._btn_history = QPushButton("📜 Query History")
        self._btn_history.setFixedHeight(26)
        self._btn_history.clicked.connect(self._on_show_history)
        layout.addWidget(self._btn_history)

    def set_connection(self, conn: DatabaseConnection) -> None:
        self._conn = conn
        self._on_new_tab()

    def open_query(self, sql: str) -> None:
        if not self._conn:
            return
        tab = self._add_tab()
        tab.set_sql(sql)

    def _add_tab(self) -> QueryTab:
        name = f"Query {self._tab_counter}"
        self._tab_counter += 1
        tab = QueryTab(self._conn, name, parent=self)
        tab.status_message.connect(self.status_message)
        tab.query_finished.connect(self.query_finished)
        self._tabs.addTab(tab, name)
        self._tabs.setCurrentWidget(tab)
        # Update completions
        if self._conn:
            try:
                from core.database.introspector import SchemaIntrospector
                intro = SchemaIntrospector(self._conn.connection)
                words = intro.get_tables() + intro.get_views()
                tab.update_completions(words)
            except Exception:
                pass
        return tab

    def _on_new_tab(self) -> None:
        if self._conn:
            self._add_tab()

    def _on_close_tab(self, index: int) -> None:
        if self._tabs.count() > 1:
            self._tabs.removeTab(index)

    def _on_show_history(self) -> None:
        try:
            if not QUERY_HISTORY_FILE.exists():
                return
            history = json.loads(QUERY_HISTORY_FILE.read_text("utf-8"))
            from PySide6.QtWidgets import QDialog, QListWidget, QListWidgetItem, QDialogButtonBox
            dlg = QDialog(self)
            dlg.setWindowTitle("Query History")
            dlg.resize(700, 500)
            v = QVBoxLayout(dlg)
            lst = QListWidget()
            for entry in history[:100]:
                item = QListWidgetItem(entry["sql"][:120].replace("\n", " "))
                item.setData(Qt.UserRole, entry["sql"])
                lst.addItem(item)
            v.addWidget(lst)
            btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            v.addWidget(btns)
            lst.doubleClicked.connect(dlg.accept)
            if dlg.exec() == QDialog.Accepted and lst.currentItem():
                sql = lst.currentItem().data(Qt.UserRole)
                self.open_query(sql)
        except Exception as exc:
            log.warning("History load failed: %s", exc)
