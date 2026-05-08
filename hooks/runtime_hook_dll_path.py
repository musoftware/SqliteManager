"""
hooks/runtime_hook_dll_path.py — PyInstaller Runtime Hook.

Executed by the PyInstaller bootloader BEFORE any Python imports.
Adds the _internal directory to the Windows DLL search path so that
python312.dll, Qt6Core.dll, and VC runtime DLLs are found correctly
even when the EXE is run from a different working directory.

This solves the classic PyInstaller 6.x issue:
    "Failed to load Python DLL 'python312.dll'"
"""
import os
import sys

# ── Add _internal to DLL search path (Windows 8+ API) ───────────────────────
# sys._MEIPASS is set by PyInstaller to the _internal/ unpacked folder path.
_meipass = getattr(sys, "_MEIPASS", None)
if _meipass and os.name == "nt":
    try:
        os.add_dll_directory(_meipass)
    except (AttributeError, OSError):
        # os.add_dll_directory requires Windows 8+ / Python 3.8+
        # Fallback: prepend to PATH
        os.environ["PATH"] = _meipass + os.pathsep + os.environ.get("PATH", "")

    # Also add the directory containing the EXE itself
    _exe_dir = os.path.dirname(sys.executable)
    if _exe_dir and _exe_dir != _meipass:
        try:
            os.add_dll_directory(_exe_dir)
        except (AttributeError, OSError):
            os.environ["PATH"] = _exe_dir + os.pathsep + os.environ.get("PATH", "")

    # Set Qt plugin path so platform plugins (qwindows.dll) are found
    _qt_plugins = os.path.join(_meipass, "PySide6", "plugins")
    if os.path.isdir(_qt_plugins):
        os.environ["QT_PLUGIN_PATH"] = _qt_plugins

    # Ensure Qt doesn't try to use system plugins
    os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH",
                          os.path.join(_qt_plugins, "platforms"))
