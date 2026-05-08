"""
core/models/schema_model.py — Qt Tree Model for Schema Explorer.

Provides a QStandardItemModel tree with:
  Tables → columns
  Views
  Indexes
  Triggers
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel, QIcon, QFont, QColor

from app.logger import get_logger
from core.database.connection import DatabaseConnection
from core.database.introspector import SchemaIntrospector

log = get_logger("schema_model")

# Item data roles
ROLE_ITEM_TYPE = Qt.UserRole + 1   # 'table'|'view'|'index'|'trigger'|'column'|'category'
ROLE_ITEM_NAME = Qt.UserRole + 2   # actual DB object name
ROLE_PARENT_TABLE = Qt.UserRole + 3  # parent table name for columns


def _make_item(text: str, bold: bool = False, color: Optional[str] = None) -> QStandardItem:
    item = QStandardItem(text)
    item.setEditable(False)
    if bold:
        f = item.font()
        f.setBold(True)
        item.setFont(f)
    if color:
        item.setForeground(QColor(color))
    return item


class SchemaTreeModel(QStandardItemModel):
    """
    Tree model backed by a DatabaseConnection.
    Call populate() to load all schema objects.
    """

    # Category colours (dark theme)
    CAT_COLORS = {
        "Tables":   "#89b4fa",
        "Views":    "#a6e3a1",
        "Indexes":  "#f9e2af",
        "Triggers": "#cba6f7",
    }

    def __init__(self, conn: DatabaseConnection, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._introspector = SchemaIntrospector(conn.connection)
        self.setHorizontalHeaderLabels(["Schema"])

    def populate(self) -> None:
        """Load full schema tree. Call from main thread after worker emits."""
        self.clear()
        self.setHorizontalHeaderLabels(["Schema"])
        root = self.invisibleRootItem()

        # Tables
        tables = self._introspector.get_tables()
        cat_tables = self._make_category("Tables", f"Tables ({len(tables)})")
        for name in tables:
            cols = self._introspector.get_columns(name)
            count = self._introspector.get_row_count(name)
            tbl_item = QStandardItem(f"{name}  ({count:,} rows)")
            tbl_item.setEditable(False)
            tbl_item.setData("table", ROLE_ITEM_TYPE)
            tbl_item.setData(name, ROLE_ITEM_NAME)
            tbl_item.setForeground(QColor("#cdd6f4"))
            for col in cols:
                suffix = ""
                if col.pk:
                    suffix += " 🔑"
                if col.notnull:
                    suffix += " !"
                col_item = QStandardItem(f"  {col.name}  [{col.type}]{suffix}")
                col_item.setEditable(False)
                col_item.setData("column", ROLE_ITEM_TYPE)
                col_item.setData(col.name, ROLE_ITEM_NAME)
                col_item.setData(name, ROLE_PARENT_TABLE)
                col_item.setForeground(QColor("#7f849c"))
                f = col_item.font()
                f.setPointSize(9)
                col_item.setFont(f)
                tbl_item.appendRow(col_item)
            cat_tables.appendRow(tbl_item)
        root.appendRow(cat_tables)

        # Views
        views = self._introspector.get_views()
        cat_views = self._make_category("Views", f"Views ({len(views)})")
        for name in views:
            item = QStandardItem(name)
            item.setEditable(False)
            item.setData("view", ROLE_ITEM_TYPE)
            item.setData(name, ROLE_ITEM_NAME)
            item.setForeground(QColor("#a6e3a1"))
            cat_views.appendRow(item)
        root.appendRow(cat_views)

        # Indexes
        indexes = self._introspector.get_indexes()
        cat_idx = self._make_category("Indexes", f"Indexes ({len(indexes)})")
        for name in indexes:
            item = QStandardItem(name)
            item.setEditable(False)
            item.setData("index", ROLE_ITEM_TYPE)
            item.setData(name, ROLE_ITEM_NAME)
            item.setForeground(QColor("#f9e2af"))
            cat_idx.appendRow(item)
        root.appendRow(cat_idx)

        # Triggers
        triggers = self._introspector.get_triggers()
        cat_trg = self._make_category("Triggers", f"Triggers ({len(triggers)})")
        for name in triggers:
            item = QStandardItem(name)
            item.setEditable(False)
            item.setData("trigger", ROLE_ITEM_TYPE)
            item.setData(name, ROLE_ITEM_NAME)
            item.setForeground(QColor("#cba6f7"))
            cat_trg.appendRow(item)
        root.appendRow(cat_trg)

    def _make_category(self, key: str, label: str) -> QStandardItem:
        item = QStandardItem(label)
        item.setEditable(False)
        item.setData("category", ROLE_ITEM_TYPE)
        item.setData(key, ROLE_ITEM_NAME)
        color = self.CAT_COLORS.get(key, "#cdd6f4")
        item.setForeground(QColor(color))
        f = item.font()
        f.setBold(True)
        item.setFont(f)
        return item
