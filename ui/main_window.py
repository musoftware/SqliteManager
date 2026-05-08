"""
ui/main_window.py — Main Application Window.

Wires all components together: schema explorer, data viewer,
query editor, ERD viewer, import/export, menus, and toolbars.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QAction, QKeySequence, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QDockWidget, QSplitter, QFileDialog, QMessageBox,
    QInputDialog, QLabel, QToolBar, QMenu, QDialog, QPushButton,
    QSizePolicy,
)

from app.config import (
    APP_NAME, APP_AUTHOR, APP_VERSION,
    SETTINGS_WINDOW_GEOM, SETTINGS_WINDOW_STATE,
    SETTINGS_AUTOSAVE, SETTINGS_AUTOBACKUP, SETTINGS_BACKUP_INTERVAL,
    DARK_ACCENT, DARK_BG_SECONDARY,
)
from app.logger import get_logger
from core.database.connection import DatabaseConnection, connection_manager
from core.workers.query_worker import SchemaLoadWorker
from services.backup_service import BackupService
from ui.theme_manager import theme_manager, THEME_DARK, THEME_LIGHT
from widgets.schema_explorer import SchemaExplorer
from widgets.data_viewer import DataViewer
from widgets.query_editor import QueryEditor
from widgets.status_bar import StatusBar
from widgets.erd_viewer import ErdViewer

log = get_logger("main_window")


class DatabaseTab(QWidget):
    """
    One tab per open database.
    Contains: Data Viewer | Query Editor | ERD Viewer sub-tabs.
    """

    def __init__(self, conn: DatabaseConnection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._inner_tabs = QTabWidget()
        self._inner_tabs.setTabPosition(QTabWidget.South)

        # Data Viewer tab
        self._data_viewer = DataViewer()
        self._inner_tabs.addTab(self._data_viewer, "📊 Data")

        # Query Editor tab
        self._query_editor = QueryEditor()
        self._query_editor.set_connection(self.conn)
        self._inner_tabs.addTab(self._query_editor, "📝 Query")

        # ERD tab
        self._erd = ErdViewer()
        self._erd.set_connection(self.conn)
        self._inner_tabs.addTab(self._erd, "🗺 ERD")

        layout.addWidget(self._inner_tabs)

    def load_table(self, table_name: str) -> None:
        self._data_viewer.load_table(self.conn, table_name)
        self._inner_tabs.setCurrentIndex(0)

    def open_query(self, sql: str) -> None:
        self._query_editor.open_query(sql)
        self._inner_tabs.setCurrentIndex(1)

    @property
    def data_viewer(self) -> DataViewer:
        return self._data_viewer

    @property
    def query_editor(self) -> QueryEditor:
        return self._query_editor

    @property
    def erd_viewer(self) -> ErdViewer:
        return self._erd


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self):
        super().__init__()
        self._settings = QSettings(APP_AUTHOR, APP_NAME)
        self._backup_service = BackupService(self)
        self._backup_service.backup_created.connect(
            lambda p: self._status_bar.show_success(f"Backup: {Path(p).name}")
        )
        self._schema_worker: Optional[SchemaLoadWorker] = None

        self._setup_window()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_dock()
        self._setup_central()
        self._setup_status_bar()
        self._restore_state()
        self._update_recent_menu()

        # Apply theme
        theme_manager.apply_saved()

        # Auto-connect to last DB
        QTimer.singleShot(200, self._try_reopen_last)

    # ── Window Setup ──────────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1200, 700)
        self.resize(1440, 860)

    def _setup_status_bar(self) -> None:
        self._status_bar = StatusBar(self)
        self.setStatusBar(self._status_bar)

    # ── Menu Bar ──────────────────────────────────────────────────────────────

    def _setup_menu(self) -> None:
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("&File")
        self._act_open = file_menu.addAction("📂 Open Database…", self._on_open_db, QKeySequence.Open)
        self._act_new = file_menu.addAction("✨ New Database…", self._on_new_db, "Ctrl+N")
        file_menu.addSeparator()
        self._recent_menu = file_menu.addMenu("🕐 Recent Databases")
        file_menu.addSeparator()
        self._act_close_tab = file_menu.addAction("✖ Close Tab", self._on_close_tab, "Ctrl+W")
        file_menu.addSeparator()
        file_menu.addAction("🚪 Exit", self.close, "Ctrl+Q")

        # Edit
        edit_menu = mb.addMenu("&Edit")
        edit_menu.addAction("🔍 Find & Replace…", self._on_find_replace, "Ctrl+H")
        edit_menu.addSeparator()
        edit_menu.addAction("↩ Undo", self._on_undo, QKeySequence.Undo)
        edit_menu.addAction("↪ Redo", self._on_redo, QKeySequence.Redo)

        # View
        view_menu = mb.addMenu("&View")
        self._act_theme = view_menu.addAction("🌙 Toggle Dark/Light Theme", self._on_toggle_theme, "Ctrl+T")
        view_menu.addSeparator()
        view_menu.addAction("↺ Refresh Schema", self._on_refresh_schema, "F5")
        view_menu.addAction("🗺 ERD Viewer", self._on_show_erd)

        # Data
        data_menu = mb.addMenu("&Data")
        data_menu.addAction("📥 Import Data…", self._on_import, "Ctrl+I")
        data_menu.addAction("📤 Export Data…", self._on_export, "Ctrl+E")
        data_menu.addSeparator()
        data_menu.addAction("🎲 Generate Fake Data…", self._on_fake_data)
        data_menu.addAction("💾 Backup Now", self._on_backup)

        # Tools
        tools_menu = mb.addMenu("&Tools")
        tools_menu.addAction("⚙ PRAGMA Editor…", self._on_pragma_editor)
        tools_menu.addAction("🗜 VACUUM Database", self._on_vacuum)
        tools_menu.addAction("📊 ANALYZE Database", self._on_analyze)
        tools_menu.addSeparator()
        tools_menu.addAction("📋 Database Statistics", self._on_db_stats)
        tools_menu.addAction("📈 Column Statistics…", self._on_column_stats)
        tools_menu.addAction("⚡ Mass Update…", self._on_mass_update)
        tools_menu.addSeparator()
        self._act_autobackup = tools_menu.addAction("🔄 Auto-Backup: OFF")
        self._act_autobackup.setCheckable(True)
        self._act_autobackup.toggled.connect(self._on_autobackup_toggle)

        # Schema
        schema_menu = mb.addMenu("&Schema")
        schema_menu.addAction("➕ Create Table…", self._on_create_table, "Ctrl+Shift+T")
        schema_menu.addAction("📋 Table Structure…", self._on_table_structure)
        schema_menu.addSeparator()
        schema_menu.addAction("↺ Refresh Schema", self._on_refresh_schema, "F5")

        # Help
        help_menu = mb.addMenu("&Help")
        help_menu.addAction("📖 About SQLite Manager", self._on_about)
        help_menu.addAction("⌨ Keyboard Shortcuts", self._on_shortcuts)
        help_menu.addSeparator()
        help_menu.addAction("🎮 Open Demo Database", self._on_open_demo)
        help_menu.addSeparator()
        help_menu.addAction("🔄 Check for Updates…", self._on_check_updates)

    def _setup_toolbar(self) -> None:
        tb = QToolBar("Main Toolbar")
        tb.setObjectName("main_toolbar")
        tb.setMovable(False)
        self.addToolBar(tb)

        tb.addAction("📂 Open", self._on_open_db)
        tb.addAction("✨ New", self._on_new_db)
        tb.addSeparator()
        tb.addAction("📥 Import", self._on_import)
        tb.addAction("📤 Export", self._on_export)
        tb.addSeparator()
        tb.addAction("💾 Backup", self._on_backup)
        tb.addAction("⚙ PRAGMA", self._on_pragma_editor)
        tb.addSeparator()
        tb.addAction("🗺 ERD", self._on_show_erd)
        tb.addSeparator()
        tb.addAction("↺ Refresh", self._on_refresh_schema)

    def _setup_dock(self) -> None:
        self._explorer = SchemaExplorer()
        self._explorer.table_activated.connect(self._on_table_activated)
        self._explorer.query_requested.connect(self._on_query_requested)
        self._explorer.drop_requested.connect(self._on_drop_object)
        self._explorer.rename_requested.connect(self._on_rename_object)
        self._explorer.refresh_requested.connect(self._on_refresh_schema)

        dock = QDockWidget("Schema Explorer", self)
        dock.setObjectName("schema_dock")
        dock.setWidget(self._explorer)
        dock.setMinimumWidth(220)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self._schema_dock = dock

    def _setup_central(self) -> None:
        self._db_tabs = QTabWidget()
        self._db_tabs.setTabsClosable(True)
        self._db_tabs.setMovable(True)
        self._db_tabs.tabCloseRequested.connect(self._on_close_db_tab)
        self._db_tabs.currentChanged.connect(self._on_active_tab_changed)

        # Welcome screen
        welcome = self._build_welcome()
        self._db_tabs.addTab(welcome, "Welcome")
        from PySide6.QtWidgets import QTabBar
        self._db_tabs.tabBar().setTabButton(0, QTabBar.ButtonPosition.RightSide, None)

        self.setCentralWidget(self._db_tabs)

    def _build_welcome(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)

        title = QLabel(f"<h1 style='color:#cba6f7'>{APP_NAME}</h1>")
        title.setAlignment(Qt.AlignCenter)
        sub = QLabel("<p style='color:#7f849c'>Modern SQLite Database Manager</p>")
        sub.setAlignment(Qt.AlignCenter)

        btn_open = QPushButton("📂  Open Database…")
        btn_open.setFixedWidth(240)
        btn_open.setFixedHeight(42)
        btn_open.setProperty("class", "primary")
        btn_open.clicked.connect(self._on_open_db)

        btn_new = QPushButton("✨  Create New Database…")
        btn_new.setFixedWidth(240)
        btn_new.setFixedHeight(42)
        btn_new.clicked.connect(self._on_new_db)

        btn_demo = QPushButton("🎮  Open Demo Database")
        btn_demo.setFixedWidth(240)
        btn_demo.setFixedHeight(42)
        btn_demo.clicked.connect(self._on_open_demo)

        version_lbl = QLabel(f"<small style='color:#7f849c'>v{APP_VERSION}</small>")
        version_lbl.setAlignment(Qt.AlignCenter)

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addSpacing(20)
        layout.addWidget(btn_open, alignment=Qt.AlignCenter)
        layout.addWidget(btn_new, alignment=Qt.AlignCenter)
        layout.addWidget(btn_demo, alignment=Qt.AlignCenter)
        layout.addStretch()
        layout.addWidget(version_lbl)
        return w

    # ── DB open/close ─────────────────────────────────────────────────────────

    def _on_open_db(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open SQLite Database", "",
            "SQLite Databases (*.db *.sqlite *.sqlite3 *.db3);;All Files (*.*)"
        )
        if path:
            self._open_database(path)

    def _on_new_db(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Create New Database", "",
            "SQLite Database (*.db);;All Files (*.*)"
        )
        if path:
            if not path.endswith(".db"):
                path += ".db"
            # Touch the file
            Path(path).touch()
            self._open_database(path)

    def _open_database(self, path: str, read_only: bool = False) -> None:
        path = str(Path(path).resolve())
        # Check if already open
        for i in range(self._db_tabs.count()):
            tab = self._db_tabs.widget(i)
            if isinstance(tab, DatabaseTab) and tab.conn.path == path:
                self._db_tabs.setCurrentIndex(i)
                return
        try:
            conn = connection_manager.open(path, read_only=read_only)
        except Exception as exc:
            QMessageBox.critical(self, "Connection Error", str(exc))
            return

        tab = DatabaseTab(conn, self)
        tab.data_viewer.status_message.connect(self._status_bar.show_message)
        tab.data_viewer.row_count_changed.connect(self._status_bar.set_row_count)
        tab.query_editor.status_message.connect(self._status_bar.show_message)
        tab.query_editor.query_finished.connect(self._status_bar.set_query_time)

        tab_name = Path(path).name
        idx = self._db_tabs.addTab(tab, f"{'🔒 ' if read_only else ''}📦 {tab_name}")
        self._db_tabs.setCurrentIndex(idx)

        self._explorer.set_connection(conn)
        self._backup_service.set_database(path)
        self._status_bar.set_connected(tab_name)
        self._update_recent_menu()
        log.info("Opened DB in tab: %s", path)

    def _on_close_tab(self) -> None:
        self._on_close_db_tab(self._db_tabs.currentIndex())

    def _on_close_db_tab(self, index: int) -> None:
        tab = self._db_tabs.widget(index)
        if isinstance(tab, DatabaseTab):
            connection_manager.close(tab.conn.path)
            self._db_tabs.removeTab(index)
            if self._db_tabs.count() == 0 or (
                self._db_tabs.count() == 1 and not isinstance(self._db_tabs.widget(0), DatabaseTab)
            ):
                self._status_bar.set_disconnected()
                self._explorer.clear()
        elif self._db_tabs.count() > 1:
            # Don't remove welcome tab if it's the only one
            pass

    def _current_db_tab(self) -> Optional[DatabaseTab]:
        tab = self._db_tabs.currentWidget()
        return tab if isinstance(tab, DatabaseTab) else None

    def _on_active_tab_changed(self, index: int) -> None:
        tab = self._db_tabs.widget(index)
        if isinstance(tab, DatabaseTab):
            self._explorer.set_connection(tab.conn)
            self._status_bar.set_connected(tab.conn.name)
            self._backup_service.set_database(tab.conn.path)

    # ── Schema actions ────────────────────────────────────────────────────────

    def _on_table_activated(self, table_name: str) -> None:
        tab = self._current_db_tab()
        if tab:
            tab.load_table(table_name)

    def _on_query_requested(self, sql: str) -> None:
        tab = self._current_db_tab()
        if tab:
            tab.open_query(sql)

    def _on_refresh_schema(self) -> None:
        self._explorer.reload()

    def _on_drop_object(self, obj_type: str, name: str) -> None:
        tab = self._current_db_tab()
        if not tab:
            return
        reply = QMessageBox.question(
            self, f"Drop {obj_type.title()}",
            f"Are you sure you want to DROP {obj_type.upper()} \"{name}\"?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._backup_service.backup_before_operation("pre_drop")
            try:
                tab.conn.execute(f'DROP {obj_type.upper()} IF EXISTS "{name}";')
                tab.conn.commit()
                self._explorer.reload()
                self._status_bar.show_success(f"Dropped {obj_type} '{name}'.")
            except Exception as exc:
                QMessageBox.critical(self, "Drop Failed", str(exc))

    def _on_rename_object(self, obj_type: str, name: str) -> None:
        tab = self._current_db_tab()
        if not tab:
            return
        new_name, ok = QInputDialog.getText(
            self, "Rename", f"New name for {obj_type} '{name}':", text=name
        )
        if ok and new_name and new_name != name:
            try:
                tab.conn.execute(f'ALTER TABLE "{name}" RENAME TO "{new_name}";')
                tab.conn.commit()
                self._explorer.reload()
                self._status_bar.show_success(f"Renamed to '{new_name}'.")
            except Exception as exc:
                QMessageBox.critical(self, "Rename Failed", str(exc))

    # ── Import / Export ───────────────────────────────────────────────────────

    def _on_import(self) -> None:
        tab = self._current_db_tab()
        if not tab:
            QMessageBox.information(self, "No Database", "Open a database first.")
            return
        from widgets.import_dialog import ImportDialog
        dlg = ImportDialog(tab.conn, self)
        if dlg.exec() == QDialog.Accepted:
            self._explorer.reload()
            self._status_bar.show_success("Import complete.")

    def _on_export(self) -> None:
        tab = self._current_db_tab()
        if not tab:
            QMessageBox.information(self, "No Database", "Open a database first.")
            return
        from widgets.export_dialog import ExportDialog
        dlg = ExportDialog(tab.conn, parent=self)
        dlg.exec()

    # ── Tools ─────────────────────────────────────────────────────────────────

    def _on_pragma_editor(self) -> None:
        tab = self._current_db_tab()
        if not tab:
            return
        from widgets.pragma_editor import PragmaEditorDialog
        dlg = PragmaEditorDialog(tab.conn, self)
        dlg.exec()

    def _on_vacuum(self) -> None:
        tab = self._current_db_tab()
        if not tab:
            return
        try:
            from core.database.pragma_manager import PragmaManager
            PragmaManager(tab.conn.connection).run_vacuum()
            self._status_bar.show_success("VACUUM completed.")
        except Exception as exc:
            QMessageBox.critical(self, "VACUUM Failed", str(exc))

    def _on_analyze(self) -> None:
        tab = self._current_db_tab()
        if not tab:
            return
        try:
            from core.database.pragma_manager import PragmaManager
            PragmaManager(tab.conn.connection).run_analyze()
            self._status_bar.show_success("ANALYZE completed.")
        except Exception as exc:
            QMessageBox.critical(self, "ANALYZE Failed", str(exc))

    def _on_fake_data(self) -> None:
        tab = self._current_db_tab()
        if not tab:
            return
        from core.database.introspector import SchemaIntrospector
        intro = SchemaIntrospector(tab.conn.connection)
        tables = intro.get_tables()
        if not tables:
            QMessageBox.information(self, "No Tables", "No tables found.")
            return
        table, ok = QInputDialog.getItem(self, "Generate Fake Data", "Select table:", tables, 0, False)
        if not ok:
            return
        n, ok2 = QInputDialog.getInt(self, "Generate Fake Data", "Number of rows:", 100, 1, 100000)
        if not ok2:
            return
        try:
            from services.fake_data_service import FakeDataService
            svc = FakeDataService(tab.conn.connection)
            inserted = svc.generate(table, n)
            self._status_bar.show_success(f"Inserted {inserted} fake rows into '{table}'.")
            self._explorer.reload()
        except Exception as exc:
            QMessageBox.critical(self, "Fake Data Error", str(exc))

    def _on_backup(self) -> None:
        path = self._backup_service.backup()
        if path:
            self._status_bar.show_success(f"Backup saved: {Path(path).name}")

    def _on_db_stats(self) -> None:
        tab = self._current_db_tab()
        if not tab:
            return
        from core.database.introspector import SchemaIntrospector
        intro = SchemaIntrospector(tab.conn.connection)
        stats = intro.get_database_stats()
        lines = "\n".join(f"  {k}: {v}" for k, v in stats.items())
        QMessageBox.information(self, f"Database Statistics — {tab.conn.name}", lines)

    def _on_column_stats(self) -> None:
        tab = self._current_db_tab()
        if not tab:
            QMessageBox.information(self, "No Database", "Open a database first.")
            return
        from core.database.introspector import SchemaIntrospector
        intro = SchemaIntrospector(tab.conn.connection)
        tables = intro.get_tables() + intro.get_views()
        if not tables:
            QMessageBox.information(self, "No Tables", "No tables found.")
            return
        table, ok = QInputDialog.getItem(self, "Column Statistics", "Select table:", tables, 0, False)
        if ok:
            from widgets.column_stats_dialog import ColumnStatsDialog
            dlg = ColumnStatsDialog(tab.conn, table, self)
            dlg.exec()

    def _on_mass_update(self) -> None:
        tab = self._current_db_tab()
        if not tab:
            QMessageBox.information(self, "No Database", "Open a database first.")
            return
        if tab.conn.read_only:
            QMessageBox.warning(self, "Read-Only", "Cannot update a read-only database.")
            return
        from widgets.mass_update_dialog import MassUpdateDialog
        dlg = MassUpdateDialog(tab.conn, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._status_bar.show_success("Mass update completed.")

    def _on_create_table(self) -> None:
        tab = self._current_db_tab()
        if not tab:
            QMessageBox.information(self, "No Database", "Open a database first.")
            return
        if tab.conn.read_only:
            QMessageBox.warning(self, "Read-Only", "Cannot create tables in read-only mode.")
            return
        from widgets.create_table_dialog import CreateTableDialog
        dlg = CreateTableDialog(tab.conn, self)
        if dlg.exec() == QDialog.Accepted:
            self._explorer.reload()
            self._status_bar.show_success("Table created.")

    def _on_table_structure(self) -> None:
        tab = self._current_db_tab()
        if not tab:
            QMessageBox.information(self, "No Database", "Open a database first.")
            return
        from core.database.introspector import SchemaIntrospector
        intro = SchemaIntrospector(tab.conn.connection)
        tables = intro.get_tables() + intro.get_views()
        if not tables:
            QMessageBox.information(self, "No Tables", "No tables found.")
            return
        table, ok = QInputDialog.getItem(self, "Table Structure", "Select table:", tables, 0, False)
        if ok:
            from widgets.table_structure_dialog import TableStructureDialog
            dlg = TableStructureDialog(tab.conn, table, self)
            if dlg.exec() == QDialog.Accepted:
                self._explorer.reload()

    def _on_open_demo(self) -> None:
        from utils.demo_database import create_demo_database, DEMO_DB_PATH
        try:
            if not DEMO_DB_PATH.exists():
                self._status_bar.show_message("Creating demo database…")
                QApplication.processEvents()
                path = create_demo_database()
            else:
                path = str(DEMO_DB_PATH)
            self._open_database(path)
            self._status_bar.show_success("Demo database opened! Try the Schema Explorer.")
        except Exception as exc:
            QMessageBox.critical(self, "Demo Error", str(exc))

    def _on_autobackup_toggle(self, checked: bool) -> None:
        if checked:
            self._backup_service.start_auto_backup()
            self._act_autobackup.setText("🔄 Auto-Backup: ON")
        else:
            self._backup_service.stop_auto_backup()
            self._act_autobackup.setText("🔄 Auto-Backup: OFF")

    # ── Find & Replace ────────────────────────────────────────────────────────

    def _on_find_replace(self) -> None:
        from widgets.find_replace import FindReplaceDialog
        dlg = FindReplaceDialog(self)
        dlg.show()

    # ── ERD ───────────────────────────────────────────────────────────────────

    def _on_show_erd(self) -> None:
        tab = self._current_db_tab()
        if tab:
            # Switch to ERD tab in the current DB tab
            tab._inner_tabs.setCurrentIndex(2)

    # ── Undo / Redo ───────────────────────────────────────────────────────────

    def _on_undo(self) -> None:
        tab = self._current_db_tab()
        if tab and tab.data_viewer._model:
            tab.data_viewer._model.undo_stack.undo()

    def _on_redo(self) -> None:
        tab = self._current_db_tab()
        if tab and tab.data_viewer._model:
            tab.data_viewer._model.undo_stack.redo()

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _on_toggle_theme(self) -> None:
        new = theme_manager.toggle()
        icon = "☀" if new == THEME_LIGHT else "🌙"
        self._status_bar.show_message(f"{icon} Switched to {new} theme.")

    # ── Recent DBs ────────────────────────────────────────────────────────────

    def _update_recent_menu(self) -> None:
        self._recent_menu.clear()
        recents = connection_manager.recent_databases()
        if not recents:
            act = self._recent_menu.addAction("(none)")
            act.setEnabled(False)
            return
        for path in recents:
            act = self._recent_menu.addAction(f"📦 {Path(path).name}")
            act.setToolTip(path)
            act.triggered.connect(lambda checked=False, p=path: self._open_database(p))
        self._recent_menu.addSeparator()
        self._recent_menu.addAction("🗑 Clear Recent", self._on_clear_recent)

    def _on_clear_recent(self) -> None:
        for p in connection_manager.recent_databases():
            connection_manager.remove_recent(p)
        self._update_recent_menu()

    # ── Help ──────────────────────────────────────────────────────────────────

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<h2 style='color:#cba6f7'>{APP_NAME}</h2>"
            f"<p>Version {APP_VERSION}</p>"
            "<p>A modern, production-grade SQLite database manager.</p>"
            "<p>Built with Python + PySide6.</p>",
        )

    def _on_shortcuts(self) -> None:
        shortcuts = (
            "<table cellpadding='4'>"
            "<tr><th align='left'>Shortcut</th><th align='left'>Action</th></tr>"
            "<tr><td>Ctrl+O</td><td>Open Database</td></tr>"
            "<tr><td>Ctrl+N</td><td>New Database</td></tr>"
            "<tr><td>Ctrl+W</td><td>Close Tab</td></tr>"
            "<tr><td>Ctrl+I</td><td>Import Data</td></tr>"
            "<tr><td>Ctrl+E</td><td>Export Data</td></tr>"
            "<tr><td>Ctrl+T</td><td>Toggle Theme</td></tr>"
            "<tr><td>Ctrl+H</td><td>Find & Replace</td></tr>"
            "<tr><td>Ctrl+Z</td><td>Undo</td></tr>"
            "<tr><td>Ctrl+Y</td><td>Redo</td></tr>"
            "<tr><td>Ctrl+S</td><td>Save (Data Viewer)</td></tr>"
            "<tr><td>Ctrl+Enter</td><td>Run Query</td></tr>"
            "<tr><td>F5</td><td>Refresh Schema</td></tr>"
            "<tr><td>Ctrl+C</td><td>Copy selected cells</td></tr>"
            "<tr><td>Ctrl+V</td><td>Paste</td></tr>"
            "</table>"
        )
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Keyboard Shortcuts")
        dlg.setText(shortcuts)
        dlg.exec()

    def _on_check_updates(self) -> None:
        """Manual update check — shows a dialog with result."""
        from PySide6.QtWidgets import QProgressDialog
        from services.updater_service import UpdaterService, ReleaseInfo

        progress = QProgressDialog("Checking for updates…", "Cancel", 0, 0, self)
        progress.setWindowTitle("Check for Updates")
        progress.setWindowModality(Qt.WindowModal)
        progress.show()

        self._update_svc = UpdaterService(self)

        def on_found(release: ReleaseInfo) -> None:
            progress.close()
            reply = QMessageBox.question(
                self,
                "Update Available",
                f"<b>v{release.version}</b> is available!<br><br>"
                f"<b>Release Notes:</b><br>{release.body[:500]}…<br><br>"
                "Download and install now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                import webbrowser
                webbrowser.open(release.browser_url)

        def on_no_update() -> None:
            progress.close()
            QMessageBox.information(self, "No Updates", f"You are running the latest version (v{APP_VERSION}).")

        def on_failed(msg: str) -> None:
            progress.close()
            QMessageBox.warning(self, "Update Check Failed",
                                f"Could not check for updates:\n{msg}\n\nCheck your internet connection.")

        self._update_svc.update_available.connect(on_found)
        self._update_svc.no_update.connect(on_no_update)
        self._update_svc.check_failed.connect(on_failed)
        self._update_svc.check(silent=False)

    # ── State persistence ─────────────────────────────────────────────────────

    def _restore_state(self) -> None:
        geom = self._settings.value(SETTINGS_WINDOW_GEOM)
        state = self._settings.value(SETTINGS_WINDOW_STATE)
        if geom:
            self.restoreGeometry(geom)
        if state:
            self.restoreState(state)

    def _try_reopen_last(self) -> None:
        last = connection_manager.last_database()
        if last:
            log.info("Auto-reopening last DB: %s", last)
            self._open_database(last)

    def closeEvent(self, event) -> None:
        self._settings.setValue(SETTINGS_WINDOW_GEOM, self.saveGeometry())
        self._settings.setValue(SETTINGS_WINDOW_STATE, self.saveState())
        connection_manager.close_all()
        self._backup_service.stop_auto_backup()
        super().closeEvent(event)
