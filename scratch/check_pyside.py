
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

def check_pyside6():
    print(f"Python version: {sys.version}")
    try:
        import PySide6
        print(f"PySide6 version: {PySide6.__version__}")
        print(f"PySide6 path: {PySide6.__file__}")
    except ImportError:
        print("PySide6 not installed")
        return

    datas, binaries, hidden = collect_all("PySide6")
    print(f"\nCollected {len(binaries)} binaries")
    
    core_found = False
    gui_found = False
    widgets_found = False
    
    for src, dest in binaries:
        name = Path(src).name.lower()
        if "qt6core.dll" in name:
            core_found = True
            print(f"Found Qt6Core: {src} -> {dest}")
        if "qt6gui.dll" in name:
            gui_found = True
            print(f"Found Qt6Gui: {src} -> {dest}")
        if "qt6widgets.dll" in name:
            widgets_found = True
            print(f"Found Qt6Widgets: {src} -> {dest}")
            
    if not core_found:
        print("MISSING: Qt6Core.dll in binaries")
    if not gui_found:
        print("MISSING: Qt6Gui.dll in binaries")
    if not widgets_found:
        print("MISSING: Qt6Widgets.dll in binaries")

if __name__ == "__main__":
    check_pyside6()
