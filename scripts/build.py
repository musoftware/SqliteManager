"""
scripts/build.py — Master Build Script for SQLite Manager.

Usage:
    python scripts/build.py                  # production one-dir build
    python scripts/build.py --onefile        # single .exe
    python scripts/build.py --debug          # debug console build
    python scripts/build.py --portable       # onefile + zip
    python scripts/build.py --installer      # trigger Inno Setup after build
    python scripts/build.py --nuitka         # Nuitka optimized build
    python scripts/build.py --all            # full release pipeline
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.version import VERSION, APP_NAME

# ── Python resolver: prefer .venv (CPython 3.12 pinned) ────────────────────
_VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
PYTHON = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else sys.executable


def validate_environment() -> None:
    """Validate Python environment before building."""
    banner("Validating build environment")
    import struct, platform as plt

    # Check architecture
    bits = struct.calcsize("P") * 8
    if bits != 64:
        print(f"  [ERROR] Python must be 64-bit. Got {bits}-bit.")
        sys.exit(1)
    print(f"  [OK] Architecture: {bits}-bit")

    # Check Python version
    vi = sys.version_info
    print(f"  [OK] Python {vi.major}.{vi.minor}.{vi.micro} ({sys.executable})")
    if vi.major != 3 or vi.minor < 10:
        print(f"  [WARN] Python 3.10+ recommended, got {vi.major}.{vi.minor}")

    # Reject Microsoft Store Python
    exe_lower = sys.executable.lower()
    if "windowsapps" in exe_lower:
        print("  [ERROR] Microsoft Store Python detected!")
        print("  Install CPython 3.12 (64-bit) from: https://www.python.org/downloads/")
        sys.exit(1)
    print("  [OK] Python installation: CPython (not Microsoft Store)")

    # Check PyInstaller
    try:
        result = subprocess.run([PYTHON, "-m", "PyInstaller", "--version"],
                                capture_output=True, text=True, check=True)
        print(f"  [OK] PyInstaller: {result.stdout.strip()}")
    except Exception:
        print("  [INFO] PyInstaller not found, installing...")
        run([PYTHON, "-m", "pip", "install", "pyinstaller>=6.0", "--quiet"])

    print("  [OK] Build environment validated")

DIST_DIR      = ROOT / "dist"
BUILD_DIR     = ROOT / "build"
RELEASES_DIR  = ROOT / "releases"
INSTALLER_DIR = ROOT / "installer"
ASSETS_DIR    = ROOT / "assets"
SPEC_FILE     = ROOT / "app.spec"
ICON          = ASSETS_DIR / "icons" / "app.ico"
EXE_NAME      = "SQLiteManager"
TIMESTAMP     = datetime.now().strftime("%Y%m%d_%H%M%S")


def banner(msg: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {msg}")
    print(f"{'=' * 60}")


def run(cmd: list[str], cwd: Path = ROOT, check: bool = True) -> int:
    print(f"  > {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if check and result.returncode != 0:
        print(f"\nERROR: Command failed with code {result.returncode}")
        sys.exit(result.returncode)
    return result.returncode


def check_tools() -> None:
    banner("Checking build tools")
    missing = []

    for tool in ["PyInstaller", "pip"]:
        try:
            result = subprocess.run(
                [PYTHON, "-m", tool, "--version"],
                capture_output=True, text=True, check=True
            )
            print(f"  [OK] {tool}: {result.stdout.strip()}")
        except Exception:
            # Fallback: check system PATH
            if shutil.which(tool.lower()):
                print(f"  [OK] {tool} (system)")
            else:
                missing.append(tool)

    if missing:
        print(f"\n  [WARN] Missing tools: {missing}")
        print("  Installing PyInstaller...")
        run([PYTHON, "-m", "pip", "install", "pyinstaller>=6.0", "--quiet"])


def clean(full: bool = False) -> None:
    banner("Cleaning build artifacts")
    for d in [BUILD_DIR, DIST_DIR]:
        if d.exists():
            shutil.rmtree(d)
            print(f"  Removed: {d}")
    for f in ROOT.glob("*.spec~"):
        f.unlink()
    if full:
        for f in ROOT.glob("**/__pycache__"):
            shutil.rmtree(f)
        print("  Cleaned __pycache__")


def update_version_info() -> None:
    """Dynamically update installer/version_info.txt with current version."""
    banner("Updating version info")
    from app.version import VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH, VERSION_BUILD
    vi_path = INSTALLER_DIR / "version_info.txt"
    content = vi_path.read_text()
    vt = f"({VERSION_MAJOR}, {VERSION_MINOR}, {VERSION_PATCH}, {VERSION_BUILD})"
    vs = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}.{VERSION_BUILD}"

    content = content.replace("(1, 0, 0, 0)", vt)
    content = content.replace("1.0.0.0", vs)
    vi_path.write_text(content)
    print(f"  Version info updated to {vs}")


def build_pyinstaller(onefile: bool = False, debug: bool = False) -> Path:
    banner(f"Building with PyInstaller (onefile={onefile}, debug={debug})")

    update_version_info()

    cmd = [
        PYTHON, "-m", "PyInstaller",
        str(SPEC_FILE),
        "--clean",
        "--noconfirm",
        "--log-level", "WARN" if not debug else "DEBUG",
    ]
    if onefile:
        cmd.append("--")
        cmd.append("--onefile")
    if debug:
        cmd.append("--debug")

    start = time.time()
    run(cmd)
    elapsed = time.time() - start
    print(f"\n  Build time: {elapsed:.1f}s")

    if onefile:
        exe_path = DIST_DIR / f"{EXE_NAME}.exe"
    else:
        exe_path = DIST_DIR / EXE_NAME / f"{EXE_NAME}.exe"

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n  [OK] Built: {exe_path}")
        print(f"       Size : {size_mb:.1f} MB")
    else:
        print(f"\n  [WARN] Expected exe not found at: {exe_path}")

    if not onefile:
        _post_build_verify(exe_path.parent)

    return exe_path


def _post_build_verify(dist_dir: Path) -> None:
    """Post-build DLL verification. Warns if critical DLLs are missing."""
    import sys as _sys
    banner("Post-build DLL verification")

    _internal = dist_dir / "_internal"
    py_ver = f"{_sys.version_info.major}{_sys.version_info.minor}"

    critical_checks = [
        # (search_dir, dll_name, description)
        (_internal,                                             f"python{py_ver}.dll", "Python runtime"),
        (_internal,                                             "vcruntime140.dll",    "VC Runtime 140"),
        (_internal / "PySide6",                                 "Qt6Core.dll",         "Qt6 Core"),
        (_internal / "PySide6",                                 "Qt6Gui.dll",          "Qt6 GUI"),
        (_internal / "PySide6",                                 "Qt6Widgets.dll",      "Qt6 Widgets"),
        (_internal / "PySide6" / "plugins" / "platforms",      "qwindows.dll",        "Qt Windows platform"),
        (_internal,                                             "python3.dll",         "Python3 stub DLL"),
    ]

    all_ok = True
    for search_dir, dll_name, desc in critical_checks:
        dll_path = search_dir / dll_name
        # Also search recursively in _internal for this dll
        found = list(dist_dir.rglob(dll_name)) if not dll_path.exists() else [dll_path]
        if found:
            print(f"  [OK] {desc} ({dll_name}): {found[0]}")
        else:
            print(f"  [WARN] {desc} ({dll_name}): NOT FOUND in dist!")
            all_ok = False

    # Belt-and-suspenders: copy python312.dll next to the EXE if it's only in _internal
    py_dll_name = f"python{py_ver}.dll"
    py_dll_root = dist_dir / py_dll_name
    py_dll_internal = _internal / py_dll_name
    if not py_dll_root.exists() and py_dll_internal.exists():
        try:
            shutil.copy2(py_dll_internal, py_dll_root)
            print(f"  [FIX] Copied {py_dll_name} to dist root (bootloader DLL fix)")
        except Exception as e:
            print(f"  [WARN] Could not copy {py_dll_name} to root: {e}")

    if all_ok:
        print("\n  All critical DLLs verified.")
    else:
        print("\n  WARNING: Some DLLs missing. EXE may fail on machines without Python!")
        print("  Check antivirus exclusions and re-run build if needed.")


def build_nuitka() -> None:
    banner("Building with Nuitka (optimized standalone)")
    # NOTE: --standalone is used instead of --onefile to avoid extraction issues.
    # --onefile in Nuitka extracts to a temp dir (similar to PyInstaller onefile)
    # which can be flagged by antivirus. Use --standalone for production.
    cmd = [
        PYTHON, "-m", "nuitka",
        "--standalone",
        "--enable-plugin=pyside6",
        "--enable-plugin=numpy",
        "--windows-disable-console",
        f"--windows-icon-from-ico={ICON}",
        f"--output-dir={DIST_DIR}",
        f"--output-filename={EXE_NAME}",
        "--company-name=SQLite Manager",
        f"--product-name={APP_NAME}",
        f"--product-version={VERSION}",
        "--copyright=Copyright 2025 SQLite Manager Team",
        "--assume-yes-for-downloads",
        # Include data files
        f"--include-data-dir={ASSETS_DIR}=assets",
        # Packages to include
        "--include-package=sqlalchemy",
        "--include-package=pandas",
        "--include-package=openpyxl",
        "--include-package=faker",
        "--include-package=reportlab",
        "--include-package=cryptography",
        "--include-package=pygments",
        "--include-package=sqlparse",
        "main.py",
    ]
    run(cmd)


def create_portable_zip(exe_path: Path | None = None) -> Path:
    banner("Creating portable ZIP")
    if exe_path is None:
        exe_path = DIST_DIR / EXE_NAME / f"{EXE_NAME}.exe"

    zip_name = f"{EXE_NAME}_v{VERSION}_Portable_{TIMESTAMP}.zip"
    zip_path = RELEASES_DIR / zip_name
    RELEASES_DIR.mkdir(exist_ok=True)

    src_dir = exe_path.parent if exe_path.is_file() and exe_path.parent.name == EXE_NAME else None

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        if src_dir and src_dir.exists():
            # One-dir: zip entire folder
            for f in src_dir.rglob("*"):
                if f.is_file():
                    arcname = Path(EXE_NAME) / f.relative_to(src_dir)
                    zf.write(f, arcname)
        elif exe_path.exists():
            # One-file: just the exe
            zf.write(exe_path, f"{EXE_NAME}/{exe_path.name}")

        # Add README
        readme = ROOT / "README.md"
        if readme.exists():
            zf.write(readme, f"{EXE_NAME}/README.md")

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  Portable ZIP: {zip_path} ({size_mb:.1f} MB)")
    return zip_path


def build_installer() -> None:
    banner("Building Inno Setup installer")
    iss_file = INSTALLER_DIR / "installer.iss"
    if not iss_file.exists():
        print("  [SKIP] installer.iss not found")
        return

    iscc = shutil.which("ISCC") or shutil.which("iscc")
    if not iscc:
        # Common Inno Setup paths
        for p in [
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            r"C:\Program Files\Inno Setup 6\ISCC.exe",
        ]:
            if Path(p).exists():
                iscc = p
                break

    if not iscc:
        print("  [SKIP] Inno Setup (ISCC) not found. Install from https://jrsoftware.org/isinfo.php")
        return

    run([iscc, str(iss_file)])

    # Move installer to releases/
    RELEASES_DIR.mkdir(exist_ok=True)
    for f in DIST_DIR.glob(f"*Setup*.exe"):
        dest = RELEASES_DIR / f"{EXE_NAME}_v{VERSION}_Setup.exe"
        shutil.move(str(f), str(dest))
        print(f"  Installer: {dest}")


def sign_executable(exe_path: Path, cert_file: str = "", password: str = "") -> None:
    """Code-sign the executable (requires signtool.exe + certificate)."""
    signtool = shutil.which("signtool")
    if not signtool:
        print("  [SKIP] signtool not found. Install Windows SDK for code signing.")
        return
    if not cert_file or not Path(cert_file).exists():
        print("  [SKIP] No certificate file provided.")
        return

    cmd = [
        signtool, "sign",
        "/f", cert_file,
        "/p", password,
        "/t", "http://timestamp.digicert.com",
        "/fd", "SHA256",
        "/v",
        str(exe_path),
    ]
    run(cmd, check=False)


def release_pipeline(portable: bool = True, installer: bool = True) -> None:
    """Full release: clean → build → zip → installer → sign (if cert available)."""
    banner(f"FULL RELEASE PIPELINE — v{VERSION}")
    start = time.time()

    clean()
    exe = build_pyinstaller(onefile=False)

    if portable:
        create_portable_zip(exe)

    if installer:
        build_installer()

    elapsed = time.time() - start
    banner(f"Release complete in {elapsed:.0f}s")
    print(f"  Version : {VERSION}")
    print(f"  Output  : {RELEASES_DIR}")
    for f in RELEASES_DIR.glob("*"):
        size = f.stat().st_size / (1024 * 1024)
        print(f"    {f.name}  ({size:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} Build System")
    parser.add_argument("--onefile",   action="store_true", help="Single-file executable")
    parser.add_argument("--debug",     action="store_true", help="Debug build with console")
    parser.add_argument("--portable",  action="store_true", help="Create portable ZIP")
    parser.add_argument("--installer", action="store_true", help="Build Inno Setup installer")
    parser.add_argument("--nuitka",    action="store_true", help="Use Nuitka instead of PyInstaller")
    parser.add_argument("--clean",     action="store_true", help="Clean only, don't build")
    parser.add_argument("--all",       action="store_true", help="Full release pipeline")
    parser.add_argument("--sign",      type=str, default="",  help="PFX cert path for signing")
    parser.add_argument("--sign-pass", type=str, default="",  help="Certificate password")
    args = parser.parse_args()

    validate_environment()
    check_tools()

    if args.clean:
        clean(full=True)
        return

    if args.all:
        release_pipeline(portable=True, installer=True)
        return

    if args.nuitka:
        build_nuitka()
        return

    exe = build_pyinstaller(onefile=args.onefile, debug=args.debug)

    if args.portable:
        create_portable_zip(exe)

    if args.installer:
        build_installer()

    if args.sign and exe.exists():
        sign_executable(exe, args.sign, args.sign_pass)


if __name__ == "__main__":
    main()
