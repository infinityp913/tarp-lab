@echo off
cd /d "%~dp0"

echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo Python is not installed or not found.
    echo Please install it from: https://www.python.org/downloads/
    echo During installation, make sure to tick "Add Python to PATH".
    echo Then run this file again.
    echo.
    pause
    exit /b 1
)

echo Installing Python dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Setup failed. Please ask Ananth for help.
    echo.
    pause
    exit /b 1
)

echo Checking Node...
npm --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo Node/npm is not installed or not found.
    echo Install it from: https://nodejs.org/  (LTS version^)
    echo Then run this file again.
    echo.
    pause
    exit /b 1
)

echo Installing frontend dependencies...
cd frontend
call npm install
if errorlevel 1 (
    echo.
    echo Frontend install failed. Please ask Ananth for help.
    echo.
    cd /d "%~dp0"
    pause
    exit /b 1
)

echo Cleaning old build output...
if exist "..\backend\static" rmdir /s /q "..\backend\static"

echo Building frontend...
call npm run build
if errorlevel 1 (
    echo.
    echo Frontend build failed. Please ask Ananth for help.
    echo.
    cd /d "%~dp0"
    pause
    exit /b 1
)

if not exist "..\backend\static\index.html" (
    echo.
    echo Frontend build did not produce index.html ^(incomplete build^).
    echo The dashboard would show a blank page. Please ask Ananth for help.
    echo.
    cd /d "%~dp0"
    pause
    exit /b 1
)
cd /d "%~dp0"

echo.
echo Setup complete! You can now double-click start.bat to launch the dashboard.
echo.
pause
