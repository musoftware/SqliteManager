"""
widgets/erd_viewer.py — Entity-Relationship Diagram Viewer.

Renders tables as boxes with FK relationships as connecting lines.
Supports zoom, pan, and click-to-select.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QRect, QPoint, QRectF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QFontMetrics,
    QMouseEvent, QWheelEvent, QPainterPath,
)
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea

from app.logger import get_logger
from core.database.connection import DatabaseConnection
from core.database.introspector import SchemaIntrospector, TableInfo

log = get_logger("erd")

# Visual constants
TABLE_W = 200
TABLE_HEADER_H = 30
TABLE_ROW_H = 20
TABLE_PADDING = 8
TABLE_MARGIN = 60

COL_HEADER = QColor("#1e1e2e")
COL_HEADER_TEXT = QColor("#cba6f7")
COL_BG_ODD = QColor("#242438")
COL_BG_EVEN = QColor("#1e1e2e")
COL_TEXT = QColor("#cdd6f4")
COL_PK_TEXT = QColor("#f9e2af")
COL_BORDER = QColor("#313244")
FK_LINE_COLOR = QColor("#89b4fa")
SELECTED_BORDER = QColor("#cba6f7")


class TableBox:
    """Visual representation of one table in the ERD."""

    def __init__(self, info: TableInfo, x: int, y: int):
        self.info = info
        self.x = x
        self.y = y
        self.width = TABLE_W
        self.height = TABLE_HEADER_H + TABLE_ROW_H * len(info.columns)
        self.selected = False

    @property
    def rect(self) -> QRect:
        return QRect(self.x, self.y, self.width, self.height)

    def col_center_y(self, col_name: str) -> int:
        for i, col in enumerate(self.info.columns):
            if col.name == col_name:
                return self.y + TABLE_HEADER_H + i * TABLE_ROW_H + TABLE_ROW_H // 2
        return self.y + self.height // 2

    def right_center(self, col_name: str) -> QPoint:
        return QPoint(self.x + self.width, self.col_center_y(col_name))

    def left_center(self, col_name: str) -> QPoint:
        return QPoint(self.x, self.col_center_y(col_name))


class ErdCanvas(QWidget):
    """Custom canvas that paints the ERD."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tables: list[TableBox] = []
        self._selected: Optional[TableBox] = None
        self._drag_start: Optional[QPoint] = None
        self._drag_box: Optional[TableBox] = None
        self._scale = 1.0
        self._offset = QPoint(20, 20)
        self.setMouseTracking(True)
        self.setMinimumSize(800, 600)

    def set_data(self, tables: list[TableBox]) -> None:
        self._tables = tables
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self._offset)
        painter.scale(self._scale, self._scale)

        # Background
        painter.fillRect(painter.window(), QColor("#181825"))

        # Draw FK connections first (under boxes)
        self._draw_fk_lines(painter)

        # Draw table boxes
        for box in self._tables:
            self._draw_table(painter, box)

        painter.end()

    def _draw_table(self, painter: QPainter, box: TableBox) -> None:
        r = box.rect
        # Shadow
        shadow = r.adjusted(4, 4, 4, 4)
        painter.fillRect(shadow, QColor(0, 0, 0, 80))

        # Header
        header_rect = QRect(r.x(), r.y(), r.width(), TABLE_HEADER_H)
        painter.fillRect(header_rect, COL_HEADER)
        pen = QPen(SELECTED_BORDER if box.selected else COL_BORDER, 2 if box.selected else 1)
        painter.setPen(pen)
        painter.drawRect(r)

        painter.setPen(COL_HEADER_TEXT)
        font = QFont("Segoe UI", 9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(header_rect.adjusted(TABLE_PADDING, 0, -TABLE_PADDING, 0),
                         Qt.AlignVCenter | Qt.AlignLeft, box.info.name)

        # Columns
        painter.setFont(QFont("Consolas", 8))
        for i, col in enumerate(box.info.columns):
            row_rect = QRect(r.x(), r.y() + TABLE_HEADER_H + i * TABLE_ROW_H,
                             r.width(), TABLE_ROW_H)
            bg = COL_BG_ODD if i % 2 else COL_BG_EVEN
            painter.fillRect(row_rect, bg)
            painter.setPen(COL_BORDER)
            painter.drawLine(row_rect.bottomLeft(), row_rect.bottomRight())

            # PK indicator
            if col.pk:
                painter.setPen(COL_PK_TEXT)
                painter.drawText(row_rect.adjusted(4, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft, "🔑 " + col.name)
            else:
                painter.setPen(COL_TEXT)
                painter.drawText(row_rect.adjusted(14, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft, col.name)

            # Type on right
            painter.setPen(QColor("#7f849c"))
            painter.drawText(row_rect.adjusted(4, 0, -4, 0), Qt.AlignVCenter | Qt.AlignRight,
                             col.type[:12])

    def _draw_fk_lines(self, painter: QPainter) -> None:
        painter.setPen(QPen(FK_LINE_COLOR, 1.5, Qt.DashLine))
        box_map = {b.info.name: b for b in self._tables}
        for box in self._tables:
            for fk in box.info.foreign_keys:
                target = box_map.get(fk.table)
                if not target:
                    continue
                p1 = box.right_center(fk.from_col)
                p2 = target.left_center(fk.to_col)
                # Bezier curve
                path = QPainterPath()
                path.moveTo(p1.x(), p1.y())
                ctrl_x = (p1.x() + p2.x()) / 2
                path.cubicTo(ctrl_x, p1.y(), ctrl_x, p2.y(), p2.x(), p2.y())
                painter.drawPath(path)
                # Arrow
                painter.setBrush(FK_LINE_COLOR)
                painter.drawEllipse(p2.x() - 4, p2.y() - 4, 8, 8)
                painter.setBrush(Qt.NoBrush)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            world = self._screen_to_world(event.position().toPoint())
            for box in self._tables:
                if box.rect.contains(world):
                    self._drag_box = box
                    self._drag_start = world - QPoint(box.x, box.y)
                    box.selected = True
                    self._selected = box
                else:
                    box.selected = False
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_box and self._drag_start:
            world = self._screen_to_world(event.position().toPoint())
            new_pos = world - self._drag_start
            self._drag_box.x = max(0, new_pos.x())
            self._drag_box.y = max(0, new_pos.y())
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_box = None
        self._drag_start = None

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9
        self._scale = max(0.2, min(3.0, self._scale * factor))
        self.update()

    def _screen_to_world(self, pt: QPoint) -> QPoint:
        return QPoint(
            int((pt.x() - self._offset.x()) / self._scale),
            int((pt.y() - self._offset.y()) / self._scale),
        )

    def zoom_reset(self) -> None:
        self._scale = 1.0
        self._offset = QPoint(20, 20)
        self.update()

    def zoom_in(self) -> None:
        self._scale = min(3.0, self._scale * 1.2)
        self.update()

    def zoom_out(self) -> None:
        self._scale = max(0.2, self._scale / 1.2)
        self.update()


class ErdViewer(QWidget):
    """ERD viewer widget — wraps the canvas with controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._conn: Optional[DatabaseConnection] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()
        btn_zoom_in = QPushButton("🔍+")
        btn_zoom_in.setFixedWidth(40)
        btn_zoom_in.clicked.connect(lambda: self._canvas.zoom_in())
        btn_zoom_out = QPushButton("🔍-")
        btn_zoom_out.setFixedWidth(40)
        btn_zoom_out.clicked.connect(lambda: self._canvas.zoom_out())
        btn_reset = QPushButton("Reset View")
        btn_reset.clicked.connect(lambda: self._canvas.zoom_reset())
        btn_refresh = QPushButton("↺ Refresh")
        btn_refresh.clicked.connect(self.reload)
        toolbar.addWidget(btn_zoom_in)
        toolbar.addWidget(btn_zoom_out)
        toolbar.addWidget(btn_reset)
        toolbar.addStretch()
        toolbar.addWidget(btn_refresh)
        layout.addLayout(toolbar)

        self._canvas = ErdCanvas()
        scroll = QScrollArea()
        scroll.setWidget(self._canvas)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

    def set_connection(self, conn: DatabaseConnection) -> None:
        self._conn = conn
        self.reload()

    def reload(self) -> None:
        if not self._conn:
            return
        try:
            intro = SchemaIntrospector(self._conn.connection)
            tables = intro.get_tables()
            boxes: list[TableBox] = []
            cols_per_row = 4
            for i, tname in enumerate(tables):
                info = intro.get_table_info(tname)
                col = i % cols_per_row
                row = i // cols_per_row
                x = col * (TABLE_W + TABLE_MARGIN) + 20
                y = row * (TABLE_HEADER_H + TABLE_ROW_H * max(1, len(info.columns)) + TABLE_MARGIN) + 20
                boxes.append(TableBox(info, x, y))
            self._canvas.set_data(boxes)
            # Resize canvas to content
            if boxes:
                max_x = max(b.x + b.width for b in boxes) + TABLE_MARGIN
                max_y = max(b.y + b.height for b in boxes) + TABLE_MARGIN
                self._canvas.setMinimumSize(max_x, max_y)
        except Exception as exc:
            log.error("ERD load failed: %s", exc)
