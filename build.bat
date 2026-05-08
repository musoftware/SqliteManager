@echo off
REM ============================================================
REM  build.bat — SQLite Manager Windows Build Script
REM  Usage:
REM    build.bat              -> Production one-dir build
REM    build.bat onefile      -> Single .exe
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

REM -- Python check: prefer .venv (Python 3.12) to avoid 3.14 bootloader issues
set PYTHON=python
if exist ".venv\Scripts\python.exe" set PYTHON=.venv\Scripts\python.exe

%PYTHON% --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] Python not found. Create venv: py -3.12 -m venv .venv
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('%PYTHON% --version 2^>^&1') do echo  Python: %%v

REM -- Parse argument
set "MODE=%~1"
if "%MODE%"=="" set "MODE=build"

if /i "%MODE%"=="clean" goto :do_clean
if /i "%MODE%"=="onefile" goto :do_onefile
if /i "%MODE%"=="debug" goto :do_debug
if /i "%MODE%"=="portable" goto :do_portable
if /i "%MODE%"=="installer" goto :do_installer
if /i "%MODE%"=="all" goto :do_all
if /i "%MODE%"=="nuitka" goto :do_nuitka
goto :do_build

:do_clean
echo  [Clean] Removing build artifacts...
python scripts\clean.py --full
goto :done

:do_build
echo  [Build] Production one-dir build...
python scripts\build.py
goto :done

:do_onefile
echo  [Build] Single-file executable...
python scripts\build.py --onefile
goto :done

:do_debug
echo  [Build] Debug build with console...
python scripts\build.py --debug
goto :done

:do_portable
echo  [Build] Production + Portable ZIP...
python scripts\build.py --portable
goto :done

:do_installer
echo  [Build] Production + Inno Setup Installer...
python scripts\build.py --installer
goto :done

:do_all
echo  [Build] Full release pipeline...
python scripts\build.py --all
goto :done

:do_nuitka
echo  [Build] Nuitka optimized build...
python -m pip install nuitka --quiet
python scripts\build.py --nuitka
goto :done

:done
echo.
if %ERRORLEVEL% EQU 0 (
    echo  [SUCCESS] Build completed successfully!
    echo  Output: dist\
) else (
    echo  [FAILED] Build failed with exit code %ERRORLEVEL%
)
echo.
pause
endlocal
