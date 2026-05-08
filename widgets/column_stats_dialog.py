"""
widgets/column_stats_dialog.py — Column Statistics Viewer.

Shows MIN, MAX, AVG, COUNT, NULL count, DISTINCT count,
and a value frequency chart for any column.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QWidget,
    QHeaderView, QProgressBar,
)
from PySide6.QtGui import QColor

from app.logger import get_logger
from core.database.connection import DatabaseConnection
from core.database.introspector import SchemaIntrospector

log = get_logger("col_stats")


class ColumnStatsDialog(QDialog):
    """Shows statistics for a selected column in a table."""

    def __init__(self, conn: DatabaseConnection, table: str, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._table = table
        self._intro = SchemaIntrospector(conn.connection)
        self._cols = [c.name for c in self._intro.get_columns(table)]

        self.setWindowTitle(f"Column Statistics — {table}")
        self.setMinimumSize(600, 500)
        self._setup_ui()
        if self._cols:
            self._load_stats(self._cols[0])

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Column selector
        top = QHBoxLayout()
        top.addWidget(QLabel("Column:"))
        self._cmb_col = QComboBox()
        self._cmb_col.addItems(self._cols)
        self._cmb_col.currentTextChanged.connect(self._load_stats)
        top.addWidget(self._cmb_col, 1)
        btn_refresh = QPushButton("↺ Refresh")
        btn_refresh.clicked.connect(lambda: self._load_stats(self._cmb_col.currentText()))
        top.addWidget(btn_refresh)
        layout.addLayout(top)

        # Stats table
        self._stats_tbl = QTableWidget(0, 2)
        self._stats_tbl.setHorizontalHeaderLabels(["Statistic", "Value"])
        self._stats_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._stats_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._stats_tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self._stats_tbl.setAlternatingRowColors(True)
        self._stats_tbl.setMaximumHeight(240)
        layout.addWidget(self._stats_tbl)

        # Top values
        layout.addWidget(QLabel("<b>Top 10 Most Common Values</b>"))
        self._freq_tbl = QTableWidget(0, 3)
        self._freq_tbl.setHorizontalHeaderLabels(["Value", "Count", "Frequency"])
        self._freq_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._freq_tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self._freq_tbl.setAlternatingRowColors(True)
        layout.addWidget(self._freq_tbl)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)

    def _load_stats(self, col_name: str) -> None:
        if not col_name:
            return
        col_q = f'"{col_name}"'
        tbl_q = f'"{self._table}"'

        stats: list[tuple[str, str]] = []
        try:
            total = self._conn.execute(f"SELECT COUNT(*) FROM {tbl_q};").fetchone()[0]
            null_count = self._conn.execute(f"SELECT COUNT(*) FROM {tbl_q} WHERE {col_q} IS NULL;").fetchone()[0]
            not_null = total - null_count
            distinct = self._conn.execute(f"SELECT COUNT(DISTINCT {col_q}) FROM {tbl_q};").fetchone()[0]

            stats.append(("Total Rows", f"{total:,}"))
            stats.append(("Not NULL", f"{not_null:,}"))
            stats.append(("NULL Values", f"{null_count:,}  ({null_count/total*100:.1f}%)" if total else "0"))
            stats.append(("Distinct Values", f"{distinct:,}"))
            stats.append(("Uniqueness", f"{distinct/not_null*100:.1f}%" if not_null else "N/A"))

            # Numeric stats
            try:
                row = self._conn.execute(
                    f"SELECT MIN({col_q}), MAX({col_q}), AVG({col_q}), SUM({col_q}) FROM {tbl_q} WHERE {col_q} IS NOT NULL;"
                ).fetchone()
                if row and row[0] is not None:
                    stats.append(("Min", str(row[0])))
                    stats.append(("Max", str(row[1])))
                    stats.append(("Average", f"{row[2]:.4f}" if isinstance(row[2], float) else str(row[2])))
                    stats.append(("Sum", str(row[3])))
            except Exception:
                pass

            # Min/max length (for text)
            try:
                row2 = self._conn.execute(
                    f"SELECT MIN(LENGTH({col_q})), MAX(LENGTH({col_q})), AVG(LENGTH({col_q})) FROM {tbl_q} WHERE {col_q} IS NOT NULL;"
                ).fetchone()
                if row2 and row2[0] is not None:
                    stats.append(("Min Length", str(row2[0])))
                    stats.append(("Max Length", str(row2[1])))
                    stats.append(("Avg Length", f"{row2[2]:.1f}" if row2[2] else "0"))
            except Exception:
                pass

        except Exception as exc:
            stats.append(("Error", str(exc)))

        self._stats_tbl.setRowCount(len(stats))
        for i, (k, v) in enumerate(stats):
            self._stats_tbl.setItem(i, 0, QTableWidgetItem(k))
            val_item = QTableWidgetItem(v)
            val_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._stats_tbl.setItem(i, 1, val_item)

        # Top values
        try:
            rows = self._conn.execute(
                f"SELECT {col_q}, COUNT(*) as cnt FROM {tbl_q} "
                f"WHERE {col_q} IS NOT NULL GROUP BY {col_q} ORDER BY cnt DESC LIMIT 10;"
            ).fetchall()
            self._freq_tbl.setRowCount(len(rows))
            max_cnt = rows[0][1] if rows else 1
            for i, (val, cnt) in enumerate(rows):
                self._freq_tbl.setItem(i, 0, QTableWidgetItem("" if val is None else str(val)))
                cnt_item = QTableWidgetItem(f"{cnt:,}")
                cnt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._freq_tbl.setItem(i, 1, cnt_item)

                # Frequency bar cell
                pct = int(cnt / max_cnt * 100)
                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setValue(pct)
                bar.setFormat(f"{cnt/total*100:.1f}%" if total else "")
                bar.setTextVisible(True)
                self._freq_tbl.setCellWidget(i, 2, bar)
        except Exception:
            pass
