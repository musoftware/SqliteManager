@echo off
REM ============================================================
REM  build.bat — SQLite Manager Windows Build Script
REM
REM  Usage:
REM    build.bat              -> Production one-dir build
REM    build.bat onefile      -> Single .exe (less portable)
REM    build.bat debug        -> Debug build (console visible)
REM    build.bat portable     -> Build + create portable ZIP
REM    build.bat installer    -> Build + run Inno Setup
REM    build.bat all          -> Full release pipeline
REM    build.bat clean        -> Clean build artifacts
REM    build.bat nuitka       -> Nuitka optimized build
REM ============================================================

setlocal EnableDelayedExpansion
title SQLite Manager Build System

echo.
echo  ============================================================
echo   SQLite Manager Build System
echo  ============================================================
echo.

REM ── Prefer .venv Python (CPython 3.12 pinned) ────────────────────────────────
set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo  [WARN] .venv not found. Run: py -3.12 -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    echo  Falling back to system Python...
    set "PYTHON=python"
)

REM ── Validate Python is available ─────────────────────────────────────────────
%PYTHON% --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] Python not found!
    echo  Create venv: py -3.12 -m venv .venv
    pause
    exit /b 1
)

REM ── Reject Microsoft Store Python ────────────────────────────────────────────
%PYTHON% -c "import sys; path=sys.executable.lower(); exit(1 if 'windowsapps' in path else 0)" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] Microsoft Store Python detected!
    echo  Install CPython 3.12 from: https://www.python.org/downloads/
    echo  Then recreate venv: py -3.12 -m venv .venv
    pause
    exit /b 1
)

REM ── Show Python version ───────────────────────────────────────────────────────
for /f "tokens=*" %%v in ('%PYTHON% --version 2^>^&1') do echo  Python: %%v

REM ── Parse argument ────────────────────────────────────────────────────────────
set "MODE=%~1"
if "%MODE%"=="" set "MODE=build"

if /i "%MODE%"=="clean"     goto :do_clean
if /i "%MODE%"=="onefile"   goto :do_onefile
if /i "%MODE%"=="debug"     goto :do_debug
if /i "%MODE%"=="portable"  goto :do_portable
if /i "%MODE%"=="installer" goto :do_installer
if /i "%MODE%"=="all"       goto :do_all
if /i "%MODE%"=="nuitka"    goto :do_nuitka
goto :do_build

:do_clean
echo  [Clean] Removing build artifacts...
%PYTHON% scripts\clean.py --full
goto :done

:do_build
echo  [Build] Production one-dir build...
%PYTHON% scripts\build.py
goto :done

:do_onefile
echo  [Build] Single-file executable...
%PYTHON% scripts\build.py --onefile
goto :done

:do_debug
echo  [Build] Debug build with console...
%PYTHON% scripts\build.py --debug
goto :done

:do_portable
echo  [Build] Production + Portable ZIP...
%PYTHON% scripts\build.py --portable
goto :done

:do_installer
echo  [Build] Production + Inno Setup Installer...
%PYTHON% scripts\build.py --installer
goto :done

:do_all
echo  [Build] Full release pipeline...
%PYTHON% scripts\build.py --all
goto :done

:do_nuitka
echo  [Build] Nuitka optimized build...
%PYTHON% -m pip install nuitka --quiet
%PYTHON% scripts\build.py --nuitka
goto :done

:done
echo.
if %ERRORLEVEL% EQU 0 (
    echo  [SUCCESS] Build completed successfully
    echo  Output: dist\
) else (
    echo  [FAILED] Build failed with exit code %ERRORLEVEL%
)
echo.
pause
endlocal
