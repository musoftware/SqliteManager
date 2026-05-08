# -*- mode: python ; coding: utf-8 -*-
"""
app.spec — PyInstaller Build Specification for SQLite Manager.
Production-hardened for PySide6 + pandas + SQLite on Windows 10/11 x64.

Key fixes vs previous version:
  - Runtime hook adds _internal/ to DLL search path BEFORE Python/Qt loads
  - python312.dll explicitly bundled from CPython install (not venv)
  - VC runtime DLLs (vcruntime140.dll, ucrtbase.dll) bundled from System32
  - Qt platform plugins (qwindows.dll) explicitly collected
  - distutils alias conflict resolved (removed from EXCLUDES)
  - UPX disabled (corrupts Qt/Python DLLs, triggers false-positive AV)

Modes:
  - Default (onedir):   pyinstaller app.spec
  - One-file:           pyinstaller app.spec -- --onefile
  - Debug:              pyinstaller app.spec -- --debug
"""

import sys
import os
import glob
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_all, get_package_paths
import importlib.util

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT       = Path(SPECPATH)
ASSETS     = ROOT / "assets"
HOOKS_DIR  = ROOT / "hooks"
APP_ICON   = str(ASSETS / "icons" / "app.ico")
SPLASH_IMG = str(ASSETS / "splash.png")

# ── Mode flags ─────────────────────────────────────────────────────────────────
ONE_FILE   = "--onefile" in sys.argv
DEBUG_MODE = "--debug"   in sys.argv
CONSOLE    = DEBUG_MODE

# ── Collect all packages (datas + binaries + hiddenimports) ───────────────────
# Using collect_all() is the most reliable approach for complex packages.
# It handles DLLs, .pyd extensions, data files, and hook-generated imports.

pyside6_datas, pyside6_binaries, pyside6_hiddenimports = collect_all("PySide6")
pandas_datas,  pandas_binaries,  pandas_hiddenimports  = collect_all("pandas")
sqlalchemy_datas, sqlalchemy_binaries, sqlalchemy_hiddenimports = collect_all("sqlalchemy")
openpyxl_datas, openpyxl_binaries, openpyxl_hiddenimports = collect_all("openpyxl")

# ── Manual DLL Collection (Belt-and-suspenders) ──────────────────────────────
# In some PySide6 versions, collect_all might miss the core DLLs or place them 
# incorrectly. We manually collect them to be safe.
def manual_collect_dlls(package_name):
    pkg_binaries = []
    try:
        spec = importlib.util.find_spec(package_name)
        if spec and spec.origin:
            pkg_dir = Path(spec.origin).parent
            # Collect all DLLs and PYDs in the package root
            for ext in ["*.dll", "*.pyd"]:
                for f in pkg_dir.glob(ext):
                    # Destination is the package name (e.g. _internal/PySide6)
                    pkg_binaries.append((str(f), package_name))
            print(f"[spec] Manually collected {len(pkg_binaries)} binaries from {package_name}")
    except Exception as e:
        print(f"[spec] WARNING: Manual collection for {package_name} failed: {e}")
    return pkg_binaries

EXTRA_PYSIDE_BINARIES = manual_collect_dlls("PySide6")
EXTRA_SHIBOKEN_BINARIES = manual_collect_dlls("shiboken6")

# ── Additional hidden imports ──────────────────────────────────────────────────
EXTRA_HIDDEN_IMPORTS = [
    # PySide6 modules used in this app
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtPrintSupport",
    "PySide6.QtXml",
    # SQLAlchemy
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.pool",
    "sqlalchemy.engine",
    "sqlalchemy.ext.declarative",
    # pandas internals
    "pandas._libs.tslibs.np_datetime",
    "pandas._libs.tslibs.nattype",
    "pandas._libs.tslibs.timedeltas",
    "pandas._libs.tslibs.offsets",
    "pandas.io.formats.excel",
    # openpyxl
    "openpyxl.cell._writer",
    # reportlab
    "reportlab",
    "reportlab.lib.pagesizes",
    "reportlab.platypus",
    "reportlab.lib.styles",
    "reportlab.lib.enums",
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
    "cryptography.hazmat.primitives.ciphers",
    "cryptography.hazmat.backends",
    # misc
    "chardet",
    "sqlparse",
    "pygments",
    "pygments.lexers",
    "pygments.lexers.sql",
    "pygments.styles",
    "pygments.formatters",
    # stdlib (some need explicit declaration for PyInstaller)
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
    "ctypes",
    "ctypes.util",
    "struct",
    "platform",
]

ALL_HIDDEN_IMPORTS = (
    pyside6_hiddenimports
    + pandas_hiddenimports
    + sqlalchemy_hiddenimports
    + openpyxl_hiddenimports
    + EXTRA_HIDDEN_IMPORTS
)

# ── Data files ─────────────────────────────────────────────────────────────────
APP_DATAS = [
    (str(ASSETS / "icons" / "app.ico"), "assets/icons"),
    (str(ASSETS / "icons" / "db.ico"),  "assets/icons"),
    (str(ASSETS / "icons" / "app.png"), "assets/icons"),
    (str(ASSETS / "splash.png"),        "assets"),
]

# Include Qt plugin directories explicitly (belt-and-suspenders alongside collect_all)
try:
    from PySide6 import __file__ as _pyside6_init
    _pyside6_dir = Path(_pyside6_init).parent
    _qt_plugins_src = _pyside6_dir / "plugins"   # flat layout: PySide6/plugins/

    NEEDED_PLUGINS = [
        "platforms",      # qwindows.dll — CRITICAL: without this Qt can't start
        "styles",         # QWindowsVistaStyle etc.
        "imageformats",   # PNG, ICO, SVG support
        "iconengines",    # SVG icon engine
        "platformthemes", # system theme
        "printsupport",   # PDF print (reportlab integration)
    ]
    for _plugin in NEEDED_PLUGINS:
        _plugin_dir = _qt_plugins_src / _plugin
        if _plugin_dir.exists():
            APP_DATAS.append((str(_plugin_dir), f"PySide6/plugins/{_plugin}"))
            print(f"[spec] Qt plugin bundled: {_plugin}")
        else:
            print(f"[spec] WARNING: Qt plugin not found: {_plugin}")
except Exception as _qt_err:
    print(f"[spec] WARNING: Could not enumerate Qt plugins: {_qt_err}")

ALL_DATAS = APP_DATAS + pyside6_datas + pandas_datas + sqlalchemy_datas + openpyxl_datas

# ── Binary files ───────────────────────────────────────────────────────────────
# 1. python312.dll — search CPython install (not venv, venv redirects to parent)
_py_ver     = f"{sys.version_info.major}{sys.version_info.minor}"  # "312"
_dll_name   = f"python{_py_ver}.dll"
_py3_dll    = "python3.dll"

_PYTHON_DLLS = []

def _find_dll_in_paths(dll_name: str, search_paths: list) -> str | None:
    """Return the first existing path for dll_name, or None."""
    for base in search_paths:
        candidate = os.path.normpath(os.path.join(base, dll_name))
        if os.path.isfile(candidate):
            return candidate
    return None

_username = os.environ.get("USERNAME", os.environ.get("USER", ""))
_dll_search_paths = [
    # Walk up from venv/Scripts to get the base CPython install
    os.path.join(os.path.dirname(sys.executable), ".."),        # venv → parent
    os.path.dirname(sys.executable),                             # python.exe dir
    # Common CPython install locations
    rf"C:\Users\{_username}\AppData\Local\Programs\Python\Python{_py_ver}",
    rf"C:\Python{_py_ver}",
    rf"C:\Program Files\Python{_py_ver}",
    rf"C:\Program Files (x86)\Python{_py_ver}",
    # System32 (sometimes python gets here)
    r"C:\Windows\System32",
]

_py312_path = _find_dll_in_paths(_dll_name, _dll_search_paths)
if _py312_path:
    _PYTHON_DLLS.append((_py312_path, "."))
    print(f"[spec] Bundling {_dll_name}: {_py312_path}")
else:
    print(f"[spec] WARNING: {_dll_name} not found — EXE may fail on machines without Python!")

_py3_path = _find_dll_in_paths(_py3_dll, _dll_search_paths)
if _py3_path:
    _PYTHON_DLLS.append((_py3_path, "."))
    print(f"[spec] Bundling {_py3_dll}: {_py3_path}")

# 2. VC Runtime DLLs — collect from System32 (they belong next to EXE for portability)
_VC_DLLS = []
_system32 = r"C:\Windows\System32"
_vc_dll_names = [
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "msvcp140.dll",
    "ucrtbase.dll",
]
for _vc_dll in _vc_dll_names:
    _vc_path = os.path.join(_system32, _vc_dll)
    if os.path.isfile(_vc_path):
        _VC_DLLS.append((_vc_path, "."))
        print(f"[spec] Bundling VC runtime: {_vc_dll}")
    else:
        print(f"[spec] NOTE: {_vc_dll} not in System32 (may be bundled by PySide6 hook)")

# 3. sqlite3.dll (if separate from python DLL)
_SQLITE_DLLS = []
for _sq_path in _dll_search_paths:
    _sq_dll = os.path.join(os.path.normpath(_sq_path), "DLLs", "sqlite3.dll")
    if os.path.isfile(_sq_dll):
        _SQLITE_DLLS.append((_sq_dll, "."))
        print(f"[spec] Bundling sqlite3.dll: {_sq_dll}")
        break

ALL_BINARIES = (
    _PYTHON_DLLS
    + _VC_DLLS
    + _SQLITE_DLLS
    + pyside6_binaries
    + pandas_binaries
    + sqlalchemy_binaries
    + openpyxl_binaries
    + EXTRA_PYSIDE_BINARIES
    + EXTRA_SHIBOKEN_BINARIES
)

# ── Exclusions ────────────────────────────────────────────────────────────────
# IMPORTANT: Do NOT exclude distutils — PyInstaller 6.x hooks alias it internally
# and excluding it causes "Target module already imported" ValueError.
EXCLUDES = [
    # Unused Qt modules (reduces size significantly)
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
    # Dev tools
    "tkinter",
    "unittest",
    "test",
    "pydoc",
    "doctest",
    "lib2to3",
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

# ── Analysis ───────────────────────────────────────────────────────────────────
block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=ALL_BINARIES,
    datas=ALL_DATAS,
    hiddenimports=ALL_HIDDEN_IMPORTS,
    hookspath=[str(HOOKS_DIR)] if HOOKS_DIR.exists() else [],
    hooksconfig={},
    runtime_hooks=[
        str(ROOT / "hooks" / "runtime_hook_dll_path.py"),
    ],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ── PYZ ────────────────────────────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── Splash ─────────────────────────────────────────────────────────────────────
# PyInstaller's built-in Splash() requires Tcl/Tk (tcl86t.dll / tk86t.dll).
# These DLLs are NOT present in this venv and cause a fatal LoadLibrary crash:
#   "Failed to load Tcl DLL 'tcl86t.dll'. LoadLibrary: The specified module could not be found."
#
# The app already has its own Qt-based SplashScreen widget (widgets/splash_screen.py)
# which works without Tcl/Tk. PyInstaller's built-in splash is permanently DISABLED.
_splash_extras = []
print("[spec] Built-in splash: DISABLED (using app's Qt SplashScreen widget instead)")

# ── EXE ────────────────────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    *_splash_extras,
    [] if not ONE_FILE else a.binaries + a.zipfiles + a.datas,
    name="SQLiteManager",
    debug=DEBUG_MODE,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # NEVER use UPX: corrupts Qt/Python DLLs, triggers AV false positives
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

# ── COLLECT (one-dir mode only) ────────────────────────────────────────────────
if not ONE_FILE:
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,      # UPX disabled — see above
        upx_exclude=[],
        name="SQLiteManager",
    )
