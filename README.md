# SQLite Manager

A modern, production-grade SQLite database management desktop application built with **Python 3.12+** and **PySide6**.

---

## Features

| Category | Features |
|---|---|
| **Database** | Open/Create/Close, multiple tabs, read-only mode, lock detection, recent history |
| **Schema Explorer** | Tables, Views, Indexes, Triggers; column details; search filter; context menus |
| **Data Viewer** | Paginated spreadsheet editor, inline editing, undo/redo, copy/paste, filters, sorting |
| **SQL Editor** | Syntax highlighting, line numbers, autocomplete, query history, multi-tab, explain plan |
| **Import** | CSV, Excel, JSON, SQL dump, SQLite→SQLite; column mapping; upsert; batch; preview |
| **Export** | CSV, Excel, JSON, SQL dump, PDF, SQLite; by table or query; ZIP compression |
| **ERD Viewer** | Custom canvas, FK connections, zoom/pan, drag tables |
| **PRAGMA Editor** | Visual editor for all SQLite PRAGMAs; VACUUM, ANALYZE, integrity check |
| **Fake Data** | Faker-based test data generator with column type heuristics |
| **Backup** | Manual & auto-scheduled backups |
| **Theme** | Dark (Catppuccin-inspired) and Light themes |

---

## Setup

### 1. Prerequisites

- Python 3.12+
- pip

### 2. Create virtual environment

```powershell
cd d:\Projects\1AOrganized\PythonProjects\DinaMohammed\SqliteManager
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Run

```powershell
python main.py
```

---

## Build Windows Executable

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name "SQLiteManager" main.py
```

The `.exe` will be in `dist/SQLiteManager.exe`.

---

## Architecture

```
SqliteManager/
├── main.py               # Entry point
├── requirements.txt
├── app/
│   ├── config.py         # Constants, paths, theme colors
│   └── logger.py         # Rotating log setup
├── core/
│   ├── database/
│   │   ├── connection.py    # Thread-safe connection manager
│   │   ├── executor.py      # Paginated SQL executor
│   │   ├── introspector.py  # Schema introspection
│   │   └── pragma_manager.py
│   ├── models/
│   │   ├── table_model.py   # Virtual paginated QAbstractTableModel
│   │   └── schema_model.py  # Tree model for schema
│   └── workers/
│       ├── query_worker.py          # Background SQL execution
│       └── import_export_workers.py # Background import/export
├── services/
│   ├── import_service.py    # CSV/Excel/JSON/SQL/SQLite import
│   ├── export_service.py    # CSV/Excel/JSON/SQL/PDF/SQLite export
│   ├── backup_service.py    # Auto-backup scheduler
│   ├── formatter_service.py # SQL formatting
│   └── fake_data_service.py # Faker test data generator
├── ui/
│   ├── main_window.py    # QMainWindow — wires everything
│   └── theme_manager.py  # Dark/Light QSS themes
└── widgets/
    ├── schema_explorer.py   # Left-panel schema tree
    ├── data_viewer.py       # Spreadsheet data editor
    ├── query_editor.py      # SQL editor with highlighting
    ├── import_dialog.py     # 5-step import wizard
    ├── export_dialog.py     # Export dialog
    ├── erd_viewer.py        # ERD canvas
    ├── pragma_editor.py     # PRAGMA editor dialog
    ├── find_replace.py      # Find & Replace
    └── status_bar.py        # Custom status bar
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+O` | Open Database |
| `Ctrl+N` | New Database |
| `Ctrl+W` | Close Tab |
| `Ctrl+I` | Import Data |
| `Ctrl+E` | Export Data |
| `Ctrl+T` | Toggle Theme |
| `Ctrl+H` | Find & Replace |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Redo |
| `Ctrl+S` | Save (Data Viewer) |
| `Ctrl+Enter` | Run Query |
| `F5` | Refresh Schema |
| `Ctrl+C` | Copy cells |
| `Ctrl+V` | Paste cells |

---

## Data Safety

- Confirmation dialog before any DROP/DELETE
- Auto-backup before destructive operations
- Transaction rollback on error
- Read-only mode available
- Undo/Redo for cell edits
