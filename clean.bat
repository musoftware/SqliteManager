@echo off
REM ============================================================
REM  clean.bat — Remove all build artifacts cleanly
REM ============================================================
setlocal
title SQLite Manager - Clean

echo.
echo  [Clean] Removing build artifacts...
echo.

set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

%PYTHON% scripts\clean.py --full

echo.
echo  [Done] Clean complete.
echo.
pause
endlocal
