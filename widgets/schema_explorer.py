"""
widgets/schema_explorer.py — Left-panel Schema Explorer.

Shows all database objects in a searchable, expandable tree.
Right-click context menus for table operations.
"""
from __future__ import annotations

from typing import Optional, Callable

from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QTreeView, QLabel, QPushButton, QMenu, QFrame,
    QSizePolicy,
)

from app.config import DARK_ACCENT, DARK_TEXT_DIM
from app.logger import get_logger
from core.database.connection import DatabaseConnection
from core.models.schema_model import SchemaTreeModel, ROLE_ITEM_TYPE, ROLE_ITEM_NAME, ROLE_PARENT_TABLE

log = get_logger("schema_explorer")


class SchemaExplorer(QWidget):
    """
    Left-panel dockable schema explorer.

    Signals
    -------
    table_activated(str)     — user double-clicked a table/view
    query_requested(str)     — user wants to open a quick SELECT query
    refresh_requested()      — user hit the Refresh button
    drop_requested(str,str)  — (type, name) drop object requested
    """

    table_activated = Signal(str)
    query_requested = Signal(str)
    refresh_requested = Signal()
    drop_requested = Signal(str, str)
    rename_requested = Signal(str, str)  # (type, name)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._conn: Optional[DatabaseConnection] = None
        self._tree_model: Optional[SchemaTreeModel] = None
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setRecursiveFilteringEnabled(True)
        self._setup_ui()

    # ── UI Setup ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(40)
        header.setStyleSheet(f"background: #181825; border-bottom: 1px solid #313244;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 0, 8, 0)
        title = QLabel("Schema Explorer")
        title.setStyleSheet(f"font-weight:700; color:{DARK_ACCENT}; font-size:10pt;")
        h_layout.addWidget(title)
        h_layout.addStretch()
        self._btn_refresh = QPushButton("↺")
        self._btn_refresh.setFixedSize(26, 26)
        self._btn_refresh.setToolTip("Refresh schema")
        self._btn_refresh.clicked.connect(self._on_refresh)
        h_layout.addWidget(self._btn_refresh)
        layout.addWidget(header)

        # Search bar
        search_bar = QWidget()
        search_bar.setStyleSheet("background: #181825; padding: 4px 6px;")
        sb_layout = QHBoxLayout(search_bar)
        sb_layout.setContentsMargins(6, 4, 6, 4)
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Search tables, columns…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search_changed)
        sb_layout.addWidget(self._search)
        layout.addWidget(search_bar)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Plain)
        sep.setStyleSheet("color: #313244;")
        layout.addWidget(sep)

        # Tree view
        self._tree = QTreeView()
        self._tree.setModel(self._proxy)
        self._tree.setHeaderHidden(True)
        self._tree.setAnimated(True)
        self._tree.setAlternatingRowColors(True)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.doubleClicked.connect(self._on_double_click)
        self._tree.setIndentation(16)
        self._tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._tree)

        # Status bar at bottom of explorer
        self._status = QLabel("")
        self._status.setStyleSheet(f"color:{DARK_TEXT_DIM}; font-size:8pt; padding:2px 8px;")
        self._status.setAlignment(Qt.AlignLeft)
        layout.addWidget(self._status)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_connection(self, conn: DatabaseConnection) -> None:
        self._conn = conn
        self.reload()

    def reload(self) -> None:
        if not self._conn:
            return
        self._tree_model = SchemaTreeModel(self._conn)
        self._tree_model.populate()
        self._proxy.setSourceModel(self._tree_model)
        self._tree.expandAll()
        self._update_status()

    def clear(self) -> None:
        self._conn = None
        self._tree_model = None
        self._proxy.setSourceModel(None)
        self._status.setText("")

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_refresh(self) -> None:
        self.reload()
        self.refresh_requested.emit()

    def _on_search_changed(self, text: str) -> None:
        self._proxy.setFilterFixedString(text)
        if text:
            self._tree.expandAll()
        else:
            # Collapse only non-category items
            self._tree.collapseAll()
            for i in range(self._proxy.rowCount()):
                self._tree.expand(self._proxy.index(i, 0))

    def _on_double_click(self, proxy_index) -> None:
        src_index = self._proxy.mapToSource(proxy_index)
        item = self._tree_model.itemFromIndex(src_index)
        if not item:
            return
        item_type = item.data(ROLE_ITEM_TYPE)
        item_name = item.data(ROLE_ITEM_NAME)
        if item_type in ("table", "view"):
            self.table_activated.emit(item_name)

    def _on_context_menu(self, pos) -> None:
        proxy_index = self._tree.indexAt(pos)
        if not proxy_index.isValid() or not self._tree_model:
            return
        src_index = self._proxy.mapToSource(proxy_index)
        item = self._tree_model.itemFromIndex(src_index)
        if not item:
            return

        item_type = item.data(ROLE_ITEM_TYPE)
        item_name = item.data(ROLE_ITEM_NAME)
        if not item_type or item_type == "category":
            return

        menu = QMenu(self)

        if item_type in ("table", "view"):
            act_open = QAction("📂  Open Data", self)
            act_open.triggered.connect(lambda: self.table_activated.emit(item_name))
            menu.addAction(act_open)

            act_query = QAction("📝  Open in Query Editor", self)
            act_query.triggered.connect(
                lambda: self.query_requested.emit(f"SELECT * FROM \"{item_name}\" LIMIT 100;")
            )
            menu.addAction(act_query)

            menu.addSeparator()

            if item_type == "table" and self._conn and not self._conn.read_only:
                act_rename = QAction("✏️  Rename", self)
                act_rename.triggered.connect(lambda: self.rename_requested.emit(item_type, item_name))
                menu.addAction(act_rename)

                act_drop = QAction("🗑️  Drop", self)
                act_drop.triggered.connect(lambda: self.drop_requested.emit(item_type, item_name))
                menu.addAction(act_drop)

        elif item_type in ("index", "trigger"):
            if self._conn and not self._conn.read_only:
                act_drop = QAction("🗑️  Drop", self)
                act_drop.triggered.connect(lambda: self.drop_requested.emit(item_type, item_name))
                menu.addAction(act_drop)

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _update_status(self) -> None:
        if not self._tree_model:
            return
        # Count items
        try:
            root = self._tree_model.invisibleRootItem()
            tables_count = root.child(0).rowCount() if root.rowCount() > 0 else 0
            views_count = root.child(1).rowCount() if root.rowCount() > 1 else 0
            self._status.setText(f"{tables_count} tables  |  {views_count} views")
        except Exception:
            pass
