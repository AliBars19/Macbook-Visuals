@echo off
echo ========================================
echo   Building Apollova Setup.exe
echo ========================================
echo.

REM Use py launcher to target Python 3.11 specifically
REM Python 3.11 standalone (python.org) is required - NOT Windows Store Python
set PY=py -3.11

REM Check Python 3.11 is available
%PY% --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.11 standalone not found.
    echo.
    echo Please install Python 3.11 from:
    echo https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    echo.
    echo Make sure to check "Add to PATH" during installation.
    pause
    exit /b 1
)

echo Found:
%PY% --version
echo.

REM Install PyInstaller if needed
%PY% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    %PY% -m pip install pyinstaller
)

REM Clean previous build
echo Cleaning previous build...
rmdir /s /q build_temp 2>nul
del /q Setup.exe 2>nul

REM Absolute icon path
set "SCRIPT_DIR=%~dp0"
set "ICON_PATH=%SCRIPT_DIR%assets\icon.ico"

echo Building Setup.exe...
echo.

if exist "%ICON_PATH%" (
    %PY% -m PyInstaller ^
        --onefile ^
        --windowed ^
        --name "Setup" ^
        --icon "%ICON_PATH%" ^
        --collect-data tkinter ^
        --distpath "%SCRIPT_DIR%." ^
        --workpath "%SCRIPT_DIR%build_temp" ^
        --specpath "%SCRIPT_DIR%build_temp" ^
        --clean ^
        "%SCRIPT_DIR%setup.py"
) else (
    %PY% -m PyInstaller ^
        --onefile ^
        --windowed ^
        --name "Setup" ^
        --collect-data tkinter ^
        --distpath "%SCRIPT_DIR%." ^
        --workpath "%SCRIPT_DIR%build_temp" ^
        --specpath "%SCRIPT_DIR%build_temp" ^
        --clean ^
        "%SCRIPT_DIR%setup.py"
)

REM Cleanup
rmdir /s /q build_temp 2>nul

echo.
if exist "Setup.exe" (
    echo ========================================
    echo   Setup.exe created successfully!
    echo ========================================
) else (
    echo ========================================
    echo   ERROR: Setup.exe was not created.
    echo   Check the error messages above.
    echo ========================================
)
echo.
pause
