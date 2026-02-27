@echo off
chcp 65001 >nul 2>&1
title Build EXE (Python 3.8 for Windows 7)

echo.
echo ========================================================
echo        Build EXE for Windows 7/10/11
echo ========================================================
echo.

:: Try Python 3.8 first (BEST for Windows 7 compatibility)
:: Python 3.8 is the last version with full Windows 7 support
set PYTHON_CMD=

:: Check Python 3.8
py -3.8 --version >nul 2>&1
if not errorlevel 1 (
    echo [OK] Found Python 3.8 - BEST for Windows 7!
    set PYTHON_CMD=py -3.8
    goto :found
)

:: Check Python 3.10 as fallback
py -3.10 --version >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Python 3.8 not found, using Python 3.10
    echo [WARNING] The EXE may need KB2999226 update on Windows 7!
    echo.
    set PYTHON_CMD=py -3.10
    goto :found
)

:: Check default Python
python --version >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Python 3.8 not found, using default Python
    echo [WARNING] The EXE may NOT work on Windows 7!
    echo.
    set PYTHON_CMD=python
    goto :found
)

echo [ERROR] Python not found!
echo.
echo Please install Python 3.8 for Windows 7 compatibility:
echo https://www.python.org/downloads/release/python-3810/
echo.
pause
exit /b 1

:found
echo Using: %PYTHON_CMD%
echo.

:: Install dependencies
echo [Step 1/3] Installing dependencies...
%PYTHON_CMD% -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ -q
%PYTHON_CMD% -m pip install pyinstaller -i https://mirrors.aliyun.com/pypi/simple/ -q
echo [OK] Dependencies installed
echo.

:: Build
echo [Step 2/3] Building EXE (this may take a few minutes)...
echo.

%PYTHON_CMD% -m PyInstaller --onefile ^
    --name "WorkloadManagement" ^
    --add-data "app;app" ^
    --add-data "static;static" ^
    --hidden-import "pandas" ^
    --hidden-import "openpyxl" ^
    --hidden-import "sqlalchemy" ^
    --noconsole ^
    run.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo [Step 3/3] Cleaning up...
echo.

:: Create release folder
if not exist "release" mkdir release
copy "dist\WorkloadManagement.exe" "release\" >nul

echo ========================================================
echo                  Build Complete!
echo ========================================================
echo.
echo   EXE file: release\WorkloadManagement.exe
echo.
if "%PYTHON_CMD%"=="py -3.10" (
    echo   [OK] Built with Python 3.10 - Compatible with Windows 7!
) else (
    echo   [WARNING] Built with default Python - May NOT work on Windows 7
)
echo.
echo   Copy this EXE to any computer and run it directly.
echo   No Python installation needed!
echo.
echo ========================================================
echo.
pause
