@echo off
REM ============================================================
REM  release_build.bat — Full production release pipeline
REM
REM  Runs:
REM    1. Clean all artifacts
REM    2. Validate venv & dependencies
REM    3. PyInstaller onedir production build
REM    4. Create portable ZIP
REM    5. Run Inno Setup installer (if ISCC found)
REM    6. Report output files in releases\
REM ============================================================
setlocal EnableDelayedExpansion
title SQLite Manager - Release Build

echo.
echo  ============================================================
echo   SQLite Manager — Production Release Build
echo  ============================================================
echo.

REM ── Environment validation ───────────────────────────────────────────────────
set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo  [ERROR] .venv not found!
    echo  Create it: py -3.12 -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM Reject Microsoft Store Python
%PYTHON% -c "import sys; path=sys.executable.lower(); exit(1 if 'windowsapps' in path else 0)" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] Microsoft Store Python detected. Install CPython from python.org
    pause
    exit /b 1
)

REM Validate architecture is x64
%PYTHON% -c "import struct; exit(0 if struct.calcsize('P')*8==64 else 1)" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] Python is not 64-bit. Install Python 3.12 x64.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('%PYTHON% --version 2^>^&1') do echo  Python: %%v
echo.

REM ── Verify PyInstaller is installed ─────────────────────────────────────────
%PYTHON% -m PyInstaller --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [INFO] Installing PyInstaller...
    %PYTHON% -m pip install pyinstaller --quiet
)

REM ── Run full pipeline ────────────────────────────────────────────────────────
echo  [Release] Starting full release pipeline...
echo.
%PYTHON% scripts\build.py --all

echo.
if %ERRORLEVEL% EQU 0 (
    echo  ============================================================
    echo   [SUCCESS] Release build complete!
    echo  ============================================================
    echo.
    echo  Output files in releases\:
    dir /b releases\ 2>nul
    echo.
) else (
    echo  [FAILED] Release build failed with exit code %ERRORLEVEL%
)

pause
endlocal
