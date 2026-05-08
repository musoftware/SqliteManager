# -*- mode: python ; coding: utf-8 -*-
"""
app.spec — PyInstaller Build Specification for SQLite Manager.

Modes:
  - Default (onedir): pyinstaller app.spec
  - One-file:         pyinstaller app.spec -- --onefile
  - Debug:            pyinstaller app.spec -- --debug

Optimizations:
  - Strips unused Qt modules
  - Compresses binaries (UPX if available)
  - Removes test/doc packages
  - Tree-shakes PySide6 to essential plugins only
"""

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(SPECPATH)
ASSETS = ROOT / "assets"
APP_ICON = str(ASSETS / "icons" / "app.ico")
SPLASH_IMG = str(ASSETS / "splash.png")

# ── Mode flags ────────────────────────────────────────────────────────────────
ONE_FILE = "--onefile" in sys.argv
DEBUG_MODE = "--debug" in sys.argv
CONSOLE = DEBUG_MODE          # show console only in debug

# ── Hidden imports ────────────────────────────────────────────────────────────
# PySide6 modules we actually use
PYSIDE6_MODULES = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",
    "PySide6.QtPrintSupport",
    "PySide6.QtSvgWidgets",
    "PySide6.QtXml",
]

# Third-party packages requiring explicit declaration
HIDDEN_IMPORTS = PYSIDE6_MODULES + [
    # SQLAlchemy dialects
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.pool",
    "sqlalchemy.engine",
    # pandas backends
    "pandas",
    "pandas.io.formats.excel",
    "pandas._libs.tslibs.np_datetime",
    "pandas._libs.tslibs.nattype",
    "pandas._libs.tslibs.timedeltas",
    # openpyxl
    "openpyxl",
    "openpyxl.cell._writer",
    # reportlab
    "reportlab",
    "reportlab.lib.pagesizes",
    "reportlab.platypus",
    # faker
    "faker",
    "faker.providers",
    "faker.providers.person",
    "faker.providers.internet",
    "faker.providers.phone_number",
    "faker.providers.address",
    "faker.providers.lorem",
    "faker.providers.date_time",
    "faker.providers.company",
    # cryptography
    "cryptography",
    "cryptography.fernet",
    "cryptography.hazmat.primitives",
    # chardet
    "chardet",
    # sqlparse
    "sqlparse",
    # pygments
    "pygments",
    "pygments.lexers",
    "pygments.lexers.sql",
    "pygments.styles",
    "pygments.formatters",
    # stdlib
    "csv",
    "json",
    "sqlite3",
    "logging",
    "logging.handlers",
    "pathlib",
    "threading",
    "zipfile",
    "tempfile",
    "shutil",
    "urllib.request",
]

# ── Data files ────────────────────────────────────────────────────────────────
DATAS = [
    (str(ASSETS / "icons" / "app.ico"),   "assets/icons"),
    (str(ASSETS / "icons" / "db.ico"),    "assets/icons"),
    (str(ASSETS / "icons" / "app.png"),   "assets/icons"),
    (str(ASSETS / "splash.png"),          "assets"),
]

# PySide6 Qt plugins needed for Windows
QT_PLUGINS = [
    "platforms",        # Windows platform
    "styles",           # QStyle
    "imageformats",     # PNG, ICO, SVG
    "iconengines",      # SVG icons
    "platformthemes",   # system theme integration
    "printsupport",     # PDF print support (reportlab)
]

# Add Qt plugin dirs
try:
    from PySide6 import __file__ as pyside6_init
    pyside6_dir = Path(pyside6_init).parent
    for plugin in QT_PLUGINS:
        plugin_dir = pyside6_dir / "Qt" / "plugins" / plugin
        if plugin_dir.exists():
            DATAS.append((str(plugin_dir), f"PySide6/Qt/plugins/{plugin}"))
except Exception as e:
    print(f"Warning: Could not add Qt plugin {plugin}: {e}")

# ── Exclusions (reduce size) ──────────────────────────────────────────────────
EXCLUDES = [
    # Heavy unused Qt modules
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtLocation",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtSensors",
    "PySide6.QtSerialBus",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtStateMachine",
    "PySide6.QtUiTools",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngine",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    # Unused standard library
    "tkinter",
    "unittest",
    "email",
    "xml.etree",
    "test",
    "pydoc",
    "doctest",
    "lib2to3",
    # NOTE: do NOT exclude 'distutils' — PyInstaller 6.x hooks alias it internally
    # Unused third-party
    "matplotlib",
    "scipy",
    "sklearn",
    "IPython",
    "jupyter",
    "notebook",
    "pytest",
    "black",
    "isort",
    "mypy",
]

# ── Explicitly bundle Python DLL ─────────────────────────────────────────────
# Required so the exe works on machines without Python installed.
# PyInstaller sometimes misses this when Python is in AppData.
import glob, os

_PYTHON_DLL_BINARIES = []
_py_ver = f"{sys.version_info.major}{sys.version_info.minor}"  # e.g. "312"
_dll_name = f"python{_py_ver}.dll"

# Search common install locations
_dll_search_paths = [
    os.path.dirname(sys.executable),           # same dir as python.exe
    os.path.join(os.path.dirname(sys.executable), ".."),
    f"C:/Users/{os.environ.get('USERNAME','')}/AppData/Local/Programs/Python/Python{_py_ver}",
    f"C:/Python{_py_ver}",
    f"C:/Program Files/Python{_py_ver}",
    f"C:/Program Files (x86)/Python{_py_ver}",
]
for _search in _dll_search_paths:
    _candidate = os.path.join(os.path.normpath(_search), _dll_name)
    if os.path.isfile(_candidate):
        _PYTHON_DLL_BINARIES = [(_candidate, ".")]
        print(f"[spec] Bundling Python DLL: {_candidate}")
        break

if not _PYTHON_DLL_BINARIES:
    print(f"[spec] WARNING: Could not find {_dll_name} — exe may fail on other machines")

# ── Analysis ──────────────────────────────────────────────────────────────────
block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=_PYTHON_DLL_BINARIES,
    datas=DATAS,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ── PYZ ───────────────────────────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── Splash (PyInstaller built-in splash support) ──────────────────────────────
# Note: Splash requires Tcl/Tk on some Python builds. If it fails, build without it.
_splash_binaries = []
_splash_datas    = []
try:
    splash = Splash(
        SPLASH_IMG,
        binaries=a.binaries,
        datas=a.datas,
        text_pos=None,
        text_size=12,
        minify_script=True,
    )
    _splash_binaries = splash.binaries
    _splash_extras   = [splash]
except Exception as e:
    print(f"[INFO] Built-in splash screen not available ({e}); using app's own SplashScreen widget.")
    splash           = None
    _splash_extras   = []

# ── EXE ───────────────────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    *_splash_extras,
    _splash_binaries,
    [] if not ONE_FILE else a.binaries + a.zipfiles + a.datas,
    name="SQLiteManager",
    debug=DEBUG_MODE,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # Disabled: UPX can corrupt Python/Qt DLLs and trigger AV false positives
    upx_exclude=[],
    runtime_tmpdir=None,
    console=CONSOLE,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=APP_ICON,
    version="installer/version_info.txt",
)

# ── COLLECT (one-dir mode only) ───────────────────────────────────────────────
if not ONE_FILE:
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=exe.upx_exclude,
        name="SQLiteManager",
    )
