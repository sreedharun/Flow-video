@echo off
title Flow Video Studio
cd /d "%~dp0"

echo =======================================================
echo          FLOW VIDEO STUDIO - LOCAL AI AUTOMATION
echo =======================================================
echo.

REM 1. Verify Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not added to your Windows PATH.
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    echo Be sure to check the box "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM 2. Check Virtual Environment
if not exist "venv\Scripts\python.exe" (
    echo [*] Setting up virtual environment in .\venv
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [*] Virtual environment created successfully.
)

REM 3. Check Dependencies
if not exist "venv\.deps_installed" (
    echo [*] Installing required Python packages
    "%~dp0venv\Scripts\pip.exe" install --upgrade pip
    "%~dp0venv\Scripts\pip.exe" install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install requirements.
        pause
        exit /b 1
    )

    echo [*] Installing Playwright Chromium browser
    "%~dp0venv\Scripts\python.exe" -m playwright install chromium
    if errorlevel 1 (
        echo [ERROR] Failed to install Playwright Chromium.
        pause
        exit /b 1
    )

    type nul > "venv\.deps_installed"
    echo [*] Environment setup completed.
    echo.
)

REM 4. Launch Application Server
"%~dp0venv\Scripts\python.exe" server.py
if errorlevel 1 (
    echo.
    echo [ERROR] Server stopped with an error.
    pause
    exit /b 1
)

pause
