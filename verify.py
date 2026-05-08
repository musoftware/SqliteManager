# -*- coding: utf-8 -*-
"""Verification script — run via: python verify.py"""
import sys
import os

# Force UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("=" * 60)
print("SQLite Manager -- Verification")
print("=" * 60)

from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

errors = []

def check(name, fn):
    try:
        fn()
        print(f"  [OK]   {name}")
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        errors.append((name, str(e)))

# Core
check("app.config", lambda: __import__("app.config"))
check("app.logger", lambda: __import__("app.logger"))
check("core.database.connection", lambda: __import__("core.database.connection"))
check("core.database.introspector", lambda: __import__("core.database.introspector"))
check("core.database.executor", lambda: __import__("core.database.executor"))
check("core.database.pragma_manager", lambda: __import__("core.database.pragma_manager"))
check("core.models.table_model", lambda: __import__("core.models.table_model"))
check("core.models.schema_model", lambda: __import__("core.models.schema_model"))
check("core.workers.query_worker", lambda: __import__("core.workers.query_worker"))
check("core.workers.import_export_workers", lambda: __import__("core.workers.import_export_workers"))

# Services
check("services.import_service", lambda: __import__("services.import_service"))
check("services.export_service", lambda: __import__("services.export_service"))
check("services.backup_service", lambda: __import__("services.backup_service"))
check("services.fake_data_service", lambda: __import__("services.fake_data_service"))
check("services.formatter_service", lambda: __import__("services.formatter_service"))

# UI
check("ui.theme_manager", lambda: __import__("ui.theme_manager"))
check("ui.main_window", lambda: __import__("ui.main_window"))

# Widgets
check("widgets.schema_explorer", lambda: __import__("widgets.schema_explorer"))
check("widgets.data_viewer", lambda: __import__("widgets.data_viewer"))
check("widgets.query_editor", lambda: __import__("widgets.query_editor"))
check("widgets.status_bar", lambda: __import__("widgets.status_bar"))
check("widgets.erd_viewer", lambda: __import__("widgets.erd_viewer"))
check("widgets.import_dialog", lambda: __import__("widgets.import_dialog"))
check("widgets.export_dialog", lambda: __import__("widgets.export_dialog"))
check("widgets.pragma_editor", lambda: __import__("widgets.pragma_editor"))
check("widgets.find_replace", lambda: __import__("widgets.find_replace"))
check("widgets.table_structure_dialog", lambda: __import__("widgets.table_structure_dialog"))
check("widgets.create_table_dialog", lambda: __import__("widgets.create_table_dialog"))
check("widgets.column_stats_dialog", lambda: __import__("widgets.column_stats_dialog"))
check("widgets.mass_update_dialog", lambda: __import__("widgets.mass_update_dialog"))

# Utils
check("utils.helpers", lambda: __import__("utils.helpers"))
check("utils.demo_database", lambda: __import__("utils.demo_database"))

print()
print("=" * 60)
print("Demo Database")
print("=" * 60)

from utils.demo_database import create_demo_database, DEMO_DB_PATH
import sqlite3

path = create_demo_database()
size_kb = os.path.getsize(path) // 1024
print(f"  Path : {path}")
print(f"  Size : {size_kb} KB")
print("  Tables:")
conn = sqlite3.connect(path)
rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
for (t,) in rows:
    count = conn.execute(f'SELECT COUNT(*) FROM "{t}";').fetchone()[0]
    print(f"    {t:<20} {count:>6} rows")
views = conn.execute("SELECT name FROM sqlite_master WHERE type='view';").fetchall()
for (v,) in views:
    print(f"    [view] {v}")
conn.close()

print()
print("=" * 60)
total = 34
if errors:
    print(f"RESULT: FAILED -- {len(errors)} errors out of {total} checks")
    for name, err in errors:
        print(f"  - {name}: {err}")
    sys.exit(1)
else:
    print(f"RESULT: ALL {total} CHECKS PASSED")
    sys.exit(0)
