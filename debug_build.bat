@echo off
REM ============================================================
REM  debug_build.bat — Debug build (console window visible)
REM  Use this to diagnose startup/DLL/Qt issues in the EXE.
REM
REM  After launch, you'll see:
REM    - Python import errors
REM    - Missing DLL messages
REM    - Qt platform plugin errors
REM    - Traceback output
REM ============================================================
setlocal
title SQLite Manager - Debug Build

echo.
echo  ============================================================
echo   SQLite Manager — Debug Build
echo   Console window will be visible in the output EXE.
echo   Check dist\SQLiteManager\SQLiteManager.exe for errors.
echo  ============================================================
echo.

set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

%PYTHON% scripts\build.py --debug

if %ERRORLEVEL% EQU 0 (
    echo.
    echo  [OK] Debug build ready at: dist\SQLiteManager\SQLiteManager.exe
    echo  Run it from a terminal to see all output.
    echo.
    choice /c YN /m "Launch debug EXE now?"
    if %ERRORLEVEL% EQU 1 (
        start "" "dist\SQLiteManager\SQLiteManager.exe"
    )
) else (
    echo.
    echo  [FAILED] Debug build failed. Check output above.
)

echo.
pause
endlocal
