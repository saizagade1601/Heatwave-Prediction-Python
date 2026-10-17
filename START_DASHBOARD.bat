@echo off
REM ================================================================
REM   HeatGuard AI - double-click me!
REM   Opens the dashboard in your browser at http://localhost:5000
REM   First time only: installs the Python libraries (1-3 minutes).
REM   After that the server runs hidden in the background - no terminal.
REM   To stop it: click "Stop server" in the dashboard sidebar
REM               (or double-click STOP_DASHBOARD.bat).
REM ================================================================
cd /d "%~dp0"
title HeatGuard AI

set "PY="
python --version >nul 2>nul && set "PY=python"
if not defined PY py --version >nul 2>nul && set "PY=py"
if not defined PY (
    echo.
    echo   Python is not installed.
    echo   1. Download Python 3.12 from https://www.python.org/downloads/
    echo   2. In the installer TICK "Add python.exe to PATH"
    echo   3. Double-click START_DASHBOARD.bat again
    echo.
    pause
    exit /b
)

if not exist ".venv\setup_done.txt" (
    echo.
    echo   ==========================================================
    echo     HeatGuard AI - first-time setup (only happens once^)
    echo     Installing Flask, pandas, numpy, matplotlib, scikit-learn
    echo     Please wait 1-3 minutes and keep this window open...
    echo   ==========================================================
    echo.
    if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo.
        echo   Installation failed - check your internet connection and try again.
        pause
        exit /b
    )
    echo done> ".venv\setup_done.txt"
    echo.
    echo   Setup complete! Opening the dashboard in your browser...
    timeout /t 2 >nul
)

REM pythonw = Python WITHOUT a console window
start "" ".venv\Scripts\pythonw.exe" server.py
exit
