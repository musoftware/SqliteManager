"""
utils/startup_diagnostics.py — Pre-launch DLL & Environment Validator.

Run at the very start of main.py (before any PySide6 imports) to:
  1. Detect Microsoft Store Python (stub) — reject it
  2. Validate architecture (x64 only)
  3. Check critical DLLs are loadable
  4. Check Visual C++ Redistributable presence
  5. Log full environment report to logs/startup.log
  6. Show user-friendly error dialog for missing dependencies

Usage in main.py:
    from utils.startup_diagnostics import run_startup_diagnostics
    run_startup_diagnostics()   # call before any Qt import
"""
from __future__ import annotations

import ctypes
import ctypes.util
import os
import platform
import struct
import sys
import traceback
from pathlib import Path


# ── Log file: written before Qt loads (plain text) ───────────────────────────
def _get_log_path() -> Path:
    appdata = os.getenv("APPDATA", str(Path.home()))
    log_dir = Path(appdata) / "SQLiteManager" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "startup.log"


def _log(msg: str) -> None:
    """Append a line to startup.log (always, even before logging module loads)."""
    try:
        with open(_get_log_path(), "a", encoding="utf-8") as f:
            import datetime
            f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


# ── Simple messagebox (no Qt needed) ─────────────────────────────────────────
def _msgbox(title: str, message: str, icon: int = 0x10) -> None:
    """Show a Windows MessageBox. icon=0x10 is MB_ICONERROR."""
    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(0, message, title, icon | 0x1000)
        except Exception:
            print(f"\n[ERROR] {title}\n{message}", file=sys.stderr)
    else:
        print(f"\n[ERROR] {title}\n{message}", file=sys.stderr)


# ── Architecture check ────────────────────────────────────────────────────────
def _check_architecture() -> None:
    bits = struct.calcsize("P") * 8
    machine = platform.machine()
    _log(f"Architecture: {bits}-bit, machine={machine}, platform={platform.platform()}")

    if bits != 64:
        msg = (
            f"SQLiteManager requires a 64-bit Python interpreter.\n\n"
            f"Detected: {bits}-bit Python\n\n"
            f"Please reinstall Python 3.12 (64-bit) from:\n"
            f"https://www.python.org/downloads/"
        )
        _log(f"FATAL: Wrong architecture ({bits}-bit)")
        _msgbox("Architecture Error", msg)
        sys.exit(1)


# ── Microsoft Store Python detection ─────────────────────────────────────────
def _check_not_store_python() -> None:
    """Reject WindowsApps stub Python — it cannot bundle python312.dll properly."""
    exe = sys.executable.lower()
    _log(f"Python executable: {sys.executable}")
    _log(f"Python version: {sys.version}")

    store_markers = [
        "windowsapps",
        "microsoft\\windowsapps",
        "localappdata\\microsoft\\windowsapps",
    ]
    is_store = any(m in exe for m in store_markers)

    if is_store:
        msg = (
            "SQLiteManager cannot run from a Microsoft Store Python installation.\n\n"
            "The Microsoft Store Python is a stub that does not include python312.dll,\n"
            "which is required for this application.\n\n"
            "Please install CPython 3.12 (64-bit) directly from:\n"
            "https://www.python.org/downloads/\n\n"
            f"Current Python: {sys.executable}"
        )
        _log("FATAL: Microsoft Store Python detected")
        _msgbox("Invalid Python Installation", msg)
        sys.exit(1)

    _log("Python installation: OK (not Microsoft Store)")


# ── DLL availability check ────────────────────────────────────────────────────
_CRITICAL_DLLS = [
    f"python{sys.version_info.major}{sys.version_info.minor}.dll",  # python312.dll
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "Qt6Core.dll",
    "Qt6Gui.dll",
    "Qt6Widgets.dll",
]

_IMPORTANT_DLLS = [
    "ucrtbase.dll",
    "msvcp140.dll",
]


def _check_dll(dll_name: str) -> tuple[bool, str]:
    """Try to load a DLL. Returns (success, path_or_error)."""
    # First: check if it's already loaded (common case in bundled apps)
    if os.name == "nt":
        h = ctypes.windll.kernel32.GetModuleHandleW(dll_name)
        if h:
            # Get path of the already-loaded module
            buf = ctypes.create_unicode_buffer(1024)
            ctypes.windll.kernel32.GetModuleFileNameW(h, buf, 1024)
            return True, buf.value

    # Second: try to load it
    try:
        lib = ctypes.CDLL(dll_name)
        return True, dll_name
    except OSError as e:
        return False, str(e)


def _check_dlls() -> None:
    """Check critical DLLs and abort if any are missing."""
    _log("--- DLL Check ---")
    missing_critical = []

    for dll in _CRITICAL_DLLS:
        ok, info = _check_dll(dll)
        status = "OK" if ok else "MISSING"
        _log(f"  {dll}: {status} ({info})")
        if not ok:
            missing_critical.append(dll)

    for dll in _IMPORTANT_DLLS:
        ok, info = _check_dll(dll)
        status = "OK" if ok else "WARNING"
        _log(f"  {dll}: {status} ({info})")

    if missing_critical:
        dlls_str = "\n  • ".join(missing_critical)
        msg = (
            f"SQLiteManager failed to start: required DLL(s) not found.\n\n"
            f"Missing:\n  • {dlls_str}\n\n"
            f"This usually means:\n"
            f"  1. The '_internal' folder was deleted or moved\n"
            f"  2. Antivirus software quarantined application files\n"
            f"  3. The application was not extracted completely\n\n"
            f"Solutions:\n"
            f"  • Re-download and extract the full application package\n"
            f"  • Add the application folder to your antivirus exclusions\n"
            f"  • Install Visual C++ Redistributable 2015-2022 (x64):\n"
            f"    https://aka.ms/vs/17/release/vc_redist.x64.exe\n\n"
            f"Log: {_get_log_path()}"
        )
        _log(f"FATAL: Missing critical DLLs: {missing_critical}")
        _msgbox("Missing Dependencies", msg)
        sys.exit(1)


# ── Visual C++ Runtime check ──────────────────────────────────────────────────
def _check_vcruntime() -> None:
    """Verify VC Runtime 2015-2022 is available. Warn if not (non-fatal since bundled)."""
    _log("--- VC Runtime Check ---")
    vcrt_ok, vcrt_info = _check_dll("vcruntime140.dll")
    vcrt1_ok, vcrt1_info = _check_dll("vcruntime140_1.dll")

    if not vcrt_ok or not vcrt1_ok:
        _log("WARNING: VC Runtime not found in system. Relying on bundled copy.")
        # Non-fatal: PyInstaller bundles these in _internal/
    else:
        _log(f"  vcruntime140.dll: {vcrt_info}")
        _log(f"  vcruntime140_1.dll: {vcrt1_info}")


# ── Qt plugin path setup ──────────────────────────────────────────────────────
def _setup_qt_paths() -> None:
    """Ensure Qt can find its platform plugins before Qt initializes."""
    _log("--- Qt Path Setup ---")

    # In frozen bundle: _MEIPASS/_internal contains PySide6
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        qt_plugins = os.path.join(meipass, "PySide6", "plugins")
        if os.path.isdir(qt_plugins):
            os.environ["QT_PLUGIN_PATH"] = qt_plugins
            _log(f"  QT_PLUGIN_PATH set to: {qt_plugins}")

            platforms_dir = os.path.join(qt_plugins, "platforms")
            if os.path.isdir(platforms_dir):
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = platforms_dir
                _log(f"  QT_QPA_PLATFORM_PLUGIN_PATH: {platforms_dir}")

                qwindows = os.path.join(platforms_dir, "qwindows.dll")
                if os.path.exists(qwindows):
                    _log(f"  qwindows.dll: FOUND")
                else:
                    _log(f"  qwindows.dll: MISSING at {qwindows}")
        else:
            _log(f"  WARNING: Qt plugins dir not found at {qt_plugins}")

        # Add _MEIPASS and subfolders to DLL search path
        # os.add_dll_directory is NOT recursive.
        for sub in ["", "PySide6", "shiboken6"]:
            search_path = os.path.join(meipass, sub) if sub else meipass
            if os.path.isdir(search_path):
                try:
                    os.add_dll_directory(search_path)
                    _log(f"  Added to DLL search: {search_path}")
                except (AttributeError, OSError):
                    os.environ["PATH"] = search_path + os.pathsep + os.environ.get("PATH", "")
                    _log(f"  Prepended to PATH: {search_path}")


# ── Loaded modules report ─────────────────────────────────────────────────────
def _log_environment() -> None:
    """Write a full environment snapshot to startup.log."""
    import platform as plt

    _log("=== Startup Environment Report ===")
    _log(f"  App         : SQLiteManager")
    _log(f"  Python      : {sys.version}")
    _log(f"  Executable  : {sys.executable}")
    _log(f"  Frozen      : {getattr(sys, 'frozen', False)}")
    _log(f"  _MEIPASS    : {getattr(sys, '_MEIPASS', 'N/A')}")
    _log(f"  CWD         : {os.getcwd()}")
    _log(f"  OS          : {plt.platform()}")
    _log(f"  Architecture: {plt.architecture()}")
    _log(f"  Machine     : {plt.machine()}")
    _log(f"  Processor   : {plt.processor()}")
    _log(f"  PATH        : {os.environ.get('PATH', '')[:200]}...")
    _log(f"  QT_PLUGIN_PATH: {os.environ.get('QT_PLUGIN_PATH', 'not set')}")
    _log("=== End Environment Report ===")


# ── Public entry point ────────────────────────────────────────────────────────
def run_startup_diagnostics() -> None:
    """
    Run all startup checks. Call this at the very top of main.py,
    BEFORE importing PySide6 or any Qt module.
    """
    try:
        _log_environment()
        _check_architecture()
        _check_not_store_python()
        _setup_qt_paths()
        _check_dlls()
        _check_vcruntime()
        _log("Startup diagnostics: ALL CHECKS PASSED")
    except SystemExit:
        raise  # re-raise fatal exits
    except Exception as e:
        _log(f"Startup diagnostics error (non-fatal): {e}\n{traceback.format_exc()}")
