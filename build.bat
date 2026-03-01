@echo off
title WorkloadManagement - Build Tool

echo ============================================================
echo   WorkloadManagement - EXE Build Tool
echo ============================================================
echo.

:: Check Python 3.8
echo [Check] Detecting Python 3.8...

:: Method 1: Try py -3.8 (Python Launcher)
py -3.8 --version >nul 2>&1
if %errorlevel%==0 (
    set PYTHON_CMD=py -3.8
    set PIP_CMD=py -3.8 -m pip
    echo [OK] Found Python 3.8 via py launcher
    goto :found_python
)

:: Method 2: Try python3.8
python3.8 --version >nul 2>&1
if %errorlevel%==0 (
    set PYTHON_CMD=python3.8
    set PIP_CMD=python3.8 -m pip
    echo [OK] Found Python 3.8 via python3.8
    goto :found_python
)

:: Method 3: Try default python
python --version >nul 2>&1
if not %errorlevel%==0 (
    echo [ERROR] Python not found! Please install Python 3.8
    echo.
    echo Download: https://www.python.org/downloads/release/python-3810/
    pause
    exit /b 1
)

:: Check default python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo %PY_VER% | findstr /r "3\.8\." >nul
if %errorlevel%==0 (
    set PYTHON_CMD=python
    set PIP_CMD=pip
    echo [OK] Default Python is 3.8 (%PY_VER%)
    goto :found_python
)

:: Not Python 3.8, show warning
echo [WARN] Current Python is %PY_VER%, not 3.8
echo [WARN] Recommend using Python 3.8 for best compatibility
echo.
echo Press any key to continue, or Ctrl+C to cancel...
pause >nul
set PYTHON_CMD=python
set PIP_CMD=pip

:found_python
echo.
echo [Info] Using Python:
%PYTHON_CMD% --version
echo.

:: Check PyInstaller
%PYTHON_CMD% -c "import PyInstaller" >nul 2>&1
if not %errorlevel%==0 (
    echo [Install] Installing PyInstaller...
    %PIP_CMD% install pyinstaller
)

:: Install dependencies
echo [Check] Installing dependencies...
%PIP_CMD% install -r requirements.txt -q

:: Build
echo.
echo [Build] Starting build...
echo.
%PYTHON_CMD% build_exe.py

echo.
echo ============================================================
if not %errorlevel%==0 (
    echo [FAIL] Build failed! Check error messages above
) else (
    echo [DONE] Build successful!
    echo.
    echo Output: dist\WorkloadManagement.exe
    echo.
    echo Usage:
    echo   1. Copy all files in dist folder to target PC
    echo   2. Double click WorkloadManagement.exe
    echo   3. Open browser: http://localhost:5001
)
echo ============================================================
echo.
pause
